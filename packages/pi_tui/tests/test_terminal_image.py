"""Tests for terminal image module."""

from pi_tui.terminal_image import (
    ITERM2_PREFIX,
    KITTY_PREFIX,
    CellDimensions,
    ImageDimensions,
    allocate_image_id,
    calculate_image_rows,
    delete_all_kitty_images,
    delete_kitty_image,
    detect_capabilities,
    encode_iterm2,
    encode_kitty,
    get_gif_dimensions,
    get_jpeg_dimensions,
    get_png_dimensions,
    get_webp_dimensions,
    is_image_line,
    render_image,
)


class TestDetectCapabilities:
    """Tests for terminal capability detection."""

    def test_kitty_detection(self, monkeypatch):
        """Should detect Kitty terminal."""
        monkeypatch.setenv("KITTY_WINDOW_ID", "1")
        caps = detect_capabilities()
        assert caps.images == "kitty"
        assert caps.true_color is True

    def test_ghostty_detection(self, monkeypatch):
        """Should detect Ghostty terminal."""
        monkeypatch.setenv("TERM_PROGRAM", "ghostty")
        caps = detect_capabilities()
        assert caps.images == "kitty"
        assert caps.true_color is True

    def test_wezterm_detection(self, monkeypatch):
        """Should detect WezTerm terminal."""
        monkeypatch.setenv("WEZTERM_PANE", "1")
        caps = detect_capabilities()
        assert caps.images == "kitty"

    def test_iterm_detection(self, monkeypatch):
        """Should detect iTerm2 terminal."""
        monkeypatch.setenv("ITERM_SESSION_ID", "w0t0p0:123")
        caps = detect_capabilities()
        assert caps.images == "iterm2"

    def test_vscode_detection(self, monkeypatch):
        """Should detect VS Code terminal."""
        monkeypatch.setenv("TERM_PROGRAM", "vscode")
        caps = detect_capabilities()
        assert caps.images is None
        assert caps.true_color is True

    def test_truecolor_detection(self, monkeypatch):
        """Should detect truecolor support."""
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        caps = detect_capabilities()
        assert caps.true_color is True


class TestKittyEncoding:
    """Tests for Kitty graphics protocol encoding."""

    def test_encode_simple(self):
        """Should encode simple image data."""
        data = "base64encodeddata"
        result = encode_kitty(data)

        assert result.startswith(KITTY_PREFIX)
        assert "base64encodeddata" in result
        assert result.endswith("\x1b\\")

    def test_encode_with_dimensions(self):
        """Should include dimensions when specified."""
        data = "base64"
        result = encode_kitty(data, columns=10, rows=5)

        assert "c=10" in result
        assert "r=5" in result

    def test_encode_with_id(self):
        """Should include image ID when specified."""
        data = "base64"
        result = encode_kitty(data, image_id=42)

        assert "i=42" in result

    def test_encode_chunks_large_data(self):
        """Should chunk large data."""
        # Create data larger than chunk size (4096)
        data = "A" * 5000
        result = encode_kitty(data)

        # Should have multiple sequences
        assert result.count(KITTY_PREFIX) > 1
        # Should have m=1 for continuation
        assert "m=1" in result


class TestIterm2Encoding:
    """Tests for iTerm2 graphics protocol encoding."""

    def test_encode_simple(self):
        """Should encode simple image data."""
        data = "base64encodeddata"
        result = encode_iterm2(data)

        assert result.startswith(ITERM2_PREFIX)
        assert "base64encodeddata" in result
        assert result.endswith("\x07")

    def test_encode_with_dimensions(self):
        """Should include dimensions when specified."""
        data = "base64"
        result = encode_iterm2(data, width=100, height=50)

        assert "width=100" in result
        assert "height=50" in result

    def test_encode_not_inline(self):
        """Should support non-inline mode."""
        data = "base64"
        result = encode_iterm2(data, inline=False)

        assert "inline=0" in result

    def test_encode_without_preserve_aspect(self):
        """Should support disabling aspect ratio preservation."""
        data = "base64"
        result = encode_iterm2(data, preserve_aspect_ratio=False)

        assert "preserveAspectRatio=0" in result


class TestIsImageLine:
    """Tests for is_image_line function."""

    def test_kitty_image_line(self):
        """Should detect Kitty image lines."""
        line = "\x1b_Gf=100;base64\x1b\\"
        assert is_image_line(line) is True

    def test_iterm_image_line(self):
        """Should detect iTerm2 image lines."""
        line = "\x1b]1337;File=inline=1:data\x07"
        assert is_image_line(line) is True

    def test_regular_line(self):
        """Should not detect regular lines."""
        line = "Hello world"
        assert is_image_line(line) is False

    def test_line_with_cursor_prefix(self):
        """Should detect images with cursor-up prefix."""
        line = "\x1b[A\x1b_Gf=100;base64\x1b\\"
        assert is_image_line(line) is True


class TestImageIdAllocation:
    """Tests for image ID allocation."""

    def test_allocate_returns_int(self):
        """Should return integer."""
        img_id = allocate_image_id()
        assert isinstance(img_id, int)

    def test_allocate_returns_positive(self):
        """Should return positive integer."""
        img_id = allocate_image_id()
        assert img_id > 0

    def test_allocate_returns_different_ids(self):
        """Should return different IDs."""
        id1 = allocate_image_id()
        id2 = allocate_image_id()
        assert id1 != id2


