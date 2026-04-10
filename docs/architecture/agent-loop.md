# Agent Loop Architecture

The agent loop is the core execution engine that manages the conversation flow between the user, LLM, and tools.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Loop                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│   │  User    │────▶│  Agent   │────▶│   LLM    │               │
│   │ Message  │     │  Loop    │     │  Stream  │               │
│   └──────────┘     └──────────┘     └──────────┘               │
│                           │              │                      │
│                           │              ▼                      │
│                           │        ┌──────────┐                │
│                           │        │  Parse   │                │
│                           │        │ Response │                │
│                           │        └──────────┘                │
│                           │              │                      │
│                           ▼              ▼                      │
│                    ┌─────────────────────────┐                 │
│                    │    Response Type?       │                 │
│                    └─────────────────────────┘                 │
│                           │                                    │
│           ┌───────────────┼───────────────┐                    │
│           ▼               ▼               ▼                    │
│     ┌──────────┐    ┌──────────┐   ┌──────────┐               │
│     │   Text   │    │ Tool Call│   │  Error   │               │
│     │ Response │    │  Needed  │   │          │               │
│     └──────────┘    └──────────┘   └──────────┘               │
│                           │                                    │
│                           ▼                                    │
│                    ┌──────────────┐                           │
│                    │ Execute Tools│                           │
│                    │ (Sequential  │                           │
│                    │  or Parallel)│                           │
│                    └──────────────┘                           │
│                           │                                    │
│                           ▼                                    │
│                    ┌──────────────┐                           │
│                    │ Add Results  │                           │
│                    │ to Context   │                           │
│                    └──────────────┘                           │
│                           │                                    │
│                           └──────────────▶ (Loop back to LLM) │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Agent Loop

The main entry point in `pi_agent_core/agent_loop.py`:

```python
async def agent_loop(
    config: AgentLoopConfig,
    messages: list[AgentMessage],
) -> AgentLoopState:
    """
    Run the agent loop until completion.
    
    Args:
        config: Loop configuration (model, tools, callbacks)
        messages: Initial conversation messages
        
    Returns:
        Final loop state with updated messages
    """
```

### 2. AgentLoopConfig

Configuration for the loop:

```python
@dataclass
class AgentLoopConfig:
    model: Model                    # LLM to use
    convertToLlm: Callable         # Convert agent messages to LLM format
    streamFn: StreamFn             # Function to stream from LLM
    tools: list[AgentTool]         # Available tools
    systemPrompt: str | None       # System prompt
    toolExecution: ToolExecutionMode = "sequential"
    beforeToolCall: Callable | None  # Pre-tool hook
    afterToolCall: Callable | None   # Post-tool hook
    onPayload: Callable | None       # Payload inspector
```

### 3. AgentLoopState

Tracks the loop's current state:

```python
@dataclass
class AgentLoopState:
    messages: list[AgentMessage]
    isComplete: bool
    error: Exception | None
    usage: TokenUsage
```

## Execution Flow

### Step 1: Message Conversion

Agent messages are converted to LLM format:

```python
def convert_to_llm_messages(messages: list[AgentMessage]) -> list[Message]:
    """Convert internal AgentMessage to pi_ai Message types."""
    llm_messages = []
    for msg in messages:
        if msg.role == "user":
            llm_messages.append(UserMessage(content=msg.content))
        elif msg.role == "assistant":
            llm_messages.append(AssistantMessage(...))
        # ...
    return llm_messages
```

### Step 2: LLM Streaming

The loop streams from the LLM:

```python
context = Context(
    messages=llm_messages,
    tools=tools,
    system=system_prompt,
)

stream = config.streamFn(config.model, context)
```

### Step 3: Response Parsing

Events from the stream are processed:

```python
async for event in stream:
    if event.type == EventType.TEXT:
        # Accumulate text content
        current_text += event.text
    elif event.type == EventType.TOOL_CALL:
        # Queue tool call for execution
        pending_tools.append(event.tool_call)
    elif event.type == EventType.ERROR:
        # Handle error
        state.error = event.error
        break
```

### Step 4: Tool Execution

If tools are called, they're executed:

