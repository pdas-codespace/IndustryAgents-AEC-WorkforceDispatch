"""
Create a Prompt Agent with Microsoft Fabric Data Agent as a Tool

This script creates a Prompt Agent in Azure AI Foundry that uses the 
Microsoft Fabric Data Agent tool for data analysis and NL2SQL capabilities.

Prerequisites:
- Create and publish a Fabric data agent in Microsoft Fabric
- Assign developers and end users at least the Azure AI User RBAC role
- Give developers and end users at least READ access to the Fabric data agent
- Ensure your Fabric data agent and Foundry project are in the same tenant
- Use user identity authentication (service principal not supported)

Required Environment Variables:
- AZURE_AI_PROJECT_ENDPOINT: Your Foundry project endpoint
- AZURE_AI_MODEL_DEPLOYMENT_NAME: Model deployment name (e.g., gpt-4o)
- FABRIC_PROJECT_CONNECTION_NAME: Name of the Fabric connection in Foundry project
- FABRIC_AGENT_NAME: Name for the agent to create (optional, defaults to "FabricDataAgent")
"""

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    MicrosoftFabricAgentTool,
    FabricDataAgentToolParameters,
    ToolProjectConnection,
)
from azure.identity import DefaultAzureCredential
import os
from dotenv import load_dotenv

load_dotenv()

# Provide agent configuration details
credential = DefaultAzureCredential()
project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")  # e.g. https://your-foundry-resource.services.ai.azure.com/api/projects/your-foundry-project
fabric_connection_name = os.getenv("FABRIC_PROJECT_CONNECTION_NAME")
agent_name = os.getenv("FABRIC_AGENT_NAME", "AECDataAgent")
agent_model = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")  # e.g. gpt-4o

# Validate required environment variables
required_vars = [
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    "FABRIC_PROJECT_CONNECTION_NAME"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Create project client
project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)

# Define agent instructions
# Note: Include clear tool guidance to help the agent invoke the Fabric tool reliably
instructions = """
You are a helpful data analyst assistant that uses the Microsoft Fabric Data Agent to answer questions about enterprise data.

Guidelines:
- For questions about data, sales, customers, products, inventory, or any structured data queries, always use the Fabric Data Agent tool.
- Provide clear, concise answers based on the data returned from the Fabric tool.
- If the query cannot be answered with the available data, explain what data would be needed.
- Always cite the data source when providing answers from the Fabric tool.
- Format numerical results clearly and provide context when needed.
"""

with project_client:
    # Get the Fabric connection to retrieve its ID
    fabric_connection = project_client.connections.get(fabric_connection_name)
    connection_id = fabric_connection.id
    print(f"Fabric connection ID: {connection_id}")

    # Create Microsoft Fabric Agent Tool
    fabric_tool = MicrosoftFabricAgentTool(
        fabric_dataagent_preview=FabricDataAgentToolParameters(
            project_connections=[
                ToolProjectConnection(project_connection_id=connection_id)
            ]
        )
    )

    # Create agent with Fabric Data Agent tool
    agent = project_client.agents.create_version(
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=agent_model,
            instructions=instructions,
            tools=[fabric_tool]
        )
    )

    print(f"Agent '{agent_name}' created successfully!")
    print(f"  - Agent ID: {agent.id}")
    print(f"  - Agent Name: {agent.name}")
    print(f"  - Agent Version: {agent.version}")
    print(f"  - Model: {agent_model}")
    print(f"  - Fabric Connection: {fabric_connection_name}")
