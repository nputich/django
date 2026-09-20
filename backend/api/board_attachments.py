"""Allowed document attachments on wall posts."""

from __future__ import annotations

from pathlib import Path

from rest_framework.exceptions import ValidationError

# Office + PDF + common pictures (no executables).
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}

# 15 MB — enough for typical decks/spreadsheets without ballooning media storage.
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def validate_wall_attachment(uploaded) -> None:
    if uploaded is None:
        return
    name = getattr(uploaded, "name", "") or ""
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            {
                "attachment": (
                    "Allowed types: PDF, Word, Excel, PowerPoint, "
                    "and pictures (PNG, JPG, GIF, WebP)."
                )
            }
        )
    size = getattr(uploaded, "size", None)
    if size is not None and size > MAX_ATTACHMENT_BYTES:
        raise ValidationError(
            {"attachment": "File must be 15 MB or smaller."}
        )


def attachment_upload_to(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    safe_ext = ext if ext in ALLOWED_EXTENSIONS else ".bin"
    kind = "org" if instance.__class__.__name__ == "BoardPost" else "personal"
    return f"wall_attachments/{kind}/{instance.board_id}/{filename[:80]}{safe_ext}"


def serialize_attachment(post, request) -> dict | None:
    file_field = getattr(post, "attachment", None)
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    if request is not None:
        url = request.build_absolute_uri(url)
    name = (getattr(post, "attachment_name", None) or "").strip()
    if not name:
        name = Path(file_field.name).name
    return {
        "name": name,
        "url": url,
        "size": file_field.size if hasattr(file_field, "size") else None,
    }
