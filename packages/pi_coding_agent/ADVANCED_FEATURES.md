# Pi Coding Agent - Advanced Features

This enhanced version of pi_coding_agent includes advanced tools, extension system, configuration management, file watching, and background execution capabilities.

## Table of Contents

1. [Additional Tools](#additional-tools)
2. [Extension System](#extension-system)
3. [Advanced CLI Features](#advanced-cli-features)
4. [Background Execution](#background-execution)
5. [File Watching](#file-watching)

---

## Additional Tools

### Browser Tool (`browser`)

Web browser automation using Playwright.

```python
result = await browser_tool(
    url="https://example.com",
    actions=[
        {"action": "click", "selector": "#button"},
        {"action": "type", "selector": "#input", "text": "hello"},
        {"action": "screenshot"},
    ]
)
```

**Supported actions:**
- `click` - Click an element
- `type` - Type text into input
- `press` - Press a key
- `scroll` - Scroll page
- `wait` - Wait for element or delay
- `screenshot` - Take full page screenshot
- `evaluate` - Execute JavaScript
- `select` - Select dropdown option

**Installation:**
```bash
pip install pi-coding-agent[browser]
playwright install
```

### Web Fetch Tool (`web_fetch`)

Fetch and extract webpage content.

```python
result = await web_fetch_tool(
    url="https://example.com/article",
    extract_mode="markdown",  # or "text" or "html"
    max_chars=5000
)
```

### Python Tool (`python`)

Execute Python code safely in a sandboxed environment.

```python
result = await python_tool(
    code="""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
""",
    timeout=30,
    safe_mode=True
)
```

### Git Tool (`git`)

Git version control operations.

```python
# Check status
result = await git_tool("status")

# View log
result = await git_tool("log", args=["--oneline", "-10"])

# Stage and commit
await git_tool("add", args=["."])
result = await git_tool("commit", args=["-m", "Initial commit"])
```

### Docker Tool (`docker`)

Docker container management.

```python
# List containers
result = await docker_tool("ps")

# Run container
result = await docker_tool(
    "run",
    args=["nginx:latest"],
    options={"name": "my-nginx", "p": ["8080:80"], "d": True}
)

# Execute command
result = await docker_tool("exec", args=["my-nginx", "ls", "-la"])
```

### Process Tool (`process`)

Process management for running and managing system processes.

```python
# Run a command
result = await process_tool("run", command=["ls", "-la"])

# Run in background
result = await process_tool(
    "run",
    command=["sleep", "60"],
    background=True
)

# Check status
result = await process_tool("status", process_id="proc_1")

# Kill process
result = await process_tool("kill", process_id="proc_1")
```

---

## Extension System

The extension system allows you to create custom tools and commands that extend pi_coding_agent.

### Creating an Extension

1. Create a directory for your extension:
```bash
pi-coding-agent --create-extension my-extension
```

2. This creates a template structure:
```
my-extension/
├── manifest.json    # Extension metadata
├── extension.py     # Main module
└── README.md        # Documentation
```

3. Define your tools in `extension.py`:

```python
from pi_coding_agent.tools import Tool

async def my_tool(query: str) -> dict:
    """My custom tool."""
    return {"success": True, "result": f"You said: {query}"}

def create_my_tool(cwd: str | None = None) -> Tool:
    return {
        "name": "my_tool",
        "description": "My custom tool",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        },
        "execute": my_tool,
    }

# Optional lifecycle functions
def init(config: dict) -> None:
    """Initialize the extension."""
    print(f"Initializing with config: {config}")

def shutdown() -> None:
    """Shutdown the extension."""
    print("Shutting down")
```

4. Update `manifest.json`:

```json
{
  "name": "my-extension",
  "version": "1.0.0",
  "description": "My custom extension",
  "author": "Your Name",
  "main": "extension",
  "tools": ["create_my_tool"],
  "commands": [],
  "requires": [],
  "default_config": {}
}
```

5. Install the extension:

```bash
pi-coding-agent --install-extension /path/to/my-extension
```

### Managing Extensions

```bash
# List installed extensions
pi-coding-agent --list-extensions

# Uninstall an extension
pi-coding-agent --uninstall-extension my-extension

# Create extension template
pi-coding-agent --create-extension new-extension
```

### Programmatic Extension API

```python
from pi_coding_agent import ExtensionManager, register_tool

# Create extension manager
manager = ExtensionManager()

# Load all extensions
extensions = manager.load_all()

# Register a custom tool programmatically
my_tool = {
    "name": "custom_tool",
    "description": "A custom tool",
    "parameters": {"type": "object", "properties": {}},
    "execute": lambda: {"result": "Hello!"}
}
register_tool(my_tool)
```

---

## Advanced CLI Features

### Config File Support

Configuration is stored in `~/.pi/config.json`:

```bash
# View current config
pi-coding-agent --list-config

# Set configuration value
pi-coding-agent --config key=value
```

### Profile Management

Profiles allow you to save different configurations:

```bash
# List profiles
pi-coding-agent --list-profiles

# Create a profile
pi-coding-agent --create-profile dev

# Use a profile
pi-coding-agent --profile dev

# Delete a profile
pi-coding-agent --delete-profile dev
```

Example profile configuration:

```json
{
  "active_profile": "dev",
  "profiles": {
    "default": {
      "model": null,
      "thinking_level": "medium",
      "tools": ["read", "bash", "edit", "write"]
    },
    "dev": {
      "model": "anthropic/claude-opus-4-5",
      "thinking_level": "high",
      "tools": ["read", "bash", "edit", "write", "git", "python"],
      "env": {"DEBUG": "1"}
    }
  }
}
```

### Syntax Highlighting

Enable syntax highlighting in output (requires `pygments`):

```bash
pip install pi-coding-agent[highlight]
```

### Auto-completion

The interactive mode supports tab completion for:
- File paths
- Command history
- Tool names

---

## Background Execution

Run tasks in the background and manage them:

```bash
# Run a background task
pi-coding-agent --background "long running task"

# List background tasks
pi-coding-agent --list-background

# Check status of a background task
pi-coding-agent process status --process_id proc_1

# Kill a background task
pi-coding-agent --kill proc_1
```

Programmatic usage:

```python
from pi_coding_agent.tools import process_tool

# Start a background process
result = await process_tool(
    "run",
    command=["python", "long_script.py"],
    background=True
)
process_id = result["process_id"]

# Check status later
status = await process_tool("status", process_id=process_id)

# Read output
output = await process_tool("read", process_id=process_id)
print(output["stdout"])

# Wait for completion
result = await process_tool("wait", process_id=process_id, timeout=300)
```

---

## File Watching

Watch files for changes and automatically run commands:

```bash
# Watch Python files and run tests on change
pi-coding-agent --watch "*.py" -- python -m pytest

# Watch multiple patterns
pi-coding-agent --watch "src/**/*.py" --watch "tests/**/*.py" -- python -m pytest

# List active watches
pi-coding-agent --list-watches

# Stop watching
pi-coding-agent --unwatch watch_1
```

Programmatic usage:

```python
from pi_coding_agent import watch, unwatch, list_watches

# Start watching
watch_id = await watch(
    patterns=["*.py"],
    command=lambda file_path: print(f"Changed: {file_path}"),
    debounce_ms=500
)

# List watches
watches = list_watches()

# Stop watching
unwatch(watch_id)
```

---

## Example Usage

### Complete Example: Web Scraping

```python
from pi_coding_agent import create_agent_session
from pi_ai import get_model

async def main():
    # Create session with browser tool
    result = await create_agent_session(
        model=get_model("anthropic", "claude-opus-4-5"),
        tools="all"  # Include all tools including browser
    )
    session = result.session
    
    # Ask agent to scrape a website
    response = await session.run("""
    Go to https://example.com and extract all the headings.
    Use the browser tool to navigate and take screenshots.
    """")
    
    print(response["content"])

asyncio.run(main())
```

### Complete Example: Git Workflow

```python
from pi_coding_agent import create_agent_session

async def main():
    result = await create_agent_session()
    session = result.session
    
    response = await session.run("""
    Check the git status of this project, show me the recent commits,
    and suggest what files should be staged for commit.
    """")
    
    print(response["content"])

asyncio.run(main())
```

---

## Installation

```bash
# Basic installation
pip install pi-coding-agent

# With all optional features
pip install pi-coding-agent[all]

# With specific features
pip install pi-coding-agent[browser,docker,highlight]
```

---

## License

MIT
