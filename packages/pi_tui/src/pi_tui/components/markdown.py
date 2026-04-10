"""Markdown rendering component for terminal display.

Uses the rich library for high-quality markdown rendering in terminals.
"""

from __future__ import annotations

from ..tui import Component
from ..utils import truncate_to_width, visible_width


class Markdown(Component):
    """Markdown rendering component.

    Renders Markdown content to terminal-friendly output using the rich library.
    Falls back to plain text if rich is not available.
    """

    def __init__(self, content: str = "", max_width: int | None = None):
        """Initialize the markdown component.

        Args:
            content: Markdown content to render
            max_width: Maximum width for rendering (None for auto)
        """
        super().__init__()
        self._content = content
        self._max_width = max_width
        self._cached_lines: list[str] | None = None
        self._cached_width: int = 0

    def set_content(self, content: str) -> None:
        """Set the markdown content."""
        if content != self._content:
            self._content = content
            self._cached_lines = None

    def get_content(self) -> str:
        """Get the current markdown content."""
        return self._content

    def invalidate(self) -> None:
        """Invalidate cached render state."""
        self._cached_lines = None

    def render(self, width: int) -> list[str]:
        """Render the markdown content.

        Args:
            width: Available width for rendering

        Returns:
            List of rendered lines
        """
        # Use cached result if available and width matches
        if self._cached_lines and self._cached_width == width:
            return self._cached_lines

        if not self._content:
            return [""]

        try:
            # Try to use rich for rendering
            lines = self._render_with_rich(width)
        except ImportError:
            # Fallback to plain text
            lines = self._render_plain(width)

        self._cached_lines = lines
        self._cached_width = width
        return lines

    def _render_with_rich(self, width: int) -> list[str]:
        """Render using rich library."""
        import io

        from rich.console import Console
        from rich.markdown import Markdown as RichMarkdown

        # Create a string buffer to capture output
        buffer = io.StringIO()

        # Create console with the buffer
        console = Console(file=buffer, width=width, highlight=False, color_system="auto", force_terminal=True)

        # Render markdown
        md = RichMarkdown(self._content, code_theme="monokai")
        console.print(md)

        # Get output and split into lines
        output = buffer.getvalue()
        lines = output.rstrip("\n").split("\n")

        # Ensure each line fits within width
        result = []
        for line in lines:
            if visible_width(line) > width:
                result.append(truncate_to_width(line, width))
            else:
                result.append(line)

        return result if result else [""]

    def _render_plain(self, width: int) -> list[str]:
        """Render as plain text (fallback)."""
        # Simple text wrapping
        words = self._content.replace("\n", " ").split()
        lines = []
        current_line = ""

        for word in words:
            if not current_line:
                current_line = word
            elif visible_width(current_line) + 1 + visible_width(word) <= width:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]


class CodeBlock(Component):
    """Code block component with syntax highlighting."""

    def __init__(self, code: str = "", language: str | None = None):
        super().__init__()
        self._code = code
        self._language = language
        self._cached_lines: list[str] | None = None

    def set_code(self, code: str, language: str | None = None) -> None:
        """Set the code content."""
        self._code = code
        if language:
            self._language = language
        self._cached_lines = None

    def invalidate(self) -> None:
        """Invalidate cached render state."""
        self._cached_lines = None

    def render(self, width: int) -> list[str]:
        """Render the code block."""
        if self._cached_lines:
            return self._cached_lines

        if not self._code:
            return [""]

        try:
            lines = self._render_highlighted(width)
        except ImportError:
            lines = self._render_plain(width)

        self._cached_lines = lines
        return lines

    def _render_highlighted(self, width: int) -> list[str]:
        """Render with syntax highlighting using rich."""
        import io

        from rich.console import Console
        from rich.syntax import Syntax

        buffer = io.StringIO()
        console = Console(file=buffer, width=width, color_system="auto", force_terminal=True)

        syntax = Syntax(self._code, self._language or "text", theme="monokai", line_numbers=True, word_wrap=True)

        console.print(syntax)
        output = buffer.getvalue()
        lines = output.rstrip("\n").split("\n")

        return [truncate_to_width(line, width) for line in lines]

    def _render_plain(self, width: int) -> list[str]:
        """Render as plain text."""
        lines = self._code.split("\n")
        return [truncate_to_width(line, width) for line in lines]


class InlineCode(Component):
    """Inline code span component."""

    def __init__(self, code: str = ""):
        super().__init__()
        self._code = code

    def set_code(self, code: str) -> None:
        self._code = code

    def render(self, width: int) -> list[str]:
        # Simple inline code rendering with backticks
        text = f"`{self._code}`"
        if visible_width(text) > width:
            text = truncate_to_width(text, width)
        return [text]


class Quote(Component):
    """Blockquote component."""

    def __init__(self, content: str = ""):
        super().__init__()
        self._content = content
        self._cached_lines: list[str] | None = None

    def set_content(self, content: str) -> None:
        self._content = content
        self._cached_lines = None

    def invalidate(self) -> None:
        self._cached_lines = None

    def render(self, width: int) -> list[str]:
        if self._cached_lines:
            return self._cached_lines

        if not self._content:
            return [""]

        # Wrap content and add quote marker
        lines = self._wrap_text(self._content, width - 2)
        result = [f"▌ {line}" for line in lines]

        self._cached_lines = result
        return result

    def _wrap_text(self, text: str, width: int) -> list[str]:
        """Wrap text to fit within width."""
        words = text.replace("\n", " ").split()
        lines = []
        current_line = ""

        for word in words:
            if not current_line:
                current_line = word
            elif visible_width(current_line) + 1 + visible_width(word) <= width:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]


