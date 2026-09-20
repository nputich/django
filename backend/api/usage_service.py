"""
Billing-period usage counters and capacity checks.

Usage periods are append-only. Visible counters live on OrganizationUsagePeriod;
historical rows are kept. Attendee counts are derived from MeetingAttendance.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .billing_plans import SERVICE_LEVEL_LABELS
from .billing_service import get_active_organization_service, get_current_service_level
from .models import (
    AiUsageEvent,
    Meeting,
    MeetingAttendance,
    MeetingSession,
    Organization,
    OrganizationUsagePeriod,
    Survey,
    SurveySubmission,
)
from .plan_limits import (
    add_calendar_months,
    effective_limit,
    get_plan_limits,
    published_limit,
    public_limits_payload,
)


class CapacityDenied(Exception):
    def __init__(self, message: str, *, code: str = "capacity_reached", metric: str = ""):
        super().__init__(message)
        self.message = message
        self.code = code
        self.metric = metric


def capacity_denied_response(exc: CapacityDenied) -> Response:
    return Response(
        {
            "detail": exc.message,
            "code": exc.code,
            "metric": exc.metric,
            "upgrade_required": True,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def usage_period_bounds(organization: Organization, *, now=None):
    now = now or timezone.now()
    service = get_active_organization_service(organization)
    if service and service.started_at:
        start = service.started_at
        while add_calendar_months(start, 1) <= now:
            start = add_calendar_months(start, 1)
        return start, add_calendar_months(start, 1)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, add_calendar_months(start, 1)


def get_or_create_usage_period(
    organization: Organization, *, now=None
) -> OrganizationUsagePeriod:
    start, end = usage_period_bounds(organization, now=now)
    period, _created = OrganizationUsagePeriod.objects.get_or_create(
        organization=organization,
        period_start=start,
        defaults={
            "period_end": end,
            "service_level": get_current_service_level(organization),
        },
    )
    return period


def _locked_period(organization: Organization) -> OrganizationUsagePeriod:
    period = get_or_create_usage_period(organization)
    return OrganizationUsagePeriod.objects.select_for_update().get(pk=period.pk)


def billing_organization(organization: Organization) -> Organization:
    """
    The org whose plan limits and usage pool apply.

    Umbrella-license members pool against their licensor; everyone else is
    their own billing org.
    """
    from .umbrella_service import umbrella_licensor_for  # noqa: PLC0415

    return umbrella_licensor_for(organization) or organization


def _spec_for(organization: Organization) -> dict:
    return get_plan_limits(get_current_service_level(billing_organization(organization)))


_METRIC_FIELDS = {
    "survey_submissions": "survey_submissions_used",
    "meetings_started": "meetings_started_used",
    "ai_meeting_runs": "ai_meeting_runs_used",
    "board_posts": "board_posts_used",
}


def _consume(organization: Organization, metric: str, message: str) -> OrganizationUsagePeriod:
    """
    Increment ``metric`` for ``organization``.

    Capacity is checked and counted on the billing org's (pool) period. When the
    org is an umbrella member, its own period is incremented too so the licensor
    portal can break usage down per member. Returns the org's own period.
    Callers must be inside ``transaction.atomic``.
    """
    field = _METRIC_FIELDS[metric]
    billing_org = billing_organization(organization)
    pool = _locked_period(billing_org)
    cap = effective_limit(_spec_for(organization), metric)
    if getattr(pool, field) >= cap:
        raise CapacityDenied(message, metric=metric)
    setattr(pool, field, getattr(pool, field) + 1)
    pool.save(update_fields=[field, "updated_at"])
    if billing_org.id == organization.id:
        return pool
    own = _locked_period(organization)
    setattr(own, field, getattr(own, field) + 1)
    own.save(update_fields=[field, "updated_at"])
    return own


def _meter_payload(used: int, published, enforced: int) -> dict:
    remaining = None if published is None else max(enforced - used, 0)
    if published is not None:
        remaining = max(published - used, 0)
    return {
        "used": used,
        "limit": published,
        "remaining": remaining,
    }


def serialize_usage(organization: Organization) -> dict:
    billing_org = billing_organization(organization)
    period = get_or_create_usage_period(billing_org)
    level = get_current_service_level(billing_org)
    spec = get_plan_limits(level)
    pooled = billing_org.id != organization.id
    own_period = get_or_create_usage_period(organization) if pooled else period
    return {
        "service_level": level,
        "service_level_label": SERVICE_LEVEL_LABELS.get(level, level),
        "pooled": pooled,
        "billing_organization": (
            {"id": billing_org.id, "name": billing_org.name, "slug": billing_org.slug}
            if pooled
            else None
        ),
        "own_usage": (
            {
                "survey_submissions": own_period.survey_submissions_used,
                "meetings_started": own_period.meetings_started_used,
                "ai_meeting_runs": own_period.ai_meeting_runs_used,
                "board_posts": own_period.board_posts_used,
            }
            if pooled
            else None
        ),
        "period_start": period.period_start,
        "period_end": period.period_end,
        "survey_submissions": _meter_payload(
            period.survey_submissions_used,
            published_limit(spec, "survey_submissions"),
            effective_limit(spec, "survey_submissions"),
        ),
        "meetings_started": _meter_payload(
            period.meetings_started_used,
            published_limit(spec, "meetings_started"),
            effective_limit(spec, "meetings_started"),
        ),
        "ai_meeting_runs": _meter_payload(
            period.ai_meeting_runs_used,
            published_limit(spec, "ai_meeting_runs"),
            effective_limit(spec, "ai_meeting_runs"),
        ),
        "board_posts": _meter_payload(
            period.board_posts_used,
            published_limit(spec, "board_posts"),
            effective_limit(spec, "board_posts"),
        ),
        "attendee_limit": published_limit(spec, "attendees"),
        "limits": public_limits_payload(level),
    }


def live_attendee_count(session: MeetingSession) -> int:
    return session.attendances.filter(status=MeetingAttendance.Status.JOINED).count()


def snapshot_attendee_limit(session: MeetingSession) -> int | None:
    """Persist the plan's attendee cap on first use of this session."""
    if session.attendee_limit is not None:
        return session.attendee_limit
    spec = _spec_for(session.meeting.organization)
    limit = effective_limit(spec, "attendees")
    session.attendee_limit = limit
    session.save(update_fields=["attendee_limit"])
    return limit


