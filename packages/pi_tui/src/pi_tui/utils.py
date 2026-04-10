"""Utility functions for terminal text handling."""

from __future__ import annotations

from .ansi import AnsiCodeTracker

# Unicode grapheme handling
try:
    import unicodedata

    def is_grapheme_boundary(text: str, pos: int) -> bool:
        """Check if position is at a grapheme boundary."""
        if pos <= 0 or pos >= len(text):
            return True
        # Simple heuristic - more complex handling may be needed
        return True
except ImportError:

    def is_grapheme_boundary(text: str, pos: int) -> bool:
        return True


def is_wide_char(char: str) -> bool:
    """Check if a character is a wide character (CJK, emoji, etc.)."""
    if not char:
        return False
    code = ord(char[0])
    # CJK ranges
    if 0x1100 <= code <= 0x115F:  # Hangul Jamo
        return True
    if 0x2E80 <= code <= 0xA4CF:  # CJK
        return True
    if 0xAC00 <= code <= 0xD7AF:  # Hangul Syllables
        return True
    if 0xF900 <= code <= 0xFAFF:  # CJK Compatibility Ideographs
        return True
    if 0xFE30 <= code <= 0xFE6F:  # CJK Compatibility Forms
        return True
    if 0xFF00 <= code <= 0xFF60:  # Fullwidth Forms
        return True
    if 0xFFE0 <= code <= 0xFFE6:  # Fullwidth Symbols
        return True
    # Emoji ranges
    if 0x1F000 <= code <= 0x1FBFF:
        return True
    if 0x2600 <= code <= 0x27BF:  # Misc symbols
        return True
    return False


def char_width(char: str) -> int:
    """Get the display width of a character."""
    if not char:
        return 0
    if char == "\t":
        return 4  # Tab width
    code = ord(char)
    # Control characters
    if code < 32 or code == 0x7F:
        return 0
    # Zero-width characters
    if 0x0300 <= code <= 0x036F:  # Combining diacritics
        return 0
    if 0x200B <= code <= 0x200F:  # Zero-width spaces
        return 0
    if 0xFE00 <= code <= 0xFE0F:  # Variation selectors
        return 0
    # Wide characters
    if is_wide_char(char):
        return 2
    return 1


def extract_ansi_code(text: str, pos: int) -> dict | None:
    """Extract an ANSI escape sequence from text at the given position.

    Returns a dict with 'code' and 'length' keys, or None if no ANSI code.
    """
    if pos >= len(text) or text[pos] != "\x1b":
        return None

    next_char = text[pos + 1] if pos + 1 < len(text) else ""

    # CSI sequence: ESC [ ... m/G/K/H/J
    if next_char == "[":
        j = pos + 2
        while j < len(text) and text[j] not in "mGKHJ":
            j += 1
        if j < len(text):
            return {"code": text[pos : j + 1], "length": j + 1 - pos}
        return None

    # OSC sequence: ESC ] ... BEL or ST
    if next_char == "]":
        j = pos + 2
        while j < len(text):
            if text[j] == "\x07":  # BEL
                return {"code": text[pos : j + 1], "length": j + 1 - pos}
            if text[j] == "\x1b" and j + 1 < len(text) and text[j + 1] == "\\":
                return {"code": text[pos : j + 2], "length": j + 2 - pos}
            j += 1
        return None

    # APC sequence: ESC _ ... BEL or ST
    if next_char == "_":
        j = pos + 2
        while j < len(text):
            if text[j] == "\x07":
                return {"code": text[pos : j + 1], "length": j + 1 - pos}
            if text[j] == "\x1b" and j + 1 < len(text) and text[j + 1] == "\\":
                return {"code": text[pos : j + 2], "length": j + 2 - pos}
            j += 1
        return None

    return None


def strip_ansi_codes(text: str) -> str:
    """Remove all ANSI escape sequences from text."""
    result = []
    i = 0
    while i < len(text):
        ansi = extract_ansi_code(text, i)
        if ansi:
            i += ansi["length"]
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def visible_width(text: str) -> int:
    """Calculate the visible width of a string in terminal columns.

    This accounts for ANSI escape codes (which have 0 width) and
    wide characters (which have 2 columns).
    """
    if not text:
        return 0

    width = 0
    i = 0

    while i < len(text):
        # Skip ANSI codes
        ansi = extract_ansi_code(text, i)
        if ansi:
            i += ansi["length"]
            continue

        char = text[i]
        if char == "\t":
            width += 4  # Tab = 4 spaces
        else:
            width += char_width(char)

        i += 1

    return width


