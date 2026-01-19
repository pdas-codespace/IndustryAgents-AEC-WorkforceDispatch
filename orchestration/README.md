# Agent Orchestration

This folder contains orchestration configurations for coordinating multiple agents in the AEC Workforce Dispatch solution.

## Folder Structure

```
orchestration/
├── foundry-workflows/              # Microsoft Foundry Workflow YAML definitions
│   ├── foundry-workflow.yaml       # Main HITL workflow with intent detection
│   ├── foundry-workflow-diagram.png # Workflow diagram
│   └── README.md
├── copilot-studio/                 # Copilot Studio orchestration examples (coming soon)
│   └── README.md
└── README.md                       # This file
```

## Orchestration Architecture

The solution uses **Microsoft Foundry Workflows** as the orchestration layer to coordinate multiple specialized Foundry Agents:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Microsoft Foundry Workflow                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  HITL-With-Intent-Detection                  │   │
│  │                                                              │   │
│  │  User Message → DetectUserIntentAgent → Route by Intent     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│          │                    │                    │                │
│          ▼                    ▼                    ▼                │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐     │
│  │  Workforce    │  │   AECData       │  │    Weather       │     │
│  │    Agent      │  │    Agent        │  │     Agent        │     │
│  │ (Foundry IQ)  │  │  (Fabric)       │  │    (MCP)         │     │
│  └───────────────┘  └─────────────────┘  └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

## Workflow: HITL-With-Intent-Detection

The main orchestration workflow uses intent detection to intelligently route user queries:

![Foundry Workflow Diagram](foundry-workflows/foundry-workflow-diagram.png)

### Flow Steps

1. **Start** → Capture user message into variable
2. **DetectUserIntentAgent** → Classify intent and determine next agent
3. **Parse Value** → Extract routing decision from JSON response
4. **If/Else Condition** → Route to appropriate specialized agent:
   - **WorkforceAgent** → WorkforceAgentWithVectorStore (workforce skills & availability)
   - **ConstructionSiteAgent** → AECDataAgent (real-time device alerts & site data)
   - **WeatherAgent** → WeatherHostedAgentWithMCP (weather conditions & safety recommendations)
5. **Send Message** → Return response to user

### Supported Intents

| Intent | Agent | Use Case |
|--------|-------|----------|
| WorkforceAgent | WorkforceAgentWithVectorStore | Find workers, check certifications, availability |
| ConstructionSiteAgent | AECDataAgent | Device alerts, site status, IoT data |
| WeatherAgent | WeatherHostedAgentWithMCP | Weather conditions, safety gear recommendations |

## Related Resources

- [Microsoft Copilot Studio Documentation](https://learn.microsoft.com/microsoft-copilot-studio/)
- [Azure AI Foundry Agents](https://learn.microsoft.com/azure/ai-foundry/agents/)
- [Foundry Hosted Agent with MCP Tools](https://github.com/pdas-codespace/Foundry-Hosted-Agent-With-MCP-Tools)
