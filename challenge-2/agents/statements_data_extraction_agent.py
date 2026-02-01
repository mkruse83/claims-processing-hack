#!/usr/bin/env python3
"""
Statements Data Extraction Agent - Extracts structured data from insurance claim statement text.
Takes output from the OCR agent and converts it into structured JSON data.
Uses GPT-4o-mini to parse and organize text into insurance claim fields.

Usage:
    python statements_data_extraction_agent.py <ocr_result.json or ocr_text.txt>

Example with OCR JSON output:
    python statements_data_extraction_agent.py ../ocr_results/document_ocr_result.json

"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Azure AI Foundry SDK
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
# Use GPT-4o-mini for this agent
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")


def get_agent_instructions() -> str:
    """
    Generate agent instructions for extracting insurance claim statement data.

    Returns:
        Agent instruction string for statement data extraction
    """
    return """You are an expert at extracting structured data from insurance claim statement text.

**Your Task**:
Parse the provided text and extract information into the structured JSON format below.

**JSON Output Structure**:
{
  "document_type": "statement_front | statement_back",
  "extracted_text": "Complete raw text from the document",
  "policyholder_information": {
    "name": "Policy holder name",
    "address": "Full address",
    "phone": "Phone number",
    "email": "Email address",
    "policy_number": "Policy number",
    "claimant_id": "Claimant ID if present"
  },
  "vehicle_information": {
    "year": "Vehicle year",
    "make": "Vehicle make/manufacturer",
    "model": "Vehicle model",
    "color": "Vehicle color",
    "vin": "VIN number",
    "license_plate": "License plate number"
  },
  "accident_information": {
    "date_of_incident": "Date in YYYY-MM-DD format if possible",
    "time": "Time of incident",
    "location": "Location/address of incident",
    "is_us_territory": true | false | null
  },
  "description_of_incident": {
    "description": "Full incident description text",
    "is_date_match": true | false | null,
    "is_location_match": true | false | null,
    "has_witness": true | false,
    "is_own_fault": true | false | null,
    "is_third_party_fault": true | false | null,
    "vehicle_was_moving": true | false | null
  },
  "description_of_damages": [
    {
      "part_name": "Name of damaged part",
      "damage_description": "Description of damage",
      "severity": "minor | moderate | severe",
      "repair_or_replace": "repair | replace | unsure" // estimation if the part should be repaired or replaced
    }
  ],
  "witness_information": {
    "name": "Witness name",
    "phone": "Witness phone",
    "is_matching": true | false | null
  },
  "police_report": {
    "report_number": "Police report number",
    "police_department": "Police department name"
  },
  "signature": {
    "is_present": true | false,
    "printed_name": "Printed name on signature",
    "date": "Signature date",
    "is_date_within_a_week": true | false | null,
    "is_name_matching": true | false | null
  },
  "confidence": "high | medium | low",
  "notes": "Any additional notes or observations"
}

**Processing Rules**:
1. Extract all available information from the text
2. Use null for fields where information is not present or unclear
3. For boolean fields, use true/false if determinable, null if unclear
4. Preserve original text formatting in the "extracted_text" field
5. Be as accurate as possible with data extraction
6. Set confidence based on text clarity and completeness
7. Return ONLY valid JSON, no additional commentary

