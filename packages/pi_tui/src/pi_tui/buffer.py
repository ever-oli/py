"""Buffer system for differential terminal rendering."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .cell import Cell


@dataclass
class BufferDiff:
    """Represents a diff between two buffer states.

    Contains the minimal operations needed to update the screen.
    """

    # List of (row, col, cell) tuples for changed cells
    changes: list[tuple[int, int, Cell]]

    # Cursor position to move to (if needed)
    cursor_row: int | None = None
    cursor_col: int | None = None

    # Whether to clear screen first
    clear_first: bool = False

    def is_empty(self) -> bool:
        """Check if this diff has no changes."""
        return len(self.changes) == 0 and not self.clear_first


class Buffer:
    """2D buffer for terminal screen content.

    The buffer stores cells in row-major order (row 0 is top).
    Each cell can contain a character and styling information.

    The buffer supports differential rendering by comparing with another buffer
    and generating a diff that only updates changed cells.
    """

    def __init__(self, rows: int = 24, cols: int = 80, default_cell: Cell | None = None):
        """Initialize a new buffer.

        Args:
            rows: Number of rows (lines)
            cols: Number of columns
            default_cell: Default cell to use for empty positions
        """
        self._rows = max(1, rows)
        self._cols = max(1, cols)
        self._default = default_cell or Cell()
        self._cells: list[list[Cell]] = []
        self._damage: set[tuple[int, int]] = set()  # Track changed cells
        self.resize(rows, cols)

    @property
    def rows(self) -> int:
        """Number of rows in the buffer."""
        return self._rows

    @property
    def cols(self) -> int:
        """Number of columns in the buffer."""
        return self._cols

    def resize(self, rows: int, cols: int) -> None:
        """Resize the buffer.

        Existing content is preserved when possible. New cells are filled
        with the default cell.
        """
        new_rows = max(1, rows)
        new_cols = max(1, cols)

        # Handle initial case when _cells is empty
        if not self._cells:
            self._cells = [[self._default.copy() for _ in range(new_cols)] for _ in range(new_rows)]
            self._rows = new_rows
            self._cols = new_cols
            self._damage = {(r, c) for r in range(self._rows) for c in range(self._cols)}
            return

        # Create new cell array
        new_cells: list[list[Cell]] = []

        for row in range(new_rows):
            new_row: list[Cell] = []
            for col in range(new_cols):
                if row < self._rows and col < self._cols:
                    # Preserve existing cell
                    new_row.append(self._cells[row][col])
                else:
                    # New cell with default value
                    new_row.append(self._default.copy())
            new_cells.append(new_row)

        self._cells = new_cells
        self._rows = new_rows
        self._cols = new_cols

        # Mark all cells as damaged on resize
        self._damage = {(r, c) for r in range(self._rows) for c in range(self._cols)}

    def get(self, row: int, col: int) -> Cell:
        """Get the cell at the given position.

        Returns the default cell if out of bounds.
        """
        if 0 <= row < self._rows and 0 <= col < self._cols:
            return self._cells[row][col]
        return self._default.copy()

    def set(self, row: int, col: int, cell: Cell) -> None:
        """Set the cell at the given position."""
        if 0 <= row < self._rows and 0 <= col < self._cols:
            old_cell = self._cells[row][col]
            if old_cell != cell:
                self._cells[row][col] = cell.copy()
                self._damage.add((row, col))

    def set_char(self, row: int, col: int, char: str) -> None:
        """Set just the character at the given position."""
        if 0 <= row < self._rows and 0 <= col < self._cols:
            old_cell = self._cells[row][col]
            if old_cell.char != char:
                self._cells[row][col].char = char
                self._damage.add((row, col))

    def set_fg(self, row: int, col: int, fg: tuple[int, int, int] | None) -> None:
        """Set the foreground color at the given position."""
        if 0 <= row < self._rows and 0 <= col < self._cols:
            old_cell = self._cells[row][col]
            if old_cell.fg != fg:
                self._cells[row][col].fg = fg
                self._damage.add((row, col))

    def set_bg(self, row: int, col: int, bg: tuple[int, int, int] | None) -> None:
        """Set the background color at the given position."""
        if 0 <= row < self._rows and 0 <= col < self._cols:
            old_cell = self._cells[row][col]
            if old_cell.bg != bg:
                self._cells[row][col].bg = bg
                self._damage.add((row, col))

    def clear(self) -> None:
        """Clear the entire buffer with the default cell."""
        for row in range(self._rows):
            for col in range(self._cols):
                old_cell = self._cells[row][col]
                if not old_cell.is_empty():
                    self._cells[row][col] = self._default.copy()
                    self._damage.add((row, col))

    def fill(self, cell: Cell) -> None:
        """Fill the entire buffer with the given cell."""
        for row in range(self._rows):
            for col in range(self._cols):
                old_cell = self._cells[row][col]
                if old_cell != cell:
                    self._cells[row][col] = cell.copy()
                    self._damage.add((row, col))

    def clear_damage(self) -> None:
        """Clear the damage tracking."""
        self._damage.clear()

    def get_damage(self) -> set[tuple[int, int]]:
        """Get the set of damaged cell positions."""
        return self._damage.copy()

    def is_damaged(self, row: int, col: int) -> bool:
        """Check if a cell is marked as damaged."""
        return (row, col) in self._damage

    def iter_cells(self) -> Iterator[tuple[int, int, Cell]]:
        """Iterate over all cells with their positions."""
        for row in range(self._rows):
            for col in range(self._cols):
                yield (row, col, self._cells[row][col])

    def iter_row(self, row: int) -> Iterator[Cell]:
        """Iterate over cells in a row."""
        if 0 <= row < self._rows:
            for col in range(self._cols):
                yield self._cells[row][col]

    def iter_col(self, col: int) -> Iterator[Cell]:
        """Iterate over cells in a column."""
        if 0 <= col < self._cols:
            for row in range(self._rows):
                yield self._cells[row][col]

    def diff(self, other: Buffer) -> BufferDiff:
        """Calculate the diff between this buffer and another.

        Returns a BufferDiff containing the minimal changes needed to
        transform this buffer into the other buffer.
        """
        changes: list[tuple[int, int, Cell]] = []

        # Compare overlapping region
        min_rows = min(self._rows, other._rows)
        min_cols = min(self._cols, other._cols)

        for row in range(min_rows):
            for col in range(min_cols):
                if self._cells[row][col] != other._cells[row][col]:
                    changes.append((row, col, other._cells[row][col].copy()))

        # Handle size differences - mark additional cells from larger buffer
        for row in range(min_rows, other._rows):
            for col in range(other._cols):
                changes.append((row, col, other._cells[row][col].copy()))

        for row in range(other._rows, self._rows):
            for col in range(self._cols):
                changes.append((row, col, Cell.empty()))

        for row in range(min_rows):
            for col in range(min_cols, other._cols):
                changes.append((row, col, other._cells[row][col].copy()))
            for col in range(other._cols, self._cols):
                changes.append((row, col, Cell.empty()))

        return BufferDiff(changes=changes)

    def apply_diff(self, diff: BufferDiff) -> None:
        """Apply a diff to this buffer."""
        for row, col, cell in diff.changes:
            if 0 <= row < self._rows and 0 <= col < self._cols:
                self._cells[row][col] = cell.copy()
                self._damage.add((row, col))

    def copy(self) -> Buffer:
        """Create a copy of this buffer."""
        new_buffer = Buffer(self._rows, self._cols, self._default.copy())
        for row in range(self._rows):
            for col in range(self._cols):
                new_buffer._cells[row][col] = self._cells[row][col].copy()
        return new_buffer

    def write_text(
        self,
        row: int,
        col: int,
        text: str,
        fg: tuple[int, int, int] | None = None,
        bg: tuple[int, int, int] | None = None,
    ) -> int:
        """Write text to the buffer starting at the given position.

        Returns the number of characters written.
        """
        if row < 0 or row >= self._rows or col >= self._cols:
            return 0

        written = 0
        for i, char in enumerate(text):
            target_col = col + i
            if target_col >= self._cols:
                break
            old_cell = self._cells[row][target_col]
            if old_cell.char != char or old_cell.fg != fg or old_cell.bg != bg:
                self._cells[row][target_col].char = char
                self._cells[row][target_col].fg = fg
                self._cells[row][target_col].bg = bg
                self._damage.add((row, target_col))
            written += 1

        return written

    def get_text(self, row: int, col: int, length: int) -> str:
        """Get text from the buffer starting at the given position."""
        if row < 0 or row >= self._rows:
            return ""

        chars = []
        for i in range(length):
            target_col = col + i
            if target_col >= self._cols:
                break
            chars.append(self._cells[row][target_col].char)

        return "".join(chars)

    def __str__(self) -> str:
        """Convert buffer to a string representation for debugging."""
        lines = []
        for row in range(self._rows):
            line = "".join(self._cells[row][col].char for col in range(self._cols))
            lines.append(line)
        return "\n".join(lines)

    def to_ansi(self) -> str:
        """Convert the entire buffer to ANSI escape sequences."""
        parts = []
        for row in range(self._rows):
            for col in range(self._cols):
                parts.append(self._cells[row][col].to_ansi())
            if row < self._rows - 1:
                parts.append("\r\n")
        return "".join(parts)
