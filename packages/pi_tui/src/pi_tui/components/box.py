"""Box component - container with padding and background."""

from __future__ import annotations

from typing import Callable

from ..tui import Component
from ..utils import apply_background_to_line, visible_width


class Box(Component):
    """Box component - a container that applies padding and background."""

    def __init__(
        self,
        padding_x: int = 1,
        padding_y: int = 1,
        bg_fn: Callable[[str], str] | None = None,
    ):
        """Initialize the box.

        Args:
            padding_x: Horizontal padding
            padding_y: Vertical padding
            bg_fn: Background color function
        """
        self._padding_x = padding_x
        self._padding_y = padding_y
        self._bg_fn = bg_fn
        self._children: list[Component] = []

        # Cache for rendered output
        self._cache: dict | None = None

    def add_child(self, component: Component) -> None:
        """Add a child component."""
        self._children.append(component)
        self._invalidate_cache()

    def remove_child(self, component: Component) -> None:
        """Remove a child component."""
        if component in self._children:
            self._children.remove(component)
            self._invalidate_cache()

    def clear(self) -> None:
        """Remove all children."""
        self._children.clear()
        self._invalidate_cache()

    def set_bg_fn(self, bg_fn: Callable[[str], str] | None) -> None:
        """Set the background function."""
        self._bg_fn = bg_fn
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Invalidate the render cache."""
        self._cache = None

    def _match_cache(self, width: int, child_lines: list[str], bg_sample: str | None) -> bool:
        """Check if cached output matches current parameters."""
        if self._cache is None:
            return False

        cached = self._cache
        if cached["width"] != width:
            return False
        if cached["bg_sample"] != bg_sample:
            return False
        if len(cached["child_lines"]) != len(child_lines):
            return False

        return all(cached["child_lines"][i] == line for i, line in enumerate(child_lines))

    def invalidate(self) -> None:
        """Invalidate cached state."""
        self._invalidate_cache()
        for child in self._children:
            if hasattr(child, "invalidate"):
                child.invalidate()

    def render(self, width: int) -> list[str]:
        """Render the box and its children."""
        if not self._children:
            return []

        content_width = max(1, width - self._padding_x * 2)
        left_pad = " " * self._padding_x

        # Render all children
        child_lines: list[str] = []
        for child in self._children:
            lines = child.render(content_width)
            for line in lines:
                child_lines.append(left_pad + line)

        if not child_lines:
            return []

        # Sample background function output
        bg_sample = self._bg_fn("test") if self._bg_fn else None

        # Check cache
        if self._match_cache(width, child_lines, bg_sample):
            return self._cache["lines"]

        # Apply background and padding
        result: list[str] = []

        # Top padding
        for _ in range(self._padding_y):
            result.append(self._apply_bg("", width))

        # Content
        for line in child_lines:
            result.append(self._apply_bg(line, width))

        # Bottom padding
        for _ in range(self._padding_y):
            result.append(self._apply_bg("", width))

        # Update cache
        self._cache = {
            "child_lines": child_lines.copy(),
            "width": width,
            "bg_sample": bg_sample,
            "lines": result,
        }

        return result

    def _apply_bg(self, line: str, width: int) -> str:
        """Apply background to a line."""
        vis_len = visible_width(line)
        pad_needed = max(0, width - vis_len)
        padded = line + " " * pad_needed

        if self._bg_fn:
            return apply_background_to_line(padded, width, self._bg_fn)
        return padded
