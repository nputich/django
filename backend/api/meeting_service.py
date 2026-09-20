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


def create_meeting_slides(
    meeting: Meeting,
    slide_payloads: list[dict],
    *,
    added_live: bool = False,
    user=None,
    ensure_disclosure: bool = True,
) -> list[MeetingSlide]:
    from api.content_media import normalize_content_config
    from api.meeting_sharing import ensure_disclosure_slide
    from api.question_tags import apply_payload_tags

    created = []
    for slide_data in slide_payloads:
        config = {}
        if slide_data["slide_type"] == MeetingSlide.SlideType.PARTICIPANT_INFO:
            config = {"fields": slide_data.get("fields", [])}
        elif slide_data["slide_type"] == MeetingSlide.SlideType.CONTENT:
            config = normalize_content_config(
                {
                    "body": slide_data.get("body") or (slide_data.get("config") or {}).get("body", ""),
                    "banner_url": slide_data.get("banner_url")
                    or (slide_data.get("config") or {}).get("banner_url", ""),
                    "video_url": slide_data.get("video_url")
                    or (slide_data.get("config") or {}).get("video_url", ""),
                }
            )
        if added_live:
            config["added_live"] = True

        slide = MeetingSlide.objects.create(
            meeting=meeting,
            order=slide_data.get("order", 0),
            slide_type=slide_data["slide_type"],
            title=slide_data.get("title", ""),
            prompt=slide_data.get("prompt", ""),
            question_format=slide_data.get("question_format", ""),
            choices=slide_data.get("choices", []),
            config=config,
        )
        if slide.is_question:
            apply_payload_tags(
                organization=meeting.organization, slide=slide, payload=slide_data, user=user
            )
        created.append(slide)
    if ensure_disclosure:
        ensure_disclosure_slide(meeting)
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


def replace_meeting_slides(meeting: Meeting, slide_payloads: list[dict], *, user=None) -> list[MeetingSlide]:
    """
    Sync slides to the payload without wiping answered history.

    Matching order: payload ``id`` → same position/type → create.
    Slides removed from the deck are deactivated (``is_active=False``) so
    MeetingResponse rows stay attached for reports and exports.
    """
    from api.content_media import normalize_content_config
    from api.meeting_sharing import ensure_disclosure_slide
    from api.question_tags import apply_payload_tags

    existing = list(meeting.slides.order_by("order", "id"))
    by_id = {s.id: s for s in existing}
    used_ids: set[int] = set()
    kept: list[MeetingSlide] = []

    for index, slide_data in enumerate(slide_payloads):
        config = {}
        if slide_data["slide_type"] == MeetingSlide.SlideType.PARTICIPANT_INFO:
            config = {"fields": slide_data.get("fields", [])}
        elif slide_data["slide_type"] == MeetingSlide.SlideType.CONTENT:
            config = normalize_content_config(
                {
                    "body": slide_data.get("body") or (slide_data.get("config") or {}).get("body", ""),
                    "banner_url": slide_data.get("banner_url")
                    or (slide_data.get("config") or {}).get("banner_url", ""),
                    "video_url": slide_data.get("video_url")
                    or (slide_data.get("config") or {}).get("video_url", ""),
                }
            )
        if slide_data.get("added_live") or (slide_data.get("config") or {}).get("added_live"):
            config["added_live"] = True

        slide = None
        raw_id = slide_data.get("id")
        if raw_id is not None:
            try:
                slide = by_id.get(int(raw_id))
            except (TypeError, ValueError):
                slide = None
        if slide is None and index < len(existing):
            candidate = existing[index]
            if candidate.id not in used_ids and candidate.slide_type == slide_data["slide_type"]:
                slide = candidate

        fields = {
            "order": slide_data.get("order", index),
            "slide_type": slide_data["slide_type"],
            "title": slide_data.get("title", ""),
            "prompt": slide_data.get("prompt", ""),
            "question_format": slide_data.get("question_format", ""),
            "choices": slide_data.get("choices", []),
            "config": config,
            "is_active": True,
        }

        if slide is not None:
            # Preserve live-added flag if the organizer is only editing text.
            if (slide.config or {}).get("added_live") and "added_live" not in config:
                config["added_live"] = True
                fields["config"] = config
            for key, value in fields.items():
                setattr(slide, key, value)
            slide.save()
            used_ids.add(slide.id)
        else:
            slide = MeetingSlide.objects.create(meeting=meeting, **fields)

        if slide.is_question:
            apply_payload_tags(
                organization=meeting.organization, slide=slide, payload=slide_data, user=user
            )
        kept.append(slide)

    for slide in existing:
        if slide.id not in {s.id for s in kept} and slide.is_active:
            slide.is_active = False
            slide.save(update_fields=["is_active"])

    ensure_disclosure_slide(meeting)
    return kept


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


