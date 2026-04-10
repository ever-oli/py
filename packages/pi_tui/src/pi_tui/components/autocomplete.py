"""Autocomplete provider for file paths and slash commands.

This is a Python port of the TypeScript CombinedAutocompleteProvider,
providing fuzzy file search using fd and path completion.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from ..fuzzy import fuzzy_filter

# Characters that delimit path tokens
PATH_DELIMITERS = set(" \t\"'=")


def to_display_path(value: str) -> str:
    """Normalize path for display."""
    return value.replace("\\", "/")


def escape_regex(value: str) -> str:
    """Escape regex special characters."""
    return re.escape(value)


def build_fd_path_query(query: str) -> str:
    """Build a regex query for fd based on path."""
    normalized = to_display_path(query)
    if "/" not in normalized:
        return normalized

    has_trailing_separator = normalized.endswith("/")
    trimmed = normalized.strip("/")
    if not trimmed:
        return normalized

    separator_pattern = "[\\\\/]"
    segments = [escape_regex(s) for s in trimmed.split("/") if s]
    if not segments:
        return normalized

    pattern = separator_pattern.join(segments)
    if has_trailing_separator:
        pattern += separator_pattern
    return pattern


def find_last_delimiter(text: str) -> int:
    """Find position of last path delimiter."""
    for i in range(len(text) - 1, -1, -1):
        if text[i] in PATH_DELIMITERS:
            return i
    return -1


def find_unclosed_quote_start(text: str) -> int | None:
    """Find position of unclosed quote."""
    in_quotes = False
    quote_start = -1

    for i, char in enumerate(text):
        if char == '"':
            in_quotes = not in_quotes
            if in_quotes:
                quote_start = i

    return quote_start if in_quotes else None


def is_token_start(text: str, index: int) -> bool:
    """Check if position is at the start of a token."""
    return index == 0 or text[index - 1] in PATH_DELIMITERS


def extract_quoted_prefix(text: str) -> str | None:
    """Extract quoted prefix if inside quotes."""
    quote_start = find_unclosed_quote_start(text)
    if quote_start is None:
        return None

    if quote_start > 0 and text[quote_start - 1] == "@":
        if not is_token_start(text, quote_start - 1):
            return None
        return text[quote_start - 1 :]

    if not is_token_start(text, quote_start):
        return None

    return text[quote_start:]


def parse_path_prefix(prefix: str) -> dict[str, Any]:
    """Parse a path prefix to extract components."""
    if prefix.startswith('@"'):
        return {"raw_prefix": prefix[2:], "is_at_prefix": True, "is_quoted_prefix": True}
    if prefix.startswith('"'):
        return {"raw_prefix": prefix[1:], "is_at_prefix": False, "is_quoted_prefix": True}
    if prefix.startswith("@"):
        return {"raw_prefix": prefix[1:], "is_at_prefix": True, "is_quoted_prefix": False}
    return {"raw_prefix": prefix, "is_at_prefix": False, "is_quoted_prefix": False}


def build_completion_value(path: str, is_directory: bool, is_at_prefix: bool, is_quoted_prefix: bool) -> str:
    """Build the completion value with appropriate quoting."""
    needs_quotes = is_quoted_prefix or " " in path
    prefix = "@" if is_at_prefix else ""

    if not needs_quotes and not is_at_prefix:
        return f"{path}"

    if needs_quotes:
        open_quote = f'{prefix}"'
        close_quote = '"'
        return f"{open_quote}{path}{close_quote}"

    return f"{prefix}{path}"


@dataclass
class AutocompleteItem:
    """An autocomplete suggestion item."""

    value: str
    label: str
    description: str | None = None


@dataclass
class SlashCommand:
    """A slash command with optional argument completions."""

    name: str
    description: str | None = None
    get_argument_completions: Callable[[str], list[AutocompleteItem]] | None = None


@dataclass
class AutocompleteSuggestions:
    """Autocomplete suggestions result."""

    items: list[AutocompleteItem]
    prefix: str  # What we're matching against


class CombinedAutocompleteProvider:
    """Combined provider that handles both slash commands and file paths."""

    def __init__(self, commands: list[Any] | None = None, base_path: str | None = None, fd_path: str | None = None):
        """Initialize the autocomplete provider.

        Args:
            commands: List of SlashCommand or AutocompleteItem
            base_path: Base directory for file completion
            fd_path: Path to fd executable for fuzzy search
        """
        self.commands = commands or []
        self.base_path = base_path or os.getcwd()
        self.fd_path = fd_path

    async def get_suggestions(
        self,
        lines: list[str],
        cursor_line: int,
        cursor_col: int,
        signal: Any,  # AbortSignal equivalent
        force: bool = False,
    ) -> AutocompleteSuggestions | None:
        """Get autocomplete suggestions for current text/cursor position.

        Args:
            lines: Current text lines
            cursor_line: Line containing cursor
            cursor_col: Cursor column position
            signal: Abort signal for cancellation
            force: Force completion even without trigger characters

        Returns:
            Suggestions or None if no suggestions available
        """
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        text_before_cursor = current_line[:cursor_col]

        # Check for @ prefix (fuzzy file search)
        at_prefix = self._extract_at_prefix(text_before_cursor)
        if at_prefix:
            parsed = parse_path_prefix(at_prefix)
            suggestions = await self._get_fuzzy_file_suggestions(
                parsed["raw_prefix"], parsed["is_quoted_prefix"], signal
            )
            if suggestions:
                return AutocompleteSuggestions(items=suggestions, prefix=at_prefix)
            return None

        # Check for slash commands
        if not force and text_before_cursor.startswith("/"):
            space_index = text_before_cursor.find(" ")

            if space_index == -1:
                # Command name completion
                prefix = text_before_cursor[1:]
                command_items = []
                for cmd in self.commands:
                    if hasattr(cmd, "name"):
                        command_items.append({"name": cmd.name, "label": cmd.name, "description": cmd.description})
                    else:
                        command_items.append({"name": cmd.value, "label": cmd.label, "description": cmd.description})

                filtered = fuzzy_filter(command_items, prefix, lambda x: x["name"])
                items = [
                    AutocompleteItem(value=item["name"], label=item["label"], description=item.get("description"))
                    for item in filtered
                ]

                if not items:
                    return None

                return AutocompleteSuggestions(items=items, prefix=text_before_cursor)

            # Command argument completion
            command_name = text_before_cursor[1:space_index]
            argument_text = text_before_cursor[space_index + 1 :]

            command = None
            for cmd in self.commands:
                name = cmd.name if hasattr(cmd, "name") else cmd.value
                if name == command_name:
                    command = cmd
                    break

            if not command or not hasattr(command, "get_argument_completions") or not command.get_argument_completions:
                return None

            argument_suggestions = command.get_argument_completions(argument_text)
            if not argument_suggestions:
                return None

            return AutocompleteSuggestions(items=argument_suggestions, prefix=argument_text)

        # Check for path completion
        path_match = self._extract_path_prefix(text_before_cursor, force)
        if path_match is None:
            return None

        suggestions = self._get_file_suggestions(path_match)
        if not suggestions:
            return None

        return AutocompleteSuggestions(items=suggestions, prefix=path_match)

    def apply_completion(
        self, lines: list[str], cursor_line: int, cursor_col: int, item: AutocompleteItem, prefix: str
    ) -> dict[str, Any]:
        """Apply the selected completion item.

        Args:
            lines: Current text lines
            cursor_line: Line containing cursor
            cursor_col: Cursor column position
            item: Selected completion item
            prefix: Current prefix being completed

        Returns:
            Dict with new lines and cursor position
        """
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        before_prefix = current_line[: cursor_col - len(prefix)]
        after_cursor = current_line[cursor_col:]

        is_quoted_prefix = prefix.startswith('"') or prefix.startswith('@"')
        has_leading_quote_after_cursor = after_cursor.startswith('"')
        has_trailing_quote_in_item = item.value.endswith('"')

        adjusted_after_cursor = ""
        if is_quoted_prefix and has_trailing_quote_in_item and has_leading_quote_after_cursor:
            adjusted_after_cursor = after_cursor[1:]
        else:
            adjusted_after_cursor = after_cursor

        # Check if completing slash command
        is_slash_command = prefix.startswith("/") and before_prefix.strip() == "" and "/" not in prefix[1:]

        if is_slash_command:
            # Command name completion
            new_line = f"{before_prefix}/{item.value} {adjusted_after_cursor}"
            new_lines = list(lines)
            new_lines[cursor_line] = new_line

            return {
                "lines": new_lines,
                "cursor_line": cursor_line,
                "cursor_col": len(before_prefix) + len(item.value) + 2,  # +2 for "/" and space
            }

        # Check if completing file attachment (@)
        if prefix.startswith("@"):
            is_directory = item.label.endswith("/")
            suffix = "" if is_directory else " "
            new_line = f"{before_prefix}{item.value}{suffix}{adjusted_after_cursor}"
            new_lines = list(lines)
            new_lines[cursor_line] = new_line

            has_trailing_quote = item.value.endswith('"')
            cursor_offset = len(item.value) - 1 if is_directory and has_trailing_quote else len(item.value)

            return {
                "lines": new_lines,
                "cursor_line": cursor_line,
                "cursor_col": len(before_prefix) + cursor_offset + len(suffix),
            }

        # File path completion
        is_directory = item.label.endswith("/")
        has_trailing_quote = item.value.endswith('"')
        cursor_offset = len(item.value) - 1 if is_directory and has_trailing_quote else len(item.value)

        new_line = before_prefix + item.value + adjusted_after_cursor
        new_lines = list(lines)
        new_lines[cursor_line] = new_line

        return {"lines": new_lines, "cursor_line": cursor_line, "cursor_col": len(before_prefix) + cursor_offset}

    def _extract_at_prefix(self, text: str) -> str | None:
        """Extract @ prefix for fuzzy file suggestions."""
        quoted_prefix = extract_quoted_prefix(text)
        if quoted_prefix and quoted_prefix.startswith('@"'):
            return quoted_prefix

        last_delimiter_index = find_last_delimiter(text)
        token_start = 0 if last_delimiter_index == -1 else last_delimiter_index + 1

        if token_start < len(text) and text[token_start] == "@":
            return text[token_start:]

        return None

    def _extract_path_prefix(self, text: str, force_extract: bool = False) -> str | None:
        """Extract a path-like prefix from the text before cursor."""
        quoted_prefix = extract_quoted_prefix(text)
        if quoted_prefix:
            return quoted_prefix

        last_delimiter_index = find_last_delimiter(text)
        path_prefix = text if last_delimiter_index == -1 else text[last_delimiter_index + 1 :]

        if force_extract:
            return path_prefix

        # For natural triggers, return if it looks like a path
        if "/" in path_prefix or path_prefix.startswith(".") or path_prefix.startswith("~/"):
            return path_prefix

        # Return empty string only after a space
        if path_prefix == "" and text.endswith(" "):
            return path_prefix

        return None

    def _expand_home_path(self, path: str) -> str:
        """Expand home directory (~/) to actual home path."""
        if path.startswith("~/"):
            expanded = os.path.expanduser(path)
            if path.endswith("/") and not expanded.endswith("/"):
                expanded += "/"
            return expanded
        elif path == "~":
            return os.path.expanduser("~")
        return path

    def _resolve_scoped_fuzzy_query(self, raw_query: str) -> dict[str, Any] | None:
        """Resolve a scoped fuzzy query (e.g., 'src/')."""
        normalized_query = to_display_path(raw_query)
        slash_index = normalized_query.rfind("/")
        if slash_index == -1:
            return None

        display_base = normalized_query[: slash_index + 1]
        query = normalized_query[slash_index + 1 :]

        if display_base.startswith("~/"):
            base_dir = self._expand_home_path(display_base)
        elif display_base.startswith("/"):
            base_dir = display_base
        else:
            base_dir = os.path.join(self.base_path, display_base)

        try:
            if not os.path.isdir(base_dir):
                return None
        except OSError:
            return None

        return {"base_dir": base_dir, "query": query, "display_base": display_base}

    def _scoped_path_for_display(self, display_base: str, relative_path: str) -> str:
        """Convert a scoped path to display format."""
        normalized_relative = to_display_path(relative_path)
        if display_base == "/":
            return f"/{normalized_relative}"
        return f"{to_display_path(display_base)}{normalized_relative}"

    def _get_file_suggestions(self, prefix: str) -> list[AutocompleteItem]:
        """Get file/directory suggestions for a given path prefix."""
        try:
            parsed = parse_path_prefix(prefix)
            raw_prefix = parsed["raw_prefix"]
            is_at_prefix = parsed["is_at_prefix"]
            is_quoted_prefix = parsed["is_quoted_prefix"]

            expanded_prefix = self._expand_home_path(raw_prefix)

            # Determine search directory
            is_root_prefix = (
                raw_prefix == ""
                or raw_prefix == "./"
                or raw_prefix == "../"
                or raw_prefix == "~"
                or raw_prefix == "~/"
                or raw_prefix == "/"
                or (is_at_prefix and raw_prefix == "")
            )

            if is_root_prefix or raw_prefix.endswith("/"):
                if raw_prefix.startswith("~") or expanded_prefix.startswith("/"):
                    search_dir = expanded_prefix
                else:
                    search_dir = os.path.join(self.base_path, expanded_prefix)
                search_prefix = ""
            else:
                search_dir = os.path.dirname(expanded_prefix)
                if search_dir == "":
                    search_dir = "."
                search_prefix = os.path.basename(expanded_prefix)

                if raw_prefix.startswith("~") or expanded_prefix.startswith("/"):
                    pass  # search_dir is already absolute
                else:
                    search_dir = os.path.join(self.base_path, search_dir)

            entries = os.listdir(search_dir)
            suggestions: list[AutocompleteItem] = []

            for entry_name in entries:
                if not entry_name.lower().startswith(search_prefix.lower()):
                    continue

                full_path = os.path.join(search_dir, entry_name)
                try:
                    is_directory = os.path.isdir(full_path)
                except OSError:
                    is_directory = False

                # Build relative path
                if raw_prefix.endswith("/"):
                    relative_path = raw_prefix + entry_name
                elif "/" in raw_prefix or "\\" in raw_prefix:
                    if raw_prefix.startswith("~/"):
                        home_relative = raw_prefix[2:]
                        dir_part = os.path.dirname(home_relative)
                        if dir_part == "." or dir_part == "":
                            relative_path = f"~/{entry_name}"
                        else:
                            relative_path = f"~/{dir_part}/{entry_name}"
                    elif raw_prefix.startswith("/"):
                        dir_part = os.path.dirname(raw_prefix)
                        relative_path = f"/{entry_name}" if dir_part == "/" else f"{dir_part}/{entry_name}"
                    else:
                        dir_part = os.path.dirname(raw_prefix)
                        relative_path = entry_name if dir_part == "." or dir_part == "" else f"{dir_part}/{entry_name}"
                        if raw_prefix.startswith("./") and not relative_path.startswith("./"):
                            relative_path = f"./{relative_path}"
                else:
                    relative_path = f"~/{entry_name}" if raw_prefix.startswith("~") else entry_name

                relative_path = to_display_path(relative_path)
                path_value = f"{relative_path}/" if is_directory else relative_path
                value = build_completion_value(path_value, is_directory, is_at_prefix, is_quoted_prefix)

                suggestions.append(
                    AutocompleteItem(value=value, label=f"{entry_name}/" if is_directory else entry_name)
                )

            # Sort directories first, then alphabetically
            suggestions.sort(key=lambda x: (not x.label.endswith("/"), x.label.lower()))

            return suggestions
        except OSError:
            return []

    def _score_entry(self, file_path: str, query: str, is_directory: bool) -> int:
        """Score an entry against the query (higher = better match)."""
        file_name = os.path.basename(file_path)
        lower_file_name = file_name.lower()
        lower_query = query.lower()

        score = 0

        # Exact filename match (highest)
        if lower_file_name == lower_query:
            score = 100
        # Filename starts with query
        elif lower_file_name.startswith(lower_query):
            score = 80
        # Substring match in filename
        elif lower_query in lower_file_name:
            score = 50
        # Substring match in full path
        elif lower_query in file_path.lower():
            score = 30

        # Directories get a bonus
        if is_directory and score > 0:
            score += 10

        return score

    async def _get_fuzzy_file_suggestions(
        self, query: str, is_quoted_prefix: bool, signal: Any
    ) -> list[AutocompleteItem]:
        """Fuzzy file search using fd (fast, respects .gitignore)."""
        if not self.fd_path:
            return []

        try:
            scoped_query = self._resolve_scoped_fuzzy_query(query)
            fd_base_dir = scoped_query["base_dir"] if scoped_query else self.base_path
            fd_query = scoped_query["query"] if scoped_query else query

            args = [
                self.fd_path,
                "--base-directory",
                fd_base_dir,
                "--max-results",
                "100",
                "--type",
                "f",
                "--type",
                "d",
                "--full-path",
                "--hidden",
                "--exclude",
                ".git",
                "--exclude",
                ".git/*",
                "--exclude",
                ".git/**",
            ]

            if fd_query:
                args.append(build_fd_path_query(fd_query))

            # Run fd process
            result = subprocess.run(args, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                return []

            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            entries = []

            for line in lines:
                display_line = to_display_path(line)
                has_trailing = display_line.endswith("/")
                normalized = display_line[:-1] if has_trailing else display_line

                # Skip .git
                if normalized == ".git" or normalized.startswith(".git/") or "/.git/" in normalized:
                    continue

                entries.append({"path": display_line, "is_directory": has_trailing})

            # Score entries
            scored = []
            for entry in entries:
                score = self._score_entry(entry["path"], fd_query, entry["is_directory"]) if fd_query else 1
                if score > 0:
                    scored.append({**entry, "score": score})

            scored.sort(key=lambda x: -x["score"])
            top_entries = scored[:20]

            suggestions = []
            for entry in top_entries:
                path_without_slash = entry["path"][:-1] if entry["is_directory"] else entry["path"]
                display_path = (
                    self._scoped_path_for_display(scoped_query["display_base"], path_without_slash)
                    if scoped_query
                    else path_without_slash
                )
                entry_name = os.path.basename(path_without_slash)
                completion_path = f"{display_path}/" if entry["is_directory"] else display_path
                value = build_completion_value(completion_path, entry["is_directory"], True, is_quoted_prefix)

                suggestions.append(
                    AutocompleteItem(
                        value=value,
                        label=f"{entry_name}/" if entry["is_directory"] else entry_name,
                        description=display_path,
                    )
                )

            return suggestions
        except Exception:
            return []

    def should_trigger_file_completion(self, lines: list[str], cursor_line: int, cursor_col: int) -> bool:
        """Check if we should trigger file completion."""
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        text_before_cursor = current_line[:cursor_col]

        # Don't trigger if typing a slash command at start of line
        return not (text_before_cursor.strip().startswith("/") and " " not in text_before_cursor.strip())
