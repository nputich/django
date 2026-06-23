import csv
import io
import json
from typing import Any

from django.http import HttpResponse

from api.models import (
    AccessCode,
    Meeting,
    MeetingResponse,
    MeetingResponseAI,
    MeetingSession,
    MeetingSlide,
    ParticipantProfileValue,
)

MEETING_DF_COLUMNS = [
    "meeting_id",
    "community_code",
    "meeting_title",
    "session_number",
    "slide_id",
    "slide_order",
    "question_id",
    "question_text",
    "question_type",
    "anonymous_participant_id",
    "attendance_id",
    "response_text",
    "selected_option",
    "provided_answer",
    "major_issue_bucket",
    "specific_issue_bucket",
    "concern_bucket",
    "ai_summary",
    "ai_tags",
    "sentiment",
    "support_level",
    "opposition_level",
    "action_item",
    "decision_made",
    "unresolved_question",
    "timestamp",
    "confidence",
]

PROFILE_EXPORT_COLUMNS = [
    "meeting_id",
    "community_code",
    "meeting_title",
    "session_number",
    "attendance_id",
    "anonymous_participant_id",
    "field_key",
    "field_label",
    "value",
    "timestamp",
]


def _community_code(meeting: Meeting) -> str:
    code = meeting.access_codes.filter(is_active=True, is_primary=True).first()
    if not code:
        code = meeting.access_codes.filter(is_active=True).first()
    return code.code if code else ""


def _question_type(slide: MeetingSlide) -> str:
    if slide.slide_type == MeetingSlide.SlideType.STANDARD and slide.question_format:
        return f"standard:{slide.question_format}"
    return slide.slide_type


def _question_text(slide: MeetingSlide) -> str:
    return slide.prompt or slide.title or slide.slide_type


def _selected_option(response: MeetingResponse) -> str:
    if response.selected_options:
        return ", ".join(str(o) for o in response.selected_options)
    return ""


def _ai_fields(response: MeetingResponse) -> dict[str, Any]:
    try:
        ai = response.ai
    except MeetingResponseAI.DoesNotExist:
        ai = None
    if not ai:
        return {
            "ai_summary": "",
            "ai_tags": "",
            "sentiment": "",
            "support_level": "",
            "opposition_level": "",
            "action_item": "",
            "decision_made": "",
            "unresolved_question": "",
            "confidence": "",
        }
    return {
        "ai_summary": ai.ai_summary,
        "ai_tags": json.dumps(ai.ai_tags) if ai.ai_tags else "",
        "sentiment": ai.sentiment,
        "support_level": ai.support_level,
        "opposition_level": ai.opposition_level,
        "action_item": ai.action_item,
        "decision_made": ai.decision_made,
        "unresolved_question": ai.unresolved_question,
        "confidence": ai.confidence if ai.confidence is not None else "",
    }


def _base_row(meeting: Meeting, session: MeetingSession, response: MeetingResponse, slide: MeetingSlide) -> dict:
    is_issue = slide.slide_type in (
        MeetingSlide.SlideType.ISSUE_CARD,
        MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
    )
    row = {
        "meeting_id": meeting.id,
        "community_code": _community_code(meeting),
        "meeting_title": meeting.title,
        "session_number": session.session_number,
        "slide_id": slide.id,
        "slide_order": slide.order,
        "question_id": slide.id,
        "question_text": _question_text(slide),
        "question_type": _question_type(slide),
        "anonymous_participant_id": str(response.participant_id) if response.participant_id else "",
        "attendance_id": str(response.attendance.attendance_id) if response.attendance_id else "",
        "response_text": response.response_text or response.raw_text,
        "selected_option": _selected_option(response),
        "provided_answer": (response.response_text or response.raw_text) if is_issue else "",
        "major_issue_bucket": "",
        "specific_issue_bucket": "",
        "concern_bucket": "",
        "timestamp": response.created_at.isoformat() if response.created_at else "",
    }
    row.update(_ai_fields(response))
    return row


def _rows_for_response(meeting: Meeting, session: MeetingSession, response: MeetingResponse) -> list[dict]:
    slide = response.slide
    if not slide:
        return []

    classifications = list(response.political_classifications.all())
    if slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD and classifications:
        rows = []
        for path in classifications:
            row = _base_row(meeting, session, response, slide)
            row["major_issue_bucket"] = path.major_issue_bucket
            row["specific_issue_bucket"] = path.specific_issue_bucket
            row["concern_bucket"] = path.concern_bucket
            if path.confidence is not None:
                row["confidence"] = path.confidence
            rows.append(row)
        return rows

    return [_base_row(meeting, session, response, slide)]


def get_sessions_for_export(meeting: Meeting, session_id: str | None) -> list[MeetingSession]:
    qs = meeting.sessions.order_by("session_number")
    if session_id and session_id.lower() != "all":
        return list(qs.filter(pk=session_id))
    return list(qs)


def build_meeting_df(meeting: Meeting, session_id: str | None = None) -> list[dict]:
    rows: list[dict] = []
    sessions = get_sessions_for_export(meeting, session_id)

    for session in sessions:
        responses = (
            MeetingResponse.objects.filter(meeting=meeting, session=session)
            .select_related("slide", "attendance", "session")
            .prefetch_related("political_classifications", "ai")
            .order_by("created_at", "id")
        )
        for response in responses:
            rows.extend(_rows_for_response(meeting, session, response))
    return rows


def build_profile_export(meeting: Meeting, session_id: str | None = None) -> list[dict]:
    rows: list[dict] = []
    code = _community_code(meeting)
    sessions = get_sessions_for_export(meeting, session_id)

    for session in sessions:
        profiles = ParticipantProfileValue.objects.filter(
            attendance__session=session,
        ).select_related("attendance").order_by("created_at", "id")

        for profile in profiles:
            rows.append(
                {
                    "meeting_id": meeting.id,
                    "community_code": code,
                    "meeting_title": meeting.title,
                    "session_number": session.session_number,
                    "attendance_id": str(profile.attendance.attendance_id),
                    "anonymous_participant_id": str(profile.attendance.participant_id),
                    "field_key": profile.field_key,
                    "field_label": profile.field_label,
                    "value": json.dumps(profile.value)
                    if not isinstance(profile.value, str)
                    else profile.value,
                    "timestamp": profile.created_at.isoformat(),
                }
            )
    return rows


def meeting_export_summary(meeting: Meeting) -> dict:
    sessions = list(meeting.sessions.order_by("session_number").values("id", "session_number", "status"))
    return {
        "meeting_id": meeting.id,
        "meeting_title": meeting.title,
        "is_anonymous": meeting.is_anonymous,
        "sessions": sessions,
        "response_row_count": MeetingResponse.objects.filter(meeting=meeting).count(),
        "columns": MEETING_DF_COLUMNS,
        "profile_columns": PROFILE_EXPORT_COLUMNS,
    }


def render_csv(rows: list[dict], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def csv_http_response(filename: str, content: str) -> HttpResponse:
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
