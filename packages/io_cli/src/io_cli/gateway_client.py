"""Gateway client for distributed node management."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import httpx


@dataclass
class Node:
    """A registered gateway node."""

    id: str
    name: str
    url: str
    status: str = "unknown"  # online, offline, busy
    last_seen: str | None = None
    capabilities: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            url=data.get("url", ""),
            status=data.get("status", "unknown"),
            last_seen=data.get("last_seen"),
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {}),
        )


class GatewayClient:
    """Client for gateway server communication."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def health_check(self) -> dict[str, Any] | None:
        """Check if gateway server is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def list_nodes(self) -> list[Node]:
        """List all registered nodes."""
        try:
            response = await self.client.get(f"{self.base_url}/nodes")
            response.raise_for_status()
            data = response.json()
            return [Node.from_dict(n) for n in data.get("nodes", [])]
        except httpx.HTTPError:
            return []

    async def register_node(self, node: Node) -> bool:
        """Register a new node with the gateway."""
        try:
            response = await self.client.post(
                f"{self.base_url}/nodes",
                json=node.to_dict(),
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def unregister_node(self, node_id: str) -> bool:
        """Unregister a node from the gateway."""
        try:
            response = await self.client.delete(f"{self.base_url}/nodes/{node_id}")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def execute_on_node(
        self,
        node_id: str,
        command: str,
        timeout: float = 60.0,
    ) -> dict[str, Any] | None:
        """Execute a command on a specific node."""
        try:
            response = await self.client.post(
                f"{self.base_url}/nodes/{node_id}/execute",
                json={"command": command, "timeout": timeout},
                timeout=timeout + 10,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def close(self) -> None:
        await self.client.aclose()


def get_gateway_client(base_url: str | None = None) -> GatewayClient:
    """Get a configured gateway client."""
    url = base_url or "http://localhost:8080"
    return GatewayClient(url)
