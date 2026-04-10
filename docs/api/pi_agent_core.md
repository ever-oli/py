# Pi Agent Core API Reference

Core agent framework with tool execution and conversation management.

## Agent

### Creating an Agent

```python
from pi_agent_core import Agent, AgentOptions
from pi_ai import get_model

agent = Agent(AgentOptions(
    initialState=AgentState(
        systemPrompt="You are a helpful assistant",
        model=get_model("openai", "gpt-4o"),
        tools=[read_tool, bash_tool],
        messages=[],
    ),
    steeringMode="all",
    toolExecution="sequential",
))
```

### Running an Agent

```python
# Run once
messages = await agent.run("List all files")

# Run with streaming
async for message in agent.run_stream("Tell me a story"):
    print(message)

# Steer mid-execution
agent.steer("Focus on Python files specifically")
```

### Agent State

```python
# Get current state
state = agent.state

# Access properties
tools = agent.tools
messages = agent.messages
system_prompt = agent.systemPrompt
model = agent.model
```

### Aborting

```python
# Cancel current operation
agent.abort()
```

## Agent Loop

### `agent_loop(config, messages)`

Run the agent loop manually.

```python
from pi_agent_core import agent_loop, AgentLoopConfig

config = AgentLoopConfig(
    model=model,
    tools=tools,
    systemPrompt="You are helpful",
)

state = await agent_loop(config, [user_message])
```

### `run_agent_loop(config, messages)`

Run and return final state.

```python
from pi_agent_core import run_agent_loop

final_state = await run_agent_loop(config, initial_messages)
```

### `agent_loop_continue(config, state)`

Continue an existing loop.

```python
from pi_agent_core import agent_loop_continue

new_state = await agent_loop_continue(config, current_state)
```

## Types

### AgentState

```python
from pi_agent_core import AgentState

state = AgentState(
    systemPrompt="You are helpful",
    model=model,
    tools=[read_tool],
    messages=[],
    thinkingLevel="medium",
    isStreaming=False,
    streamingMessage=None,
    pendingToolCalls=set(),
    errorMessage=None,
)
```

### AgentMessage

```python
from pi_agent_core import AgentMessage
from pi_ai import TextContent

message = AgentMessage(
    role="user",  # "user", "assistant", "tool"
    content=[TextContent(text="Hello")],
    timestamp=int(time.time() * 1000),
)
```

### AgentTool

```python
from pi_agent_core import AgentTool

tool = AgentTool(
    name="read",
    description="Read a file",
    parameters={"type": "object", ...},
    execute=read_function,
)
```

### AgentToolCall

```python
from pi_agent_core import AgentToolCall

tool_call = AgentToolCall(
    id="call_123",
    name="read",
    arguments={"file_path": "test.txt"},
)
```

## Configuration

### AgentLoopConfig

```python
from pi_agent_core import AgentLoopConfig

config = AgentLoopConfig(
    model=model,
    convertToLlm=my_converter,
    streamFn=my_streamer,
    tools=[read_tool],
    systemPrompt="You are helpful",
    toolExecution="sequential",  # or "parallel"
    beforeToolCall=my_before_hook,
    afterToolCall=my_after_hook,
    onPayload=my_payload_inspector,
)
```

### AgentOptions

```python
from pi_agent_core import AgentOptions

options = AgentOptions(
    initialState=initial_state,
    convertToLlm=converter,
    streamFn=streamer,
    getApiKey=api_key_fn,
    onPayload=payload_fn,
    beforeToolCall=before_fn,
    afterToolCall=after_fn,
    steeringMode="all",  # or "one-at-a-time"
    followUpMode="one-at-a-time",
    sessionId="session-123",
    thinkingBudgets=ThinkingBudgets(),
    toolExecution="sequential",
)
```

## Events

### Event Types

```python
from pi_agent_core import (
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    MessageEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
)
```

### AgentEventStream

```python
from pi_agent_core import AgentEventStream

stream = AgentEventStream()

async for event in stream:
    if isinstance(event, MessageUpdateEvent):
        print(event.delta, end="")
    elif isinstance(event, ToolExecutionStartEvent):
        print(f"[Tool: {event.tool_name}]")
```

## Callbacks

### Before Tool Call

```python
from pi_agent_core import BeforeToolCallContext, BeforeToolCallResult

async def before_tool(context: BeforeToolCallContext):
    """Called before each tool execution."""
    print(f"Executing: {context.tool_call.name}")
    
    # Cancel execution
    if context.tool_call.name == "dangerous":
        return BeforeToolCallResult(
            cancel=True,
            reason="Too dangerous"
        )
    
    # Modify arguments
    args = context.tool_call.arguments
    args["safe_mode"] = True
    return BeforeToolCallResult(modified_arguments=args)
```

### After Tool Call

```python
from pi_agent_core import AfterToolCallContext, AfterToolCallResult

async def after_tool(context: AfterToolCallContext):
    """Called after each tool execution."""
    result = context.result
    
    # Modify result
    if result.get("is_error"):
        result["content"] += "\n\nPlease try again."
    
    return AfterToolCallResult(modified_result=result)
```

## Enums

### QueueMode

```python
from pi_agent_core import QueueMode

"all"            # Process all queued messages
"one-at-a-time"  # Process one message at a time
```

### ToolExecutionMode

```python
from pi_agent_core import ToolExecutionMode

"sequential"  # Execute tools one at a time
"parallel"    # Execute tools concurrently
```
