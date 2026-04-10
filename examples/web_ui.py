#!/usr/bin/env python3
"""
Web UI Example - Running pi_web_ui server.

This example demonstrates:
- Starting the web UI server
- Creating chat sessions
- Handling file uploads
- Managing settings
"""

import asyncio
import os
from pathlib import Path

# Note: These imports require pi_web_ui to be installed
# pip install -e packages/pi_web_ui

try:
    from pi_web_ui import create_app, run_server, ChatPanel
    from pi_web_ui import AppStorage, SessionStore, SettingsStore
except ImportError:
    print("pi_web_ui package not installed. Install with:")
    print("  pip install -e packages/pi_web_ui")
    exit(1)


# ============================================================================
# Example 1: Basic Server
# ============================================================================

async def basic_server_example():
    """Example: Basic server setup."""
    print("=" * 60)
    print("Basic Web UI Server Example")
    print("=" * 60)
    
    print("""
Start the web UI server:

    from pi_web_ui import run_server
    
    # Run with defaults (localhost:8000)
    run_server()
    
    # Or with custom settings
    run_server(
        host="0.0.0.0",
        port=8080,
        reload=True,  # Auto-reload on code changes
    )

Or use the command line:

    python -m pi_web_ui
    python -m pi_web_ui --host 0.0.0.0 --port 8080 --reload

The web UI will be available at http://localhost:8000
""")
    print()


# ============================================================================
# Example 2: Creating the App
# ============================================================================

async def create_app_example():
    """Example: Creating a FastAPI app."""
    print("=" * 60)
    print("Creating FastAPI App Example")
    print("=" * 60)
    
    print("""
Create a FastAPI app with Pi Web UI:

    from pi_web_ui import create_app
    from fastapi import Request
    
    # Create the app
    app = create_app(
        debug=False,
        data_dir="~/.pi/web-ui",
    )
    
    # Add custom routes
    @app.get("/api/status")
    async def status():
        return {"status": "ok", "version": "0.1.0"}
    
    @app.post("/api/custom")
    async def custom_endpoint(request: Request):
        data = await request.json()
        return {"received": data}
    
    # Run the app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

This allows you to extend the web UI with your own endpoints.
""")
    print()


# ============================================================================
# Example 3: Chat Panel
# ============================================================================

async def chat_panel_example():
    """Example: Using ChatPanel programmatically."""
    print("=" * 60)
    print("Chat Panel Example")
    print("=" * 60)
    
    print("""
Interact with the chat system programmatically:

    from pi_web_ui import ChatPanel
    from pi_ai import get_model
    
    # Create a chat panel
    panel = ChatPanel(
        session_id="my-session-123",
        model=get_model("openai", "gpt-4o"),
    )
    
    # Send a message
    response = await panel.send_message("Hello!")
    print(response.content)
    
    # Stream a response
    async for chunk in panel.stream_message("Tell me a story"):
        print(chunk.content, end="")
    
    # Get message history
    history = panel.get_history()
    for msg in history:
        print(f"{msg.role}: {msg.content}")
    
    # Clear history
    panel.clear_history()
    
    # Set system prompt
    panel.set_system_prompt("You are a helpful coding assistant.")

This is useful for:
- Testing the chat system
- Building custom interfaces
- Integrating with other services
""")
    print()


# ============================================================================
# Example 4: Storage
# ============================================================================

async def storage_example():
    """Example: Using storage backends."""
    print("=" * 60)
    print("Storage Example")
    print("=" * 60)
    
    print("""
The web UI provides several storage backends:

1. AppStorage - General purpose storage:

    from pi_web_ui import AppStorage
    
    storage = AppStorage(data_dir="~/.pi/web-ui")
    
    # Save data
    storage.save("my-key", {"data": "value"})
    
    # Load data
    data = storage.load("my-key")
    
    # Delete
    storage.delete("my-key")
    
    # List keys
    keys = storage.list_keys()

2. SessionStore - Chat session management:

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
    
    # List all sessions
    all_sessions = sessions.list()

3. SettingsStore - User preferences:

    from pi_web_ui import SettingsStore
    
    settings = SettingsStore()
    
    # Get setting with default
    model = settings.get("default_model", "openai/gpt-4o")
    
    # Set setting
    settings.set("default_model", "anthropic/claude-opus-4")
    
    # Get all settings
    all = settings.get_all()

All storage is persisted to disk in the data directory.
""")
    print()