```python
if pending_tools:
    if config.toolExecution == "sequential":
        results = []
        for tool_call in pending_tools:
            # Pre-tool hook
            if config.beforeToolCall:
                await config.beforeToolCall(...)
            
            # Execute
            result = await execute_tool(tool_call, config.tools)
            
            # Post-tool hook
            if config.afterToolCall:
                await config.afterToolCall(...)
            
            results.append(result)
    else:  # parallel
        results = await asyncio.gather(*[
            execute_tool(tc, config.tools) for tc in pending_tools
        ])
```

### Step 5: Loop Continuation

Tool results are added to context, and the loop continues:

```python
for result in results:
    messages.append(AgentMessage(
        role="tool",
        content=result.content,
        tool_call_id=result.tool_call_id,
    ))

# Loop back to step 1 with updated messages
return await agent_loop(config, messages)
```

## Event Types

The loop emits events for observability:

```python
class AgentStartEvent:
    """Agent loop started."""
    
class TurnStartEvent:
    """New turn (user message + response)."""
    
class MessageStartEvent:
    """LLM started responding."""
    
class MessageUpdateEvent:
    """New content from LLM stream."""
    
class MessageEndEvent:
    """LLM finished responding."""
    
class ToolExecutionStartEvent:
    """About to execute tool(s)."""
    
class ToolExecutionUpdateEvent:
    """Tool execution progress."""
    
class ToolExecutionEndEvent:
    """Tool execution completed."""
    
class TurnEndEvent:
    """Turn completed."""
    
class AgentEndEvent:
    """Agent loop completed."""
```

## Usage Example

### Basic Loop

```python
from pi_agent_core import agent_loop, AgentLoopConfig
from pi_ai import get_model

config = AgentLoopConfig(
    model=get_model("openai", "gpt-4o"),
    tools=[read_tool, bash_tool],
    systemPrompt="You are a helpful coding assistant.",
)

messages = [AgentMessage(role="user", content="List all Python files")]
final_state = await agent_loop(config, messages)
```

### With Event Streaming

```python
from pi_agent_core import AgentEventStream

stream = AgentEventStream()

async for event in stream:
    if isinstance(event, MessageUpdateEvent):
        print(event.delta, end="", flush=True)
    elif isinstance(event, ToolExecutionStartEvent):
        print(f"\n[Executing: {event.tool_name}]")
```

### With Callbacks

```python
async def before_tool(context: BeforeToolCallContext) -> BeforeToolCallResult | None:
    """Called before each tool execution."""
    print(f"About to execute: {context.tool_call.name}")
    
    # Can modify arguments or cancel
    if context.tool_call.name == "bash":
        args = context.tool_call.arguments
        if "rm -rf /" in args.get("command", ""):
            return BeforeToolCallResult(
                cancel=True,
                reason="Dangerous command blocked"
            )
    return None

config = AgentLoopConfig(
    beforeToolCall=before_tool,
    # ...
)
```

## Steering Mode

The agent loop supports "steering" - adding user messages mid-stream:

```python
agent = Agent()

# Start a long operation
task = asyncio.create_task(agent.run("Analyze this large codebase"))

# Mid-stream, steer the agent
await asyncio.sleep(5)
agent.steer("Focus specifically on the auth module")

# Continue with updated direction
results = await task
```

## Error Handling

The loop handles various error scenarios:

```python
try:
    state = await agent_loop(config, messages)
except ModelError as e:
    # LLM API error
    print(f"Model error: {e}")
except ToolError as e:
    # Tool execution error
    print(f"Tool error: {e}")
except asyncio.TimeoutError:
    # Operation timed out
    print("Operation timed out")
```

## Performance Considerations

### Streaming vs Complete

```python
# Streaming - better UX, lower latency
async for event in stream:
    update_ui(event)

# Complete - simpler, but waits for full response
response = await complete(model, context)
```

### Tool Execution Mode

```python
# Sequential - deterministic, slower
config = AgentLoopConfig(toolExecution="sequential")

# Parallel - faster, but order not guaranteed  
config = AgentLoopConfig(toolExecution="parallel")
```

### Cancellation

```python
agent = Agent()

# Start operation
task = asyncio.create_task(agent.run("Long task"))

# Cancel after timeout
try:
    result = await asyncio.wait_for(task, timeout=30)
except asyncio.TimeoutError:
    agent.abort()
```
