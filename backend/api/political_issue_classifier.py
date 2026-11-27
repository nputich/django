"""
Batch political issue classification for live results.

Analyzes all responses for a political issue card slide together so similar
responses receive consistent taxonomy labels.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from api.models import (
    Meeting,
    MeetingResponse,
    MeetingResponseAI,
    MeetingSession,
    MeetingSlide,
    PoliticalClassification,
)
from api.meeting_ai import _http_post_json, _parse_llm_json, ai_mode_enabled

logger = logging.getLogger(__name__)

CLASSIFICATION_STATUSES = frozenset({"classified", "needs_review", "invalid"})
LOW_CONFIDENCE_THRESHOLD = 0.6
MAX_BATCH_RETRIES = 2

MAJOR_ISSUES = (
    "Transportation",
    "Economy",
    "Education",
    "Healthcare",
    "Housing",
    "Public Safety",
    "Environment",
    "Technology",
    "Government",
    "National Security",
    "Foreign Affairs",
    "Demographics",
    "Community Services",
)


@dataclass
class PoliticalClassificationItem:
    response_id: int
    normalized_response: str = ""
    major_issue: str = ""
    specific_issue: str = ""
    issue_type: str = ""
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    classification_status: str = "pending"
    review_reason: str = ""


def _raw_text(response: MeetingResponse) -> str:
    return response.raw_response or ""


def _is_gibberish(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < 3:
        return False
    alpha = sum(1 for ch in stripped if ch.isalpha())
    if alpha / len(stripped) < 0.35:
        return True
    if re.fullmatch(r"[a-zA-Z;,\s\d]{3,}", stripped) and ";" in stripped:
        consonant_runs = re.findall(r"[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{4,}", stripped)
        if consonant_runs:
            return True
    return False


def response_needs_reclassification(
    response: MeetingResponse,
    *,
    force: bool = False,
) -> bool:
    raw = _raw_text(response).strip()
    if not raw:
        return False

    if force or response.classification_reprocess:
        return True

    status = (response.classification_status or "pending").strip()
    if status in ("", "pending"):
        return True

    snapshot = (response.classified_raw_snapshot or "").strip()
    if snapshot != raw.strip():
        return True

    return False


def _build_batch_prompt(
    responses: list[MeetingResponse],
    *,
    target_ids: set[int],
) -> str:
    payload = []
    for response in responses:
        entry = {
            "response_id": response.id,
            "raw_response": _raw_text(response),
            "classify": response.id in target_ids,
        }
        if response.id not in target_ids:
            status = (response.classification_status or "").strip()
            if status in CLASSIFICATION_STATUSES:
                entry["existing_classification"] = {
                    "normalized_response": response.normalized_response or "",
                    "major_issue": response.major_issue or "",
                    "specific_issue": response.specific_issue or "",
                    "issue_type": response.issue_type or "",
                    "classification_status": status,
                }
        payload.append(entry)
    major_list = ", ".join(MAJOR_ISSUES)
    return f"""You classify community meeting political issue card responses.

Review ALL responses together before assigning labels. Similar or identical
responses MUST use the same major_issue, specific_issue, and issue_type labels.
Reuse existing labels from existing_classification entries when new responses
express substantially the same issue.

Only return entries where classify is true. Do not return rows for responses
with classify false.

Return valid JSON only with this shape:
{{
  "responses": [
    {{
      "response_id": 123,
      "normalized_response": "short neutral restatement of the concern",
      "major_issue": "Transportation",
      "specific_issue": "Road Maintenance",
      "issue_type": "Pothole Repair",
      "tags": ["potholes", "road maintenance"],
      "confidence": 0.96,
      "classification_status": "classified",
      "review_reason": ""
    }}
  ]
}}

Rules:
- normalized_response is a human-readable restatement, NOT a category label.
- major_issue must be one of: {major_list}
- specific_issue is a narrower subject within major_issue.
- issue_type is the most specific reusable label (title case).
- classification_status must be classified, needs_review, or invalid.
- For invalid/gibberish responses: empty normalized_response and category fields,
  classification_status invalid, low confidence, and review_reason explaining why.
- For vague one-word responses (e.g. "china", "ai"): use needs_review, low
  confidence, broad categories only, and explain in review_reason.