def truncate_to_width(
    text: str,
    max_width: int,
    ellipsis: str = "...",
    pad: bool = False,
) -> str:
    """Truncate text to fit within a maximum visible width.

    Args:
        text: Text to truncate (may contain ANSI codes)
        max_width: Maximum visible width
        ellipsis: Ellipsis string to append when truncating
        pad: If True, pad result with spaces to exactly max_width

    Returns:
        Truncated text, optionally padded to exactly max_width
    """
    if max_width <= 0:
        return ""

    if not text:
        return " " * max_width if pad else ""

    ellipsis_width = visible_width(ellipsis)

    # If ellipsis is wider than max_width, don't use it
    if ellipsis_width >= max_width:
        if visible_width(text) <= max_width:
            if pad:
                text_width = visible_width(text)
                return text + " " * (max_width - text_width)
            return text
        # Just truncate without ellipsis
        return _truncate_exact(text, max_width, pad)

    text_width = visible_width(text)
    if text_width <= max_width:
        if pad:
            return text + " " * (max_width - text_width)
        return text

    # Need to truncate with ellipsis
    target_width = max_width - ellipsis_width
    result = _truncate_exact(text, target_width, False)

    if pad:
        result_width = visible_width(result) + ellipsis_width
        return result + "\x1b[0m" + ellipsis + "\x1b[0m" + " " * (max_width - result_width)

    return result + "\x1b[0m" + ellipsis + "\x1b[0m"


def _truncate_exact(text: str, max_width: int, pad: bool) -> str:
    """Truncate text to exactly max_width without ellipsis."""
    result = []
    width = 0
    pending_ansi = ""
    i = 0

    while i < len(text) and width < max_width:
        ansi = extract_ansi_code(text, i)
        if ansi:
            pending_ansi += ansi["code"]
            i += ansi["length"]
            continue

        char = text[i]
        char_w = char_width(char)

        if width + char_w > max_width:
            break

        if pending_ansi:
            result.append(pending_ansi)
            pending_ansi = ""

        result.append(char)
        width += char_w
        i += 1

    result.append(pending_ansi)

    if pad:
        result.append(" " * (max_width - width))

    return "".join(result)


def slice_by_column(text: str, start_col: int, length: int, strict: bool = False) -> str:
    """Extract a range of visible columns from a line.

    Args:
        text: Source text (may contain ANSI codes)
        start_col: Starting column (0-indexed)
        length: Number of columns to extract
        strict: If True, exclude wide chars at boundary that would extend past range

    Returns:
        Extracted text segment
    """
    return slice_with_width(text, start_col, length, strict)["text"]


def slice_with_width(
    text: str,
    start_col: int,
    length: int,
    strict: bool = False,
) -> dict:
    """Extract a column range and return both text and actual width.

    Returns dict with 'text' and 'width' keys.
    """
    if length <= 0:
        return {"text": "", "width": 0}

    end_col = start_col + length
    result = []
    result_width = 0
    current_col = 0
    i = 0
    pending_ansi = ""

    while i < len(text):
        ansi = extract_ansi_code(text, i)
        if ansi:
            if current_col >= start_col and current_col < end_col:
                result.append(ansi["code"])
            elif current_col < start_col:
                pending_ansi += ansi["code"]
            i += ansi["length"]
            continue

        char = text[i]
        w = char_width(char)

        in_range = current_col >= start_col and current_col < end_col
        fits = not strict or current_col + w <= end_col

        if in_range and fits:
            if pending_ansi:
                result.append(pending_ansi)
                pending_ansi = ""
            result.append(char)
            result_width += w

        current_col += w
        if current_col >= end_col:
            break

        i += 1

    return {"text": "".join(result), "width": result_width}