def _assert_slide_response_allowed(meeting: Meeting, session: MeetingSession, slide: MeetingSlide) -> None:
    if session.status != MeetingSession.Status.LIVE:
        raise ValidationError("The meeting is paused. Wait for the organizer to resume.")
    if meeting.allow_self_paced:
        return
    if session.current_slide_id != slide.id:
        raise ValidationError("You can only respond to the organizer's current slide.")


def submit_participant_profile(
    attendance: MeetingAttendance,
    slide: MeetingSlide,
    field_values: dict,
) -> None:
    if slide.slide_type != MeetingSlide.SlideType.PARTICIPANT_INFO:
        raise ValidationError("This slide is not a participant information slide.")

    _assert_slide_response_allowed(attendance.session.meeting, attendance.session, slide)
    fields = slide.config.get("fields", [])
    field_map = {f["key"]: f for f in fields}

    # Disclosure-only (no demographic fields): record acknowledgment.
    if not field_map:
        ParticipantProfileValue.objects.update_or_create(
            attendance=attendance,
            field_key="__disclosure_ack__",
            defaults={"field_label": "Disclosure acknowledged", "value": True},
        )
        return

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
        elif field_type in ("text", "textarea"):
            if value is None:
                raise ValidationError(f"Invalid value for {field_def.get('label', key)}.")
            field_values[key] = str(value)

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


def acknowledge_content_slide(
    meeting: Meeting,
    session: MeetingSession,
    attendance: MeetingAttendance,
    slide: MeetingSlide,
) -> MeetingResponse:
    if slide.slide_type != MeetingSlide.SlideType.CONTENT:
        raise ValidationError("This endpoint is only for content slides.")
    _assert_slide_response_allowed(meeting, session, slide)
    response, _ = MeetingResponse.objects.update_or_create(
        session=session,
        slide=slide,
        participant_id=attendance.participant_id,
        defaults={
            "meeting": meeting,
            "attendance": attendance,
            "user": attendance.user,
            "raw_response": "__viewed__",
            "selected_options": [],
            "normalization_status": "complete",
        },
    )
    return response


def submit_slide_response(
    meeting: Meeting,
    session: MeetingSession,
    attendance: MeetingAttendance,
    slide: MeetingSlide,
    raw_response: str = "",
    selected_options: list | None = None,
) -> MeetingResponse:
    if slide.slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO:
        raise ValidationError("Use the profile endpoint for participant info slides.")
    if slide.slide_type == MeetingSlide.SlideType.CONTENT:
        return acknowledge_content_slide(meeting, session, attendance, slide)

    _assert_slide_response_allowed(meeting, session, slide)

    selected_options = selected_options or []
    text = raw_response.strip()

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

    defaults = {
        "meeting": meeting,
        "attendance": attendance,
        "user": attendance.user,
        "raw_response": text,
        "selected_options": selected_options,
        "normalization_status": "pending",
        "importance_order": 1
        if slide.slide_type
        in (
            MeetingSlide.SlideType.ISSUE_CARD,
            MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
        )
        else None,
    }
    if slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
        defaults.update(
            {
                "normalized_response": "",
                "major_issue": "",
                "specific_issue": "",
                "issue_type": "",
                "classification_confidence": None,
                "classification_status": "pending",
                "review_reason": "",
                "classified_raw_snapshot": "",
                "classification_processed_at": None,
            }
        )

    response, _ = MeetingResponse.objects.update_or_create(
        session=session,
        slide=slide,
        participant_id=attendance.participant_id,
        defaults=defaults,
    )
    return response


