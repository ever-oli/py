"""Core TUI framework - container and component management."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from .ansi import ansi
from .buffer import Buffer, BufferDiff
from .terminal import ProcessTerminal, Terminal

# Cursor marker for hardware cursor positioning
CURSOR_MARKER = "\x1b[_G\x1b[\\"


class SizeValue:
    """Represents a size value (fixed or percentage)."""

    def __init__(self, value: int | float, is_percent: bool = False):
        self.value = value
        self.is_percent = is_percent

    @classmethod
    def fixed(cls, value: int) -> SizeValue:
        return cls(value, False)

    @classmethod
    def percent(cls, value: float) -> SizeValue:
        return cls(value, True)

    def resolve(self, total: int) -> int:
        if self.is_percent:
            return int(total * self.value / 100)
        return int(self.value)


@dataclass
class OverlayMargin:
    """Margins for overlay positioning."""

    top: int = 0
    bottom: int = 0
    left: int = 0
    right: int = 0


@dataclass
class OverlayAnchor:
    """Anchor point for overlay positioning."""

    x: str = "center"  # "left", "center", "right"
    y: str = "center"  # "top", "center", "bottom"


@dataclass
class OverlayOptions:
    """Options for creating an overlay."""

    id: str = ""
    width: SizeValue = field(default_factory=lambda: SizeValue.percent(50))
    height: SizeValue = field(default_factory=lambda: SizeValue.percent(50))
    margin: OverlayMargin = field(default_factory=OverlayMargin)
    anchor: OverlayAnchor = field(default_factory=OverlayAnchor)
    focusable: bool = True


@dataclass
class OverlayHandle:
    """Handle to an active overlay."""

    id: str
    close: Callable[[], None]
    focus: Callable[[], None]


class Component(ABC):
    """Base interface for TUI components."""

    @abstractmethod
    def render(self, width: int) -> list[str]:
        """Render the component to lines of text.

        Args:
            width: Available width for rendering

        Returns:
            List of rendered lines
        """
        pass

    def invalidate(self) -> None:
        """Invalidate cached state, forcing a re-render."""
        pass


class Focusable(ABC):
    """Interface for focusable components.

    Note: Components that are focusable should inherit from both
    Component and Focusable.
    """

    def __init__(self):
        self.focused = False

    @abstractmethod
    def handle_input(self, data: str) -> None:
        """Handle input data when focused."""
        pass


def is_focusable(component: Component) -> bool:
    """Check if a component is focusable."""
    return isinstance(component, Focusable)


class Container(Component):
    """Container that manages child components."""

    def __init__(self):
        self._children: list[Component] = []
        self._cached_lines: list[str] | None = None
        self._cached_width: int = 0

    def add_child(self, component: Component) -> None:
        """Add a child component."""
        self._children.append(component)
        self.invalidate()

    def remove_child(self, component: Component) -> None:
        """Remove a child component."""
        if component in self._children:
            self._children.remove(component)
            self.invalidate()

    def clear_children(self) -> None:
        """Remove all child components."""
        self._children.clear()
        self.invalidate()

    def get_children(self) -> list[Component]:
        """Get all child components."""
        return self._children.copy()

    def invalidate(self) -> None:
        """Invalidate cached state."""
        self._cached_lines = None
        for child in self._children:
            if hasattr(child, "invalidate"):
                child.invalidate()

    def render(self, width: int) -> list[str]:
        """Render all children and combine their output."""
        if self._cached_lines and self._cached_width == width:
            return self._cached_lines

        lines: list[str] = []
        for child in self._children:
            child_lines = child.render(width)
            lines.extend(child_lines)

        self._cached_lines = lines
        self._cached_width = width
        return lines


class TUI:
    """Main TUI class - manages terminal I/O and component rendering.

    This is the core class that coordinates:
    - Terminal input/output
    - Component tree management
    - Focus management
    - Differential rendering for efficiency
    """

    def __init__(self, terminal: Terminal | None = None):
        """Initialize the TUI.

        Args:
            terminal: Terminal implementation (defaults to ProcessTerminal)
        """
        self.terminal = terminal or ProcessTerminal()
        self._root: Component | None = None
        self._focus_chain: list[Focusable] = []
        self._focused_index = -1
        self._overlays: dict[str, Component] = {}
        self._overlay_order: list[str] = []
        self._running = False
        self._needs_render = False
        self._prev_buffer: Buffer | None = None
        self._cur_buffer: Buffer | None = None
        self._stdin_buffer: Any | None = None
        self._render_lock = threading.Lock()
        self._input_handlers: list[Callable[[str], bool]] = []
        self._resize_handlers: list[Callable[[], None]] = []

    def set_root(self, component: Component) -> None:
        """Set the root component."""
        self._root = component
        self.request_render()

    def start(self) -> None:
        """Start the TUI event loop."""
        if self._running:
            return

        self._running = True

        # Initialize buffers
        rows = self.terminal.rows
        cols = self.terminal.cols
        self._prev_buffer = Buffer(rows, cols)
        self._cur_buffer = Buffer(rows, cols)

        # Start terminal
        self.terminal.start(
            on_input=self._on_input,
            on_resize=self._on_resize,
        )

        # Hide cursor, clear screen
        self.terminal.hide_cursor()
        self.terminal.clear_screen()

        # Create stdin buffer for input handling
        from .stdin_buffer import StdinBuffer

        self._stdin_buffer = StdinBuffer()
        self._stdin_buffer.on("data", self._on_stdin_data)
        self._stdin_buffer.on("paste", self._on_stdin_paste)

        # Initial render
        self.render()

    def stop(self) -> None:
        """Stop the TUI and restore terminal state."""
        if not self._running:
            return

        self._running = False

        # Show cursor, clear screen
        self.terminal.show_cursor()
        self.terminal.clear_screen()

        # Stop terminal
        self.terminal.stop()

        # Clean up stdin buffer
        if self._stdin_buffer:
            self._stdin_buffer.destroy()
            self._stdin_buffer = None

    def request_render(self) -> None:
        """Request a re-render on the next frame."""
        self._needs_render = True

    def render(self) -> None:
        """Render the current state to the terminal."""
        with self._render_lock:
            if not self._running or not self._root:
                return

            # Get terminal size
            rows = self.terminal.rows
            cols = self.terminal.cols

            # Resize buffers if needed
            if self._prev_buffer.rows != rows or self._prev_buffer.cols != cols:
                self._prev_buffer.resize(rows, cols)
                self._cur_buffer.resize(rows, cols)

            # Clear current buffer
            self._cur_buffer.clear()

            # Render root component to buffer
            if self._root:
                lines = self._root.render(cols)
                for row, line in enumerate(lines[:rows]):
                    self._write_line_to_buffer(row, line, cols)

            # Render overlays
            for overlay_id in self._overlay_order:
                overlay = self._overlays.get(overlay_id)
                if overlay:
                    # Calculate overlay position
                    opts = self._get_overlay_options(overlay_id)
                    overlay_lines = overlay.render(opts.width.resolve(cols))
                    self._render_overlay(overlay_lines, opts, rows, cols)

            # Calculate diff and output
            diff = self._prev_buffer.diff(self._cur_buffer)
            self._output_diff(diff)

            # Swap buffers
            self._prev_buffer, self._cur_buffer = self._cur_buffer, self._prev_buffer
            self._cur_buffer.clear()

            self._needs_render = False

    def _write_line_to_buffer(self, row: int, line: str, max_cols: int) -> None:
        """Write a rendered line to the buffer."""
        if row >= self._cur_buffer.rows:
            return

        col = 0
        i = 0
        current_fg = None
        current_bg = None
        from .cell import CellAttributes

        current_attrs = CellAttributes()

        while i < len(line) and col < max_cols:
            # Handle ANSI codes
            from .utils import extract_ansi_code

            ansi = extract_ansi_code(line, i)
            if ansi:
                code = ansi["code"]
                # Parse SGR codes
                if code.startswith("\x1b[") and code.endswith("m"):
                    params = code[2:-1].split(";")
                    for p in params:
                        try:
                            pval = int(p) if p else 0
                            if pval == 0:
                                current_fg = None
                                current_bg = None
                                current_attrs = CellAttributes()
                            elif pval == 1:
                                current_attrs.bold = True
                            elif pval == 2:
                                current_attrs.dim = True
                            elif pval == 3:
                                current_attrs.italic = True
                            elif pval == 4:
                                current_attrs.underline = True
                            elif pval == 5:
                                current_attrs.blink = True
                            elif pval == 7:
                                current_attrs.inverse = True
                            elif pval == 8:
                                current_attrs.hidden = True
                            elif pval == 9:
                                current_attrs.strikethrough = True
                            elif pval == 22:
                                current_attrs.bold = False
                                current_attrs.dim = False
                            elif pval == 23:
                                current_attrs.italic = False
                            elif pval == 24:
                                current_attrs.underline = False
                            elif pval == 25:
                                current_attrs.blink = False
                            elif pval == 27:
                                current_attrs.inverse = False
                            elif pval == 28:
                                current_attrs.hidden = False
                            elif pval == 29:
                                current_attrs.strikethrough = False
                            elif pval == 39:
                                current_fg = None
                            elif pval == 49:
                                current_bg = None
                            elif 30 <= pval <= 37:
                                # Standard colors - map to RGB
                                color_map = [
                                    (0, 0, 0),  # black
                                    (205, 0, 0),  # red
                                    (0, 205, 0),  # green
                                    (205, 205, 0),  # yellow
                                    (0, 0, 238),  # blue
                                    (205, 0, 205),  # magenta
                                    (0, 205, 205),  # cyan
                                    (229, 229, 229),  # white
                                ]
                                current_fg = color_map[pval - 30]
                            elif 40 <= pval <= 47:
                                color_map = [
                                    (0, 0, 0),
                                    (205, 0, 0),
                                    (0, 205, 0),
                                    (205, 205, 0),
                                    (0, 0, 238),
                                    (205, 0, 205),
                                    (0, 205, 205),
                                    (229, 229, 229),
                                ]
                                current_bg = color_map[pval - 40]
                            elif pval == 38 and len(params) >= 5 and params[1] == "2":
                                # True color foreground
                                current_fg = (int(params[2]), int(params[3]), int(params[4]))
                            elif pval == 48 and len(params) >= 5 and params[1] == "2":
                                # True color background
                                current_bg = (int(params[2]), int(params[3]), int(params[4]))
                        except (ValueError, IndexError):
                            pass
                i += ansi["length"]
                continue

            char = line[i]
            from .cell import Cell

            cell = Cell(char=char, fg=current_fg, bg=current_bg, attrs=current_attrs.copy())
            self._cur_buffer.set(row, col, cell)

            # Handle wide characters
            from .utils import char_width

            w = char_width(char)
            col += w if w > 0 else 1
            i += 1

    def _get_overlay_options(self, overlay_id: str) -> OverlayOptions:
        """Get options for an overlay (stored in overlay or default)."""
        # This would be implemented with overlay metadata
        return OverlayOptions(id=overlay_id)

    def _render_overlay(self, lines: list[str], opts: OverlayOptions, rows: int, cols: int) -> None:
        """Render an overlay onto the buffer."""
        width = opts.width.resolve(cols)
        height = opts.height.resolve(rows)

        # Calculate position
        if opts.anchor.x == "center":
            x = (cols - width) // 2
        elif opts.anchor.x == "right":
            x = cols - width - opts.margin.right
        else:
            x = opts.margin.left

        if opts.anchor.y == "center":
            y = (rows - height) // 2
        elif opts.anchor.y == "bottom":
            y = rows - height - opts.margin.bottom
        else:
            y = opts.margin.top

        # Render overlay lines
        for row_idx, line in enumerate(lines[:height]):
            if y + row_idx >= rows:
                break
            self._write_line_to_buffer(y + row_idx, line, min(width, cols - x))

    def _output_diff(self, diff: BufferDiff) -> None:
        """Output a diff to the terminal."""
        if diff.is_empty():
            return

        # Start synchronized output
        self.terminal.write(ansi.SYNC_START)

        # Track current position for optimization
        current_row = -1
        current_col = -1

        # Group changes by row
        rows_changed: dict[int, list[tuple[int, Any]]] = {}
        for row, col, cell in diff.changes:
            if row not in rows_changed:
                rows_changed[row] = []
            rows_changed[row].append((col, cell))

        # Output changes
        for row in sorted(rows_changed.keys()):
            cols_changed = sorted(rows_changed[row], key=lambda x: x[0])

            # Move to row
            if current_row != row:
                self.terminal.write(ansi.cursor_position(row + 1, 1))
                current_row = row
                current_col = 0

            # Output cells
            for col, cell in cols_changed:
                if current_col != col:
                    self.terminal.write(ansi.cursor_position(row + 1, col + 1))
                    current_col = col

                self.terminal.write(cell.to_ansi())
                from .utils import char_width

                current_col += char_width(cell.char)

        # End synchronized output
        self.terminal.write(ansi.SYNC_END)

    def _on_input(self, data: str) -> None:
        """Handle raw input from terminal."""
        if self._stdin_buffer:
            self._stdin_buffer.process(data)

    def _on_stdin_data(self, data: str) -> None:
        """Handle processed input data."""
        # Try custom input handlers first
        for handler in self._input_handlers:
            if handler(data):
                return

        # Route to focused component
        if self._focused_index >= 0 and self._focused_index < len(self._focus_chain):
            focused = self._focus_chain[self._focused_index]
            if focused:
                focused.handle_input(data)
                self.request_render()

    def _on_stdin_paste(self, data: str) -> None:
        """Handle paste data."""
        # Route paste to focused component
        if self._focused_index >= 0 and self._focused_index < len(self._focus_chain):
            focused = self._focus_chain[self._focused_index]
            if hasattr(focused, "handle_paste"):
                focused.handle_paste(data)
                self.request_render()

    def _on_resize(self) -> None:
        """Handle terminal resize."""
        for handler in self._resize_handlers:
            handler()
        self.request_render()

    def add_input_handler(self, handler: Callable[[str], bool]) -> None:
        """Add a custom input handler.

        Handlers should return True if they handled the input.
        """
        self._input_handlers.append(handler)

    def remove_input_handler(self, handler: Callable[[str], bool]) -> None:
        """Remove a custom input handler."""
        if handler in self._input_handlers:
            self._input_handlers.remove(handler)

    def add_resize_handler(self, handler: Callable[[], None]) -> None:
        """Add a resize handler."""
        self._resize_handlers.append(handler)

    def create_overlay(
        self,
        component: Component,
        options: OverlayOptions,
    ) -> OverlayHandle:
        """Create an overlay.

        Returns a handle that can be used to close or focus the overlay.
        """
        overlay_id = options.id or f"overlay_{id(component)}"

        self._overlays[overlay_id] = component
        if overlay_id not in self._overlay_order:
            self._overlay_order.append(overlay_id)

        def close() -> None:
            if overlay_id in self._overlays:
                del self._overlays[overlay_id]
            if overlay_id in self._overlay_order:
                self._overlay_order.remove(overlay_id)
            self.request_render()

        def focus() -> None:
            if is_focusable(component):
                self._focus_on(component)

        if options.focusable and is_focusable(component):
            self._focus_chain.append(component)
            self._focus_on(component)

        self.request_render()

        return OverlayHandle(id=overlay_id, close=close, focus=focus)

    def _focus_on(self, component: Focusable) -> None:
        """Set focus to a specific component."""
        # Unfocus current
        if self._focused_index >= 0 and self._focused_index < len(self._focus_chain):
            current = self._focus_chain[self._focused_index]
            if current:
                current.focused = False

        # Focus new
        if component in self._focus_chain:
            self._focused_index = self._focus_chain.index(component)
            component.focused = True

    def focus_next(self) -> None:
        """Move focus to the next focusable component."""
        if not self._focus_chain:
            return

        # Unfocus current
        if self._focused_index >= 0:
            current = self._focus_chain[self._focused_index]
            current.focused = False

        # Move to next
        self._focused_index = (self._focused_index + 1) % len(self._focus_chain)
        self._focus_chain[self._focused_index].focused = True
        self.request_render()

    def focus_prev(self) -> None:
        """Move focus to the previous focusable component."""
        if not self._focus_chain:
            return

        # Unfocus current
        if self._focused_index >= 0:
            current = self._focus_chain[self._focused_index]
            current.focused = False

        # Move to previous
        self._focused_index = (self._focused_index - 1) % len(self._focus_chain)
        self._focus_chain[self._focused_index].focused = True
        self.request_render()

    def exit(self) -> None:
        """Exit the TUI."""
        self.stop()