**Important**: 
- Your entire response must be valid JSON that can be parsed
- Do not include any text before or after the JSON object"""


def structure_ocr_to_json(
    ocr_text: str,
    source_file: Optional[str] = None,
    project_client=None,
    agent=None,
) -> dict:
    """
    Convert OCR text into structured JSON format using GPT-4o-mini agent.

    Args:
        ocr_text: The text to structure
        source_file: Optional path to the source file for metadata
        project_client: Optional existing AIProjectClient
        agent: Optional existing agent to reuse

    Returns:
        Structured JSON dictionary containing extracted claim information
    """
    response_text = ""

    try:
        logger.info(f"Processing text from: {source_file or 'unknown source'}")

        # Create client if not provided
        if project_client is None:
            logger.info("Creating AI Project Client...")
            project_client = AIProjectClient(
                endpoint=project_endpoint,
                credential=DefaultAzureCredential(),
            )

        # Get agent instructions
        agent_instructions = get_agent_instructions()

        # Create the agent
        agent = project_client.agents.create_version(
            agent_name="StatementsDataExtractionAgent",
            definition=PromptAgentDefinition(
                model=model_deployment_name,
                instructions=agent_instructions,
                temperature=0.1,  # Low temperature for consistent, factual structuring
            ),
        )

        logger.info(
            f"✅ Created Statements Data Extraction Agent: {agent.name} (version {agent.version})"
        )

        # Get OpenAI client for responses
        openai_client = project_client.get_openai_client()

        # Create user query
        user_query = f"""Please extract and structure the following text into the standardized JSON format.

---TEXT START---
{ocr_text}
---TEXT END---

Return only the structured JSON object."""

        logger.info("Sending text to agent...")

        # Get response from agent
        response = openai_client.responses.create(
            input=user_query,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )

        # Extract the JSON from response
        response_text = response.output_text.strip()

        # Try to parse the response as JSON
        # Remove markdown code fences if present
        if response_text.startswith("```"):
            # Find first { and last }
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx : end_idx + 1]

        structured_data = json.loads(response_text)

        # Add metadata
        structured_data["metadata"] = {
            "source_file": source_file or "unknown",
            "processing_timestamp": datetime.now().isoformat(),
            "agent_model": model_deployment_name,
            "original_text_length": len(ocr_text),
        }

        logger.info("✓ Successfully structured text into JSON")
        return structured_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response as JSON: {e}")
        # Return error structure
        raw_response_value = response_text or "No response"
        return {
            "error": "JSON parsing failed",
            "error_details": str(e),
            "raw_response": raw_response_value,
            "metadata": {
                "source_file": source_file or "unknown",
                "processing_timestamp": datetime.now().isoformat(),
                "agent_model": model_deployment_name,
            },
        }

    except Exception as e:
        logger.error(f"Error in JSON structuring: {e}")
        return {
            "error": "Processing failed",
            "error_details": str(e),
            "metadata": {
                "source_file": source_file or "unknown",
                "processing_timestamp": datetime.now().isoformat(),
            },
        }


def process_ocr_result(ocr_result_json: str) -> dict:
    """
    Process an OCR result JSON string and structure its text content.

    Args:
        ocr_result_json: JSON string from OCR agent output

    Returns:
        Structured JSON dictionary
    """
    try:
        # Parse OCR result
        ocr_data = json.loads(ocr_result_json)

        if ocr_data.get("status") != "success":
            return {
                "error": "OCR processing failed",
                "ocr_error": ocr_data.get("error", "Unknown error"),
                "metadata": {
                    "source_file": ocr_data.get("file_path", "unknown"),
                    "processing_timestamp": datetime.now().isoformat(),
                },
            }

        # Extract OCR text and metadata
        ocr_text = ocr_data.get("text", "")
        source_file = ocr_data.get("file_path")

        if not ocr_text:
            return {
                "error": "No text extracted from OCR",
                "metadata": {
                    "source_file": source_file or "unknown",
                    "processing_timestamp": datetime.now().isoformat(),
                },
            }

        # Structure the OCR text
        return structure_ocr_to_json(ocr_text, source_file)

    except json.JSONDecodeError as e:
        return {
            "error": "Invalid OCR result JSON",
            "error_details": str(e),
            "metadata": {"processing_timestamp": datetime.now().isoformat()},
        }


def main():
    """Main function to create and test the Statements Data Extraction Agent."""

    print("=== Statements Data Extraction Agent with GPT-4o-mini ===\n")

    try:
        # Get input from CLI args
        if len(sys.argv) < 2:
            print(
                "Usage: python statements_data_extraction_agent.py <ocr_text_file_or_json>"
            )
            print("\nExample with OCR JSON result:")
            print("  python statements_data_extraction_agent.py ocr_result.json")
            print("\nExample with raw text file:")
            print("  python statements_data_extraction_agent.py extracted_text.txt")
            return

        input_file = sys.argv[1]

        if not os.path.exists(input_file):
            print(f"❌ Error: File not found: {input_file}")
            return

        print(f"📄 Processing file: {input_file}\n")

        # Create AI Project Client
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )

        with project_client:
            # Generate agent instructions
            agent_instructions = get_agent_instructions()

            # Create the agent
            agent = project_client.agents.create_version(
                agent_name="StatementsDataExtractionAgent",
                definition=PromptAgentDefinition(
                    model=model_deployment_name,
                    instructions=agent_instructions,
                    temperature=0.1,
                ),
            )

            print(
                f"✅ Created Statements Data Extraction Agent: {agent.name} (version {agent.version})"
            )
            print("   Agent visible in Foundry portal\n")

            # Read input file
            with open(input_file, "r") as f:
                file_content = f.read()

            # Check if it's OCR JSON result or raw text
            is_ocr_json = False
            ocr_text = ""
            source_file = input_file

            try:
                # Try to parse as JSON (OCR result)
                ocr_data = json.loads(file_content)
                if "text" in ocr_data and "status" in ocr_data:
                    is_ocr_json = True
                    if ocr_data.get("status") == "success":
                        ocr_text = ocr_data.get("text", "")
                        source_file = ocr_data.get("file_path", input_file)
                    else:
                        print(
                            f"❌ OCR failed: {ocr_data.get('error', 'Unknown error')}"
                        )
                        return
                else:
                    # JSON but not OCR format, treat as raw text
                    ocr_text = file_content
            except json.JSONDecodeError:
                # Not JSON, treat as raw text
                ocr_text = file_content

            print(f"   Type: {'OCR JSON result' if is_ocr_json else 'Raw text'}")
            print(f"   Text length: {len(ocr_text)} characters\n")

            # Get OpenAI client
            openai_client = project_client.get_openai_client()

            # Create user query
            user_query = f"""Please extract and structure the following text into the standardized JSON format.

