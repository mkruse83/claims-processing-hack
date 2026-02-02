#!/usr/bin/env python3
"""
Policy Evaluation Agent

Takes the structured JSON output from `statements_data_extraction_agent.py`,
searches for matching insurance policies in Azure AI Search, and then uses an
LLM (GPT-4o-mini via Azure AI Foundry) to:

- Select the best matching policy (if any)
- Estimate liability under that policy
- Decide whether the claim appears valid under the policy terms

The agent appends this information under a new `policy_evaluation` field in the
input JSON and returns the enriched JSON.

Usage:
    python policy_evaluation_agent.py <structured_claim_json>

Environment variables required for Azure AI Projects:
    AI_FOUNDRY_PROJECT_ENDPOINT   - Azure AI Foundry project endpoint
    MODEL_DEPLOYMENT_NAME         - (optional) model deployment name, defaults to 'gpt-4o-mini'

Environment variables required for Azure AI Search:
    AZURE_SEARCH_ENDPOINT         - e.g. https://<search-service>.search.windows.net
    AZURE_SEARCH_INDEX_NAME       - name of the index containing policy documents
    AZURE_SEARCH_API_KEY          - admin or query key for the search service

The Azure AI Search index is expected to contain policy documents similar to the
sample markdown policies in `challenge-0/data/policies/*.md`. Field names are
not strictly enforced; the agent will see the full document JSON.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

# Azure AI Foundry SDK
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    AzureAISearchAgentTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
    AzureAISearchIndex,
)
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure AI Foundry configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")

"""Environment variables for Azure AI Search as agent knowledge.

We do NOT call the Azure Search SDK for documents directly. Instead, we
attach an Azure AI Search index asset in the Azure AI Foundry project
as knowledge for the agent via `AzureAISearchAgentTool`.

Auto-created index asset (preferred):
    AZURE_AI_CONNECTION_ID    - Full resource ID of the Cognitive Search
                                connection in the Azure AI Project.
    AI_SEARCH_INDEX_NAME      - Name of the Azure AI Search index in the
                                connected search service.
    AI_SEARCH_INDEX_ASSET_NAME- (optional) name for the Index asset in the
                                project, defaults to AI_SEARCH_INDEX_NAME.
    AI_SEARCH_INDEX_VERSION   - (optional) Index asset version, defaults
                                to "1".
"""
azure_ai_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")
ai_search_index_name = os.environ.get(
    "AI_SEARCH_INDEX_NAME", "insurance-documents-index"
)
ai_search_index_asset_name = os.environ.get(
    "AI_SEARCH_INDEX_ASSET_NAME", ai_search_index_name
)
ai_search_index_version = os.environ.get("AI_SEARCH_INDEX_VERSION", "1")


def get_policy_evaluation_agent_instructions() -> str:
    """Return instructions for the policy evaluation agent.

    The agent receives structured claim JSON from statements_data_extraction_agent
    and has direct access to the policy index in Azure AI Search as a
    knowledge source via the `azure_ai_search` tool.

    It must:
        - Use the Azure AI Search tool to retrieve the most relevant policy
            documents for the claim
        - Decide which policy (if any) best matches the claim
        - Estimate liability (who is at fault, coverage, etc.)
        - Decide if the claim appears valid under the matched policy
        - Return ONLY a JSON object for the `policy_evaluation` field
    """

    return """You are an experienced insurance claims adjuster.

You will be given a structured JSON object called `claim_data` representing
an auto insurance claim, already extracted from a handwritten or scanned
statement.

You also have access to an Azure AI Search tool that is already attached to
an index containing insurance policy documents (for example, commercial auto
liability, comprehensive, high value vehicle policies, etc.). Use that tool
to retrieve whatever policy content you need in order to make a grounded
decision.

Your task:
- Carefully read `claim_data`.
- Use the Azure AI Search tool to look up the most relevant policy documents
    for this claim.
- Identify the single best matching policy for this claim (if any).
- Using both the claim details and the retrieved policy text, estimate whether
    the loss is covered, who is likely liable, and whether the claim appears
    valid.

You MUST output a single JSON object with the following structure, representing
ONLY the value of a new top-level field `policy_evaluation` that will be added
onto `claim_data` by the calling application:

{
  "matched_policy": {
    "id": "Policy identifier or null if unknown",
    "title": "Short human-readable policy name or null",
    "score": 0.0,
    "summary": "Short summary of the relevant policy coverage in your own words",
    "raw_document_reference": "Optional short identifier for the matched document or null"
  },
  "coverage_assessment": {
    "coverage_applicability": "covered | partially_covered | not_covered | unclear",
    "estimated_company_liability_amount": 0,
    "deductible_applicable": true,
    "deductible_amount": 0,
    "limits_may_be_exceeded": false,
    "relevant_policy_sections": "Short description of which parts of the policy matter here"
  },
  "liability_assessment": {
    "at_fault_party": "policyholder | third_party | shared | unclear",
    "estimated_fault_split": {
      "policyholder_percent": 0,
      "third_party_percent": 0
    },
    "key_factors": "Brief explanation of why you assigned fault this way"
  },
  "claim_validity": {
    "is_claim_valid": true,
    "primary_reasons": "Short explanation of why the claim is or is not valid",
    "confidence": "high | medium | low"
  },
  "notes": "Any additional expert notes that could help a human adjuster review this case"
}

Important rules:
- Use numeric values for amounts and percentages when possible. Use 0 if unknown.
- Use null where information is genuinely not available.
- Be conservative: if policy coverage is ambiguous, prefer `unclear` with explanation.
- Do NOT repeat the entire claim JSON. Do NOT include any keys other than those
  shown above at the top level of your response.
- Your entire response must be valid JSON and must represent exactly the
  `policy_evaluation` object (no surrounding quotes or extra text).
"""


def _get_connection_name_from_id(connection_id: str) -> str:
    """Extract the connection *name* from a full connection resource ID.

    AZURE_AI_CONNECTION_ID is typically of the form:

        /subscriptions/.../resourceGroups/.../providers/...
            /accounts/<hub>/connections/<connection-name>
    """

    if "/connections/" in connection_id:
        return connection_id.split("/connections/")[-1]
    return connection_id


def ensure_ai_search_index_asset(project_client: AIProjectClient) -> str:
    if not azure_ai_connection_id:
        raise RuntimeError(
            "AZURE_AI_CONNECTION_ID is not set; cannot create Azure AI Search index asset.",
        )

    connection_name = _get_connection_name_from_id(azure_ai_connection_id)

    # First, try to reuse an existing Index asset with the requested
    # name/version. If it does not exist, we create it.
    try:
        existing_index = project_client.indexes.get(
            name=ai_search_index_asset_name,
            version=ai_search_index_version,
        )
        asset_id = (
            existing_index.id
            or f"{ai_search_index_asset_name}/versions/{ai_search_index_version}"
        )
        logger.info(
            "Using existing Azure AI Search index asset '%s' version '%s' (id=%s)",
            existing_index.name,
            existing_index.version,
            asset_id,
        )
        return asset_id
    except ResourceNotFoundError:
        logger.info(
            "Azure AI Search index asset '%s' (version %s) not found; creating it.",
            ai_search_index_asset_name,
            ai_search_index_version,
        )

    index_definition = AzureAISearchIndex(
        connection_name=connection_name,
        index_name=ai_search_index_name,
    )

    created_index = project_client.indexes.create_or_update(
        name=ai_search_index_asset_name,
        version=ai_search_index_version,
        index=index_definition,
    )

    asset_id = (
        created_index.id
        or f"{ai_search_index_asset_name}/versions/{ai_search_index_version}"
    )
    logger.info(
        "Created Azure AI Search index asset '%s' version '%s' (id=%s)",
        created_index.name,
        created_index.version,
        asset_id,
    )
    return asset_id


def evaluate_policy_and_liability(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """Call GPT-4o-mini via Azure AI Projects to build `policy_evaluation`.

    Returns the full enriched claim JSON with a new `policy_evaluation` field.
    """

    if not project_endpoint:
        raise RuntimeError(
            "AI_FOUNDRY_PROJECT_ENDPOINT is not set; cannot create policy evaluation agent."
        )

    logger.info(
        "Creating Policy Evaluation Agent with GPT model '%s'", model_deployment_name
    )

    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )

    with project_client:
        index_asset_id = ensure_ai_search_index_asset(project_client)

        agent_instructions = get_policy_evaluation_agent_instructions()

        index_resource = AISearchIndexResource(
            index_asset_id=index_asset_id,
            top_k=5,
            query_type="semantic",
        )

        search_tool_resource = AzureAISearchToolResource(indexes=[index_resource])

        search_tool = AzureAISearchAgentTool(azure_ai_search=search_tool_resource)

        agent = project_client.agents.create_version(
            agent_name="PolicyEvaluationAgent",
            definition=PromptAgentDefinition(
                model=model_deployment_name,
                instructions=agent_instructions,
                temperature=0.1,
                tools=[search_tool],
            ),
        )

        logger.info(
            "Created Policy Evaluation Agent: %s (version %s)",
            agent.name,
            agent.version,
        )

        openai_client = project_client.get_openai_client()

        user_query = {
            "role": "user",
            "content": """Using the instructions you were given, generate ONLY the `policy_evaluation` JSON object.

