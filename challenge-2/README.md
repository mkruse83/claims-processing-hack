# Challenge 2: Build an AI Agent for Claims Processing

**Expected Duration:** 60 minutes

## Overview
In this challenge, you'll create an intelligent AI agent that orchestrates the document processing pipeline you built in Challenge 1. The agent will analyze claim documents, make intelligent decisions about processing, validate claim information, and produce structured outputs.

## The Evolution of Functions: From Traditional Systems to AI Agents

### Functions in Traditional Systems (Pre-GenAI Era)

Before generative AI, functions were the fundamental building blocks of software, but they required **explicit, deterministic control** by developers. In traditional claims processing systems, a developer would write code that explicitly orchestrated every step of the workflow. The developer had to manually control the entire flow—checking if an image exists, calling the OCR function, parsing policy documents, validating amounts against coverage limits, and making approval decisions.

The challenges with this approach:
- **Rigid Logic**: Every possible scenario had to be anticipated and coded explicitly
- **Manual Orchestration**: Developers decided the exact sequence and conditions for function calls
- **No Adaptability**: Systems couldn't handle variations or edge cases they weren't programmed for
- **Maintenance Burden**: Adding new document types or validation rules required code changes and redeployment

### From Function Calling to Agent Tools

If you've worked with Azure OpenAI or other LLM APIs before, you're likely familiar with **function calling** (also known as tool use). Function calling allows language models to intelligently invoke external functions to retrieve data, perform calculations, or interact with APIs—essentially extending the model's capabilities beyond text generation.

**The Traditional Approach:**
In the early days of GPT-3.5 and GPT-4, developers would define functions with JSON schemas, pass them to the chat completion API, and handle the function execution loop manually. The model would return a `function_call` object, you'd execute the function, return the results, and continue the conversation. This gave models the ability to use calculators, search databases, call APIs, or retrieve real-time information.

**The Evolution to Agents:**
Modern AI agents, like those built with Microsoft Agent Framework and Microsoft Foundry, take this concept to the next level. Instead of manually orchestrating the function calling loop, agents **autonomously manage tool execution** within their workflow. You define tools (functions) once, and the agent decides when to use them, chains multiple tool calls together, handles errors, and iterates until it completes the task.

**Why This Matters for Claims Processing:**
In our insurance claims scenario, an agent can seamlessly orchestrate multiple tools—extracting text from damage photos via OCR, parsing policy documents for coverage terms, validating claim amounts against policy limits, and generating structured outputs—all without you manually managing each step. The agent reasons about which tools to use, in what order, and how to combine their results to produce accurate claim assessments. This makes building complex, multi-step workflows dramatically simpler and more robust.

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

### Task 2: Run the JSON Structuring Agent

The JSON Structuring Agent converts raw OCR text into structured claim data using GPT-4.1-mini.

```bash
cd challenge-2/agents

# Run the JSON structuring agent on the OCR output from Task 1
python json_structuring_agent.py ../ocr_results/crash1_front_ocr_result.json
```

**What it does:**
- Reads the OCR output from Task 1
- Uses GPT-4.1-mini to parse and structure the text
- Extracts key claim fields (vehicle info, damage assessment, incident details)
- Returns well-structured JSON ready for downstream processing

**Expected output:** Structured JSON with fields like vehicle information, damage severity, incident details, and claim assessment.

---

## Agent Implementation

### What is the Claims Processing Agent?

The Claims Processing Agent is an intelligent AI assistant built using Microsoft Agent Framework and Microsoft Foundry. Think of it as an experienced claims adjuster that can automatically review insurance claims, validate coverage, check policy terms, and provide recommendations—all without human intervention for routine cases.

Instead of requiring manual review of every document and calculation, the agent autonomously orchestrates the entire claims assessment process, making intelligent decisions about what information to gather and how to analyze it.

### How the Agent Works

The agent operates as an intelligent coordinator that:

1. **Receives a claim description** containing basic information like the policy holder's name, incident details, estimated damages, and available documents

2. **Automatically decides what actions to take** by analyzing the claim and determining which tools it needs to use

3. **Gathers all necessary information** by calling specialized tools to extract data from documents, parse policy terms, and validate coverage

4. **Makes informed decisions** by combining all the gathered information to assess eligibility, calculate payouts, and determine approval status

5. **Generates a comprehensive report** with clear recommendations, reasoning, and next steps

The key advantage is that the agent makes these decisions autonomously—you don't need to program every step or decision point. It reasons through the process like a human claims adjuster would.

### Agent Capabilities (Tools)

The agent has access to five specialized tools that it can use to process claims:

#### 1. Image Text Extraction
**What it does**: Reads and extracts text from damage photos or scanned documents

**Why it's useful**: Automatically captures information from photos of damaged vehicles, including visible text, license plates, or other identifying information without manual data entry

**Example use**: When a customer submits a photo of their damaged car, the agent can extract any visible text or details from the image to supplement the claim information

#### 2. Policy Document Parser
**What it does**: Reads and interprets insurance policy documents to understand coverage terms, limits, and conditions

**Why it's useful**: Ensures the agent has accurate, up-to-date policy information to validate claims against actual coverage terms

**Example use**: The agent reviews the customer's comprehensive auto policy to confirm it covers collision damage and identify the coverage limit ($50,000) and deductible ($500)

**Information extracted**:
- Policy type (comprehensive, liability-only, commercial, etc.)
- Coverage limits (maximum payout amounts)
- Deductible amounts
- Covered incident types
- Policy terms and conditions

