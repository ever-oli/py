"""Web fetch tool for extracting webpage content."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin


async def web_fetch_tool(
    url: str,
    extract_mode: str = "markdown",
    max_chars: int | None = None,
    include_links: bool = True,
    include_images: bool = False,
) -> dict[str, Any]:
    """Fetch and extract content from a webpage.

    Args:
        url: URL to fetch
        extract_mode: Extraction mode - "markdown", "text", or "html"
        max_chars: Maximum characters to return (truncates when exceeded)
        include_links: Whether to include links in markdown output
        include_images: Whether to include image references

    Returns:
        Extracted content with metadata

    Example:
        >>> result = await web_fetch_tool(
        ...     url="https://example.com/article",
        ...     extract_mode="markdown",
        ...     max_chars=5000
        ... )
    """
    try:
        import httpx
    except ImportError:
        return {
            "success": False,
            "error": "httpx not installed. Run: pip install httpx",
            "content": "",
            "url": url,
        }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Handle different content types
            if "application/json" in content_type:
                return {
                    "success": True,
                    "url": str(response.url),
                    "title": "",
                    "content": response.text,
                    "content_type": "json",
                }

            html = response.text

            if extract_mode == "html":
                content = html
            elif extract_mode == "text":
                content = _extract_text(html)
            else:  # markdown
                content = _html_to_markdown(html, url, include_links, include_images)

            # Extract title
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = _clean_html_text(title_match.group(1)) if title_match else ""

            # Truncate if needed
            if max_chars and len(content) > max_chars:
                content = content[:max_chars] + "\n\n[Content truncated...]"

            return {
                "success": True,
                "url": str(response.url),
                "title": title,
                "content": content,
                "content_type": extract_mode,
            }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
            "content": "",
            "url": url,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": "",
            "url": url,
        }


def _extract_text(html: str) -> str:
    """Extract plain text from HTML."""
    # Remove script and style tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Replace common block elements with newlines
    text = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Clean up whitespace
    text = _clean_html_text(text)

    return text


def _html_to_markdown(html: str, base_url: str, include_links: bool, include_images: bool) -> str:
    """Convert HTML to markdown."""
    from html.parser import HTMLParser

    class MarkdownConverter(HTMLParser):
        def __init__(self, base_url: str):
            super().__init__()
            self.base_url = base_url
            self.result = []
            self.in_skip = 0
            self.link_url = None
            self.link_text = []
            self.list_stack = []
            self.in_pre = False

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)

            if tag in ("script", "style", "nav", "header", "footer", "aside"):
                self.in_skip += 1
                return

            if tag == "pre":
                self.in_pre = True
                self.result.append("\n```\n")
            elif tag == "code" and not self.in_pre:
                self.result.append("`")
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(tag[1])
                self.result.append("\n" + "#" * level + " ")
            elif tag == "p":
                self.result.append("\n\n")
            elif tag == "br":
                self.result.append("\n")
            elif tag == "a" and include_links:
                href = attrs_dict.get("href", "")
                if href:
                    self.link_url = urljoin(self.base_url, href)
                    self.link_text = []
            elif tag == "img" and include_images:
                src = attrs_dict.get("src", "")
                alt = attrs_dict.get("alt", "")
                if src:
                    full_src = urljoin(self.base_url, src)
                    self.result.append(f"![{alt}]({full_src})")
            elif tag in ("ul", "ol"):
                self.list_stack.append(tag)
            elif tag == "li":
                indent = "  " * (len(self.list_stack) - 1)
                marker = "- " if self.list_stack[-1] == "ul" else "1. "
                self.result.append("\n" + indent + marker)
            elif tag in ("strong", "b"):
                self.result.append("**")
            elif tag in ("em", "i"):
                self.result.append("*")
            elif tag == "blockquote":
                self.result.append("\n> ")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "header", "footer", "aside"):
                self.in_skip -= 1
                return

            if self.in_skip > 0:
                return

            if tag == "pre":
                self.in_pre = False
                self.result.append("\n```\n")
            elif tag == "code" and not self.in_pre:
                self.result.append("`")
            elif tag in ("strong", "b"):
                self.result.append("**")
            elif tag in ("em", "i"):
                self.result.append("*")
            elif tag == "a" and self.link_url:
                text = "".join(self.link_text).strip()
                if text:
                    self.result.append(f"[{text}]({self.link_url})")
                self.link_url = None
                self.link_text = []
            elif tag in ("ul", "ol"):
                if self.list_stack:
                    self.list_stack.pop()
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div"):
                self.result.append("\n")

        def handle_data(self, data):
            if self.in_skip > 0:
                return

            if self.link_url is not None:
                self.link_text.append(data)
            else:
                if self.in_pre:
                    self.result.append(data)
                else:
                    # Clean whitespace but preserve structure
                    cleaned = " ".join(data.split())
                    if cleaned:
                        self.result.append(cleaned)

        def get_result(self) -> str:
            text = "".join(self.result)
            # Clean up multiple newlines
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

    converter = MarkdownConverter(base_url)
    try:
        converter.feed(html)
    except Exception:
        # Fallback to text extraction
        return _extract_text(html)

    return converter.get_result()


def _clean_html_text(text: str) -> str:
    """Clean up HTML text by unescaping and normalizing whitespace."""
    import html

    text = html.unescape(text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def create_web_fetch_tool(cwd: str | None = None) -> dict[str, Any]:
    """Create a web fetch tool instance."""
    return {
        "name": "web_fetch",
        "description": """Fetch and extract readable content from a webpage.

Retrieves web pages and converts them to markdown, text, or returns raw HTML.
Useful for reading documentation, articles, or any web content.
""",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch (HTTP or HTTPS)",
                },
                "extract_mode": {
                    "type": "string",
                    "enum": ["markdown", "text", "html"],
                    "default": "markdown",
                    "description": "Content extraction mode",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (truncates when exceeded)",
                },
                "include_links": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include links in markdown output",
                },
                "include_images": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include image references in output",
                },
            },
            "required": ["url"],
        },
        "execute": web_fetch_tool,
    }


web_fetch_tool_definition = create_web_fetch_tool()
