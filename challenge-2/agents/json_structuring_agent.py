#!/usr/bin/env python3
"""
JSON Structuring Agent - Converts OCR text into structured JSON format.
Uses GPT-4.1-mini to parse OCR results and create structured claim data.

Usage:
    python json_structuring_agent.py <ocr_result.json or ocr_text.txt>
    
Example with OCR JSON output:
    python json_structuring_agent.py ../ocr_results/crash1_front_ocr_result.json
    
"""
import os
import sys
import json
import logging
from datetime import datetime
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


def get_agent_instructions(vehicle_side: str = None) -> str:
    """
    Generate agent instructions based on detected vehicle side.
    
    Args:
        vehicle_side: 'front', 'back', or None for general instructions
        
    Returns:
        Agent instruction string
    """
    # Build side-specific requirements
    if vehicle_side == "front":
        side_specific_fields = """
  "vehicle_side": "front",
  "front_specific": {
    "windshield_damage": "intact | cracked | shattered | null",
    "front_bumper_damage": "none | scratched | dented | detached | null",
    "headlights_damage": "intact | cracked | broken | missing | null",
    "hood_damage": "none | scratched | dented | buckled | null",
    "grille_damage": "intact | damaged | missing | null",
    "license_plate_visible": true or false,
    "front_damage_severity": "none | minor | moderate | severe"
  },"""
        side_requirements = """\n**FRONT PHOTO REQUIREMENTS**:
- MUST extract windshield condition (intact/cracked/shattered)
- MUST assess front bumper damage level
- MUST check headlight condition (both left and right if visible)
- MUST evaluate hood damage
- MUST note if license plate is visible and readable
- MUST provide overall front damage severity rating"""
    elif vehicle_side == "back":
        side_specific_fields = """
  "vehicle_side": "back",
  "back_specific": {
    "rear_windshield_damage": "intact | cracked | shattered | null",
    "rear_bumper_damage": "none | scratched | dented | detached | null",
    "taillights_damage": "intact | cracked | broken | missing | null",
    "trunk_damage": "none | scratched | dented | buckled | null",
    "exhaust_damage": "intact | damaged | detached | null",
    "license_plate_visible": true or false,
    "rear_damage_severity": "none | minor | moderate | severe"
  },"""
        side_requirements = """\n**BACK PHOTO REQUIREMENTS**:
- MUST extract rear windshield condition (intact/cracked/shattered)
- MUST assess rear bumper damage level
- MUST check taillight condition (both left and right if visible)
- MUST evaluate trunk/hatchback damage
- MUST note if rear license plate is visible and readable
- MUST provide overall rear damage severity rating"""
    else:
        side_specific_fields = """
  "vehicle_side": "unspecified","""
        side_requirements = """\n**GENERAL PHOTO**:
- Extract any visible damage information
- Note which parts of vehicle are visible in the image"""
    
    return f"""You are an expert document structuring assistant specialized in converting OCR text from insurance claims documents into structured JSON format.

**Your Task**:
Extract and structure information from OCR text into a standardized JSON format for insurance claims processing.

**JSON Output Structure**:
{{{side_specific_fields}
  "document_type": "claim_form | damage_photo | policy_document | statement",
  "extracted_data": {{
    "policy_holder": {{
      "name": "extracted name or null",
      "policy_number": "extracted policy number or null"
    }},
    "incident": {{
      "date": "YYYY-MM-DD or null",
      "type": "vehicle_collision | theft | vandalism | weather | fire | other",
      "description": "brief description or null",
      "location": "location if mentioned or null"
    }},
    "damages": {{
      "description": "damage description",
      "estimated_amount": numeric_amount or null,
      "currency": "USD or other",
      "items": [
        {{
          "part": "part name",
          "cost": numeric_cost or null
        }}
      ]
    }},
    "vehicle_info": {{
      "make": "manufacturer or null",
      "model": "model or null",
      "year": numeric_year or null,
      "license_plate": "plate number or null",
      "vin": "VIN if present or null"
    }},
    "contact_info": {{
      "phone": "phone number or null",
      "email": "email or null",
      "address": "address or null"
    }},
    "additional_details": "any other relevant information"
  }},
  "confidence": "high | medium | low",
  "extraction_notes": "notes about the extraction quality or missing information"
}}{side_requirements}

**Processing Rules**:
1. Extract all available information from the OCR text
2. Use null for fields where information is not present
3. Preserve numeric values as numbers, not strings
4. Standardize dates to YYYY-MM-DD format when possible
5. Classify document type based on content
6. Set confidence level based on text clarity and completeness
7. Include extraction notes about any ambiguities or issues
8. For damage photos with minimal text, focus on visible damage descriptions
9. Return ONLY valid JSON, no additional commentary

**Important**: Your entire response must be valid JSON that can be parsed. Do not include any text before or after the JSON object."""


