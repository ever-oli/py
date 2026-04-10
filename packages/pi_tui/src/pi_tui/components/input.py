"""Single-line text input component with autocomplete support.

This is a Python port of the TypeScript Input component, providing
Emacs-style key bindings, history, undo support, and autocomplete integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..keybindings import get_keybindings
from ..keys import decode_kitty_printable, matches_key
from ..tui import CURSOR_MARKER, Component, Focusable
from ..utils import truncate_to_width, visible_width
from .select_list import SelectItem, SelectList, SelectListTheme


@dataclass
class InputTheme:
    """Visual theme for the input."""

    border_color: Callable[[str], str]
    select_list: SelectListTheme


class KillRing:
    """Ring buffer for Emacs-style kill/yank operations.

    Tracks killed (deleted) text entries. Consecutive kills can accumulate
    into a single entry. Supports yank (paste most recent) and yank-pop
    (cycle through older entries).
    """

    def __init__(self):
        self._ring: list[str] = []

    def push(self, text: str, prepend: bool = False, accumulate: bool = False) -> None:
        """Add text to the kill ring.

        Args:
            text: The killed text to add
            prepend: If accumulating, prepend (backward deletion) or append (forward)
            accumulate: Merge with the most recent entry instead of creating new
        """
        if not text:
            return

        if accumulate and self._ring:
            last = self._ring.pop()
            self._ring.append(text + last if prepend else last + text)
        else:
            self._ring.append(text)

    def peek(self) -> str | None:
        """Get most recent entry without modifying the ring."""
        return self._ring[-1] if self._ring else None

    def rotate(self) -> None:
        """Move last entry to front (for yank-pop cycling)."""
        if len(self._ring) > 1:
            last = self._ring.pop()
            self._ring.insert(0, last)

    def __len__(self) -> int:
        return len(self._ring)


class UndoStack:
    """Generic undo stack with clone-on-push semantics.

    Stores deep clones of state snapshots.
    """

    def __init__(self):
        self._stack: list[dict] = []

    def push(self, state: dict) -> None:
        """Push a deep clone of the given state onto the stack."""
        import copy

        self._stack.append(copy.deepcopy(state))

    def pop(self) -> dict | None:
        """Pop and return the most recent snapshot, or None if empty."""
        return self._stack.pop() if self._stack else None

    def clear(self) -> None:
        """Remove all snapshots."""
        self._stack.clear()

    def __len__(self) -> int:
        return len(self._stack)


class Input(Component, Focusable):
    """Single-line text input component.

    Supports:
    - Single-line text editing
    - Emacs-style key bindings
    - History (up/down arrow navigation)
    - Undo/redo
    - Kill/yank (cut/paste ring)
    - Autocomplete integration
    - Horizontal scrolling
    """

    def __init__(
        self, tui=None, theme: InputTheme | None = None, padding_x: int = 0, autocomplete_max_visible: int = 5
    ):
        super().__init__()
        self.tui = tui
        self.theme = theme
        self.padding_x = max(0, padding_x)
        self.autocomplete_max_visible = autocomplete_max_visible

        # State
        self._value = ""
        self._cursor_pos = 0
        self._scroll_offset = 0
        self._last_width = 80

        # Border color (can be changed dynamically)
        self.border_color = theme.border_color if theme else lambda x: x

        # History
        self._history: list[str] = []
        self._history_index = -1

        # Kill ring
        self._kill_ring = KillRing()
        self._last_yank_text: str | None = None
        self._last_action: str | None = None

        # Undo
        self._undo_stack = UndoStack()
        self._undo_coalesce_group: str | None = None

        # Autocomplete
        self._autocomplete_list: SelectList | None = None
        self._autocomplete_prefix = ""

        # Callbacks
        self.on_submit: Callable[[str], None] | None = None
        self.on_change: Callable[[str], None] | None = None

    def get_value(self) -> str:
        """Get the current input value."""
        return self._value

    def set_value(self, value: str) -> None:
        """Set the input value."""
        self._push_undo_state()
        self._value = value
        self._cursor_pos = len(value)
        self._scroll_offset = 0
        self._invalidate_cache()

        if self.on_change:
            self.on_change(value)

    def clear(self) -> None:
        """Clear the input."""
        self._push_undo_state()
        self._value = ""
        self._cursor_pos = 0
        self._scroll_offset = 0
        self._history_index = -1
        self._invalidate_cache()

        if self.on_change:
            self.on_change("")

    def _push_undo_state(self) -> None:
        """Save current state to undo stack."""
        self._undo_stack.push(
            {
                "value": self._value,
                "cursor_pos": self._cursor_pos,
            }
        )

    def undo(self) -> None:
        """Undo the last change."""
        state = self._undo_stack.pop()
        if state:
            self._value = state["value"]
            self._cursor_pos = state["cursor_pos"]
            self._scroll_offset = 0
            self._invalidate_cache()
            if self.on_change:
                self.on_change(self._value)
            if self.tui:
                self.tui.request_render()

    def _invalidate_cache(self) -> None:
        """Invalidate any cached render state."""
        pass

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

    def is_empty(self) -> bool:
        """Check if the input is empty."""
        return self._value == ""

    def invalidate(self) -> None:
        """Invalidate cached state."""
        pass

    def render(self, width: int) -> list[str]:
        """Render the input to a single line."""
        max_padding = max(0, (width - 1) // 2)
        padding_x = min(self.padding_x, max_padding)
        content_width = max(1, width - padding_x * 2)

        self._last_width = content_width

        # Calculate scroll to keep cursor visible
        visible_value_width = visible_width(self._value)

        if visible_value_width <= content_width:
            # Value fits, no scrolling needed
            self._scroll_offset = 0
            display_text = self._value
            cursor_display_pos = visible_width(self._value[: self._cursor_pos])
        else:
            # Need to scroll horizontally
            cursor_display_pos = visible_width(self._value[: self._cursor_pos])

            # Keep cursor in middle third of visible area
            third = content_width // 3

            if cursor_display_pos < self._scroll_offset + third:
                # Cursor too far left
                self._scroll_offset = max(0, cursor_display_pos - third)
            elif cursor_display_pos > self._scroll_offset + content_width - third:
                # Cursor too far right
                max_scroll = max(0, visible_value_width - content_width)
                self._scroll_offset = min(max_scroll, cursor_display_pos - content_width + third)

            # Extract visible portion
            display_text = self._get_visible_portion(content_width)

        # Build the line
        left_padding = " " * padding_x
        right_padding = " " * padding_x

        # Insert cursor
        visible_text_before_cursor = visible_width(self._value[: self._cursor_pos])
        cursor_in_visible = self._scroll_offset <= visible_text_before_cursor <= self._scroll_offset + content_width

        emit_cursor_marker = self.focused and not self._autocomplete_list

        if cursor_in_visible:
            # Cursor is visible in the scrolled view
            local_cursor_pos = visible_text_before_cursor - self._scroll_offset
            local_cursor_pos = max(0, min(local_cursor_pos, len(display_text)))

            before = display_text[:local_cursor_pos]
            after = display_text[local_cursor_pos:]

            marker = CURSOR_MARKER if emit_cursor_marker else ""

            if after:
                first_char = after[0]
                rest = after[1:]
                cursor = f"\x1b[7m{first_char}\x1b[0m"
                display_text = before + marker + cursor + rest
            else:
                cursor = "\x1b[7m \x1b[0m"
                display_text = before + marker + cursor

        # Pad to content width
        text_width = visible_width(display_text)
        if text_width < content_width:
            display_text += " " * (content_width - text_width)

        result = left_padding + display_text + right_padding

        # Ensure exact width
        result_width = visible_width(result)
        if result_width < width:
            result += " " * (width - result_width)
        elif result_width > width:
            result = truncate_to_width(result, width)

        return [result]

    def _get_visible_portion(self, content_width: int) -> str:
        """Get the visible portion of the value based on scroll offset."""
        if not self._value:
            return ""

        # Find character position corresponding to scroll offset
        char_pos = 0
        width_accum = 0

        for i, char in enumerate(self._value):
            char_w = 2 if ord(char) > 127 else 1  # Simplified width calc
            if width_accum + char_w > self._scroll_offset:
                char_pos = i
                break
            width_accum += char_w

        # Extract visible portion
        result = []
        width = 0

        for i in range(char_pos, len(self._value)):
            char = self._value[i]
            char_w = 2 if ord(char) > 127 else 1

            if width + char_w > content_width:
                break

            result.append(char)
            width += char_w

        return "".join(result)

    def handle_input(self, data: str) -> None:
        """Handle keyboard input."""
        kb = get_keybindings()

        # Ctrl+C - let parent handle
        if kb.matches(data, "tui.input.copy"):
            return

        # Undo
        if kb.matches(data, "tui.editor.undo"):
            self.undo()
            return

        # Handle autocomplete mode
        if self._autocomplete_list:
            if kb.matches(data, "tui.select.cancel"):
                self._cancel_autocomplete()
                return

            if kb.matches(data, "tui.select.up") or kb.matches(data, "tui.select.down"):
                self._autocomplete_list.handle_input(data)
                if self.tui:
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
                    self._cancel_autocomplete()
                return

        # Tab - trigger completion
        if kb.matches(data, "tui.input.tab") and not self._autocomplete_list:
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
            self._move_to_start()
            return
        if kb.matches(data, "tui.editor.cursorLineEnd"):
            self._move_to_end()
            return
        if kb.matches(data, "tui.editor.cursorWordLeft"):
            self._move_word_backwards()
            return
        if kb.matches(data, "tui.editor.cursorWordRight"):
            self._move_word_forwards()
            return
        if kb.matches(data, "tui.editor.cursorLeft"):
            self._move_cursor(-1)
            return
        if kb.matches(data, "tui.editor.cursorRight"):
            self._move_cursor(1)
            return

        # Submit
        if kb.matches(data, "tui.input.submit"):
            self._submit()
            return

        # History navigation
        if kb.matches(data, "tui.editor.cursorUp"):
            self._navigate_history(-1)
            return
        if kb.matches(data, "tui.editor.cursorDown"):
            self._navigate_history(1)
            return

        # Try Kitty printable
        kitty_printable = decode_kitty_printable(data)
        if kitty_printable is not None:
            self._insert_characters(kitty_printable)
            return

        # Regular characters
        if data and ord(data[0]) >= 32:
            self._insert_characters(data)

    def _insert_characters(self, chars: str) -> None:
        """Insert characters at cursor position."""
        # Start new undo group for first character
        if self._undo_coalesce_group != "typing":
            self._push_undo_state()
            self._undo_coalesce_group = "typing"

        self._value = self._value[: self._cursor_pos] + chars + self._value[self._cursor_pos :]
        self._cursor_pos += len(chars)
        self._last_action = "type"

        if self.on_change:
            self.on_change(self._value)

        if self.tui:
            self.tui.request_render()

    def _handle_backspace(self) -> None:
        """Handle backspace key."""
        if self._cursor_pos > 0:
            self._push_undo_state()
            self._undo_coalesce_group = "delete"

            self._value[self._cursor_pos - 1]
            self._value = self._value[: self._cursor_pos - 1] + self._value[self._cursor_pos :]
            self._cursor_pos -= 1
            self._last_action = "delete"

            if self.on_change:
                self.on_change(self._value)

            if self.tui:
                self.tui.request_render()

    def _handle_forward_delete(self) -> None:
        """Handle forward delete key."""
        if self._cursor_pos < len(self._value):
            self._push_undo_state()
            self._undo_coalesce_group = "delete"

            self._value = self._value[: self._cursor_pos] + self._value[self._cursor_pos + 1 :]
            self._last_action = "delete"

            if self.on_change:
                self.on_change(self._value)

            if self.tui:
                self.tui.request_render()

    def _delete_word_backwards(self) -> None:
        """Delete word backwards."""
        if self._cursor_pos == 0:
            return

        self._push_undo_state()
        self._undo_coalesce_group = "kill"

        # Find start of word
        start = self._cursor_pos
        while start > 0 and self._value[start - 1].isspace():
            start -= 1
        while start > 0 and not self._value[start - 1].isspace():
            start -= 1

        killed_text = self._value[start : self._cursor_pos]
        self._kill_ring.push(killed_text, prepend=True, accumulate=(self._last_action == "kill"))

        self._value = self._value[:start] + self._value[self._cursor_pos :]
        self._cursor_pos = start
        self._last_action = "kill"

        if self.on_change:
            self.on_change(self._value)

        if self.tui:
            self.tui.request_render()

    def _delete_word_forwards(self) -> None:
        """Delete word forwards."""
        if self._cursor_pos >= len(self._value):
            return

        self._push_undo_state()
        self._undo_coalesce_group = "kill"

        # Find end of word
        end = self._cursor_pos
        while end < len(self._value) and not self._value[end].isspace():
            end += 1
        while end < len(self._value) and self._value[end].isspace():
            end += 1

        killed_text = self._value[self._cursor_pos : end]
        self._kill_ring.push(killed_text, prepend=False, accumulate=(self._last_action == "kill"))

        self._value = self._value[: self._cursor_pos] + self._value[end:]
        self._last_action = "kill"

        if self.on_change:
            self.on_change(self._value)

        if self.tui:
            self.tui.request_render()

    def _delete_to_end_of_line(self) -> None:
        """Delete from cursor to end of line."""
        if self._cursor_pos < len(self._value):
            self._push_undo_state()
            self._undo_coalesce_group = "kill"

            killed_text = self._value[self._cursor_pos :]
            self._kill_ring.push(killed_text, prepend=False, accumulate=(self._last_action == "kill"))

            self._value = self._value[: self._cursor_pos]
            self._last_action = "kill"

            if self.on_change:
                self.on_change(self._value)

            if self.tui:
                self.tui.request_render()

    def _delete_to_start_of_line(self) -> None:
        """Delete from cursor to start of line."""
        if self._cursor_pos > 0:
            self._push_undo_state()
            self._undo_coalesce_group = "kill"

            killed_text = self._value[: self._cursor_pos]
            self._kill_ring.push(killed_text, prepend=True, accumulate=(self._last_action == "kill"))

            self._value = self._value[self._cursor_pos :]
            self._cursor_pos = 0
            self._last_action = "kill"

            if self.on_change:
                self.on_change(self._value)

            if self.tui:
                self.tui.request_render()

    def _yank(self) -> None:
        """Yank (paste) from kill ring."""
        text = self._kill_ring.peek()
        if text:
            self._push_undo_state()
            self._undo_coalesce_group = "yank"

            self._value = self._value[: self._cursor_pos] + text + self._value[self._cursor_pos :]
            self._cursor_pos += len(text)
            self._last_yank_text = text
            self._last_action = "yank"

            if self.on_change:
                self.on_change(self._value)

            if self.tui:
                self.tui.request_render()

    def _yank_pop(self) -> None:
        """Rotate kill ring and yank."""
        if self._last_action == "yank" and self._last_yank_text:
            # Remove previous yank
            self._value = self._value[: self._cursor_pos - len(self._last_yank_text)] + self._value[self._cursor_pos :]
            self._cursor_pos -= len(self._last_yank_text)

            # Rotate and yank next
            self._kill_ring.rotate()
            text = self._kill_ring.peek()
            if text:
                self._value = self._value[: self._cursor_pos] + text + self._value[self._cursor_pos :]
                self._cursor_pos += len(text)
                self._last_yank_text = text

                if self.on_change:
                    self.on_change(self._value)

                if self.tui:
                    self.tui.request_render()

    def _move_cursor(self, delta: int) -> None:
        """Move cursor by delta."""
        new_pos = max(0, min(self._cursor_pos + delta, len(self._value)))
        if new_pos != self._cursor_pos:
            self._cursor_pos = new_pos
            self._undo_coalesce_group = None  # Movement breaks coalescing
            if self.tui:
                self.tui.request_render()

    def _move_to_start(self) -> None:
        """Move cursor to start."""
        self._cursor_pos = 0
        self._undo_coalesce_group = None
        if self.tui:
            self.tui.request_render()

    def _move_to_end(self) -> None:
        """Move cursor to end."""
        self._cursor_pos = len(self._value)
        self._undo_coalesce_group = None
        if self.tui:
            self.tui.request_render()

    def _move_word_backwards(self) -> None:
        """Move cursor back one word."""
        col = self._cursor_pos

        # Skip whitespace
        while col > 0 and col <= len(self._value) and self._value[col - 1].isspace():
            col -= 1

        # Skip word characters
        while col > 0 and col <= len(self._value) and not self._value[col - 1].isspace():
            col -= 1

        self._cursor_pos = col
        self._undo_coalesce_group = None
        if self.tui:
            self.tui.request_render()

    def _move_word_forwards(self) -> None:
        """Move cursor forward one word."""
        col = self._cursor_pos

        # Skip word characters
        while col < len(self._value) and not self._value[col].isspace():
            col += 1

        # Skip whitespace
        while col < len(self._value) and self._value[col].isspace():
            col += 1

        self._cursor_pos = col
        self._undo_coalesce_group = None
        if self.tui:
            self.tui.request_render()

    def _navigate_history(self, direction: int) -> None:
        """Navigate through history."""
        if not self._history:
            return

        new_index = self._history_index + direction
        new_index = max(-1, min(new_index, len(self._history) - 1))

        if new_index == self._history_index:
            return

        self._push_undo_state()
        self._history_index = new_index

        if self._history_index >= 0:
            self._value = self._history[self._history_index]
        else:
            self._value = ""

        self._cursor_pos = len(self._value)
        self._undo_coalesce_group = None

        if self.on_change:
            self.on_change(self._value)

        if self.tui:
            self.tui.request_render()

    def _submit(self) -> None:
        """Submit the current value."""
        text = self._value
        self.add_to_history(text)

        if self.on_submit:
            self.on_submit(text)

    def _cancel_autocomplete(self) -> None:
        """Cancel autocomplete mode."""
        self._autocomplete_list = None
        self._autocomplete_prefix = ""
        if self.tui:
            self.tui.request_render()

    def _handle_tab_completion(self) -> None:
        """Handle tab key for completion."""
        # Placeholder - would integrate with autocomplete provider
        self._autocomplete_list = None
        if self.tui:
            self.tui.request_render()

    def _apply_completion(self, item: SelectItem) -> None:
        """Apply a completion item."""
        # Placeholder - would apply the completion
        self._cancel_autocomplete()