Here is the structured claim data as JSON:

```json
%s
```

Use your attached Azure AI Search tool to retrieve any relevant policy
documents needed to evaluate coverage, liability, and claim validity.

Remember: respond with ONLY the JSON object for `policy_evaluation` and
nothing else."""
            % (json.dumps(claim_data, indent=2)),
        }

        logger.info(
            "Sending claim and policy search results to Policy Evaluation Agent"
        )

        response = openai_client.responses.create(
            input=[user_query],
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )

        response_text = response.output_text.strip()

        # Strip markdown fences if present
        if response_text.startswith("```"):
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx : end_idx + 1]

        try:
            policy_eval = json.loads(response_text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse policy_evaluation JSON: %s", exc)
            # Fallback minimal structure so downstream code still works
            policy_eval = {
                "matched_policy": {
                    "id": None,
                    "title": None,
                    "score": 0.0,
                    "summary": "Policy evaluation agent failed to return valid JSON.",
                    "raw_document_reference": None,
                },
                "coverage_assessment": {
                    "coverage_applicability": "unclear",
                    "estimated_company_liability_amount": 0,
                    "deductible_applicable": False,
                    "deductible_amount": 0,
                    "limits_may_be_exceeded": False,
                    "relevant_policy_sections": "No details; parsing error.",
                },
                "liability_assessment": {
                    "at_fault_party": "unclear",
                    "estimated_fault_split": {
                        "policyholder_percent": 0,
                        "third_party_percent": 0,
                    },
                    "key_factors": "Could not parse LLM response.",
                },
                "claim_validity": {
                    "is_claim_valid": None,
                    "primary_reasons": "LLM response could not be parsed.",
                    "confidence": "low",
                },
                "notes": "This object was generated by a fallback handler after JSON parsing failed.",
                "_raw_response": response_text,
            }

        # Attach evaluation to claim data
        enriched = dict(claim_data)
        enriched["policy_evaluation"] = policy_eval

        # Add/augment metadata
        metadata = enriched.get("metadata", {}) or {}
        metadata.setdefault("processing_timestamp", datetime.now().isoformat())
        metadata.setdefault("agent_model", model_deployment_name)
        metadata["policy_evaluation_agent"] = {
            "name": "PolicyEvaluationAgent",
            "version": agent.version,
            "ai_search_index_asset_id": index_asset_id,
        }
        enriched["metadata"] = metadata

        return enriched


def load_claim_json(path: str) -> Dict[str, Any]:
    """Load structured claim JSON from a file."""

    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_enriched_claim_json(path: str, data: Dict[str, Any]) -> str:
    """Save enriched claim JSON next to the input file.

    Returns the output file path.
    """

    base, ext = os.path.splitext(path)
    output_path = base + "_with_policy_evaluation" + (ext or ".json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return output_path


def main() -> None:
    """CLI entrypoint for the Policy Evaluation Agent."""

    print("=== Policy Evaluation Agent ===\n")

    if len(sys.argv) < 2:
        print("Usage: python policy_evaluation_agent.py <structured_claim_json>")
        print("\nExample (using output from statements_data_extraction_agent):")
        print(
            "  python policy_evaluation_agent.py ../ocr_results/crash1_front_ocr_result_structured.json",
        )
        sys.exit(1)

    input_path = sys.argv[1]
    logger.info("Loading structured claim JSON from %s", input_path)

    try:
        claim_data = load_claim_json(input_path)
    except Exception as exc:
        logger.error("Failed to load input JSON: %s", exc)
        print(f"❌ Failed to load input JSON: {exc}")
        sys.exit(1)

    # Have the LLM, with Azure AI Search attached as knowledge, estimate
    # liability and claim validity and select the relevant policy.
    try:
        enriched_claim = evaluate_policy_and_liability(claim_data)
    except Exception as exc:  # pragma: no cover - network/SDK errors
        logger.error("Policy evaluation failed: %s", exc)
        print(f"❌ Policy evaluation failed: {exc}")
        sys.exit(1)

    # Step 3: save and print results
    output_path = save_enriched_claim_json(input_path, enriched_claim)

    print("\n=== Enriched Claim JSON (with policy_evaluation) ===")
    print(json.dumps(enriched_claim, indent=2))

    print(f"\n✓ Enriched JSON saved to: {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
