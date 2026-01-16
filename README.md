# AEC Industry Agent - Workforce Dispatch Assistant

An Azure AI Foundry Prompt Agent that helps construction site managers with **workforce dispatch** and **skill finding** using Foundry IQ as a knowledge base. The agent retrieves workforce details, skills, certifications, and availability to assist in matching the right workers to job sites.

## Use Case

In the **Architecture, Engineering & Construction (AEC)** industry, dispatching the right workforce to construction sites is critical. This agent helps:

- 🔍 **Find workers by skill** - Search for workers with specific certifications (e.g., crane operators, electricians)
- 📋 **Check availability** - Query worker schedules and availability for dispatch
- 🏗️ **Site assignment** - Get recommendations for workforce allocation based on project needs
- 📊 **Compliance tracking** - Verify worker certifications and training status

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure AI Foundry                         │
│  ┌─────────────────┐      ┌─────────────────────────────┐  │
│  │  Prompt Agent   │──────│  Foundry IQ Knowledge Base  │  │
│  │  (GPT-4o)       │ MCP  │  (Workforce Data Index)     │  │
│  └─────────────────┘      └─────────────────────────────┘  │
│           │                           │                     │
│           ▼                           ▼                     │
│  ┌─────────────────┐      ┌─────────────────────────────┐  │
│  │  OpenAI API     │      │  Azure AI Search            │  │
│  │  (Responses)    │      │  (Vector + Semantic Search) │  │
│  └─────────────────┘      └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Components

1. **Knowledge Base Creation** - Script to create Azure AI Search index with blob storage as document source
2. **Foundry IQ MCP Connection** - Connects the agent to Azure AI Search knowledge base via MCP protocol
3. **Prompt Agent** - A Foundry-hosted agent with instructions to query the workforce knowledge base
4. **Client Application** - Interactive Python client to chat with the agent

## Prerequisites

- Python 3.10+
- Azure CLI installed and authenticated
- Access to Azure AI Foundry with a project
- Azure AI Search resource (with agentic retrieval support)
- Azure Blob Storage with workforce documents (PDF, DOCX, etc.)
- Azure OpenAI with embedding model deployed (e.g., text-embedding-3-large)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/pdas-codespace/IndustryAgents-AEC-WorkforceDispatch.git
cd IndustryAgents-AEC-WorkforceDispatch

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your Azure resource details
```

### 2. Configure Environment Variables

Edit `.env` with your Azure resource details:

```env
# Azure AI Foundry Project
AZURE_AI_PROJECT_ENDPOINT=https://<your-foundry-account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_PROJECT_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>

# Model Configuration
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o

# Foundry IQ Knowledge Base (Azure AI Search)
FOUNDRY_KNOWLEDGE_BASE_MCP_URL=https://<ai-search>.search.windows.net/knowledgebases/<kb-id>/mcp?api-version=2025-11-01-preview
MCP_TOOL_CONNECTION_NAME=<your-connection-name>
AI_SEARCH_API_KEY=<your-ai-search-api-key>

# Agent Names
PROMPT_AGENT_NAME=WorkforceDispatchAgent
```

### 3. Create the Foundry IQ MCP Connection

This creates a connection between your Foundry project and the Azure AI Search knowledge base:

```bash
python createFoundryIQMCPConnection.py
```

### 4. Create the Prompt Agent

This registers the Prompt Agent with Foundry IQ as its knowledge tool:

```bash
python createPromptAgentWithFoundryIQ.py
```

### 5. Chat with the Agent

Start an interactive session to ask questions about your workforce:

```bash
python callPromptAgent.py
```

## Creating a Knowledge Base from Blob Storage (Optional)

If you need to create a new knowledge base from scratch with your own documents:

### 1. Configure Blob Storage

Add these variables to your `.env`:

```env
# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<your-search-service>.search.windows.net
AZURE_SEARCH_INDEX_NAME=workforce-documents
AZURE_SEARCH_KNOWLEDGE_BASE_NAME=workforce-knowledge-base

# Azure Blob Storage (using Entra ID authentication)
AZURE_BLOB_STORAGE_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-account>
AZURE_BLOB_CONTAINER_NAME=workforce-documents

# Azure OpenAI Embedding Model
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```

### 2. Assign Required Roles

```bash
# Get Search service managed identity
SEARCH_MI=$(az search service show --name <search-service> --resource-group <rg> --query "identity.principalId" -o tsv)

# Assign Storage Blob Data Reader to Search service
az role assignment create --assignee $SEARCH_MI --role "Storage Blob Data Reader" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-account>"
```

### 3. Upload Documents and Create Knowledge Base

```bash
# Upload workforce documents to blob container
az storage blob upload-batch --destination workforce-documents --source ./documents --account-name <storage-account> --auth-mode login

# Create the knowledge base (index, indexer, skillset, knowledge source)
python createKnowledgeBaseFromBlobStorage.py
```

The script will output the MCP endpoint URL to use in `FOUNDRY_KNOWLEDGE_BASE_MCP_URL`.

## Usage Examples

```
You: Who are the certified crane operators available this week?

Agent: Based on the knowledge base, I found the following certified crane operators 
available this week:

1. **John Smith** - NCCCO Certified, available Mon-Fri
   - Certifications: Lattice Boom Crane, Tower Crane
   - Current assignment: None
   【1:0†workforce_data.pdf】

2. **Maria Garcia** - NCCCO Certified, available Tue-Sat
   - Certifications: Mobile Crane, Overhead Crane
   - Current assignment: Downtown Project (ends Tuesday)
   【1:1†workforce_data.pdf】
...
```

```
You: Find electricians with high voltage certification for the new hospital project

Agent: I found 3 electricians with high voltage certification suitable for the 
hospital project...
```

## Project Structure

```
├── createFoundryIQMCPConnection.py  # Creates MCP connection to Foundry IQ
├── createPromptAgentWithFoundryIQ.py # Registers Prompt Agent with KB tool
├── callPromptAgent.py               # Interactive client to chat with agent
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variable template
├── .gitignore                       # Git ignore patterns
└── README.md                        # This file
```

## Files Description

| File | Description |
|------|-------------|
| `createFoundryIQMCPConnection.py` | Creates an MCP connection in Foundry project pointing to Azure AI Search knowledge base |
| `createPromptAgentWithFoundryIQ.py` | Registers a Prompt Agent that uses Foundry IQ for retrieval-augmented generation |
| `callPromptAgent.py` | Interactive client with streaming responses and OpenTelemetry tracing |
| `.env.example` | Template for required environment variables |

## Required Azure Permissions

### On Azure AI Search
The Foundry project managed identity needs:
- `Search Index Data Reader` - To query the knowledge base
- `Search Index Data Contributor` - For full knowledge base operations

### On Azure AI Foundry
Your user account needs:
- `Azure AI User` or `Cognitive Services Contributor` - To create agents and connections

## Tracing & Observability

The client includes OpenTelemetry integration with Azure Monitor:
- Agent calls are traced to Application Insights
- View traces in Foundry portal → Observability → Tracing

## Security Notes

- **Never commit `.env` files** - they contain API keys
- Use **Managed Identity** in production when possible
- The `AI_SEARCH_API_KEY` is used for CustomKeys auth; consider Key Vault for production
- Rotate API keys regularly

## License

MIT


