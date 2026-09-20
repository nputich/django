"""
Umbrella licensing: a paid org shares a code; member orgs run on its plan and
their metered usage pools against the licensor.

Flow
----
1. Licensor (with an active, non-umbrella paid service) creates a license →
   gets a shareable code (rotatable, deactivatable).
2. A member org admin enters the code on its Billing page →
   * accepted ``umbrella_member`` relationship (licensor → member),
   * ``OrganizationService`` for the member with billing_source=UMBRELLA_LICENSE
     mirroring the licensor's level,
   * FYI message in the licensor's inbox.
3. Usage by the member counts against the licensor's pooled period
   (see ``usage_service.billing_organization``) and is also recorded on the
   member's own period for the parent usage portal.
4. Either side can end membership; the member drops back to FREE.
"""

from __future__ import annotations

import re
import secrets

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .billing_plans import SERVICE_LEVEL_LABELS
from .billing_service import (
    CheckoutError,
    activate_organization_service,
    create_pending_organization_service,
    get_active_organization_service,
    next_billing_reference,
)
from .models import (
    Organization,
    OrganizationRelationship,
    OrganizationService,
    OrganizationUsagePeriod,
    UmbrellaLicense,
)
from .relationship_service import _post_message, expire_if_due  # noqa: PLC2701

Kind = OrganizationRelationship.Kind
RelStatus = OrganizationRelationship.Status

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class UmbrellaError(CheckoutError):
    """Umbrella license problem (code carries a machine-readable reason)."""


def _org_ref(org: Organization) -> dict:
    return {"id": org.id, "name": org.name, "slug": org.slug}


def generate_umbrella_code() -> str:
    while True:
        body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        code = f"UMB-{body[:4]}-{body[4:]}"
        if not UmbrellaLicense.objects.filter(code=code).exists():
            return code


def normalize_umbrella_code(raw: str | None) -> str:
    """Accept UMB-XXXX-XXXX, UMB-XXXXXXXX, UMBXXXXXXXX, or bare XXXXXXXX."""
    text = re.sub(r"[^A-Z0-9]", "", (raw or "").upper())
    if text.startswith("UMB"):
        text = text[3:]
    if len(text) == 8:
        return f"UMB-{text[:4]}-{text[4:]}"
    return (raw or "").strip().upper()


# --------------------------------------------------------------------------- #
# Licensor side
# --------------------------------------------------------------------------- #


def licensor_service(organization: Organization) -> OrganizationService | None:
    """The licensor's own (non-umbrella) active paid service, or None."""
    service = get_active_organization_service(organization)
    if not service:
        return None
    if service.billing_source == OrganizationService.BillingSource.UMBRELLA_LICENSE:
        return None
    return service


def get_license(organization: Organization) -> UmbrellaLicense | None:
    return UmbrellaLicense.objects.filter(organization=organization).first()


def can_offer_umbrella(organization: Organization) -> bool:
    return licensor_service(organization) is not None


@transaction.atomic
def create_license(*, organization: Organization, user: User | None) -> UmbrellaLicense:
    if not can_offer_umbrella(organization):
        raise UmbrellaError(
            "An umbrella license requires an active paid plan on this organization.",
            code="paid_plan_required",
        )
    if is_umbrella_member(organization):
        raise UmbrellaError(
            "An organization covered by someone else's umbrella cannot issue its own.",
            code="already_member",
        )
    existing = get_license(organization)
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=["is_active", "updated_at"])
        return existing
    return UmbrellaLicense.objects.create(
        organization=organization,
        code=generate_umbrella_code(),
        created_by=user,
    )


def rotate_code(license: UmbrellaLicense) -> UmbrellaLicense:
    license.code = generate_umbrella_code()
    license.rotated_at = timezone.now()
    license.save(update_fields=["code", "rotated_at", "updated_at"])
    return license


def set_license_active(license: UmbrellaLicense, active: bool) -> UmbrellaLicense:
    """Deactivating stops new redemptions; existing members keep coverage."""
    license.is_active = bool(active)
    license.save(update_fields=["is_active", "updated_at"])
    return license


def member_relationships(licensor: Organization):
    return (
        OrganizationRelationship.objects.filter(
            kind=Kind.UMBRELLA_MEMBER,
            from_organization=licensor,
            status=RelStatus.ACCEPTED,
        )
        .select_related("to_organization")
        .order_by("to_organization__name")
    )


# --------------------------------------------------------------------------- #
# Member side
# --------------------------------------------------------------------------- #


def membership_of(organization: Organization) -> OrganizationRelationship | None:
    return (
        OrganizationRelationship.objects.filter(
            kind=Kind.UMBRELLA_MEMBER,
            to_organization=organization,
            status=RelStatus.ACCEPTED,
        )
        .select_related("from_organization")
        .first()
    )


def is_umbrella_member(organization: Organization) -> bool:
    return membership_of(organization) is not None


