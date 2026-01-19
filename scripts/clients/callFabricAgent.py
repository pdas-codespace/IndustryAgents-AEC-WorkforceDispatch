#!/usr/bin/env python3
"""
Call a deployed Microsoft Foundry Prompt Agent with Fabric Data Agent Tool

This script calls a Prompt Agent that uses Microsoft Fabric Data Agent as a tool
to answer questions about enterprise data using natural language queries.

Prerequisites:
- The Prompt Agent must be created using createPromptAgentWithFabric.py
- User must have access to the Fabric Data Agent and its underlying data sources
- Use user identity authentication (az login)

Required Environment Variables:
- AZURE_AI_PROJECT_ENDPOINT: Your Foundry project endpoint
- FABRIC_AGENT_NAME: Name of the Fabric agent (optional, defaults to "FabricDataAgent")
- AZURE_AI_MODEL_DEPLOYMENT_NAME: Model deployment name (optional, for fallback)
"""

import os
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
AGENT_NAME = os.getenv("FABRIC_AGENT_NAME", "FabricDataAgent")
MODEL_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

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
        api_key=token_provider(),  # OpenAI client expects string, not callable
        base_url=f"{PROJECT_ENDPOINT}/openai",
        default_query={"api-version": "2025-05-15-preview"}
    )

    # Interactive loop for asking questions
    print("\n" + "="*60)
    print("Microsoft Fabric Data Agent")
    print("Ask questions about your enterprise data.")
    print("Type 'exit' or 'quit' to end the session.")
    print("="*60 + "\n")

    while True:
        # Get user input
        user_question = input("\nYou: ").strip()
        
        if not user_question:
            continue
        
        if user_question.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break

        # Wrap the agent call in a trace span
        with tracer.start_as_current_span("fabric_agent_call") as span:
            # Add custom attributes to the span
            span.set_attribute("agent.name", agent.name)
            span.set_attribute("agent.version", agent.version)
            span.set_attribute("agent.id", agent.id or "unknown")
            span.set_attribute("user.question", user_question)
            
            # Reference the prompt agent using the Responses API
            print("\nAgent: ", end="", flush=True)
            
            try:
                # Use tool_choice="required" to force the Fabric tool usage
                # This ensures the agent always uses the Fabric Data Agent for queries
                stream_response = openai_client.responses.create(
                    stream=True,
                    tool_choice="required",  # Force tool use for data queries
                    input=user_question,
                    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}}
                )

                full_response = ""
                # Process the streaming response
                for event in stream_response:
                    if event.type == "response.created":
                        span.set_attribute("response.id", event.response.id)
                    elif event.type == "response.output_text.delta":
                        print(event.delta, end="", flush=True)
                        full_response += event.delta
                    elif event.type == "response.completed":
                        span.set_attribute("response.output_length", len(full_response))
                
                print()  # New line after response
                
            except Exception as e:
                error_msg = str(e)
                print(f"\nError: {error_msg}")
                span.set_attribute("error", error_msg)
                
                # Provide troubleshooting hints for common errors
                if "unauthorized" in error_msg.lower():
                    print("Hint: Make sure you have access to the Fabric Data Agent and its underlying data sources.")
                elif "not found" in error_msg.lower():
                    print("Hint: Make sure your Fabric Data Agent is published and active.")
                elif "BadRequest" in error_msg:
                    print("Hint: Check if the artifact ID and workspace ID are correct in your Fabric configuration.")

print("\nTraces sent to Application Insights. Check Foundry portal → Observability → Tracing")
