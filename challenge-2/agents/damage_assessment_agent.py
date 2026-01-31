#!/usr/bin/env python3
"""
Damage Assessment Agent - Specialized agent for analyzing crash images and vehicle damage.
Uses GPT-4o-mini multimodal capabilities for visual analysis with Azure AI Foundry Agents.

Usage:
    python damage_assessment_agent.py [IMAGE_PATH]
    
Example:
    python damage_assessment_agent.py /path/to/crash.jpg
"""
import os
import sys
import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Azure AI Foundry SDK
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")


def encode_image_to_base64(image_path: str) -> tuple[str, str]:
    """
    Encode an image file to base64 string.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (base64_string, image_format)
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
    
    # Determine image format from file extension
    file_extension = Path(image_path).suffix.lower()
    if file_extension in [".jpg", ".jpeg"]:
        image_format = "jpeg"
    elif file_extension == ".png":
        image_format = "png"
    else:
        image_format = "jpeg"  # default
    
    return base64_encoded, image_format


def analyze_crash_image(image_path: str) -> str:
    """
    Analyze a crash image and generate a detailed damage assessment using GPT-4o-mini.
    
    Args:
        image_path: Path to the crash image file
        
    Returns:
        JSON string containing analysis results with status, description, and metadata
    """
    try:
        logger.info(f"Starting damage assessment for: {image_path}")
        
        # Validate file exists
        if not os.path.exists(image_path):
            return json.dumps({
                "status": "error",
                "error": f"File not found: {image_path}",
                "description": "",
                "file_path": image_path
            })
        
        # Get Azure OpenAI configuration
        openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        openai_api_key = os.getenv('AZURE_OPENAI_KEY')
        openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
        openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
        
        if not openai_endpoint or not openai_api_key:
            return json.dumps({
                "status": "error",
                "error": "Azure OpenAI credentials not configured in environment",
                "description": "",
                "file_path": image_path
            })
        
        # Encode image to base64
        logger.info(f"Encoding image to base64: {image_path}")
        base64_image, image_format = encode_image_to_base64(image_path)
        
        # Create Azure OpenAI client
        from openai import AzureOpenAI
        openai_client = AzureOpenAI(
            azure_endpoint=openai_endpoint,
            api_key=openai_api_key,
            api_version=openai_api_version
        )
        
        logger.info(f"Submitting to Azure OpenAI for damage assessment")
        
        # Process with GPT-4o-mini for description generation
        response = openai_client.chat.completions.create(
            model=openai_deployment,
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert insurance claims analyst with advanced image analysis capabilities. 
Your task is to provide detailed, professional descriptions of insurance-related images, particularly vehicle damage and accident scenes.

Focus on:
- Type of vehicle (car, motorcycle, truck, etc.) and identifying details (make, model, color if visible)
- Location and extent of damage (scratches, dents, broken parts, shattered glass, bent metal, etc.)
- Specific damaged parts (bumper, hood, doors, windows, lights, wheels, etc.)
- Severity assessment (minor, moderate, severe)
- Environmental context (road conditions, weather signs, location type)
- Any visible people, other vehicles, or relevant objects
- Overall safety concerns or hazards visible

Provide clear, objective descriptions that would be useful for insurance claim processing and risk assessment."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please provide a detailed description of this insurance claim image. Focus on vehicle identification, damage assessment, environmental factors, and any relevant details for insurance processing."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000,
            temperature=0.3  # Lower temperature for more consistent, objective descriptions
        )
        
        description = response.choices[0].message.content
        
        # Get file size
        file_size = os.path.getsize(image_path)
        
        # Build success response
        success_result = {
            "status": "success",
            "description": description,
            "file_path": image_path,
            "file_name": os.path.basename(image_path),
            "image_format": image_format,
            "image_size_bytes": file_size,
            "description_length": len(description),
            "model_used": openai_deployment,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Damage assessment completed: {len(description)} characters generated for {image_path}")
        return json.dumps(success_result)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Damage assessment error: {error_msg}")
        return json.dumps({
            "status": "error",
            "error": error_msg,
            "description": "",
            "file_path": image_path
        })


# Define the damage assessment function tool for the agent
damage_assessment_function_tool = FunctionTool(
    name="analyze_crash_image",
    parameters={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the crash/damage image file to analyze (JPEG, PNG)"
            }
        },
        "required": ["image_path"],
        "additionalProperties": False
    },
    description="Analyze a crash or damage image using GPT-4o-mini vision capabilities to assess vehicle damage and generate detailed descriptions for insurance claims. Supports JPEG and PNG files.",
    strict=True
)


def main():
    """Main function to create and test the Damage Assessment Agent."""
    
    print("=== Damage Assessment Agent with Azure AI Foundry ===\n")
    
    try:
        # Get image path from CLI args or use default
        test_image_path = sys.argv[1] if len(sys.argv) > 1 else "/workspaces/claims-processing-hack/challenge-0/data/images/crash1.jpg"
        
        # Create output directory for damage assessment results
        output_dir = "/workspaces/claims-processing-hack/challenge-2/damage_assessment_results"
        os.makedirs(output_dir, exist_ok=True)
        
        # Create AI Project Client
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )
        
        with project_client:
            # Agent instructions
            agent_instructions = """You are an expert Damage Assessment Agent specialized in analyzing crash and damage images for insurance claims.