---TEXT START---
{ocr_text}
---TEXT END---

Return only the structured JSON object."""

            print("🤖 Sending to agent for data extraction...")

            # Get response from agent
            response = openai_client.responses.create(
                input=user_query,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )

            # Extract and parse response
            response_text = response.output_text.strip()

            # Remove markdown code fences if present
            if response_text.startswith("```"):
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    response_text = response_text[start_idx : end_idx + 1]

            try:
                result = json.loads(response_text)

                # Add metadata
                result["metadata"] = {
                    "source_file": source_file,
                    "processing_timestamp": datetime.now().isoformat(),
                    "agent_model": model_deployment_name,
                    "original_text_length": len(ocr_text),
                }

                # Output results
                print("\n=== Structured JSON Output ===")
                print(json.dumps(result, indent=2))

                # Save to output file
                output_file = input_file.rsplit(".", 1)[0] + "_structured.json"
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)

                print(f"\n✓ Structured JSON saved to: {output_file}")

                # Summary
                print("\n📊 Summary:")
                print(f"   Document type: {result.get('document_type', 'unknown')}")
                print(f"   Confidence: {result.get('confidence', 'unknown')}")

                if result.get("policyholder_information", {}).get("name"):
                    print(
                        f"   Policy holder: {result['policyholder_information']['name']}"
                    )
                if result.get("accident_information", {}).get("date_of_incident"):
                    print(
                        f"   Incident date: {result['accident_information']['date_of_incident']}"
                    )

                print("\n✓ Statements Data Extraction Agent completed successfully!")

            except json.JSONDecodeError as e:
                print(f"\n❌ Failed to parse agent response as JSON: {e}")
                print(f"Raw response:\n{response_text}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        print(f"❌ Error: {e}")
        import traceback

        print(f"\nStack trace:\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
