import os
import requests
from dotenv import load_dotenv
load_dotenv()

#from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Provide connection details
#credential = DefaultAzureCredential()
project_resource_id = os.getenv("AZURE_AI_PROJECT_RESOURCE_ID")
project_connection_name = os.getenv("MCP_TOOL_CONNECTION_NAME")
mcp_endpoint = os.getenv("FOUNDRY_KNOWLEDGE_BASE_MCP_URL")
ai_search_api_key = os.getenv("AI_SEARCH_API_KEY")  # Azure AI Search API key for CustomKeys auth

# Get bearer token for ARM API
#bearer_token_provider = get_bearer_token_provider(credential, "https://management.azure.com/.default")
headers = {
    #"Authorization": f"Bearer {bearer_token_provider()}",
    "Content-Type": "application/json"
}

# Create project connection using ARM API for Cognitive Services
print(f"Creating connection at: {project_resource_id}/connections/{project_connection_name}")

response = requests.put(
    f"https://management.azure.com{project_resource_id}/connections/{project_connection_name}?api-version=2025-10-01-preview",
    headers=headers,
    json={
        "properties": {
            "authType": "CustomKeys",
            "category": "RemoteTool",
            "group": "GenericProtocol",
            "target": mcp_endpoint,
            "isSharedToAll": False,
            "useWorkspaceManagedIdentity": False,
            "credentials": {
                "keys": {
                    "api-key": ai_search_api_key
                }
            },
            "metadata": {
                "type": "knowledgeBase_MCP"
            }
        }
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code in [200, 201]:
    print(f"\nConnection '{project_connection_name}' created or updated successfully.")
else:
    print(f"\nFailed to create connection.")