# Foundry Hosted Agent with MCP Tools

A hosted agent deployed on Azure AI Foundry that integrates with external MCP (Model Context Protocol) tools via Azure API Management for authentication and tracing.

## Architecture

This agent uses the Microsoft Agent Framework with:
- **MCPStreamableHTTPTool**: Executes MCP tool calls directly within the container (enables full tracing)
- **HostedMCPTool**: Alternative that delegates tool execution to the Foundry platform
- **Azure API Management**: Provides secure access to MCP servers with subscription key authentication
- **OpenTelemetry + Application Insights**: Full observability including tool call tracing

## Features

- 🔧 **MCP Tool Integration**: Connect to any MCP-compliant server
- 🔐 **APIM Authentication**: Secure MCP access via subscription keys or Managed Identity
- 📊 **Full Tracing**: OpenTelemetry integration with Azure Monitor/Application Insights
- 🚀 **CI/CD Pipeline**: GitHub Actions workflow for automated deployment
- 🐳 **Container-based**: Deployed via Azure Container Registry

## Prerequisites

- Python 3.10+
- Azure CLI installed and authenticated
- Access to Azure AI Foundry
- Azure Container Registry for hosting the agent image
- Azure API Management (if using APIM for MCP authentication)

## Setup

### 1. Clone and Configure (DevContainer also supported for you to launch through GH Codespaces)

```bash
# Clone the repository
git clone <repository-url>
cd Foundry-Hosted-Agent

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

### 2. Azure Resources Required

- **Azure AI Foundry Account** with a project
- **Azure OpenAI deployment** (e.g., gpt-4o)
- **Azure Container Registry** for hosting the agent image
- **Azure API Management** (optional) for MCP server authentication
- **Application Insights** (optional) for tracing

### 3. Required Permissions

The Foundry Project Managed Identity needs:
- `Cognitive Services OpenAI User` role on the Azure OpenAI resource
- `Azure AI User` role on the Foundry project

For APIM-backed MCP tools, configure one of:
- **Subscription Key**: Pass via `Ocp-Apim-Subscription-Key` header
- **Managed Identity**: Configure APIM policy to validate JWT from Foundry's managed identity

## CI/CD Pipeline

This repository includes a GitHub Actions workflow that automatically builds and deploys the agent when changes are pushed to `main`.

### Setup GitHub Secrets

Add the following secrets to your repository (Settings → Secrets and variables → Actions):

One sample gh command to help you achieve that - 

```bash

# Set a simple text secret
gh secret set AGENT_NAME --repo <user-name>/<repo-name> --body "testconcurrentflowasagent"

```

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `AZURE_CREDENTIALS` | Service Principal credentials (JSON) | See below |
| `AZURE_AI_PROJECT_ENDPOINT` | Foundry project endpoint | `https://<foundry-account>.services.ai.azure.com/api/projects/<project-name>` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | `https://<foundry-account>.openai.azure.com/` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment name | `gpt-4o` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | Chat model deployment name | `gpt-4o` |
| `ACR_NAME` | Azure Container Registry name | `myacr` (without .azurecr.io) |
| `IMAGE_NAME` | Container image name | `foundry-workflow-agent` |
| `FOUNDRY_ACCOUNT` | Foundry account name | `myfoundryaccount` |
| `PROJECT_NAME` | Foundry project name | `myproject` |
| `AGENT_NAME` | Name for the hosted agent | `MyHostedAgent` |
| `REMOTE_MCP_URL` | MCP server URL (APIM endpoint) | `https://myapim.azure-api.net/mcp/mcp` |
| `MCP_TOOL_CONNECTION_ID` | Foundry project connection for MCP | `WeatherMCPTool` |
| `APIM_SUBSCRIPTION_KEY` | APIM subscription key | `abc123...` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights connection string | `InstrumentationKey=...` |

**Create `AZURE_CREDENTIALS`:**
```bash
az ad sp create-for-rbac --name "github-foundry-agent-cicd" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group> \
  --sdk-auth
```
Copy the entire JSON output as the secret value and use to set AZURE_CREDENTIALS

### Required Role Assignments for CI/CD Service Principal

```bash
# ACR Contributor access (for az acr build)
az role assignment create --assignee <sp-app-id> --role "Contributor" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ContainerRegistry/registries/<acr-name>

# Cognitive Services access for agent management
az role assignment create --assignee <sp-app-id> --role "Cognitive Services Contributor" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>

# Azure AI User access at Foundry resource level (required for agent registration)
az role assignment create --assignee <sp-app-id> --role "Azure AI User" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>

# Azure AI User access at Foundry Project level
az role assignment create --assignee <sp-app-id> --role "Azure AI User" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>/projects/<project-name>
```

### Workflow Triggers

- **Automatic**: Pushes to `main` that modify `main.py`, `requirements.txt`, or `Dockerfile`
- **Manual**: Use "Run workflow" in GitHub Actions to deploy with a custom version tag

## Manual Deployment

### Build and Push Container Image

```bash
az acr build --image <agent-name>:<version> --registry <your-acr>.azurecr.io --file Dockerfile .
```

### Register the Agent

```bash
python registerAgent.py
```

### Start the Agent

```bash
az cognitiveservices agent start \
  --account-name <foundry-account> \
  --project-name <project-name> \
  --name <agent-name> \
  --agent-version <version>
```

## Local Testing

```bash
python callHostedAgent.py
```
You can also test the deployed agent through Foundry Playground.

## MCP Tool Types

This project supports two approaches for MCP tool integration:

### MCPStreamableHTTPTool (Recommended for Tracing)
- Executes MCP calls **within the container**
- HTTP requests are visible in Application Insights traces
- Requires passing authentication headers manually (e.g., `Ocp-Apim-Subscription-Key`)

```python
MCPStreamableHTTPTool(
    name="WeatherMCPAPIM",
    url=os.environ["REMOTE_MCP_URL"],
    headers={"Ocp-Apim-Subscription-Key": os.environ.get("APIM_SUBSCRIPTION_KEY", "")},
    description="Weather tool...",
    approval_mode="never_require"
)
```

### HostedMCPTool (Platform-managed)
- Delegates MCP calls to **Foundry platform**
- Uses `project_connection_id` for authentication (configured in Foundry portal)
- Tool calls are NOT visible in your Application Insights (platform-managed)

```python
HostedMCPTool(
    name="WeatherMCPAPIM",
    url=os.environ["REMOTE_MCP_URL"],
    description="Weather tool...",
    approval_mode="never_require"
)
```

## Project Structure

```
├── main.py                 # Hosted agent entry point with MCP tools
├── registerAgent.py        # Agent registration script with tools config
├── callHostedAgent.py      # Client script to invoke the hosted agent
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
├── agent.yaml              # Declarative agent manifest (optional)
├── .env.example            # Environment variable template
└── .github/workflows/
    └── deploy-agent.yml    # CI/CD pipeline
```

## Security Notes

- **Never commit `.env` files** - they contain secrets
- Use **Managed Identity** when running in Azure (preferred)
- Use **Service Principal** only for local development if needed
- Rotate secrets regularly
- Store production secrets in Azure Key Vault

## Files

| File | Description |
|------|-------------|
| `main.py` | Agent implementation with concurrent workflow |
| `registerAgent.py` | Script to register the agent in Foundry |
| `callHostedAgent.py` | Client script to test the deployed agent |
| `agent.yaml` | Agent configuration and metadata |
| `Dockerfile` | Container image definition |
| `requirements.txt` | Python dependencies |