#### 3. Claim Amount Validation
**What it does**: Checks if a claimed amount is within policy coverage limits and calculates the actual payout after deductibles

**Why it's useful**: Provides instant financial validation and accurate payout calculations without manual review

**Example use**: For a $3,500 repair claim with a $500 deductible under a $50,000 coverage limit:
- Confirms the claim is within coverage limits ✓
- Calculates net payout: $3,000 ($3,500 - $500 deductible)
- Validates eligibility

#### 4. Policy Coverage Assessment
**What it does**: Verifies that the type of incident is actually covered under the customer's policy type

**Why it's useful**: Prevents approval of claims for incidents not covered by the policy, reducing fraud and processing errors

**Coverage rules by policy type**:
- **Comprehensive Auto**: Covers collision, theft, vandalism, weather damage, fire
- **Liability Only**: Covers collision only
- **Commercial Auto**: Covers collision, theft, vandalism, business use
- **Motorcycle**: Covers collision, theft, vandalism
- **High Value Vehicle**: Covers collision, theft, vandalism, weather damage, fire, custom parts

**Example use**: Customer files a collision claim under a comprehensive auto policy—agent confirms collision is a covered incident type and approves further processing

#### 5. Claim Report Generator
**What it does**: Creates a structured, professional claim assessment report with recommendations

**Why it's useful**: Provides consistent, well-documented claim decisions with clear reasoning for audit trails and customer communication

**Report includes**:
- Unique claim report ID and timestamp
- Summary of claim details
- Validation results
- Approval/denial recommendation
- Reasoning and confidence level
- Next steps for processing

**Example use**: After validating all aspects of a claim, the agent generates a formal report recommending approval for a $3,000 payout

### Agent Intelligence and Decision-Making

The agent is configured with expertise in insurance claims processing and follows these principles:

**Primary Responsibilities**:
- **Claims Analysis**: Automatically identify and extract key information from claim descriptions (policy holder details, incident type, damage descriptions, claimed amounts)
- **Document Processing**: Use appropriate tools to read and interpret various document types (policies, photos, statements)
- **Validation and Assessment**: Verify claim amounts against policy limits, confirm incident coverage, and calculate accurate payouts
- **Report Generation**: Produce professional, structured reports with clear recommendations

**Decision-Making Logic**:
- Always validates claims against actual policy terms (not assumptions)
- Automatically factors in deductibles when calculating payouts
- Verifies incident type is covered before approving claims
- Documents all validation steps to create a complete audit trail
- Prioritizes accuracy and thoroughness over processing speed

**Quality Standards**:
- Provides clear, well-structured analysis
- Uses all available tools to gather complete information
- Includes specific reasoning for every recommendation
- Flags any missing or unclear information for human review
- Maintains professional insurance industry communication standards

### Real-World Example

**Scenario**: Customer John Smith files a claim

**Input to Agent**:
```
Policy Holder: John Smith
Policy Number: POL-12345
Policy Type: Comprehensive Auto
Incident Date: January 3, 2026
Incident Type: Vehicle collision
Description: My car was hit by another vehicle while parked.
The front bumper and headlight are damaged.

Estimated repair cost: $3,500
Policy Coverage Limit: $50,000
Deductible: $500

Available Documents:
- Policy: comprehensive_auto_policy.md
```

**Agent's Autonomous Process**:

1. **Reads and understands** the claim details
2. **Retrieves policy information** using the policy document parser to confirm coverage terms
3. **Verifies coverage** by checking that "collision" is covered under "comprehensive auto" policy
4. **Validates the claim amount** by confirming $3,500 is within the $50,000 limit
5. **Calculates payout** by subtracting the $500 deductible ($3,500 - $500 = $3,000)
6. **Generates recommendation** to approve the claim

**Agent's Output**:

**Claim Processing Report for John Smith (Policy POL-12345)**

**Incident Summary**:
- Date: January 3, 2026
- Type: Vehicle collision (parked car hit by another vehicle)
- Damage: Front bumper and headlight

**Financial Assessment**:
- Claimed Amount: $3,500
- Coverage Limit: $50,000
- Deductible: $500
- **Estimated Payout: $3,000**

**Policy Analysis**:
- Policy Type: Comprehensive Auto
- Incident Coverage: ✓ Collision is covered
- Amount Validation: ✓ Within coverage limits

**Recommendation**:
- **Status**: APPROVED
- **Payout**: $3,000
- **Confidence**: High
- **Reasoning**: Claim is consistent with policy terms, incident type is covered, and amount is within limits after deductible

**Next Steps**:
- Verify damage with repair shop estimates
- Request additional documentation (photos, police report if available)
- Schedule final review before processing payment

**Status**: Pending final documentation verification

### Business Benefits

✅ **Faster Processing**: Automates routine claim reviews that would normally take hours  
✅ **Consistent Decisions**: Applies the same validation logic to every claim, reducing human error  
✅ **24/7 Availability**: Processes claims instantly without waiting for business hours  
✅ **Accurate Calculations**: Automatically calculates payouts with deductibles applied correctly  
✅ **Audit Trail**: Documents every decision with clear reasoning for compliance  
✅ **Cost Reduction**: Reduces manual review workload for straightforward claims  
✅ **Fraud Prevention**: Consistently checks coverage eligibility to prevent invalid claims  
✅ **Scalability**: Handles high claim volumes without additional staffing  



## Next Steps

After completing this challenge, you'll be ready for Challenge 3 where we'll deploy this agent as a production API with CI/CD and monitoring!

---


Good luck! 🚀
