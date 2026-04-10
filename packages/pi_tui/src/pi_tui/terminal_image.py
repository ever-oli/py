"""Terminal image display support.

Provides image rendering in terminals using Kitty or iTerm2 graphics protocols.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Optional

ImageProtocol = Optional[str]  # "kitty" | "iterm2" | None


@dataclass
class TerminalCapabilities:
    """Detected terminal capabilities."""

    images: ImageProtocol
    true_color: bool
    hyperlinks: bool


@dataclass
class CellDimensions:
    """Cell dimensions in pixels."""

    width_px: int
    height_px: int


@dataclass
class ImageDimensions:
    """Image dimensions in pixels."""

    width_px: int
    height_px: int


@dataclass
class ImageRenderOptions:
    """Options for image rendering."""

    max_width_cells: int | None = None
    max_height_cells: int | None = None
    preserve_aspect_ratio: bool = True
    image_id: int | None = None  # Kitty image ID


@dataclass
class ImageRenderResult:
    """Result of image rendering."""

    sequence: str
    rows: int
    image_id: int | None = None


# Default cell dimensions
_cell_dimensions = CellDimensions(width_px=9, height_px=18)
_cached_capabilities: TerminalCapabilities | None = None


KITTY_PREFIX = "\x1b_G"
ITERM2_PREFIX = "\x1b]1337;File="


def get_cell_dimensions() -> CellDimensions:
    """Get current cell dimensions."""
    return _cell_dimensions


def set_cell_dimensions(dims: CellDimensions) -> None:
    """Set cell dimensions."""
    global _cell_dimensions
    _cell_dimensions = dims


def detect_capabilities() -> TerminalCapabilities:
    """Detect terminal capabilities from environment variables."""
    term_program = (os.environ.get("TERM_PROGRAM", "")).lower()
    term = (os.environ.get("TERM", "")).lower()
    color_term = (os.environ.get("COLORTERM", "")).lower()

    # Kitty terminal
    if os.environ.get("KITTY_WINDOW_ID") or term_program == "kitty":
        return TerminalCapabilities(images="kitty", true_color=True, hyperlinks=True)

    # Ghostty
    if term_program == "ghostty" or "ghostty" in term or os.environ.get("GHOSTTY_RESOURCES_DIR"):
        return TerminalCapabilities(images="kitty", true_color=True, hyperlinks=True)

    # WezTerm
    if os.environ.get("WEZTERM_PANE") or term_program == "wezterm":
        return TerminalCapabilities(images="kitty", true_color=True, hyperlinks=True)

    # iTerm2
    if os.environ.get("ITERM_SESSION_ID") or term_program == "iterm.app":
        return TerminalCapabilities(images="iterm2", true_color=True, hyperlinks=True)

    # VS Code
    if term_program == "vscode":
        return TerminalCapabilities(images=None, true_color=True, hyperlinks=True)

    # Alacritty
    if term_program == "alacritty":
        return TerminalCapabilities(images=None, true_color=True, hyperlinks=True)

    true_color = color_term in ("truecolor", "24bit")
    return TerminalCapabilities(images=None, true_color=true_color, hyperlinks=True)


def get_capabilities() -> TerminalCapabilities:
    """Get cached terminal capabilities."""
    global _cached_capabilities
    if _cached_capabilities is None:
        _cached_capabilities = detect_capabilities()
    return _cached_capabilities


def reset_capabilities_cache() -> None:
    """Reset the capabilities cache."""
    global _cached_capabilities
    _cached_capabilities = None


def is_image_line(line: str) -> bool:
    """Check if a line contains an image escape sequence."""
    # Fast path: sequence at line start (single-row images)
    if line.startswith(KITTY_PREFIX) or line.startswith(ITERM2_PREFIX):
        return True
    # Slow path: sequence elsewhere (multi-row images have cursor-up prefix)
    return KITTY_PREFIX in line or ITERM2_PREFIX in line


def allocate_image_id() -> int:
    """Generate a random image ID for Kitty graphics protocol.

    Uses random IDs to avoid collisions between different module instances
    (e.g., main app vs extensions).
    """
    return random.randint(1, 0xFFFFFFFF)


def encode_kitty(
    base64_data: str, columns: int | None = None, rows: int | None = None, image_id: int | None = None
) -> str:
    """Encode image data using Kitty graphics protocol.

    Args:
        base64_data: Base64-encoded image data
        columns: Number of columns to display
        rows: Number of rows to display
        image_id: Optional image ID for reuse/replacement

    Returns:
        Kitty graphics escape sequence
    """
    CHUNK_SIZE = 4096

    params = ["a=T", "f=100", "q=2"]
    if columns is not None:
        params.append(f"c={columns}")
    if rows is not None:
        params.append(f"r={rows}")
    if image_id is not None:
        params.append(f"i={image_id}")

    if len(base64_data) <= CHUNK_SIZE:
        return f"\x1b_G{','.join(params)};{base64_data}\x1b\\"

    chunks = []
    offset = 0
    is_first = True

    while offset < len(base64_data):
        chunk = base64_data[offset : offset + CHUNK_SIZE]
        is_last = offset + CHUNK_SIZE >= len(base64_data)

        if is_first:
            chunks.append(f"\x1b_G{','.join(params)},m=1;{chunk}\x1b\\")
            is_first = False
        elif is_last:
            chunks.append(f"\x1b_Gm=0;{chunk}\x1b\\")
        else:
            chunks.append(f"\x1b_Gm=1;{chunk}\x1b\\")

        offset += CHUNK_SIZE

    return "".join(chunks)


def delete_kitty_image(image_id: int) -> str:
    """Delete a Kitty graphics image by ID.

    Uses uppercase 'I' to also free the image data.
    """
    return f"\x1b_Ga=d,d=I,i={image_id}\x1b\\"


def delete_all_kitty_images() -> str:
    """Delete all visible Kitty graphics images.

    Uses uppercase 'A' to also free the image data.
    """
    return "\x1b_Ga=d,d=A\x1b\\"


def encode_iterm2(
    base64_data: str,
    width: int | None = None,
    height: int | None = None,
    name: str | None = None,
    preserve_aspect_ratio: bool = True,
    inline: bool = True,
) -> str:
    """Encode image data using iTerm2 graphics protocol.

    Args:
        base64_data: Base64-encoded image data
        width: Width (cells or px with 'px' suffix)
        height: Height (cells or px with 'px' suffix)
        name: Image name
        preserve_aspect_ratio: Whether to preserve aspect ratio
        inline: Whether to display inline

    Returns:
        iTerm2 graphics escape sequence
    """
    params = [f"inline={1 if inline else 0}"]

    if width is not None:
        params.append(f"width={width}")
    if height is not None:
        params.append(f"height={height}")
    if name:
        import base64

        name_b64 = base64.b64encode(name.encode()).decode()
        params.append(f"name={name_b64}")
    if not preserve_aspect_ratio:
        params.append("preserveAspectRatio=0")

    return f"\x1b]1337;File={';'.join(params)}:{base64_data}\x07"


def calculate_image_rows(
    image_dimensions: ImageDimensions, target_width_cells: int, cell_dimensions: CellDimensions | None = None
) -> int:
    """Calculate the number of rows needed to display an image.

    Args:
        image_dimensions: Image dimensions in pixels
        target_width_cells: Target width in terminal columns
        cell_dimensions: Cell dimensions (uses default if None)

    Returns:
        Number of rows needed
    """
    if cell_dimensions is None:
        cell_dimensions = _cell_dimensions

    target_width_px = target_width_cells * cell_dimensions.width_px
    scale = target_width_px / image_dimensions.width_px
    scaled_height_px = image_dimensions.height_px * scale
    rows = int(scaled_height_px / cell_dimensions.height_px)
    return max(1, rows)


def get_png_dimensions(base64_data: str) -> ImageDimensions | None:
    """Extract dimensions from PNG base64 data."""
    try:
        import base64

        data = base64.b64decode(base64_data)

        if len(data) < 24:
            return None

        # PNG signature
        if data[0] != 0x89 or data[1] != 0x50 or data[2] != 0x4E or data[3] != 0x47:
            return None

        # Width and height are at offsets 16-23 (big-endian)
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")

        return ImageDimensions(width_px=width, height_px=height)
    except Exception:
        return None


def get_jpeg_dimensions(base64_data: str) -> ImageDimensions | None:
    """Extract dimensions from JPEG base64 data."""
    try:
        import base64

        data = base64.b64decode(base64_data)

        if len(data) < 2:
            return None

        # JPEG SOI marker
        if data[0] != 0xFF or data[1] != 0xD8:
            return None

        offset = 2
        while offset < len(data) - 9:
            if data[offset] != 0xFF:
                offset += 1
                continue

            marker = data[offset + 1]

            # SOF markers (0xC0-0xC2)
            if 0xC0 <= marker <= 0xC2:
                if offset + 9 >= len(data):
                    return None
                height = int.from_bytes(data[offset + 5 : offset + 7], "big")
                width = int.from_bytes(data[offset + 7 : offset + 9], "big")
                return ImageDimensions(width_px=width, height_px=height)

            if offset + 3 >= len(data):
                return None

            length = int.from_bytes(data[offset + 2 : offset + 4], "big")
            if length < 2:
                return None

            offset += 2 + length

        return None
    except Exception:
        return None


def get_gif_dimensions(base64_data: str) -> ImageDimensions | None:
    """Extract dimensions from GIF base64 data."""
    try:
        import base64

        data = base64.b64decode(base64_data)

        if len(data) < 10:
            return None

        sig = data[:6].decode("ascii", errors="ignore")
        if sig not in ("GIF87a", "GIF89a"):
            return None

        # Width and height are at offsets 6-9 (little-endian)
        width = int.from_bytes(data[6:8], "little")
        height = int.from_bytes(data[8:10], "little")

        return ImageDimensions(width_px=width, height_px=height)
    except Exception:
        return None


def get_webp_dimensions(base64_data: str) -> ImageDimensions | None:
    """Extract dimensions from WebP base64 data."""
    try:
        import base64

        data = base64.b64decode(base64_data)

        if len(data) < 30:
            return None

        riff = data[:4].decode("ascii", errors="ignore")
        webp = data[8:12].decode("ascii", errors="ignore")
        if riff != "RIFF" or webp != "WEBP":
            return None

        chunk = data[12:16].decode("ascii", errors="ignore")

        if chunk == "VP8 ":
            if len(data) < 30:
                return None
            # VP8 bitstream
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return ImageDimensions(width_px=width, height_px=height)

        elif chunk == "VP8L":
            if len(data) < 25:
                return None
            # VP8L bitstream
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return ImageDimensions(width_px=width, height_px=height)

        elif chunk == "VP8X":
            if len(data) < 30:
                return None
            # VP8X extended
            width = (data[24] | (data[25] << 8) | (data[26] << 16)) + 1
            height = (data[27] | (data[28] << 8) | (data[29] << 16)) + 1
            return ImageDimensions(width_px=width, height_px=height)

        return None
    except Exception:
        return None


def get_image_dimensions(base64_data: str, mime_type: str) -> ImageDimensions | None:
    """Extract dimensions from image base64 data based on MIME type.

    Args:
        base64_data: Base64-encoded image data
        mime_type: MIME type (image/png, image/jpeg, etc.)

    Returns:
        Image dimensions or None if not detectable
    """
    if mime_type == "image/png":
        return get_png_dimensions(base64_data)
    elif mime_type == "image/jpeg":
        return get_jpeg_dimensions(base64_data)
    elif mime_type == "image/gif":
        return get_gif_dimensions(base64_data)
    elif mime_type == "image/webp":
        return get_webp_dimensions(base64_data)
    return None


def render_image(
    base64_data: str, image_dimensions: ImageDimensions, options: ImageRenderOptions = None
) -> ImageRenderResult | None:
    """Render an image for terminal display.

    Args:
        base64_data: Base64-encoded image data
        image_dimensions: Image dimensions in pixels
        options: Rendering options

    Returns:
        Render result with escape sequence and row count, or None if not supported
    """
    if options is None:
        options = ImageRenderOptions()

    caps = get_capabilities()
    if not caps.images:
        return None

    max_width = options.max_width_cells or 80
    rows = calculate_image_rows(image_dimensions, max_width)

    if caps.images == "kitty":
        sequence = encode_kitty(base64_data, columns=max_width, rows=rows, image_id=options.image_id)
        return ImageRenderResult(sequence=sequence, rows=rows, image_id=options.image_id)

    if caps.images == "iterm2":
        sequence = encode_iterm2(
            base64_data, width=max_width, height="auto", preserve_aspect_ratio=options.preserve_aspect_ratio
        )
        return ImageRenderResult(sequence=sequence, rows=rows)

    return None


def image_fallback(mime_type: str, dimensions: ImageDimensions | None = None, filename: str | None = None) -> str:
    """Generate a fallback text representation of an image.

    Args:
        mime_type: MIME type of the image
        dimensions: Optional image dimensions
        filename: Optional filename

    Returns:
        Text fallback for the image
    """
    parts = []
    if filename:
        parts.append(filename)
    parts.append(f"[{mime_type}]")
    if dimensions:
        parts.append(f"{dimensions.width_px}x{dimensions.height_px}")
    return f"[Image: {' '.join(parts)}]"
