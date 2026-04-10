"""Keyboard input handling for terminal applications.

Supports both legacy terminal sequences and Kitty keyboard protocol.
See: https://sw.kovidgoyal.net/kitty/keyboard-protocol/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Global Kitty Protocol State
# =============================================================================

_kitty_protocol_active = False


def set_kitty_protocol_active(active: bool) -> None:
    """Set the global Kitty keyboard protocol state."""
    global _kitty_protocol_active
    _kitty_protocol_active = active


def is_kitty_protocol_active() -> bool:
    """Query whether Kitty keyboard protocol is currently active."""
    return _kitty_protocol_active


# =============================================================================
# Key Event Type
# =============================================================================


class KeyEventType(Enum):
    """Event types from Kitty keyboard protocol."""

    PRESS = "press"
    REPEAT = "repeat"
    RELEASE = "release"


# =============================================================================
# Type-safe Key Identifiers
# =============================================================================

# KeyId is a string representing a key with optional modifiers
KeyId = str


class Key:
    """Helper object for creating typed key identifiers with autocomplete."""

    # Special keys
    ESCAPE = "escape"
    ESC = "esc"
    ENTER = "enter"
    RETURN = "return"
    TAB = "tab"
    SPACE = "space"
    BACKSPACE = "backspace"
    DELETE = "delete"
    INSERT = "insert"
    CLEAR = "clear"
    HOME = "home"
    END = "end"
    PAGEUP = "pageUp"
    PAGEDOWN = "pageDown"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"

    # Symbol keys
    BACKTICK = "`"
    HYPHEN = "-"
    EQUALS = "="
    LEFTBRACKET = "["
    RIGHTBRACKET = "]"
    BACKSLASH = "\\"
    SEMICOLON = ";"
    QUOTE = "'"
    COMMA = ","
    PERIOD = "."
    SLASH = "/"
    EXCLAMATION = "!"
    AT = "@"
    HASH = "#"
    DOLLAR = "$"
    PERCENT = "%"
    CARET = "^"
    AMPERSAND = "&"
    ASTERISK = "*"
    LEFTPAREN = "("
    RIGHTPAREN = ")"
    UNDERSCORE = "_"
    PLUS = "+"
    PIPE = "|"
    TILDE = "~"
    LEFTBRACE = "{"
    RIGHTBRACE = "}"
    COLON = ":"
    LESSTHAN = "<"
    GREATERTHAN = ">"
    QUESTION = "?"

    @staticmethod
    def ctrl(key: str) -> KeyId:
        """Create a ctrl+key identifier."""
        return f"ctrl+{key}"

    @staticmethod
    def shift(key: str) -> KeyId:
        """Create a shift+key identifier."""
        return f"shift+{key}"

    @staticmethod
    def alt(key: str) -> KeyId:
        """Create an alt+key identifier."""
        return f"alt+{key}"

    @staticmethod
    def ctrl_shift(key: str) -> KeyId:
        """Create a ctrl+shift+key identifier."""
        return f"ctrl+shift+{key}"

    @staticmethod
    def ctrl_alt(key: str) -> KeyId:
        """Create a ctrl+alt+key identifier."""
        return f"ctrl+alt+{key}"

    @staticmethod
    def shift_alt(key: str) -> KeyId:
        """Create a shift+alt+key identifier."""
        return f"shift+alt+{key}"

    @staticmethod
    def ctrl_shift_alt(key: str) -> KeyId:
        """Create a ctrl+shift+alt+key identifier."""
        return f"ctrl+shift+alt+{key}"


# =============================================================================
# Constants
# =============================================================================

SYMBOL_KEYS = frozenset(
    [
        "`",
        "-",
        "=",
        "[",
        "]",
        "\\",
        ";",
        "'",
        ",",
        ".",
        "/",
        "!",
        "@",
        "#",
        "$",
        "%",
        "^",
        "&",
        "*",
        "(",
        ")",
        "_",
        "+",
        "|",
        "~",
        "{",
        "}",
        ":",
        "<",
        ">",
        "?",
    ]
)

# Modifier bitmasks
MODIFIERS = {
    "shift": 1,
    "alt": 2,
    "ctrl": 4,
}

LOCK_MASK = 64 + 128  # Caps Lock + Num Lock

# Special codepoints
CODEPOINTS = {
    "escape": 27,
    "tab": 9,
    "enter": 13,
    "space": 32,
    "backspace": 127,
    "kp_enter": 57414,
}

# Arrow key codepoints (negative for identification)
ARROW_CODEPOINTS = {
    "up": -1,
    "down": -2,
    "right": -3,
    "left": -4,
}

# Functional key codepoints
FUNCTIONAL_CODEPOINTS = {
    "delete": -10,
    "insert": -11,
    "pageUp": -12,
    "pageDown": -13,
    "home": -14,
    "end": -15,
}

# Kitty functional key equivalents
KITTY_FUNCTIONAL_KEY_EQUIVALENTS = {
    57399: 48,  # KP_0 -> 0
    57400: 49,  # KP_1 -> 1
    57401: 50,  # KP_2 -> 2
    57402: 51,  # KP_3 -> 3
    57403: 52,  # KP_4 -> 4
    57404: 53,  # KP_5 -> 5
    57405: 54,  # KP_6 -> 6
    57406: 55,  # KP_7 -> 7
    57407: 56,  # KP_8 -> 8
    57408: 57,  # KP_9 -> 9
    57409: 46,  # KP_DECIMAL -> .
    57410: 47,  # KP_DIVIDE -> /
    57411: 42,  # KP_MULTIPLY -> *
    57412: 45,  # KP_SUBTRACT -> -
    57413: 43,  # KP_ADD -> +
    57415: 61,  # KP_EQUAL -> =
    57416: 44,  # KP_SEPARATOR -> ,
    57417: ARROW_CODEPOINTS["left"],
    57418: ARROW_CODEPOINTS["right"],
    57419: ARROW_CODEPOINTS["up"],
    57420: ARROW_CODEPOINTS["down"],
    57421: FUNCTIONAL_CODEPOINTS["pageUp"],
    57422: FUNCTIONAL_CODEPOINTS["pageDown"],
    57423: FUNCTIONAL_CODEPOINTS["home"],
    57424: FUNCTIONAL_CODEPOINTS["end"],
    57425: FUNCTIONAL_CODEPOINTS["insert"],
    57426: FUNCTIONAL_CODEPOINTS["delete"],
}


def normalize_kitty_codepoint(codepoint: int) -> int:
    """Normalize Kitty functional key codepoint."""
    return KITTY_FUNCTIONAL_KEY_EQUIVALENTS.get(codepoint, codepoint)


# Legacy key sequences
LEGACY_KEY_SEQUENCES = {
    "up": ["\x1b[A", "\x1bOA"],
    "down": ["\x1b[B", "\x1bOB"],
    "right": ["\x1b[C", "\x1bOC"],
    "left": ["\x1b[D", "\x1bOD"],
    "home": ["\x1b[H", "\x1bOH", "\x1b[1~", "\x1b[7~"],
    "end": ["\x1b[F", "\x1bOF", "\x1b[4~", "\x1b[8~"],
    "insert": ["\x1b[2~"],
    "delete": ["\x1b[3~"],
    "pageUp": ["\x1b[5~", "\x1b[[5~"],
    "pageDown": ["\x1b[6~", "\x1b[[6~"],
    "clear": ["\x1b[E", "\x1bOE"],
    "f1": ["\x1bOP", "\x1b[11~", "\x1b[[A"],
    "f2": ["\x1bOQ", "\x1b[12~", "\x1b[[B"],
    "f3": ["\x1bOR", "\x1b[13~", "\x1b[[C"],
    "f4": ["\x1bOS", "\x1b[14~", "\x1b[[D"],
    "f5": ["\x1b[15~", "\x1b[[E"],
    "f6": ["\x1b[17~"],
    "f7": ["\x1b[18~"],
    "f8": ["\x1b[19~"],
    "f9": ["\x1b[20~"],
    "f10": ["\x1b[21~"],
    "f11": ["\x1b[23~"],
    "f12": ["\x1b[24~"],
}

LEGACY_SHIFT_SEQUENCES = {
    "up": ["\x1b[a"],
    "down": ["\x1b[b"],
    "right": ["\x1b[c"],
    "left": ["\x1b[d"],
    "clear": ["\x1b[e"],
    "insert": ["\x1b[2$"],
    "delete": ["\x1b[3$"],
    "pageUp": ["\x1b[5$"],
    "pageDown": ["\x1b[6$"],
    "home": ["\x1b[7$"],
    "end": ["\x1b[8$"],
}

LEGACY_CTRL_SEQUENCES = {
    "up": ["\x1bOa"],
    "down": ["\x1bOb"],
    "right": ["\x1bOc"],
    "left": ["\x1bOd"],
    "clear": ["\x1bOe"],
    "insert": ["\x1b[2^"],
    "delete": ["\x1b[3^"],
    "pageUp": ["\x1b[5^"],
    "pageDown": ["\x1b[6^"],
    "home": ["\x1b[7^"],
    "end": ["\x1b[8^"],
}

LEGACY_SEQUENCE_KEY_IDS = {
    "\x1bOA": "up",
    "\x1bOB": "down",
    "\x1bOC": "right",
    "\x1bOD": "left",
    "\x1bOH": "home",
    "\x1bOF": "end",
    "\x1b[E": "clear",
    "\x1bOE": "clear",
    "\x1bOe": "ctrl+clear",
    "\x1b[e": "shift+clear",
    "\x1b[2~": "insert",
    "\x1b[2$": "shift+insert",
    "\x1b[2^": "ctrl+insert",
    "\x1b[3$": "shift+delete",
    "\x1b[3^": "ctrl+delete",
    "\x1b[[5~": "pageUp",
    "\x1b[[6~": "pageDown",
    "\x1b[a": "shift+up",
    "\x1b[b": "shift+down",
    "\x1b[c": "shift+right",
    "\x1b[d": "shift+left",
    "\x1bOa": "ctrl+up",
    "\x1bOb": "ctrl+down",
    "\x1bOc": "ctrl+right",
    "\x1bOd": "ctrl+left",
    "\x1b[5$": "shift+pageUp",
    "\x1b[6$": "shift+pageDown",
    "\x1b[7$": "shift+home",
    "\x1b[8$": "shift+end",
    "\x1b[5^": "ctrl+pageUp",
    "\x1b[6^": "ctrl+pageDown",
    "\x1b[7^": "ctrl+home",
    "\x1b[8^": "ctrl+end",
    "\x1bOP": "f1",
    "\x1bOQ": "f2",
    "\x1bOR": "f3",
    "\x1bOS": "f4",
    "\x1b[11~": "f1",
    "\x1b[12~": "f2",
    "\x1b[13~": "f3",
    "\x1b[14~": "f4",
    "\x1b[[A": "f1",
    "\x1b[[B": "f2",
    "\x1b[[C": "f3",
    "\x1b[[D": "f4",
    "\x1b[[E": "f5",
    "\x1b[15~": "f5",
    "\x1b[17~": "f6",
    "\x1b[18~": "f7",
    "\x1b[19~": "f8",
    "\x1b[20~": "f9",
    "\x1b[21~": "f10",
    "\x1b[23~": "f11",
    "\x1b[24~": "f12",
    "\x1bb": "alt+left",
    "\x1bf": "alt+right",
    "\x1bp": "alt+up",
    "\x1bn": "alt+down",
}


# =============================================================================
# Kitty Protocol Parsing
# =============================================================================


@dataclass
class ParsedKittySequence:
    """Parsed Kitty protocol sequence."""

    codepoint: int
    modifier: int
    event_type: KeyEventType
    shifted_key: int | None = None
    base_layout_key: int | None = None


def parse_event_type(event_type_str: str | None) -> KeyEventType:
    """Parse event type string."""
    if event_type_str is None:
        return KeyEventType.PRESS
    try:
        event_type = int(event_type_str)
        if event_type == 2:
            return KeyEventType.REPEAT
        if event_type == 3:
            return KeyEventType.RELEASE
    except ValueError:
        pass
    return KeyEventType.PRESS


def parse_kitty_sequence(data: str) -> ParsedKittySequence | None:
    """Parse a Kitty protocol sequence."""
    # CSI u format with alternate keys
    csi_u_match = re.match(
        r"^\x1b\[(\d+)(?::(\d*))?(?::(\d+))?(?:;(\d+))?(?::(\d+))?u$",
        data,
    )
    if csi_u_match:
        codepoint = int(csi_u_match.group(1))
        shifted_key = int(csi_u_match.group(2)) if csi_u_match.group(2) and csi_u_match.group(2).strip() else None
        base_layout_key = int(csi_u_match.group(3)) if csi_u_match.group(3) else None
        mod_value = int(csi_u_match.group(4)) if csi_u_match.group(4) else 1
        event_type = parse_event_type(csi_u_match.group(5))
        return ParsedKittySequence(
            codepoint=codepoint,
            modifier=mod_value - 1,
            event_type=event_type,
            shifted_key=shifted_key,
            base_layout_key=base_layout_key,
        )

    # Arrow keys with modifier
    arrow_match = re.match(r"^\x1b\[1;(\d+)(?::(\d+))?([ABCD])$", data)
    if arrow_match:
        mod_value = int(arrow_match.group(1))
        event_type = parse_event_type(arrow_match.group(2))
        arrow_codes = {"A": -1, "B": -2, "C": -3, "D": -4}
        return ParsedKittySequence(
            codepoint=arrow_codes[arrow_match.group(3)],
            modifier=mod_value - 1,
            event_type=event_type,
        )

    # Functional keys
    func_match = re.match(r"^\x1b\[(\d+)(?:;(\d+))?(?::(\d+))?~$", data)
    if func_match:
        key_num = int(func_match.group(1))
        mod_value = int(func_match.group(2)) if func_match.group(2) else 1
        event_type = parse_event_type(func_match.group(3))
        func_codes = {
            2: FUNCTIONAL_CODEPOINTS["insert"],
            3: FUNCTIONAL_CODEPOINTS["delete"],
            5: FUNCTIONAL_CODEPOINTS["pageUp"],
            6: FUNCTIONAL_CODEPOINTS["pageDown"],
            7: FUNCTIONAL_CODEPOINTS["home"],
            8: FUNCTIONAL_CODEPOINTS["end"],
        }
        codepoint = func_codes.get(key_num)
        if codepoint is not None:
            return ParsedKittySequence(
                codepoint=codepoint,
                modifier=mod_value - 1,
                event_type=event_type,
            )

    # Home/End with modifier
    home_end_match = re.match(r"^\x1b\[1;(\d+)(?::(\d+))?([HF])$", data)
    if home_end_match:
        mod_value = int(home_end_match.group(1))
        event_type = parse_event_type(home_end_match.group(2))
        codepoint = FUNCTIONAL_CODEPOINTS["home"] if home_end_match.group(3) == "H" else FUNCTIONAL_CODEPOINTS["end"]
        return ParsedKittySequence(
            codepoint=codepoint,
            modifier=mod_value - 1,
            event_type=event_type,
        )

    return None


def matches_kitty_sequence(data: str, expected_codepoint: int, expected_modifier: int) -> bool:
    """Check if data matches a Kitty sequence."""
    parsed = parse_kitty_sequence(data)
    if parsed is None:
        return False

    actual_mod = parsed.modifier & ~LOCK_MASK
    expected_mod = expected_modifier & ~LOCK_MASK

    if actual_mod != expected_mod:
        return False

    normalized_codepoint = normalize_kitty_codepoint(parsed.codepoint)
    normalized_expected = normalize_kitty_codepoint(expected_codepoint)

    if normalized_codepoint == normalized_expected:
        return True

    # Alternate match using base layout key
    if parsed.base_layout_key is not None and parsed.base_layout_key == expected_codepoint:
        cp = normalized_codepoint
        is_latin = 97 <= cp <= 122
        is_symbol = chr(cp) in SYMBOL_KEYS
        if not is_latin and not is_symbol:
            return True

    return False


# =============================================================================
# modifyOtherKeys Parsing
# =============================================================================


@dataclass
class ParsedModifyOtherKeysSequence:
    """Parsed modifyOtherKeys sequence."""

    codepoint: int
    modifier: int


def parse_modify_other_keys_sequence(data: str) -> ParsedModifyOtherKeysSequence | None:
    """Parse xterm modifyOtherKeys sequence."""
    match = re.match(r"^\x1b\[27;(\d+);(\d+)~$", data)
    if match:
        mod_value = int(match.group(1))
        codepoint = int(match.group(2))
        return ParsedModifyOtherKeysSequence(codepoint=codepoint, modifier=mod_value - 1)
    return None


def matches_modify_other_keys(data: str, expected_codepoint: int, expected_modifier: int) -> bool:
    """Check if data matches a modifyOtherKeys sequence."""
    parsed = parse_modify_other_keys_sequence(data)
    if parsed is None:
        return False
    return parsed.codepoint == expected_codepoint and parsed.modifier == expected_modifier


# =============================================================================
# Key Release Detection
# =============================================================================


def is_key_release(data: str) -> bool:
    """Check if the key event was a key release.

    Only meaningful when Kitty keyboard protocol with flag 2 is active.
    """
    # Don't treat bracketed paste content as key release
    if "\x1b[200~" in data:
        return False

    # Release events contain ":3"
    patterns = [":3u", ":3~", ":3A", ":3B", ":3C", ":3D", ":3H", ":3F"]
    return any(p in data for p in patterns)


def is_key_repeat(data: str) -> bool:
    """Check if the key event was a key repeat.

    Only meaningful when Kitty keyboard protocol with flag 2 is active.
    """
    if "\x1b[200~" in data:
        return False

    patterns = [":2u", ":2~", ":2A", ":2B", ":2C", ":2D", ":2H", ":2F"]
    return any(p in data for p in patterns)


# =============================================================================
# Legacy Sequence Matching
# =============================================================================


def matches_legacy_sequence(data: str, sequences: list[str]) -> bool:
    """Check if data matches any of the legacy sequences."""
    return data in sequences


def matches_legacy_modifier_sequence(data: str, key: str, modifier: int) -> bool:
    """Check if data matches a legacy modifier sequence."""
    if modifier == MODIFIERS["shift"] and key in LEGACY_SHIFT_SEQUENCES:
        return matches_legacy_sequence(data, LEGACY_SHIFT_SEQUENCES[key])
    if modifier == MODIFIERS["ctrl"] and key in LEGACY_CTRL_SEQUENCES:
        return matches_legacy_sequence(data, LEGACY_CTRL_SEQUENCES[key])
    return False


def is_windows_terminal_session() -> bool:
    """Check if running in Windows Terminal."""
    import os

    wt_session = os.environ.get("WT_SESSION")
    is_ssh = any(os.environ.get(k) for k in ["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"])
    return bool(wt_session and not is_ssh)


def matches_raw_backspace(data: str, expected_modifier: int) -> bool:
    """Match raw backspace handling."""
    if data == "\x7f":
        return expected_modifier == 0
    if data != "\x08":
        return False
    return is_windows_terminal_session() if expected_modifier == MODIFIERS["ctrl"] else (expected_modifier == 0)


# =============================================================================
# Key Matching
# =============================================================================


def raw_ctrl_char(key: str) -> str | None:
    """Get the control character for a key."""
    char = key.lower()
    code = ord(char[0]) if char else 0

    if (97 <= code <= 122) or char in ["[", "\\", "]", "_"]:
        return chr(code & 0x1F)
    if char == "-":
        return chr(31)  # Same as Ctrl+_
    return None


def is_digit_key(key: str) -> bool:
    """Check if key is a digit."""
    return len(key) == 1 and key.isdigit()


def matches_printable_modify_other_keys(data: str, expected_codepoint: int, expected_modifier: int) -> bool:
    """Check if data matches a printable modifyOtherKeys sequence."""
    if expected_modifier == 0:
        return False
    return matches_modify_other_keys(data, expected_codepoint, expected_modifier)


def format_key_name_with_modifiers(key_name: str, modifier: int) -> str | None:
    """Format a key name with modifiers."""
    mods = []
    effective_mod = modifier & ~LOCK_MASK
    supported_mask = MODIFIERS["shift"] | MODIFIERS["ctrl"] | MODIFIERS["alt"]

    if (effective_mod & ~supported_mask) != 0:
        return None

    if effective_mod & MODIFIERS["shift"]:
        mods.append("shift")
    if effective_mod & MODIFIERS["ctrl"]:
        mods.append("ctrl")
    if effective_mod & MODIFIERS["alt"]:
        mods.append("alt")

    return f"{'+'.join(mods)}+{key_name}" if mods else key_name


def parse_key_id(key_id: str) -> dict | None:
    """Parse a key identifier into components."""
    parts = key_id.lower().split("+")
    key = parts[-1] if parts else ""
    return {
        "key": key,
        "ctrl": "ctrl" in parts,
        "shift": "shift" in parts,
        "alt": "alt" in parts,
    }


def matches_key(data: str, key_id: KeyId) -> bool:
    """Check if input data matches a key identifier.

    Supported key identifiers:
    - Single keys: "escape", "tab", "enter", etc.
    - Arrow keys: "up", "down", "left", "right"
    - Ctrl combinations: "ctrl+c", "ctrl+z", etc.
    - Shift combinations: "shift+tab", "shift+enter"
    - Alt combinations: "alt+enter", "alt+backspace"
    - Combined modifiers: "shift+ctrl+p", "ctrl+alt+x"

    Args:
        data: Raw input data from terminal
        key_id: Key identifier (e.g., "ctrl+c", "escape")

    Returns:
        True if data matches the key identifier
    """
    parsed = parse_key_id(key_id)
    if parsed is None:
        return False

    key = parsed["key"]
    modifier = 0
    if parsed["shift"]:
        modifier |= MODIFIERS["shift"]
    if parsed["alt"]:
        modifier |= MODIFIERS["alt"]
    if parsed["ctrl"]:
        modifier |= MODIFIERS["ctrl"]

    # Handle special keys
    if key in ("escape", "esc"):
        if modifier != 0:
            return False
        return (
            data == "\x1b"
            or matches_kitty_sequence(data, CODEPOINTS["escape"], 0)
            or matches_modify_other_keys(data, CODEPOINTS["escape"], 0)
        )

    if key == "space":
        if not _kitty_protocol_active:
            if modifier == MODIFIERS["ctrl"] and not parsed["alt"] and not parsed["shift"] and data == "\x00":
                return True
            if modifier == MODIFIERS["alt"] and not parsed["ctrl"] and not parsed["shift"] and data == "\x1b ":
                return True
        if modifier == 0:
            return (
                data == " "
                or matches_kitty_sequence(data, CODEPOINTS["space"], 0)
                or matches_modify_other_keys(data, CODEPOINTS["space"], 0)
            )
        return matches_kitty_sequence(data, CODEPOINTS["space"], modifier) or matches_modify_other_keys(
            data, CODEPOINTS["space"], modifier
        )

    if key == "tab":
        if parsed["shift"] and not parsed["ctrl"] and not parsed["alt"]:
            return (
                data == "\x1b[Z"
                or matches_kitty_sequence(data, CODEPOINTS["tab"], MODIFIERS["shift"])
                or matches_modify_other_keys(data, CODEPOINTS["tab"], MODIFIERS["shift"])
            )
        if modifier == 0:
            return data == "\t" or matches_kitty_sequence(data, CODEPOINTS["tab"], 0)
        return matches_kitty_sequence(data, CODEPOINTS["tab"], modifier) or matches_modify_other_keys(
            data, CODEPOINTS["tab"], modifier
        )

    if key in ("enter", "return"):
        if parsed["shift"] and not parsed["ctrl"] and not parsed["alt"]:
            if matches_kitty_sequence(data, CODEPOINTS["enter"], MODIFIERS["shift"]) or matches_kitty_sequence(
                data, CODEPOINTS["kp_enter"], MODIFIERS["shift"]
            ):
                return True
            if matches_modify_other_keys(data, CODEPOINTS["enter"], MODIFIERS["shift"]):
                return True
            if _kitty_protocol_active:
                return data == "\x1b\r" or data == "\n"
            return False
        if parsed["alt"] and not parsed["ctrl"] and not parsed["shift"]:
            if matches_kitty_sequence(data, CODEPOINTS["enter"], MODIFIERS["alt"]) or matches_kitty_sequence(
                data, CODEPOINTS["kp_enter"], MODIFIERS["alt"]
            ):
                return True
            if matches_modify_other_keys(data, CODEPOINTS["enter"], MODIFIERS["alt"]):
                return True
            if not _kitty_protocol_active:
                return data == "\x1b\r"
            return False
        if modifier == 0:
            return (
                data == "\r"
                or (not _kitty_protocol_active and data == "\n")
                or data == "\x1bOM"
                or matches_kitty_sequence(data, CODEPOINTS["enter"], 0)
                or matches_kitty_sequence(data, CODEPOINTS["kp_enter"], 0)
            )
        return (
            matches_kitty_sequence(data, CODEPOINTS["enter"], modifier)
            or matches_kitty_sequence(data, CODEPOINTS["kp_enter"], modifier)
            or matches_modify_other_keys(data, CODEPOINTS["enter"], modifier)
        )

    if key == "backspace":
        if parsed["alt"] and not parsed["ctrl"] and not parsed["shift"]:
            if data in ("\x1b\x7f", "\x1b\x08"):
                return True
            return matches_kitty_sequence(data, CODEPOINTS["backspace"], MODIFIERS["alt"]) or matches_modify_other_keys(
                data, CODEPOINTS["backspace"], MODIFIERS["alt"]
            )
        if parsed["ctrl"] and not parsed["alt"] and not parsed["shift"]:
            if matches_raw_backspace(data, MODIFIERS["ctrl"]):
                return True
            return matches_kitty_sequence(
                data, CODEPOINTS["backspace"], MODIFIERS["ctrl"]
            ) or matches_modify_other_keys(data, CODEPOINTS["backspace"], MODIFIERS["ctrl"])
        if modifier == 0:
            return (
                matches_raw_backspace(data, 0)
                or matches_kitty_sequence(data, CODEPOINTS["backspace"], 0)
                or matches_modify_other_keys(data, CODEPOINTS["backspace"], 0)
            )
        return matches_kitty_sequence(data, CODEPOINTS["backspace"], modifier) or matches_modify_other_keys(
            data, CODEPOINTS["backspace"], modifier
        )

    # Arrow keys
    if key in ARROW_CODEPOINTS:
        codepoint = ARROW_CODEPOINTS[key]
        if parsed["alt"] and not parsed["ctrl"] and not parsed["shift"]:
            if key == "left":
                return data in ("\x1b[1;3D", "\x1bb") or matches_kitty_sequence(data, codepoint, MODIFIERS["alt"])
            if key == "right":
                return data in ("\x1b[1;3C", "\x1bf") or matches_kitty_sequence(data, codepoint, MODIFIERS["alt"])
            return matches_kitty_sequence(data, codepoint, MODIFIERS["alt"])
        if parsed["ctrl"] and not parsed["alt"] and not parsed["shift"]:
            if key == "left":
                return (
                    data == "\x1b[1;5D"
                    or matches_legacy_modifier_sequence(data, key, MODIFIERS["ctrl"])
                    or matches_kitty_sequence(data, codepoint, MODIFIERS["ctrl"])
                )
            if key == "right":
                return (
                    data == "\x1b[1;5C"
                    or matches_legacy_modifier_sequence(data, key, MODIFIERS["ctrl"])
                    or matches_kitty_sequence(data, codepoint, MODIFIERS["ctrl"])
                )
            return matches_legacy_modifier_sequence(data, key, MODIFIERS["ctrl"]) or matches_kitty_sequence(
                data, codepoint, MODIFIERS["ctrl"]
            )
        if modifier == 0:
            return matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES.get(key, [])) or matches_kitty_sequence(
                data, codepoint, 0
            )
        return matches_legacy_modifier_sequence(data, key, modifier) or matches_kitty_sequence(
            data, codepoint, modifier
        )

    # Functional keys
    if key in FUNCTIONAL_CODEPOINTS:
        codepoint = FUNCTIONAL_CODEPOINTS[key]
        if modifier == 0:
            return matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES.get(key, [])) or matches_kitty_sequence(
                data, codepoint, 0
            )
        if matches_legacy_modifier_sequence(data, key, modifier):
            return True
        return matches_kitty_sequence(data, codepoint, modifier)

    # Function keys F1-F12
    if key.startswith("f") and key[1:].isdigit():
        if modifier != 0:
            return False
        return matches_legacy_sequence(data, LEGACY_KEY_SEQUENCES.get(key, []))

    # Handle single letter/digit keys and symbols
    if len(key) == 1 and (key.isalpha() or key.isdigit() or key in SYMBOL_KEYS):
        codepoint = ord(key)
        raw_ctrl = raw_ctrl_char(key)
        is_letter = key.isalpha()

        if parsed["ctrl"] and parsed["alt"] and not parsed["shift"] and not _kitty_protocol_active and raw_ctrl:
            return data == f"\x1b{raw_ctrl}"

        if (
            parsed["alt"]
            and not parsed["ctrl"]
            and not parsed["shift"]
            and not _kitty_protocol_active
            and (is_letter or key.isdigit())
        ):
            if data == f"\x1b{key}":
                return True

        if parsed["ctrl"] and not parsed["shift"] and not parsed["alt"]:
            if raw_ctrl and data == raw_ctrl:
                return True
            return matches_kitty_sequence(data, codepoint, MODIFIERS["ctrl"]) or matches_printable_modify_other_keys(
                data, codepoint, MODIFIERS["ctrl"]
            )

        if parsed["ctrl"] and parsed["shift"] and not parsed["alt"]:
            return matches_kitty_sequence(
                data, codepoint, MODIFIERS["shift"] | MODIFIERS["ctrl"]
            ) or matches_printable_modify_other_keys(data, codepoint, MODIFIERS["shift"] | MODIFIERS["ctrl"])

        if parsed["shift"] and not parsed["ctrl"] and not parsed["alt"]:
            if is_letter and data == key.upper():
                return True
            return matches_kitty_sequence(data, codepoint, MODIFIERS["shift"]) or matches_printable_modify_other_keys(
                data, codepoint, MODIFIERS["shift"]
            )

        if modifier != 0:
            return matches_kitty_sequence(data, codepoint, modifier) or matches_printable_modify_other_keys(
                data, codepoint, modifier
            )

        return data == key or matches_kitty_sequence(data, codepoint, 0)

    return False


# =============================================================================
# Key Parsing
# =============================================================================


def format_parsed_key(codepoint: int, modifier: int, base_layout_key: int | None = None) -> str | None:
    """Format a parsed key into a key identifier string."""
    normalized = normalize_kitty_codepoint(codepoint)

    # Check if we should use base layout key
    is_latin = 97 <= normalized <= 122
    is_digit = 48 <= normalized <= 57
    is_symbol = chr(normalized) in SYMBOL_KEYS
    effective_codepoint = normalized if (is_latin or is_digit or is_symbol) else (base_layout_key or normalized)

    # Map codepoint to key name
    if effective_codepoint == CODEPOINTS["escape"]:
        key_name = "escape"
    elif effective_codepoint == CODEPOINTS["tab"]:
        key_name = "tab"
    elif effective_codepoint in (CODEPOINTS["enter"], CODEPOINTS["kp_enter"]):
        key_name = "enter"
    elif effective_codepoint == CODEPOINTS["space"]:
        key_name = "space"
    elif effective_codepoint == CODEPOINTS["backspace"]:
        key_name = "backspace"
    elif effective_codepoint == FUNCTIONAL_CODEPOINTS["delete"]:
        key_name = "delete"
    elif effective_codepoint == FUNCTIONAL_CODEPOINTS["insert"]:
        key_name = "insert"
    elif effective_codepoint == FUNCTIONAL_CODEPOINTS["home"]:
        key_name = "home"
    elif effective_codepoint == FUNCTIONAL_CODEPOINTS["end"]:
        key_name = "end"
    elif effective_codepoint == FUNCTIONAL_CODEPOINTS["pageUp"]:
        key_name = "pageUp"
    elif effective_codepoint == FUNCTIONAL_CODEPOINTS["pageDown"]:
        key_name = "pageDown"
    elif effective_codepoint == ARROW_CODEPOINTS["up"]:
        key_name = "up"
    elif effective_codepoint == ARROW_CODEPOINTS["down"]:
        key_name = "down"
    elif effective_codepoint == ARROW_CODEPOINTS["left"]:
        key_name = "left"
    elif effective_codepoint == ARROW_CODEPOINTS["right"]:
        key_name = "right"
    elif 48 <= effective_codepoint <= 57 or 97 <= effective_codepoint <= 122 or chr(effective_codepoint) in SYMBOL_KEYS:
        key_name = chr(effective_codepoint)
    else:
        return None

    return format_key_name_with_modifiers(key_name, modifier)


def parse_key(data: str) -> str | None:
    """Parse input data and return the key identifier if recognized.

    Args:
        data: Raw input data from terminal

    Returns:
        Key identifier string (e.g., "ctrl+c") or None
    """
    # Try Kitty protocol first
    kitty = parse_kitty_sequence(data)
    if kitty:
        return format_parsed_key(kitty.codepoint, kitty.modifier, kitty.base_layout_key)

    # Try modifyOtherKeys
    modify_other_keys = parse_modify_other_keys_sequence(data)
    if modify_other_keys:
        return format_parsed_key(modify_other_keys.codepoint, modify_other_keys.modifier)

    # Mode-aware legacy sequences
    if _kitty_protocol_active and data in ("\x1b\r", "\n"):
        return "shift+enter"

    # Legacy sequence key IDs
    if data in LEGACY_SEQUENCE_KEY_IDS:
        return LEGACY_SEQUENCE_KEY_IDS[data]

    # Legacy sequences
    if data == "\x1b":
        return "escape"
    if data == "\x1c":
        return "ctrl+\\"
    if data == "\x1d":
        return "ctrl+]"
    if data == "\x1f":
        return "ctrl+-"
    if data == "\x1b\x1b":
        return "ctrl+alt+["
    if data == "\x1b\x1c":
        return "ctrl+alt+\\"
    if data == "\x1b\x1d":
        return "ctrl+alt+]"
    if data == "\x1b\x1f":
        return "ctrl+alt+-"
    if data == "\t":
        return "tab"
    if data == "\r" or (not _kitty_protocol_active and data == "\n") or data == "\x1bOM":
        return "enter"
    if data == "\x00":
        return "ctrl+space"
    if data == " ":
        return "space"
    if data == "\x7f":
        return "backspace"
    if data == "\x08":
        return "ctrl+backspace" if is_windows_terminal_session() else "backspace"
    if data == "\x1b[Z":
        return "shift+tab"
    if not _kitty_protocol_active and data == "\x1b\r":
        return "alt+enter"
    if not _kitty_protocol_active and data == "\x1b ":
        return "alt+space"
    if data in ("\x1b\x7f", "\x1b\x08"):
        return "alt+backspace"
    if not _kitty_protocol_active and data == "\x1bB":
        return "alt+left"
    if not _kitty_protocol_active and data == "\x1bF":
        return "alt+right"
    if not _kitty_protocol_active and len(data) == 2 and data[0] == "\x1b":
        code = ord(data[1])
        if 1 <= code <= 26:
            return f"ctrl+alt+{chr(code + 96)}"
        if (97 <= code <= 122) or (48 <= code <= 57):
            return f"alt+{chr(code)}"
    if data == "\x1b[A":
        return "up"
    if data == "\x1b[B":
        return "down"
    if data == "\x1b[C":
        return "right"
    if data == "\x1b[D":
        return "left"
    if data in ("\x1b[H", "\x1bOH"):
        return "home"
    if data in ("\x1b[F", "\x1bOF"):
        return "end"
    if data == "\x1b[3~":
        return "delete"
    if data == "\x1b[5~":
        return "pageUp"
    if data == "\x1b[6~":
        return "pageDown"

    # Raw Ctrl+letter
    if len(data) == 1:
        code = ord(data)
        if 1 <= code <= 26:
            return f"ctrl+{chr(code + 96)}"
        if 32 <= code <= 126:
            return data

    return None


# =============================================================================
# Kitty Printable Decoding
# =============================================================================

KITTY_CSI_U_REGEX = re.compile(r"^\x1b\[(\d+)(?::(\d*))?(?::(\d+))?(?:;(\d+))?(?::(\d+))?u$")
KITTY_PRINTABLE_ALLOWED_MODIFIERS = MODIFIERS["shift"] | LOCK_MASK


def decode_kitty_printable(data: str) -> str | None:
    """Decode a Kitty CSI-u sequence into a printable character.

    When Kitty keyboard protocol flag 1 is active, terminals send CSI-u
    sequences for all keys, including plain printable characters.

    Args:
        data: Raw input data from terminal

    Returns:
        The printable character, or None if not a printable CSI-u sequence
    """
    match = KITTY_CSI_U_REGEX.match(data)
    if not match:
        return None

    codepoint = int(match.group(1))
    shifted_key = int(match.group(2)) if match.group(2) and match.group(2).strip() else None
    mod_value = int(match.group(4)) if match.group(4) else 1
    modifier = mod_value - 1

    # Only accept plain or Shift-modified text keys
    if (modifier & ~KITTY_PRINTABLE_ALLOWED_MODIFIERS) != 0:
        return None
    if modifier & (MODIFIERS["alt"] | MODIFIERS["ctrl"]):
        return None

    # Prefer the shifted keycode when Shift is held
    effective_codepoint = codepoint
    if modifier & MODIFIERS["shift"] and shifted_key is not None:
        effective_codepoint = shifted_key

    effective_codepoint = normalize_kitty_codepoint(effective_codepoint)
    if effective_codepoint < 32:
        return None

    try:
        return chr(effective_codepoint)
    except ValueError:
        return None