def umbrella_licensor_for(organization: Organization) -> Organization | None:
    rel = membership_of(organization)
    return rel.from_organization if rel else None


def member_service(organization: Organization) -> OrganizationService | None:
    return (
        OrganizationService.objects.filter(
            organization=organization,
            status=OrganizationService.Status.ACTIVE,
            billing_source=OrganizationService.BillingSource.UMBRELLA_LICENSE,
        )
        .order_by("-started_at", "-id")
        .first()
    )


def _cancel_member_service(organization: Organization) -> None:
    now = timezone.now()
    OrganizationService.objects.filter(
        organization=organization,
        status=OrganizationService.Status.ACTIVE,
        billing_source=OrganizationService.BillingSource.UMBRELLA_LICENSE,
    ).update(status=OrganizationService.Status.CANCELLED, cancelled_at=now, updated_at=now)


@transaction.atomic
def redeem_umbrella_code(
    *, organization: Organization, user: User | None, code: str
) -> tuple[OrganizationRelationship, OrganizationService]:
    normalized = normalize_umbrella_code(code)
    license = (
        UmbrellaLicense.objects.select_related("organization")
        .filter(code=normalized)
        .first()
    )
    if not license or not license.is_active:
        raise UmbrellaError("That umbrella code is not valid.", code="invalid_umbrella_code")
    licensor = license.organization
    if licensor.id == organization.id:
        raise UmbrellaError(
            "You cannot redeem your own umbrella code.", code="self_redemption"
        )
    if licensor.status != Organization.Status.ACTIVE or not licensor.is_active:
        raise UmbrellaError("That umbrella code is not valid.", code="invalid_umbrella_code")
    backing = licensor_service(licensor)
    if not backing:
        raise UmbrellaError(
            f"{licensor.name}'s umbrella license is not currently backed by an active plan.",
            code="licensor_plan_inactive",
        )
    if license.max_members is not None:
        if member_relationships(licensor).count() >= license.max_members:
            raise UmbrellaError(
                "This umbrella license has reached its member limit.",
                code="umbrella_full",
            )

    own = get_active_organization_service(organization)
    if own and own.billing_source != OrganizationService.BillingSource.UMBRELLA_LICENSE:
        raise UmbrellaError(
            "This organization already has an active paid service. "
            "Cancel it before joining an umbrella license.",
            code="active_subscription_exists",
        )
    if is_umbrella_member(organization):
        raise UmbrellaError(
            "This organization is already covered by an umbrella license.",
            code="already_member",
        )
    if member_relationships(organization).exists():
        raise UmbrellaError(
            "An organization that issues its own umbrella license cannot join another.",
            code="is_licensor",
        )
    # Cycle guard via parent chain: licensor cannot be below this org.
    from .relationship_service import _is_ancestor  # noqa: PLC0415

    if _is_ancestor(organization, licensor):
        raise UmbrellaError(
            "This would create a circular organization chain.", code="cycle"
        )

    now = timezone.now()
    OrganizationService.objects.filter(
        organization=organization,
        status=OrganizationService.Status.PENDING,
        billing_source=OrganizationService.BillingSource.PAYPAL,
    ).update(status=OrganizationService.Status.CANCELLED, cancelled_at=now)

    rel = OrganizationRelationship.objects.create(
        kind=Kind.UMBRELLA_MEMBER,
        status=RelStatus.ACCEPTED,
        from_organization=licensor,
        to_organization=organization,
        initiated_by_organization=organization,
        requested_by=user,
        responded_by=user,
        responded_at=now,
        public=True,
        note="Joined via umbrella code",
    )

    service = create_pending_organization_service(
        organization=organization,
        service_level=backing.service_level,
        billing_source=OrganizationService.BillingSource.UMBRELLA_LICENSE,
        paypal_plan_id="",
        billing_reference=next_billing_reference(organization),
        requested_by=user,
    )
    service = activate_organization_service(service)
    service.paypal_subscription_id = ""
    service.cancelled_at = None
    service.cancel_at_period_end = False
    service.current_period_end = backing.current_period_end
    service.umbrella_license = license
    service.save(
        update_fields=[
            "paypal_subscription_id",
            "cancelled_at",
            "cancel_at_period_end",
            "current_period_end",
            "umbrella_license",
            "updated_at",
        ]
    )

    level_label = SERVICE_LEVEL_LABELS.get(backing.service_level, backing.service_level)
    rel.conversation = _post_message(
        conversation=None,
        sender_org=organization,
        recipient_org=licensor,
        subject=f"{organization.name} joined your umbrella license",
        body=(
            f"{organization.name} redeemed your umbrella code and is now covered by "
            f"your {level_label} plan. Their meetings, surveys, board posts, and AI runs "
            f"count against your pooled usage.\n\n"
            "You can review members and usage, remove members, or rotate the code in "
            "your Billing → Umbrella license portal."
        ),
    )
    rel.save(update_fields=["conversation"])
    return rel, service


