"""Cell representation for terminal display."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CellAttributes:
    """Text attributes for a cell."""

    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    inverse: bool = False
    hidden: bool = False
    strikethrough: bool = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CellAttributes):
            return NotImplemented
        return (
            self.bold == other.bold
            and self.dim == other.dim
            and self.italic == other.italic
            and self.underline == other.underline
            and self.blink == other.blink
            and self.inverse == other.inverse
            and self.hidden == other.hidden
            and self.strikethrough == other.strikethrough
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.bold,
                self.dim,
                self.italic,
                self.underline,
                self.blink,
                self.inverse,
                self.hidden,
                self.strikethrough,
            )
        )

    def to_sgr_codes(self) -> list[int]:
        """Convert attributes to SGR codes."""
        codes = []
        if self.bold:
            codes.append(1)
        if self.dim:
            codes.append(2)
        if self.italic:
            codes.append(3)
        if self.underline:
            codes.append(4)
        if self.blink:
            codes.append(5)
        if self.inverse:
            codes.append(7)
        if self.hidden:
            codes.append(8)
        if self.strikethrough:
            codes.append(9)
        return codes

    @classmethod
    def from_sgr_codes(cls, codes: list[int]) -> CellAttributes:
        """Create attributes from SGR codes."""
        attrs = cls()
        for code in codes:
            if code == 1:
                attrs.bold = True
            elif code == 2:
                attrs.dim = True
            elif code == 3:
                attrs.italic = True
            elif code == 4:
                attrs.underline = True
            elif code == 5:
                attrs.blink = True
            elif code == 7:
                attrs.inverse = True
            elif code == 8:
                attrs.hidden = True
            elif code == 9:
                attrs.strikethrough = True
        return attrs


@dataclass
class Cell:
    """A single cell in the terminal buffer.

    Each cell represents one display position and contains:
    - Character (may be empty string or multi-byte Unicode)
    - Foreground color (RGB tuple or None for default)
    - Background color (RGB tuple or None for default)
    - Text attributes (bold, italic, etc.)
    """

    char: str = " "
    fg: tuple[int, int, int] | None = None
    bg: tuple[int, int, int] | None = None
    attrs: CellAttributes = field(default_factory=CellAttributes)

    def __post_init__(self):
        """Ensure char is a valid string."""
        if not isinstance(self.char, str):
            self.char = str(self.char)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cell):
            return NotImplemented
        return self.char == other.char and self.fg == other.fg and self.bg == other.bg and self.attrs == other.attrs

    def __hash__(self) -> int:
        return hash(
            (
                self.char,
                self.fg,
                self.bg,
                hash(self.attrs),
            )
        )

    def is_empty(self) -> bool:
        """Check if this cell is empty (space with default colors/attrs)."""
        return (
            self.char == " "
            and self.fg is None
            and self.bg is None
            and not any(
                [
                    self.attrs.bold,
                    self.attrs.dim,
                    self.attrs.italic,
                    self.attrs.underline,
                    self.attrs.blink,
                    self.attrs.inverse,
                    self.attrs.hidden,
                    self.attrs.strikethrough,
                ]
            )
        )

    def to_ansi(self) -> str:
        """Convert cell to ANSI escape sequence string."""
        parts = []

        # Add attributes
        if self.attrs.bold:
            parts.append("\x1b[1m")
        if self.attrs.dim:
            parts.append("\x1b[2m")
        if self.attrs.italic:
            parts.append("\x1b[3m")
        if self.attrs.underline:
            parts.append("\x1b[4m")
        if self.attrs.blink:
            parts.append("\x1b[5m")
        if self.attrs.inverse:
            parts.append("\x1b[7m")
        if self.attrs.hidden:
            parts.append("\x1b[8m")
        if self.attrs.strikethrough:
            parts.append("\x1b[9m")

        # Add foreground color
        if self.fg:
            parts.append(f"\x1b[38;2;{self.fg[0]};{self.fg[1]};{self.fg[2]}m")

        # Add background color
        if self.bg:
            parts.append(f"\x1b[48;2;{self.bg[0]};{self.bg[1]};{self.bg[2]}m")

        # Add character
        parts.append(self.char)

        return "".join(parts)

    def copy(self) -> Cell:
        """Create a copy of this cell."""
        return Cell(
            char=self.char,
            fg=self.fg,
            bg=self.bg,
            attrs=CellAttributes(
                bold=self.attrs.bold,
                dim=self.attrs.dim,
                italic=self.attrs.italic,
                underline=self.attrs.underline,
                blink=self.attrs.blink,
                inverse=self.attrs.inverse,
                hidden=self.attrs.hidden,
                strikethrough=self.attrs.strikethrough,
            ),
        )

    @classmethod
    def empty(cls) -> Cell:
        """Create an empty cell."""
        return cls(char=" ")

    @classmethod
    def with_char(cls, char: str) -> Cell:
        """Create a cell with the given character."""
        return cls(char=char)

    @classmethod
    def with_style(
        cls,
        char: str,
        fg: tuple[int, int, int] | None = None,
        bg: tuple[int, int, int] | None = None,
        **attrs: bool,
    ) -> Cell:
        """Create a cell with the given character and style."""
        return cls(
            char=char,
            fg=fg,
            bg=bg,
            attrs=CellAttributes(**attrs),
        )
