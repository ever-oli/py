# Pi AI

LLM provider abstraction layer supporting OpenAI, Anthropic, Google, Mistral, and more.

## Installation

```bash
pip install pi_ai
```

## Quick Start

```python
import asyncio
from pi_ai import get_model, complete, Context, UserMessage

async def main():
    # Get a model (requires OPENAI_API_KEY env var)
    model = get_model("openai", "gpt-4o")
    
    # Create context
    context = Context(messages=[
        UserMessage(content="Hello, what can you do?")
    ])
    
    # Get completion
    response = await complete(model, context)
    print(response.content[0].text)

asyncio.run(main())
```

## Supported Providers

| Provider | Models | Features |
|----------|--------|----------|
| OpenAI | GPT-4o, GPT-4, GPT-3.5 | Streaming, tools, vision |
| Anthropic | Claude Opus, Sonnet, Haiku | Streaming, tools, extended thinking |
| Google | Gemini 2.5, 2.0, 1.5 | Streaming, tools, multimodal |
| Mistral | Mistral Large, Medium, Small | Streaming, tools |
| OpenRouter | Many providers | Unified API |
| Azure | GPT-4, GPT-3.5 | Enterprise features |
| AWS Bedrock | Claude, Llama | AWS integration |

## Usage

### Streaming

```python
from pi_ai import stream, EventType

stream_obj = stream(model, context)
async for event in stream_obj:
    if event.type == EventType.TEXT:
        print(event.text, end="")
```

### Tools

```python
from pi_ai import Tool, Context

tools = [
    Tool(
        name="get_weather",
        description="Get weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"]
        }
    )
]

context = Context(messages=[...], tools=tools)
```

### Reasoning

```python
from pi_ai import complete_simple, ThinkingLevel

response = await complete_simple(
    model, 
    context,
    reasoning=ThinkingLevel.HIGH
)
```

## Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
```

## Documentation

- [Full API Docs](../docs/api/pi_ai.md)
- [Provider Setup Guide](../docs/guides/providers.md)
- [Examples](../examples/basic_chat.py)

## License

MIT
