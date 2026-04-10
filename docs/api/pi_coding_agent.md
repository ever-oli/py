# Pi Coding Agent API Reference

Full-featured coding assistant with file operations and shell execution.

## SDK

### `create_agent_session(options)`

Create a new agent session.

```python
from pi_coding_agent import create_agent_session
from pi_ai import get_model

result = await create_agent_session(
    model=get_model("openai", "gpt-4o"),
    thinking_level="high",
)

session = result.session
```

### `create_agent_session_sync(options)`

Synchronous version.

```python
from pi_coding_agent import create_agent_session_sync

result = create_agent_session_sync()
session = result.session
```

### Session Options

```python
from pi_coding_agent import CreateAgentSessionOptions
from pi_ai import ThinkingLevel

options = CreateAgentSessionOptions(
    cwd="/path/to/project",
    agent_dir="~/.pi/agent",
    model=get_model("openai", "gpt-4o"),
    thinking_level=ThinkingLevel.HIGH,
    scoped_models=[
        {"provider": "openai", "model": "gpt-4o"},
        {"provider": "anthropic", "model": "claude-opus-4"},
    ],
    tools=coding_tools,
    custom_tools=[my_custom_tool],
    session_id="20250410_123456",  # Resume specific session
    continue_last=True,  # Resume most recent session
    no_session=False,  # Disable persistence
)
```

## AgentSession

### Properties

```python
session.session_id       # Session identifier
session.is_active        # Whether session is running
session.usage            # Token usage statistics
session.persistence_enabled  # Whether persistence is on
```

### Running the Agent

```python
# Run with a message
response = await session.run("Create a Python script")

# Response format
{
    "role": "assistant",
    "content": "Here's the script...",
    "tool_calls": [...],  # If tools were used
    "tool_results": [...],  # Results from tools
    "usage": {
        "input": 100,
        "output": 200,
        "total": 300,
        "cost": 0.005
    }
}
```

### Managing Context

```python
# Add a message manually
session.add_message("user", "Hello")
session.add_message("assistant", "Hi there!")

# Get available tools
tools = session.get_tools()
```

### Model Management

```python
# Change model mid-session
session.set_model(new_model)

# Change thinking level
session.set_thinking_level("xhigh")
```

### Tool Execution

```python
# Execute a tool directly
result = await session.execute_tool("read", file_path="test.txt")
```

### Session Persistence

```python
# Manually save session
session_id = session.save_session()

# Create from saved data
from pi_coding_agent import AgentSession

session = AgentSession.from_session_data(
    session_data=loaded_data,
    agent_dir="~/.pi/agent",
)
```

## Session Management

### `list_sessions(agent_dir, limit)`

List available sessions.

```python
from pi_coding_agent import list_sessions

sessions = list_sessions(limit=10)
for session in sessions:
    print(f"{session.id}: {session.preview}")
```

### `format_session_for_display(session)`

Format a session for display.

```python
from pi_coding_agent import format_session_for_display

text = format_session_for_display(session)
print(text)
```

## Session Store

### SessionStore

```python
from pi_coding_agent import SessionStore

store = SessionStore("~/.pi/agent")

# Save a session
session_id = store.save_session(
    session_id="my-session",
    messages=[{"role": "user", "content": "Hello"}],
    model="openai/gpt-4o",
    cwd="/project",
)

# Load a session
session_data = store.load_session("my-session")

# List sessions
sessions = store.list_sessions(limit=50)

# Delete a session
store.delete_session("my-session")

# Generate new ID
new_id = store.generate_session_id()
```

### SessionData

```python
from pi_coding_agent import SessionData

data = SessionData(
    id="session-123",
    messages=[...],
    model="openai/gpt-4o",
    cwd="/project",
    created_at=1234567890,
    updated_at=1234567890,
)
```

## Tools

### Built-in Tools

```python
from pi_coding_agent import (
    read_tool,
    bash_tool,
    edit_tool,
    write_tool,
    grep_tool,
    find_tool,
    ls_tool,
)

# Tool sets
coding_tools      # All coding tools
read_only_tools   # Safe read-only tools
all_tools         # All available tools
```

### Creating Tools

```python
from pi_coding_agent.tools import (
    create_read_tool,
    create_bash_tool,
    create_edit_tool,
    create_write_tool,
    create_grep_tool,
    create_find_tool,
    create_ls_tool,
    create_coding_tools,
    create_read_only_tools,
)

# Create with custom working directory
read_tool = create_read_tool("/project/path")
bash_tool = create_bash_tool("/project/path")
all = create_coding_tools("/project/path")
```

### Tool Types

```python
from pi_coding_agent.tools import (
    Tool,
    ToolDef,
    ToolName,
)

# Tool definition
ToolDef = {
    "name": str,
    "description": str,
    "parameters": dict,  # JSON Schema
}

# Full tool
Tool = {
    **ToolDef,
    "execute": Callable,  # Async function
}
```

## CLI

### Running the CLI

```bash
# Interactive mode
pi-coding-agent

# Single command
pi-coding-agent "List files"

# Continue last session
pi-coding-agent --continue

# List sessions
pi-coding-agent --list-sessions

# Resume specific session
pi-coding-agent --session-id 20250410_123456

# No session persistence
pi-coding-agent --no-session
```

### CLI Arguments

```python
from pi_coding_agent.cli.args import parse_args

args = parse_args()
# args.prompt: Optional initial prompt
# args.continue_last: Resume last session
# args.session_id: Specific session to resume
# args.no_session: Disable persistence
# args.list_sessions: List and exit
```

## Configuration

### `get_agent_dir()`

Get the default agent directory.

```python
from pi_coding_agent import get_agent_dir

agent_dir = get_agent_dir()  # ~/.pi/agent
```

### `VERSION`

Package version.

```python
from pi_coding_agent import VERSION

print(VERSION)  # "0.1.0"
```
