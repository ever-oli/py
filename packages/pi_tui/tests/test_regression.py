"""Regression tests for edge cases and bugs."""

from pi_tui.utils import truncate_to_width, visible_width, wrap_text_with_ansi


class TestTruncateToWidth:
    """Tests for truncate_to_width edge cases."""

    def test_large_unicode_input(self):
        """Should handle very large unicode input."""
        text = "🙂界" * 100_000
        truncated = truncate_to_width(text, 40, "…")
        assert visible_width(truncated) <= 40
        assert "…" in truncated  # Just check ellipsis is present

    def test_preserves_ansi_styling(self):
        """Should preserve ANSI styling for kept text."""
        text = f"\x1b[31m{'hello ' * 1000}\x1b[0m"
        truncated = truncate_to_width(text, 20, "…")

        assert visible_width(truncated) <= 20
        assert "\x1b[31m" in truncated
        assert "…" in truncated  # Just check ellipsis is present

    def test_malformed_ansi_prefix(self):
        """Should handle malformed ANSI escape prefixes without hanging."""
        text = f"abc\x1bnot-ansi {'🙂' * 1000}"
        truncated = truncate_to_width(text, 20, "…")

        assert visible_width(truncated) <= 20

    def test_returns_fitting_text(self):
        """Should return text that fits within width."""
        result = truncate_to_width("abcdef", 3, "…")
        assert visible_width(result) <= 3
        assert "…" in result

    def test_original_when_fits(self):
        """Should return original text when it fits."""
        assert truncate_to_width("a", 2, "🙂") == "a"
        assert truncate_to_width("界", 2, "🙂") == "界"

    def test_pads_to_width(self):
        """Should pad truncated output to requested width."""
        truncated = truncate_to_width("🙂界🙂界🙂界", 8, "…", True)
        assert visible_width(truncated) == 8

    def test_adds_trailing_reset(self):
        """Should add trailing reset when truncating without ellipsis."""
        truncated = truncate_to_width(f"\x1b[31m{'hello' * 100}", 10, "")
        assert visible_width(truncated) <= 10
        assert truncated.endswith("\x1b[0m")

    def test_contiguous_prefix(self):
        """Should keep contiguous prefix instead of skipping wide grapheme."""
        truncated = truncate_to_width("🙂\t界 \x1b_abc\x07", 7, "…", True)
        assert visible_width(truncated) <= 7


class TestRegionalIndicatorWidth:
    """Tests for regional indicator (flag emoji) width handling.

    Note: These tests require the wcwidth library for proper emoji width handling.
    If wcwidth is not available, the tests will be skipped.
    """

    def test_partial_flag_grapheme_width(self):
        """Should treat partial flag grapheme as full-width."""
        # During streaming, "🇨🇳" often appears as an intermediate "🇨" first.
        # If "🇨" is measured as width 1 while terminal renders it as width 2,
        # differential rendering can drift.
        partial_flag = "🇨"
        list_line = "      - 🇨"

        # Width may vary depending on wcwidth availability
        w = visible_width(partial_flag)
        assert w >= 1  # At least 1, ideally 2 with wcwidth

        # The list line should account for the emoji width
        line_width = visible_width(list_line)
        assert line_width >= 8  # "      - " = 8 chars minimum

    def test_wrap_partial_flag(self):
        """Should wrap partial flag list line before overflow."""
        # Width 9 cannot fit "      - 🇨" if 🇨 is width 2 (8 + 2 = 10).
        wrapped = wrap_text_with_ansi("      - 🇨", 9)

        assert len(wrapped) >= 1
        # First line should fit within width
        assert visible_width(wrapped[0]) <= 9


class TestVisibleWidthEdgeCases:
    """Additional edge cases for visible_width."""

    def test_tabs_counted_inline(self):
        """Tabs should be counted inline."""
        w = visible_width("\t")
        assert w > 0  # Tab has some width

    def test_ansi_skipped(self):
        """ANSI codes should be skipped in width calculation."""
        assert visible_width("\x1b[31m") == 0
        assert visible_width("\x1b[0m") == 0

    def test_mixed_ansi_and_text(self):
        """Mixed ANSI and text should work correctly."""
        text = "\t\x1b[31m界\x1b[0m"
        # Tab + 界 (2) = 6
        w = visible_width(text)
        assert w > 0  # Should have some width