@transaction.atomic
def consume_meeting_start(meeting: Meeting) -> OrganizationUsagePeriod:
    """Count the first interactive start of a meeting in this billing period."""
    if meeting.sessions.filter(started_at__isnull=False).exists():
        return get_or_create_usage_period(meeting.organization)

    return _consume(
        meeting.organization,
        "meetings_started",
        "This organization has reached its meeting limit for the current "
        "billing period. Upgrade to start additional interactive meetings.",
    )


def assert_session_has_capacity(session: MeetingSession) -> None:
    limit = snapshot_attendee_limit(session)
    if limit is None:
        return
    if live_attendee_count(session) >= limit:
        raise CapacityDenied(
            "This meeting is at capacity. Interactive attendee limit reached.",
            metric="attendees",
        )


@transaction.atomic
def consume_survey_submission(
    *,
    survey: Survey,
    response_session: str,
) -> tuple[SurveySubmission, bool]:
    """
    Record one completed survey submission.

    Returns (row, created). Duplicate response_session is idempotent.
    """
    existing = SurveySubmission.objects.filter(
        survey=survey, response_session=response_session
    ).first()
    if existing:
        return existing, False

    organization = survey.organization
    period = _consume(
        organization,
        "survey_submissions",
        "This organization has reached its survey response limit for the "
        "current billing period.",
    )

    try:
        with transaction.atomic():
            submission = SurveySubmission.objects.create(
                survey=survey,
                organization=organization,
                usage_period=period,
                response_session=response_session,
            )
    except IntegrityError:
        # Row already existed (race): undo the counter increment at commit
        # time, but keep the connection usable to fetch the existing row.
        transaction.set_rollback(True)
        existing = SurveySubmission.objects.get(
            survey=survey, response_session=response_session
        )
        return existing, False
    return submission, True


@transaction.atomic
def consume_board_post(organization: Organization) -> OrganizationUsagePeriod:
    return _consume(
        organization,
        "board_posts",
        "This organization has reached its community board post limit "
        "for the current billing period.",
    )


def meeting_ai_run_reserved(meeting: Meeting) -> bool:
    period = get_or_create_usage_period(meeting.organization)
    return AiUsageEvent.objects.filter(
        usage_period=period,
        meeting=meeting,
        consumed_run=True,
    ).exists()


@transaction.atomic
def reserve_ai_meeting_run(meeting: Meeting) -> bool:
    """
    Reserve one AI-processed-meeting unit for this meeting in the current period.

    Self-hosted AI does not consume paid units (returns True).
    Returns True if processing may proceed.
    Raises CapacityDenied when the paid quota is exhausted.
    """
    if meeting.ai_mode == Meeting.AIMode.NONE:
        return False
    if meeting.ai_mode == Meeting.AIMode.SELF_HOSTED:
        return True

    organization = meeting.organization
    period = _locked_period(organization)
    if AiUsageEvent.objects.filter(
        usage_period=period, meeting=meeting, consumed_run=True
    ).exists():
        return True

    period = _consume(
        organization,
        "ai_meeting_runs",
        "This organization has reached its AI meeting processing limit "
        "for the current billing period.",
    )
    AiUsageEvent.objects.create(
        organization=organization,
        meeting=meeting,
        usage_period=period,
        provider="paid",
        consumed_run=True,
        success=True,
    )
    return True