Your primary responsibility is to assess vehicle damage from images using the available vision analysis tool.

**Available Tool**:
- `analyze_crash_image`: Analyzes crash or damage images using GPT-4o-mini vision capabilities

**Processing Approach**:
- When given an image path, use the analysis tool to generate detailed damage assessments
- Report analysis results including vehicle details, damage descriptions, and severity
- For errors, provide clear diagnostic information
- For successful analyses, summarize key findings from the damage assessment

You are designed to be a reliable, accurate damage assessment service for insurance claims processing."""
            
            # Create the agent version with the function tool
            agent = project_client.agents.create_version(
                agent_name="DamageAssessmentAgent",
                definition=PromptAgentDefinition(
                    model=model_deployment_name,
                    instructions=agent_instructions,
                    tools=[damage_assessment_function_tool],
                ),
            )
            
            print(f"✅ Created Damage Assessment Agent: {agent.name} (version {agent.version})")
            print(f"   Agent visible in Foundry portal\n")
            
            # Get OpenAI client for responses
            openai_client = project_client.get_openai_client()
            
            # Test the agent
            print(f"🧪 Testing the agent with damage assessment...")
            print(f"   Processing: {test_image_path}\n")
            
            if not os.path.exists(test_image_path):
                print(f"   ✗ Error: File not found: {test_image_path}")
                return
            
            # Create initial response with user query
            user_query = f"""Please analyze this crash image file and provide a detailed damage assessment:
{test_image_path}

Provide a comprehensive summary of the vehicle damage, vehicle type, and any relevant details for insurance claim processing."""
            
            response = openai_client.responses.create(
                input=user_query,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            )
            
            print(f"Response output: {response.output_text}")
            
            # Process function calls and save results
            input_list = []
            assessment_result_json = None
            
            for item in response.output:
                if item.type == "function_call":
                    if item.name == "analyze_crash_image":
                        print(f"\n📞 Agent calling function: {item.name}")
                        
                        # Parse function arguments
                        args = json.loads(item.arguments)
                        print(f"   Arguments: {args}")
                        
                        # Execute the damage assessment function
                        assessment_result_json = analyze_crash_image(**args)
                        
                        print(f"   ✓ Function executed successfully")
                        
                        # Save assessment result to JSON file
                        base_name = os.path.splitext(os.path.basename(test_image_path))[0]
                        output_file = os.path.join(output_dir, f"{base_name}_damage_assessment.json")
                        
                        with open(output_file, 'w') as f:
                            assessment_data = json.loads(assessment_result_json)
                            json.dump(assessment_data, f, indent=2)
                        
                        print(f"   💾 Saved damage assessment to: {output_file}")
                        
                        # Provide function call results back to the agent
                        input_list.append(
                            FunctionCallOutput(
                                type="function_call_output",
                                call_id=item.call_id,
                                output=assessment_result_json,
                            )
                        )
            
            # If function was called, get final response
            if input_list:
                print(f"\n🤖 Getting agent's final response...\n")
                
                final_response = openai_client.responses.create(
                    input=input_list,
                    previous_response_id=response.id,
                    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                )
                
                print("=== Damage Assessment Agent Final Response ===")
                print(final_response.output_text)
                print()
            
            print("✓ Damage Assessment Agent completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        print(f"❌ Error: {e}")
        print("Make sure you have run 'az login' and have proper Azure credentials configured.")
        import traceback
        print(f"\nStack trace:\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
