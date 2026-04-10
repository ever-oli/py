# Getting Started with Pi Mono Python

Welcome to Pi Mono Python - a comprehensive ecosystem for building AI agents with Python.

## What is Pi Mono Python?

Pi Mono Python is a monorepo containing packages for building AI-powered applications:

- **pi_ai** - LLM provider abstraction layer supporting OpenAI, Anthropic, Google, Mistral, and more
- **pi_agent_core** - Core agent framework with tool execution and conversation management
- **pi_coding_agent** - Full-featured coding assistant with file operations and shell execution
- **pi_tui** - Terminal UI components for building rich terminal interfaces
- **pi_mom** - Slack bot integration for remote agent access
- **pi_pods** - GPU pod and vLLM management system
- **pi_web_ui** - Web-based interface for agent interaction

## Installation

### Prerequisites

- Python 3.11 or higher
- pip or uv for package management

### Install from Source

```bash
# Clone the repository
git clone https://github.com/your-org/pi-mono-python.git
cd pi-mono-python

# Install all packages in editable mode
pip install -e ".[dev]"

# Or using uv (recommended)
uv pip install -e ".[dev]"
```

### Install Individual Packages

```bash
# Install only the AI package
pip install -e packages/pi_ai

# Install the coding agent
pip install -e packages/pi_coding_agent

# Install with specific extras
pip install -e packages/pi_ai[openai,anthropic]
```

## Quick Start

### 1. Basic Chat with LLM

```python
import asyncio
from pi_ai import get_model, complete_simple, Context, UserMessage

async def main():
    # Get a model (requires OPENAI_API_KEY env var)
    model = get_model("openai", "gpt-4o")
    
    # Create a context with messages
    context = Context(messages=[
        UserMessage(role="user", content="Hello, what can you do?")
    ])
    
    # Get a completion
    response = await complete_simple(model, context)
    print(response.content[0].text)

asyncio.run(main())
```

### 2. Using the Coding Agent

```python
import asyncio
from pi_coding_agent import create_agent_session
from pi_ai import get_model

async def main():
    # Create a session with a specific model
    result = await create_agent_session(
        model=get_model("anthropic", "claude-opus-4")
    )
    session = result.session
    
    # Run a coding task
    response = await session.run(
        "Create a Python function that calculates fibonacci numbers"
    )
    print(response["content"])

asyncio.run(main())
```

### 3. Using the CLI

```bash
# Start an interactive coding session
pi-coding-agent

# Run a single command
pi-coding-agent "List all Python files in the current directory"

# Continue the last session
pi-coding-agent --continue

# List available sessions
pi-coding-agent --list-sessions
```

## Configuration

### Environment Variables

Create a `.env` file or set these in your environment:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google/Gemini
GOOGLE_API_KEY=...

# Mistral
MISTRAL_API_KEY=...

# OpenRouter (for access to many models)
OPENROUTER_API_KEY=sk-or-...

# For pi_mom Slack bot
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

### Configuration Files

The coding agent stores configuration in `~/.pi/agent/`:

```
~/.pi/agent/
├── settings.json       # Default model and preferences
├── sessions/           # Saved conversation sessions
└── history/            # Command history
```

## Next Steps

- **[Configuration Guide](configuration.md)** - Detailed configuration options
- **[Provider Setup](providers.md)** - Setting up API keys for each provider
- **[Tool Usage](tools.md)** - Using and creating custom tools
- **[Examples](../examples/)** - Working code examples

## Troubleshooting

### Common Issues

**Import errors after installation:**
```bash
# Make sure you're in the virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Reinstall in editable mode
pip install -e ".[dev]"
```

**API key not found:**
```bash
# Check if environment variable is set
echo $OPENAI_API_KEY

# Or set it explicitly
export OPENAI_API_KEY="your-key-here"
```

**Model not found:**
```python
# List available providers
from pi_ai import get_providers
print(get_providers())

# List models for a provider
from pi_ai import get_models
print(get_models("openai"))
```

## Getting Help

- Check the [API Documentation](api/)
- Read the [Architecture Guides](architecture/)
- Open an issue on GitHub
- Join our community Discord
