#!/usr/bin/env python3
"""
Call a deployed Microsoft Foundry Prompt Agent with Foundry IQ Knowledge Base

This script calls a Prompt Agent that uses Foundry IQ (Knowledge Base) as an MCP tool
to answer questions from indexed documents.
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
AGENT_NAME = os.getenv("PROMPT_AGENT_NAME")
MODEL_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

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
    print("Foundry IQ Knowledge Base Agent")
    print("Ask questions about your indexed documents.")
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
        with tracer.start_as_current_span("prompt_agent_call") as span:
            # Add custom attributes to the span
            span.set_attribute("agent.name", agent.name)
            span.set_attribute("agent.version", agent.version)
            span.set_attribute("agent.id", agent.id or "unknown")
            span.set_attribute("user.question", user_question)
            
            # Reference the prompt agent using the Responses API
            print("\nAgent: ", end="", flush=True)
            
            try:
                stream_response = openai_client.responses.create(
                    stream=True,        
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
                print(f"\nError: {e}")
                span.set_attribute("error", str(e))

print("\nTraces sent to Application Insights. Check Foundry portal → Observability → Tracing")
