# Challenge 2: Build AI Agents for Claims Processing

**Expected Duration:** 60 minutes

## Overview
In this challenge, you'll explore different mechanisms for extracting text from pictures and processing that text with LLMs to extract structured information. You'll work with two specialized AI agents that handle document processing for insurance claims: first extracting raw text from images using OCR, then using an LLM to parse and structure that text into standardized claim data ready for downstream processing.

## The Evolution of Functions: From Traditional Systems to AI Agents

### Functions in Traditional Systems (Pre-GenAI Era)

Before generative AI, functions were the fundamental building blocks of software, but they required **explicit, deterministic control** by developers. In traditional claims processing systems, a developer would write code that explicitly orchestrated every step of the workflow. The developer had to manually control the entire flow—checking if an image exists, calling the OCR function, parsing documents, and extracting structured data.

The challenges with this approach:
- **Rigid Logic**: Every possible scenario had to be anticipated and coded explicitly
- **Manual Orchestration**: Developers decided the exact sequence and conditions for function calls
- **No Adaptability**: Systems couldn't handle variations or edge cases they weren't programmed for
- **Maintenance Burden**: Adding new document types or extraction rules required code changes and redeployment

### From Function Calling to Agent Tools

If you've worked with Azure OpenAI or other LLM APIs before, you're likely familiar with **function calling** (also known as tool use). Function calling allows language models to intelligently invoke external functions to retrieve data, perform calculations, or interact with APIs—essentially extending the model's capabilities beyond text generation.

**The Traditional Approach:**
In the early days of GPT-3.5 and GPT-4, developers would define functions with JSON schemas, pass them to the chat completion API, and handle the function execution loop manually. The model would return a `function_call` object, you'd execute the function, return the results, and continue the conversation.

**The Evolution to Agents:**
Modern AI agents, like those built with Microsoft Agent Framework and Azure AI Foundry, take this concept to the next level. Instead of manually orchestrating the function calling loop, agents **autonomously manage tool execution** within their workflow. You define tools (functions) once, and the agent decides when to use them, chains multiple tool calls together, handles errors, and iterates until it completes the task.

**Why This Matters for Claims Processing:**
In our insurance claims scenario, agents can seamlessly extract text from damage photos via OCR and then intelligently structure that text into standardized JSON formats—all without you manually managing each step.

---

## Tasks

### Task 1: Run the OCR Agent

The OCR Agent uses Mistral Document AI to extract text from claim images.

```bash
cd challenge-2/agents

# Run the OCR agent on a sample claim image
python ocr_agent.py ../../challenge-0/data/statements/crash1_front.jpeg
```

**What it does:**
- Encodes the image to base64
- Sends it to Mistral Document AI via Azure AI Foundry
- Extracts all text from the document/image
- Returns structured JSON with the extracted text

**Expected output:** JSON containing the extracted text from the claim statement, saved to the `ocr_results/` folder.

### Task 2: Run the Statements Data Extraction Agent

The Statements Data Extraction Agent converts raw OCR text into structured insurance claim data using GPT-4.1-mini.

```bash
cd challenge-2/agents

# Run the statements data extraction agent on the OCR output from Task 1
python statements_data_extraction_agent.py ../ocr_results/crash1_front_ocr_result.json
```

**What it does:**
- Reads the OCR output from Task 1
- Uses GPT-4.1-mini to parse and structure the text
- Extracts key claim fields (policyholder info, vehicle info, accident details, damages, signatures, etc.)
- Returns well-structured JSON ready for downstream processing

**Expected output:** Structured JSON with fields like policyholder information, vehicle information, accident information, damage descriptions, witness information, police report details, and signature verification.

---

## Agent Implementation

This challenge includes two specialized agents that work together in a document processing pipeline:

### 1. OCR Agent (`ocr_agent.py`)

The OCR Agent is responsible for extracting raw text from images and documents using Mistral Document AI.

**Technology Stack:**
- **Model**: Mistral Document AI via Azure AI Foundry
- **SDK**: Azure AI Projects SDK with `PromptAgentDefinition`
- **Input**: Image files (JPEG, PNG) or PDF documents
- **Output**: JSON with extracted text and metadata

**How It Works:**

1. **File Encoding**: The agent reads the input file and encodes it to base64, detecting the file type (image vs. document)

2. **OCR Processing**: Sends the encoded file to Mistral Document AI, which uses advanced vision capabilities to extract all visible text

