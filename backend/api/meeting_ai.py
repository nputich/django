"""
AI enrichment for meeting responses.

When meeting.ai_mode is not ``none``, responses on issue and political slides
are analyzed and stored in MeetingResponseAI and PoliticalClassification.

Provider priority:
  - paid + OPENAI_API_KEY → OpenAI API
  - self_hosted + OLLAMA_BASE_URL → local Ollama
  - otherwise → rule-based demo classifier (no external services)
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from api.models import (
    Meeting,
    MeetingResponse,
    MeetingResponseAI,
    MeetingSession,
    MeetingSlide,
    PoliticalClassification,
)

logger = logging.getLogger(__name__)

# Keyword hints for rule-based political classification (expandable; AI may add more later).
POLITICAL_HINTS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("Transportation", "Roads", "Potholes and road repair", ("pothole", "road", "highway", "bridge", "traffic")),
    ("Transportation", "Public Transit", "Bus and rail service", ("bus", "transit", "train", "metro")),
    ("Public Safety", "Police", "Police response and safety", ("police", "crime", "safety", "violence")),
    ("Housing", "Affordable Housing", "Rent and housing costs", ("rent", "housing", "affordable", "evict")),
    ("Education", "School Funding", "Schools and overcrowding", ("school", "education", "teacher", "classroom")),
    ("Healthcare", "Mental Health Services", "Mental health access", ("mental health", "hospital", "clinic")),
    ("Taxes and Budget", "Property Taxes", "Tax increases", ("tax", "property tax", "budget")),
    ("Environment", "Water and Sewer", "Water infrastructure", ("water", "sewer", "flood")),
    ("Local Government", "Government Transparency", "Corruption and transparency", ("corrupt", "transparent", "accountability")),
]

SENTIMENT_POSITIVE = ("support", "agree", "good", "great", "yes", "improve", "thank")
SENTIMENT_NEGATIVE = ("oppose", "against", "bad", "worst", "no", "hate", "angry", "unsafe", "corrupt")


@dataclass
class PoliticalPath:
    major_issue_bucket: str
    specific_issue_bucket: str
    concern_bucket: str
    confidence: float = 0.5


@dataclass
class AnalysisResult:
    ai_summary: str = ""
    ai_tags: list[str] = field(default_factory=list)
    sentiment: str = ""
    support_level: str = ""
    opposition_level: str = ""
    action_item: str = ""
    decision_made: str = ""
    unresolved_question: str = ""
    confidence: float | None = None
    political_paths: list[PoliticalPath] = field(default_factory=list)
    provider: str = "rule_based"


def ai_mode_enabled(meeting: Meeting) -> bool:
    return meeting.ai_mode != Meeting.AIMode.NONE


def _response_text(response: MeetingResponse) -> str:
    return (response.response_text or response.raw_text or "").strip()


def _rule_sentiment(text: str) -> str:
    lower = text.lower()
    pos = sum(1 for w in SENTIMENT_POSITIVE if w in lower)
    neg = sum(1 for w in SENTIMENT_NEGATIVE if w in lower)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _rule_political_paths(text: str) -> list[PoliticalPath]:
    lower = text.lower()
    paths: list[PoliticalPath] = []
    for major, specific, concern, keywords in POLITICAL_HINTS:
        if any(kw in lower for kw in keywords):
            paths.append(
                PoliticalPath(
                    major_issue_bucket=major,
                    specific_issue_bucket=specific,
                    concern_bucket=concern,
                    confidence=0.55,
                )
            )
    if not paths and len(text) > 10:
        paths.append(
            PoliticalPath(
                major_issue_bucket="Community Services",
                specific_issue_bucket="General Feedback",
                concern_bucket=text[:200],
                confidence=0.35,
            )
        )
    return paths[:3]


def _rule_analyze(text: str, slide_type: str) -> AnalysisResult:
    sentiment = _rule_sentiment(text)
    tags = []
    for word in re.findall(r"[A-Za-z]{4,}", text.lower())[:8]:
        if word not in tags:
            tags.append(word)

    result = AnalysisResult(
        ai_summary=text[:280] + ("…" if len(text) > 280 else ""),
        ai_tags=tags[:6],
        sentiment=sentiment,
        support_level="moderate" if sentiment == "positive" else "low",
        opposition_level="moderate" if sentiment == "negative" else "low",
        action_item="Review participant feedback" if len(text) > 20 else "",
        unresolved_question=text if "?" in text else "",
        confidence=0.45,
        provider="rule_based",
    )
    if slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        result.political_paths = _rule_political_paths(text)
    elif slide_type == MeetingSlide.SlideType.ISSUE_CARD:
        result.political_paths = []
    return result


def _http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _build_llm_prompt(text: str, slide_type: str) -> str:
    return f"""Analyze this community meeting response as JSON only.
