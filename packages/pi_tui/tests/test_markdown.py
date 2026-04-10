"""Tests for Markdown component."""

from pi_tui.components.markdown import (
    CodeBlock,
    Heading,
    HorizontalRule,
    InlineCode,
    Link,
    ListComponent,
    Markdown,
    Quote,
    Table,
)


class TestMarkdown:
    """Tests for Markdown component."""

    def test_set_content(self):
        """Should set and get content."""
        md = Markdown()
        md.set_content("# Hello")
        assert md.get_content() == "# Hello"

    def test_empty_content(self):
        """Should handle empty content."""
        md = Markdown()
        lines = md.render(80)
        assert len(lines) == 1
        assert lines[0] == ""

    def test_render_with_content(self):
        """Should render markdown content."""
        md = Markdown("# Hello World")
        lines = md.render(80)
        assert len(lines) >= 1

    def test_caching(self):
        """Should cache render results."""
        md = Markdown("# Test")
        lines1 = md.render(80)
        lines2 = md.render(80)
        assert lines1 == lines2
        # Same width should use cache

    def test_different_width_invalidates_cache(self):
        """Different width should invalidate cache."""
        md = Markdown("# Test")
        md.render(80)
        md.render(40)
        # May be different due to wrapping
        assert md._cached_width == 40

    def test_invalidate(self):
        """Invalidate should clear cache."""
        md = Markdown("# Test")
        md.render(80)
        assert md._cached_lines is not None

        md.invalidate()
        assert md._cached_lines is None


class TestCodeBlock:
    """Tests for CodeBlock component."""

    def test_set_code(self):
        """Should set code content."""
        cb = CodeBlock()
        cb.set_code("print('hello')", "python")
        # Should not raise

    def test_render_code(self):
        """Should render code block."""
        cb = CodeBlock("print('hello')", "python")
        lines = cb.render(80)
        assert len(lines) >= 1

    def test_empty_code(self):
        """Should handle empty code."""
        cb = CodeBlock()
        lines = cb.render(80)
        assert len(lines) == 1

    def test_caching(self):
        """Should cache rendered output."""
        cb = CodeBlock("print('test')", "python")
        lines1 = cb.render(80)
        lines2 = cb.render(80)
        assert lines1 == lines2


class TestInlineCode:
    """Tests for InlineCode component."""

    def test_set_code(self):
        """Should set code."""
        ic = InlineCode()
        ic.set_code("var")
        lines = ic.render(80)
        assert "var" in lines[0]

    def test_render_includes_backticks(self):
        """Should include backticks in output."""
        ic = InlineCode("code")
        lines = ic.render(80)
        assert lines[0] == "`code`"

    def test_truncate_long_code(self):
        """Should truncate long code."""
        ic = InlineCode("x" * 100)
        lines = ic.render(20)
        assert len(lines) == 1


class TestQuote:
    """Tests for Quote component."""

    def test_set_content(self):
        """Should set content."""
        q = Quote()
        q.set_content("Important quote")
        lines = q.render(80)
        assert any("Important" in line for line in lines)

    def test_quote_marker(self):
        """Should include quote marker."""
        q = Quote("This is a quote")
        lines = q.render(80)
        assert lines[0].startswith("▌")

    def test_wrapping(self):
        """Should wrap long quotes."""
        q = Quote("a " * 100)
        lines = q.render(40)
        assert len(lines) > 1


class TestListComponent:
    """Tests for ListComponent."""

    def test_set_items(self):
        """Should set items."""
        lc = ListComponent()
        lc.set_items(["one", "two", "three"])
        lines = lc.render(80)
        assert len(lines) >= 3

    def test_add_item(self):
        """Should add item."""
        lc = ListComponent()
        lc.add_item("first")
        lc.add_item("second")
        lines = lc.render(80)
        assert len(lines) >= 2

    def test_unordered_list(self):
        """Should render unordered list."""
        lc = ListComponent(["one", "two"], ordered=False)
        lines = lc.render(80)
        assert any("•" in line for line in lines)

    def test_ordered_list(self):
        """Should render ordered list."""
        lc = ListComponent(["one", "two"], ordered=True)
        lines = lc.render(80)
        assert any("1." in line for line in lines)
        assert any("2." in line for line in lines)

    def test_wrapping(self):
        """Should wrap long items."""
        lc = ListComponent(["a " * 50])
        lines = lc.render(40)
        assert len(lines) > 1


class TestHeading:
    """Tests for Heading component."""

    def test_level_1(self):
        """Level 1 heading."""
        h = Heading("Title", 1)
        lines = h.render(80)
        assert "═══" in lines[0] or "Title" in lines[0]

    def test_level_2(self):
        """Level 2 heading."""
        h = Heading("Subtitle", 2)
        lines = h.render(80)
        assert "══" in lines[0] or "Subtitle" in lines[0]

    def test_level_3(self):
        """Level 3 heading."""
        h = Heading("Section", 3)
        lines = h.render(80)
        assert "═" in lines[0] or "Section" in lines[0]

    def test_truncate_long_heading(self):
        """Should truncate long heading."""
        h = Heading("x" * 100, 1)
        lines = h.render(40)
        # Check visible width (excluding ANSI codes)
        from pi_tui.utils import visible_width

        assert visible_width(lines[0]) <= 40

    def test_set_text(self):
        """Should set text."""
        h = Heading()
        h.set_text("New Title")
        lines = h.render(80)
        assert "New Title" in lines[0]


class TestHorizontalRule:
    """Tests for HorizontalRule component."""

    def test_render(self):
        """Should render horizontal line."""
        hr = HorizontalRule()
        lines = hr.render(40)
        assert len(lines) == 1
        assert len(lines[0]) == 40
        assert all(c == "─" for c in lines[0])


class TestLink:
    """Tests for Link component."""

    def test_render_with_text(self):
        """Should render link with text."""
        link = Link("Click here", "https://example.com")
        lines = link.render(80)
        assert "Click here" in lines[0]

    def test_render_without_text(self):
        """Should render link without text."""
        link = Link("", "https://example.com")
        lines = link.render(80)
        assert "example.com" in lines[0]

    def test_set_link(self):
        """Should set link."""
        link = Link()
        link.set_link("Visit", "http://test.com")
        lines = link.render(80)
        assert "Visit" in lines[0]


class TestTable:
    """Tests for Table component."""

    def test_empty_table(self):
        """Should handle empty table."""
        t = Table()
        lines = t.render(80)
        assert len(lines) == 1
        assert lines[0] == ""

    def test_headers_only(self):
        """Should render headers."""
        t = Table(["Name", "Value"])
        lines = t.render(80)
        assert len(lines) >= 1
        assert any("Name" in line for line in lines)

    def test_with_rows(self):
        """Should render with data rows."""
        t = Table(
            ["Name", "Value"],
            [
                ["Alice", "100"],
                ["Bob", "200"],
            ],
        )
        lines = t.render(80)
        assert any("Alice" in line for line in lines)
        assert any("Bob" in line for line in lines)

    def test_set_data(self):
        """Should set table data."""
        t = Table()
        t.set_data(["A", "B"], [["1", "2"]])
        lines = t.render(80)
        assert any("A" in line for line in lines)

    def test_separator_line(self):
        """Should include separator after headers."""
        t = Table(["Name", "Value"], [["A", "1"]])
        lines = t.render(80)
        assert any("-" in line for line in lines)
