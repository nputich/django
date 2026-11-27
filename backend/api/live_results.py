"""Participant-facing live results: organizer-released aggregates for meetings and surveys."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone

from api.meeting_ai import ai_mode_enabled
from api.meeting_analytics import _bars_from_counter, get_slide_analytics, is_analyzable_slide
from api.models import (
    Meeting,
    MeetingAttendance,
    MeetingSession,
    MeetingSlide,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    SurveySubmission,
)

RESULT_BAR_LIMIT = 10


class LiveResultsDenied(Exception):
    def __init__(self, detail: str, code: str, status_code: int = 403):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


def _toggle_id(ids: list, item_id: int, released: bool) -> list[int]:
    current = [int(i) for i in (ids or [])]
    if released and item_id not in current:
        current.append(item_id)
    if not released:
        current = [i for i in current if i != item_id]
    return current


def participant_ai_status(meeting: Meeting, slide: MeetingSlide, classification: dict | None) -> dict:
    """AI analysis state for one slide, safe to show participants (counts only)."""
    if slide.slide_type != MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        return {"status": "not_applicable", "message": ""}
    if not ai_mode_enabled(meeting):
        return {
            "status": "disabled",
            "message": "AI analysis is off for this meeting. Results show answers as written.",
        }
    summary = classification or {}
    pending = int(summary.get("pending", 0))
    processed = sum(int(summary.get(key, 0)) for key in ("classified", "needs_review", "invalid"))
    total = pending + processed
    counts = {"pending": pending, "processed": processed, "total": total}
    if total == 0:
        return {"status": "no_responses", "message": "No answers to analyze yet.", **counts}
    if processed == 0:
        return {
            "status": "pending",
            "message": "The facilitator has not run AI analysis yet. Results show answers as written.",
            **counts,
        }
    if pending > 0:
        return {
            "status": "partial",
            "message": (
                f"AI analysis covers {processed} of {total} answers. Newer answers show as "
                "written until the facilitator runs it again."
            ),
            **counts,
        }
    return {
        "status": "ready",
        "message": "AI analysis is up to date. Similar answers are grouped by issue.",
        **counts,
    }


# --- Meetings -----------------------------------------------------------------


def released_meeting_slides(meeting: Meeting, session: MeetingSession) -> list[MeetingSlide]:
    order = [int(i) for i in (session.participant_results_released_slide_ids or [])]
    slides = {
        s.id: s
        for s in meeting.slides.filter(is_active=True, id__in=order)
        if is_analyzable_slide(s)
    }
    return [slides[i] for i in order if i in slides]


def set_meeting_slide_released(session: MeetingSession, slide: MeetingSlide, released: bool) -> None:
    if not is_analyzable_slide(slide):
        raise ValidationError("Only question slides have results to share.")
    session.participant_results_released_slide_ids = _toggle_id(
        session.participant_results_released_slide_ids, slide.id, released
    )
    session.save(update_fields=["participant_results_released_slide_ids"])


def _participant_attendance(session: MeetingSession, attendance_id: str | None) -> MeetingAttendance:
    if not attendance_id:
        raise LiveResultsDenied("Join the meeting to view live results.", "join_required")
    try:
        parsed = uuid.UUID(str(attendance_id))
    except ValueError as exc:
        raise LiveResultsDenied("Join the meeting to view live results.", "join_required") from exc
    attendance = MeetingAttendance.objects.filter(session=session, attendance_id=parsed).first()
    if not attendance:
        raise LiveResultsDenied("Join the meeting to view live results.", "join_required")
    return attendance


def meeting_live_results(
    meeting: Meeting,
    session: MeetingSession | None,
    *,
    attendance_id: str | None,
    slide_id: int | None,
) -> dict[str, Any]:
    if not meeting.live_results_for_participants:
        raise LiveResultsDenied("Live results are not turned on for this meeting.", "disabled")
    if not session or session.status == MeetingSession.Status.SCHEDULED:
        raise LiveResultsDenied("This meeting has not started yet.", "not_started", 409)
    _participant_attendance(session, attendance_id)

    released = released_meeting_slides(meeting, session)
    items = [
        {"id": s.id, "title": s.title or s.prompt or "Question", "order": s.order}
        for s in released
    ]
    payload: dict[str, Any] = {
        "kind": "meeting",
        "meeting_id": meeting.id,
        "title": meeting.title,
        "session_status": session.status,
        "released_items": items,
        "result": None,
    }
    if not released:
        return payload

    by_id = {s.id: s for s in released}
    if slide_id is not None:
        slide = by_id.get(int(slide_id))
        if not slide:
            raise LiveResultsDenied(
                "The facilitator has not shared results for this question.", "not_released"
            )
    else:
        slide = released[-1]

    analytics = get_slide_analytics(meeting, session, slide, limit=RESULT_BAR_LIMIT)
    payload["result"] = {
        "item_id": slide.id,
        "title": slide.title or slide.prompt or "Question",
        "prompt": slide.prompt if slide.title else "",
        "item_type": slide.slide_type,
        "total_respondents": analytics.get("total_respondents", 0),
        "response_row_count": analytics.get("response_row_count", 0),
        "bars": analytics.get("bars", []),
        "ai": participant_ai_status(meeting, slide, analytics.get("classification")),
        "generated_at": timezone.now(),
    }
    return payload


# --- Surveys ------------------------------------------------------------------


def _is_answerable_question(question: SurveyQuestion) -> bool:
    return question.question_type != SurveyQuestion.QuestionType.CONTENT


def released_survey_questions(survey: Survey) -> list[SurveyQuestion]:
    order = [int(i) for i in (survey.participant_results_released_question_ids or [])]
    questions = {
        q.id: q
        for q in survey.questions.filter(id__in=order)
        if _is_answerable_question(q) and not q.is_demographic
    }
    return [questions[i] for i in order if i in questions]


def set_survey_question_released(survey: Survey, question: SurveyQuestion, released: bool) -> None:
    if not _is_answerable_question(question):
        raise ValidationError("Content blocks have no results to share.")
    if question.is_demographic:
        raise ValidationError("Demographic answers are never shared with respondents.")
    survey.participant_results_released_question_ids = _toggle_id(
        survey.participant_results_released_question_ids, question.id, released
    )
    survey.save(update_fields=["participant_results_released_question_ids"])


def survey_question_bars(question: SurveyQuestion) -> dict[str, Any]:
    answers = list(SurveyAnswer.objects.filter(question=question).values_list("response_session", "value"))
    counts: Counter = Counter()
    choices = list(question.choices or [])
    for _session, value in answers:
        text = (value or "").strip()
        if not text:
            continue
        if question.question_type == SurveyQuestion.QuestionType.CHOICE and choices:
            if text in choices:
                counts[text] += 1
                continue
            for part in (p.strip() for p in text.split(",")):
                if part in choices:
                    counts[part] += 1
            continue
        counts[text] += 1
    ordered = choices if question.question_type == SurveyQuestion.QuestionType.CHOICE and choices else None
    return {
        "bars": _bars_from_counter(counts, ordered_labels=ordered, limit=RESULT_BAR_LIMIT),
        "total_respondents": len({s for s, v in answers if (v or "").strip()}),
        "response_row_count": len(answers),
    }


def survey_live_results(
    survey: Survey,
    *,
    response_session: str | None,
    question_id: int | None,
) -> dict[str, Any]:
    if not survey.live_results_for_respondents:
        raise LiveResultsDenied("Live results are not turned on for this survey.", "disabled")
    session = (response_session or "").strip()
    if not session or not SurveySubmission.objects.filter(
        survey=survey, response_session=session
    ).exists():
        raise LiveResultsDenied("Submit the survey to view live results.", "submit_required")

    released = released_survey_questions(survey)
    payload: dict[str, Any] = {
        "kind": "survey",
        "survey_id": survey.id,
        "title": survey.title,
        "released_items": [
            {"id": q.id, "title": q.text or "Question", "order": q.order} for q in released
        ],
        "result": None,
    }
    if not released:
        return payload

    by_id = {q.id: q for q in released}
    if question_id is not None:
        question = by_id.get(int(question_id))
        if not question:
            raise LiveResultsDenied(
                "The organizer has not shared results for this question.", "not_released"
            )
    else:
        question = released[-1]

    stats = survey_question_bars(question)
    payload["result"] = {
        "item_id": question.id,
        "title": question.text or "Question",
        "prompt": "",
        "item_type": question.question_type,
        **stats,
        "ai": {"status": "not_applicable", "message": ""},
        "generated_at": timezone.now(),
    }
    return payload