- Never force unclear responses into unrelated categories.
- Never use Community Services as a catch-all.
- Never infer sentiment, support, opposition, or action items.
- Tags must be meaningful concepts, not stopwords or single-word splits.
- Preserve participant meaning; do not add unstated policy positions.

Responses to classify:
{json.dumps(payload, ensure_ascii=False)}"""


def _validate_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence < 0.0 or confidence > 1.0:
        return None
    return confidence


def _validate_batch_payload(
    data: dict,
    expected_ids: set[int],
) -> list[PoliticalClassificationItem] | None:
    if not isinstance(data, dict):
        return None
    entries = data.get("responses")
    if not isinstance(entries, list):
        return None

    if not expected_ids and not entries:
        return []

    seen: set[int] = set()
    items: list[PoliticalClassificationItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        try:
            response_id = int(entry.get("response_id"))
        except (TypeError, ValueError):
            return None
        if response_id not in expected_ids or response_id in seen:
            return None
        seen.add(response_id)

        status = str(entry.get("classification_status", "")).strip()
        if status not in CLASSIFICATION_STATUSES:
            return None

        confidence = _validate_confidence(entry.get("confidence"))
        if confidence is None:
            return None

        tags = entry.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            return None

        normalized = str(entry.get("normalized_response", "") or "").strip()
        major = str(entry.get("major_issue", "") or "").strip()
        specific = str(entry.get("specific_issue", "") or "").strip()
        issue_type = str(entry.get("issue_type", "") or "").strip()
        review_reason = str(entry.get("review_reason", "") or "").strip()

        if status == "invalid":
            if normalized or major or specific or issue_type:
                return None
            if not review_reason:
                return None
        elif status == "needs_review":
            if not normalized:
                return None
        elif status == "classified":
            if not normalized or not major or not specific or not issue_type:
                return None

        items.append(
            PoliticalClassificationItem(
                response_id=response_id,
                normalized_response=normalized,
                major_issue=major,
                specific_issue=specific,
                issue_type=issue_type,
                tags=[tag.strip() for tag in tags if tag.strip()],
                confidence=confidence,
                classification_status=status,
                review_reason=review_reason,
            )
        )

    if seen != expected_ids:
        return None
    return items


def _call_openai_batch(prompt: str, meeting: Meeting) -> dict | None:
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
                    {
                        "role": "system",
                        "content": "You return only valid JSON matching the requested schema.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )
        content = data["choices"][0]["message"]["content"]
        return _parse_llm_json(content)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("OpenAI batch political classification failed: %s", exc)
        return None


def _call_ollama_batch(prompt: str, meeting: Meeting) -> dict | None:
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
                    {
                        "role": "system",
                        "content": "You return only valid JSON matching the requested schema.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=120,
        )
        content = data["message"]["content"]
        return _parse_llm_json(content)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Ollama batch political classification failed: %s", exc)
        return None


def _title_case_phrase(text: str) -> str:
    return " ".join(word.capitalize() for word in text.split())


def _rule_classify_text(text: str) -> PoliticalClassificationItem:
    raw = text.strip()
    if _is_gibberish(raw):
        return PoliticalClassificationItem(
            response_id=0,
            confidence=0.05,
            classification_status="invalid",
            review_reason="The response does not contain understandable issue content.",
        )

    lower = raw.lower()
    word_count = len(re.findall(r"\w+", lower))

    if word_count <= 1:
        if lower in {"china", "chinese"}:
            return PoliticalClassificationItem(
                response_id=0,
                normalized_response="Concern related to China",
                major_issue="Foreign Affairs",
                specific_issue="International Relations",
                issue_type="China-Related Concern",
                tags=["china"],
                confidence=0.25,
                classification_status="needs_review",
                review_reason=(
                    "The response does not specify whether the concern involves trade, "
                    "national security, foreign policy, human rights, or another issue."
                ),
            )
        if lower in {"ai", "artificial intelligence"}:
            return PoliticalClassificationItem(
                response_id=0,
                normalized_response="Concern related to artificial intelligence",
                major_issue="Technology",
                specific_issue="Artificial Intelligence",
                issue_type="General AI Concern",
                tags=["artificial intelligence"],
                confidence=0.25,
                classification_status="needs_review",
                review_reason=(
                    "The response does not identify a specific concern about artificial intelligence."
                ),
            )
        return PoliticalClassificationItem(
            response_id=0,
            normalized_response=f"Concern related to {raw}",
            confidence=0.2,
            classification_status="needs_review",
            review_reason="The response is too vague to classify confidently.",
        )

    if "pothole" in lower or ("fix" in lower and "road" in lower):
        return PoliticalClassificationItem(
            response_id=0,
            normalized_response=_title_case_phrase(raw.rstrip(".")),
            major_issue="Transportation",
            specific_issue="Road Maintenance",
            issue_type="Pothole Repair",
            tags=["potholes", "road maintenance"],
            confidence=0.85,
            classification_status="classified",
        )

    if "low paying job" in lower or "low paying jobs" in lower or lower == "low wages":
        return PoliticalClassificationItem(
            response_id=0,
            normalized_response="Increase access to better-paying jobs",
            major_issue="Economy",
            specific_issue="Wages and Employment",
            issue_type="Low Wages",
            tags=["wages", "employment"],
            confidence=0.9,
            classification_status="classified",
        )

    if "consolidation" in lower and ("business" in lower or "companies" in lower or "company" in lower):
        return PoliticalClassificationItem(
            response_id=0,
            normalized_response="Concern about businesses becoming concentrated under fewer companies",
            major_issue="Economy",
            specific_issue="Market Competition",
            issue_type="Corporate Consolidation",
            tags=["business consolidation", "market competition"],
            confidence=0.9,
            classification_status="classified",
        )

    if ("fighting" in lower or "fight" in lower) and ("school" in lower or "kid" in lower or "student" in lower):
        return PoliticalClassificationItem(
            response_id=0,
            normalized_response="Reduce fighting among students at school",
            major_issue="Education",
            specific_issue="School Safety",
            issue_type="Student Fighting",
            tags=["school safety", "student fighting"],
            confidence=0.9,
            classification_status="classified",
        )

    if "having kids" in lower or "birth rate" in lower or "aren't having kids" in lower or "arent having kids" in lower:
        return PoliticalClassificationItem(
            response_id=0,
            normalized_response="Concern about declining birth rates",
            major_issue="Demographics",
            specific_issue="Population Trends",
            issue_type="Declining Birth Rate",
            tags=["birth rate", "demographics"],
            confidence=0.88,
            classification_status="classified",
        )

    return PoliticalClassificationItem(
        response_id=0,
        normalized_response=raw[:280] + ("…" if len(raw) > 280 else ""),
        confidence=0.35,
        classification_status="needs_review",
        review_reason="Unable to confidently map this response without AI review.",
    )


def _rule_based_batch_classify(
    responses: list[MeetingResponse],
) -> list[PoliticalClassificationItem]:
    text_to_template: dict[str, PoliticalClassificationItem] = {}
    items: list[PoliticalClassificationItem] = []

    for response in responses:
        raw = _raw_text(response).strip()
        key = raw.lower()
        if key not in text_to_template:
            template = _rule_classify_text(raw)
            text_to_template[key] = template
        template = text_to_template[key]
        items.append(
            PoliticalClassificationItem(
                response_id=response.id,
                normalized_response=template.normalized_response,
                major_issue=template.major_issue,
                specific_issue=template.specific_issue,
                issue_type=template.issue_type,
                tags=list(template.tags),
                confidence=template.confidence,
                classification_status=template.classification_status,
                review_reason=template.review_reason,
            )
        )
    return items


def _classify_batch_with_llm(
    meeting: Meeting,
    all_responses: list[MeetingResponse],
    target_ids: set[int],
) -> tuple[list[PoliticalClassificationItem] | None, str]:
    expected_ids = set(target_ids)
    prompt = _build_batch_prompt(all_responses, target_ids=expected_ids)

    providers: list[tuple[str, Any]] = []
    if meeting.ai_mode == Meeting.AIMode.PAID:
        providers.append(("openai", _call_openai_batch))
    elif meeting.ai_mode == Meeting.AIMode.SELF_HOSTED:
        providers.append(("ollama", _call_ollama_batch))
        providers.append(("openai", _call_openai_batch))

    for provider_name, provider_fn in providers:
        for attempt in range(MAX_BATCH_RETRIES + 1):
            raw_data = provider_fn(prompt, meeting)
            if raw_data is None:
                break
            validated = _validate_batch_payload(raw_data, expected_ids)
            if validated is not None:
                return validated, provider_name
            logger.warning(
                "Invalid %s batch political JSON (attempt %s); retrying.",
                provider_name,
                attempt + 1,
            )
    return None, "rule_based"


def classify_batch(
    meeting: Meeting,
    all_responses: list[MeetingResponse],
    target_ids: set[int],
) -> tuple[list[PoliticalClassificationItem], str]:
    if not target_ids:
        return [], "skipped"

    llm_items, provider = _classify_batch_with_llm(meeting, all_responses, target_ids)
    if llm_items is not None:
        return llm_items, provider

    target_responses = [response for response in all_responses if response.id in target_ids]
    return _rule_based_batch_classify(target_responses), "rule_based"


@transaction.atomic
def apply_political_classification(
    response: MeetingResponse,
    item: PoliticalClassificationItem,
) -> None:
    raw = _raw_text(response)
    response.normalized_response = item.normalized_response
    response.major_issue = item.major_issue
    response.specific_issue = item.specific_issue
    response.issue_type = item.issue_type
    response.classification_confidence = item.confidence
    response.classification_status = item.classification_status
    response.review_reason = item.review_reason
    response.classified_raw_snapshot = raw
    response.classification_reprocess = False
    response.classification_processed_at = timezone.now()
    response.normalization_status = "complete"
    response.save(
        update_fields=[
            "normalized_response",
            "major_issue",
            "specific_issue",
            "issue_type",
            "classification_confidence",
            "classification_status",
            "review_reason",
            "classified_raw_snapshot",
            "classification_reprocess",
            "classification_processed_at",
            "normalization_status",
        ]
    )

    MeetingResponseAI.objects.update_or_create(
        response=response,
        defaults={
            "ai_summary": item.normalized_response,
            "ai_tags": item.tags,
            "confidence": item.confidence,
            "processed_at": timezone.now(),
        },
    )

    response.political_classifications.all().delete()
    if item.classification_status == "classified":
        PoliticalClassification.objects.create(
            response=response,
            major_issue=item.major_issue,
            specific_issue=item.specific_issue,
            source=PoliticalClassification.Source.AI,
            confidence=item.confidence,
        )


def classify_political_slide_responses(
    session: MeetingSession,
    slide: MeetingSlide,
    *,
    force: bool = False,
) -> dict[str, Any]:
    meeting = session.meeting
    if slide.slide_type != MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        return {"status": "skipped", "reason": "slide_type_skipped"}

    if not ai_mode_enabled(meeting):
        return {"status": "skipped", "reason": "ai_disabled", "processed": 0, "skipped": 0}

    all_responses = list(
        MeetingResponse.objects.filter(session=session, slide=slide)
        .select_related("meeting", "slide")
        .order_by("id")
    )
    to_process = [
        response
        for response in all_responses
        if response_needs_reclassification(response, force=force)
    ]
    already_done = len(all_responses) - len(to_process)

    if not to_process:
        return {
            "status": "success",
            "processed": 0,
            "skipped": already_done,
            "failed": 0,
            "provider": None,
            "message": "All responses already classified.",
        }

    try:
        target_ids = {response.id for response in to_process}
        items, provider = classify_batch(meeting, all_responses, target_ids)
        by_id = {item.response_id: item for item in items}
        processed = 0
        failed = 0
        for response in to_process:
            item = by_id.get(response.id)
            if not item:
                failed += 1
                continue
            apply_political_classification(response, item)
            processed += 1

        status = "success" if failed == 0 else "partial"
        return {
            "status": status,
            "processed": processed,
            "skipped": already_done,
            "failed": failed,
            "provider": provider,
        }
    except Exception as exc:
        logger.exception(
            "Batch political classification failed for slide %s session %s",
            slide.id,
            session.id,
        )
        return {
            "status": "error",
            "processed": 0,
            "skipped": already_done,
            "failed": len(to_process),
            "detail": str(exc),
        }


def classification_summary(responses: list[MeetingResponse]) -> dict[str, int]:
    summary = {"pending": 0, "classified": 0, "needs_review": 0, "invalid": 0}
    for response in responses:
        raw = _raw_text(response).strip()
        if not raw:
            continue
        status = (response.classification_status or "pending").strip()
        if status not in summary:
            status = "pending"
        summary[status] += 1
    return summary
