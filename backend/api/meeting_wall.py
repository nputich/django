"""Meeting wall post lifecycle: create, serialize, RSVP, summaries, permissions."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.utils import timezone

from api.board_service import get_org_board, is_org_admin
from api.models import (
    BoardPost,
    Meeting,
    MeetingAttendance,
    MeetingExpectedAttendance,
    MeetingResponse,
    MeetingSummary,
    WallPostType,
)


def meeting_lifecycle_phase(meeting: Meeting) -> str:
    """upcoming | in_progress | complete — based on meeting status, not wall bumps."""
    status = (meeting.status or "").lower()
    if status in ("live", "paused"):
        return "in_progress"
    if status in ("ended", "complete", "completed"):
        return "complete"
    return "upcoming"


def published_summary(meeting: Meeting) -> MeetingSummary | None:
    return (
        meeting.summaries.filter(status=MeetingSummary.Status.PUBLISHED)
        .order_by("-published_at", "-id")
        .first()
    )


def can_view_meeting_results(meeting: Meeting, user: User | None) -> bool:
    if is_org_admin(meeting.organization, user):
        return True
    if meeting_lifecycle_phase(meeting) != "complete":
        return False
    return bool(meeting.results_visible_to_community)


def can_create_meeting_minutes(meeting: Meeting, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_org_admin(meeting.organization, user):
        return True
    if meeting.minutes_creator != Meeting.MinutesCreator.ORGANIZER_OR_ATTENDEES:
        return False
    if meeting_lifecycle_phase(meeting) != "complete":
        return False
    return MeetingAttendance.objects.filter(
        session__meeting=meeting, user=user
    ).exists()


def can_publish_meeting_summary(meeting: Meeting, user: User | None) -> bool:
    return is_org_admin(meeting.organization, user)


def participation_totals(meeting: Meeting) -> dict:
    participant_count = (
        MeetingAttendance.objects.filter(session__meeting=meeting)
        .values("participant_id")
        .distinct()
        .count()
    )
    response_count = MeetingResponse.objects.filter(meeting=meeting).count()
    return {
        "participant_count": participant_count,
        "response_count": response_count,
    }


def create_meeting_wall_post(*, meeting: Meeting, author: User) -> BoardPost:
    """Create a chronological wall post for a new meeting. Do not bump later."""
    existing = BoardPost.objects.filter(meeting=meeting).first()
    if existing:
        return existing

    board = get_org_board(meeting.organization)
    return BoardPost.objects.create(
        board=board,
        author=author,
        post_type=WallPostType.MEETING,
        title=meeting.title,
        body="",
        event_starts_at=meeting.scheduled_start_at,
        event_ends_at=meeting.scheduled_end_at,
        event_location=meeting.location or "",
        meeting=meeting,
    )


def sync_meeting_wall_post_fields(meeting: Meeting) -> None:
    """Update display fields on the linked wall post without changing created_at."""
    try:
        post = meeting.wall_post
    except BoardPost.DoesNotExist:
        return
    BoardPost.objects.filter(pk=post.pk).update(
        title=meeting.title,
        event_starts_at=meeting.scheduled_start_at,
        event_ends_at=meeting.scheduled_end_at,
        event_location=meeting.location or "",
        updated_at=timezone.now(),
    )


def serialize_meeting_wall_card(meeting: Meeting, user: User | None) -> dict:
    phase = meeting_lifecycle_phase(meeting)
    is_admin = is_org_admin(meeting.organization, user)
    published = published_summary(meeting)
    my_rsvp = None
    if user and user.is_authenticated:
        row = MeetingExpectedAttendance.objects.filter(
            meeting=meeting, user=user
        ).first()
        if row:
            my_rsvp = row.status

    payload = {
        "id": meeting.id,
        "title": meeting.title,
        "organization_name": meeting.organization.name,
        "organization_slug": meeting.organization.slug,
        "phase": phase,
        "status": meeting.status,
        "scheduled_start_at": meeting.scheduled_start_at,
        "scheduled_end_at": meeting.scheduled_end_at,
        "location": meeting.location or "",
        "results_visible_to_community": meeting.results_visible_to_community,
        "minutes_creator": meeting.minutes_creator,
        "my_rsvp": my_rsvp,
        "paths": {
            "details": f"/m/{meeting.id}/details",
            "join": f"/m/{meeting.id}",
            "results": f"/m/{meeting.id}/results",
            "summary": f"/m/{meeting.id}/summary",
        },
        "actions": {
            "can_rsvp": bool(user and user.is_authenticated) and phase == "upcoming",
            "can_view_details": True,
            "can_join": phase == "in_progress",
            "can_view_results": False,
            "can_read_summary": False,
            "can_create_summary": False,
        },
        "totals": None,
        "published_summary_id": published.id if published else None,
        "is_organizer": is_admin,
    }

    if phase == "complete":
        can_results = can_view_meeting_results(meeting, user)
        payload["actions"]["can_view_results"] = can_results
        if can_results:
            payload["totals"] = participation_totals(meeting)
        if published:
            payload["actions"]["can_read_summary"] = True
        payload["actions"]["can_create_summary"] = can_create_meeting_minutes(
            meeting, user
        ) and published is None

    return payload


def set_expected_attendance(
    *, meeting: Meeting, user: User, status: str | None
) -> MeetingExpectedAttendance | None:
    """Set Going/Pending or remove response when status is None/empty."""
    if not status:
        MeetingExpectedAttendance.objects.filter(meeting=meeting, user=user).delete()
        return None
    if status not in MeetingExpectedAttendance.Status.values:
        raise ValueError("Invalid RSVP status.")
    row, _ = MeetingExpectedAttendance.objects.update_or_create(
        meeting=meeting,
        user=user,
        defaults={"status": status},
    )
    return row
