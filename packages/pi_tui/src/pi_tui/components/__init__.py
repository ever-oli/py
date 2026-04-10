"""TUI Components - Box, Text, Editor, SelectList, Input, Autocomplete, Markdown, etc."""

from .autocomplete import (
    AutocompleteItem,
    AutocompleteSuggestions,
    CombinedAutocompleteProvider,
    SlashCommand,
)
from .box import Box
from .editor import Editor, EditorOptions, EditorTheme
from .input import Input, InputTheme, KillRing, UndoStack
from .markdown import (
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
from .select_list import SelectItem, SelectList, SelectListLayoutOptions, SelectListTheme
from .text import Text

__all__ = [
    # Basic components
    "Box",
    "Text",
    # Select list
    "SelectList",
    "SelectItem",
    "SelectListTheme",
    "SelectListLayoutOptions",
    # Editor
    "Editor",
    "EditorOptions",
    "EditorTheme",
    # Input
    "Input",
    "InputTheme",
    "KillRing",
    "UndoStack",
    # Autocomplete
    "CombinedAutocompleteProvider",
    "AutocompleteItem",
    "SlashCommand",
    "AutocompleteSuggestions",
    # Markdown
    "Markdown",
    "CodeBlock",
    "InlineCode",
    "Quote",
    "ListComponent",
    "Heading",
    "HorizontalRule",
    "Link",
    "Table",
]