def structure_ocr_to_json(ocr_text: str, source_file: str = None, project_client=None, agent=None) -> dict:
    """
    Convert OCR text into structured JSON format using GPT-4o-mini agent.
    
    Args:
        ocr_text: The raw OCR text to structure
        source_file: Optional path to the source file for metadata
        project_client: Optional existing AIProjectClient
        agent: Optional existing agent to reuse
        
    Returns:
        Structured JSON dictionary containing claim information
    """
    try:
        # Detect vehicle side from filename
        vehicle_side = None
        if source_file:
            filename_lower = os.path.basename(source_file).lower()
            if "front" in filename_lower:
                vehicle_side = "front"
            elif "back" in filename_lower:
                vehicle_side = "back"
        
        logger.info(f"Detected vehicle side: {vehicle_side or 'unspecified'}")
        
        # Create client if not provided
        should_close_client = False
        if project_client is None:
            logger.info("Creating AI Project Client...")
            project_client = AIProjectClient(
                endpoint=project_endpoint,
                credential=DefaultAzureCredential(),
            )
            should_close_client = True
        
        # Build side-specific requirements
        if vehicle_side == "front":
            side_specific_fields = """
  "vehicle_side": "front",
  "front_specific": {
    "windshield_damage": "intact | cracked | shattered | null",
    "front_bumper_damage": "none | scratched | dented | detached | null",
    "headlights_damage": "intact | cracked | broken | missing | null",
    "hood_damage": "none | scratched | dented | buckled | null",
    "grille_damage": "intact | damaged | missing | null",
    "license_plate_visible": true or false,
    "front_damage_severity": "none | minor | moderate | severe"
  },"""
            side_requirements = """\n**FRONT PHOTO REQUIREMENTS**:
- MUST extract windshield condition (intact/cracked/shattered)
- MUST assess front bumper damage level
- MUST check headlight condition (both left and right if visible)
- MUST evaluate hood damage
- MUST note if license plate is visible and readable
- MUST provide overall front damage severity rating"""
        elif vehicle_side == "back":
            side_specific_fields = """
  "vehicle_side": "back",
  "back_specific": {
    "rear_windshield_damage": "intact | cracked | shattered | null",
    "rear_bumper_damage": "none | scratched | dented | detached | null",
    "taillights_damage": "intact | cracked | broken | missing | null",
    "trunk_damage": "none | scratched | dented | buckled | null",
    "exhaust_damage": "intact | damaged | detached | null",
    "license_plate_visible": true or false,
    "rear_damage_severity": "none | minor | moderate | severe"
  },"""
            side_requirements = """\n**BACK PHOTO REQUIREMENTS**:
- MUST extract rear windshield condition (intact/cracked/shattered)
- MUST assess rear bumper damage level
- MUST check taillight condition (both left and right if visible)
- MUST evaluate trunk/hatchback damage
- MUST note if rear license plate is visible and readable
- MUST provide overall rear damage severity rating"""
        else:
            side_specific_fields = """
  "vehicle_side": "unspecified","""
            side_requirements = """\n**GENERAL PHOTO**:
- Extract any visible damage information
- Note which parts of vehicle are visible in the image"""
        
        # Agent instructions for structuring OCR output
        agent_instructions = f"""You are an expert document structuring assistant specialized in converting OCR text from insurance claims documents into structured JSON format.

**Your Task**:
Extract and structure information from OCR text into a standardized JSON format for insurance claims processing.

**JSON Output Structure**:
{{
  "document_type": "claim_form | damage_photo | policy_document | statement",{side_specific_fields}
  "extracted_data": {{
    "policy_holder": {{
      "name": "extracted name or null",
      "policy_number": "extracted policy number or null"
    }},
    "incident": {{
      "date": "YYYY-MM-DD or null",
      "type": "vehicle_collision | theft | vandalism | weather | fire | other",
      "description": "brief description or null",
      "location": "location if mentioned or null"
    }},
    "damages": {{
      "description": "damage description",
      "estimated_amount": numeric_amount or null,
      "currency": "USD or other",
      "items": [
        {{
          "part": "part name",
          "cost": numeric_cost or null
        }}
      ]
    }},
    "vehicle_info": {{
      "make": "manufacturer or null",
      "model": "model or null",
      "year": numeric_year or null,
      "license_plate": "plate number or null",
      "vin": "VIN if present or null"
    }},
    "contact_info": {{
      "phone": "phone number or null",
      "email": "email or null",
      "address": "address or null"
    }},
    "additional_details": "any other relevant information"
  }},
  "confidence": "high | medium | low",
  "extraction_notes": "notes about the extraction quality or missing information"
}}{side_requirements}

**Processing Rules**:
1. Extract all available information from the OCR text
2. Use null for fields where information is not present
3. Preserve numeric values as numbers, not strings
4. Standardize dates to YYYY-MM-DD format when possible
5. Classify document type based on content
6. Set confidence level based on text clarity and completeness
7. Include extraction notes about any ambiguities or issues
8. For damage photos with minimal text, focus on visible damage descriptions
9. Return ONLY valid JSON, no additional commentary

**Important**: Your entire response must be valid JSON that can be parsed. Do not include any text before or after the JSON object."""
        
        # Create the agent
        agent = project_client.agents.create_version(
            agent_name="JSONStructuringAgent",
            definition=PromptAgentDefinition(
                model=model_deployment_name,
                instructions=agent_instructions,
                temperature=0.1,  # Low temperature for consistent, factual extraction
            ),
        )
        
        logger.info(f"✅ Created JSON Structuring Agent: {agent.name} (version {agent.version})")
        
        # Get OpenAI client for responses
        openai_client = project_client.get_openai_client()
        
        # Create user query with OCR text
        side_context = f" This is a {vehicle_side.upper()} view of the vehicle." if vehicle_side else ""
        user_query = f"""Please structure the following OCR text into the standardized JSON format.{side_context}

---OCR TEXT START---
{ocr_text}
---OCR TEXT END---

Return only the structured JSON object."""
        
        logger.info("Sending OCR text to structuring agent...")
        
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
                response_text = response_text[start_idx:end_idx+1]
        
        structured_data = json.loads(response_text)
        
        # Add metadata
        structured_data["metadata"] = {
            "source_file": source_file or "unknown",
            "detected_vehicle_side": vehicle_side,
            "processing_timestamp": datetime.now().isoformat(),
            "agent_model": model_deployment_name,
            "original_text_length": len(ocr_text)
        }
        
        logger.info("✓ Successfully structured OCR text into JSON")
        return structured_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response as JSON: {e}")
        # Return error structure
        return {
            "error": "JSON parsing failed",
            "error_details": str(e),
            "raw_response": response_text if 'response_text' in locals() else "No response",
            "metadata": {
                "source_file": source_file or "unknown",
                "processing_timestamp": datetime.now().isoformat(),
                "agent_model": model_deployment_name
            }
        }
    
    except Exception as e:
        logger.error(f"Error in JSON structuring: {e}")
        return {
            "error": "Processing failed",
            "error_details": str(e),
            "metadata": {
                "source_file": source_file or "unknown",
                "processing_timestamp": datetime.now().isoformat()
            }
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
                    "processing_timestamp": datetime.now().isoformat()
                }
            }
        
        # Extract OCR text and metadata
        ocr_text = ocr_data.get("text", "")
        source_file = ocr_data.get("file_path")
        
        if not ocr_text:
            return {
                "error": "No text extracted from OCR",
                "metadata": {
                    "source_file": source_file or "unknown",
                    "processing_timestamp": datetime.now().isoformat()
                }
            }
        
        # Structure the OCR text
        return structure_ocr_to_json(ocr_text, source_file)
        
    except json.JSONDecodeError as e:
        return {
            "error": "Invalid OCR result JSON",
            "error_details": str(e),
            "metadata": {
                "processing_timestamp": datetime.now().isoformat()
            }
        }


