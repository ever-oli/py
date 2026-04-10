"""Keybindings management for TUI applications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .keys import KeyId, matches_key

# Keybinding identifiers
Keybinding = str


@dataclass
class KeybindingDefinition:
    """Definition of a keybinding."""

    default_keys: KeyId | list[KeyId]
    description: str | None = None


# Type aliases
KeybindingDefinitions = dict[Keybinding, KeybindingDefinition]
KeybindingsConfig = dict[str, Union[KeyId, list[KeyId], None]]


# Default TUI keybindings
TUI_KEYBINDINGS: KeybindingDefinitions = {
    # Editor navigation
    "tui.editor.cursorUp": KeybindingDefinition(default_keys="up", description="Move cursor up"),
    "tui.editor.cursorDown": KeybindingDefinition(default_keys="down", description="Move cursor down"),
    "tui.editor.cursorLeft": KeybindingDefinition(default_keys=["left", "ctrl+b"], description="Move cursor left"),
    "tui.editor.cursorRight": KeybindingDefinition(default_keys=["right", "ctrl+f"], description="Move cursor right"),
    "tui.editor.cursorWordLeft": KeybindingDefinition(
        default_keys=["alt+left", "ctrl+left", "alt+b"], description="Move cursor word left"
    ),
    "tui.editor.cursorWordRight": KeybindingDefinition(
        default_keys=["alt+right", "ctrl+right", "alt+f"], description="Move cursor word right"
    ),
    "tui.editor.cursorLineStart": KeybindingDefinition(
        default_keys=["home", "ctrl+a"], description="Move to line start"
    ),
    "tui.editor.cursorLineEnd": KeybindingDefinition(default_keys=["end", "ctrl+e"], description="Move to line end"),
    "tui.editor.jumpForward": KeybindingDefinition(default_keys="ctrl+]", description="Jump forward to character"),
    "tui.editor.jumpBackward": KeybindingDefinition(
        default_keys="ctrl+alt+]", description="Jump backward to character"
    ),
    "tui.editor.pageUp": KeybindingDefinition(default_keys="pageUp", description="Page up"),
    "tui.editor.pageDown": KeybindingDefinition(default_keys="pageDown", description="Page down"),
    "tui.editor.deleteCharBackward": KeybindingDefinition(
        default_keys="backspace", description="Delete character backward"
    ),
    "tui.editor.deleteCharForward": KeybindingDefinition(
        default_keys=["delete", "ctrl+d"], description="Delete character forward"
    ),
    "tui.editor.deleteWordBackward": KeybindingDefinition(
        default_keys=["ctrl+w", "alt+backspace"], description="Delete word backward"
    ),
    "tui.editor.deleteWordForward": KeybindingDefinition(
        default_keys=["alt+d", "alt+delete"], description="Delete word forward"
    ),
    "tui.editor.deleteToLineStart": KeybindingDefinition(default_keys="ctrl+u", description="Delete to line start"),
    "tui.editor.deleteToLineEnd": KeybindingDefinition(default_keys="ctrl+k", description="Delete to line end"),
    "tui.editor.yank": KeybindingDefinition(default_keys="ctrl+y", description="Yank"),
    "tui.editor.yankPop": KeybindingDefinition(default_keys="alt+y", description="Yank pop"),
    "tui.editor.undo": KeybindingDefinition(default_keys="ctrl+-", description="Undo"),
    # Generic input
    "tui.input.newLine": KeybindingDefinition(default_keys="shift+enter", description="Insert newline"),
    "tui.input.submit": KeybindingDefinition(default_keys="enter", description="Submit input"),
    "tui.input.tab": KeybindingDefinition(default_keys="tab", description="Tab / autocomplete"),
    "tui.input.copy": KeybindingDefinition(default_keys="ctrl+c", description="Copy selection"),
    # Selection
    "tui.select.up": KeybindingDefinition(default_keys="up", description="Move selection up"),
    "tui.select.down": KeybindingDefinition(default_keys="down", description="Move selection down"),
    "tui.select.pageUp": KeybindingDefinition(default_keys="pageUp", description="Selection page up"),
    "tui.select.pageDown": KeybindingDefinition(default_keys="pageDown", description="Selection page down"),
    "tui.select.confirm": KeybindingDefinition(default_keys="enter", description="Confirm selection"),
    "tui.select.cancel": KeybindingDefinition(default_keys=["escape", "ctrl+c"], description="Cancel selection"),
}


@dataclass
class KeybindingConflict:
    """Represents a conflict between keybindings."""

    key: KeyId
    keybindings: list[str]


def normalize_keys(keys: KeyId | list[KeyId] | None) -> list[KeyId]:
    """Normalize keys to a list."""
    if keys is None:
        return []
    if isinstance(keys, str):
        return [keys]
    return list(keys)


class KeybindingsManager:
    """Manages keybindings and resolves conflicts."""

    def __init__(
        self,
        definitions: KeybindingDefinitions | None = None,
        user_bindings: KeybindingsConfig | None = None,
    ):
        """Initialize the keybindings manager.

        Args:
            definitions: Keybinding definitions
            user_bindings: User-defined keybindings (overrides defaults)
        """
        self._definitions = definitions or TUI_KEYBINDINGS
        self._user_bindings = user_bindings or {}
        self._keys_by_id: dict[Keybinding, list[KeyId]] = {}
        self._conflicts: list[KeybindingConflict] = []
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild internal state from definitions and user bindings."""
        self._keys_by_id.clear()
        self._conflicts = []

        # Check for user-defined conflicts
        user_claims: dict[KeyId, set[Keybinding]] = {}
        for keybinding, keys in self._user_bindings.items():
            if keybinding not in self._definitions:
                continue
            for key in normalize_keys(keys):
                claimants = user_claims.get(key, set())
                claimants.add(keybinding)
                user_claims[key] = claimants

        for key, keybindings in user_claims.items():
            if len(keybindings) > 1:
                self._conflicts.append(
                    KeybindingConflict(
                        key=key,
                        keybindings=list(keybindings),
                    )
                )

        # Build keys_by_id
        for keybinding, definition in self._definitions.items():
            user_keys = self._user_bindings.get(keybinding)
            keys = normalize_keys(definition.default_keys) if user_keys is None else normalize_keys(user_keys)
            self._keys_by_id[keybinding] = keys

    def matches(self, data: str, keybinding: Keybinding) -> bool:
        """Check if input data matches a keybinding.

        Args:
            data: Raw input data from terminal
            keybinding: Keybinding identifier

        Returns:
            True if data matches the keybinding
        """
        keys = self._keys_by_id.get(keybinding, [])
        return any(matches_key(data, key) for key in keys)

    def get_keys(self, keybinding: Keybinding) -> list[KeyId]:
        """Get the keys bound to a keybinding."""
        return list(self._keys_by_id.get(keybinding, []))

    def get_definition(self, keybinding: Keybinding) -> KeybindingDefinition | None:
        """Get the definition for a keybinding."""
        return self._definitions.get(keybinding)

    def get_conflicts(self) -> list[KeybindingConflict]:
        """Get all keybinding conflicts."""
        return [
            KeybindingConflict(
                key=c.key,
                keybindings=list(c.keybindings),
            )
            for c in self._conflicts
        ]

    def set_user_bindings(self, user_bindings: KeybindingsConfig) -> None:
        """Set user-defined keybindings."""
        self._user_bindings = dict(user_bindings)
        self._rebuild()

    def get_user_bindings(self) -> KeybindingsConfig:
        """Get user-defined keybindings."""
        return dict(self._user_bindings)

    def get_resolved_bindings(self) -> KeybindingsConfig:
        """Get all resolved bindings (user + defaults)."""
        resolved: KeybindingsConfig = {}
        for keybinding in self._definitions:
            keys = self._keys_by_id.get(keybinding, [])
            if len(keys) == 1:
                resolved[keybinding] = keys[0]
            elif keys:
                resolved[keybinding] = keys
        return resolved

    def bind(self, keybinding: Keybinding, keys: KeyId | list[KeyId]) -> None:
        """Bind keys to a keybinding."""
        self._user_bindings[keybinding] = keys
        self._rebuild()

    def unbind(self, keybinding: Keybinding) -> None:
        """Remove user binding for a keybinding (revert to default)."""
        if keybinding in self._user_bindings:
            del self._user_bindings[keybinding]
            self._rebuild()


# Global keybindings instance
_global_keybindings: KeybindingsManager | None = None


def get_keybindings() -> KeybindingsManager:
    """Get the global keybindings manager."""
    global _global_keybindings
    if _global_keybindings is None:
        _global_keybindings = KeybindingsManager(TUI_KEYBINDINGS)
    return _global_keybindings


def set_keybindings(keybindings: KeybindingsManager) -> None:
    """Set the global keybindings manager."""
    global _global_keybindings
    _global_keybindings = keybindings
