# Tool Execution Architecture

Tools are the primary way agents interact with the outside world. This document covers how tools are defined, executed, and managed.

## Tool Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                     Tool Structure                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐                                               │
│  │   ToolDef   │  JSON Schema definition for LLM              │
│  │             │                                               │
│  │ - name      │  Unique identifier                            │
│  │ - description│ What the tool does (for LLM)                 │
│  │ - parameters│ JSON Schema for arguments                     │
│  └─────────────┘                                               │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────┐                                               │
│  │    Tool     │  Full tool with execution logic               │
│  │             │                                               │
│  │ - name      │  Same as ToolDef                              │
│  │ - description│ Same as ToolDef                              │
│  │ - parameters│ Same as ToolDef                               │
│  │ - execute   │  Async function that does the work            │
│  └─────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Tool Definition

### JSON Schema (for LLM)

```python
tool_def = {
    "name": "read_file",
    "description": "Read the contents of a file",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read"
            },
            "limit": {
                "type": "integer",
                "description": "Max lines to read",
                "default": 100
            }
        },
        "required": ["file_path"]
    }
}
```

### Full Tool (with execution)

```python
async def execute_read(file_path: str, limit: int = 100):
    """Execute the read tool."""
    try:
        with open(file_path) as f:
            lines = f.readlines()[:limit]
        return {
            "content": "".join(lines),
            "is_error": False
        }
    except FileNotFoundError:
        return {
            "content": f"File not found: {file_path}",
            "is_error": True
        }

tool = {
    **tool_def,
    "execute": execute_read
}
```

## Tool Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   Tool Execution Flow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. LLM decides to use tool                                     │
│           │                                                     │
│           ▼                                                     │
│  2. Tool call received from stream                              │
│     {                                                           │
│       "name": "read_file",                                      │
│       "arguments": {"file_path": "/tmp/test.txt"}               │
│     }                                                           │
│           │                                                     │
│           ▼                                                     │
│  3. Validate arguments against schema                           │
│           │                                                     │
│           ▼                                                     │
│  4. Execute tool function                                       │
│           │                                                     │
│           ▼                                                     │
│  5. Convert result to ToolResultMessage                         │
│           │                                                     │
│           ▼                                                     │
│  6. Add to context and continue loop                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Built-in Tools

### Tool Factory Pattern

```python
# pi_coding_agent/tools/tool_factory.py

def create_read_tool(cwd: str) -> Tool:
    """Create a read tool bound to a working directory."""
    
    async def execute(file_path: str, limit: int = 100):
        full_path = os.path.join(cwd, file_path)
        # ... implementation
    
    return {
        "name": "read",
        "description": "Read a file",
        "parameters": {...},
        "execute": execute
    }
```

### Tool Categories

```python
# Read-only tools (safe)
read_only_tools = [
    create_read_tool(cwd),
    create_ls_tool(cwd),
    create_grep_tool(cwd),
    create_find_tool(cwd),
]

# Coding tools (destructive)
coding_tools = read_only_tools + [
    create_bash_tool(cwd),
    create_write_tool(cwd),
    create_edit_tool(cwd),
]
```

## Tool Result Format

### Success Result

```python
{
    "content": "File contents here...",  # str or list[TextContent]
    "is_error": False,
    "details": {                         # Optional extra data
        "line_count": 42,
        "file_size": 1024
    }
}
```

### Error Result

```python
{
    "content": "Error message explaining what went wrong",
    "is_error": True,
    "details": {
        "error_type": "FileNotFoundError",
        "suggestion": "Check the file path and try again"
    }
}
```

## Tool Execution Modes

### Sequential

```python
# Tools execute one at a time, in order
for tool_call in tool_calls:
    result = await execute_tool(tool_call)
    results.append(result)
    
    # Result is available before next tool starts
    if result["is_error"]:
        # Can cancel remaining tools
        break
```

### Parallel

```python
# All tools execute concurrently
results = await asyncio.gather(*[
    execute_tool(tc) for tc in tool_calls
])

# Order matches tool_calls order
```

## Validation

### Schema Validation

```python
from jsonschema import validate

def validate_tool_call(tool_def: ToolDef, arguments: dict):
    """Validate arguments against tool schema."""
    validate(
        instance=arguments,
        schema=tool_def["parameters"]
    )
```

### Custom Validation

```python
async def execute_bash(command: str, workdir: str = "."):
    # Security validation
    dangerous = ["rm -rf /", ":(){ :|:& };:"]
    for d in dangerous:
        if d in command:
            return {
                "content": f"Dangerous command blocked: {d}",
                "is_error": True
            }
    
    # Path validation
    if ".." in workdir:
        return {
            "content": "Path traversal not allowed",
            "is_error": True
        }
    
    # Execute
    # ...
```

## Custom Tool Example

### Database Query Tool

```python
import aiosqlite

async def create_db_tool(db_path: str) -> Tool:
    """Create a database query tool."""
    
    async def execute(query: str, params: list = None):
        """Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters
        """
        try:
            async with aiosqlite.connect(db_path) as db:
                if query.strip().upper().startswith("SELECT"):
                    async with db.execute(query, params or []) as cursor:
                        rows = await cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                        
                        # Format as table
                        result = "| " + " | ".join(columns) + " |\n"
                        result += "|" + "|".join(["---"] * len(columns)) + "|\n"
                        for row in rows:
                            result += "| " + " | ".join(map(str, row)) + " |\n"
                        
                        return {"content": result}
                else:
                    await db.execute(query, params or [])
                    await db.commit()
                    return {"content": "Query executed successfully"}
                    
        except Exception as e:
            return {
                "content": f"Database error: {e}",
                "is_error": True
            }
    
    return {
        "name": "query_database",
        "description": "Execute SQL queries on the project database",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL query to execute"
                },
                "params": {
                    "type": "array",
                    "description": "Query parameters",
                    "default": []
                }
            },
            "required": ["query"]
        },
        "execute": execute
    }
```

## Tool Lifecycle Hooks

### Before Tool Call

```python
from pi_agent_core import BeforeToolCallContext, BeforeToolCallResult

async def before_tool(context: BeforeToolCallContext):
    """Called before each tool execution."""
    
    # Log the tool call
    logger.info(f"Executing {context.tool_call.name}")
    
    # Check permissions
    if context.tool_call.name == "bash":
        command = context.tool_call.arguments.get("command", "")
        if requires_confirmation(command):
            return BeforeToolCallResult(
                cancel=True,
                reason="This command requires user confirmation"
            )
    
    # Modify arguments
    if context.tool_call.name == "write":
        # Add file header
        args = context.tool_call.arguments
        args["content"] = f"# Auto-generated\n{args['content']}"
        return BeforeToolCallResult(modified_arguments=args)
```

### After Tool Call

```python
from pi_agent_core import AfterToolCallContext, AfterToolCallResult

async def after_tool(context: AfterToolCallContext):
    """Called after each tool execution."""
    
    # Log result
    logger.info(f"Tool {context.tool_call.name} completed")
    
    # Modify result
    if context.result.get("is_error"):
        # Add helpful context
        context.result["content"] += "\n\nTry checking the file path."
    
    return AfterToolCallResult(modified_result=context.result)
```
