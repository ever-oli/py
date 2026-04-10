# Provider Setup Guide

This guide walks through setting up API keys for each supported LLM provider.

## Quick Reference

| Provider | Env Variable | Free Tier | Best For |
|----------|--------------|-----------|----------|
| OpenAI | `OPENAI_API_KEY` | $5 credit | General purpose, GPT-4o |
| Anthropic | `ANTHROPIC_API_KEY` | $5 credit | Long context, Claude |
| Google | `GOOGLE_API_KEY` | Generous | Gemini, multimodal |
| Mistral | `MISTRAL_API_KEY` | Limited | European, fast |
| OpenRouter | `OPENROUTER_API_KEY` | Varies | Access to many models |
| Azure | `AZURE_OPENAI_API_KEY` | Pay-as-you-go | Enterprise, compliance |
| AWS Bedrock | `AWS_*` | Trial | AWS ecosystem |

## OpenAI

### Getting an API Key

1. Visit [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Go to **API Keys** → **Create new secret key**
4. Copy the key (starts with `sk-`)

### Setup

```bash
export OPENAI_API_KEY="sk-..."
```

### Usage

```python
from pi_ai import get_model, complete_simple, Context, UserMessage

model = get_model("openai", "gpt-4o")
context = Context(messages=[UserMessage(content="Hello!")])
response = await complete_simple(model, context)
```

### Available Models

```python
from pi_ai import get_models

models = get_models("openai")
# gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, etc.
```

## Anthropic (Claude)

### Getting an API Key

1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Go to **Get API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-`)

### Setup

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### Usage

```python
from pi_ai import get_model

model = get_model("anthropic", "claude-opus-4")
```

### Model IDs

- `claude-opus-4` - Most capable
- `claude-sonnet-4` - Balanced
- `claude-haiku-3` - Fast, economical

## Google (Gemini)

### Getting an API Key

1. Visit [aistudio.google.com](https://aistudio.google.com)
2. Sign in with Google account
3. Go to **Get API key**
4. Create a new key

### Setup

```bash
export GOOGLE_API_KEY="..."
```

### Usage

```python
from pi_ai import get_model

model = get_model("google", "gemini-2.5-pro")
```

### Available Models

- `gemini-2.5-pro` - Latest flagship
- `gemini-2.0-flash` - Fast
- `gemini-1.5-pro` - Long context

## Mistral AI

### Getting an API Key

1. Visit [console.mistral.ai](https://console.mistral.ai)
2. Sign up or log in
3. Go to **API Keys** → **Create API Key**

### Setup

```bash
export MISTRAL_API_KEY="..."
```

### Usage

```python
from pi_ai import get_model

model = get_model("mistral", "mistral-large-latest")
```

## OpenRouter

OpenRouter provides unified access to many models from different providers.

### Getting an API Key

1. Visit [openrouter.ai](https://openrouter.ai)
2. Sign up or log in
3. Go to **Keys** → **Create Key**

### Setup

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

### Usage

```python
from pi_ai import get_model

# Access Anthropic models through OpenRouter
model = get_model("openrouter", "anthropic/claude-3.5-sonnet")

# Or OpenAI
model = get_model("openrouter", "openai/gpt-4o")

# Or many others
model = get_model("openrouter", "meta-llama/llama-3.1-405b")
```

## Azure OpenAI

### Setup

1. Create an Azure OpenAI resource in [Azure Portal](https://portal.azure.com)
2. Deploy a model (e.g., gpt-4)
3. Get the endpoint and key from **Keys and Endpoint**

### Configuration

```bash
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"
```

### Usage

```python
from pi_ai import get_model

model = get_model("azure-openai-responses", "gpt-4")
```

## AWS Bedrock

### Setup

1. Enable Bedrock in your AWS account
2. Request model access in the [Bedrock Console](https://console.aws.amazon.com/bedrock)
3. Create IAM credentials with Bedrock permissions

### Configuration

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

### Usage

```python
from pi_ai import get_model

# Claude through Bedrock
model = get_model("amazon-bedrock", "anthropic.claude-3-opus-20240229-v1:0")

# Or Llama
model = get_model("amazon-bedrock", "meta.llama3-1-405b-instruct-v1:0")
```

## GitHub Copilot

### Setup

GitHub Copilot uses your existing Copilot subscription.

```bash
export GITHUB_TOKEN="ghp_..."  # Personal access token with Copilot scope
```

### Usage

```python
from pi_ai import get_model

model = get_model("github-copilot", "copilot-chat")
```

## Custom / Self-Hosted

For self-hosted models or custom endpoints:

```python
from pi_ai import Model, ModelCapabilities

model = Model(
    id="my-custom-model",
    api="openai-completions",
    provider="custom",
    base_url="http://localhost:8000/v1",
    capabilities=ModelCapabilities(
        supports_tools=True,
        supports_streaming=True,
    ),
)
```

## Testing Your Setup

### Quick Test Script

```python
import asyncio
from pi_ai import get_providers, get_models, get_model, complete_simple, Context, UserMessage

async def test_provider(provider: str, model_id: str):
    """Test a provider configuration."""
    try:
        model = get_model(provider, model_id)
        context = Context(messages=[
            UserMessage(content="Say 'Hello from Pi!' and nothing else.")
        ])
        response = await complete_simple(model, context)
        text = response.content[0].text if response.content else ""
        print(f"✅ {provider}/{model_id}: {text[:50]}...")
        return True
    except Exception as e:
        print(f"❌ {provider}/{model_id}: {e}")
        return False

async def main():
    # Test all configured providers
    tests = [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-haiku-3"),
        ("google", "gemini-2.0-flash"),
    ]
    
    results = await asyncio.gather(*[
        test_provider(p, m) for p, m in tests
    ])
    
    print(f"\nPassed: {sum(results)}/{len(results)}")

asyncio.run(main())
```

## Troubleshooting

### "No API provider registered"

```python
# Make sure to import pi_ai which registers providers
import pi_ai  # This registers built-in providers

from pi_ai import get_model
model = get_model("openai", "gpt-4o")
```

### Rate Limit Errors

```python
from pi_ai import SimpleStreamOptions

options = SimpleStreamOptions(
    max_retry_delay_ms=120000,  # Increase retry delay
)

response = await stream_simple(model, context, options)
```

### Authentication Errors

```bash
# Verify your key is set
echo $OPENAI_API_KEY

# Test with curl
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

## Provider-Specific Features

### Reasoning/Thinking Levels

Not all providers support reasoning levels equally:

```python
from pi_ai import ThinkingLevel

# OpenAI - GPT-5.x series supports xhigh
options = SimpleStreamOptions(reasoning=ThinkingLevel.XHIGH)

# Anthropic - Claude Opus supports extended thinking
options = SimpleStreamOptions(reasoning=ThinkingLevel.HIGH)

# Google - Gemini uses thinking_budget
from pi_ai import ThinkingBudgets
options = SimpleStreamOptions(
    reasoning=ThinkingLevel.HIGH,
    thinking_budgets=ThinkingBudgets(high=8000),
)
```

### Vision Support

```python
from pi_ai import ImageContent

# Check if model supports vision
if model.capabilities.supports_vision:
    message = UserMessage(content=[
        TextContent(text="Describe this image:"),
        ImageContent(data=base64_image, mime_type="image/jpeg")
    ])
```

### Tool Calling

```python
# Check capability
if model.capabilities.supports_tools:
    context = Context(
        messages=[...],
        tools=[my_tool],
    )
```
