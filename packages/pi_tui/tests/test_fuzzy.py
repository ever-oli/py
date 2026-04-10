"""Tests for fuzzy matching utilities."""

from pi_tui.fuzzy import fuzzy_filter, fuzzy_match


class TestFuzzyMatch:
    """Tests for fuzzy_match function."""

    def test_empty_query(self):
        """Empty query should match everything with score 0."""
        result = fuzzy_match("", "hello")
        assert result.matches is True
        assert result.score == 0

    def test_exact_match(self):
        """Exact match should have best score."""
        result = fuzzy_match("hello", "hello")
        assert result.matches is True
        # Exact match at start has negative score (lower is better)
        assert result.score < 0

    def test_prefix_match(self):
        """Prefix match should have good score."""
        result = fuzzy_match("hel", "hello")
        assert result.matches is True
        assert result.score < 0

    def test_substring_match(self):
        """Substring match should work."""
        result = fuzzy_match("ell", "hello")
        assert result.matches is True

    def test_no_match(self):
        """Non-matching query should return matches=False."""
        result = fuzzy_match("xyz", "hello")
        assert result.matches is False

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        result = fuzzy_match("HEL", "hello")
        assert result.matches is True

    def test_consecutive_bonus(self):
        """Consecutive character matches get bonus."""
        result1 = fuzzy_match("abc", "abc")
        result2 = fuzzy_match("abc", "aXbXc")
        assert result1.matches is True
        assert result2.matches is True
        # Consecutive match should have better (lower) score
        assert result1.score < result2.score

    def test_word_boundary_bonus(self):
        """Word boundary matches get bonus."""
        result = fuzzy_match("hw", "hello_world")
        assert result.matches is True
        # Score should reflect word boundary bonus

    def test_gap_penalty(self):
        """Gaps between matches get penalized."""
        result1 = fuzzy_match("ab", "ab")
        result2 = fuzzy_match("ab", "aXXXXXb")
        assert result1.score < result2.score  # More gaps = higher (worse) score

    def test_query_longer_than_text(self):
        """Query longer than text should not match."""
        result = fuzzy_match("hello", "hi")
        assert result.matches is False

    def test_letter_digit_swapping(self):
        """Should try swapping letters and digits."""
        result = fuzzy_match("abc123", "123abc")
        assert result.matches is True


class TestFuzzyFilter:
    """Tests for fuzzy_filter function."""

    def test_empty_query_returns_all(self):
        """Empty query should return all items."""
        items = ["apple", "banana", "cherry"]
        result = fuzzy_filter(items, "", lambda x: x)
        assert len(result) == 3

    def test_filters_items(self):
        """Should filter items based on query."""
        items = ["apple", "banana", "cherry"]
        result = fuzzy_filter(items, "a", lambda x: x)
        # apple and banana contain 'a', cherry doesn't
        assert len(result) == 2
        assert "apple" in result
        assert "banana" in result

    def test_excludes_non_matches(self):
        """Should exclude non-matching items."""
        items = ["apple", "banana", "cherry"]
        result = fuzzy_filter(items, "z", lambda x: x)
        assert len(result) == 0

    def test_sorts_by_score(self):
        """Should sort by match quality."""
        items = ["zzhello", "hello", "hezzllo"]
        result = fuzzy_filter(items, "hello", lambda x: x)
        # Exact match should be first
        assert result[0] == "hello"

    def test_get_text_function(self):
        """Should use get_text function to extract text."""
        items = [
            {"name": "apple", "value": 1},
            {"name": "banana", "value": 2},
        ]
        result = fuzzy_filter(items, "app", lambda x: x["name"])
        assert len(result) == 1
        assert result[0]["name"] == "apple"

    def test_space_separated_tokens(self):
        """Should handle space-separated tokens."""
        items = ["hello world", "hello", "world", "foo bar"]
        result = fuzzy_filter(items, "hello world", lambda x: x)
        # All tokens must match
        assert "hello world" in result

    def test_does_not_modify_original(self):
        """Should not modify original list."""
        items = ["apple", "banana"]
        original = items.copy()
        fuzzy_filter(items, "a", lambda x: x)
        assert items == original
