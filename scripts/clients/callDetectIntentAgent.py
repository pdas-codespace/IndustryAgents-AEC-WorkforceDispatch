#!/usr/bin/env python3
"""
Call the Detect User Intent Agent

This script calls the DetectUserIntentAgent to classify user messages
and determine which specialized agent should handle the request.

The agent returns structured JSON with intent classification and routing decisions.

Required Environment Variables:
- AZURE_AI_PROJECT_ENDPOINT: Your Foundry project endpoint
- DETECT_INTENT_AGENT_NAME: Name of the intent detection agent (optional, defaults to "DetectUserIntentAgent")
"""

import os
import json

# Enable content recording for traces - MUST be set before importing Azure SDKs
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.projects import AIProjectClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Import tracing components
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

# Configuration
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
AGENT_NAME = os.getenv("DETECT_INTENT_AGENT_NAME", "DetectUserIntentAgent")

# Validate required environment variables
if not PROJECT_ENDPOINT:
    raise ValueError("Missing required environment variable: AZURE_AI_PROJECT_ENDPOINT")

# Initialize the client
credential = DefaultAzureCredential()

with AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as client:
    # Get the latest prompt agent version
    versions = list(client.agents.list_versions(agent_name=AGENT_NAME))
    if not versions:
        raise ValueError(f"No versions found for agent: {AGENT_NAME}")

    agent = versions[0]  # Latest version
    print(f"Using agent: {agent.name}, version: {agent.version}, id: {agent.id}")

    # Configure Azure Monitor for tracing
    connection_string = client.telemetry.get_application_insights_connection_string()
    if connection_string:
        configure_azure_monitor(connection_string=connection_string)
        print(f"Tracing enabled - sending to Application Insights")
    else:
        print("Warning: No Application Insights connection string found")

    # Set up OpenTelemetry tracer
    tracer = trace.get_tracer(__name__)
    
    # Instrument OpenAI SDK to capture tool calls and completions
    OpenAIInstrumentor().instrument()

    # Create OpenAI client with the correct scope for Foundry
    token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
    
    openai_client = OpenAI(
        api_key=token_provider(),
        base_url=f"{PROJECT_ENDPOINT}/openai",
        default_query={"api-version": "2025-05-15-preview"}
    )

    # Interactive loop for testing intent detection
    print("\n" + "="*60)
    print("Detect User Intent Agent")
    print("Enter messages to classify and route to appropriate agents.")
    print("Type 'exit' or 'quit' to end the session.")
    print("="*60 + "\n")

    while True:
        # Get user input
        user_message = input("\nYou: ").strip()
        
        if not user_message:
            continue
        
        if user_message.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break

        # Wrap the agent call in a trace span
        with tracer.start_as_current_span("detect_intent_agent_call") as span:
            # Add custom attributes to the span
            span.set_attribute("agent.name", agent.name)
            span.set_attribute("agent.version", agent.version)
            span.set_attribute("agent.id", agent.id or "unknown")
            span.set_attribute("user.message", user_message)
            
            try:
                # Call the intent detection agent
                response = openai_client.responses.create(
                    input=user_message,
                    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}}
                )

                # Parse the JSON response
                response_text = response.output_text
                span.set_attribute("response.raw", response_text)
                
                try:
                    intent_result = json.loads(response_text)
                    
                    print("\n" + "-"*40)
                    print("Intent Classification Result:")
                    print("-"*40)
                    print(f"  Intent: {intent_result.get('intent', 'N/A')}")
                    print(f"  Next Agent: {intent_result.get('nextAgent', 'N/A')}")
                    print(f"  Confidence: {intent_result.get('confidence', 'N/A')}")
                    print(f"  Reasoning: {intent_result.get('reasoning', 'N/A')}")
                    
                    if intent_result.get('requiresMultipleAgents'):
                        print(f"  Additional Agents: {intent_result.get('additionalAgents', [])}")
                    
                    print("-"*40)
                    
                    # Set span attributes for the parsed result
                    span.set_attribute("intent.category", intent_result.get('intent', 'unknown'))
                    span.set_attribute("intent.next_agent", intent_result.get('nextAgent', 'unknown'))
                    span.set_attribute("intent.confidence", intent_result.get('confidence', 0))
                    
                except json.JSONDecodeError:
                    print(f"\nAgent Response (not JSON): {response_text}")
                    span.set_attribute("error", "Invalid JSON response")
                
            except Exception as e:
                error_msg = str(e)
                print(f"\nError: {error_msg}")
                span.set_attribute("error", error_msg)

print("\nTraces sent to Application Insights. Check Foundry portal → Observability → Tracing")
