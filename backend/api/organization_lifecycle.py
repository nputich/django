"""
Organization ownership, subscription cancel (keep org), and soft-close lifecycle.

Leaving the organization affects the person.
Canceling service affects the subscription.
Closing the organization affects the organization itself.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .billing_service import (
    get_active_organization_service,
    request_cancel_paid_service,
)
from .models import (
    Organization,
    OrganizationAuditEvent,
    OrganizationMembership,
)
from .paypal_client import PayPalError


class LifecycleError(Exception):
    def __init__(self, message: str, *, code: str = "lifecycle_error"):
        super().__init__(message)
        self.code = code
        self.message = message


def record_audit(
    organization: Organization,
    *,
    actor: User | None,
    event_type: str,
    event_data: dict | None = None,
) -> OrganizationAuditEvent:
    return OrganizationAuditEvent.objects.create(
        organization=organization,
        actor=actor,
        event_type=event_type,
        event_data=event_data or {},
    )


def normalize_org_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def find_closed_name_conflicts(name: str, *, exclude_org_id: int | None = None):
    """Closed / archived orgs that match this name (duplicate protection)."""
    needle = normalize_org_name(name)
    if not needle:
        return Organization.objects.none()
    qs = Organization.objects.filter(status=Organization.Status.CLOSED)
    if exclude_org_id:
        qs = qs.exclude(pk=exclude_org_id)
    matches = []
    for org in qs.only("id", "name", "slug", "status", "closed_at"):
        if normalize_org_name(org.name) == needle:
            matches.append(org)
    return matches


def organization_is_directory_visible(organization: Organization) -> bool:
    ensure_organization_lifecycle(organization)
    return organization.status == Organization.Status.ACTIVE


def organization_accepts_new_activity(organization: Organization) -> bool:
    """Meetings/surveys/board posts/new members while org is operational."""
    ensure_organization_lifecycle(organization)
    return organization.status in {
        Organization.Status.ACTIVE,
        Organization.Status.CLOSURE_PENDING,
    }


def ensure_organization_lifecycle(organization: Organization) -> Organization:
    """
    Apply due closure and expire cancel-at-period-end entitlements.
    Safe to call on read paths.
    """
    now = timezone.now()
    changed = False

    active = get_active_organization_service(organization)
    if (
        active
        and active.cancel_at_period_end
        and active.current_period_end
        and active.current_period_end <= now
    ):
        active.status = active.Status.CANCELLED
        if active.cancelled_at is None:
            active.cancelled_at = now
        active.save(update_fields=["status", "cancelled_at", "updated_at"])
        record_audit(
            organization,
            actor=None,
            event_type=OrganizationAuditEvent.EventType.SUBSCRIPTION_CANCELED,
            event_data={
                "organization_service_id": active.id,
                "reason": "period_ended",
            },
        )

    if (
        organization.status == Organization.Status.CLOSURE_PENDING
        and organization.closure_effective_at
        and organization.closure_effective_at <= now
    ):
        organization.status = Organization.Status.CLOSED
        organization.is_active = False
        if organization.closed_at is None:
            organization.closed_at = now
        organization.save(
            update_fields=["status", "is_active", "closed_at"]
        )
        record_audit(
            organization,
            actor=None,
            event_type=OrganizationAuditEvent.EventType.ORGANIZATION_CLOSED,
            event_data={"reason": "closure_effective"},
        )
        changed = True

    if changed:
        organization.refresh_from_db()
    return organization


def count_owners(organization: Organization) -> int:
    return organization.memberships.filter(
        role=OrganizationMembership.Role.OWNER
    ).count()


def list_transfer_candidates(organization: Organization, *, exclude_user: User):
    """Admins eligible to receive ownership (not the current actor)."""
    return (
        organization.memberships.filter(
            role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.OWNER,
            ]
        )
        .exclude(user=exclude_user)
        .select_related("user")
        .order_by("user__username")
    )


@transaction.atomic
def transfer_ownership(
    organization: Organization,
    *,
    actor: User,
    new_owner: User,
) -> OrganizationMembership:
    ensure_organization_lifecycle(organization)
    if organization.status == Organization.Status.CLOSED:
        raise LifecycleError(
            "Cannot transfer ownership of a closed organization.",
            code="organization_closed",
        )

    actor_membership = organization.memberships.filter(user=actor).first()
    if not actor_membership or actor_membership.role != OrganizationMembership.Role.OWNER:
        raise LifecycleError("Only an owner can transfer ownership.", code="not_owner")

    if new_owner.pk == actor.pk:
        raise LifecycleError("Select a different user as the new owner.", code="invalid_target")

    target = organization.memberships.filter(user=new_owner).first()
    if not target or target.role not in {
        OrganizationMembership.Role.ADMIN,
        OrganizationMembership.Role.OWNER,
    }:
        raise LifecycleError(
            "Ownership can only be transferred to an organization administrator.",
            code="invalid_target",
        )

    # Demote other owners to admin; promote target.
    organization.memberships.filter(role=OrganizationMembership.Role.OWNER).exclude(
        user=new_owner
    ).update(role=OrganizationMembership.Role.ADMIN)
    target.role = OrganizationMembership.Role.OWNER
    target.save(update_fields=["role"])

    record_audit(
        organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.OWNERSHIP_TRANSFERRED,
        event_data={
            "from_user_id": actor.id,
            "to_user_id": new_owner.id,
            "to_username": new_owner.username,
        },
    )
    return target


@transaction.atomic
def cancel_my_ownership(organization: Organization, *, actor: User) -> None:
    ensure_organization_lifecycle(organization)
    membership = organization.memberships.filter(user=actor).first()
    if not membership or membership.role != OrganizationMembership.Role.OWNER:
        raise LifecycleError("Only an owner can cancel ownership.", code="not_owner")

    if count_owners(organization) <= 1:
        raise LifecycleError(
            "You are the only owner. Transfer ownership to another administrator "
            "or close the organization.",
            code="sole_owner",
        )

    membership.role = OrganizationMembership.Role.ADMIN
    membership.save(update_fields=["role"])
    record_audit(
        organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.OWNERSHIP_CANCELED,
        event_data={"former_owner_id": actor.id},
    )


@transaction.atomic
def close_organization(
    organization: Organization,
    *,
    actor: User,
    confirmation_name: str,
) -> Organization:
    ensure_organization_lifecycle(organization)

    membership = organization.memberships.filter(user=actor).first()
    if not membership or membership.role != OrganizationMembership.Role.OWNER:
        raise LifecycleError("Only an owner can close the organization.", code="not_owner")

    if (confirmation_name or "").strip() != organization.name:
        raise LifecycleError(
            "Type the organization name exactly to confirm.",
            code="confirmation_mismatch",
        )

    if organization.status == Organization.Status.CLOSED:
        return organization  # idempotent

    if organization.status == Organization.Status.CLOSURE_PENDING:
        return organization  # already scheduled

    now = timezone.now()
    paid = get_active_organization_service(organization)
    paid_through = None

    if paid:
        try:
            paid = request_cancel_paid_service(paid, actor=actor)
        except PayPalError as exc:
            raise LifecycleError(str(exc), code=getattr(exc, "code", "paypal_error")) from exc
        paid_through = paid.current_period_end or now
        organization.status = Organization.Status.CLOSURE_PENDING
        organization.closure_effective_at = paid_through
        organization.closed_by = actor
        organization.is_active = True
        organization.save(
            update_fields=[
                "status",
                "closure_effective_at",
                "closed_by",
                "is_active",
            ]
        )
        record_audit(
            organization,
            actor=actor,
            event_type=OrganizationAuditEvent.EventType.ORGANIZATION_CLOSURE_REQUESTED,
            event_data={
                "closure_effective_at": paid_through.isoformat(),
                "had_paid_service": True,
            },
        )
        return organization

    organization.status = Organization.Status.CLOSED
    organization.is_active = False
    organization.closed_at = now
    organization.closed_by = actor
    organization.closure_effective_at = now
    organization.save(
        update_fields=[
            "status",
            "is_active",
            "closed_at",
            "closed_by",
            "closure_effective_at",
        ]
    )
    record_audit(
        organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.ORGANIZATION_CLOSED,
        event_data={"had_paid_service": False},
    )
    return organization


@transaction.atomic
def cancel_organization_closure(
    organization: Organization,
    *,
    actor: User,
) -> Organization:
    membership = organization.memberships.filter(user=actor).first()
    if not membership or membership.role != OrganizationMembership.Role.OWNER:
        raise LifecycleError(
            "Only an owner can cancel a scheduled closure.",
            code="not_owner",
        )

    if organization.status != Organization.Status.CLOSURE_PENDING:
        raise LifecycleError(
            "This organization is not scheduled to close.",
            code="not_pending",
        )

    organization.status = Organization.Status.ACTIVE
    organization.is_active = True
    organization.closure_effective_at = None
    organization.closed_by = None
    organization.save(
        update_fields=["status", "is_active", "closure_effective_at", "closed_by"]
    )
    record_audit(
        organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.ORGANIZATION_CLOSURE_CANCELED,
        event_data={},
    )
    return organization


@transaction.atomic
def restore_organization(
    organization: Organization,
    *,
    actor: User,
) -> Organization:
    if not actor.is_staff:
        raise LifecycleError(
            "Only CommuniB administrators can restore organizations.",
            code="not_staff",
        )

    if organization.status != Organization.Status.CLOSED:
        if organization.status == Organization.Status.ACTIVE:
            return organization
        # Pending → active
        organization.status = Organization.Status.ACTIVE
        organization.is_active = True
        organization.closure_effective_at = None
        organization.closed_by = None
        organization.restored_at = timezone.now()
        organization.restored_by = actor
        organization.save(
            update_fields=[
                "status",
                "is_active",
                "closure_effective_at",
                "closed_by",
                "restored_at",
                "restored_by",
            ]
        )
    else:
        organization.status = Organization.Status.ACTIVE
        organization.is_active = True
        organization.restored_at = timezone.now()
        organization.restored_by = actor
        organization.closure_effective_at = None
        organization.save(
            update_fields=[
                "status",
                "is_active",
                "restored_at",
                "restored_by",
                "closure_effective_at",
            ]
        )

    record_audit(
        organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.ORGANIZATION_RESTORED,
        event_data={},
    )
    return organization


def serialize_lifecycle(organization: Organization) -> dict:
    ensure_organization_lifecycle(organization)
    return {
        "status": organization.status,
        "is_active": organization.is_active,
        "closed_at": organization.closed_at,
        "closure_effective_at": organization.closure_effective_at,
        "restored_at": organization.restored_at,
        "directory_visible": organization_is_directory_visible(organization),
        "accepts_new_activity": organization_accepts_new_activity(organization),
    }


def default_period_end(*, started_at=None) -> timezone.datetime:
    base = started_at or timezone.now()
    return base + timedelta(days=30)
