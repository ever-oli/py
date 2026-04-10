# Pi Mono Python Documentation

Welcome to the Pi Mono Python documentation!

## Getting Started

New to Pi Mono Python? Start here:

1. **[Getting Started Guide](guides/getting-started.md)** - Installation and first steps
2. **[Configuration Guide](guides/configuration.md)** - Setup and configuration options
3. **[Provider Setup](guides/providers.md)** - Configure API keys for LLM providers
4. **[Tool Usage Guide](guides/tools.md)** - Using and creating tools

## Architecture

Understand how Pi Mono Python works:

- **[Agent Loop](architecture/agent-loop.md)** - The core execution engine
- **[Provider Architecture](architecture/providers.md)** - How LLM providers are structured
- **[Tool Execution](architecture/tools.md)** - How tools are executed

## API Reference

Complete API documentation for all packages:

| Package | Description |
|---------|-------------|
| [pi_ai](api/pi_ai.md) | LLM provider abstraction |
| [pi_agent_core](api/pi_agent_core.md) | Agent framework |
| [pi_coding_agent](api/pi_coding_agent.md) | Coding agent |
| [pi_mom](api/pi_mom.md) | Slack bot |
| [pi_pods](api/pi_pods.md) | Pod management |
| [pi_tui](api/pi_tui.md) | Terminal UI |
| [pi_web_ui](api/pi_web_ui.md) | Web interface |

## Examples

Working code examples:

| Example | Description |
|---------|-------------|
| [basic_chat.py](../examples/basic_chat.py) | Simple LLM chat |
| [coding_agent.py](../examples/coding_agent.py) | Using the coding agent |
| [custom_tool.py](../examples/custom_tool.py) | Creating custom tools |
| [slack_bot.py](../examples/slack_bot.py) | Slack bot setup |
| [web_ui.py](../examples/web_ui.py) | Web UI server |
| [vllm_pods.py](../examples/vllm_pods.py) | GPU pod management |

## Quick Reference

### Common Tasks

**Install all packages:**
```bash
pip install -e ".[dev]"
```

**Run the coding agent:**
```bash
pi-coding-agent
```

**Basic chat with LLM:**
```python
from pi_ai import get_model, complete, Context, UserMessage

model = get_model("openai", "gpt-4o")
context = Context(messages=[UserMessage(content="Hello!")])
response = await complete(model, context)
```

**Create coding session:**
```python
from pi_coding_agent import create_agent_session

result = await create_agent_session()
session = result.session
response = await session.run("List files")
```

### Environment Variables

| Variable | For | Get From |
|----------|-----|----------|
| `OPENAI_API_KEY` | OpenAI models | [platform.openai.com](https://platform.openai.com) |
| `ANTHROPIC_API_KEY` | Claude models | [console.anthropic.com](https://console.anthropic.com) |
| `GOOGLE_API_KEY` | Gemini models | [aistudio.google.com](https://aistudio.google.com) |
| `MISTRAL_API_KEY` | Mistral models | [console.mistral.ai](https://console.mistral.ai) |
| `OPENROUTER_API_KEY` | Many providers | [openrouter.ai](https://openrouter.ai) |

## Support

- Check the [examples](../examples/) directory
- Read the [architecture guides](architecture/)
- Open an issue on GitHub
