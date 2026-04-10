"""FastAPI server for Pi Web UI.

Provides HTTP API and WebSocket endpoints for the chat interface.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pi_ai import get_model

from .chat_panel import ChatPanel
from .storage import AppStorage
from .utils.attachment import process_attachment

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request

    from pi_agent_core import AgentEvent

# Global state
_chat_panels: dict[str, ChatPanel] = {}
_connections: dict[str, WebSocket] = {}
_storage: AppStorage | None = None


def get_storage() -> AppStorage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        _storage = AppStorage()
    return _storage


async def broadcast_event(session_id: str, event: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients for a session."""
    if session_id in _connections:
        with suppress(Exception):
            await _connections[session_id].send_json(event)


def create_chat_panel(session_id: str | None = None) -> ChatPanel:
    """Create a new chat panel with optional session ID."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    storage = get_storage()

    async def event_handler(event: AgentEvent) -> None:
        """Handle agent events and broadcast to WebSocket."""
        await broadcast_event(
            session_id,
            {
                "type": "agent_event",
                "event": event_to_dict(event),
            },
        )

    panel = ChatPanel(
        session_id=session_id,
        storage=storage,
        on_event=event_handler,
    )
    _chat_panels[session_id] = panel
    return panel


def event_to_dict(event: AgentEvent) -> dict[str, Any]:
    """Convert an agent event to a dictionary."""
    if hasattr(event, "__dataclass_fields__"):
        result = {}
        for key, value in event.__dict__.items():
            if key.startswith("_"):
                continue
            result[key] = serialize_value(value)
        result["type"] = event.type if hasattr(event, "type") else "unknown"
        return result
    elif isinstance(event, dict):
        return {k: serialize_value(v) for k, v in event.items()}
    return {"type": "unknown"}


def serialize_value(value: Any) -> Any:
    """Serialize a value for JSON transmission."""
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif hasattr(value, "__dataclass_fields__"):
        result = {}
        for k, v in value.__dict__.items():
            if not k.startswith("_"):
                result[k] = serialize_value(v)
        return result
    elif isinstance(value, datetime):
        return value.isoformat()
    else:
        return str(value)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown
    for panel in _chat_panels.values():
        await panel.close()
    _chat_panels.clear()


def create_app(
    static_dir: Path | str | None = None, templates_dir: Path | str | None = None
) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Pi Web UI",
        description="Web interface for Pi AI ecosystem",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Determine directories
    package_dir = Path(__file__).parent
    if static_dir is None:
        static_dir = package_dir / "static"
    if templates_dir is None:
        templates_dir = package_dir / "templates"

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Templates
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Render the main chat page."""
        return templates.TemplateResponse("chat.html", {"request": request})

    @app.get("/chat/{session_id}", response_class=HTMLResponse)
    async def chat_page(request: Request, session_id: str) -> HTMLResponse:
        """Render chat page for a specific session."""
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "session_id": session_id,
            },
        )

    @app.get("/api/models")
    async def list_models() -> JSONResponse:
        """List available models."""
        from pi_ai import get_models

        models = get_models()
        return JSONResponse(
            content=[
                {
                    "id": m.id,
                    "name": m.name,
                    "provider": m.provider,
                    "api": m.api,
                }
                for m in models
            ]
        )

    @app.post("/api/sessions")
    async def create_session() -> JSONResponse:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        create_chat_panel(session_id)
        return JSONResponse(
            content={
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
            }
        )

    @app.get("/api/sessions")
    async def list_sessions() -> JSONResponse:
        """List all chat sessions."""
        storage = get_storage()
        sessions = await storage.sessions.get_all_metadata()
        return JSONResponse(
            content=[
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at,
                    "last_modified": s.last_modified,
                    "message_count": s.message_count,
                }
                for s in sessions
            ]
        )

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> JSONResponse:
        """Get a specific session's data."""
        storage = get_storage()
        session = await storage.sessions.get(session_id)
        if session is None:
            return JSONResponse(
                content={"error": "Session not found"},
                status_code=404,
            )
        return JSONResponse(content=serialize_value(session))

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> JSONResponse:
        """Delete a session."""
        storage = get_storage()
        await storage.sessions.delete(session_id)
        if session_id in _chat_panels:
            await _chat_panels[session_id].close()
            del _chat_panels[session_id]
        return JSONResponse(content={"success": True})

    @app.post("/api/sessions/{session_id}/messages")
    async def send_message(
        session_id: str,
        message: str = Form(...),
        model_id: str | None = Form(None),
    ) -> JSONResponse:
        """Send a message to a session (non-streaming)."""
        if session_id not in _chat_panels:
            create_chat_panel(session_id)

        panel = _chat_panels[session_id]

        # Set model if provided
        if model_id:
            from pi_ai import get_model

            try:
                model = get_model(model_id)
                panel.agent.model = model
            except ValueError:
                pass

        # Send message
        result = await panel.send_message(message)

        return JSONResponse(content=serialize_value(result))

    @app.post("/api/sessions/{session_id}/attachments")
    async def upload_attachment(
        session_id: str,
        file: UploadFile = File(...),
    ) -> JSONResponse:
        """Upload a file attachment."""
        try:
            content = await file.read()
            attachment = await process_attachment(
                content,
                filename=file.filename or "unnamed",
                content_type=file.content_type or "application/octet-stream",
            )
            return JSONResponse(content=serialize_value(attachment))
        except Exception as e:
            return JSONResponse(
                content={"error": str(e)},
                status_code=400,
            )

    @app.post("/api/sessions/{session_id}/abort")
    async def abort_session(session_id: str) -> JSONResponse:
        """Abort the current streaming response."""
        if session_id in _chat_panels:
            await _chat_panels[session_id].abort()
        return JSONResponse(content={"success": True})

    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for real-time chat."""
        await websocket.accept()
        _connections[session_id] = websocket

        try:
            if session_id not in _chat_panels:
                create_chat_panel(session_id)

            panel = _chat_panels[session_id]

            # Send initial state
            await websocket.send_json(
                {
                    "type": "connected",
                    "session_id": session_id,
                    "messages": serialize_value(panel.agent.messages),
                }
            )

            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "message":
                    content = data.get("content", "")
                    attachments = data.get("attachments", [])
                    model_id = data.get("model_id")

                    # Set model if provided
                    if model_id:
                        try:
                            model = get_model(model_id)
                            panel.agent.model = model
                        except ValueError:
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": f"Unknown model: {model_id}",
                                }
                            )
                            continue

                    # Send the message with streaming
                    async for event in panel.send_message_stream(content, attachments):
                        await websocket.send_json(
                            {
                                "type": "stream_event",
                                "event": event_to_dict(event),
                            }
                        )

                elif msg_type == "abort":
                    await panel.abort()

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "get_state":
                    await websocket.send_json(
                        {
                            "type": "state",
                            "state": serialize_value(panel.agent.state),
                        }
                    )

        except WebSocketDisconnect:
            pass
        finally:
            if session_id in _connections:
                del _connections[session_id]

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    static_dir: Path | str | None = None,
    templates_dir: Path | str | None = None,
) -> None:
    """Run the web UI server."""
    import uvicorn

    app = create_app(static_dir=static_dir, templates_dir=templates_dir)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server()
