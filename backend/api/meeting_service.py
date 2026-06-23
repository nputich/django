import uuid

from django.core.exceptions import ValidationError

from api.models import (
    Meeting,
    MeetingAttendance,
    MeetingResponse,
    MeetingSession,
    MeetingSlide,
    ParticipantProfileValue,
)


def create_meeting_slides(meeting: Meeting, slide_payloads: list[dict]) -> list[MeetingSlide]:
    created = []
    for slide_data in slide_payloads:
        config = {}
        if slide_data["slide_type"] == MeetingSlide.SlideType.PARTICIPANT_INFO:
            config = {"fields": slide_data.get("fields", [])}

        created.append(
            MeetingSlide.objects.create(
                meeting=meeting,
                order=slide_data.get("order", 0),
                slide_type=slide_data["slide_type"],
                title=slide_data.get("title", ""),
                prompt=slide_data.get("prompt", ""),
                question_format=slide_data.get("question_format", ""),
                choices=slide_data.get("choices", []),
                config=config,
            )
        )
    return created


def create_initial_session(meeting: Meeting) -> MeetingSession:
    first_slide = meeting.slides.filter(is_active=True).order_by("order", "id").first()
    return MeetingSession.objects.create(
        meeting=meeting,
        session_number=1,
        status=MeetingSession.Status.SCHEDULED,
        current_slide=first_slide,
        started_from_slide=first_slide,
    )


def replace_meeting_slides(meeting: Meeting, slide_payloads: list[dict]) -> list[MeetingSlide]:
    meeting.slides.all().delete()
    return create_meeting_slides(meeting, slide_payloads)


def join_session(
    meeting: Meeting,
    session: MeetingSession,
    user=None,
) -> MeetingAttendance:
    participant_id = uuid.uuid4()
    attendance = MeetingAttendance.objects.create(
        session=session,
        attendance_id=uuid.uuid4(),
        participant_id=participant_id,
        user=user if user and user.is_authenticated else None,
    )
    return attendance


def get_attendance(session: MeetingSession, attendance_id: str) -> MeetingAttendance:
    try:
        parsed = uuid.UUID(str(attendance_id))
    except ValueError as exc:
        raise ValidationError("Invalid attendance_id.") from exc
    try:
        return MeetingAttendance.objects.get(
            session=session,
            attendance_id=parsed,
            status=MeetingAttendance.Status.JOINED,
        )
    except MeetingAttendance.DoesNotExist as exc:
        raise ValidationError("Attendance not found or you have left this meeting.") from exc


def leave_attendance(attendance: MeetingAttendance) -> None:
    from django.utils import timezone

    attendance.status = MeetingAttendance.Status.LEFT
    attendance.left_at = timezone.now()
    attendance.save(update_fields=["status", "left_at"])


def submit_participant_profile(
    attendance: MeetingAttendance,
    slide: MeetingSlide,
    field_values: dict,
) -> None:
    if slide.slide_type != MeetingSlide.SlideType.PARTICIPANT_INFO:
        raise ValidationError("This slide is not a participant information slide.")

    if attendance.session.status != MeetingSession.Status.LIVE:
        raise ValidationError("The meeting is paused. Wait for the organizer to resume.")
    fields = slide.config.get("fields", [])
    field_map = {f["key"]: f for f in fields}

    for key, field_def in field_map.items():
        if field_def.get("required") and key not in field_values:
            raise ValidationError(f"Required field missing: {field_def.get('label', key)}")

    for key, value in field_values.items():
        if key not in field_map:
            raise ValidationError(f"Unknown field: {key}")
        field_def = field_map[key]
        field_type = field_def.get("field_type", "text")
        if field_type == "single_select" and value not in field_def.get("options", []):
            raise ValidationError(f"Invalid option for {field_def.get('label', key)}.")
        if field_type == "multi_select":
            if not isinstance(value, list):
                raise ValidationError(f"{field_def.get('label', key)} must be a list.")
            options = set(field_def.get("options", []))
            if not set(value).issubset(options):
                raise ValidationError(f"Invalid options for {field_def.get('label', key)}.")

    for key, value in field_values.items():
        field_def = field_map[key]
        ParticipantProfileValue.objects.update_or_create(
            attendance=attendance,
            field_key=key,
            defaults={
                "field_label": field_def.get("label", key),
                "value": value,
            },
        )


def submit_slide_response(
    meeting: Meeting,
    session: MeetingSession,
    attendance: MeetingAttendance,
    slide: MeetingSlide,
    response_text: str = "",
    selected_options: list | None = None,
) -> MeetingResponse:
    if slide.slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO:
        raise ValidationError("Use the profile endpoint for participant info slides.")

    if session.current_slide_id != slide.id:
        raise ValidationError("You can only respond to the organizer's current slide.")

    if session.status != MeetingSession.Status.LIVE:
        raise ValidationError("The meeting is paused. Wait for the organizer to resume.")

    selected_options = selected_options or []
    text = response_text.strip()

    if slide.slide_type == MeetingSlide.SlideType.STANDARD:
        if slide.question_format == MeetingSlide.QuestionFormat.TEXT:
            if not text:
                raise ValidationError("A text response is required.")
        elif slide.question_format == MeetingSlide.QuestionFormat.SINGLE_CHOICE:
            if len(selected_options) != 1:
                raise ValidationError("Select exactly one option.")
            if selected_options[0] not in slide.choices:
                raise ValidationError("Invalid option selected.")
            text = selected_options[0]
        elif slide.question_format == MeetingSlide.QuestionFormat.MULTI_CHOICE:
            if not selected_options:
                raise ValidationError("Select at least one option.")
            if not set(selected_options).issubset(set(slide.choices)):
                raise ValidationError("Invalid option selected.")
            text = ", ".join(selected_options)
    else:
        if not text:
            raise ValidationError("A response is required.")

    response, _ = MeetingResponse.objects.update_or_create(
        session=session,
        slide=slide,
        participant_id=attendance.participant_id,
        defaults={
            "meeting": meeting,
            "attendance": attendance,
            "user": attendance.user,
            "response_text": text,
            "selected_options": selected_options,
            "raw_text": text,
            "normalization_status": "pending",
        },
    )
    return response


