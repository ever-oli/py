# Pi Web UI

Web-based interface for the Pi ecosystem.

## Installation

```bash
pip install pi_web_ui
```

## Quick Start

### Run Server

```bash
python -m pi_web_ui
# or
python -m pi_web_ui --host 0.0.0.0 --port 8080
```

Then open http://localhost:8000

### Programmatic

```python
from pi_web_ui import create_app, run_server

# Create app
app = create_app()

# Run server
run_server(host="0.0.0.0", port=8000)
```

## Features

- **Chat Interface**: Web-based chat with agents
- **Session Management**: Persistent conversations
- **File Uploads**: Support for images and documents
- **WebSocket**: Real-time streaming

## Documentation

- [Full API Docs](../docs/api/pi_web_ui.md)
- [Example](../examples/web_ui.py)