Slide type: {slide_type}
Response: {text}

Return a single JSON object with keys:
ai_summary (string), ai_tags (array of strings), sentiment (positive|negative|neutral),
support_level (string), opposition_level (string), action_item (string),
unresolved_question (string), confidence (0-1 number),
political_paths (array of objects with major_issue_bucket, specific_issue_bucket, concern_bucket, confidence).
Use empty political_paths for non-political slides. No markdown."""


def _parse_llm_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def _llm_result_to_analysis(data: dict, provider: str) -> AnalysisResult:
    paths = [
        PoliticalPath(
            major_issue_bucket=p.get("major_issue_bucket", ""),
            specific_issue_bucket=p.get("specific_issue_bucket", ""),
            concern_bucket=p.get("concern_bucket", ""),
            confidence=float(p.get("confidence", 0.7)),
        )
        for p in data.get("political_paths", [])
        if p.get("major_issue_bucket") or p.get("concern_bucket")
    ]
    return AnalysisResult(
        ai_summary=data.get("ai_summary", ""),
        ai_tags=data.get("ai_tags", []) or [],
        sentiment=data.get("sentiment", ""),
        support_level=data.get("support_level", ""),
        opposition_level=data.get("opposition_level", ""),
        action_item=data.get("action_item", ""),
        decision_made=data.get("decision_made", ""),
        unresolved_question=data.get("unresolved_question", ""),
        confidence=data.get("confidence"),
        political_paths=paths,
        provider=provider,
    )


def _analyze_openai(text: str, slide_type: str, meeting: Meeting) -> AnalysisResult | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
    if meeting.ai_mode == Meeting.AIMode.PAID:
        model = os.getenv("PAID_AI_MODEL", model)
    try:
        data = _http_post_json(
            f"{base}/chat/completions",
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You return only valid JSON."},
                    {"role": "user", "content": _build_llm_prompt(text, slide_type)},
                ],
                "temperature": 0.2,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        content = data["choices"][0]["message"]["content"]
        return _llm_result_to_analysis(_parse_llm_json(content), "openai")
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("OpenAI analysis failed: %s", exc)
        return None


def _analyze_ollama(text: str, slide_type: str, meeting: Meeting) -> AnalysisResult | None:
    base = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    if not base:
        return None
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        data = _http_post_json(
            f"{base}/api/chat",
            {
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "You return only valid JSON."},
                    {"role": "user", "content": _build_llm_prompt(text, slide_type)},
                ],
            },
        )
        content = data["message"]["content"]
        return _llm_result_to_analysis(_parse_llm_json(content), "ollama")
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Ollama analysis failed: %s", exc)
        return None


def analyze_response(meeting: Meeting, text: str, slide_type: str) -> AnalysisResult:
    if not text:
        return AnalysisResult(provider="skipped")

    result = None
    if meeting.ai_mode == Meeting.AIMode.PAID:
        result = _analyze_openai(text, slide_type, meeting)
    elif meeting.ai_mode == Meeting.AIMode.SELF_HOSTED:
        result = _analyze_ollama(text, slide_type, meeting)
        if result is None:
            result = _analyze_openai(text, slide_type, meeting)

    if result is None:
        result = _rule_analyze(text, slide_type)
    return result


def _should_analyze_slide(slide: MeetingSlide | None) -> bool:
    if not slide:
        return False
    return slide.slide_type in (
        MeetingSlide.SlideType.ISSUE_CARD,
        MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
        MeetingSlide.SlideType.STANDARD,
    )


def apply_analysis(response: MeetingResponse, analysis: AnalysisResult) -> MeetingResponseAI:
    ai, _ = MeetingResponseAI.objects.update_or_create(
        response=response,
        defaults={
            "ai_summary": analysis.ai_summary,
            "ai_tags": analysis.ai_tags,
            "sentiment": analysis.sentiment,
            "support_level": analysis.support_level,
            "opposition_level": analysis.opposition_level,
            "action_item": analysis.action_item,
            "decision_made": analysis.decision_made,
            "unresolved_question": analysis.unresolved_question,
            "confidence": analysis.confidence,
            "processed_at": timezone.now(),
        },
    )

    if response.slide and response.slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        response.political_classifications.all().delete()
        for path in analysis.political_paths:
            PoliticalClassification.objects.create(
                response=response,
                major_issue_bucket=path.major_issue_bucket,
                specific_issue_bucket=path.specific_issue_bucket,
                concern_bucket=path.concern_bucket,
                source=PoliticalClassification.Source.AI,
                confidence=path.confidence,
            )

    response.normalization_status = "complete"
    response.normalized_text = analysis.ai_summary or response.response_text
    response.save(update_fields=["normalization_status", "normalized_text"])
    return ai


def process_meeting_response(response: MeetingResponse) -> dict[str, Any]:
    meeting = response.meeting
    if not ai_mode_enabled(meeting):
        return {"processed": False, "reason": "ai_disabled"}

    slide = response.slide
    if not _should_analyze_slide(slide):
        return {"processed": False, "reason": "slide_type_skipped"}

    text = _response_text(response)
    if not text:
        return {"processed": False, "reason": "empty_response"}

    try:
        analysis = analyze_response(meeting, text, slide.slide_type)
        apply_analysis(response, analysis)
        return {
            "processed": True,
            "response_id": response.id,
            "provider": analysis.provider,
            "sentiment": analysis.sentiment,
            "political_paths": len(analysis.political_paths),
        }
    except Exception as exc:
        logger.exception("AI processing failed for response %s", response.id)
        response.normalization_status = "failed"
        response.save(update_fields=["normalization_status"])
        return {"processed": False, "reason": str(exc), "response_id": response.id}


def process_meeting_response_by_id(response_id: int) -> dict[str, Any]:
    response = MeetingResponse.objects.select_related("meeting", "slide").get(pk=response_id)
    return process_meeting_response(response)


def process_session_ai(session: MeetingSession) -> dict[str, Any]:
    meeting = session.meeting
    if not ai_mode_enabled(meeting):
        return {"processed": 0, "skipped": 0, "reason": "ai_disabled"}

    qs = MeetingResponse.objects.filter(session=session).select_related("slide", "meeting")
    processed = 0
    skipped = 0
    results = []
    for response in qs:
        outcome = process_meeting_response(response)
        if outcome.get("processed"):
            processed += 1
        else:
            skipped += 1
        results.append(outcome)
    return {"processed": processed, "skipped": skipped, "results": results}


def process_meeting_ai(meeting: Meeting, session_id: str | None = None) -> dict[str, Any]:
    from api.meeting_export import get_sessions_for_export

    if not ai_mode_enabled(meeting):
        return {"processed": 0, "skipped": 0, "reason": "ai_disabled"}

    total_processed = 0
    total_skipped = 0
    session_results = []
    for session in get_sessions_for_export(meeting, session_id or "all"):
        outcome = process_session_ai(session)
        total_processed += outcome.get("processed", 0)
        total_skipped += outcome.get("skipped", 0)
        session_results.append({"session_id": session.id, **outcome})
    return {
        "processed": total_processed,
        "skipped": total_skipped,
        "sessions": session_results,
    }


def schedule_response_ai_processing(response: MeetingResponse) -> None:
    """Run after DB commit so participants are not blocked on AI latency."""
    from django.db import transaction

    if not ai_mode_enabled(response.meeting):
        return
    transaction.on_commit(lambda: process_meeting_response_by_id(response.id))