def get_session_stats(session: MeetingSession) -> dict:
    attendance_count = session.attendances.filter(
        status=MeetingAttendance.Status.JOINED
    ).count()
    current_slide = session.current_slide
    response_count = 0
    if current_slide:
        response_count = MeetingResponse.objects.filter(
            session=session,
            slide=current_slide,
        ).count()
    return {
        "attendance_count": attendance_count,
        "current_slide_response_count": response_count,
    }


def participant_completed_slide_ids(session: MeetingSession, participant_id) -> list[int]:
    response_ids = set(
        MeetingResponse.objects.filter(
            session=session,
            participant_id=participant_id,
        ).values_list("slide_id", flat=True)
    )
    attendance = MeetingAttendance.objects.filter(
        session=session,
        participant_id=participant_id,
        status=MeetingAttendance.Status.JOINED,
    ).first()
    if attendance:
        if attendance.profile_values.exists():
            info_slides = MeetingSlide.objects.filter(
                meeting=session.meeting,
                slide_type=MeetingSlide.SlideType.PARTICIPANT_INFO,
            )
            for slide in info_slides:
                if participant_profile_complete(attendance, slide):
                    response_ids.add(slide.id)
    return list(response_ids)


def participant_profile_complete(attendance: MeetingAttendance, slide: MeetingSlide) -> bool:
    if slide.slide_type != MeetingSlide.SlideType.PARTICIPANT_INFO:
        return True
    required_keys = [
        f["key"]
        for f in slide.config.get("fields", [])
        if f.get("required")
    ]
    if not required_keys:
        return attendance.profile_values.exists()
    saved_keys = set(attendance.profile_values.values_list("field_key", flat=True))
    return all(key in saved_keys for key in required_keys)


def append_meeting_slides(meeting: Meeting, slide_payloads: list[dict]) -> list[MeetingSlide]:
    max_order = (
        meeting.slides.filter(is_active=True).order_by("-order").values_list("order", flat=True).first()
    )
    base_order = (max_order or 0) + 1
    normalized = []
    for index, slide_data in enumerate(slide_payloads):
        normalized.append({**slide_data, "order": slide_data.get("order", base_order + index)})
    return create_meeting_slides(meeting, normalized)


def get_organizer_live_payload(meeting: Meeting, session: MeetingSession) -> dict:
    from django.db.models import Count

    from api.meeting_ai import ai_mode_enabled

    stats = get_session_stats(session)
    slide_stats = (
        MeetingResponse.objects.filter(session=session)
        .values("slide_id")
        .annotate(response_count=Count("id"))
    )
    counts_by_slide = {row["slide_id"]: row["response_count"] for row in slide_stats}

    profile_counts = {}
    for slide in get_active_slides(meeting).filter(
        slide_type=MeetingSlide.SlideType.PARTICIPANT_INFO
    ):
        complete = 0
        for attendance in session.attendances.filter(status=MeetingAttendance.Status.JOINED):
            if participant_profile_complete(attendance, slide):
                complete += 1
        profile_counts[slide.id] = complete

    slides_payload = []
    for slide in get_active_slides(meeting):
        slides_payload.append(
            {
                "id": slide.id,
                "order": slide.order,
                "slide_type": slide.slide_type,
                "title": slide.title,
                "prompt": slide.prompt,
                "is_current": slide.id == session.current_slide_id,
                "response_count": counts_by_slide.get(slide.id, 0)
                if slide.slide_type != MeetingSlide.SlideType.PARTICIPANT_INFO
                else profile_counts.get(slide.id, 0),
            }
        )

    return {
        "meeting_id": meeting.id,
        "meeting_title": meeting.title,
        "meeting_status": meeting.status,
        "is_anonymous": meeting.is_anonymous,
        "ai_mode": meeting.ai_mode,
        "ai_pending_count": MeetingResponse.objects.filter(
            meeting=meeting,
            session=session,
            normalization_status="pending",
        ).exclude(response_text="", raw_text="").count()
        if ai_mode_enabled(meeting)
        else 0,
        "sessions": [
            {
                "id": s.id,
                "session_number": s.session_number,
                "status": s.status,
            }
            for s in meeting.sessions.order_by("session_number")
        ],
        "session": {
            "id": session.id,
            "session_number": session.session_number,
            "status": session.status,
            "current_slide_id": session.current_slide_id,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "attendance_count": stats["attendance_count"],
            "current_slide_response_count": stats["current_slide_response_count"],
        },
        "slides": slides_payload,
    }


def get_active_slides(meeting: Meeting):
    return meeting.slides.filter(is_active=True).order_by("order", "id")
