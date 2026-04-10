# Configuration Guide

This guide covers all configuration options for Pi Mono Python packages.

## Environment Variables

### Core API Keys

| Variable | Provider | Required For |
|----------|----------|--------------|
| `OPENAI_API_KEY` | OpenAI | GPT-4, GPT-3.5, Codex |
| `ANTHROPIC_API_KEY` | Anthropic | Claude models |
| `GOOGLE_API_KEY` | Google | Gemini models |
| `MISTRAL_API_KEY` | Mistral AI | Mistral models |
| `OPENROUTER_API_KEY` | OpenRouter | Access to many providers |
| `AZURE_OPENAI_API_KEY` | Azure | Azure OpenAI Service |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS | Amazon Bedrock |
| `GITHUB_TOKEN` | GitHub Copilot | Copilot Chat |

### Optional Settings

```bash
# Default model to use when none specified
PI_DEFAULT_MODEL=openai/gpt-4o

# Default thinking level (off, minimal, low, medium, high, xhigh)
PI_DEFAULT_THINKING=medium

# Session timeout in seconds
PI_SESSION_TIMEOUT=3600

# Enable/disable session persistence
PI_SESSION_PERSISTENCE=true

# Log level (debug, info, warning, error)
PI_LOG_LEVEL=info

# API base URLs (for proxies or custom endpoints)
OPENAI_BASE_URL=https://api.openai.com/v1
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

### Slack Bot Configuration (pi_mom)

```bash
# Required
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret

# Optional
SLACK_APP_TOKEN=xapp-your-app-token  # For Socket Mode
PI_MOM_DEFAULT_MODEL=anthropic/claude-opus-4
PI_MOM_ALLOWED_CHANNELS=C123456,C789012
```

### Web UI Configuration (pi_web_ui)

```bash
# Server settings
PI_WEB_UI_HOST=0.0.0.0
PI_WEB_UI_PORT=8000
PI_WEB_UI_DEBUG=false

# Authentication (optional)
PI_WEB_UI_API_KEY=your-secret-key
PI_WEB_UI_JWT_SECRET=your-jwt-secret

# Storage
PI_WEB_UI_DATA_DIR=~/.pi/web-ui
```

### Pod Management (pi_pods)

```bash
# SSH settings for remote pods
PI_PODS_SSH_KEY=~/.ssh/pi_pods
PI_PODS_SSH_USER=ubuntu

# vLLM settings
PI_PODS_VLLM_IMAGE=vllm/vllm-openai:latest
PI_PODS_DEFAULT_GPU=A100

# Provider API endpoints
RUNPOD_API_KEY=...
LAMBDALABS_API_KEY=...
```

## Configuration Files

### Agent Settings (~/.pi/agent/settings.json)

```json
{
  "defaultModel": {
    "provider": "openai",
    "model": "gpt-4o"
  },
  "thinkingLevel": "medium",
  "scopedModels": [
    {"provider": "openai", "model": "gpt-4o"},
    {"provider": "anthropic", "model": "claude-opus-4"}
  ],
  "tools": {
    "read": {"enabled": true},
    "bash": {"enabled": true},
    "edit": {"enabled": true},
    "write": {"enabled": true}
  },
  "ui": {
    "theme": "dark",
    "autoSave": true
  }
}
```

### Pod Configuration (~/.pi/pods/config.yaml)

```yaml
active_pod: gpu-cluster-01
pods:
  - name: gpu-cluster-01
    host: 192.168.1.100
    user: ubuntu
    gpus:
      - id: gpu-0
        type: A100
        memory: 80GB
    models:
      - name: llama-3-70b
        type: vllm
        port: 8000
  
  - name: runpod-worker
    provider: runpod
    gpu_type: A6000
    image: vllm/vllm-openai:latest
