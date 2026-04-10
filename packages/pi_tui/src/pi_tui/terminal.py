"""Terminal interface for TUI."""

from __future__ import annotations

import fcntl
import os
import select
import signal
import struct
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Callable, TextIO

from .ansi import ansi


@dataclass
class TerminalSize:
    """Terminal dimensions."""

    rows: int
    cols: int


class Terminal:
    """Abstract terminal interface.

    This defines the interface for terminal operations. Implementations
    can provide real terminal I/O or mock terminals for testing.
    """

    def __init__(self):
        self._kitty_protocol_active = False
        self._on_input: Callable[[str], None] | None = None
        self._on_resize: Callable[[], None] | None = None

    @property
    def rows(self) -> int:
        """Number of rows in the terminal."""
        raise NotImplementedError

    @property
    def cols(self) -> int:
        """Number of columns in the terminal."""
        raise NotImplementedError

    @property
    def kitty_protocol_active(self) -> bool:
        """Whether Kitty keyboard protocol is active."""
        return self._kitty_protocol_active

    def start(
        self,
        on_input: Callable[[str], None],
        on_resize: Callable[[], None],
    ) -> None:
        """Start the terminal with input and resize handlers."""
        self._on_input = on_input
        self._on_resize = on_resize

    def stop(self) -> None:
        """Stop the terminal and restore state."""
        pass

    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None:
        """Drain stdin before exiting to prevent key release events from leaking."""
        pass

    def write(self, data: str) -> None:
        """Write output to terminal."""
        raise NotImplementedError

    def move_by(self, lines: int) -> None:
        """Move cursor up (negative) or down (positive) by N lines."""
        if lines > 0:
            self.write(ansi.move_down(lines))
        elif lines < 0:
            self.write(ansi.move_up(-lines))

    def hide_cursor(self) -> None:
        """Hide the cursor."""
        self.write(ansi.CURSOR_HIDE)

    def show_cursor(self) -> None:
        """Show the cursor."""
        self.write(ansi.CURSOR_SHOW)

    def clear_line(self) -> None:
        """Clear current line."""
        self.write(ansi.CLEAR_LINE)

    def clear_from_cursor(self) -> None:
        """Clear from cursor to end of screen."""
        self.write(ansi.CLEAR_FROM_CURSOR)

    def clear_screen(self) -> None:
        """Clear entire screen and move cursor to home."""
        self.write(ansi.CLEAR_SCREEN + ansi.CURSOR_HOME)

    def set_title(self, title: str) -> None:
        """Set terminal window title."""
        self.write(ansi.set_title(title))

    def cursor_position(self, row: int, col: int) -> None:
        """Move cursor to position (1-indexed)."""
        self.write(ansi.cursor_position(row, col))

    def set_column(self, col: int) -> None:
        """Move cursor to column (1-indexed)."""
        self.write(ansi.set_column(col))


