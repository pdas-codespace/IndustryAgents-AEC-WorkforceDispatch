"""
Create the Detect User Intent Agent for Multi-Agent Orchestration

This agent analyzes user messages and determines which specialized agent
should handle the request (WorkforceAgent, ConstructionSiteAgent, WeatherAgent, etc.)

The agent returns a JSON response with the nextAgent field for routing decisions.

Required Environment Variables:
- AZURE_AI_PROJECT_ENDPOINT: Your Foundry project endpoint
- AZURE_AI_MODEL_DEPLOYMENT_NAME: Model deployment name (e.g., gpt-4o)
- DETECT_INTENT_AGENT_NAME: Name for the intent detection agent (optional, defaults to "DetectUserIntentAgent")
"""

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, ResponseFormatJsonSchemaType
from azure.identity import DefaultAzureCredential
import os
from dotenv import load_dotenv

load_dotenv()

# Provide agent configuration details
credential = DefaultAzureCredential()
project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_name = os.getenv("DETECT_INTENT_AGENT_NAME", "DetectUserIntentAgent")
agent_model = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")

# Validate required environment variables
required_vars = [
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Create project client
project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)

# Define agent instructions for intent detection
# This is a comprehensive prompt for classifying user intents in a construction site management system
instructions = """You are an Intent Classification Agent for a Construction Site Management System. Analyze the user's message and determine which agent(s) should handle the request.

## Available Agents:
1. **WorkforceAgent** - Handles questions about:
   - Worker skills and competencies
   - Certification status and expiration
   - Worker schedules and availability
   - Crew assignments and qualifications

2. **ConstructionSiteAgent** - Handles questions about:
   - IoT sensor data from construction sites
   - Safety protocols and compliance
   - Equipment monitoring and status
   - Environmental compliance data
   - Real-time site conditions

3. **WeatherAgent** - Handles:
   - Current weather conditions
   - Weather alerts and warnings
   - Weather forecasts for work planning

4. **CommunicationAgent** - Handles:
   - Generating and sending emails
   - Worker notifications
   - Dispatch confirmations

## Intent Categories:
- **workforce_query**: Questions about workers, skills, certifications, schedules
- **site_data_query**: Questions about IoT, sensors, equipment, safety, environment
- **combined_query**: Questions requiring both workforce AND site data
- **dispatch_request**: User wants to dispatch/assign a worker to a task
- **dispatch_confirm**: User explicitly confirms dispatch with "Yes I confirm this dispatch"
- **weather_query**: Questions specifically about weather
- **general_query**: Other questions that don't fit above categories

## Dispatch Flow Rules:
- If intent is "dispatch_request", the workflow needs: Weather → Attire → Worker Name → Confirmation
- Only invoke CommunicationAgent when user says "Yes I confirm this dispatch"
- Collect worker name before generating email

## Instructions:
1. Analyze the user message carefully
2. Identify the primary intent
3. Determine if multiple agents are needed
4. Check if this is part of a dispatch workflow
5. Return structured JSON response

Respond ONLY with a valid JSON object, no additional text."""

# Define JSON schema for structured output
intent_response_schema = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "description": "The classified intent category",
            "enum": ["workforce_query", "site_data_query", "combined_query", "dispatch_request", "dispatch_confirm", "weather_query", "general_query"]
        },
        "nextAgent": {
            "type": "string",
            "description": "The agent to route the request to",
            "enum": ["WorkforceAgent", "ConstructionSiteAgent", "WeatherAgent", "CommunicationAgent"]
        },
        "confidence": {
            "type": "number",
            "description": "Confidence score between 0 and 1"
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of the classification decision"
        },
        "requiresMultipleAgents": {
            "type": "boolean",
            "description": "Whether multiple agents are needed"
        },
        "additionalAgents": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of additional agents if multiple are needed"
        }
    },
    "required": ["intent", "nextAgent", "confidence", "reasoning"],
    "additionalProperties": False
}

with project_client:
    # Create agent with structured JSON output
    agent = project_client.agents.create_version(
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=agent_model,
            instructions=instructions,
            response_format=ResponseFormatJsonSchemaType(
                json_schema={
                    "name": "intent_classification",
                    "strict": True,
                    "schema": intent_response_schema
                }
            )
        )
    )

    print(f"Agent '{agent_name}' created successfully!")
    print(f"  - Agent ID: {agent.id}")
    print(f"  - Agent Name: {agent.name}")
    print(f"  - Agent Version: {agent.version}")
    print(f"  - Model: {agent_model}")
    print(f"  - Response Format: JSON Schema (structured output)")
