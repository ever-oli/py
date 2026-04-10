# Provider Architecture

The provider system abstracts different LLM APIs behind a unified interface.

## Design Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Provider Architecture                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────┐      │
│   │                 Unified API                         │      │
│   │  stream() / complete() / stream_simple()           │      │
│   └─────────────────────────────────────────────────────┘      │
│                           │                                     │
│           ┌───────────────┼───────────────┐                    │
│           ▼               ▼               ▼                    │
│   ┌──────────┐    ┌──────────┐   ┌──────────┐                 │
│   │  OpenAI  │    │ Anthropic│   │  Google  │                 │
│   │ Provider │    │ Provider │   │ Provider │                 │
│   └──────────┘    └──────────┘   └──────────┘                 │
│           │               │               │                    │
│           ▼               ▼               ▼                    │
│   ┌──────────┐    ┌──────────┐   ┌──────────┐                 │
│   │ OpenAI   │    │ Anthropic│   │  Gemini  │                 │
│   │   API    │    │   API    │   │   API    │                 │
│   └──────────┘    └──────────┘   └──────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Types

### Model

```python
@dataclass
class Model:
    id: str                          # Model identifier
    api: Api                         # API type (e.g., "openai-completions")
    provider: Provider               # Provider name (e.g., "openai")
    name: str                        # Human-readable name
    base_url: str | None             # Custom endpoint
    capabilities: ModelCapabilities  # Feature flags
    pricing: ModelPricing            # Cost per token
    context_window: int              # Max context size
    compat: dict | None              # Provider-specific options
```

### ApiProvider Protocol

```python
class ApiProvider(ABC):
    """Base class for all API providers."""
    
    @abstractmethod
    def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """Stream completion events."""
        pass
    
    @abstractmethod
    def stream_simple(
        self,
        model: Model,
        context: Context,
        options: SimpleStreamOptions,
    ) -> AssistantMessageEventStream:
        """Stream with simplified options."""
        pass
```

## Provider Registry

Providers are registered in `api_registry.py`:

```python
# Register a provider
from pi_ai import register_api_provider

register_api_provider("openai-completions", OpenAIProvider())

# Get a provider
from pi_ai import get_api_provider

provider = get_api_provider("openai-completions")
stream = provider.stream(model, context, options)
```

## Provider Implementation

### OpenAI Provider Example

```python
class OpenAIProvider(ApiProvider):
    """OpenAI API provider implementation."""
    
    def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        
        # 1. Convert context to OpenAI format
        messages = self._convert_messages(context.messages)
        
        # 2. Build request payload
        payload = {
            "model": model.id,
            "messages": messages,
            "stream": True,
        }
        
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        
        if context.tools:
            payload["tools"] = self._convert_tools(context.tools)
        
        # 3. Make streaming request
        response = requests.post(
            f"{model.base_url or 'https://api.openai.com/v1'}/chat/completions",
            headers={"Authorization": f"Bearer {options.api_key}"},
            json=payload,
            stream=True,
        )
        
        # 4. Parse SSE stream and yield events
        stream = AssistantMessageEventStream()
        
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = json.loads(line[6:])
                
                # Extract delta
                delta = data["choices"][0]["delta"]
                
                if "content" in delta:
                    stream.push(TextDeltaEvent(delta=delta["content"]))
                
                elif "tool_calls" in delta:
                    stream.push(ToolCallDeltaEvent(
                        delta=json.dumps(delta["tool_calls"])
                    ))
        
        stream.end()
        return stream
```

### Provider-Specific Adaptations

Different providers have different APIs. The provider layer normalizes these:

| Feature | OpenAI | Anthropic | Google |
|---------|--------|-----------|--------|
| Streaming | SSE | SSE | Server-streaming gRPC |
| Tool format | JSON Schema | JSON Schema | Protobuf-like |
| Content format | string/array | string | parts array |
| Reasoning | `reasoning_effort` | `thinking` | `thinking_budget` |

## Message Conversion

### OpenAI Format