class ProcessTerminal(Terminal):
    """Real terminal using stdin/stdout."""

    def __init__(
        self,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ):
        super().__init__()
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._original_tty: list | None = None
        self._is_raw = False
        self._modify_other_keys_active = False
        self._old_signal_handler: Callable | None = None

    @property
    def rows(self) -> int:
        """Get number of terminal rows."""
        try:
            size = self._get_terminal_size()
            return size.rows
        except OSError:
            return int(os.environ.get("LINES", "24"))

    @property
    def cols(self) -> int:
        """Get number of terminal columns."""
        try:
            size = self._get_terminal_size()
            return size.cols
        except OSError:
            return int(os.environ.get("COLUMNS", "80"))

    def _get_terminal_size(self) -> TerminalSize:
        """Get terminal size using ioctl."""
        fd = self._stdin.fileno()
        # TIOCGWINSZ = 0x5413
        data = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 4)
        rows, cols = struct.unpack("hh", data)
        return TerminalSize(rows=rows, cols=cols)

    def start(
        self,
        on_input: Callable[[str], None],
        on_resize: Callable[[], None],
    ) -> None:
        """Start terminal in raw mode with input handling."""
        super().start(on_input, on_resize)

        # Save current TTY settings
        fd = self._stdin.fileno()
        self._original_tty = termios.tcgetattr(fd)

        # Set raw mode
        tty.setraw(fd)
        self._is_raw = True

        # Enable bracketed paste mode
        self.write(ansi.BRACKETED_PASTE_ON)

        # Query Kitty keyboard protocol
        self.write(ansi.KITTY_QUERY)

        # Set up resize handler
        self._old_signal_handler = signal.signal(signal.SIGWINCH, self._handle_sigwinch)

        # Start input thread
        import threading

        self._input_thread = threading.Thread(target=self._read_input, daemon=True)
        self._input_thread_running = True
        self._input_thread.start()

    def stop(self) -> None:
        """Stop terminal and restore original state."""
        super().stop()

        self._input_thread_running = False

        # Disable bracketed paste
        self.write(ansi.BRACKETED_PASTE_OFF)

        # Disable Kitty keyboard protocol
        if self._kitty_protocol_active:
            self.write(ansi.KITTY_DISABLE)
            self._kitty_protocol_active = False

        # Disable modifyOtherKeys
        if self._modify_other_keys_active:
            self.write(ansi.MODIFY_OTHER_KEYS_DISABLE)
            self._modify_other_keys_active = False

        # Restore signal handler
        if self._old_signal_handler is not None:
            signal.signal(signal.SIGWINCH, self._old_signal_handler)

        # Restore TTY settings
        if self._original_tty and self._is_raw:
            fd = self._stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, self._original_tty)
            self._is_raw = False

    def _handle_sigwinch(self, signum, frame) -> None:
        """Handle terminal resize signal."""
        if self._on_resize:
            self._on_resize()

    def _read_input(self) -> None:
        """Read input from stdin in a loop."""
        while self._input_thread_running:
            try:
                # Check if input is available
                fd = self._stdin.fileno()
                ready, _, _ = select.select([fd], [], [], 0.1)
                if ready:
                    data = os.read(fd, 1024)
                    if data:
                        decoded = data.decode("utf-8", errors="surrogateescape")
                        if self._on_input:
                            self._on_input(decoded)
            except OSError:
                if not self._input_thread_running:
                    break

    def write(self, data: str) -> None:
        """Write data to stdout."""
        try:
            self._stdout.write(data)
            self._stdout.flush()
        except OSError:
            pass

    def enable_sync_output(self) -> None:
        """Enable synchronized output mode."""
        self.write(ansi.SYNC_START)

    def disable_sync_output(self) -> None:
        """Disable synchronized output mode."""
        self.write(ansi.SYNC_END)

    def enable_kitty_protocol(self) -> None:
        """Enable Kitty keyboard protocol."""
        self._kitty_protocol_active = True
        self.write(ansi.KITTY_ENABLE)

    def disable_kitty_protocol(self) -> None:
        """Disable Kitty keyboard protocol."""
        self._kitty_protocol_active = False
        self.write(ansi.KITTY_DISABLE)

    def enable_modify_other_keys(self) -> None:
        """Enable xterm modifyOtherKeys mode."""
        self._modify_other_keys_active = True
        self.write(ansi.MODIFY_OTHER_KEYS_ENABLE)

    def disable_modify_other_keys(self) -> None:
        """Disable xterm modifyOtherKeys mode."""
        self._modify_other_keys_active = False
        self.write(ansi.MODIFY_OTHER_KEYS_DISABLE)


class MockTerminal(Terminal):
    """Mock terminal for testing."""

    def __init__(self, rows: int = 24, cols: int = 80):
        super().__init__()
        self._rows = rows
        self._cols = cols
        self._output: list[str] = []

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    def write(self, data: str) -> None:
        self._output.append(data)

    def get_output(self) -> str:
        """Get all written output as a single string."""
        return "".join(self._output)

    def clear_output(self) -> None:
        """Clear the output buffer."""
        self._output.clear()