def submit_issue_card_responses(
    meeting: Meeting,
    session: MeetingSession,
    attendance: MeetingAttendance,
    slide: MeetingSlide,
    issues: list[dict],
) -> list[MeetingResponse]:
    if slide.slide_type not in (
        MeetingSlide.SlideType.ISSUE_CARD,
        MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
    ):
        raise ValidationError("This endpoint is only for issue card slides.")

    _assert_slide_response_allowed(meeting, session, slide)

    cleaned: list[dict] = []
    for item in issues:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        order = item.get("importance_order")
        cleaned.append(
            {
                "text": text,
                "importance_order": int(order) if order is not None else len(cleaned) + 1,
            }
        )

    if not cleaned:
        raise ValidationError("Add at least one issue before submitting.")

    cleaned.sort(key=lambda row: row["importance_order"])
    for index, item in enumerate(cleaned, start=1):
        item["importance_order"] = index

    MeetingResponse.objects.filter(
        session=session,
        slide=slide,
        participant_id=attendance.participant_id,
    ).delete()

    responses: list[MeetingResponse] = []
    for item in cleaned:
        responses.append(
            MeetingResponse.objects.create(
                meeting=meeting,
                session=session,
                slide=slide,
                attendance=attendance,
                user=attendance.user,
                participant_id=attendance.participant_id,
                raw_response=item["text"],
                importance_order=item["importance_order"],
                normalization_status="pending",
            )
        )
    return responses


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
    fields = slide.config.get("fields", [])
    if not fields:
        return attendance.profile_values.filter(field_key="__disclosure_ack__").exists()
    required_keys = [f["key"] for f in fields if f.get("required")]
    if not required_keys:
        return attendance.profile_values.exclude(field_key="__disclosure_ack__").exists()
    saved_keys = set(attendance.profile_values.values_list("field_key", flat=True))
    return all(key in saved_keys for key in required_keys)


def append_meeting_slides(
    meeting: Meeting, slide_payloads: list[dict], *, added_live: bool = False, user=None
) -> list[MeetingSlide]:
    max_order = (
        meeting.slides.filter(is_active=True).order_by("-order").values_list("order", flat=True).first()
    )
    base_order = (max_order or 0) + 1
    normalized = []
    for index, slide_data in enumerate(slide_payloads):
        normalized.append({**slide_data, "order": slide_data.get("order", base_order + index)})
    # Never reorder a running deck; the disclosure slide already exists.
    return create_meeting_slides(
        meeting, normalized, added_live=added_live, user=user, ensure_disclosure=not added_live
    )


def reusable_slides_payload(meeting: Meeting) -> dict:
    """Planned vs live-added question slides from a past meeting, for reuse."""
    from api.question_tags import serialize_tag, tags_for_slide

    planned, live_added = [], []
    for slide in get_active_slides(meeting):
        if not slide.is_question:
            continue
        item = {
            "id": slide.id,
            "order": slide.order,
            "slide_type": slide.slide_type,
            "title": slide.title,
            "prompt": slide.prompt,
            "question_format": slide.question_format,
            "choices": slide.choices,
            "response_count": slide.responses.count(),
            "tag_ids": [t.id for t in tags_for_slide(slide)],
            "tags": [serialize_tag(t) for t in tags_for_slide(slide)],
        }
        (live_added if slide.config.get("added_live") else planned).append(item)
    return {
        "meeting": {
            "id": meeting.id,
            "title": meeting.title,
            "status": meeting.status,
            "started_at": meeting.started_at,
            "ended_at": meeting.ended_at,
        },
        "planned": planned,
        "live_added": live_added,
    }


def get_organizer_live_payload(meeting: Meeting, session: MeetingSession) -> dict:
    from django.db.models import Count

    from api.meeting_ai import ai_mode_enabled
    from api.meeting_analytics import get_demographic_fields

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
                "is_analyzable": slide.slide_type
                in (
                    MeetingSlide.SlideType.STANDARD,
                    MeetingSlide.SlideType.ISSUE_CARD,
                    MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
                ),
                "is_content": slide.slide_type == MeetingSlide.SlideType.CONTENT,
            }
        )

    return {
        "meeting_id": meeting.id,
        "meeting_title": meeting.title,
        "meeting_status": meeting.status,
        "is_anonymous": meeting.is_anonymous,
        "allow_self_paced": meeting.allow_self_paced,
        "ai_mode": meeting.ai_mode,
        "ai_pending_count": MeetingResponse.objects.filter(
            meeting=meeting,
            session=session,
            normalization_status="pending",
        ).exclude(raw_response="").count()
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
        "demographic_fields": get_demographic_fields(meeting),
    }


def get_active_slides(meeting: Meeting):
    return meeting.slides.filter(is_active=True).order_by("order", "id")
