"""Editor component - multi-line text editor with keyboard navigation.

This is a Python port of the TypeScript Editor component, providing
Emacs-style key bindings, history, undo support, and autocomplete integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..keybindings import get_keybindings
from ..keys import decode_kitty_printable, matches_key
from ..tui import CURSOR_MARKER, TUI, Component, Focusable
from ..utils import (
    truncate_to_width,
    visible_width,
)
from .select_list import SelectItem, SelectList, SelectListTheme


@dataclass
class EditorState:
    """Editor state for undo/redo."""

    lines: list[str] = field(default_factory=lambda: [""])
    cursor_line: int = 0
    cursor_col: int = 0


@dataclass
class TextChunk:
    """A chunk of text for word-wrap layout."""

    text: str
    start_index: int
    end_index: int


@dataclass
class EditorTheme:
    """Visual theme for the editor."""

    border_color: Callable[[str], str]
    select_list: SelectListTheme


@dataclass
class EditorOptions:
    """Options for the editor component."""

    padding_x: int = 0
    autocomplete_max_visible: int = 5


class UndoStack:
    """Simple undo stack for editor state."""

    def __init__(self, max_size: int = 100):
        self._stack: list[EditorState] = []
        self._max_size = max_size
        self._index = -1

    def push(self, state: EditorState) -> None:
        """Push a state onto the stack."""
        # Remove redo states
        if self._index < len(self._stack) - 1:
            self._stack = self._stack[: self._index + 1]

        self._stack.append(state)

        # Limit size
        if len(self._stack) > self._max_size:
            self._stack.pop(0)
        else:
            self._index += 1

    def undo(self) -> EditorState | None:
        """Undo to previous state."""
        if self._index > 0:
            self._index -= 1
            return self._stack[self._index]
        return None

    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self._index > 0

    def clear(self) -> None:
        """Clear the undo stack."""
        self._stack.clear()
        self._index = -1


class KillRing:
    """Emacs-style kill ring for cut/yank operations."""

    def __init__(self):
        self._entries: list[str] = []
        self._index = -1

    def push(self, text: str) -> None:
        """Add text to the kill ring."""
        if text:
            self._entries.append(text)
            self._index = len(self._entries) - 1

    def yank(self) -> str:
        """Get the current kill ring entry."""
        if 0 <= self._index < len(self._entries):
            return self._entries[self._index]
        return ""

    def yank_pop(self) -> str:
        """Rotate and get previous kill ring entry."""
        if self._entries:
            self._index = (self._index - 1) % len(self._entries)
            return self._entries[self._index]
        return ""

    def is_empty(self) -> bool:
        """Check if kill ring is empty."""
        return not self._entries


class Editor(Component, Focusable):
    """Multi-line text editor component.

    Supports:
    - Multi-line text editing
    - Emacs-style key bindings
    - History (up/down arrow navigation)
    - Undo/redo
    - Kill/yank (cut/paste ring)
    - Autocomplete integration
    - Word wrapping with scroll indicators
    """

    def __init__(
        self,
        tui: TUI,
        theme: EditorTheme,
        options: EditorOptions | None = None,
    ):
        """Initialize the editor.

        Args:
            tui: Parent TUI instance
            theme: Visual theme
            options: Editor options
        """
        super().__init__()
        self.tui = tui
        self.theme = theme
        self.options = options or EditorOptions()

        # State
        self._state = EditorState()
        self._last_width = 80
        self._scroll_offset = 0
        self._preferred_visual_col: int | None = None

        # Border color (can be changed dynamically)
        self.border_color = theme.border_color

        # History
        self._history: list[str] = []
        self._history_index = -1

        # Kill ring
        self._kill_ring = KillRing()
        self._last_action: str | None = None

        # Jump mode
        self._jump_mode: str | None = None  # "forward" or "backward"

        # Autocomplete
        self._autocomplete_list: SelectList | None = None
        self._autocomplete_state: str | None = None  # "regular", "force", or None
        self._autocomplete_prefix = ""

        # Paste tracking
        self._pastes: dict[int, str] = {}
        self._paste_counter = 0
        self._paste_buffer = ""
        self._is_in_paste = False

        # Callbacks
        self.on_submit: Callable[[str], None] | None = None
        self.on_change: Callable[[str], None] | None = None
        self.disable_submit = False

        # Padding
        self._padding_x = max(0, self.options.padding_x)

    def get_text(self) -> str:
        """Get the current text content."""
        return "\n".join(self._state.lines)

    def set_text(self, text: str) -> None:
        """Set the text content."""
        self._push_undo_snapshot()
        lines = text.split("\n") if text else [""]
        self._state.lines = lines
        self._state.cursor_line = len(lines) - 1
        self._set_cursor_col(len(lines[-1]) if lines else 0)
        self._scroll_offset = 0

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def clear(self) -> None:
        """Clear the editor content."""
        self._push_undo_snapshot()
        self._state = EditorState()
        self._history_index = -1
        self._scroll_offset = 0

        if self.on_change:
            self.on_change("")

        self.tui.requestRender()

    def _push_undo_snapshot(self) -> None:
        """Save current state to undo stack."""
        self._undo_stack = getattr(self, "_undo_stack", None) or UndoStack()
        self._undo_stack.push(
            EditorState(
                lines=self._state.lines.copy(),
                cursor_line=self._state.cursor_line,
                cursor_col=self._state.cursor_col,
            )
        )

    def undo(self) -> None:
        """Undo the last change."""
        undo_stack = getattr(self, "_undo_stack", None)
        if undo_stack and undo_stack.can_undo():
            prev_state = undo_stack.undo()
            if prev_state:
                self._state = EditorState(
                    lines=prev_state.lines.copy(),
                    cursor_line=prev_state.cursor_line,
                    cursor_col=prev_state.cursor_col,
                )
                self._last_action = None
                if self.on_change:
                    self.on_change(self.get_text())
                self.tui.request_render()

    def add_to_history(self, text: str) -> None:
        """Add text to history."""
        trimmed = text.strip()
        if not trimmed:
            return

        # Don't add consecutive duplicates
        if self._history and self._history[0] == trimmed:
            return

        self._history.insert(0, trimmed)

        # Limit history size
        if len(self._history) > 100:
            self._history.pop()

    def _is_editor_empty(self) -> bool:
        """Check if the editor is empty."""
        return len(self._state.lines) == 1 and self._state.lines[0] == ""

    def invalidate(self) -> None:
        """Invalidate cached state."""
        pass

    def render(self, width: int) -> list[str]:
        """Render the editor."""
        max_padding = max(0, (width - 1) // 2)
        padding_x = min(self._padding_x, max_padding)
        content_width = max(1, width - padding_x * 2)

        # Layout width accounts for cursor overflow
        layout_width = max(1, content_width - (1 if padding_x == 0 else 0))
        self._last_width = layout_width

        horizontal = self.border_color("─")

        # Layout the text
        layout_lines = self._layout_text(layout_width)

        # Calculate max visible lines (30% of terminal height, min 5)
        terminal_rows = self.tui.terminal.rows
        max_visible_lines = max(5, terminal_rows // 3)

        # Find cursor line index
        cursor_line_index = next(
            (i for i, line in enumerate(layout_lines) if line.get("has_cursor")),
            0,
        )

        # Adjust scroll offset
        if cursor_line_index < self._scroll_offset:
            self._scroll_offset = cursor_line_index
        elif cursor_line_index >= self._scroll_offset + max_visible_lines:
            self._scroll_offset = cursor_line_index - max_visible_lines + 1

        # Clamp scroll offset
        max_scroll = max(0, len(layout_lines) - max_visible_lines)
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))

        # Get visible lines
        visible_lines = layout_lines[self._scroll_offset : self._scroll_offset + max_visible_lines]

        result: list[str] = []
        left_padding = " " * padding_x
        right_padding = left_padding

        # Top border with scroll indicator
        if self._scroll_offset > 0:
            indicator = f"─── ↑ {self._scroll_offset} more "
            remaining = width - visible_width(indicator)
            if remaining >= 0:
                result.append(self.border_color(indicator + "─" * remaining))
            else:
                result.append(self.border_color(truncate_to_width(indicator, width)))
        else:
            result.append(horizontal * width)

        # Render visible lines
        emit_cursor_marker = self.focused and not self._autocomplete_state

        for layout_line in visible_lines:
            display_text = layout_line.get("text", "")
            line_visible_width = visible_width(display_text)
            cursor_in_padding = False

            # Add cursor
            if layout_line.get("has_cursor") and layout_line.get("cursor_pos") is not None:
                cursor_pos = layout_line["cursor_pos"]
                before = display_text[:cursor_pos]
                after = display_text[cursor_pos:]

                # Hardware cursor marker
                marker = CURSOR_MARKER if emit_cursor_marker else ""

                if after:
                    # Replace first character with highlighted version
                    first_char = after[0]
                    rest = after[1:]
                    cursor = f"\x1b[7m{first_char}\x1b[0m"
                    display_text = before + marker + cursor + rest
                else:
                    # Cursor at end - add highlighted space
                    cursor = "\x1b[7m \x1b[0m"
                    display_text = before + marker + cursor
                    line_visible_width += 1
                    if line_visible_width > content_width and padding_x > 0:
                        cursor_in_padding = True

            # Calculate padding
            padding = " " * max(0, content_width - line_visible_width)
            line_right_padding = right_padding[1:] if cursor_in_padding else right_padding

            result.append(f"{left_padding}{display_text}{padding}{line_right_padding}")

        # Bottom border with scroll indicator
        lines_below = len(layout_lines) - (self._scroll_offset + len(visible_lines))
        if lines_below > 0:
            indicator = f"─── ↓ {lines_below} more "
            remaining = width - visible_width(indicator)
            result.append(self.border_color(indicator + "─" * max(0, remaining)))
        else:
            result.append(horizontal * width)

        # Add autocomplete list if active
        if self._autocomplete_state and self._autocomplete_list:
            autocomplete_result = self._autocomplete_list.render(content_width)
            for line in autocomplete_result:
                line_w = visible_width(line)
                line_pad = " " * max(0, content_width - line_w)
                result.append(f"{left_padding}{line}{line_pad}{right_padding}")

        return result

    def handle_input(self, data: str) -> None:
        """Handle keyboard input."""
        kb = get_keybindings()

        # Handle jump mode
        if self._jump_mode is not None:
            if kb.matches(data, "tui.editor.jumpForward") or kb.matches(data, "tui.editor.jumpBackward"):
                self._jump_mode = None
                return

            if ord(data[0]) >= 32 if data else False:
                direction = self._jump_mode
                self._jump_mode = None
                self._jump_to_char(data[0], direction)
                return

            self._jump_mode = None

        # Handle bracketed paste
        if "\x1b[200~" in data:
            self._is_in_paste = True
            self._paste_buffer = ""
            data = data.replace("\x1b[200~", "")

        if self._is_in_paste:
            self._paste_buffer += data
            end_index = self._paste_buffer.find("\x1b[201~")
            if end_index != -1:
                paste_content = self._paste_buffer[:end_index]
                if paste_content:
                    self._handle_paste(paste_content)
                self._is_in_paste = False
                remaining = self._paste_buffer[end_index + 6 :]
                self._paste_buffer = ""
                if remaining:
                    self.handle_input(remaining)
            return

        # Ctrl+C - let parent handle
        if kb.matches(data, "tui.input.copy"):
            return

        # Undo
        if kb.matches(data, "tui.editor.undo"):
            self.undo()
            return

        # Handle autocomplete mode
        if self._autocomplete_state and self._autocomplete_list:
            if kb.matches(data, "tui.select.cancel"):
                self._cancel_autocomplete()
                return

            if kb.matches(data, "tui.select.up") or kb.matches(data, "tui.select.down"):
                self._autocomplete_list.handle_input(data)
                self.tui.request_render()
                return

            if kb.matches(data, "tui.input.tab"):
                selected = self._autocomplete_list.get_selected_item()
                if selected:
                    self._apply_completion(selected)
                return

            if kb.matches(data, "tui.select.confirm"):
                selected = self._autocomplete_list.get_selected_item()
                if selected:
                    self._apply_completion(selected)
                    if self._autocomplete_prefix.startswith("/"):
                        self._cancel_autocomplete()
                    else:
                        self._cancel_autocomplete()
                        if self.on_change:
                            self.on_change(self.get_text())
                return

        # Tab - trigger completion
        if kb.matches(data, "tui.input.tab") and not self._autocomplete_state:
            self._handle_tab_completion()
            return

        # Deletion actions
        if kb.matches(data, "tui.editor.deleteToLineEnd"):
            self._delete_to_end_of_line()
            return
        if kb.matches(data, "tui.editor.deleteToLineStart"):
            self._delete_to_start_of_line()
            return
        if kb.matches(data, "tui.editor.deleteWordBackward"):
            self._delete_word_backwards()
            return
        if kb.matches(data, "tui.editor.deleteWordForward"):
            self._delete_word_forwards()
            return
        if kb.matches(data, "tui.editor.deleteCharBackward") or matches_key(data, "shift+backspace"):
            self._handle_backspace()
            return
        if kb.matches(data, "tui.editor.deleteCharForward") or matches_key(data, "shift+delete"):
            self._handle_forward_delete()
            return

        # Kill ring actions
        if kb.matches(data, "tui.editor.yank"):
            self._yank()
            return
        if kb.matches(data, "tui.editor.yankPop"):
            self._yank_pop()
            return

        # Cursor movement
        if kb.matches(data, "tui.editor.cursorLineStart"):
            self._move_to_line_start()
            return
        if kb.matches(data, "tui.editor.cursorLineEnd"):
            self._move_to_line_end()
            return
        if kb.matches(data, "tui.editor.cursorWordLeft"):
            self._move_word_backwards()
            return
        if kb.matches(data, "tui.editor.cursorWordRight"):
            self._move_word_forwards()
            return

        # New line
        if kb.matches(data, "tui.input.newLine") or data == "\n":
            self._add_new_line()
            return

        # Submit
        if kb.matches(data, "tui.input.submit"):
            if self.disable_submit:
                return

            # Workaround for terminals without Shift+Enter:
            # If char before cursor is \, delete it and insert newline
            current_line = (
                self._state.lines[self._state.cursor_line] if self._state.cursor_line < len(self._state.lines) else ""
            )
            if (
                self._state.cursor_col > 0
                and self._state.cursor_col <= len(current_line)
                and current_line[self._state.cursor_col - 1] == "\\"
            ):
                self._handle_backspace()
                self._add_new_line()
                return

            self._submit_value()
            return

        # Arrow key navigation
        if kb.matches(data, "tui.editor.cursorUp"):
            self._move_cursor(-1, 0)
            return
        if kb.matches(data, "tui.editor.cursorDown"):
            self._move_cursor(1, 0)
            return
        if kb.matches(data, "tui.editor.cursorRight"):
            self._move_cursor(0, 1)
            return
        if kb.matches(data, "tui.editor.cursorLeft"):
            self._move_cursor(0, -1)
            return

        # Page up/down
        if kb.matches(data, "tui.editor.pageUp"):
            self._page_scroll(-1)
            return
        if kb.matches(data, "tui.editor.pageDown"):
            self._page_scroll(1)
            return

        # Jump mode
        if kb.matches(data, "tui.editor.jumpForward"):
            self._jump_mode = "forward"
            return
        if kb.matches(data, "tui.editor.jumpBackward"):
            self._jump_mode = "backward"
            return

        # Shift+Space - insert regular space
        if matches_key(data, "shift+space"):
            self._insert_character(" ")
            return

        # Try Kitty printable
        kitty_printable = decode_kitty_printable(data)
        if kitty_printable is not None:
            self._insert_character(kitty_printable)
            return

        # Regular characters
        if data and ord(data[0]) >= 32:
            self._insert_character(data)

    def _layout_text(self, content_width: int) -> list[dict]:
        """Layout text into wrapped lines."""
        layout_lines: list[dict] = []

        # Empty editor
        if not self._state.lines or (len(self._state.lines) == 1 and not self._state.lines[0]):
            layout_lines.append(
                {
                    "text": "",
                    "has_cursor": True,
                    "cursor_pos": 0,
                }
            )
            return layout_lines

        # Process each logical line
        for i, line in enumerate(self._state.lines):
            is_current_line = i == self._state.cursor_line
            line_width = visible_width(line)

            if line_width <= content_width:
                # Line fits in one layout line
                if is_current_line:
                    layout_lines.append(
                        {
                            "text": line,
                            "has_cursor": True,
                            "cursor_pos": self._state.cursor_col,
                        }
                    )
                else:
                    layout_lines.append(
                        {
                            "text": line,
                            "has_cursor": False,
                        }
                    )
            else:
                # Line needs wrapping
                chunks = self._word_wrap_line(line, content_width)

                for chunk_idx, chunk in enumerate(chunks):
                    is_last_chunk = chunk_idx == len(chunks) - 1
                    cursor_pos = self._state.cursor_col

                    # Determine if cursor is in this chunk
                    has_cursor_in_chunk = False
                    adjusted_cursor_pos = 0

                    if is_current_line:
                        if is_last_chunk:
                            has_cursor_in_chunk = cursor_pos >= chunk.start_index
                            adjusted_cursor_pos = cursor_pos - chunk.start_index
                        else:
                            has_cursor_in_chunk = chunk.start_index <= cursor_pos < chunk.end_index
                            if has_cursor_in_chunk:
                                adjusted_cursor_pos = cursor_pos - chunk.start_index
                                adjusted_cursor_pos = min(adjusted_cursor_pos, len(chunk.text))

                    if has_cursor_in_chunk:
                        layout_lines.append(
                            {
                                "text": chunk.text,
                                "has_cursor": True,
                                "cursor_pos": adjusted_cursor_pos,
                            }
                        )
                    else:
                        layout_lines.append(
                            {
                                "text": chunk.text,
                                "has_cursor": False,
                            }
                        )

        return layout_lines

    def _word_wrap_line(self, line: str, max_width: int) -> list[TextChunk]:
        """Split a line into word-wrapped chunks."""
        if not line or max_width <= 0:
            return [TextChunk(text="", start_index=0, end_index=0)]

        line_width = visible_width(line)
        if line_width <= max_width:
            return [TextChunk(text=line, start_index=0, end_index=len(line))]

        chunks: list[TextChunk] = []
        current_width = 0
        chunk_start = 0
        wrap_opp_index = -1
        wrap_opp_width = 0

        i = 0
        while i < len(line):
            char = line[i]
            char_width = 1 if ord(char) < 128 else 2  # Simplified width calc
            is_ws = char.isspace()

            # Overflow check
            if current_width + char_width > max_width:
                if wrap_opp_index >= 0 and current_width - wrap_opp_width + char_width <= max_width:
                    # Backtrack to last wrap opportunity
                    chunks.append(
                        TextChunk(
                            text=line[chunk_start:wrap_opp_index],
                            start_index=chunk_start,
                            end_index=wrap_opp_index,
                        )
                    )
                    chunk_start = wrap_opp_index
                    current_width -= wrap_opp_width
                elif chunk_start < i:
                    # Force break at current position
                    chunks.append(
                        TextChunk(
                            text=line[chunk_start:i],
                            start_index=chunk_start,
                            end_index=i,
                        )
                    )
                    chunk_start = i
                    current_width = 0
                wrap_opp_index = -1

            # Advance
            current_width += char_width

            # Record wrap opportunity
            if is_ws and i + 1 < len(line) and not line[i + 1].isspace():
                wrap_opp_index = i + 1
                wrap_opp_width = current_width

            i += 1

        # Push final chunk
        if chunk_start < len(line):
            chunks.append(
                TextChunk(
                    text=line[chunk_start:],
                    start_index=chunk_start,
                    end_index=len(line),
                )
            )

        return chunks

    def _move_cursor(self, delta_line: int, delta_col: int) -> None:
        """Move cursor by the given deltas."""
        new_line = max(0, min(self._state.cursor_line + delta_line, len(self._state.lines) - 1))

        if delta_line != 0:
            # Vertical movement - use preferred column
            if self._preferred_visual_col is None:
                self._preferred_visual_col = self._state.cursor_col

            target_line = self._state.lines[new_line] if new_line < len(self._state.lines) else ""
            new_col = min(self._preferred_visual_col, len(target_line))
        else:
            new_col = max(0, self._state.cursor_col + delta_col)
            self._preferred_visual_col = None

        self._state.cursor_line = new_line
        self._set_cursor_col(new_col)
        self.tui.request_render()

    def _set_cursor_col(self, col: int) -> None:
        """Set cursor column, clamped to valid range."""
        line = self._state.lines[self._state.cursor_line] if self._state.cursor_line < len(self._state.lines) else ""
        self._state.cursor_col = max(0, min(col, len(line)))

    def _move_to_line_start(self) -> None:
        """Move cursor to start of line."""
        self._state.cursor_col = 0
        self._preferred_visual_col = 0
        self.tui.request_render()

    def _move_to_line_end(self) -> None:
        """Move cursor to end of line."""
        line = self._state.lines[self._state.cursor_line] if self._state.cursor_line < len(self._state.lines) else ""
        self._state.cursor_col = len(line)
        self._preferred_visual_col = None
        self.tui.request_render()

    def _move_word_backwards(self) -> None:
        """Move cursor back one word."""
        line = self._state.lines[self._state.cursor_line] if self._state.cursor_line < len(self._state.lines) else ""
        col = self._state.cursor_col

        # Skip whitespace
        while col > 0 and col <= len(line) and line[col - 1].isspace():
            col -= 1

        # Skip word characters
        while col > 0 and col <= len(line) and not line[col - 1].isspace():
            col -= 1

        self._state.cursor_col = col
        self._preferred_visual_col = None
        self.tui.request_render()

    def _move_word_forwards(self) -> None:
        """Move cursor forward one word."""
        line = self._state.lines[self._state.cursor_line] if self._state.cursor_line < len(self._state.lines) else ""
        col = self._state.cursor_col

        # Skip word characters
        while col < len(line) and not line[col].isspace():
            col += 1

        # Skip whitespace
        while col < len(line) and line[col].isspace():
            col += 1

        self._state.cursor_col = col
        self._preferred_visual_col = None
        self.tui.request_render()

    def _jump_to_char(self, char: str, direction: str) -> None:
        """Jump to the next occurrence of a character."""
        line = self._state.lines[self._state.cursor_line] if self._state.cursor_line < len(self._state.lines) else ""

        if direction == "forward":
            # Find next occurrence
            pos = line.find(char, self._state.cursor_col + 1)
            if pos != -1:
                self._state.cursor_col = pos
        else:
            # Find previous occurrence
            # Search before cursor
            search_end = self._state.cursor_col
            if search_end > 0:
                pos = line.rfind(char, 0, search_end)
                if pos != -1:
                    self._state.cursor_col = pos

        self._preferred_visual_col = None
        self.tui.request_render()

    def _page_scroll(self, direction: int) -> None:
        """Scroll by a page."""
        terminal_rows = self.tui.terminal.rows
        page_size = max(5, terminal_rows // 3)

        # Calculate new scroll offset
        if direction > 0:
            self._scroll_offset += page_size
        else:
            self._scroll_offset = max(0, self._scroll_offset - page_size)

        # Also move cursor
        if direction > 0:
            # Move cursor down
            new_line = min(self._state.cursor_line + page_size, len(self._state.lines) - 1)
            self._state.cursor_line = new_line
        else:
            # Move cursor up
            self._state.cursor_line = max(0, self._state.cursor_line - page_size)

        self.tui.request_render()

    def _insert_character(self, char: str) -> None:
        """Insert a character at cursor position."""
        self._push_undo_snapshot()
        self._last_action = "type"

        line = self._state.lines[self._state.cursor_line]
        new_line = line[: self._state.cursor_col] + char + line[self._state.cursor_col :]
        self._state.lines[self._state.cursor_line] = new_line
        self._state.cursor_col += len(char)
        self._preferred_visual_col = None

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def _handle_backspace(self) -> None:
        """Handle backspace key."""
        if self._state.cursor_col > 0:
            self._push_undo_snapshot()
            self._last_action = "delete"

            line = self._state.lines[self._state.cursor_line]
            new_line = line[: self._state.cursor_col - 1] + line[self._state.cursor_col :]
            self._state.lines[self._state.cursor_line] = new_line
            self._state.cursor_col -= 1
            self._preferred_visual_col = None

            if self.on_change:
                self.on_change(self.get_text())

            self.tui.request_render()
        elif self._state.cursor_line > 0:
            # Join with previous line
            self._push_undo_snapshot()
            self._last_action = "delete"

            prev_line = self._state.lines[self._state.cursor_line - 1]
            current_line = self._state.lines[self._state.cursor_line]

            self._state.cursor_col = len(prev_line)
            self._state.lines[self._state.cursor_line - 1] = prev_line + current_line
            self._state.lines.pop(self._state.cursor_line)
            self._state.cursor_line -= 1
            self._preferred_visual_col = None

            if self.on_change:
                self.on_change(self.get_text())

            self.tui.request_render()

    def _handle_forward_delete(self) -> None:
        """Handle forward delete key."""
        line = self._state.lines[self._state.cursor_line]

        if self._state.cursor_col < len(line):
            self._push_undo_snapshot()
            self._last_action = "delete"

            new_line = line[: self._state.cursor_col] + line[self._state.cursor_col + 1 :]
            self._state.lines[self._state.cursor_line] = new_line

            if self.on_change:
                self.on_change(self.get_text())

            self.tui.request_render()
        elif self._state.cursor_line < len(self._state.lines) - 1:
            # Join with next line
            self._push_undo_snapshot()
            self._last_action = "delete"

            next_line = self._state.lines[self._state.cursor_line + 1]
            self._state.lines[self._state.cursor_line] = line + next_line
            self._state.lines.pop(self._state.cursor_line + 1)

            if self.on_change:
                self.on_change(self.get_text())

            self.tui.request_render()

    def _delete_word_backwards(self) -> None:
        """Delete word backwards."""
        line = self._state.lines[self._state.cursor_line]
        col = self._state.cursor_col

        if col == 0:
            return

        self._push_undo_snapshot()
        self._last_action = "kill"

        # Find start of word
        start = col
        while start > 0 and line[start - 1].isspace():
            start -= 1
        while start > 0 and not line[start - 1].isspace():
            start -= 1

        killed_text = line[start:col]
        self._kill_ring.push(killed_text)

        new_line = line[:start] + line[col:]
        self._state.lines[self._state.cursor_line] = new_line
        self._state.cursor_col = start
        self._preferred_visual_col = None

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def _delete_word_forwards(self) -> None:
        """Delete word forwards."""
        line = self._state.lines[self._state.cursor_line]
        col = self._state.cursor_col

        if col >= len(line):
            return

        self._push_undo_snapshot()
        self._last_action = "kill"

        # Find end of word
        end = col
        while end < len(line) and not line[end].isspace():
            end += 1
        while end < len(line) and line[end].isspace():
            end += 1

        killed_text = line[col:end]
        self._kill_ring.push(killed_text)

        new_line = line[:col] + line[end:]
        self._state.lines[self._state.cursor_line] = new_line

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def _delete_to_end_of_line(self) -> None:
        """Delete from cursor to end of line."""
        line = self._state.lines[self._state.cursor_line]
        col = self._state.cursor_col

        if col < len(line):
            self._push_undo_snapshot()
            self._last_action = "kill"

            killed_text = line[col:]
            self._kill_ring.push(killed_text)

            self._state.lines[self._state.cursor_line] = line[:col]

            if self.on_change:
                self.on_change(self.get_text())

            self.tui.request_render()

    def _delete_to_start_of_line(self) -> None:
        """Delete from cursor to start of line."""
        line = self._state.lines[self._state.cursor_line]
        col = self._state.cursor_col

        if col > 0:
            self._push_undo_snapshot()
            self._last_action = "kill"

            killed_text = line[:col]
            self._kill_ring.push(killed_text)

            self._state.lines[self._state.cursor_line] = line[col:]
            self._state.cursor_col = 0
            self._preferred_visual_col = 0

            if self.on_change:
                self.on_change(self.get_text())

            self.tui.request_render()

    def _add_new_line(self) -> None:
        """Insert a new line."""
        self._push_undo_snapshot()
        self._last_action = "type"

        line = self._state.lines[self._state.cursor_line]
        before = line[: self._state.cursor_col]
        after = line[self._state.cursor_col :]

        self._state.lines[self._state.cursor_line] = before
        self._state.lines.insert(self._state.cursor_line + 1, after)
        self._state.cursor_line += 1
        self._state.cursor_col = 0
        self._preferred_visual_col = None

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def _yank(self) -> None:
        """Yank (paste) from kill ring."""
        if not self._kill_ring.is_empty():
            text = self._kill_ring.yank()
            self._insert_text(text)
            self._last_action = "yank"

    def _yank_pop(self) -> None:
        """Rotate kill ring and yank."""
        if self._last_action == "yank":
            text = self._kill_ring.yank_pop()
            # This is simplified - proper yank-pop requires tracking what was yanked
            self._insert_text(text)

    def _insert_text(self, text: str) -> None:
        """Insert text at cursor position."""
        self._push_undo_snapshot()

        line = self._state.lines[self._state.cursor_line]
        new_line = line[: self._state.cursor_col] + text + line[self._state.cursor_col :]
        self._state.lines[self._state.cursor_line] = new_line
        self._state.cursor_col += len(text)

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def _handle_paste(self, text: str) -> None:
        """Handle pasted content."""
        self._push_undo_snapshot()
        self._last_action = "type"

        # Split paste by newlines
        lines = text.split("\n")
        if not lines:
            return

        current_line = self._state.lines[self._state.cursor_line]
        before = current_line[: self._state.cursor_col]
        after = current_line[self._state.cursor_col :]

        # Insert first line
        self._state.lines[self._state.cursor_line] = before + lines[0]
        self._state.cursor_col = len(before + lines[0])

        # Insert remaining lines
        for i, paste_line in enumerate(lines[1:], 1):
            self._state.lines.insert(self._state.cursor_line + i, paste_line)

        # Append after text to last inserted line
        if len(lines) > 1:
            last_idx = self._state.cursor_line + len(lines) - 1
            self._state.lines[last_idx] += after
            self._state.cursor_line = last_idx
            self._state.cursor_col = len(self._state.lines[last_idx]) - len(after)

        self._preferred_visual_col = None

        if self.on_change:
            self.on_change(self.get_text())

        self.tui.request_render()

    def _submit_value(self) -> None:
        """Submit the current value."""
        text = self.get_text()
        self.add_to_history(text)

        if self.on_submit:
            self.on_submit(text)

    def _cancel_autocomplete(self) -> None:
        """Cancel autocomplete mode."""
        self._autocomplete_state = None
        self._autocomplete_list = None
        self._autocomplete_prefix = ""
        self.tui.request_render()

    def _handle_tab_completion(self) -> None:
        """Handle tab key for completion."""
        # Placeholder - would integrate with autocomplete provider
        self._autocomplete_state = "force"
        self.tui.request_render()

    def _apply_completion(self, item: SelectItem) -> None:
        """Apply a completion item."""
        # Placeholder - would apply the completion
        self._cancel_autocomplete()
