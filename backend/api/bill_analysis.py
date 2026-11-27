"""Analyze stored North Carolina bills with local Ollama (default qwen3.5:9b)."""

from __future__ import annotations

import os
import re

from django.utils import timezone

from api.meeting_ai import _http_post_json, _parse_llm_json
from api.models import LegislativeBill
from api.nc_bills import bill_history, bill_text

DEFAULT_OLLAMA = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3.5:9b"


def ollama_base() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA).strip().rstrip("/")


def bill_model() -> str:
    return os.getenv("OLLAMA_BILL_MODEL", os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)).strip()


def store_bill(session_year: int, chamber_code: str, number: int) -> LegislativeBill:
    meta = bill_history(session_year, chamber_code, number)
    text = bill_text(session_year, chamber_code, number)
    bill, _created = LegislativeBill.objects.update_or_create(
        session_year=session_year,
        bill_type=chamber_code.lower(),
        bill_number=number,
        defaults={
            "chamber": meta["chamber"],
            "title": meta["title"],
            "latest_action": meta["latest_action"],
            "latest_action_date": meta["latest_action_date"],
            "source_url": meta["source_url"],
            "bill_text": text,
            "official_summary": "",
        },
    )
    return bill


def summarize_text(title: str, citation: str, source: str) -> str:
    """Executive summary from the local model. Empty string when the model is unavailable."""
    if not (source or "").strip():
        return ""
    prompt = f"""Summarize this government measure in 2-4 plain sentences.
Return one JSON object with a single key, summary. No other text.

{citation}
Title: {title}

Text:
{source[:8000]}
"""
    try:
        data = _http_post_json(
            f"{ollama_base()}/api/chat",
            {
                "model": bill_model(),
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": "You return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=180,
        )
        content = data.get("message", {}).get("content") or ""
        parsed = _parse_llm_json(_strip_think(content))
        return (parsed.get("summary") or "").strip()
    except Exception:
        return ""


def analyze_bill(bill: LegislativeBill) -> LegislativeBill:
    source = bill.bill_text or bill.title
    if not source.strip():
        bill.analysis_status = LegislativeBill.AnalysisStatus.FAILED
        bill.analysis_error = "No bill text to analyze."
        bill.save(update_fields=["analysis_status", "analysis_error", "updated_at"])
        return bill

    citation = f"{bill.bill_type.upper()}{bill.bill_number}"
    prompt = f"""You analyze North Carolina General Assembly legislation. Use only the text below.
Return one JSON object and no other text. Keys:
summary (2-4 sentences, plain language),
what_it_does (array of short strings),
who_is_affected (array of short strings),
key_provisions (array of short strings),
open_questions (array of short strings; empty if none).

Bill: {citation}, {bill.session_year} session
Title: {bill.title}
Latest action: {bill.latest_action}

Text:
{source[:8000]}
"""
    model = bill_model()
    try:
        data = _http_post_json(
            f"{ollama_base()}/api/chat",
            {
                "model": model,
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": "You return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=180,
        )
        content = data.get("message", {}).get("content") or ""
        parsed = _parse_llm_json(_strip_think(content))
        bill.analysis = parsed
        bill.analysis_summary = (parsed.get("summary") or "").strip()
        bill.analysis_model = model
        bill.analysis_status = LegislativeBill.AnalysisStatus.DONE
        bill.analysis_error = ""
        bill.analyzed_at = timezone.now()
    except Exception as exc:
        bill.analysis_status = LegislativeBill.AnalysisStatus.FAILED
        bill.analysis_error = str(exc)[:500]
        bill.analysis_model = model
    bill.save()
    return bill


def _strip_think(content: str) -> str:
    return re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