@transaction.atomic
def remove_member(
    rel: OrganizationRelationship, *, acting_org: Organization, user: User | None
) -> OrganizationRelationship:
    """End umbrella membership from either side and drop the member to FREE."""
    if rel.kind != Kind.UMBRELLA_MEMBER or rel.status != RelStatus.ACCEPTED:
        raise UmbrellaError("This membership is not active.", code="not_active")
    if acting_org.id not in (rel.from_organization_id, rel.to_organization_id):
        raise UmbrellaError("You are not part of this umbrella license.", code="not_party")
    now = timezone.now()
    rel.status = RelStatus.ENDED
    rel.ended_at = now
    rel.ended_by_organization = acting_org
    rel.save(update_fields=["status", "ended_at", "ended_by_organization"])
    _cancel_member_service(rel.to_organization)

    other = rel.counterpart_of(acting_org)
    if acting_org.id == rel.from_organization_id:
        body = (
            f"{acting_org.name} removed {other.name} from its umbrella license. "
            f"{other.name} is now on the free plan."
        )
    else:
        body = (
            f"{acting_org.name} left {other.name}'s umbrella license and is now on "
            "the free plan."
        )
    _post_message(
        conversation=rel.conversation,
        sender_org=acting_org,
        recipient_org=other,
        subject="Umbrella license membership ended",
        body=body,
    )
    return rel


def reconcile_member_service(
    organization: Organization, service: OrganizationService
) -> OrganizationService | None:
    """
    Called from ``get_active_organization_service`` when the active row is
    umbrella-sourced. Cancels it if the licensor's plan lapsed or membership
    ended; mirrors the licensor's level otherwise.
    """
    license = service.umbrella_license
    rel = membership_of(organization)
    licensor = license.organization if license else (rel.from_organization if rel else None)
    backing = licensor_service(licensor) if licensor else None
    if rel is None or backing is None:
        _cancel_member_service(organization)
        if rel is not None and backing is None:
            # Membership remains but has no backing plan: end it cleanly.
            rel.status = RelStatus.ENDED
            rel.ended_at = timezone.now()
            rel.save(update_fields=["status", "ended_at"])
        return None
    changed = []
    if service.service_level != backing.service_level:
        service.service_level = backing.service_level
        changed.append("service_level")
    if service.current_period_end != backing.current_period_end:
        service.current_period_end = backing.current_period_end
        changed.append("current_period_end")
    if changed:
        changed.append("updated_at")
        service.save(update_fields=changed)
    return service


# --------------------------------------------------------------------------- #
# Payloads
# --------------------------------------------------------------------------- #


def _period_counters(period: OrganizationUsagePeriod | None) -> dict:
    if not period:
        return {
            "survey_submissions": 0,
            "meetings_started": 0,
            "ai_meeting_runs": 0,
            "board_posts": 0,
        }
    return {
        "survey_submissions": period.survey_submissions_used,
        "meetings_started": period.meetings_started_used,
        "ai_meeting_runs": period.ai_meeting_runs_used,
        "board_posts": period.board_posts_used,
    }


def member_coverage_payload(organization: Organization) -> dict | None:
    """For the member's Billing page: who covers us."""
    rel = membership_of(organization)
    if not rel:
        return None
    service = member_service(organization)
    return {
        "relationship_id": rel.id,
        "licensor": _org_ref(rel.from_organization),
        "service_level": service.service_level if service else None,
        "service_level_label": SERVICE_LEVEL_LABELS.get(
            service.service_level, service.service_level
        )
        if service
        else None,
        "since": rel.responded_at or rel.created_at,
    }


def license_portal_payload(organization: Organization) -> dict:
    """For the licensor's Umbrella portal."""
    from .usage_service import (  # noqa: PLC0415
        get_or_create_usage_period,
        serialize_usage,
    )

    license = get_license(organization)
    members = []
    if license:
        for rel in member_relationships(organization):
            member = rel.to_organization
            period = get_or_create_usage_period(member)
            members.append(
                {
                    "relationship_id": rel.id,
                    "organization": _org_ref(member),
                    "joined_at": rel.responded_at or rel.created_at,
                    "usage": _period_counters(period),
                    "period_start": period.period_start,
                    "period_end": period.period_end,
                }
            )
    backing = licensor_service(organization)
    return {
        "organization": _org_ref(organization),
        "can_offer": backing is not None,
        "is_member_elsewhere": is_umbrella_member(organization),
        "backing_service_level": backing.service_level if backing else None,
        "backing_service_level_label": (
            SERVICE_LEVEL_LABELS.get(backing.service_level, backing.service_level)
            if backing
            else None
        ),
        "license": (
            {
                "code": license.code,
                "is_active": license.is_active,
                "max_members": license.max_members,
                "created_at": license.created_at,
                "rotated_at": license.rotated_at,
                "member_count": len(members),
            }
            if license
            else None
        ),
        "pooled_usage": serialize_usage(organization),
        "members": members,
    }