def main():
    """Main function to create and test the JSON Structuring Agent."""
    
    print("=== JSON Structuring Agent with GPT-4o-mini ===\n")
    
    try:
        # Get input from CLI args
        if len(sys.argv) < 2:
            print("Usage: python json_structuring_agent.py <ocr_text_file_or_json>")
            print("\nExample with OCR JSON result:")
            print("  python json_structuring_agent.py ocr_result.json")
            print("\nExample with raw text file:")
            print("  python json_structuring_agent.py extracted_text.txt")
            return
        
        input_file = sys.argv[1]
        
        if not os.path.exists(input_file):
            print(f"❌ Error: File not found: {input_file}")
            return
        
        # Detect vehicle side from filename
        vehicle_side = None
        filename_lower = os.path.basename(input_file).lower()
        if "front" in filename_lower:
            vehicle_side = "front"
        elif "back" in filename_lower:
            vehicle_side = "back"
        
        print(f"📄 Processing file: {input_file}")
        print(f"   Detected vehicle side: {vehicle_side or 'unspecified'}\n")
        
        # Create AI Project Client
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        with project_client:
            # Generate agent instructions based on vehicle side
            agent_instructions = get_agent_instructions(vehicle_side)
            
            # Create the agent
            agent = project_client.agents.create_version(
                agent_name="JSONStructuringAgent",
                definition=PromptAgentDefinition(
                    model=model_deployment_name,
                    instructions=agent_instructions,
                    temperature=0.1,
                ),
            )
            
            print(f"✅ Created JSON Structuring Agent: {agent.name} (version {agent.version})")
            print(f"   Agent visible in Foundry portal\n")
            
            # Read input file
            with open(input_file, 'r') as f:
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
                        print(f"❌ OCR failed: {ocr_data.get('error', 'Unknown error')}")
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
            side_context = f" This is a {vehicle_side.upper()} view of the vehicle." if vehicle_side else ""
            user_query = f"""Please structure the following OCR text into the standardized JSON format.{side_context}

---OCR TEXT START---
{ocr_text}
---OCR TEXT END---

Return only the structured JSON object."""
            
            print("🤖 Sending to agent for structuring...")
            
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
                    response_text = response_text[start_idx:end_idx+1]
            
            try:
                result = json.loads(response_text)
                
                # Add metadata
                result["metadata"] = {
                    "source_file": source_file,
                    "detected_vehicle_side": vehicle_side,
                    "processing_timestamp": datetime.now().isoformat(),
                    "agent_model": model_deployment_name,
                    "original_text_length": len(ocr_text)
                }
                
                # Output results
                print("\n=== Structured JSON Output ===")
                print(json.dumps(result, indent=2))
                
                # Save to output file
                output_file = input_file.rsplit('.', 1)[0] + '_structured.json'
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"\n✓ Structured JSON saved to: {output_file}")
                
                # Summary
                print(f"\n📊 Summary:")
                print(f"   Document type: {result.get('document_type', 'unknown')}")
                print(f"   Vehicle side: {result.get('vehicle_side', 'unspecified')}")
                print(f"   Confidence: {result.get('confidence', 'unknown')}")
                
                if result.get('extracted_data', {}).get('policy_holder', {}).get('name'):
                    print(f"   Policy holder: {result['extracted_data']['policy_holder']['name']}")
                if result.get('extracted_data', {}).get('damages', {}).get('estimated_amount'):
                    print(f"   Estimated amount: ${result['extracted_data']['damages']['estimated_amount']}")
                
                print("\n✓ JSON Structuring Agent completed successfully!")
                
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
