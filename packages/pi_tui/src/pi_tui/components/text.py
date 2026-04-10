"""Text component - displays multi-line text with word wrapping."""

from __future__ import annotations

from typing import Callable

from ..tui import Component
from ..utils import apply_background_to_line, visible_width, wrap_text_with_ansi


class Text(Component):
    """Text component - displays multi-line text with word wrapping."""

    def __init__(
        self,
        text: str = "",
        padding_x: int = 1,
        padding_y: int = 1,
        custom_bg_fn: Callable[[str], str] | None = None,
    ):
        """Initialize the text component.

        Args:
            text: Text content
            padding_x: Left/right padding
            padding_y: Top/bottom padding
            custom_bg_fn: Custom background function
        """
        self._text = text
        self._padding_x = padding_x
        self._padding_y = padding_y
        self._custom_bg_fn = custom_bg_fn

        # Cache for rendered output
        self._cached_text: str | None = None
        self._cached_width: int | None = None
        self._cached_lines: list[str] | None = None

    def set_text(self, text: str) -> None:
        """Set the text content."""
        self._text = text
        self._invalidate_cache()

    def set_custom_bg_fn(self, custom_bg_fn: Callable[[str], str] | None) -> None:
        """Set the custom background function."""
        self._custom_bg_fn = custom_bg_fn
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Invalidate the render cache."""
        self._cached_text = None
        self._cached_width = None
        self._cached_lines = None

    def invalidate(self) -> None:
        """Invalidate cached state."""
        self._invalidate_cache()

    def render(self, width: int) -> list[str]:
        """Render the text component."""
        # Check cache
        if self._cached_lines and self._cached_text == self._text and self._cached_width == width:
            return self._cached_lines

        # Don't render empty text
        if not self._text or not self._text.strip():
            self._cached_text = self._text
            self._cached_width = width
            self._cached_lines = []
            return []

        # Replace tabs with 3 spaces
        normalized_text = self._text.replace("\t", "   ")

        # Calculate content width
        content_width = max(1, width - self._padding_x * 2)

        # Wrap text
        wrapped_lines = wrap_text_with_ansi(normalized_text, content_width)

        # Add margins and background
        left_margin = " " * self._padding_x
        content_lines: list[str] = []

        for line in wrapped_lines:
            line_with_margins = left_margin + line + left_margin

            if self._custom_bg_fn:
                content_lines.append(apply_background_to_line(line_with_margins, width, self._custom_bg_fn))
            else:
                vis_len = visible_width(line_with_margins)
                pad_needed = max(0, width - vis_len)
                content_lines.append(line_with_margins + " " * pad_needed)

        # Add top/bottom padding
        empty_line = " " * width
        empty_lines: list[str] = []
        for _ in range(self._padding_y):
            if self._custom_bg_fn:
                empty_lines.append(apply_background_to_line(empty_line, width, self._custom_bg_fn))
            else:
                empty_lines.append(empty_line)

        result = empty_lines + content_lines + empty_lines

        # Update cache
        self._cached_text = self._text
        self._cached_width = width
        self._cached_lines = result

        return result if result else [""]
