![Banner](banner.png)

# AI-Powered Claims Processing Hackathon

Today, you'll dive into the world of intelligent agent systems powered by Azure AI to revolutionize insurance claims processing. Get ready for a hands-on, high-impact day of learning and innovation!

## Introduction

Get ready to transform insurance claims processing with AI using cutting-edge technologies from Azure AI! In this hackathon, you'll master multimodal document processing, vectorized search, and intelligent agent orchestration to build a production-ready claims processing system that understands policy documents, analyzes damage photos, and validates claims—just like experienced insurance adjusters, but faster and more consistent.

Using GPT-4o's multimodal capabilities, Azure AI Search with integrated vectorization, and the Microsoft Agent Framework, you'll create a sophisticated document processing pipeline that handles text, images, and handwritten statements seamlessly. From environment setup through document processing to intelligent agent creation, you'll build a complete system that automates complex insurance workflows while maintaining transparency and accuracy.

## Learning Objectives 🎯

By participating in this hackathon, you will learn how to:

- **Process Multimodal Documents** using GPT-4o to extract and understand information from text documents, images, and handwritten statements with advanced OCR and vision capabilities.
- **Build Vectorized Search Systems** with Azure AI Search's integrated vectorization to enable semantic search across insurance policies, claims, and statements using hybrid search (keyword + vector + semantic).
- **Create Intelligent AI Agents** using Microsoft Agent Framework and Microsoft Foundry to orchestrate document processing workflows, make intelligent decisions, and validate claim information.
- **Implement Function Calling/Tools** to extend agent capabilities with custom tools for OCR, document parsing, policy validation, and claim assessment.
- **Generate Structured Outputs** from unstructured documents, producing standardized JSON claim reports with validation, confidence scores, and actionable recommendations.

## Overview

This hands-on hackathon guides you through building a production-ready, AI-powered insurance claims processing system. You'll learn to leverage cutting-edge generative AI models, multimodal document processing, and intelligent agents to automate complex insurance workflows.

## Requirements
To successfully complete this hackathon, you will need the following:

- GitHub account to access the repository and run GitHub Codespaces and Github Copilot. 
- Be familiar with Python programming, including handling JSON data and making API calls.​ 
- Be familiar with Generative AI Solutions and Azure Services. 
- An active Azure subscription, with Owner rights. 
- Ability to provision resources in **Sweden Central** or [another supported region](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models?tabs=global-standard%2Cstandard-chat-completions#global-standard-model-availability). 

## Challenges

- **Challenge 00**: **[Environment Setup & Azure Resource Deployment](challenge-0/README.md)** : Set up your development environment, deploy Azure resources (Microsoft Foundry, Azure AI Search, Blob Storage), configure environment variables, and prepare sample insurance documents for processing
- **Challenge 01**: **[GenAI Powered Document Processing](challenge-1/README.md)**: Build a comprehensive document processing pipeline using GPT-4o and Mistral AI for multimodal processing, implement Azure AI Search with vector embeddings for semantic retrieval, and create hybrid search capabilities across insurance policies and claims
- **Challenge 02**: **[Creating Your AI Document Agent](challenge-2/README.md)**: Build an intelligent AI agent using Microsoft Agent Framework and Microsoft Foundry that orchestrates claims processing workflows, implements function calling for OCR and document parsing, validates claim information against policies, and generates structured JSON claim reports with confidence scores
- **Challenge 03**: **[Observability and Monitoring for AI Agents](challenge-3/README.md)**: Implement comprehensive observability and monitoring for your Claims Processing Agent using Microsoft Foundry's observability capabilities, set up OpenTelemetry-based tracing, configure continuous evaluation for quality and safety metrics, integrate Application Insights for centralized telemetry, and establish proactive alerting for production AI systems
- **Challenge 04**: **[Agent Deployment](challenge-4/README.md)**: *Coming Soon* - Deploy your AI agent to production in Azure with comprehensive monitoring, implement scaling strategies, and establish observability for production-ready systems



## Contributing
We welcome contributions! Please see the [Contributing Guide](CONTRIBUTING.md) for details on coding standards, development environment setup and submission processes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
