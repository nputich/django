"""
Feature capabilities by organization service level.

Principle:
  FREE  → maintain org + view historical data
  BASIC+ → create and conduct new paid engagement

Never deny READ of existing meetings/surveys/reports because of FREE.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from .billing_plans import (
    SERVICE_LEVEL_BASIC,
    SERVICE_LEVEL_COMMUNITY,
    SERVICE_LEVEL_COMMUNITY_PLUS,
    SERVICE_LEVEL_ENTERPRISE,
    SERVICE_LEVEL_FREE,
    SERVICE_LEVEL_LABELS,
)
from .billing_service import get_current_service_level
from .models import Organization
from .organization_lifecycle import (
    ensure_organization_lifecycle,
    organization_accepts_new_activity,
)

# Ordered from free → highest.
SERVICE_LEVEL_RANK = {
    SERVICE_LEVEL_FREE: 0,
    SERVICE_LEVEL_BASIC: 1,
    SERVICE_LEVEL_COMMUNITY: 2,
    SERVICE_LEVEL_COMMUNITY_PLUS: 3,
    SERVICE_LEVEL_ENTERPRISE: 4,
}

PAID_CREATE_LEVELS = frozenset(
    {
        SERVICE_LEVEL_BASIC,
        SERVICE_LEVEL_COMMUNITY,
        SERVICE_LEVEL_COMMUNITY_PLUS,
        SERVICE_LEVEL_ENTERPRISE,
    }
)


class EntitlementDenied(Exception):
    def __init__(self, message: str, *, code: str = "upgrade_required"):
        super().__init__(message)
        self.code = code
        self.message = message


def service_level_rank(level: str) -> int:
    return SERVICE_LEVEL_RANK.get((level or "").upper(), 0)


def is_paid_service_level(level: str) -> bool:
    return (level or "").upper() in PAID_CREATE_LEVELS


def get_organization_capabilities(organization: Organization) -> dict:
    """
    Capability flags for UI + API.

    View/history flags are always True for active orgs.
    Create / new-engagement flags require Basic or higher and an operational org.
    """
    ensure_organization_lifecycle(organization)
    level = get_current_service_level(organization)
    paid = is_paid_service_level(level)
    operational = organization_accepts_new_activity(organization)
    closed = organization.status == Organization.Status.CLOSED
    return {
        "service_level": level,
        "service_level_label": SERVICE_LEVEL_LABELS.get(level, level),
        "is_free": not paid,
        "organization_status": organization.status,
        "organization_operational": operational,
        # Always retain org + history
        "organization_profile": not closed,
        "messaging": operational,
        "view_meetings": True,
        "view_surveys": True,
        "view_reports": True,
        "view_historical_analytics": True,
        "view_historical_ai": True,
        # New paid engagement
        "create_meetings": paid and operational,
        "start_meetings": paid and operational,
        "create_surveys": paid and operational,
        "run_new_ai_analysis": paid and operational,
        "required_plan_for_create": SERVICE_LEVEL_BASIC,
        "required_plan_label": SERVICE_LEVEL_LABELS[SERVICE_LEVEL_BASIC],
    }


def require_capability(organization: Organization, capability: str) -> dict:
    """
    Return capabilities if allowed; raise EntitlementDenied otherwise.
    """
    caps = get_organization_capabilities(organization)
    if not caps.get(capability):
        label = caps["required_plan_label"]
        messages = {
            "create_meetings": (
                f"Creating new meetings requires CommuniB {label} or higher. "
                "Your previous meetings, responses, and reports remain available."
            ),
            "start_meetings": (
                f"Starting meetings requires CommuniB {label} or higher. "
                "You can still view previous meeting results."
            ),
            "create_surveys": (
                f"Creating new surveys requires CommuniB {label} or higher. "
                "You can continue viewing your previous surveys and results."
            ),
            "run_new_ai_analysis": (
                f"Running new AI analysis requires a paid CommuniB service. "
                "Previously generated AI summaries remain available."
            ),
        }
        raise EntitlementDenied(
            messages.get(
                capability,
                f"This action requires CommuniB {label} or higher.",
            ),
            code="upgrade_required",
        )
    return caps


def entitlement_denied_response(exc: EntitlementDenied) -> Response:
    return Response(
        {
            "detail": exc.message,
            "code": exc.code,
            "upgrade_required": True,
            "required_plan": SERVICE_LEVEL_BASIC,
        },
        status=status.HTTP_403_FORBIDDEN,
    )
