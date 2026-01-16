from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool
from azure.identity import DefaultAzureCredential
import os
from dotenv import load_dotenv
load_dotenv()

# Provide agent configuration details
credential = DefaultAzureCredential()
mcp_endpoint = os.getenv("FOUNDRY_KNOWLEDGE_BASE_MCP_URL")
project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") # e.g. https://your-foundry-resource.services.ai.azure.com/api/projects/your-foundry-project
project_connection_name = os.getenv("MCP_TOOL_CONNECTION_NAME")
agent_name = os.getenv("PROMPT_AGENT_NAME")
agent_model = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") # e.g. gpt-4.1-mini

# Create project client
project_client = AIProjectClient(endpoint = project_endpoint, credential = credential)

# Define agent instructions (see "Optimize agent instructions" section for guidance)
instructions = """
You are a helpful assistant that must use the knowledge base to answer all the questions from user. You must never answer from your own knowledge under any circumstances.
Every answer must always provide annotations for using the MCP knowledge base tool  when user specifically asks for citations or reasoning explanation. Otherwise just provide the response.
"""

# Create MCP tool with knowledge base connection
mcp_kb_tool = MCPTool(
    server_label = "knowledge-base",
    server_url = mcp_endpoint,
    require_approval = "never",
    allowed_tools = ["knowledge_base_retrieve"],
    project_connection_id = project_connection_name
)

# Create agent with MCP tool
agent = project_client.agents.create_version(
    agent_name = agent_name,
    definition = PromptAgentDefinition(
        model = agent_model,
        instructions = instructions,
        tools = [mcp_kb_tool]
    )
)

print(f"Agent '{agent_name}' created or updated successfully.")