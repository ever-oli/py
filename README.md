# Pi Mono Python

A monorepo for the Pi ecosystem - AI agents, TUI, web UI, and core utilities.

## Overview

Pi Mono Python is a comprehensive toolkit for building AI-powered applications with Python. It provides a unified interface to multiple LLM providers, a powerful agent framework, terminal and web interfaces, and utilities for deployment.

## Packages

| Package | Description | Status |
|---------|-------------|--------|
| `pi_ai` | LLM provider abstraction layer | ✅ Ready |
| `pi_agent_core` | Core agent framework | ✅ Ready |
| `pi_coding_agent` | Coding assistant agent | ✅ Ready |
| `pi_tui` | Terminal User Interface | 🚧 WIP |
| `pi_mom` | Slack bot integration | 🚧 WIP |
| `pi_pods` | GPU pod management | 🚧 WIP |
| `pi_web_ui` | Web-based interface | 🚧 WIP |

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/pi-mono-python.git
cd pi-mono-python

# Install all packages
pip install -e ".[dev]"
```

### Basic Chat

```python
import asyncio
from pi_ai import get_model, complete, Context, UserMessage

async def main():
    model = get_model("openai", "gpt-4o")
    context = Context(messages=[
        UserMessage(content="Hello!")
    ])
    response = await complete(model, context)
    print(response.content[0].text)

asyncio.run(main())
```

### Coding Agent

```bash
# Interactive mode
pi-coding-agent

# Single command
pi-coding-agent "List all Python files"
```

```python
import asyncio
from pi_coding_agent import create_agent_session

async def main():
    result = await create_agent_session()
    session = result.session
    response = await session.run("Create a Python hello world script")
    print(response["content"])

asyncio.run(main())
```

## Documentation

### User Guides

- [Getting Started](docs/guides/getting-started.md) - First steps with Pi Mono Python
- [Configuration](docs/guides/configuration.md) - Environment variables and config files
- [Provider Setup](docs/guides/providers.md) - Setting up API keys for each provider
- [Tool Usage](docs/guides/tools.md) - Using and creating custom tools

### Architecture

- [Agent Loop](docs/architecture/agent-loop.md) - How the agent loop works
- [Providers](docs/architecture/providers.md) - Provider architecture
- [Tools](docs/architecture/tools.md) - Tool execution architecture

### API Reference

- [pi_ai](docs/api/pi_ai.md) - LLM provider API
- [pi_agent_core](docs/api/pi_agent_core.md) - Agent framework API
- [pi_coding_agent](docs/api/pi_coding_agent.md) - Coding agent API
- [pi_mom](docs/api/pi_mom.md) - Slack bot API
- [pi_pods](docs/api/pi_pods.md) - Pod management API
- [pi_tui](docs/api/pi_tui.md) - Terminal UI API
- [pi_web_ui](docs/api/pi_web_ui.md) - Web UI API

### Examples

- [Basic Chat](examples/basic_chat.py) - Simple LLM conversations
- [Coding Agent](examples/coding_agent.py) - Using the coding agent
- [Custom Tools](examples/custom_tool.py) - Creating custom tools
- [Slack Bot](examples/slack_bot.py) - Running as a Slack bot
- [Web UI](examples/web_ui.py) - Web interface
- [vLLM Pods](examples/vllm_pods.py) - GPU pod management

## Supported Providers

| Provider | Setup | Models |
|----------|-------|--------|
| OpenAI | `OPENAI_API_KEY` | GPT-4o, GPT-4, GPT-3.5 |
| Anthropic | `ANTHROPIC_API_KEY` | Claude Opus, Sonnet, Haiku |
| Google | `GOOGLE_API_KEY` | Gemini 2.5, 2.0, 1.5 |
| Mistral | `MISTRAL_API_KEY` | Mistral Large, Medium |
| OpenRouter | `OPENROUTER_API_KEY` | 100+ models |
| Azure | `AZURE_OPENAI_API_KEY` | GPT-4, GPT-3.5 |
| AWS Bedrock | `AWS_*` | Claude, Llama |

## Project Structure

```
pi-mono-python/
├── packages/
│   ├── pi_agent_core/    # Core agent framework
│   ├── pi_ai/            # LLM integrations
│   ├── pi_tui/           # Terminal UI
│   ├── pi_coding_agent/  # Coding agent
│   ├── pi_mom/           # Slack bot
│   ├── pi_pods/          # Pod management
│   └── pi_web_ui/        # Web interface
├── docs/                 # Documentation
│   ├── guides/           # User guides
│   ├── architecture/     # Architecture docs
│   └── api/              # API reference
├── examples/             # Code examples
├── pyproject.toml        # Workspace config
└── README.md             # This file
```

## Development

```bash
# Run tests
make test

# Run linting
make lint

# Format code
make format

# Type checking
make typecheck

# Run all checks
make all
```

## Environment Variables

```bash
# Required for basic usage
export OPENAI_API_KEY="sk-..."

# For other providers
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."

# For Slack bot
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_SIGNING_SECRET="..."
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - See individual package LICENSE files for details.

## Acknowledgments

Ported from the TypeScript [pi-mono](https://github.com/your-org/pi-mono) project.
