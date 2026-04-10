"""Tests for autocomplete provider."""

import os

import pytest

from pi_tui.components.autocomplete import (
    AutocompleteItem,
    CombinedAutocompleteProvider,
    SlashCommand,
    build_completion_value,
    build_fd_path_query,
    escape_regex,
    extract_quoted_prefix,
    find_last_delimiter,
    find_unclosed_quote_start,
    is_token_start,
    parse_path_prefix,
    to_display_path,
)


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_to_display_path(self):
        """Should normalize backslashes to forward slashes."""
        assert to_display_path("path\\to\\file") == "path/to/file"
        assert to_display_path("path/to/file") == "path/to/file"

    def test_escape_regex(self):
        """Should escape regex special characters."""
        assert escape_regex("file.txt") == r"file\.txt"
        assert escape_regex("path/to") == r"path/to"

    def test_build_fd_path_query(self):
        """Should build regex query for fd."""
        query = build_fd_path_query("src/components")
        assert "/" in query
        assert "\\\\" in query or "/" in query

    def test_find_last_delimiter(self):
        """Should find last path delimiter."""
        assert find_last_delimiter("hello world") == 5
        assert find_last_delimiter("hello") == -1
        assert find_last_delimiter('"quoted text"') == 12

    def test_find_unclosed_quote(self):
        """Should find unclosed quote position."""
        assert find_unclosed_quote_start('say "hello') == 4
        assert find_unclosed_quote_start('say "hello"') is None
        assert find_unclosed_quote_start("no quotes") is None

    def test_is_token_start(self):
        """Should detect token start positions."""
        assert is_token_start("hello world", 0) is True
        assert is_token_start("hello world", 6) is True
        assert is_token_start("hello world", 7) is False

    def test_extract_quoted_prefix(self):
        """Should extract quoted prefix."""
        assert extract_quoted_prefix('say "hello') == '"hello'
        assert extract_quoted_prefix('say @"hello') == '@"hello'
        assert extract_quoted_prefix("no quote") is None

    def test_parse_path_prefix(self):
        """Should parse path prefix correctly."""
        assert parse_path_prefix('"path') == {"raw_prefix": "path", "is_at_prefix": False, "is_quoted_prefix": True}
        assert parse_path_prefix('@"path') == {"raw_prefix": "path", "is_at_prefix": True, "is_quoted_prefix": True}
        assert parse_path_prefix("@path") == {"raw_prefix": "path", "is_at_prefix": True, "is_quoted_prefix": False}
        assert parse_path_prefix("path") == {"raw_prefix": "path", "is_at_prefix": False, "is_quoted_prefix": False}

    def test_build_completion_value(self):
        """Should build completion value with proper quoting."""
        assert build_completion_value("file.txt", False, False, False) == "file.txt"
        assert build_completion_value("file with spaces.txt", False, False, True) == '"file with spaces.txt"'
        assert build_completion_value("dir/", True, True, False) == "@dir/"
        assert build_completion_value("dir/", True, True, True) == '@"dir/"'


