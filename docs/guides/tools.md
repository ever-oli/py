# Tool Usage Guide

Tools allow AI agents to interact with the outside world - read files, run commands, query databases, and more.

## Built-in Tools

The coding agent comes with these built-in tools:

| Tool | Description | Safety |
|------|-------------|--------|
| `read` | Read file contents | ✅ Read-only |
| `ls` | List directory contents | ✅ Read-only |
| `grep` | Search file contents | ✅ Read-only |
| `find` | Find files by pattern | ✅ Read-only |
| `bash` | Execute shell commands | ⚠️ Destructive |
| `write` | Write files | ⚠️ Destructive |
| `edit` | Edit files in place | ⚠️ Destructive |

## Using Built-in Tools

### Read-Only Mode

```python
from pi_coding_agent import create_agent_session, read_only_tools

result = create_agent_session(tools=read_only_tools)
session = result.session

# Agent can only read, not modify
response = await session.run("Show me the project structure")
```

### Full Coding Tools

```python
from pi_coding_agent import create_agent_session, coding_tools

result = create_agent_session(tools=coding_tools)
session = result.session

# Agent can read, write, edit, and run commands
response = await session.run(
    "Create a Python script that prints hello world"
)
```

### All Tools

```python
from pi_coding_agent import create_agent_session, all_tools

result = create_agent_session(tools=all_tools)
```

## Tool Reference

### read

Read file contents with optional offset and limit.

```python
# Agent uses via natural language
"Read the first 50 lines of README.md"

# Or directly
from pi_coding_agent.tools import read_tool

result = await read_tool["execute"](
    file_path="README.md",
    limit=50,
    offset=1
)
```

**Parameters:**
- `file_path` (string, required): Path to the file
- `limit` (number): Maximum lines to read (default: 2000)
- `offset` (number): Starting line number (1-indexed, default: 1)

### ls

List directory contents.

```python
result = await ls_tool["execute"](path=".")
```

**Parameters:**
- `path` (string, required): Directory path

### grep

Search for patterns in files.

```python
result = await grep_tool["execute"](
    pattern="def ",
    paths=["src/"],
    output_limit=50
)
```

**Parameters:**
- `pattern` (string, required): Regex pattern to search
- `paths` (array): Paths to search (default: ["."])
- `output_limit` (number): Max results (default: 50)

### find

Find files by name pattern.

```python
result = await find_tool["execute"](
    pattern="*.py",
    paths=["src/"]
)
```

**Parameters:**
- `pattern` (string, required): Glob pattern
- `paths` (array): Paths to search (default: ["."])

### bash

Execute shell commands.

```python
result = await bash_tool["execute"](
    command="ls -la",
    workdir="/tmp"
)
```

**Parameters:**
- `command` (string, required): Shell command
- `workdir` (string): Working directory
- `timeout` (number): Timeout in seconds

### write

Write content to a file.

```python
result = await write_tool["execute"](
    file_path="hello.py",
    content="print('Hello, World!')"
)
```

**Parameters:**
- `file_path` (string, required): Path to write
- `content` (string, required): Content to write

### edit

Edit a file with targeted replacements.

```python
result = await edit_tool["execute"](
    file_path="hello.py",
    old_string="print('Hello, World!')",
    new_string="print('Hello, Pi!')"
)
```

**Parameters:**
- `file_path` (string, required): Path to edit
- `old_string` (string, required): Text to replace
- `new_string` (string, required): Replacement text

## Creating Custom Tools

### Basic Custom Tool

```python
from typing import Any

async def search_database(query: str, limit: int = 10) -> dict[str, Any]:
    """Search the internal database.
    
    Args:
        query: Search query string
        limit: Maximum results to return
    """
    # Your implementation
    results = db.search(query, limit=limit)
    return {
        "content": f"Found {len(results)} results:\n" + "\n".join(results)
    }

# Define the tool schema
search_tool = {
    "name": "search_database",
    "description": "Search the internal knowledge base for information",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return",
                "default": 10
            }
        },
        "required": ["query"]
    },
    "execute": search_database
}

# Use with agent
from pi_coding_agent import create_agent_session

result = create_agent_session(
    custom_tools=[search_tool]
)
```

### Tool with State

```python
class CalculatorTool:
    def __init__(self):
        self.history = []
    
    async def calculate(self, expression: str) -> dict[str, Any]:
        """Evaluate a mathematical expression."""
        try:
            result = eval(expression)  # In production, use a safe evaluator
            self.history.append(f"{expression} = {result}")
            return {"content": str(result)}
        except Exception as e:
            return {"content": f"Error: {e}", "is_error": True}
    
    async def get_history(self) -> dict[str, Any]:
        """Get calculation history."""
        return {"content": "\n".join(self.history)}

calc = CalculatorTool()

calculator_tools = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"]
        },
        "execute": calc.calculate
    },
    {
        "name": "calc_history",
        "description": "Get calculation history",
        "parameters": {"type": "object", "properties": {}},
        "execute": calc.get_history
    }
]

result = create_agent_session(custom_tools=calculator_tools)
```

