# Example Extension for pi_coding_agent

This directory contains an example extension demonstrating the extension system.

## Installation

```bash
# Copy to extensions directory
cp -r examples/extension ~/.pi/extensions/example-tools

# Or install via CLI
pi-coding-agent --install-extension examples/extension
```

## Tools Provided

### calculator
Evaluate mathematical expressions safely.

```python
result = await calculator_tool(expression="2 + 2 * 5", precision=2)
# Returns: {"success": True, "result": 12, "expression": "2 + 2 * 5"}
```

### uuid
Generate UUIDs (Universally Unique Identifiers).

```python
result = await uuid_tool(count=3, format="standard")
# Returns: {"success": True, "uuids": [...], "count": 3}
```

### qrcode
Generate QR codes from text or URLs.

```python
result = await qrcode_tool(data="https://example.com", size=10)
# Returns: {"success": True, "ascii": "...", "dimensions": "21x21"}
```

## Extension Structure

```
extension/
├── manifest.json      # Extension metadata and configuration
├── extension.py       # Main extension module
└── README.md         # This file
```

## Manifest Format

```json
{
  "name": "example-tools",
  "version": "1.0.0",
  "description": "Example extension",
  "author": "Pi Team",
  "main": "extension",
  "tools": ["create_calculator_tool", "create_uuid_tool"],
  "commands": ["example_command"],
  "hooks": {"on_init": "on_extension_init"},
  "default_config": {"precision": 2}
}
```

## Creating Your Own Extension

1. Create a new directory in `~/.pi/extensions/`
2. Create `manifest.json` with your extension metadata
3. Create your main Python module with tool functions
4. Restart pi-coding-agent or use `--install-extension`

## Tool Function Pattern

```python
async def my_tool(arg1: str, arg2: int = 0) -> dict[str, Any]:
    """Tool description."""
    try:
        # Do something
        return {"success": True, "result": ...}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_my_tool(cwd: str | None = None) -> Tool:
    """Create the tool definition."""
    return {
        "name": "my_tool",
        "description": "What this tool does...",
        "parameters": {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"},
                "arg2": {"type": "integer", "default": 0},
            },
            "required": ["arg1"],
        },
        "execute": my_tool,
    }
```
