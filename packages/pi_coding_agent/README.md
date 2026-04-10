# Pi Coding Agent

Full-featured coding assistant with file operations and shell execution.

## Installation

```bash
pip install pi_coding_agent
```

## Quick Start

### CLI Usage

```bash
# Interactive mode
pi-coding-agent

# Single command
pi-coding-agent "List all Python files"

# Continue last session
pi-coding-agent --continue
```

### Programmatic Usage

```python
import asyncio
from pi_coding_agent import create_agent_session
from pi_ai import get_model

async def main():
    result = await create_agent_session(
        model=get_model("openai", "gpt-4o")
    )
    session = result.session
    
    response = await session.run(
        "Create a Python function to calculate fibonacci"
    )
    print(response["content"])

asyncio.run(main())
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read` | Read file contents |
| `ls` | List directory contents |
| `grep` | Search file contents |
| `find` | Find files by pattern |
| `bash` | Execute shell commands |
| `write` | Write files |
| `edit` | Edit files in place |

## Features

- **Session Persistence**: Conversations saved to `~/.pi/agent/`
- **Multiple Models**: Switch between providers
- **Custom Tools**: Add your own tools
- **Read-only Mode**: Safe exploration without modifications

## Configuration

```python
from pi_coding_agent import CreateAgentSessionOptions
from pi_ai import ThinkingLevel

options = CreateAgentSessionOptions(
    cwd="/project/path",
    model=get_model("openai", "gpt-4o"),
    thinking_level=ThinkingLevel.HIGH,
    tools=coding_tools,
    custom_tools=[my_tool],
)
```

## Documentation

- [Full API Docs](../docs/api/pi_coding_agent.md)
- [Tool Usage Guide](../docs/guides/tools.md)
- [Examples](../examples/coding_agent.py)
