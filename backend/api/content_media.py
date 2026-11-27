"""Helpers for content slides/blocks (text, banner, video embeds)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_YT = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})",
    re.I,
)
_VIMEO = re.compile(r"vimeo\.com/(?:video/)?(\d+)", re.I)


def normalize_content_config(raw: dict | None) -> dict:
    data = raw or {}
    body = (data.get("body") or "").strip()
    banner = (data.get("banner_url") or "").strip()
    video = (data.get("video_url") or "").strip()
    return {
        "body": body[:20000],
        "banner_url": banner[:2000],
        "video_url": video[:2000],
        "video_embed": video_embed_payload(video) if video else None,
    }


def video_embed_payload(url: str) -> dict | None:
    url = (url or "").strip()
    if not url:
        return None
    yt = _YT.search(url)
    if yt:
        vid = yt.group(1)
        return {
            "provider": "youtube",
            "id": vid,
            "embed_url": f"https://www.youtube.com/embed/{vid}",
        }
    vim = _VIMEO.search(url)
    if vim:
        vid = vim.group(1)
        return {
            "provider": "vimeo",
            "id": vid,
            "embed_url": f"https://player.vimeo.com/video/{vid}",
        }
    # Allowlist only known hosts — reject arbitrary iframes.
    host = urlparse(url).netloc.lower()
    if host.endswith("youtube.com") or host.endswith("youtu.be") or host.endswith("vimeo.com"):
        return {"provider": "unknown", "id": "", "embed_url": ""}
    return None


def survey_disclosure_payload(survey) -> dict:
    parts = []
    if survey.is_anonymous:
        parts.append(
            "Anonymous survey: we do not ask for your name with your answers. "
            "Organizers can still read the answers. "
            "Demographic comparisons are only shown when every group is large enough "
            "so no one is singled out."
        )
    else:
        parts.append(
            "This survey is not anonymous. Organizers may connect your answers to "
            "information you provide. "
            "Demographic comparisons are only shown when every group is large enough "
            "so no one is singled out."
        )
    if getattr(survey, "aggregate_sharing_notice", True):
        parts.append(
            "We may share anonymous combined results with policymakers."
        )
    return {
        "text": " ".join(parts),
        "is_anonymous": survey.is_anonymous,
        "aggregate_sharing_notice": getattr(survey, "aggregate_sharing_notice", True),
    }


def ordered_survey_questions(questions):
    """Main questions first (by order), then demographics (by order). Content stays in place within its group."""
    main = [q for q in questions if not getattr(q, "is_demographic", False)]
    demo = [q for q in questions if getattr(q, "is_demographic", False)]
    return list(main) + list(demo)