# ============================================================================
# Example 5: Configuration
# ============================================================================

async def configuration_example():
    """Example: Configuration options."""
    print("=" * 60)
    print("Configuration Example")
    print("=" * 60)
    
    print("""
Environment variables for configuration:

    # Server settings
    PI_WEB_UI_HOST=0.0.0.0
    PI_WEB_UI_PORT=8000
    PI_WEB_UI_DEBUG=false
    
    # Data directory
    PI_WEB_UI_DATA_DIR=~/.pi/web-ui
    
    # Optional authentication
    PI_WEB_UI_API_KEY=your-secret-key
    PI_WEB_UI_JWT_SECRET=your-jwt-secret

Settings file (~/.pi/web-ui/settings.json):

    {
      "sessions": {
        "maxHistory": 100,
        "autoSave": true
      },
      "appearance": {
        "theme": "system",
        "fontSize": 14,
        "codeTheme": "github-dark"
      },
      "shortcuts": {
        "newChat": "Ctrl+N",
        "sendMessage": "Enter",
        "toggleSidebar": "Ctrl+B"
      }
    }
""")
    print()


# ============================================================================
# Example 6: WebSocket Chat
# ============================================================================

async def websocket_example():
    """Example: WebSocket-based chat."""
    print("=" * 60)
    print("WebSocket Chat Example")
    print("=" * 60)
    
    print("""
The web UI uses WebSockets for real-time streaming:

    from pi_web_ui.chat import WebSocketChat
    
    async def websocket_endpoint(websocket):
        chat = WebSocketChat(websocket)
        
        # Handle incoming messages
        async for message in chat:
            # Stream response
            async for chunk in chat.stream_response(message):
                await chat.send(chunk)

WebSocket benefits:
- Real-time streaming of LLM responses
- Lower latency than HTTP polling
- Bidirectional communication
- Better for long-running conversations

The JavaScript client connects to:
  ws://localhost:8000/ws/chat

And sends/receives JSON messages:
  {"type": "message", "content": "Hello"}
  {"type": "chunk", "content": "Hi there"}
  {"type": "done"}
""")
    print()


# ============================================================================
# Example 7: File Uploads
# ============================================================================

async def file_uploads_example():
    """Example: Handling file uploads."""
    print("=" * 60)
    print("File Uploads Example")
    print("=" * 60)
    
    print("""
Handle file uploads in chat:

    from pi_web_ui.utils.attachment import save_attachment
    from fastapi import UploadFile
    
    @app.post("/api/upload")
    async def upload_file(file: UploadFile):
        # Save uploaded file
        attachment_id = await save_attachment(file)
        
        return {
            "attachment_id": attachment_id,
            "filename": file.filename,
            "size": file.size,
        }
    
    # Later, use in chat
    @app.post("/api/chat")
    async def chat_with_file(message: str, attachment_id: str):
        # Load attachment
        attachment = await get_attachment(attachment_id)
        
        # Include in context
        context = Context(messages=[
            UserMessage(content=[
                TextContent(text=message),
                ImageContent(data=attachment.data, mime_type=attachment.mime_type)
            ])
        ])
        
        # Stream response
        # ...

Supported file types:
- Images (PNG, JPEG, GIF) - for vision models
- Documents (PDF, TXT) - for text extraction
- Code files - for analysis
""")
    print()


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run all examples."""
    print("\nPi Web UI - Examples\n")
    print("These examples show how to use the web UI.\n")
    
    await basic_server_example()
    await create_app_example()
    await chat_panel_example()
    await storage_example()
    await configuration_example()
    await websocket_example()
    await file_uploads_example()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nTo start the web UI:")
    print("  python -m pi_web_ui")
    print("\nThen open http://localhost:8000 in your browser.")


if __name__ == "__main__":
    asyncio.run(main())