class TestCalculateImageRows:
    """Tests for calculate_image_rows function."""

    def test_basic_calculation(self):
        """Should calculate rows based on aspect ratio."""
        dims = ImageDimensions(width_px=90, height_px=18)  # 5:1 ratio
        cell = CellDimensions(width_px=9, height_px=18)

        rows = calculate_image_rows(dims, 10, cell)

        # 90px / 9px = 10 columns, scaled height = 18px / 18px = 1 row
        assert rows == 1

    def test_wide_image(self):
        """Should handle wide images."""
        dims = ImageDimensions(width_px=180, height_px=36)
        cell = CellDimensions(width_px=9, height_px=18)

        rows = calculate_image_rows(dims, 10, cell)

        # Same aspect ratio, should be 1 row
        assert rows == 1

    def test_returns_at_least_one(self):
        """Should return at least 1 row."""
        dims = ImageDimensions(width_px=9, height_px=9)
        cell = CellDimensions(width_px=9, height_px=18)

        rows = calculate_image_rows(dims, 10, cell)

        assert rows >= 1


class TestPngDimensions:
    """Tests for PNG dimension extraction."""

    def test_extract_valid_png(self):
        """Should extract dimensions from valid PNG."""
        import base64

        # Minimal PNG: 1x1 pixel
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        b64 = base64.b64encode(png_data).decode()

        dims = get_png_dimensions(b64)

        assert dims is not None
        assert dims.width_px == 1
        assert dims.height_px == 1

    def test_invalid_png(self):
        """Should return None for invalid PNG."""
        import base64

        invalid_data = base64.b64encode(b"not a png").decode()

        dims = get_png_dimensions(invalid_data)

        assert dims is None


class TestJpegDimensions:
    """Tests for JPEG dimension extraction."""

    def test_extract_valid_jpeg(self):
        """Should extract dimensions from valid JPEG."""
        import base64

        # Minimal valid JPEG
        jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xd9"
        b64 = base64.b64encode(jpeg_data).decode()

        dims = get_jpeg_dimensions(b64)

        assert dims is not None
        assert dims.width_px == 1
        assert dims.height_px == 1

    def test_invalid_jpeg(self):
        """Should return None for invalid JPEG."""
        import base64

        invalid_data = base64.b64encode(b"not a jpeg").decode()

        dims = get_jpeg_dimensions(invalid_data)

        assert dims is None


class TestGifDimensions:
    """Tests for GIF dimension extraction."""

    def test_extract_gif87a(self):
        """Should extract dimensions from GIF87a."""
        import base64

        # Minimal GIF87a: 1x1 pixel
        gif_data = b"GIF87a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        b64 = base64.b64encode(gif_data).decode()

        dims = get_gif_dimensions(b64)

        assert dims is not None
        assert dims.width_px == 1
        assert dims.height_px == 1

    def test_extract_gif89a(self):
        """Should extract dimensions from GIF89a."""
        import base64

        # Minimal GIF89a: 1x1 pixel
        gif_data = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        b64 = base64.b64encode(gif_data).decode()

        dims = get_gif_dimensions(b64)

        assert dims is not None
        assert dims.width_px == 1
        assert dims.height_px == 1


class TestWebpDimensions:
    """Tests for WebP dimension extraction."""

    def test_extract_vp8(self):
        """Should extract dimensions from VP8 WebP."""
        import base64

        # VP8 WebP signature + dimensions (1x1)
        webp_data = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\x30\x01\x00\x9d\x01\x2a\x01\x00\x01\x00\x00\x34\x25\xa4\x00\x03\x70\x00\xfe\xfb\x94\x00\x00"
        b64 = base64.b64encode(webp_data).decode()

        dims = get_webp_dimensions(b64)

        assert dims is not None
        assert dims.width_px == 1
        assert dims.height_px == 1


class TestDeleteKittyImage:
    """Tests for Kitty image deletion."""

    def test_delete_single_image(self):
        """Should create delete sequence for single image."""
        result = delete_kitty_image(42)

        assert KITTY_PREFIX in result
        assert "a=d" in result
        assert "d=I" in result
        assert "i=42" in result

    def test_delete_all_images(self):
        """Should create delete sequence for all images."""
        result = delete_all_kitty_images()

        assert KITTY_PREFIX in result
        assert "a=d" in result
        assert "d=A" in result


class TestRenderImage:
    """Tests for render_image function."""

    def test_render_no_support(self, monkeypatch):
        """Should return None if no image support."""
        monkeypatch.setenv("TERM_PROGRAM", "alacritty")

        dims = ImageDimensions(width_px=100, height_px=50)
        result = render_image("base64data", dims)

        assert result is None

    def test_render_kitty(self, monkeypatch):
        """Should render Kitty graphics."""
        from pi_tui import terminal_image

        monkeypatch.setenv("KITTY_WINDOW_ID", "1")
        terminal_image.reset_capabilities_cache()  # Reset cache

        dims = ImageDimensions(width_px=90, height_px=18)
        result = render_image("base64data", dims)

        assert result is not None
        assert KITTY_PREFIX in result.sequence
        assert result.rows >= 1