class ListComponent(Component):
    """List (ordered or unordered) component."""

    def __init__(self, items: list[str] | None = None, ordered: bool = False):
        super().__init__()
        self._items = items or []
        self._ordered = ordered
        self._cached_lines: list[str] | None = None

    def set_items(self, items: list[str]) -> None:
        self._items = items
        self._cached_lines = None

    def add_item(self, item: str) -> None:
        self._items.append(item)
        self._cached_lines = None

    def invalidate(self) -> None:
        self._cached_lines = None

    def render(self, width: int) -> list[str]:
        if self._cached_lines:
            return self._cached_lines

        if not self._items:
            return [""]

        result = []
        for i, item in enumerate(self._items):
            prefix = f"{i + 1}. " if self._ordered else "• "

            # Wrap item text
            item_width = width - len(prefix)
            wrapped = self._wrap_text(item, item_width)

            for j, line in enumerate(wrapped):
                if j == 0:
                    result.append(f"{prefix}{line}")
                else:
                    result.append(f"{' ' * len(prefix)}{line}")

        self._cached_lines = result
        return result

    def _wrap_text(self, text: str, width: int) -> list[str]:
        """Wrap text to fit within width."""
        words = text.replace("\n", " ").split()
        lines = []
        current_line = ""

        for word in words:
            if not current_line:
                current_line = word
            elif visible_width(current_line) + 1 + visible_width(word) <= width:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]


class Heading(Component):
    """Heading component."""

    LEVEL_STYLES = {
        1: ("═══ ", " ═══"),
        2: ("══ ", ""),
        3: ("═ ", ""),
        4: ("▪ ", ""),
        5: ("  ▪ ", ""),
        6: ("    ▪ ", ""),
    }

    def __init__(self, text: str = "", level: int = 1):
        super().__init__()
        self._text = text
        self._level = max(1, min(6, level))

    def set_text(self, text: str) -> None:
        self._text = text

    def render(self, width: int) -> list[str]:
        prefix, suffix = self.LEVEL_STYLES.get(self._level, ("", ""))
        text = f"\x1b[1m{prefix}{self._text}{suffix}\x1b[0m"

        if visible_width(text) > width:
            text = truncate_to_width(text, width)

        return [text]


class HorizontalRule(Component):
    """Horizontal rule component."""

    def render(self, width: int) -> list[str]:
        return ["─" * width]


class Link(Component):
    """Link component."""

    def __init__(self, text: str = "", url: str = ""):
        super().__init__()
        self._text = text
        self._url = url

    def set_link(self, text: str, url: str) -> None:
        self._text = text
        self._url = url

    def render(self, width: int) -> list[str]:
        # Render as [text](url) or just text with underline
        text = f"\x1b[4m{self._text}\x1b[0m" if self._text else f"\x1b[4m{self._url}\x1b[0m"

        if visible_width(text) > width:
            text = truncate_to_width(text, width)

        return [text]


class Table(Component):
    """Simple table component."""

    def __init__(self, headers: list[str] | None = None, rows: list[list[str]] | None = None):
        super().__init__()
        self._headers = headers or []
        self._rows = rows or []
        self._cached_lines: list[str] | None = None

    def set_data(self, headers: list[str], rows: list[list[str]]) -> None:
        self._headers = headers
        self._rows = rows
        self._cached_lines = None

    def invalidate(self) -> None:
        self._cached_lines = None

    def render(self, width: int) -> list[str]:
        if self._cached_lines:
            return self._cached_lines

        if not self._headers and not self._rows:
            return [""]

        # Calculate column widths
        all_rows = [self._headers] + self._rows if self._headers else self._rows
        num_cols = max(len(row) for row in all_rows) if all_rows else 0

        col_widths = [0] * num_cols
        for row in all_rows:
            for i, cell in enumerate(row):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], visible_width(str(cell)))

        # Adjust to fit width
        total_width = sum(col_widths) + (num_cols - 1) * 3  # " | " separators
        if total_width > width and num_cols > 0:
            # Scale down proportionally
            scale = (width - (num_cols - 1) * 3) / sum(col_widths)
            col_widths = [max(3, int(w * scale)) for w in col_widths]

        lines = []

        # Header row
        if self._headers:
            header_cells = [truncate_to_width(str(h), col_widths[i]) for i, h in enumerate(self._headers)]
            lines.append(
                " | ".join(
                    f"\x1b[1m{cell}\x1b[0m" if i < len(header_cells) else "" for i, cell in enumerate(header_cells)
                )
            )
            lines.append("-" * width)

        # Data rows
        for row in self._rows:
            row_cells = [truncate_to_width(str(cell), col_widths[i]) for i, cell in enumerate(row)]
            lines.append(" | ".join(row_cells))

        self._cached_lines = lines
        return lines
