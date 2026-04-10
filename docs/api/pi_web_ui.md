# Pi Web UI API Reference

Web-based interface for the Pi ecosystem.

## Server

### Creating an App

```python
from pi_web_ui import create_app

app = create_app(
    debug=False,
    data_dir="~/.pi/web-ui",
)
```

### Running the Server

```python
from pi_web_ui import run_server

# Run with defaults
run_server()

# Or with custom config
run_server(
    host="0.0.0.0",
    port=8000,
    reload=True,
)
```

### FastAPI App

```python
from pi_web_ui.server import app

# Add custom routes
@app.get("/api/custom")
async def custom_endpoint():
    return {"message": "Hello"}
```

## Chat Panel

### Creating a Chat Panel

```python
from pi_web_ui import ChatPanel

panel = ChatPanel(
    session_id="session-123",
    model="openai/gpt-4o",
)
```

### Sending Messages

```python
# Send a message
response = await panel.send_message("Hello!")

# Stream a message
async for chunk in panel.stream_message("Tell me a story"):
    print(chunk.content, end="")
```

### Managing Context

```python
# Get message history
history = panel.get_history()

# Clear history
panel.clear_history()

# Set system prompt
panel.set_system_prompt("You are a helpful assistant")
```

## Storage

### AppStorage

```python
from pi_web_ui import AppStorage

storage = AppStorage(data_dir="~/.pi/web-ui")

# Save data
storage.save("key", {"data": "value"})

# Load data
data = storage.load("key")

# Delete
storage.delete("key")

# List keys
keys = storage.list_keys()
```

### SessionStore

```python
from pi_web_ui import SessionStore

sessions = SessionStore()

# Create session
session = sessions.create(
    model="openai/gpt-4o",
    system_prompt="You are helpful",
)

# Get session
session = sessions.get(session_id)

# Update session
sessions.update(session_id, messages=new_messages)

# Delete session
sessions.delete(session_id)

# List sessions
all_sessions = sessions.list()
```

### SettingsStore

```python
from pi_web_ui import SettingsStore

settings = SettingsStore()

# Get setting
model = settings.get("default_model", "openai/gpt-4o")

# Set setting
settings.set("default_model", "anthropic/claude-opus-4")

# Get all settings
all_settings = settings.get_all()
```

## Chat

### Chat Handler

```python
from pi_web_ui.chat import ChatHandler

handler = ChatHandler()

# Handle chat request
response = await handler.handle(
    message="Hello",
    session_id="session-123",
    model="openai/gpt-4o",
)
```

### WebSocket Chat

```python
from pi_web_ui.chat import WebSocketChat

# Connect
ws_chat = WebSocketChat(websocket)

# Handle messages
async for message in ws_chat:
    async for chunk in ws_chat.stream_response(message):
        await ws_chat.send(chunk)
```

## CLI

### Running via CLI

```bash
# Start server
python -m pi_web_ui

# With options
python -m pi_web_ui --host 0.0.0.0 --port 8080

# With reload (development)
python -m pi_web_ui --reload
```

### CLI Arguments

```python
from pi_web_ui.cli import parse_args

args = parse_args()
# args.host: Server host
# args.port: Server port
# args.reload: Enable auto-reload
# args.data_dir: Data directory
```

## Utilities

### Attachment Handling

```python
from pi_web_ui.utils.attachment import (
    save_attachment,
    get_attachment,
    delete_attachment,
)

# Save uploaded file
path = await save_attachment(uploaded_file)

# Get attachment
data = await get_attachment(attachment_id)

# Delete
await delete_attachment(attachment_id)
```
