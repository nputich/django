import hashlib

from django.utils import timezone

from .models import Meeting, MeetingSession, MeetingSlide


def hash_private_code(code: str) -> str:
    normalized = code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_private_code(meeting: Meeting, code: str | None) -> bool:
    if not meeting.private_code_hash:
        return True
    if not code or not code.strip():
        return False
    return hash_private_code(code) == meeting.private_code_hash


def meeting_join_error(meeting: Meeting, user, private_code: str | None) -> str | None:
    if meeting.access_mode == Meeting.AccessMode.SEMI_PUBLIC and not user.is_authenticated:
        return "Login required to join this meeting."
    if meeting.access_mode == Meeting.AccessMode.PRIVATE:
        if not user.is_authenticated:
            return "Login required to join this meeting."
        if not verify_private_code(meeting, private_code):
            return "Invalid private meeting code."
    return None


def get_latest_session(meeting: Meeting) -> MeetingSession | None:
    return meeting.sessions.order_by("-session_number").first()


def session_is_joinable(session: MeetingSession) -> bool:
    return session.status in (
        MeetingSession.Status.LIVE,
        MeetingSession.Status.PAUSED,
    )


def session_accepts_responses(session: MeetingSession) -> bool:
    return session.status == MeetingSession.Status.LIVE


def get_active_slides(meeting: Meeting):
    return meeting.slides.filter(is_active=True).order_by("order", "id")


def get_slide_by_id(meeting: Meeting, slide_id: int) -> MeetingSlide:
    return get_active_slides(meeting).get(pk=slide_id)


def can_start_meeting(meeting: Meeting, session: MeetingSession) -> str | None:
    if session.status != MeetingSession.Status.SCHEDULED:
        return "Meeting session has already started or ended."
    if meeting.scheduled_start_at and not meeting.allow_start_early:
        if timezone.now() < meeting.scheduled_start_at:
            return "This meeting cannot start before the scheduled time."
    return None


def start_meeting_session(
    meeting: Meeting,
    session: MeetingSession,
    from_slide: MeetingSlide | None = None,
) -> MeetingSession:
    slides = list(get_active_slides(meeting))
    if not slides:
        raise ValueError("Meeting has no active slides.")
    start_slide = from_slide or slides[0]
    if start_slide not in slides:
        raise ValueError("Invalid start slide for this meeting.")

    now = timezone.now()
    session.status = MeetingSession.Status.LIVE
    session.started_at = now
    session.current_slide = start_slide
    session.started_from_slide = start_slide
    session.ended_at = None
    session.save(
        update_fields=[
            "status",
            "started_at",
            "current_slide",
            "started_from_slide",
            "ended_at",
        ]
    )
    meeting.status = "live"
    meeting.started_at = now
    meeting.ended_at = None
    meeting.save(update_fields=["status", "started_at", "ended_at"])
    return session


def pause_meeting_session(meeting: Meeting, session: MeetingSession) -> MeetingSession:
    if session.status != MeetingSession.Status.LIVE:
        raise ValueError("Only a live meeting can be paused.")
    session.status = MeetingSession.Status.PAUSED
    session.save(update_fields=["status"])
    meeting.status = "paused"
    meeting.save(update_fields=["status"])
    return session


def resume_meeting_session(meeting: Meeting, session: MeetingSession) -> MeetingSession:
    if session.status != MeetingSession.Status.PAUSED:
        raise ValueError("Only a paused meeting can be resumed.")
    session.status = MeetingSession.Status.LIVE
    session.save(update_fields=["status"])
    meeting.status = "live"
    meeting.save(update_fields=["status"])
    return session


def end_meeting_session(meeting: Meeting, session: MeetingSession) -> MeetingSession:
    if session.status == MeetingSession.Status.ENDED:
        raise ValueError("Meeting session has already ended.")
    now = timezone.now()
    session.status = MeetingSession.Status.ENDED
    session.ended_at = now
    session.save(update_fields=["status", "ended_at"])
    meeting.status = "ended"
    meeting.ended_at = now
    meeting.save(update_fields=["status", "ended_at"])
    return session


def _require_controllable_session(session: MeetingSession) -> None:
    if session.status not in (
        MeetingSession.Status.LIVE,
        MeetingSession.Status.PAUSED,
    ):
        raise ValueError("Meeting must be live or paused to control slides.")


def go_to_slide(
    meeting: Meeting,
    session: MeetingSession,
    slide: MeetingSlide,
) -> MeetingSession:
    _require_controllable_session(session)
    slides = list(get_active_slides(meeting))
    if slide not in slides:
        raise ValueError("Slide is not part of this meeting.")
    session.current_slide = slide
    session.save(update_fields=["current_slide"])
    return session


def go_to_next_slide(meeting: Meeting, session: MeetingSession) -> MeetingSession:
    _require_controllable_session(session)
    slides = list(get_active_slides(meeting))
    if not slides or not session.current_slide:
        raise ValueError("No current slide.")
    ids = [s.id for s in slides]
    try:
        idx = ids.index(session.current_slide_id)
    except ValueError:
        session.current_slide = slides[0]
        session.save(update_fields=["current_slide"])
        return session
    if idx >= len(slides) - 1:
        raise ValueError("Already on the last slide.")
    session.current_slide = slides[idx + 1]
    session.save(update_fields=["current_slide"])
    return session


def go_to_previous_slide(meeting: Meeting, session: MeetingSession) -> MeetingSession:
    _require_controllable_session(session)
    slides = list(get_active_slides(meeting))
    if not slides or not session.current_slide:
        raise ValueError("No current slide.")
    ids = [s.id for s in slides]
    try:
        idx = ids.index(session.current_slide_id)
    except ValueError:
        session.current_slide = slides[0]
        session.save(update_fields=["current_slide"])
        return session
    if idx <= 0:
        raise ValueError("Already on the first slide.")
    session.current_slide = slides[idx - 1]
    session.save(update_fields=["current_slide"])
    return session


def restart_meeting_session(
    meeting: Meeting,
    current_session: MeetingSession,
    from_slide: MeetingSlide | None = None,
) -> MeetingSession:
    if current_session.status == MeetingSession.Status.SCHEDULED:
        now = timezone.now()
        current_session.status = MeetingSession.Status.ENDED
        current_session.ended_at = now
        current_session.save(update_fields=["status", "ended_at"])
    elif current_session.status != MeetingSession.Status.ENDED:
        end_meeting_session(meeting, current_session)

    next_number = (
        meeting.sessions.order_by("-session_number")
        .values_list("session_number", flat=True)
        .first()
        or 0
    ) + 1
    slides = list(get_active_slides(meeting))
    if not slides:
        raise ValueError("Meeting has no active slides.")
    start_slide = from_slide or slides[0]
    if start_slide not in slides:
        raise ValueError("Invalid start slide for restart.")

    now = timezone.now()
    new_session = MeetingSession.objects.create(
        meeting=meeting,
        session_number=next_number,
        status=MeetingSession.Status.LIVE,
        current_slide=start_slide,
        started_from_slide=start_slide,
        started_at=now,
    )
    meeting.status = "live"
    meeting.started_at = now
    meeting.ended_at = None
    meeting.save(update_fields=["status", "started_at", "ended_at"])
    return new_session