```python
def _convert_messages(self, messages: list[Message]) -> list[dict]:
    result = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            result.append({
                "role": "user",
                "content": msg.content if isinstance(msg.content, str)
                          else self._convert_content_list(msg.content)
            })
        elif isinstance(msg, AssistantMessage):
            result.append({
                "role": "assistant",
                "content": self._extract_text(msg),
                "tool_calls": self._extract_tool_calls(msg),
            })
        elif isinstance(msg, ToolResultMessage):
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": self._extract_content(msg),
            })
    return result
```

### Anthropic Format

```python
def _convert_messages(self, messages: list[Message]) -> tuple[str, list[dict]]:
    """Anthropic uses system prompt + messages."""
    system = ""
    converted = []
    
    for msg in messages:
        if msg.role == "system":
            system = msg.content
        else:
            converted.append({
                "role": msg.role,
                "content": self._convert_content(msg.content),
            })
    
    return system, converted
```

## Tool Conversion

### To OpenAI Format

```python
def _convert_tools(self, tools: list[Tool]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
        }
        for tool in tools
    ]
```

### From OpenAI Response

```python
def _parse_tool_calls(self, data: dict) -> list[ToolCall]:
    tool_calls = []
    for tc in data["choices"][0]["message"].get("tool_calls", []:
        tool_calls.append(ToolCall(
            id=tc["id"],
            name=tc["function"]["name"],
            arguments=json.loads(tc["function"]["arguments"]),
        ))
    return tool_calls
```

## Streaming Events

Providers normalize streaming to common events:

```python
class AssistantMessageEventStream:
    """Normalizes different streaming formats."""
    
    # Common events all providers emit:
    - StartEvent          # Stream started
    - TextStartEvent      # Text content starting
    - TextDeltaEvent      # Text chunk
    - TextEndEvent        # Text content complete
    - ToolCallStartEvent  # Tool call starting
    - ToolCallDeltaEvent  # Tool call args streaming
    - ToolCallEndEvent    # Tool call complete
    - UsageEvent          # Token usage update
    - ErrorEvent          # Error occurred
    - DoneEvent           # Stream complete
```

## Adding a New Provider

### 1. Create Provider Class

```python
# pi_ai/providers/my_provider.py
from pi_ai import ApiProvider, Model, Context, StreamOptions

class MyProvider(ApiProvider):
    def stream(self, model, context, options):
        stream = AssistantMessageEventStream()
        
        # Implementation here
        
        return stream
```

### 2. Register Provider

```python
# pi_ai/register_builtins.py
from .providers.my_provider import MyProvider

def register_built_in_api_providers():
    register_api_provider("my-api", MyProvider())
```

### 3. Register Models

```python
# pi_ai/models_generated.py (or runtime registration)
from pi_ai import register_model, Model, ModelCapabilities

register_model("my-provider", Model(
    id="my-model",
    api="my-api",
    provider="my-provider",
    capabilities=ModelCapabilities(
        supports_tools=True,
        supports_streaming=True,
    ),
))
```

## Provider Capabilities

Check what a provider supports:

```python
from pi_ai import get_model

model = get_model("openai", "gpt-4o")

if model.capabilities.supports_vision:
    # Can send images
    pass

if model.capabilities.supports_tools:
    # Can use function calling
    pass

if model.capabilities.supports_reasoning:
    # Can use thinking/reasoning levels
    pass
```

## Error Handling

Providers normalize errors:

```python
try:
    stream = provider.stream(model, context, options)
except AuthenticationError:
    # Invalid API key
    pass
except RateLimitError:
    # Rate limited
    pass
except ModelNotFoundError:
    # Invalid model ID
    pass
except ProviderError as e:
    # Generic provider error
    pass
```

## Testing Providers

```python
import pytest
from pi_ai import get_model, complete_simple, Context, UserMessage

@pytest.mark.asyncio
async def test_openai_provider():
    model = get_model("openai", "gpt-4o-mini")
    context = Context(messages=[
        UserMessage(content="Say 'Hello' and nothing else.")
    ])
    
    response = await complete_simple(model, context)
    
    assert "Hello" in response.content[0].text
    assert response.usage.total_tokens > 0
```
