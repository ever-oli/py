"""ANSI escape sequence utilities for terminal control."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnsiCodes:
    """ANSI escape code constants."""

    # Control characters
    ESC: str = "\x1b"
    BEL: str = "\x07"

    # Cursor control
    CURSOR_HIDE: str = "\x1b[?25l"
    CURSOR_SHOW: str = "\x1b[?25h"
    CURSOR_HOME: str = "\x1b[H"

    # Screen control
    CLEAR_SCREEN: str = "\x1b[2J"
    CLEAR_LINE: str = "\x1b[2K"
    CLEAR_FROM_CURSOR: str = "\x1b[J"

    # Synchronized output (DECSET 2026)
    SYNC_START: str = "\x1b[?2026h"
    SYNC_END: str = "\x1b[?2026l"

    # Bracketed paste mode
    BRACKETED_PASTE_ON: str = "\x1b[?2004h"
    BRACKETED_PASTE_OFF: str = "\x1b[?2004l"
    BRACKETED_PASTE_START: str = "\x1b[200~"
    BRACKETED_PASTE_END: str = "\x1b[201~"

    # Kitty keyboard protocol
    KITTY_QUERY: str = "\x1b[?u"
    KITTY_ENABLE: str = "\x1b[>7u"
    KITTY_DISABLE: str = "\x1b[<u"

    # modifyOtherKeys
    MODIFY_OTHER_KEYS_ENABLE: str = "\x1b[>4;2m"
    MODIFY_OTHER_KEYS_DISABLE: str = "\x1b[>4;0m"

    # Reset
    RESET: str = "\x1b[0m"

    @staticmethod
    def move_up(n: int = 1) -> str:
        """Generate escape sequence to move cursor up n lines."""
        return f"\x1b[{n}A" if n > 0 else ""

    @staticmethod
    def move_down(n: int = 1) -> str:
        """Generate escape sequence to move cursor down n lines."""
        return f"\x1b[{n}B" if n > 0 else ""

    @staticmethod
    def move_right(n: int = 1) -> str:
        """Generate escape sequence to move cursor right n columns."""
        return f"\x1b[{n}C" if n > 0 else ""

    @staticmethod
    def move_left(n: int = 1) -> str:
        """Generate escape sequence to move cursor left n columns."""
        return f"\x1b[{n}D" if n > 0 else ""

    @staticmethod
    def set_column(n: int) -> str:
        """Generate escape sequence to move cursor to column n (1-indexed)."""
        return f"\x1b[{n}G"

    @staticmethod
    def cursor_position(row: int, col: int) -> str:
        """Generate escape sequence to move cursor to position (1-indexed)."""
        return f"\x1b[{row};{col}H"

    @staticmethod
    def set_title(title: str) -> str:
        """Generate escape sequence to set terminal window title."""
        return f"\x1b]0;{title}\x07"

    @staticmethod
    def sgr(*codes: int) -> str:
        """Generate SGR (Select Graphic Rendition) escape sequence."""
        return f"\x1b[{';'.join(str(c) for c in codes)}m"

    @staticmethod
    def fg_color(r: int, g: int, b: int) -> str:
        """Generate true color foreground escape sequence."""
        return f"\x1b[38;2;{r};{g};{b}m"

    @staticmethod
    def bg_color(r: int, g: int, b: int) -> str:
        """Generate true color background escape sequence."""
        return f"\x1b[48;2;{r};{g};{b}m"

    @staticmethod
    def fg_256(color: int) -> str:
        """Generate 256-color foreground escape sequence."""
        return f"\x1b[38;5;{color}m"

    @staticmethod
    def bg_256(color: int) -> str:
        """Generate 256-color background escape sequence."""
        return f"\x1b[48;5;{color}m"


# Global instance
ansi = AnsiCodes()


class AnsiCodeTracker:
    """Track active ANSI SGR codes to preserve styling across operations."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """Reset all tracked attributes."""
        self.bold = False
        self.dim = False
        self.italic = False
        self.underline = False
        self.blink = False
        self.inverse = False
        self.hidden = False
        self.strikethrough = False
        self.fg_color: str | None = None
        self.bg_color: str | None = None

    def clear(self) -> None:
        """Alias for reset()."""
        self.reset()

    def process(self, ansi_code: str) -> None:
        """Process an ANSI SGR code and update tracked state."""
        if not ansi_code.endswith("m"):
            return

        # Extract parameters between \x1b[ and m
        import re

        match = re.match(r"\x1b\[([\d;]*)m", ansi_code)
        if not match:
            return

        params = match.group(1)
        if params == "" or params == "0":
            self.reset()
            return

        # Parse parameters (semicolon-separated)
        parts = params.split(";")
        i = 0
        while i < len(parts):
            try:
                code = int(parts[i])
            except ValueError:
                i += 1
                continue

            # Handle 256-color and RGB codes
            if code in (38, 48) and i + 2 < len(parts):
                if parts[i + 1] == "5" and parts[i + 2] is not None:
                    # 256 color
                    color_code = f"{parts[i]};{parts[i + 1]};{parts[i + 2]}"
                    if code == 38:
                        self.fg_color = color_code
                    else:
                        self.bg_color = color_code
                    i += 3
                    continue
                elif parts[i + 1] == "2" and i + 4 < len(parts):
                    # RGB color
                    color_code = f"{parts[i]};{parts[i + 1]};{parts[i + 2]};{parts[i + 3]};{parts[i + 4]}"
                    if code == 38:
                        self.fg_color = color_code
                    else:
                        self.bg_color = color_code
                    i += 5
                    continue

            # Standard SGR codes
            if code == 0:
                self.reset()
            elif code == 1:
                self.bold = True
            elif code == 2:
                self.dim = True
            elif code == 3:
                self.italic = True
            elif code == 4:
                self.underline = True
            elif code == 5:
                self.blink = True
            elif code == 7:
                self.inverse = True
            elif code == 8:
                self.hidden = True
            elif code == 9:
                self.strikethrough = True
            elif code == 21:
                self.bold = False
            elif code == 22:
                self.bold = False
                self.dim = False
            elif code == 23:
                self.italic = False
            elif code == 24:
                self.underline = False
            elif code == 25:
                self.blink = False
            elif code == 27:
                self.inverse = False
            elif code == 28:
                self.hidden = False
            elif code == 29:
                self.strikethrough = False
            elif code == 39:
                self.fg_color = None
            elif code == 49:
                self.bg_color = None
            elif 30 <= code <= 37 or 90 <= code <= 97:
                self.fg_color = str(code)
            elif 40 <= code <= 47 or 100 <= code <= 107:
                self.bg_color = str(code)

            i += 1

    def get_active_codes(self) -> str:
        """Get the escape sequence for currently active attributes."""
        codes = []
        if self.bold:
            codes.append("1")
        if self.dim:
            codes.append("2")
        if self.italic:
            codes.append("3")
        if self.underline:
            codes.append("4")
        if self.blink:
            codes.append("5")
        if self.inverse:
            codes.append("7")
        if self.hidden:
            codes.append("8")
        if self.strikethrough:
            codes.append("9")
        if self.fg_color:
            codes.append(self.fg_color)
        if self.bg_color:
            codes.append(self.bg_color)

        if not codes:
            return ""
        return f"\x1b[{';'.join(codes)}m"

    def has_active_codes(self) -> bool:
        """Check if any attributes are currently active."""
        return (
            self.bold
            or self.dim
            or self.italic
            or self.underline
            or self.blink
            or self.inverse
            or self.hidden
            or self.strikethrough
            or self.fg_color is not None
            or self.bg_color is not None
        )

    def get_line_end_reset(self) -> str:
        """Get reset codes for attributes that need to be turned off at line end."""
        # Only underline causes visual bleeding into padding
        if self.underline:
            return "\x1b[24m"
        return ""