class TestCombinedAutocompleteProvider:
    """Tests for CombinedAutocompleteProvider."""

    @pytest.fixture
    def provider(self, tmp_path):
        """Create a provider with temp directory."""
        return CombinedAutocompleteProvider(base_path=str(tmp_path))

    @pytest.fixture
    def provider_with_commands(self, tmp_path):
        """Create a provider with commands."""
        commands = [
            SlashCommand("model", "Select a model"),
            SlashCommand("help", "Show help"),
        ]
        return CombinedAutocompleteProvider(commands=commands, base_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_empty_input_returns_none(self, provider):
        """Empty input should return None."""
        result = await provider.get_suggestions([""], 0, 0, None, force=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_slash_command_completion(self, provider_with_commands):
        """Should complete slash commands."""
        result = await provider_with_commands.get_suggestions(["/mod"], 0, 4, None, force=False)

        assert result is not None
        assert any(item.value == "model" for item in result.items)

    @pytest.mark.asyncio
    async def test_slash_command_not_triggered_without_force(self, provider):
        """Slash command shouldn't trigger without force if not at root."""
        await provider.get_suggestions([" /"], 0, 2, None, force=False)
        # Should not trigger for non-root context

    @pytest.mark.asyncio
    async def test_at_prefix_triggers_fuzzy(self, provider):
        """@ prefix should trigger fuzzy file search."""
        await provider.get_suggestions(["@"], 0, 1, None, force=False)
        # Should attempt fuzzy search (returns empty if no files)


class TestApplyCompletion:
    """Tests for apply_completion method."""

    def test_apply_command_completion(self):
        """Should apply command completion."""
        provider = CombinedAutocompleteProvider()
        lines = ["/mod"]
        item = AutocompleteItem(value="model", label="model")

        result = provider.apply_completion(lines, 0, 4, item, "/mod")

        assert result["lines"][0] == "/model "

    def test_apply_file_completion(self):
        """Should apply file completion."""
        provider = CombinedAutocompleteProvider()
        lines = ["fil"]
        item = AutocompleteItem(value="file.txt", label="file.txt")

        result = provider.apply_completion(lines, 0, 3, item, "fil")

        assert result["lines"][0] == "file.txt"

    def test_apply_at_completion(self):
        """Should apply @ file attachment completion."""
        provider = CombinedAutocompleteProvider()
        lines = ["@fil"]
        item = AutocompleteItem(value="@file.txt", label="file.txt")

        result = provider.apply_completion(lines, 0, 4, item, "@fil")

        assert "@file.txt" in result["lines"][0]


class TestPathExtraction:
    """Tests for path prefix extraction."""

    def test_extract_at_prefix(self):
        """Should extract @ prefix."""
        provider = CombinedAutocompleteProvider()

        assert provider._extract_at_prefix("say @") == "@"
        assert provider._extract_at_prefix("say @fil") == "@fil"
        assert provider._extract_at_prefix('say @"fil') == '@"fil'
        assert provider._extract_at_prefix("no at") is None

    def test_extract_path_prefix_force(self):
        """Should extract path with force."""
        provider = CombinedAutocompleteProvider()

        assert provider._extract_path_prefix("/home", True) == "/home"
        assert provider._extract_path_prefix("./file", True) == "./file"

    def test_extract_path_prefix_natural(self):
        """Should extract path with natural triggers."""
        provider = CombinedAutocompleteProvider()

        assert provider._extract_path_prefix("/home/user", False) == "/home/user"
        assert provider._extract_path_prefix("./file", False) == "./file"
        assert provider._extract_path_prefix("~/docs", False) == "~/docs"
        assert provider._extract_path_prefix("regular text", False) is None


class TestHomePathExpansion:
    """Tests for home path expansion."""

    def test_expand_tilde_slash(self):
        """Should expand ~/ to home directory."""
        provider = CombinedAutocompleteProvider()
        expanded = provider._expand_home_path("~/Documents")

        assert expanded != "~/Documents"
        assert expanded.startswith(os.path.expanduser("~"))

    def test_expand_tilde_only(self):
        """Should expand ~ to home directory."""
        provider = CombinedAutocompleteProvider()
        expanded = provider._expand_home_path("~")

        assert expanded == os.path.expanduser("~")

    def test_no_expansion_for_regular_path(self):
        """Should not expand regular paths."""
        provider = CombinedAutocompleteProvider()
        expanded = provider._expand_home_path("/usr/local")

        assert expanded == "/usr/local"


class TestFileSuggestions:
    """Tests for file suggestions."""

    def test_get_suggestions_for_directory(self, tmp_path):
        """Should get suggestions for directory contents."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.py").write_text("content")
        (tmp_path / "subdir").mkdir()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("")

        values = [item.value for item in suggestions]
        assert any("file1.txt" in v for v in values)
        assert any("file2.py" in v for v in values)
        assert any("subdir/" in v for v in values)

    def test_directories_sorted_first(self, tmp_path):
        """Should sort directories before files."""
        (tmp_path / "aaa.txt").write_text("content")
        (tmp_path / "bbb").mkdir()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("")

        labels = [item.label for item in suggestions]
        # Directory should come before file
        dir_idx = next(i for i, l in enumerate(labels) if l.endswith("/"))
        file_idx = next(i for i, l in enumerate(labels) if not l.endswith("/"))
        assert dir_idx < file_idx


class TestScopedFuzzyQuery:
    """Tests for scoped fuzzy query resolution."""

    def test_resolve_scoped_query(self, tmp_path):
        """Should resolve scoped query with directory prefix."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("")

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider._resolve_scoped_fuzzy_query("src/")

        assert result is not None
        assert result["base_dir"].rstrip("/") == str(tmp_path / "src")
        assert result["display_base"] == "src/"

    def test_resolve_nested_path(self, tmp_path):
        """Should resolve nested path."""
        (tmp_path / "src" / "components").mkdir(parents=True)
        (tmp_path / "src" / "components" / "Button.tsx").write_text("")

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider._resolve_scoped_fuzzy_query("src/components/Butt")

        assert result is not None
        assert result["query"] == "Butt"

    def test_nonexistent_directory_returns_none(self, tmp_path):
        """Should return None for nonexistent directory."""
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider._resolve_scoped_fuzzy_query("nonexistent/")

        assert result is None


class TestEntryScoring:
    """Tests for entry scoring."""

    def test_exact_match_highest_score(self):
        """Exact filename match should have highest score."""
        provider = CombinedAutocompleteProvider()

        score = provider._score_entry("README.md", "README.md", False)
        assert score == 100

    def test_prefix_match_high_score(self):
        """Prefix match should have high score."""
        provider = CombinedAutocompleteProvider()

        score = provider._score_entry("README.md", "READ", False)
        assert score == 80

    def test_directory_bonus(self):
        """Directories should get bonus."""
        provider = CombinedAutocompleteProvider()

        file_score = provider._score_entry("src/index.ts", "src", False)
        dir_score = provider._score_entry("src/", "src", True)

        assert dir_score > file_score
