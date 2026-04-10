# Pi AI API Reference

The `pi_ai` package provides a unified interface to multiple LLM providers.

## Core Functions

### `stream(model, context, options)`

Stream completion events from an LLM.

```python
from pi_ai import stream, Context, UserMessage

context = Context(messages=[
    UserMessage(content="Hello!")
])

stream_obj = stream(model, context)

async for event in stream_obj:
    if event.type == EventType.TEXT:
        print(event.text, end="")
```

### `complete(model, context, options)`

Get a complete response (non-streaming).

```python
from pi_ai import complete, Context, UserMessage

response = await complete(model, Context(
    messages=[UserMessage(content="Hello!")]
))
print(response.content[0].text)
```

### `stream_simple(model, context, options)`

Stream with simplified options including reasoning.

```python
from pi_ai import stream_simple, SimpleStreamOptions, ThinkingLevel

options = SimpleStreamOptions(
    reasoning=ThinkingLevel.HIGH
)
stream = stream_simple(model, context, options)
```

### `complete_simple(model, context, options)`

Complete with simplified options.

```python
from pi_ai import complete_simple

response = await complete_simple(model, context)
```

## Model Management

### `get_model(provider, model_id)`

Get a model by provider and ID.

```python
from pi_ai import get_model

model = get_model("openai", "gpt-4o")
model = get_model("anthropic", "claude-opus-4")
model = get_model("google", "gemini-2.5-pro")
```

### `get_models(provider)`

List all models for a provider.

```python
from pi_ai import get_models

models = get_models("openai")
for model in models:
    print(f"{model.id}: {model.name}")
```

### `get_providers()`

List all registered providers.

```python
from pi_ai import get_providers

providers = get_providers()
# ['openai', 'anthropic', 'google', ...]
```

### `register_model(provider, model)`

Register a custom model.

```python
from pi_ai import register_model, Model, ModelCapabilities

custom_model = Model(
    id="my-model",
    api="openai-completions",
    provider="custom",
    capabilities=ModelCapabilities(
        supports_tools=True,
        supports_streaming=True,
    ),
)

register_model("custom", custom_model)
```

## Types

### Message Types

```python
from pi_ai import (
    UserMessage,      # User input
    AssistantMessage, # LLM response
    ToolResultMessage, # Tool execution result
)

# User message
user_msg = UserMessage(
    role="user",
    content="Hello!"
)

# Assistant message
assistant_msg = AssistantMessage(
    role="assistant",
    content=[TextContent(text="Hello!")],
    usage=Usage(),
    stop_reason=StopReason.STOP,
)

# Tool result
tool_result = ToolResultMessage(
    role="toolResult",
    tool_call_id="call_123",
    tool_name="read",
    content=[TextContent(text="File contents")],
)
```

### Content Types

```python
from pi_ai import (
    TextContent,      # Text content
    ImageContent,     # Image (base64)
    ThinkingContent,  # Reasoning/thinking
    ToolCall,         # Tool call from LLM
)

# Text
text = TextContent(type="text", text="Hello")

# Image
image = ImageContent(
    type="image",
    data="base64encoded...",
    mime_type="image/jpeg"
)

# Tool call
tool_call = ToolCall(
    type="toolCall",
    id="call_123",
    name="read",
    arguments={"file_path": "test.txt"},
)
```

### Context

```python
from pi_ai import Context, Tool

context = Context(
    messages=[user_msg],
    tools=[
        Tool(
            name="read",
            description="Read a file",
            parameters={"type": "object", ...}
        )
    ],
    system="You are a helpful assistant",
)
```

### Stream Options

```python
from pi_ai import StreamOptions, SimpleStreamOptions

# Full options
options = StreamOptions(
    temperature=0.7,
    max_tokens=4096,
    api_key="sk-...",
    cache_retention=CacheRetention.SHORT,
)

# Simple options with reasoning
simple_options = SimpleStreamOptions(
    temperature=0.7,
    reasoning=ThinkingLevel.HIGH,
    thinking_budgets=ThinkingBudgets(high=8000),
)
```

## Event Types

### Stream Events

```python
from pi_ai import (
    # Start/Done
    StartEvent,       # Stream started
    DoneEvent,        # Stream completed
    
    # Text events
    TextStartEvent,   # Text block starting
    TextDeltaEvent,   # Text chunk (delta)
    TextEndEvent,     # Text block complete
    
    # Thinking events
    ThinkingStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    
    # Tool call events
    ToolCallStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    
    # Other
    UsageEvent,       # Token usage update
    ErrorEvent,       # Error occurred
)
```

## API Registry

### Register a Custom Provider

```python
from pi_ai import (
    register_api_provider,
    ApiProvider,
    Model,
    Context,
    StreamOptions,
)

class MyProvider(ApiProvider):
    def stream(self, model, context, options):
        # Implementation
        pass
    
    def stream_simple(self, model, context, options):
        # Implementation
        pass

register_api_provider("my-api", MyProvider())
```

### List Registered APIs

```python
from pi_ai import list_api_providers

apis = list_api_providers()
# ['openai-completions', 'anthropic-messages', ...]
```

## Utilities

### Environment API Keys

```python
from pi_ai.utils.env_api_keys import get_env_api_key

# Get API key from environment
api_key = get_env_api_key("openai")  # Checks OPENAI_API_KEY
```

### JSON Parsing

```python
from pi_ai.utils.json_parse import parse_streaming_json

# Parse partial JSON from stream
for chunk in stream:
    data = parse_streaming_json(chunk)
```

### Validation

```python
from pi_ai.utils.validation import validate_tool_call

# Validate a tool call against schema
is_valid = validate_tool_call(tool_call, tool_definition)
```
