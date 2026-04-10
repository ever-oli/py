"""Tests for pi-tui."""

import pytest

from pi_tui import Buffer, Cell, CellAttributes, truncate_to_width, visible_width


class TestCell:
    """Test Cell class."""

    def test_cell_creation(self):
        """Test creating a cell."""
        cell = Cell(char="X", fg=(255, 255, 255), bg=(0, 0, 0))
        assert cell.char == "X"
        assert cell.fg == (255, 255, 255)
        assert cell.bg == (0, 0, 0)

    def test_cell_default(self):
        """Test cell defaults."""
        cell = Cell()
        assert cell.char == " "
        assert cell.fg is None
        assert cell.bg is None

    def test_cell_empty(self):
        """Test empty cell check."""
        cell = Cell()
        assert cell.is_empty()

        cell2 = Cell(char="A")
        assert not cell2.is_empty()

    def test_cell_copy(self):
        """Test cell copying."""
        cell = Cell(char="X", fg=(255, 0, 0))
        copy = cell.copy()
        assert copy.char == cell.char
        assert copy.fg == cell.fg

        # Modify original, copy should be unchanged
        cell.char = "Y"
        assert copy.char == "X"


class TestCellAttributes:
    """Test CellAttributes class."""

    def test_default_attributes(self):
        """Test default attributes."""
        attrs = CellAttributes()
        assert not attrs.bold
        assert not attrs.italic
        assert not attrs.underline

    def test_attributes_equality(self):
        """Test attribute equality."""
        attrs1 = CellAttributes(bold=True)
        attrs2 = CellAttributes(bold=True)
        attrs3 = CellAttributes()

        assert attrs1 == attrs2
        assert attrs1 != attrs3


class TestBuffer:
    """Test Buffer class."""

    def test_buffer_creation(self):
        """Test creating a buffer."""
        buf = Buffer(rows=10, cols=20)
        assert buf.rows == 10
        assert buf.cols == 20

    def test_buffer_get_set(self):
        """Test getting and setting cells."""
        buf = Buffer(rows=5, cols=5)

        cell = Cell(char="X")
        buf.set(0, 0, cell)

        retrieved = buf.get(0, 0)
        assert retrieved.char == "X"

    def test_buffer_out_of_bounds(self):
        """Test out of bounds access."""
        buf = Buffer(rows=5, cols=5)

        # Should return default cell
        cell = buf.get(10, 10)
        assert cell.char == " "

    def test_buffer_clear(self):
        """Test clearing buffer."""
        buf = Buffer(rows=5, cols=5)
        buf.set(0, 0, Cell(char="X"))

        buf.clear()
        assert buf.get(0, 0).char == " "

    def test_buffer_diff(self):
        """Test buffer diffing."""
        buf1 = Buffer(rows=3, cols=3)
        buf2 = Buffer(rows=3, cols=3)

        buf2.set(0, 0, Cell(char="X"))
        buf2.set(1, 1, Cell(char="Y"))

        diff = buf1.diff(buf2)
        assert len(diff.changes) == 2


class TestUtils:
    """Test utility functions."""

    def test_visible_width(self):
        """Test visible width calculation."""
        assert visible_width("hello") == 5
        assert visible_width("") == 0

    def test_visible_width_with_ansi(self):
        """Test visible width with ANSI codes."""
        text = "\x1b[31mred\x1b[0m"
        assert visible_width(text) == 3

    def test_truncate_to_width(self):
        """Test text truncation."""
        text = "hello world"
        result = truncate_to_width(text, 5)
        assert visible_width(result) == 5

    def test_truncate_with_ellipsis(self):
        """Test truncation with ellipsis."""
        text = "hello world"
        result = truncate_to_width(text, 8, ellipsis="...")
        assert "..." in result


class TestKeys:
    """Test key handling."""

    def test_parse_key_simple(self):
        """Test parsing simple keys."""
        from pi_tui import parse_key

        # Regular character
        assert parse_key("a") == "a"
        assert parse_key("1") == "1"

    def test_parse_key_escape(self):
        """Test parsing escape key."""
        from pi_tui import parse_key

        assert parse_key("\x1b") == "escape"

    def test_matches_key(self):
        """Test key matching."""
        from pi_tui import matches_key

        assert matches_key("a", "a")
        assert matches_key("\x1b", "escape")
        assert matches_key("\r", "enter")
        assert not matches_key("a", "b")


class TestBufferDiff:
    """Test buffer differential rendering."""

    def test_diff_empty(self):
        """Test diff between identical buffers."""
        buf1 = Buffer(rows=3, cols=3)
        buf2 = Buffer(rows=3, cols=3)

        diff = buf1.diff(buf2)
        assert diff.is_empty()

    def test_diff_changes(self):
        """Test diff with changes."""
        buf1 = Buffer(rows=3, cols=3)
        buf2 = Buffer(rows=3, cols=3)

        buf2.set(0, 0, Cell(char="A"))
        buf2.set(1, 1, Cell(char="B"))

        diff = buf1.diff(buf2)
        assert not diff.is_empty()
        assert len(diff.changes) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
