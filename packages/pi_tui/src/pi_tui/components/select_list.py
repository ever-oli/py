"""SelectList component - scrollable list of selectable items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..keybindings import get_keybindings
from ..tui import Component
from ..utils import truncate_to_width, visible_width


@dataclass
class SelectItem:
    """An item in the select list."""

    value: str
    label: str
    description: str | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SelectListTheme:
    """Theme for SelectList component."""

    selected_prefix: Callable[[str], str]
    selected_text: Callable[[str], str]
    description: Callable[[str], str]
    scroll_info: Callable[[str], str]
    no_match: Callable[[str], str]


@dataclass
class SelectListLayoutOptions:
    """Layout options for SelectList."""

    min_primary_column_width: int = 12
    max_primary_column_width: int = 32


class SelectList(Component):
    """SelectList component - scrollable list of selectable items."""

    PRIMARY_COLUMN_GAP = 2
    MIN_DESCRIPTION_WIDTH = 10

    def __init__(
        self,
        items: list[SelectItem],
        max_visible: int = 5,
        theme: SelectListTheme | None = None,
        layout_options: SelectListLayoutOptions | None = None,
    ):
        """Initialize the select list.

        Args:
            items: List of items to display
            max_visible: Maximum number of items visible at once
            theme: Visual theme
            layout_options: Layout configuration
        """
        self._items = items
        self._filtered_items = items.copy()
        self._selected_index = 0
        self._max_visible = max_visible
        self._theme = theme or self._default_theme()
        self._layout = layout_options or SelectListLayoutOptions()

        # Callbacks
        self.on_select: Callable[[SelectItem], None] | None = None
        self.on_cancel: Callable[[], None] | None = None
        self.on_selection_change: Callable[[SelectItem], None] | None = None

    @staticmethod
    def _default_theme() -> SelectListTheme:
        """Get default theme."""
        return SelectListTheme(
            selected_prefix=lambda s: f"\x1b[1m{s}\x1b[0m",
            selected_text=lambda s: f"\x1b[1m\x1b[7m{s}\x1b[0m",
            description=lambda s: f"\x1b[2m{s}\x1b[0m",
            scroll_info=lambda s: f"\x1b[2m{s}\x1b[0m",
            no_match=lambda s: f"\x1b[2m{s}\x1b[0m",
        )

    def set_items(self, items: list[SelectItem]) -> None:
        """Set the items in the list."""
        self._items = items
        self._filtered_items = items.copy()
        self._selected_index = 0

    def set_filter(self, filter_text: str) -> None:
        """Filter items by text."""
        filter_lower = filter_text.lower()
        self._filtered_items = [
            item
            for item in self._items
            if item.value.lower().startswith(filter_lower) or item.label.lower().startswith(filter_lower)
        ]
        self._selected_index = 0

    def set_selected_index(self, index: int) -> None:
        """Set the selected index."""
        self._selected_index = max(0, min(index, len(self._filtered_items) - 1))

    def invalidate(self) -> None:
        """Invalidate cached state."""
        pass

    def render(self, width: int) -> list[str]:
        """Render the select list."""
        lines: list[str] = []

        # No items match
        if not self._filtered_items:
            lines.append(self._theme.no_match("  No matching items"))
            return lines

        primary_column_width = self._get_primary_column_width()

        # Calculate visible range with scrolling
        start_index = max(
            0,
            min(
                self._selected_index - self._max_visible // 2,
                len(self._filtered_items) - self._max_visible,
            ),
        )
        end_index = min(start_index + self._max_visible, len(self._filtered_items))

        # Render visible items
        for i in range(start_index, end_index):
            item = self._filtered_items[i]
            is_selected = i == self._selected_index
            description = self._normalize_to_single_line(item.description) if item.description else None
            lines.append(self._render_item(item, is_selected, width, description, primary_column_width))

        # Add scroll indicators
        if start_index > 0 or end_index < len(self._filtered_items):
            scroll_text = f"  ({self._selected_index + 1}/{len(self._filtered_items)})"
            lines.append(self._theme.scroll_info(truncate_to_width(scroll_text, width - 2, "")))

        return lines

    def handle_input(self, key_data: str) -> None:
        """Handle input for navigation."""
        kb = get_keybindings()

        # Up arrow - wrap to bottom
        if kb.matches(key_data, "tui.select.up"):
            self._selected_index = (
                len(self._filtered_items) - 1 if self._selected_index == 0 else self._selected_index - 1
            )
            self._notify_selection_change()

        # Down arrow - wrap to top
        elif kb.matches(key_data, "tui.select.down"):
            self._selected_index = (
                0 if self._selected_index == len(self._filtered_items) - 1 else self._selected_index + 1
            )
            self._notify_selection_change()

        # Enter - confirm
        elif kb.matches(key_data, "tui.select.confirm"):
            selected = self.get_selected_item()
            if selected and self.on_select:
                self.on_select(selected)

        # Escape or Ctrl+C - cancel
        elif kb.matches(key_data, "tui.select.cancel"):
            if self.on_cancel:
                self.on_cancel()

    def _render_item(
        self,
        item: SelectItem,
        is_selected: bool,
        width: int,
        description: str | None,
        primary_column_width: int,
    ) -> str:
        """Render a single item."""
        prefix = "→ " if is_selected else "  "
        prefix_width = visible_width(prefix)

        if description and width > 40:
            effective_width = max(1, min(primary_column_width, width - prefix_width - 4))
            max_primary_width = max(1, effective_width - self.PRIMARY_COLUMN_GAP)
            truncated_value = truncate_to_width(item.label, max_primary_width, "")
            truncated_value_width = visible_width(truncated_value)
            spacing = " " * max(1, effective_width - truncated_value_width)
            description_start = prefix_width + truncated_value_width + len(spacing)
            remaining_width = width - description_start - 2

            if remaining_width > self.MIN_DESCRIPTION_WIDTH:
                truncated_desc = truncate_to_width(description, remaining_width, "")
                if is_selected:
                    return self._theme.selected_text(f"{prefix}{truncated_value}{spacing}{truncated_desc}")

                desc_text = self._theme.description(spacing + truncated_desc)
                return prefix + truncated_value + desc_text

        max_width = width - prefix_width - 2
        truncated_value = truncate_to_width(item.label, max_width, "")
        if is_selected:
            return self._theme.selected_text(f"{prefix}{truncated_value}")

        return prefix + truncated_value

    def _get_primary_column_width(self) -> int:
        """Calculate primary column width."""
        min_w = max(1, min(self._layout.min_primary_column_width, self._layout.max_primary_column_width))
        max_w = max(1, max(self._layout.min_primary_column_width, self._layout.max_primary_column_width))

        widest = max(
            (visible_width(item.label) + self.PRIMARY_COLUMN_GAP for item in self._filtered_items),
            default=0,
        )

        return max(min_w, min(widest, max_w))

    @staticmethod
    def _normalize_to_single_line(text: str) -> str:
        """Normalize text to a single line."""
        return " ".join(text.split())

    def _notify_selection_change(self) -> None:
        """Notify listeners of selection change."""
        selected = self.get_selected_item()
        if selected and self.on_selection_change:
            self.on_selection_change(selected)

    def get_selected_item(self) -> SelectItem | None:
        """Get the currently selected item."""
        if 0 <= self._selected_index < len(self._filtered_items):
            return self._filtered_items[self._selected_index]
        return None

    def get_selected_index(self) -> int:
        """Get the currently selected index."""
        return self._selected_index