def extract_segments(
    line: str,
    before_end: int,
    after_start: int,
    after_len: int,
    strict_after: bool = False,
) -> dict:
    """Extract 'before' and 'after' segments from a line in a single pass.

    Used for overlay compositing where we need content before and after
    the overlay region.

    Returns dict with:
    - before: text before the overlay
    - beforeWidth: visible width of before text
    - after: text after the overlay
    - afterWidth: visible width of after text
    """
    before = []
    before_width = 0
    after = []
    after_width = 0
    current_col = 0
    i = 0
    pending_ansi_before = ""
    after_started = False
    after_end = after_start + after_len

    tracker = AnsiCodeTracker()

    while i < len(line):
        ansi = extract_ansi_code(line, i)
        if ansi:
            tracker.process(ansi["code"])
            if current_col < before_end:
                pending_ansi_before += ansi["code"]
            elif current_col >= after_start and current_col < after_end and after_started:
                after.append(ansi["code"])
            i += ansi["length"]
            continue

        char = line[i]
        w = char_width(char)

        if current_col < before_end:
            if pending_ansi_before:
                before.append(pending_ansi_before)
                pending_ansi_before = ""
            before.append(char)
            before_width += w
        elif current_col >= after_start and current_col < after_end:
            fits = not strict_after or current_col + w <= after_end
            if fits:
                if not after_started:
                    after.append(tracker.get_active_codes())
                    after_started = True
                after.append(char)
                after_width += w

        current_col += w
        if after_len <= 0:
            if current_col >= before_end:
                break
        else:
            if current_col >= after_end:
                break

        i += 1

    return {
        "before": "".join(before),
        "beforeWidth": before_width,
        "after": "".join(after),
        "afterWidth": after_width,
    }


def apply_background_to_line(text: str, width: int, bg_fn: callable) -> str:
    """Apply background color to a line, padding to full width.

    Args:
        text: Line of text (may contain ANSI codes)
        width: Total width to pad to
        bg_fn: Background color function

    Returns:
        Line with background applied and padded to width
    """
    # Calculate padding needed
    vis_len = visible_width(text)
    padding_needed = max(0, width - vis_len)
    padding = " " * padding_needed

    # Apply background to content + padding
    with_padding = text + padding
    return bg_fn(with_padding)


def split_into_tokens_with_ansi(text: str) -> list[str]:
    """Split text into tokens while keeping ANSI codes attached."""
    tokens = []
    current = ""
    pending_ansi = ""
    in_whitespace = False
    i = 0

    while i < len(text):
        ansi = extract_ansi_code(text, i)
        if ansi:
            pending_ansi += ansi["code"]
            i += ansi["length"]
            continue

        char = text[i]
        char_is_space = char == " "

        if char_is_space != in_whitespace and current:
            tokens.append(current)
            current = ""

        if pending_ansi:
            current += pending_ansi
            pending_ansi = ""

        in_whitespace = char_is_space
        current += char
        i += 1

    if pending_ansi:
        current += pending_ansi

    if current:
        tokens.append(current)

    return tokens


def wrap_text_with_ansi(text: str, width: int) -> list[str]:
    """Wrap text with ANSI codes preserved.

    Only does word wrapping - NO padding, NO background colors.
    Returns lines where each line is <= width visible chars.

    Args:
        text: Text to wrap (may contain ANSI codes and newlines)
        width: Maximum visible width per line

    Returns:
        Array of wrapped lines (NOT padded to width)
    """
    if not text:
        return [""]

    # Handle newlines by processing each line separately
    input_lines = text.split("\n")
    result = []
    tracker = AnsiCodeTracker()

    for input_line in input_lines:
        # Prepend active ANSI codes from previous lines
        prefix = tracker.get_active_codes() if result else ""
        wrapped = _wrap_single_line(prefix + input_line, width)
        result.extend(wrapped)
        # Update tracker with codes from this line
        _update_tracker_from_text(input_line, tracker)

    return result if result else [""]


def _update_tracker_from_text(text: str, tracker: AnsiCodeTracker) -> None:
    """Update tracker state from text containing ANSI codes."""
    i = 0
    while i < len(text):
        ansi = extract_ansi_code(text, i)
        if ansi:
            tracker.process(ansi["code"])
            i += ansi["length"]
        else:
            i += 1


