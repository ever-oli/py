"""Gateway server for distributed node management."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException

from .constants import get_gateway_dir


@dataclass
class Node:
    """A registered gateway node."""

    id: str
    name: str
    url: str
    status: str = "online"
    last_seen: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update last_seen timestamp."""
        self.last_seen = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NodeRegistry:
    """In-memory node registry with persistence."""

    def __init__(self):
        self._nodes: dict[str, Node] = {}
        self._file = get_gateway_dir() / "nodes.json"
        self._load()

    def _load(self) -> None:
        """Load nodes from disk."""
        if not self._file.exists():
            return

        try:
            data = json.loads(self._file.read_text())
            for node_data in data.get("nodes", []):
                node = Node(**node_data)
                self._nodes[node.id] = node
        except (json.JSONDecodeError, KeyError):
            pass

    def _save(self) -> None:
        """Save nodes to disk."""
        data = {"nodes": [n.to_dict() for n in self._nodes.values()]}
        self._file.write_text(json.dumps(data, indent=2))

    def list_nodes(self) -> list[Node]:
        """List all registered nodes."""
        return list(self._nodes.values())

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def register(self, node: Node) -> None:
        """Register or update a node."""
        node.touch()
        self._nodes[node.id] = node
        self._save()

    def unregister(self, node_id: str) -> bool:
        """Unregister a node. Returns True if removed."""
        if node_id not in self._nodes:
            return False

        del self._nodes[node_id]
        self._save()
        return True

    def update_status(self, node_id: str, status: str) -> bool:
        """Update node status."""
        node = self._nodes.get(node_id)
        if not node:
            return False

        node.status = status
        node.touch()
        self._save()
        return True


class GatewayServer:
    """FastAPI-based gateway server."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.registry = NodeRegistry()
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI app."""
        app = FastAPI(title="IO Gateway", version="0.1.0")
        registry = self.registry

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/nodes")
        async def list_nodes() -> dict[str, list[dict[str, Any]]]:
            return {"nodes": [n.to_dict() for n in registry.list_nodes()]}

        @app.get("/nodes/{node_id}")
        async def get_node(node_id: str) -> dict[str, Any]:
            node = registry.get_node(node_id)
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")
            return node.to_dict()

        @app.post("/nodes")
        async def register_node(node_data: dict[str, Any]) -> dict[str, str]:
            node = Node(**node_data)
            registry.register(node)
            return {"status": "registered", "id": node.id}

        @app.delete("/nodes/{node_id}")
        async def unregister_node(node_id: str) -> dict[str, str]:
            if not registry.unregister(node_id):
                raise HTTPException(status_code=404, detail="Node not found")
            return {"status": "unregistered"}

        @app.post("/nodes/{node_id}/heartbeat")
        async def heartbeat(node_id: str) -> dict[str, str]:
            if not registry.update_status(node_id, "online"):
                raise HTTPException(status_code=404, detail="Node not found")
            return {"status": "ok"}

        @app.post("/nodes/{node_id}/execute")
        async def execute_on_node(
            node_id: str,
            _request: dict[str, Any],
        ) -> dict[str, Any]:
            node = registry.get_node(node_id)
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")

            return {
                "status": "pending",
                "message": "Execution not yet implemented",
                "node_id": node_id,
            }

        return app

    async def start(self) -> None:
        """Start the gateway server."""
        import uvicorn

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()


def create_gateway_server(host: str = "0.0.0.0", port: int = 8080) -> GatewayServer:
    """Create a gateway server instance."""
    return GatewayServer(host=host, port=port)
