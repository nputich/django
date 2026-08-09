"""Live meeting analytics for host results panels."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from api.models import (
    Meeting,
    MeetingResponse,
    MeetingSession,
    MeetingSlide,
    ParticipantProfileValue,
)
from api.political_issue_classifier import classification_summary


def _normalize_profile_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, (dict, bool, int, float)):
        return json.dumps(value)
    return str(value).strip()


def _profile_value_matches(stored: Any, split_value: str) -> bool:
    target = str(split_value).strip()
    if not target:
        return False
    if isinstance(stored, list):
        return any(str(item).strip() == target for item in stored)
    return _normalize_profile_value(stored) == target


def get_demographic_fields(meeting: Meeting) -> list[dict[str, Any]]:
    """Voluntary participant-info fields available for one-at-a-time splits."""
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slide in meeting.slides.filter(
        slide_type=MeetingSlide.SlideType.PARTICIPANT_INFO,
        is_active=True,
    ).order_by("order", "id"):
        for field in slide.config.get("fields", []):
            key = field.get("key")
            if not key or key in seen:
                continue
            seen.add(key)
            fields.append(
                {
                    "key": key,
                    "label": field.get("label", key),
                    "field_type": field.get("field_type", "text"),
                    "options": field.get("options", []),
                }
            )
    return fields


def get_demographic_values(session: MeetingSession, field_key: str) -> list[str]:
    """Distinct values submitted for a demographic field in this session."""
    values: set[str] = set()
    for row in ParticipantProfileValue.objects.filter(
        attendance__session=session,
        field_key=field_key,
    ).values_list("value", flat=True):
        if isinstance(row, list):
            for item in row:
                text = str(item).strip()
                if text:
                    values.add(text)
        else:
            text = _normalize_profile_value(row)
            if text:
                values.add(text)
    return sorted(values, key=str.casefold)


def _filtered_attendance_ids(
    session: MeetingSession,
    split_field: str | None,
    split_value: str | None,
) -> list[int] | None:
    if not split_field or split_value is None or str(split_value).strip() == "":
        return None
    target = str(split_value).strip()
    matched: list[int] = []
    for profile in ParticipantProfileValue.objects.filter(
        attendance__session=session,
        field_key=split_field,
    ).select_related("attendance"):
        if _profile_value_matches(profile.value, target):
            matched.append(profile.attendance_id)
    return matched


def _responses_for_slide(
    session: MeetingSession,
    slide: MeetingSlide,
    attendance_ids: list[int] | None,
) -> list[MeetingResponse]:
    qs = MeetingResponse.objects.filter(session=session, slide=slide).select_related(
        "attendance"
    )
    if attendance_ids is not None:
        qs = qs.filter(attendance_id__in=attendance_ids)
    return list(qs)


def _distinct_respondents(responses: list[MeetingResponse]) -> int:
    return len({r.attendance_id for r in responses if r.attendance_id})


def _bars_from_counter(
    counts: Counter,
    ordered_labels: list[str] | None = None,
    limit: int = 10,
    *,
    include_zero_labels: bool = False,
) -> list[dict[str, Any]]:
    if ordered_labels:
        labels = ordered_labels[:limit]
        items = [(label, counts.get(label, 0)) for label in labels]
        if not include_zero_labels:
            items = [(label, count) for label, count in items if count > 0]
    else:
        items = [(label, count) for label, count in counts.most_common(limit) if count > 0]

    if not items:
        return []

    max_count = max(count for _, count in items) or 1
    bars = []
    for label, count in items[:limit] if not ordered_labels else items:
        bars.append(
            {
                "label": label,
                "count": count,
                "percent": round((count / max_count) * 100, 1) if max_count else 0,
            }
        )
    return bars


def _issue_response_display_text(slide: MeetingSlide, response: MeetingResponse) -> str:
    """For political issue cards, chart by issue_type when classification is available."""
    if slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        status = (response.classification_status or "pending").strip()
        if status in ("classified", "needs_review"):
            issue_type = (response.issue_type or "").strip()
            if issue_type:
                return issue_type
            specific = (response.specific_issue or "").strip()
            if specific:
                return specific
            major = (response.major_issue or "").strip()
            if major:
                return major
            normalized = (response.normalized_response or "").strip()
            if normalized:
                return normalized
    return (response.raw_response or "").strip()


def _response_answer_text(slide: MeetingSlide, response: MeetingResponse) -> str:
    if slide.slide_type in (
        MeetingSlide.SlideType.ISSUE_CARD,
        MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
    ):
        return _issue_response_display_text(slide, response)
    if slide.question_format in (
        MeetingSlide.QuestionFormat.SINGLE_CHOICE,
        MeetingSlide.QuestionFormat.MULTI_CHOICE,
    ):
        if slide.question_format == MeetingSlide.QuestionFormat.MULTI_CHOICE:
            options = response.selected_options or []
            if options:
                return ", ".join(options)
        text = (response.raw_response or "").strip()
        if text:
            return text
        if response.selected_options:
            return response.selected_options[0]
        return ""
    return (response.raw_response or "").strip()


def _counts_for_responses(
    slide: MeetingSlide, responses: list[MeetingResponse]
) -> Counter:
    if slide.slide_type == MeetingSlide.SlideType.STANDARD:
        if slide.question_format in (
            MeetingSlide.QuestionFormat.SINGLE_CHOICE,
            MeetingSlide.QuestionFormat.MULTI_CHOICE,
        ):
            counts: Counter = Counter()
            if slide.question_format == MeetingSlide.QuestionFormat.SINGLE_CHOICE:
                for response in responses:
                    text = _response_answer_text(slide, response)
                    if text:
                        counts[text] += 1
            else:
                for response in responses:
                    for option in response.selected_options or []:
                        counts[option] += 1
            return counts
    counts = Counter()
    for response in responses:
        text = _response_answer_text(slide, response)
        if text:
            counts[text] += 1
    return counts


def _label_order_for_compare(
    slide: MeetingSlide, counters: list[Counter], limit: int
) -> list[str]:
    if (
        slide.slide_type == MeetingSlide.SlideType.STANDARD
        and slide.question_format
        in (
            MeetingSlide.QuestionFormat.SINGLE_CHOICE,
            MeetingSlide.QuestionFormat.MULTI_CHOICE,
        )
        and slide.choices
    ):
        return list(slide.choices)[:limit]

    merged: Counter = Counter()
    for counter in counters:
        merged.update(counter)
    return [label for label, _ in merged.most_common(limit)]


def _split_values_for_field(
    meeting: Meeting, session: MeetingSession, field_key: str
) -> list[str]:
    observed = get_demographic_values(session, field_key)
    for field in get_demographic_fields(meeting):
        if field["key"] != field_key:
            continue
        options = field.get("options") or []
        if not options:
            return observed
        merged = list(options)
        for value in observed:
            if value not in merged:
                merged.append(value)
        return merged
    return observed


def _demographics_by_attendance(
    session: MeetingSession, field_keys: list[str]
) -> dict[int, dict[str, str]]:
    profiles: dict[int, dict[str, str]] = {}
    if not field_keys:
        return profiles
    for profile in ParticipantProfileValue.objects.filter(
        attendance__session=session,
        field_key__in=field_keys,
    ):
        profiles.setdefault(profile.attendance_id, {})[profile.field_key] = (
            _normalize_profile_value(profile.value)
        )
    return profiles


def _individual_responses(
    meeting: Meeting,
    session: MeetingSession,
    slide: MeetingSlide,
    responses: list[MeetingResponse],
) -> list[dict[str, Any]]:
    demo_keys = [field["key"] for field in get_demographic_fields(meeting)]
    profiles = _demographics_by_attendance(session, demo_keys)
    rows: list[dict[str, Any]] = []
    for index, response in enumerate(responses, start=1):
        answer = _response_answer_text(slide, response)
        if not answer:
            continue
        attendance_id = response.attendance_id
        label = (
            f"Participant #{attendance_id}"
            if attendance_id
            else f"Response #{index}"
        )
        rows.append(
            {
                "response_id": response.id,
                "attendance_id": attendance_id,
                "participant_label": label,
                "answer": answer,
                "demographics": profiles.get(attendance_id, {}),
                "raw_response": response.raw_response or "",
                "normalized_response": response.normalized_response or "",
                "major_issue": response.major_issue or "",
                "specific_issue": response.specific_issue or "",
                "issue_type": response.issue_type or "",
                "classification_status": response.classification_status or "pending",
                "confidence": response.classification_confidence,
                "review_reason": response.review_reason or "",
            }
        )
    return rows


def _analytics_standard(
    slide: MeetingSlide,
    responses: list[MeetingResponse],
    limit: int,
    *,
    label_order: list[str] | None = None,
    include_zero_labels: bool = False,
) -> list[dict]:
    counts = _counts_for_responses(slide, responses)
    ordered = label_order
    if ordered is None and slide.choices:
        ordered = list(slide.choices)
    return _bars_from_counter(
        counts,
        ordered_labels=ordered,
        limit=limit,
        include_zero_labels=include_zero_labels,
    )


def _analytics_issues(
    slide: MeetingSlide,
    responses: list[MeetingResponse],
    limit: int,
    *,
    label_order: list[str] | None = None,
    include_zero_labels: bool = False,
) -> list[dict]:
    counts = Counter()
    for response in responses:
        text = _issue_response_display_text(slide, response)
        if text:
            counts[text] += 1
    return _bars_from_counter(
        counts,
        ordered_labels=label_order,
        limit=limit,
        include_zero_labels=include_zero_labels,
    )


def is_analyzable_slide(slide: MeetingSlide) -> bool:
    if slide.slide_type in (
        MeetingSlide.SlideType.ISSUE_CARD,
        MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
    ):
        return True
    if slide.slide_type == MeetingSlide.SlideType.STANDARD:
        return True
    return False


def get_slide_analytics(
    meeting: Meeting,
    session: MeetingSession,
    slide: MeetingSlide,
    *,
    split_field: str | None = None,
    split_value: str | None = None,
    limit: int = 10,
    include_individual: bool = False,
) -> dict[str, Any]:
    if not is_analyzable_slide(slide):
        return {
            "error": "This slide type does not support live results.",
            "bars": [],
        }

    all_responses = _responses_for_slide(session, slide, None)
    attendance_ids = _filtered_attendance_ids(session, split_field, split_value)
    filtered_responses = _responses_for_slide(session, slide, attendance_ids)

    split_meta = None
    if split_field and split_value is not None and str(split_value).strip() != "":
        field_label = split_field
        for field in get_demographic_fields(meeting):
            if field["key"] == split_field:
                field_label = field["label"]
                break
        split_meta = {
            "field_key": split_field,
            "field_label": field_label,
            "value": str(split_value).strip(),
        }

    if slide.slide_type == MeetingSlide.SlideType.STANDARD:
        bars = _analytics_standard(slide, filtered_responses, limit)
    else:
        bars = _analytics_issues(slide, filtered_responses, limit)

    individual_responses = []
    if include_individual:
        individual_responses = _individual_responses(
            meeting, session, slide, all_responses
        )

    payload = {
        "meeting_id": meeting.id,
        "session_id": session.id,
        "slide_id": slide.id,
        "slide_order": slide.order,
        "slide_type": slide.slide_type,
        "slide_title": slide.title or slide.prompt or slide.slide_type,
        "question_format": slide.question_format or "",
        "total_respondents": _distinct_respondents(all_responses),
        "filtered_respondents": _distinct_respondents(filtered_responses),
        "response_row_count": len(filtered_responses),
        "split": split_meta,
        "bars": bars,
        "demographic_fields": get_demographic_fields(meeting),
        "split_values": get_demographic_values(session, split_field) if split_field else [],
        "individual_responses": individual_responses,
    }
    if slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        payload["classification"] = classification_summary(all_responses)
    return payload


def get_slide_analytics_compare(
    meeting: Meeting,
    session: MeetingSession,
    slide: MeetingSlide,
    *,
    split_field: str,
    limit: int = 10,
    include_individual: bool = False,
) -> dict[str, Any]:
    if not is_analyzable_slide(slide):
        return {
            "error": "This slide type does not support live results.",
            "bars": [],
            "comparisons": [],
        }

    all_responses = _responses_for_slide(session, slide, None)
    split_values = _split_values_for_field(meeting, session, split_field)

    field_label = split_field
    for field in get_demographic_fields(meeting):
        if field["key"] == split_field:
            field_label = field["label"]
            break

    counters: list[Counter] = []
    comparison_payloads: list[dict[str, Any]] = []
    for value in split_values:
        attendance_ids = _filtered_attendance_ids(session, split_field, value)
        filtered = _responses_for_slide(session, slide, attendance_ids)
        counter = _counts_for_responses(slide, filtered)
        counters.append(counter)
        comparison_payloads.append(
            {
                "value": value,
                "filtered_respondents": _distinct_respondents(filtered),
                "response_row_count": len(filtered),
                "counts": counter,
            }
        )

    overall_counter = _counts_for_responses(slide, all_responses)
    counters.append(overall_counter)
    label_order = _label_order_for_compare(slide, counters, limit)

    comparisons = []
    align_rows = bool(label_order)
    for item in comparison_payloads:
        bars = _bars_from_counter(
            item["counts"],
            ordered_labels=label_order or None,
            limit=limit,
            include_zero_labels=align_rows,
        )
        comparisons.append(
            {
                "value": item["value"],
                "filtered_respondents": item["filtered_respondents"],
                "response_row_count": item["response_row_count"],
                "bars": bars,
            }
        )

    overall_bars = _bars_from_counter(
        overall_counter,
        ordered_labels=label_order or None,
        limit=limit,
        include_zero_labels=align_rows,
    )

    individual_responses = []
    if include_individual:
        individual_responses = _individual_responses(
            meeting, session, slide, all_responses
        )

    payload = {
        "meeting_id": meeting.id,
        "session_id": session.id,
        "slide_id": slide.id,
        "slide_order": slide.order,
        "slide_type": slide.slide_type,
        "slide_title": slide.title or slide.prompt or slide.slide_type,
        "question_format": slide.question_format or "",
        "total_respondents": _distinct_respondents(all_responses),
        "response_row_count": len(all_responses),
        "split": {
            "field_key": split_field,
            "field_label": field_label,
            "mode": "compare",
        },
        "label_order": label_order,
        "overall": {
            "filtered_respondents": _distinct_respondents(all_responses),
            "response_row_count": len(all_responses),
            "bars": overall_bars,
        },
        "comparisons": comparisons,
        "demographic_fields": get_demographic_fields(meeting),
        "split_values": split_values,
        "individual_responses": individual_responses,
    }
    if slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        payload["classification"] = classification_summary(all_responses)
    return payload