def _wrap_single_line(line: str, width: int) -> list[str]:
    """Wrap a single line of text."""
    if not line:
        return [""]

    if visible_width(line) <= width:
        return [line]

    wrapped = []
    tracker = AnsiCodeTracker()
    tokens = split_into_tokens_with_ansi(line)

    current_line = ""
    current_visible = 0

    for token in tokens:
        token_width = visible_width(token)
        is_whitespace = token.strip() == ""

        # Token itself is too long - break it
        if token_width > width and not is_whitespace:
            if current_line:
                # Add reset for underline only
                line_end_reset = tracker.get_line_end_reset()
                if line_end_reset:
                    current_line += line_end_reset
                wrapped.append(current_line)
                current_line = ""
                current_visible = 0

            # Break long token character by character
            broken = _break_long_word(token, width, tracker)
            wrapped.extend(broken[:-1])
            current_line = broken[-1]
            current_visible = visible_width(current_line)
            continue

        # Check if adding this token would exceed width
        if current_visible + token_width > width and current_visible > 0:
            line_to_wrap = current_line.rstrip()
            line_end_reset = tracker.get_line_end_reset()
            if line_end_reset:
                line_to_wrap += line_end_reset
            wrapped.append(line_to_wrap)

            if is_whitespace:
                # Don't start new line with whitespace
                current_line = tracker.get_active_codes()
                current_visible = 0
            else:
                current_line = tracker.get_active_codes() + token
                current_visible = token_width
        else:
            current_line += token
            current_visible += token_width

        _update_tracker_from_text(token, tracker)

    if current_line:
        wrapped.append(current_line)

    return [line.rstrip() for line in wrapped] if wrapped else [""]


def _break_long_word(word: str, width: int, tracker: AnsiCodeTracker) -> list[str]:
    """Break a word that's longer than the available width."""
    lines = []
    current_line = tracker.get_active_codes()
    current_width = 0

    # First, separate ANSI codes from visible content
    segments = []
    i = 0
    while i < len(word):
        ansi = extract_ansi_code(word, i)
        if ansi:
            segments.append(("ansi", ansi["code"]))
            i += ansi["length"]
        else:
            end = i
            while end < len(word) and not extract_ansi_code(word, end):
                end += 1
            text_portion = word[i:end]
            for char in text_portion:
                segments.append(("char", char))
            i = end

    # Process segments
    for seg_type, seg_value in segments:
        if seg_type == "ansi":
            current_line += seg_value
            tracker.process(seg_value)
            continue

        char = seg_value
        char_w = char_width(char)

        if current_width + char_w > width:
            line_end_reset = tracker.get_line_end_reset()
            if line_end_reset:
                current_line += line_end_reset
            lines.append(current_line)
            current_line = tracker.get_active_codes()
            current_width = 0

        current_line += char
        current_width += char_w

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def is_whitespace_char(char: str) -> bool:
    """Check if a character is whitespace."""
    return char.isspace()


def is_punctuation_char(char: str) -> bool:
    """Check if a character is punctuation."""
    return char in "(){}[]<>.,;:'\"!?+-=*/\\|&%^$#@~`"


def grapheme_next(text: str, pos: int) -> int:
    """Get the position of the next grapheme cluster."""
    if pos >= len(text):
        return pos

    # Skip ANSI codes
    while pos < len(text) and text[pos] == "\x1b":
        ansi = extract_ansi_code(text, pos)
        if ansi:
            pos += ansi["length"]
        else:
            pos += 1

    if pos >= len(text):
        return pos

    # Move to next character
    pos += 1

    # Skip combining characters
    while pos < len(text):
        char = text[pos]
        if char_width(char) == 0 and char != "\x1b":
            pos += 1
        else:
            break

    return pos


def grapheme_prev(text: str, pos: int) -> int:
    """Get the position of the previous grapheme cluster."""
    if pos <= 0:
        return 0

    pos -= 1

    # Skip ANSI codes going backwards
    while pos > 0 and text[pos] in "mGKHJ\x07\\":
        # Check for end of ANSI sequence
        i = pos - 1
        while i > 0 and text[i] != "\x1b":
            i -= 1
        if i >= 0 and text[i] == "\x1b":
            pos = i - 1
        else:
            break

    if pos < 0:
        return 0

    # Skip combining characters going backwards
    while pos > 0:
        char = text[pos]
        if char_width(char) == 0:
            pos -= 1
        else:
            break

    return pos