### Async HTTP Tool

```python
import aiohttp

async def fetch_weather(city: str) -> dict[str, Any]:
    """Fetch weather information for a city.
    
    Args:
        city: City name (e.g., "London", "New York")
    """
    async with aiohttp.ClientSession() as session:
        # Using a weather API
        url = f"https://api.weather.com/v1/current?city={city}"
        async with session.get(url) as response:
            data = await response.json()
            return {
                "content": f"Weather in {city}: {data['temperature']}°C, {data['condition']}"
            }

weather_tool = {
    "name": "get_weather",
    "description": "Get current weather for a city",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"}
        },
        "required": ["city"]
    },
    "execute": fetch_weather
}
```

### Tool with Files

```python
from pathlib import Path

async def analyze_csv(file_path: str) -> dict[str, Any]:
    """Analyze a CSV file and return statistics.
    
    Args:
        file_path: Path to the CSV file
    """
    import pandas as pd
    
    path = Path(file_path)
    if not path.exists():
        return {"content": f"File not found: {file_path}", "is_error": True}
    
    df = pd.read_csv(file_path)
    
    stats = {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "summary": df.describe().to_string()
    }
    
    return {
        "content": f"""
CSV Analysis for {file_path}:
- Rows: {stats['rows']}
- Columns: {stats['columns']}
- Column names: {', '.join(stats['column_names'])}

Summary statistics:
{stats['summary']}
"""
    }

csv_tool = {
    "name": "analyze_csv",
    "description": "Analyze a CSV file and return statistics",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to CSV file"}
        },
        "required": ["file_path"]
    },
    "execute": analyze_csv
}
```

## Tool Best Practices

### 1. Clear Descriptions

```python
# Good
tool = {
    "name": "search_docs",
    "description": "Search the documentation for a specific topic. Returns matching pages with summaries.",
    # ...
}

# Bad
tool = {
    "name": "search",
    "description": "Searches stuff",
    # ...
}
```

### 2. Validate Inputs

```python
async def safe_tool(user_id: str) -> dict[str, Any]:
    # Validate format
    if not user_id.startswith("user_"):
        return {
            "content": "Invalid user_id format. Must start with 'user_'",
            "is_error": True
        }
    
    # Proceed with validated input
    # ...
```

### 3. Handle Errors Gracefully

```python
async def robust_tool(api_endpoint: str) -> dict[str, Any]:
    try:
        result = await call_api(api_endpoint)
        return {"content": format_result(result)}
    except NetworkError as e:
        return {"content": f"Network error: {e}. Please retry.", "is_error": True}
    except ValidationError as e:
        return {"content": f"Invalid input: {e}", "is_error": True}
    except Exception as e:
        return {"content": f"Unexpected error: {e}", "is_error": True}
```

### 4. Return Structured Content

```python
# Good - easy for LLM to parse
return {
    "content": [
        {"type": "text", "text": "Found 3 results:"},
        {"type": "text", "text": "1. First item"},
        {"type": "text", "text": "2. Second item"},
    ]
}

# Also good - formatted text
return {
    "content": """
## Search Results

1. **First Item** - Description here
2. **Second Item** - Description here
"""
}
```

## Tool Execution Modes

### Sequential (Default)

Tools execute one at a time:

```python
from pi_agent_core import AgentOptions

options = AgentOptions(toolExecution="sequential")
```

### Parallel

Tools execute concurrently:

```python
options = AgentOptions(toolExecution="parallel")
```

### Custom Execution

```python
async def custom_executor(tools_calls):
    # Custom logic for executing tool calls
    results = []
    for call in tool_calls:
        if call.name == "risky_operation":
            # Require confirmation
            if await confirm_with_user(call):
                result = await execute(call)
            else:
                result = {"error": "User cancelled"}
        else:
            result = await execute(call)
        results.append(result)
    return results
```

## Testing Tools

```python
import pytest

@pytest.mark.asyncio
async def test_read_tool():
    from pi_coding_agent.tools import read_tool
    
    # Create a test file
    test_file = "/tmp/test.txt"
    with open(test_file, "w") as f:
        f.write("Hello, World!")
    
    # Test the tool
    result = await read_tool["execute"](file_path=test_file)
    
    assert "Hello, World!" in result["content"]

@pytest.mark.asyncio
async def test_custom_tool():
    tool = {
        "name": "double",
        "execute": lambda x: {"content": str(x * 2)}
    }
    
    result = await tool["execute"](5)
    assert result["content"] == "10"
```