3. **Result Formatting**: Returns a structured JSON response containing:
   - Status (success/error)
   - Extracted text content
   - File metadata
   - Processing timestamp

**Example Output:**
```json
{
  "status": "success",
  "text": "ACCIDENT REPORT\nDate: January 3, 2026\nVehicle: 2023 Honda Accord\nDamage: Front bumper collision...",
  "file_path": "crash1_front.jpeg",
  "timestamp": "2026-01-20T10:30:00Z"
}
```

---

### 2. Statements Data Extraction Agent (`statements_data_extraction_agent.py`)

The Statements Data Extraction Agent takes raw OCR text and converts it into a standardized, structured JSON format suitable for insurance claims processing.

**Technology Stack:**
- **Model**: GPT-4.1-mini via Azure AI Foundry
- **SDK**: Azure AI Projects SDK with `PromptAgentDefinition`
- **Input**: OCR result JSON or raw text file
- **Output**: Structured claim data JSON

**How It Works:**

1. **Input Processing**: Reads the OCR output from the previous step and extracts the raw text content

2. **Document Type Detection**: Automatically detects if the text is from a statement front or back page

3. **Intelligent Structuring**: Uses GPT-4.1-mini with specialized prompts to extract and categorize information into predefined fields:
   - Policyholder information (name, address, phone, email, policy number)
   - Vehicle information (year, make, model, color, VIN, license plate)
   - Accident information (date, time, location, US territory)
   - Description of incident (with validation flags)
   - Description of damages (parts, severity, repair vs replace)
   - Witness information (with matching validation)
   - Police report details
   - Signature verification

4. **Validation**: Ensures all required fields are populated and formats are consistent

**Example Output:**
```json
{
  "document_type": "statement_front",
  "policyholder_information": {
    "name": "John Peterson",
    "address": "1142 Pinecrest Avenue, Springfield, OH 45503",
    "phone": "(937) 555-2319",
    "email": "john.peterson@email.com",
    "policy_number": "LIAB-AUTO-001"
  },
  "vehicle_information": {
    "year": "2004",
    "make": "Honda",
    "model": "Accord",
    "color": "Silver",
    "vin": "1HGCH56404A123456",
    "license_plate": "OH-GHR1984"
  },
  "accident_information": {
    "date_of_incident": "2025-07-17",
    "time": "8:30 AM",
    "location": "Parking Lot, 2325 Main Street, Springfield, OH 45503",
    "is_us_territory": true
  },
  "description_of_damages": [
    {
      "part_name": "front bumper",
      "damage_description": "dented",
      "severity": "moderate",
      "repair_or_replace": "repair"
    }
  ],
  "confidence": "high"
}
```

---

## Pipeline Workflow

The two agents work together in a sequential pipeline:

```
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────────┐
│  Claim Image    │───▶│     OCR Agent        │───▶│  Statements Data         │
│  (JPEG/PNG/PDF) │    │  (Mistral Doc AI)    │    │  Extraction Agent        │
│                 │    │                      │    │  (GPT-4.1)               │
└─────────────────┘    └──────────────────────┘    └──────────────────────────┘
                              │                            │
                              ▼                            ▼
                       Raw OCR Text               Structured Claim JSON
                       (ocr_result.json)          (structured_result.json)
```

**Step 1**: Submit a claim image to the OCR Agent
**Step 2**: OCR Agent extracts all text and saves to `ocr_results/`
**Step 3**: Pass the OCR output to the Statements Data Extraction Agent
**Step 4**: Extraction Agent creates standardized JSON for downstream processing

---

## Key Concepts Demonstrated

### Azure AI Foundry Agents
Both agents use the Azure AI Projects SDK with `PromptAgentDefinition` to create intelligent agents that can:
- Process complex inputs (images, documents, text)
- Apply domain-specific reasoning
- Generate structured outputs

### Multi-Model Architecture
This challenge demonstrates using different AI models for different tasks:
- **Mistral Document AI**: Specialized for OCR and document understanding
- **GPT-4.1-mini**: Optimized for text parsing and structured output generation

### Pipeline Design
The agents are designed to be modular and composable, allowing you to:
- Run each agent independently
- Chain agents together for end-to-end processing
- Add new agents to extend the pipeline

---

## Next Steps

After completing this challenge, you'll be ready for Challenge 3 where we'll evaluate the accuracy of these agents against ground truth data!

---

Good luck! 🚀