```

### Web UI Settings (~/.pi/web-ui/settings.json)

```json
{
  "sessions": {
    "maxHistory": 100,
    "autoSave": true
  },
  "appearance": {
    "theme": "system",
    "fontSize": 14,
    "codeTheme": "github-dark"
  },
  "shortcuts": {
    "newChat": "Ctrl+N",
    "sendMessage": "Enter",
    "toggleSidebar": "Ctrl+B"
  }
}
```

## Programmatic Configuration

### Creating a Custom Config

```python
from pi_coding_agent import create_agent_session
from pi_ai import get_model, Model, ModelCapabilities

# Create a custom model configuration
custom_model = Model(
    id="gpt-4o",
    api="openai-completions",
    provider="openai",
    name="Custom GPT-4o",
    base_url="https://proxy.my-company.com/v1",
    capabilities=ModelCapabilities(
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
    ),
)

# Create session with custom config
result = create_agent_session(
    model=custom_model,
    thinking_level="high",
    custom_tools=[my_custom_tool],
)
```

### Provider-Specific Options

```python
from pi_ai import stream_simple, SimpleStreamOptions, CacheRetention

options = SimpleStreamOptions(
    temperature=0.7,
    max_tokens=4096,
    reasoning="high",
    cache_retention=CacheRetention.LONG,  # For prompt caching
)

response = await stream_simple(model, context, options)
```

## Advanced Configuration

### Custom Tool Registration

```python
from pi_coding_agent import create_agent_session

async def my_custom_handler(query: str):
    """Custom tool implementation."""
    return {"result": f"Processed: {query}"}

custom_tool = {
    "name": "custom_search",
    "description": "Search internal knowledge base",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    },
    "execute": my_custom_handler
}

result = create_agent_session(custom_tools=[custom_tool])
```

### Agent Loop Configuration

```python
from pi_agent_core import Agent, AgentOptions
from pi_ai import ThinkingBudgets

options = AgentOptions(
    steeringMode="all",  # Queue mode for user messages
    followUpMode="one-at-a-time",
    toolExecution="sequential",  # or "parallel"
    thinkingBudgets=ThinkingBudgets(
        minimal=1024,
        low=2048,
        medium=4096,
        high=8192,
    ),
)

agent = Agent(options)
```

## Security Best Practices

### API Key Management

1. **Never commit API keys to version control**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   echo "*.key" >> .gitignore
   ```

2. **Use environment-specific configs**
   ```bash
   # .env.development
   OPENAI_API_KEY=sk-test-...
   
   # .env.production
   OPENAI_API_KEY=sk-prod-...
   ```

3. **Use a secrets manager in production**
   ```python
   import os
   from aws_secretsmanager import get_secret
   
   if os.getenv("ENV") == "production":
       os.environ["OPENAI_API_KEY"] = get_secret("openai-api-key")
   ```

### Session Security

```python
# Disable session persistence for sensitive work
result = create_agent_session(no_session=True)

# Or use encrypted storage
result = create_agent_session(
    session_store=EncryptedSessionStore(key=my_key)
)
```

## Debugging Configuration

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("pi_ai").setLevel(logging.DEBUG)
logging.getLogger("pi_agent_core").setLevel(logging.DEBUG)
```

### Request Inspection

```python
from pi_ai import SimpleStreamOptions

def inspect_payload(payload: dict, model):
    """Inspect/modify API payload before sending."""
    print(f"Sending to {model.provider}/{model.id}:")
    print(json.dumps(payload, indent=2))
    return payload  # Return modified payload or None to cancel

options = SimpleStreamOptions(
    on_payload=inspect_payload,
)
```

## Migration from TypeScript

If you're migrating from the TypeScript version:

| TypeScript | Python | Notes |
|------------|--------|-------|
| `config.json` | `settings.json` | Same format |
| `PI_OPENAI_API_KEY` | `OPENAI_API_KEY` | Simpler naming |
| `~/.pi-agent/` | `~/.pi/agent/` | Consolidated location |
| `agent.config.ts` | `config.py` | Python module |
