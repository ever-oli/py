# Pi Agent Core

Core agent framework with tool execution and conversation management.

## Installation

```bash
pip install pi_agent_core
```

## Quick Start

```python
import asyncio
from pi_agent_core import Agent, AgentOptions
from pi_ai import get_model

async def main():
    # Create an agent
    agent = Agent(AgentOptions(
        initialState=AgentState(
            systemPrompt="You are a helpful assistant",
            model=get_model("openai", "gpt-4o"),
            tools=[],
            messages=[],
        )
    ))
    
    # Run the agent
    messages = await agent.run("Hello!")
    print(messages[-1].content)

asyncio.run(main())
```

## Features

- **Agent Loop**: Core execution engine for LLM conversations
- **Tool Execution**: Sequential or parallel tool calling
- **Streaming**: Real-time response streaming
- **Steering**: Add user messages mid-execution
- **Callbacks**: Hooks for before/after tool execution

## Usage

### Agent Loop

```python
from pi_agent_core import agent_loop, AgentLoopConfig

config = AgentLoopConfig(
    model=model,
    tools=tools,
    systemPrompt="You are helpful",
)

state = await agent_loop(config, messages)
```

### With Tools

```python
from pi_agent_core import Agent

tools = [read_tool, bash_tool, write_tool]

agent = Agent(AgentOptions(
    initialState=AgentState(tools=tools, ...)
))

messages = await agent.run("List files")
```

### Streaming

```python
async for message in agent.run_stream("Tell me a story"):
    update_ui(message)
```

### Callbacks

```python
async def before_tool(context):
    print(f"Executing: {context.tool_call.name}")

agent = Agent(AgentOptions(
    beforeToolCall=before_tool
))
```

## Documentation

- [Full API Docs](../docs/api/pi_agent_core.md)
- [Architecture Guide](../docs/architecture/agent-loop.md)
