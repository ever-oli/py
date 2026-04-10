"""Attachment utilities for Pi Web UI.

Ported from TypeScript attachment-utils.ts
"""

from __future__ import annotations

import base64
import io
import mimetypes
import uuid
from dataclasses import dataclass
from typing import Any

from pi_ai import ImageContent, TextContent


@dataclass
class Attachment:
    """File attachment."""

    id: str
    type: str  # "image" or "document"
    filename: str
    content_type: str
    size: int
    content: str  # base64 encoded
    extracted_text: str | None = None
    preview: str | None = None  # base64 preview image


async def process_attachment(
    content: bytes,
    filename: str,
    content_type: str | None = None,
) -> Attachment:
    """Process an uploaded file into an attachment.

    Args:
        content: Raw file bytes
        filename: Original filename
        content_type: MIME type (detected if not provided)

    Returns:
        Processed attachment
    """
    if content_type is None:
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = "application/octet-stream"

    # Generate ID
    att_id = f"{filename}_{uuid.uuid4().hex[:8]}"

    # Encode to base64
    base64_content = base64.b64encode(content).decode("utf-8")

    # Determine type
    if content_type.startswith("image/"):
        att_type = "image"
        preview = base64_content  # For images, preview is the content itself
        extracted_text = None
    else:
        att_type = "document"
        preview = None

        # Try to extract text for supported document types
        if content_type == "application/pdf":
            extracted_text = await extract_pdf_text(content, filename)
        elif content_type in [
            "text/plain",
            "text/markdown",
            "text/html",
            "text/css",
            "text/javascript",
            "application/json",
            "application/xml",
        ]:
            try:
                extracted_text = content.decode("utf-8")
            except UnicodeDecodeError:
                extracted_text = None
        else:
            extracted_text = None

    return Attachment(
        id=att_id,
        type=att_type,
        filename=filename,
        content_type=content_type,
        size=len(content),
        content=base64_content,
        extracted_text=extracted_text,
        preview=preview,
    )


async def extract_pdf_text(content: bytes, filename: str) -> str | None:
    """Extract text from PDF content.

    Note: This is a placeholder implementation. In production, you would
    use a library like PyPDF2 or pdfplumber.
    """
    try:
        # Try to use pdfplumber if available
        import pdfplumber

        text_parts = [f'<pdf filename="{filename}">']

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f'<page number="{i}">\n{page_text}\n</page>')

        text_parts.append("</pdf>")
        return "\n".join(text_parts)
    except ImportError:
        # pdfplumber not available
        return None
    except Exception:
        # Extraction failed
        return None


def convert_attachments(attachments: list[Attachment]) -> list[TextContent | ImageContent]:
    """Convert attachments to content blocks for LLM.

    - Images become ImageContent blocks
    - Documents with extracted_text become TextContent blocks
    """
    content: list[TextContent | ImageContent] = []

    for attachment in attachments:
        if attachment.type == "image":
            content.append(
                ImageContent(
                    type="image",
                    data=attachment.content,
                    mime_type=attachment.content_type,
                )
            )
        elif attachment.type == "document" and attachment.extracted_text:
            content.append(
                TextContent(
                    type="text",
                    text=f"\n\n[Document: {attachment.filename}]\n{attachment.extracted_text}",
                )
            )

    return content


def attachment_to_dict(attachment: Attachment) -> dict[str, Any]:
    """Convert attachment to dictionary."""
    return {
        "id": attachment.id,
        "type": attachment.type,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "content": attachment.content,
        "extracted_text": attachment.extracted_text,
        "preview": attachment.preview,
    }
