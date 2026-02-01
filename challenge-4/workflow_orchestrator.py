#!/usr/bin/env python3
"""
Claims Processing Multi-Agent Workflow
Orchestrates OCR Agent and OCR Text Extraction Agent using sequential processing
"""

import os
import sys
import json
import logging
import asyncio
from dotenv import load_dotenv

# Import the OCR and JSON structuring functions from challenge-2
# Handle both local development and container deployment paths
if os.path.exists(
    os.path.join(os.path.dirname(__file__), "..", "challenge-2", "agents")
):
    # Local development: challenge-2 is a sibling directory
    sys.path.append(
        os.path.join(os.path.dirname(__file__), "..", "challenge-2", "agents")
    )
else:
    # Container deployment: challenge-2 is in the same directory as the app
    sys.path.append(os.path.join(os.path.dirname(__file__), "challenge-2", "agents"))
from ocr_agent import extract_text_with_ocr
from statements_data_extraction_agent import process_ocr_result
from policy_evaluation_agent import evaluate_policy_and_liability

# Load environment
load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ENDPOINT = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME = os.environ.get("MODEL_DEPLOYMENT_NAME")


async def process_claim_workflow(image_path: str) -> dict:
    """Multi-agent workflow that orchestrates OCR, JSON structuring, and
    policy evaluation.

    Args:
        image_path: Path to the claim image file

    Returns:
        Structured and policy-enriched claim data as dictionary
    """
    logger.info(f"🔄 Starting claims processing workflow for: {image_path}")

    # Step 1: OCR Agent - Extract text from image
    logger.info("📸 Step 1: OCR Agent - Extracting text from image...")
    ocr_result_json = extract_text_with_ocr(image_path)
    ocr_result = json.loads(ocr_result_json)

    if ocr_result.get("status") == "error":
        logger.error(f"OCR failed: {ocr_result.get('error')}")
        return {
            "error": "OCR processing failed",
            "details": ocr_result.get("error"),
            "image_path": image_path,
        }

    ocr_text = ocr_result.get("text", "")
    logger.info(f"✅ OCR Agent extracted {len(ocr_text)} characters")

    # Step 2: Statements Data Extraction Agent - Convert OCR result to structured JSON
    logger.info(
        "📊 Step 2: Statements Data Extraction Agent - Converting OCR output to structured JSON..."
    )

    # Use the existing challenge-2 statements data extraction agent
    structured_data = process_ocr_result(ocr_result_json)

    # Ensure metadata exists and augment with workflow-specific details
    if not isinstance(structured_data, dict):
        logger.error("Statements Data Extraction Agent returned non-dict result")
        return {
            "error": "Invalid result from statements data extraction agent",
            "details": str(structured_data),
        }

    metadata = structured_data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    metadata.update(
        {
            "source_image": image_path,
            "ocr_characters": len(ocr_text),
            "workflow": "multi-agent",
        }
    )
    structured_data["metadata"] = metadata

    logger.info(
        "✅ Successfully processed OCR output with Statements Data Extraction Agent"
    )

    # Step 3: Policy Evaluation Agent - Attach policy coverage and liability assessment
    logger.info(
        "📑 Step 3: Policy Evaluation Agent - Evaluating policy coverage and liability..."
    )

    try:
        enriched_claim = evaluate_policy_and_liability(structured_data)
    except Exception as exc:  # pragma: no cover - network/SDK errors
        logger.error("Policy evaluation failed: %s", exc)
        return {
            "error": "Policy evaluation failed",
            "details": str(exc),
            "partial_result": structured_data,
        }

    logger.info("✅ Successfully evaluated policy and liability")
    return enriched_claim


async def main():
    """Test the workflow with a sample image"""
    if len(sys.argv) < 2:
        print("Usage: python workflow_orchestrator.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"❌ Error: Image not found: {image_path}")
        sys.exit(1)

    # Run workflow
    result = await process_claim_workflow(image_path)

    print("\n" + "=" * 60)
    print("📊 WORKFLOW OUTPUT")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
