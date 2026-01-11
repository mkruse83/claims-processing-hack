# Import Required Libraries
import os
import json
import base64
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from openai import AzureOpenAI
from collections import defaultdict

# Load environment variables
load_dotenv()

# Azure Storage Account credentials
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')

# Azure OpenAI credentials
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# Initialize Azure OpenAI Client
openai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version=AZURE_OPENAI_API_VERSION
)

print(f"✅ Configuration loaded:")
print(f"   OpenAI API Version: {AZURE_OPENAI_API_VERSION}")
print(f"   OpenAI Deployment: {AZURE_OPENAI_DEPLOYMENT_NAME}")

# Function to encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to perform OCR using GPT-4.1-mini model
def ocr_using_gpt4(front_image_path, back_image_path):
    """Process front and back images using GPT-4.1-mini"""
    front_base64 = encode_image(front_image_path)
    back_base64 = encode_image(back_image_path)
    
    prompt = """Extract all information from these claim statement images (front and back).
    Return a structured JSON with all the information found including:
    - Claim number
    - Policy holder information
    - Vehicle information
    - Accident details
    - Damages description
    - Any other relevant information
    
    Combine information from both front and back images into a single comprehensive JSON object."""
    
    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{front_base64}"
                        }
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{back_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000
    )
    
    return response.choices[0].message.content

# Function to group claims by number
def group_claims_by_number(blob_list):
    """Group front and back images by claim number"""
    claims = defaultdict(dict)
    
    for blob in blob_list:
        # Extract claim number and side (front/back)
        # Example: crash1_front.jpeg -> claim_number='crash1', side='front'
        name_parts = blob.name.replace('.jpeg', '').replace('.jpg', '').split('_')
        if len(name_parts) >= 2:
            claim_number = name_parts[0]
            side = name_parts[1]
            claims[claim_number][side] = blob.name
    
    return claims

# Main processing function
def process_statements_with_gpt4():
    """Process all statement images using GPT-4.1-mini Model"""
    container_name = 'statements'
    
    # List all blobs and group them by claim number
    blobs = list(blob_service_client.get_container_client(container_name).list_blobs())
    grouped_claims = group_claims_by_number(blobs)
    
    # Store results
    gpt4_results = {}
    
    # Process each claim (front + back together)
    for claim_number, images in grouped_claims.items():
        if 'front' in images and 'back' in images:
            print(f"Processing {claim_number} with GPT-4.1-mini...")
            
            # Download front image
            front_path = f'/tmp/{images["front"]}'
            with open(front_path, 'wb') as f:
                blob_data = blob_service_client.get_blob_client(
                    container=container_name, 
                    blob=images["front"]
                ).download_blob().readall()
                f.write(blob_data)
            
            # Download back image
            back_path = f'/tmp/{images["back"]}'
            with open(back_path, 'wb') as f:
                blob_data = blob_service_client.get_blob_client(
                    container=container_name, 
                    blob=images["back"]
                ).download_blob().readall()
                f.write(blob_data)
            
            # Perform OCR on both images together
            result = ocr_using_gpt4(front_path, back_path)
            gpt4_results[claim_number] = result
            
            print(f"✓ Completed {claim_number}")
    
    print(f"\n✅ Processed {len(gpt4_results)} claims with GPT-4.1-mini")
    
    # Save results to file
    output_file = 'gpt4_statement_results.json'
    with open(output_file, 'w') as f:
        json.dump(gpt4_results, f, indent=2)
    
    print(f"💾 Results saved to {output_file}")
    
    return gpt4_results

if __name__ == "__main__":
    results = process_statements_with_gpt4()
    print(f"\n📊 Total claims processed: {len(results)}")
