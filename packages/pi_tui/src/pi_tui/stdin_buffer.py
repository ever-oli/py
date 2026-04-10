"""StdinBuffer - buffers input and emits complete sequences.

This is necessary because stdin data events can arrive in partial chunks,
especially for escape sequences like mouse events. Without buffering,
partial sequences can be misinterpreted as regular keypresses.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Callable

ESC = "\x1b"
BRACKETED_PASTE_START = "\x1b[200~"
BRACKETED_PASTE_END = "\x1b[201~"


def is_complete_sequence(data: str) -> str:
    """Check if a string is a complete escape sequence.

    Returns: "complete", "incomplete", or "not-escape"
    """
    if not data.startswith(ESC):
        return "not-escape"

    if len(data) == 1:
        return "incomplete"

    after_esc = data[1:]

    # CSI sequences: ESC [
    if after_esc.startswith("["):
        if after_esc.startswith("[M"):
            # Old-style mouse needs ESC[M + 3 bytes = 6 total
            return "complete" if len(data) >= 6 else "incomplete"
        return is_complete_csi_sequence(data)

    # OSC sequences: ESC ]
    if after_esc.startswith("]"):
        return is_complete_osc_sequence(data)

    # DCS sequences: ESC P ... ESC \
    if after_esc.startswith("P"):
        return is_complete_dcs_sequence(data)

    # APC sequences: ESC _ ... ESC \
    if after_esc.startswith("_"):
        return is_complete_apc_sequence(data)

    # SS3 sequences: ESC O
    if after_esc.startswith("O"):
        return "complete" if len(after_esc) >= 2 else "incomplete"

    # Meta key sequences: ESC followed by a single character
    if len(after_esc) == 1:
        return "complete"

    return "complete"


def is_complete_csi_sequence(data: str) -> str:
    """Check if CSI sequence is complete.

    CSI sequences: ESC [ ... followed by a final byte (0x40-0x7E)
    """
    if not data.startswith(f"{ESC}["):
        return "complete"

    if len(data) < 3:
        return "incomplete"

    payload = data[2:]
    last_char = payload[-1]
    last_char_code = ord(last_char)

    if 0x40 <= last_char_code <= 0x7E:
        # Special handling for SGR mouse sequences
        if payload.startswith("<"):
            import re

            mouse_match = re.match(r"^<\d+;\d+;\d+[Mm]$", payload)
            if mouse_match:
                return "complete"
            if last_char in "Mm":
                parts = payload[1:-1].split(";")
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    return "complete"
            return "incomplete"
        return "complete"

    return "incomplete"


def is_complete_osc_sequence(data: str) -> str:
    r"""Check if OSC sequence is complete.

    OSC sequences: ESC ] ... ST (where ST is ESC \\ or BEL)
    """
    if not data.startswith(f"{ESC}]"):
        return "complete"

    if data.endswith(f"{ESC}\\") or data.endswith("\x07"):
        return "complete"

    return "incomplete"


def is_complete_dcs_sequence(data: str) -> str:
    """Check if DCS sequence is complete.

    DCS sequences: ESC P ... ST
    """
    if not data.startswith(f"{ESC}P"):
        return "complete"

    if data.endswith(f"{ESC}\\"):
        return "complete"

    return "incomplete"


def is_complete_apc_sequence(data: str) -> str:
    """Check if APC sequence is complete.

    APC sequences: ESC _ ... ST
    """
    if not data.startswith(f"{ESC}_"):
        return "complete"

    if data.endswith(f"{ESC}\\"):
        return "complete"

    return "incomplete"


def extract_complete_sequences(buffer: str) -> dict:
    """Split accumulated buffer into complete sequences.

    Returns dict with 'sequences' and 'remainder' keys.
    """
    sequences = []
    pos = 0

    while pos < len(buffer):
        remaining = buffer[pos:]

        if remaining.startswith(ESC):
            seq_end = 1
            while seq_end <= len(remaining):
                candidate = remaining[:seq_end]
                status = is_complete_sequence(candidate)

                if status == "complete":
                    sequences.append(candidate)
                    pos += seq_end
                    break
                elif status == "incomplete":
                    seq_end += 1
                else:
                    sequences.append(candidate)
                    pos += seq_end
                    break

            if seq_end > len(remaining):
                return {"sequences": sequences, "remainder": remaining}
        else:
            # Not an escape sequence - take single character
            sequences.append(remaining[0])
            pos += 1

    return {"sequences": sequences, "remainder": ""}


class StdinBuffer:
    """Buffers stdin input and emits complete sequences.

    Handles partial escape sequences that arrive across multiple chunks.
    """

    def __init__(self, timeout: int = 10):
        """Initialize the buffer.

        Args:
            timeout: Maximum time to wait for sequence completion in ms
        """
        self._buffer = ""
        self._timeout_ms = timeout
        self._timer: threading.Timer | None = None
        self._paste_mode = False
        self._paste_buffer = ""
        self._callbacks: dict[str, list[Callable]] = {
            "data": [],
            "paste": [],
        }
        self._lock = threading.Lock()

    def on(self, event: str, callback: Callable) -> None:
        """Register an event handler."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """Unregister an event handler."""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _emit(self, event: str, data: str) -> None:
        """Emit an event to all registered handlers."""
        for callback in self._callbacks.get(event, []):
            with contextlib.suppress(Exception):
                callback(data)

    def _cancel_timer(self) -> None:
        """Cancel any pending timeout."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _start_timer(self) -> None:
        """Start the timeout timer."""
        self._cancel_timer()
        self._timer = threading.Timer(self._timeout_ms / 1000.0, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _on_timeout(self) -> None:
        """Handle timeout - flush incomplete sequences."""
        with self._lock:
            if self._buffer:
                flushed = self.flush()
                for seq in flushed:
                    self._emit("data", seq)

    def process(self, data: str) -> None:
        """Process incoming data.

        Args:
            data: Raw input data from terminal
        """
        with self._lock:
            self._cancel_timer()

            # Handle high-byte conversion
            if isinstance(data, bytes):
                if len(data) == 1 and data[0] > 127:
                    byte = data[0] - 128
                    data = f"\x1b{chr(byte)}"
                else:
                    data = data.decode("utf-8", errors="surrogateescape")

            if not data and not self._buffer:
                self._emit("data", "")
                return

            self._buffer += data

            # Handle paste mode
            if self._paste_mode:
                self._paste_buffer += self._buffer
                self._buffer = ""

                end_index = self._paste_buffer.find(BRACKETED_PASTE_END)
                if end_index != -1:
                    pasted_content = self._paste_buffer[:end_index]
                    remaining = self._paste_buffer[end_index + len(BRACKETED_PASTE_END) :]

                    self._paste_mode = False
                    self._paste_buffer = ""

                    self._emit("paste", pasted_content)

                    if remaining:
                        self.process(remaining)
                return

            # Check for bracketed paste start
            start_index = self._buffer.find(BRACKETED_PASTE_START)
            if start_index != -1:
                if start_index > 0:
                    before_paste = self._buffer[:start_index]
                    result = extract_complete_sequences(before_paste)
                    for sequence in result["sequences"]:
                        self._emit("data", sequence)

                self._buffer = self._buffer[start_index + len(BRACKETED_PASTE_START) :]
                self._paste_mode = True
                self._paste_buffer = self._buffer
                self._buffer = ""

                end_index = self._paste_buffer.find(BRACKETED_PASTE_END)
                if end_index != -1:
                    pasted_content = self._paste_buffer[:end_index]
                    remaining = self._paste_buffer[end_index + len(BRACKETED_PASTE_END) :]

                    self._paste_mode = False
                    self._paste_buffer = ""

                    self._emit("paste", pasted_content)

                    if remaining:
                        self.process(remaining)
                return

            # Normal processing
            result = extract_complete_sequences(self._buffer)
            self._buffer = result["remainder"]

            for sequence in result["sequences"]:
                self._emit("data", sequence)

            if self._buffer:
                self._start_timer()

    def flush(self) -> list[str]:
        """Flush the buffer, returning any incomplete sequences."""
        with self._lock:
            self._cancel_timer()

            if not self._buffer:
                return []

            sequences = [self._buffer]
            self._buffer = ""
            return sequences

    def clear(self) -> None:
        """Clear the buffer and cancel any pending operations."""
        with self._lock:
            self._cancel_timer()
            self._buffer = ""
            self._paste_mode = False
            self._paste_buffer = ""

    def get_buffer(self) -> str:
        """Get the current buffer contents."""
        with self._lock:
            return self._buffer

    def destroy(self) -> None:
        """Clean up resources."""
        self.clear()
