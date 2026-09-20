"""
Numeric plan limits (server-side catalog).

None on a published limit means "unlimited" for customers; the matching
abuse cap is still enforced. 0 means the feature is not available.
"""

from __future__ import annotations

from calendar import monthrange

from .billing_plans import (
    SERVICE_LEVEL_BASIC,
    SERVICE_LEVEL_COMMUNITY,
    SERVICE_LEVEL_COMMUNITY_PLUS,
    SERVICE_LEVEL_ENTERPRISE,
    SERVICE_LEVEL_FREE,
    SERVICE_LEVEL_STARTER,
    SERVICE_LEVEL_LABELS,
)

# Complimentary Basic duration — shared with access_codes.
BASIC_ACCESS_CODE_DURATION_MONTHS = 4

PLAN_LIMITS = {
    SERVICE_LEVEL_FREE: {
        "survey_submission_limit": 0,
        "meetings_started_limit": 0,
        "attendee_limit": 0,
        "ai_meeting_runs_limit": 0,
        "board_posts_limit": 5,
        "survey_submission_abuse_limit": 0,
        "meetings_started_abuse_limit": 0,
        "attendee_abuse_limit": 0,
        "ai_meeting_runs_abuse_limit": 0,
        "board_posts_abuse_limit": 10,
    },
    SERVICE_LEVEL_STARTER: {
        "survey_submission_limit": 500,
        "meetings_started_limit": 3,
        "attendee_limit": 50,
        "ai_meeting_runs_limit": 1,
        "board_posts_limit": None,
        "survey_submission_abuse_limit": 750,
        "meetings_started_abuse_limit": 6,
        "attendee_abuse_limit": 75,
        "ai_meeting_runs_abuse_limit": 2,
        "board_posts_abuse_limit": 2_000,
    },
    SERVICE_LEVEL_BASIC: {
        "survey_submission_limit": 2_000,
        "meetings_started_limit": 10,
        "attendee_limit": 200,
        "ai_meeting_runs_limit": 3,
        "board_posts_limit": None,
        "survey_submission_abuse_limit": 3_000,
        "meetings_started_abuse_limit": 20,
        "attendee_abuse_limit": 250,
        "ai_meeting_runs_abuse_limit": 5,
        "board_posts_abuse_limit": 2_000,
    },
    SERVICE_LEVEL_COMMUNITY: {
        "survey_submission_limit": 15_000,
        "meetings_started_limit": 30,
        "attendee_limit": 1_000,
        "ai_meeting_runs_limit": 10,
        "board_posts_limit": None,
        "survey_submission_abuse_limit": 22_500,
        "meetings_started_abuse_limit": 50,
        "attendee_abuse_limit": 1_200,
        "ai_meeting_runs_abuse_limit": 15,
        "board_posts_abuse_limit": 2_000,
    },
    SERVICE_LEVEL_COMMUNITY_PLUS: {
        "survey_submission_limit": 75_000,
        "meetings_started_limit": None,
        "attendee_limit": 5_000,
        "ai_meeting_runs_limit": 30,
        "board_posts_limit": None,
        "survey_submission_abuse_limit": 112_500,
        "meetings_started_abuse_limit": 200,
        "attendee_abuse_limit": 6_000,
        "ai_meeting_runs_abuse_limit": 45,
        "board_posts_abuse_limit": 2_000,
    },
    SERVICE_LEVEL_ENTERPRISE: {
        "survey_submission_limit": None,
        "meetings_started_limit": None,
        "attendee_limit": None,
        "ai_meeting_runs_limit": None,
        "board_posts_limit": None,
        "survey_submission_abuse_limit": 500_000,
        "meetings_started_abuse_limit": 500,
        "attendee_abuse_limit": 50_000,
        "ai_meeting_runs_abuse_limit": 200,
        "board_posts_abuse_limit": 10_000,
    },
}

_METRIC_KEYS = {
    "survey_submissions": ("survey_submission_limit", "survey_submission_abuse_limit"),
    "meetings_started": ("meetings_started_limit", "meetings_started_abuse_limit"),
    "attendees": ("attendee_limit", "attendee_abuse_limit"),
    "ai_meeting_runs": ("ai_meeting_runs_limit", "ai_meeting_runs_abuse_limit"),
    "board_posts": ("board_posts_limit", "board_posts_abuse_limit"),
}


def add_calendar_months(dt, months: int):
    """Add calendar months, clamping the day if the target month is shorter."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def get_plan_limits(service_level: str) -> dict:
    level = (service_level or SERVICE_LEVEL_FREE).upper()
    return PLAN_LIMITS.get(level, PLAN_LIMITS[SERVICE_LEVEL_FREE])


def published_limit(spec: dict, metric: str):
    published_key, _abuse_key = _METRIC_KEYS[metric]
    return spec[published_key]


def effective_limit(spec: dict, metric: str) -> int:
    """Integer cap actually enforced (published, else hidden abuse cap)."""
    published_key, abuse_key = _METRIC_KEYS[metric]
    published = spec[published_key]
    if published is not None:
        return int(published)
    return int(spec[abuse_key])


def public_limits_payload(service_level: str) -> dict:
    spec = get_plan_limits(service_level)
    return {
        "service_level": (service_level or SERVICE_LEVEL_FREE).upper(),
        "service_level_label": SERVICE_LEVEL_LABELS.get(
            (service_level or SERVICE_LEVEL_FREE).upper(), service_level
        ),
        "survey_submission_limit": spec["survey_submission_limit"],
        "meetings_started_limit": spec["meetings_started_limit"],
        "attendee_limit": spec["attendee_limit"],
        "ai_meeting_runs_limit": spec["ai_meeting_runs_limit"],
        "board_posts_limit": spec["board_posts_limit"],
    }
