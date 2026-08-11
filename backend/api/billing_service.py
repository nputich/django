"""
Organization service entitlements and service-level resolution.

PayPal is not required here. FREE is the default when no ACTIVE paid
OrganizationService exists.
"""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .billing_plans import (
    DEFAULT_SERVICE_LEVEL,
    SERVICE_LEVEL_FREE,
    SERVICE_LEVEL_LABELS,
    PlanResolutionError,
    resolve_paypal_checkout_plan,
)
from .models import Organization, OrganizationService
from .paypal_client import (
    PayPalError,
    create_subscription,
    get_subscription,
    paypal_checkout_enabled,
)


class CheckoutError(Exception):
    def __init__(self, message: str, *, code: str = "checkout_error"):
        super().__init__(message)
        self.code = code


def billing_simulation_allowed() -> bool:
    """Dev/test-only simulated activation (never unrestricted in production)."""
    if getattr(settings, "BILLING_SIMULATION_ENABLED", False):
        return True
    if getattr(settings, "DEBUG", False):
        return True
    app_env = getattr(settings, "APP_ENV", "local") or "local"
    return app_env.lower() in {"local", "test", "development", "dev"}


def get_active_organization_service(organization: Organization):
    """
    Return the current ACTIVE entitlement that grants paid/enterprise access,
    or None (caller should treat as FREE).

    Entitlements with cancel_at_period_end past current_period_end are expired first.
    """
    now = timezone.now()
    due = (
        OrganizationService.objects.filter(
            organization=organization,
            status=OrganizationService.Status.ACTIVE,
            cancel_at_period_end=True,
            current_period_end__lte=now,
        )
        .exclude(service_level=OrganizationService.ServiceLevel.FREE)
    )
    for service in due:
        service.status = OrganizationService.Status.CANCELLED
        if service.cancelled_at is None:
            service.cancelled_at = now
        service.save(update_fields=["status", "cancelled_at", "updated_at"])

    return (
        OrganizationService.objects.filter(
            organization=organization,
            status=OrganizationService.Status.ACTIVE,
        )
        .exclude(service_level=OrganizationService.ServiceLevel.FREE)
        .order_by("-started_at", "-id")
        .first()
    )


def get_pending_checkout(organization: Organization):
    """Latest PENDING PayPal checkout for the organization, if any."""
    return (
        OrganizationService.objects.filter(
            organization=organization,
            status=OrganizationService.Status.PENDING,
            billing_source=OrganizationService.BillingSource.PAYPAL,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def get_current_service_level(organization: Organization) -> str:
    """Authoritative effective service level for feature authorization."""
    active = get_active_organization_service(organization)
    if active:
        return active.service_level
    return DEFAULT_SERVICE_LEVEL


def serialize_organization_service(service: OrganizationService | None) -> dict | None:
    if not service:
        return None
    return {
        "id": service.id,
        "service_level": service.service_level,
        "name": SERVICE_LEVEL_LABELS.get(service.service_level, service.service_level),
        "status": service.status,
        "billing_source": service.billing_source,
        "billing_reference": service.billing_reference,
        "paypal_plan_id": service.paypal_plan_id or None,
        "paypal_subscription_id": service.paypal_subscription_id or None,
        "requested_by_id": service.requested_by_id,
        "started_at": service.started_at,
        "current_period_end": service.current_period_end,
        "cancelled_at": service.cancelled_at,
        "cancel_at_period_end": service.cancel_at_period_end,
        "created_at": service.created_at,
    }


def get_current_service_summary(organization: Organization) -> dict:
    """Payload for Billing & Service UI."""
    active = get_active_organization_service(organization)
    if not active:
        return {
            "service_level": DEFAULT_SERVICE_LEVEL,
            "name": SERVICE_LEVEL_LABELS.get(DEFAULT_SERVICE_LEVEL, "Organization"),
            "status": None,
            "billing_source": None,
            "billing_reference": None,
            "organization_service_id": None,
        }
    payload = serialize_organization_service(active)
    payload["organization_service_id"] = active.id
    return payload


def next_billing_reference(organization: Organization) -> str:
    """Opaque reference: COMMUNIB-SUB-{org_id:06d}-{seq:05d}."""
    seq = organization.services.count() + 1
    return f"COMMUNIB-SUB-{organization.id:06d}-{seq:05d}"


@transaction.atomic
def create_pending_organization_service(
    *,
    organization: Organization,
    service_level: str,
    billing_source: str = OrganizationService.BillingSource.PAYPAL,
    paypal_plan_id: str = "",
    billing_reference: str | None = None,
    requested_by=None,
) -> OrganizationService:
    """
    Create a PENDING entitlement.
    Does not activate service. Prefer start_pending_checkout() for PayPal flows.
    """
    if service_level == SERVICE_LEVEL_FREE:
        raise ValueError("Do not create PENDING records for FREE; FREE is the default.")

    plan_id = paypal_plan_id
    if not plan_id:
        try:
            resolved = resolve_paypal_checkout_plan(service_level)
            plan_id = resolved["paypal_plan_id"]
        except PlanResolutionError:
            plan_id = ""

    return OrganizationService.objects.create(
        organization=organization,
        requested_by=requested_by,
        service_level=service_level,
        billing_source=billing_source,
        status=OrganizationService.Status.PENDING,
        paypal_plan_id=plan_id,
        billing_reference=billing_reference or next_billing_reference(organization),
    )


@transaction.atomic
def start_pending_checkout(
    *,
    organization: Organization,
    user,
    service_level: str,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> tuple[OrganizationService, dict, dict]:
    """
    Authorize + resolve official plan + create PENDING OrganizationService.

    When PayPal checkout is enabled, also creates a PayPal subscription and
    stores the PayPal subscription ID while keeping local status PENDING.

    Returns (pending, resolved_plan, paypal_meta)
    paypal_meta keys: enabled, contacted, approve_url, paypal_subscription_id
    """
    resolved = resolve_paypal_checkout_plan(service_level)

    active = get_active_organization_service(organization)
    if (
        active
        and active.billing_source == OrganizationService.BillingSource.PAYPAL
        and active.status == OrganizationService.Status.ACTIVE
    ):
        raise CheckoutError(
            "This organization already has an active PayPal subscription. "
            "Use plan change flow instead of starting a new checkout.",
            code="active_subscription_exists",
        )

    now = timezone.now()
    OrganizationService.objects.filter(
        organization=organization,
        status=OrganizationService.Status.PENDING,
        billing_source=OrganizationService.BillingSource.PAYPAL,
    ).update(
        status=OrganizationService.Status.CANCELLED,
        cancelled_at=now,
    )

    pending = create_pending_organization_service(
        organization=organization,
        service_level=resolved["service_level"],
        billing_source=OrganizationService.BillingSource.PAYPAL,
        paypal_plan_id=resolved["paypal_plan_id"],
        requested_by=user,
    )

    paypal_meta = {
        "enabled": paypal_checkout_enabled(),
        "contacted": False,
        "approve_url": None,
        "paypal_subscription_id": None,
    }

    if not paypal_meta["enabled"]:
        return pending, resolved, paypal_meta

    frontend = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:10001").rstrip("/")
    ret = return_url or (
        f"{frontend}/dashboard/{organization.slug}/billing"
        f"?paypal=success&org={organization.slug}"
    )
    can = cancel_url or (
        f"{frontend}/dashboard/{organization.slug}/billing"
        f"?paypal=cancelled&org={organization.slug}"
    )

    try:
        created = create_subscription(
            plan_id=resolved["paypal_plan_id"],
            custom_id=pending.billing_reference,
            return_url=ret,
            cancel_url=can,
        )
    except PayPalError as exc:
        # Keep the pending row for audit, but surface failure to the client.
        raise CheckoutError(str(exc), code=exc.code) from exc

    pending.paypal_subscription_id = created["paypal_subscription_id"]
    pending.save(update_fields=["paypal_subscription_id", "updated_at"])

    paypal_meta.update(
        {
            "contacted": True,
            "approve_url": created["approve_url"],
            "paypal_subscription_id": created["paypal_subscription_id"],
        }
    )
    return pending, resolved, paypal_meta


@transaction.atomic
def attach_paypal_subscription_id(
    *,
    organization: Organization,
    subscription_id: str,
    billing_reference: str | None = None,
) -> OrganizationService:
    """
    Record a PayPal subscription ID on a PENDING checkout.

    Does NOT activate the entitlement by itself. Prefer
    confirm_paypal_subscription_return() which verifies status with PayPal.
    """
    subscription_id = (subscription_id or "").strip()
    if not subscription_id:
        raise CheckoutError("subscription_id is required.", code="missing_subscription_id")

    pending = None
    if billing_reference:
        pending = OrganizationService.objects.filter(
            organization=organization,
            billing_reference=billing_reference,
        ).first()
    if pending is None:
        pending = OrganizationService.objects.filter(
            organization=organization,
            paypal_subscription_id=subscription_id,
        ).first()
    if pending is None:
        pending = get_pending_checkout(organization)

    if pending is None:
        raise CheckoutError(
            "No pending checkout found for this organization.",
            code="pending_not_found",
        )

    if pending.organization_id != organization.id:
        raise CheckoutError(
            "Subscription does not belong to this organization.",
            code="organization_mismatch",
        )

    if not pending.paypal_subscription_id:
        pending.paypal_subscription_id = subscription_id
        pending.save(update_fields=["paypal_subscription_id", "updated_at"])
    elif pending.paypal_subscription_id != subscription_id:
        raise CheckoutError(
            "PayPal subscription ID does not match the pending checkout.",
            code="subscription_mismatch",
        )

    return pending


def confirm_paypal_subscription_return(
    *,
    organization: Organization,
    subscription_id: str,
    billing_reference: str | None = None,
) -> tuple[OrganizationService, bool, str]:
    """
    Browser return handler: attach subscription id, then verify with PayPal.

    Activates locally when PayPal reports ACTIVE (or APPROVED). Needed for local
    Docker where PayPal webhooks cannot reach localhost; also covers webhook delay
    in production.

    Returns (service, activated, paypal_status).
    """
    from .organization_lifecycle import default_period_end

    service = attach_paypal_subscription_id(
        organization=organization,
        subscription_id=subscription_id,
        billing_reference=billing_reference,
    )

    if service.status == OrganizationService.Status.ACTIVE:
        return service, False, "ACTIVE"

    paypal_status = ""
    period_end = None
    if paypal_checkout_enabled():
        try:
            remote = get_subscription(subscription_id)
            paypal_status = (remote.get("status") or "").strip().upper()
            billing_info = remote.get("billing_info") or {}
            period_end = _parse_paypal_datetime(billing_info.get("next_billing_time"))
        except PayPalError as exc:
            raise CheckoutError(str(exc), code=exc.code) from exc
    else:
        return service, False, paypal_status

    if paypal_status in {"ACTIVE", "APPROVED"}:
        service = activate_organization_service(
            service, paypal_subscription_id=subscription_id
        )
        service.cancel_at_period_end = False
        service.cancelled_at = None
        if period_end:
            service.current_period_end = period_end
        elif not service.current_period_end:
            service.current_period_end = default_period_end(started_at=service.started_at)
        service.save(
            update_fields=[
                "cancel_at_period_end",
                "cancelled_at",
                "current_period_end",
                "updated_at",
            ]
        )
        return service, True, paypal_status

    return service, False, paypal_status


@transaction.atomic
def activate_organization_service(
    service: OrganizationService,
    *,
    paypal_subscription_id: str | None = None,
) -> OrganizationService:
    """
    Mark an entitlement ACTIVE.

    Used by verified PayPal webhooks later, and by Stage 2 tests / guarded simulation.
    Does not delete the organization or other historical entitlements.
    """
    if service.status == OrganizationService.Status.ACTIVE:
        return service

    now = timezone.now()
    service.status = OrganizationService.Status.ACTIVE
    if service.started_at is None:
        service.started_at = now
    if paypal_subscription_id:
        service.paypal_subscription_id = paypal_subscription_id
    service.cancelled_at = None
    service.save(
        update_fields=[
            "status",
            "started_at",
            "paypal_subscription_id",
            "cancelled_at",
            "updated_at",
        ]
    )
    return service


@transaction.atomic
def cancel_organization_service(
    service: OrganizationService,
) -> OrganizationService:
    """
    Immediately mark entitlement CANCELLED.
    Prefer request_cancel_paid_service for owner-facing cancel-at-period-end.
    """
    now = timezone.now()
    service.status = OrganizationService.Status.CANCELLED
    service.cancelled_at = now
    service.cancel_at_period_end = False
    service.save(
        update_fields=["status", "cancelled_at", "cancel_at_period_end", "updated_at"]
    )
    return service


@transaction.atomic
def request_cancel_paid_service(
    service: OrganizationService,
    *,
    actor=None,
) -> OrganizationService:
    """
    Cancel future renewal; keep ACTIVE paid access until current_period_end.

    Does NOT close or delete the organization.
    If PayPal cancel fails, local state is not updated.
    """
    from .organization_lifecycle import default_period_end, record_audit
    from .models import OrganizationAuditEvent
    from .paypal_client import PayPalError, cancel_subscription, paypal_checkout_enabled

    if service.status != OrganizationService.Status.ACTIVE:
        if service.cancel_at_period_end:
            return service  # idempotent
        raise CheckoutError(
            "There is no active paid service to cancel.",
            code="no_active_service",
        )

    if service.cancel_at_period_end:
        return service  # idempotent

    record_audit(
        service.organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.SUBSCRIPTION_CANCEL_REQUESTED,
        event_data={"organization_service_id": service.id},
    )

    if (
        service.billing_source == OrganizationService.BillingSource.PAYPAL
        and service.paypal_subscription_id
        and paypal_checkout_enabled()
    ):
        try:
            cancel_subscription(service.paypal_subscription_id)
        except PayPalError:
            raise

    now = timezone.now()
    if not service.current_period_end or service.current_period_end < now:
        service.current_period_end = default_period_end(started_at=service.started_at)

    service.cancel_at_period_end = True
    service.cancelled_at = now
    # Remain ACTIVE until period end so paid features continue.
    service.save(
        update_fields=[
            "cancel_at_period_end",
            "cancelled_at",
            "current_period_end",
            "updated_at",
        ]
    )

    record_audit(
        service.organization,
        actor=actor,
        event_type=OrganizationAuditEvent.EventType.SUBSCRIPTION_CANCELED,
        event_data={
            "organization_service_id": service.id,
            "cancel_at_period_end": True,
            "current_period_end": service.current_period_end.isoformat()
            if service.current_period_end
            else None,
        },
    )
    return service


def _parse_paypal_datetime(value: str | None):
    if not value:
        return None
    from django.utils.dateparse import parse_datetime

    parsed = parse_datetime(value.replace("Z", "+00:00"))
    if parsed and timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.utc)
    return parsed


def _period_end_from_subscription_resource(resource: dict):
    billing_info = resource.get("billing_info") or {}
    return _parse_paypal_datetime(billing_info.get("next_billing_time"))


def find_organization_service_for_paypal_event(resource: dict) -> OrganizationService | None:
    """Locate local entitlement by PayPal subscription id or custom_id (billing_reference)."""
    subscription_id = (resource.get("id") or "").strip()
    custom_id = (resource.get("custom_id") or "").strip()

    if subscription_id:
        match = (
            OrganizationService.objects.filter(paypal_subscription_id=subscription_id)
            .order_by("-id")
            .first()
        )
        if match:
            return match
    if custom_id:
        match = (
            OrganizationService.objects.filter(billing_reference=custom_id)
            .order_by("-id")
            .first()
        )
        if match:
            return match
    return None


def _record_paypal_webhook_audit(
    service: OrganizationService,
    *,
    event_type: str,
    event_id: str,
    action: str,
    extra: dict | None = None,
) -> None:
    from .organization_lifecycle import record_audit
    from .models import OrganizationAuditEvent

    data = {
        "paypal_event_id": event_id,
        "paypal_event_type": event_type,
        "action": action,
        "organization_service_id": service.id,
        "paypal_subscription_id": service.paypal_subscription_id or None,
    }
    if extra:
        data.update(extra)
    record_audit(
        service.organization,
        actor=None,
        event_type=OrganizationAuditEvent.EventType.PAYPAL_WEBHOOK,
        event_data=data,
    )


@transaction.atomic
def handle_paypal_webhook_event(event: dict) -> dict:
    """
    Apply a verified PayPal webhook event to CommuniB entitlements.

    Returns a small result dict for logging / HTTP responses.
    """
    import logging

    from .organization_lifecycle import default_period_end
    from .models import OrganizationAuditEvent

    logger = logging.getLogger(__name__)
    event_type = (event.get("event_type") or "").strip().upper()
    event_id = (event.get("id") or "").strip()
    resource = event.get("resource") or {}
    subscription_id = (resource.get("id") or "").strip()

    service = find_organization_service_for_paypal_event(resource)
    if service is None:
        logger.warning(
            "PayPal webhook with no matching OrganizationService event=%s sub=%s custom=%s",
            event_type,
            subscription_id,
            resource.get("custom_id"),
        )
        return {
            "handled": False,
            "reason": "service_not_found",
            "event_type": event_type,
            "paypal_event_id": event_id,
        }

    # Idempotent skip if we already recorded this exact PayPal event id.
    if event_id and OrganizationAuditEvent.objects.filter(
        organization=service.organization,
        event_data__paypal_event_id=event_id,
    ).exists():
        return {
            "handled": True,
            "reason": "already_processed",
            "event_type": event_type,
            "organization_service_id": service.id,
            "paypal_event_id": event_id,
        }

    period_end = _period_end_from_subscription_resource(resource)
    action = "ignored"
    now = timezone.now()

    if event_type in {
        "BILLING.SUBSCRIPTION.ACTIVATED",
        "BILLING.SUBSCRIPTION.RE-ACTIVATED",
    }:
        service = activate_organization_service(
            service, paypal_subscription_id=subscription_id or None
        )
        service.cancel_at_period_end = False
        service.cancelled_at = None
        if period_end:
            service.current_period_end = period_end
        elif not service.current_period_end:
            service.current_period_end = default_period_end(started_at=service.started_at)
        service.save(
            update_fields=[
                "cancel_at_period_end",
                "cancelled_at",
                "current_period_end",
                "updated_at",
            ]
        )
        action = "activated"

    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        # Owner cancel keeps paid access until period end; PayPal confirms cancel here.
        if not service.current_period_end or service.current_period_end < now:
            service.current_period_end = period_end or default_period_end(
                started_at=service.started_at
            )
        service.cancel_at_period_end = True
        if not service.cancelled_at:
            service.cancelled_at = now
        if subscription_id and not service.paypal_subscription_id:
            service.paypal_subscription_id = subscription_id
        # Remain ACTIVE while period is still open.
        if (
            service.status == OrganizationService.Status.ACTIVE
            and service.current_period_end
            and service.current_period_end > now
        ):
            service.save(
                update_fields=[
                    "cancel_at_period_end",
                    "cancelled_at",
                    "current_period_end",
                    "paypal_subscription_id",
                    "updated_at",
                ]
            )
            action = "cancel_at_period_end"
        else:
            service = cancel_organization_service(service)
            action = "cancelled"

    elif event_type == "BILLING.SUBSCRIPTION.EXPIRED":
        service.status = OrganizationService.Status.EXPIRED
        service.cancel_at_period_end = False
        if not service.cancelled_at:
            service.cancelled_at = now
        service.save(
            update_fields=[
                "status",
                "cancel_at_period_end",
                "cancelled_at",
                "updated_at",
            ]
        )
        action = "expired"

    elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
        service = cancel_organization_service(service)
        action = "suspended"

    elif event_type in {
        "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
        "PAYMENT.SALE.DENIED",
    }:
        # Keep ACTIVE for now; surface via audit. Hard cancel only on SUSPENDED/EXPIRED.
        action = "payment_failed"

    elif event_type == "BILLING.SUBSCRIPTION.UPDATED":
        if period_end:
            service.current_period_end = period_end
            service.save(update_fields=["current_period_end", "updated_at"])
            action = "period_synced"
        if subscription_id and not service.paypal_subscription_id:
            service.paypal_subscription_id = subscription_id
            service.save(update_fields=["paypal_subscription_id", "updated_at"])
            action = "subscription_id_attached"

    elif event_type == "BILLING.SUBSCRIPTION.CREATED":
        if subscription_id and not service.paypal_subscription_id:
            service.paypal_subscription_id = subscription_id
            service.save(update_fields=["paypal_subscription_id", "updated_at"])
            action = "subscription_id_attached"

    _record_paypal_webhook_audit(
        service,
        event_type=event_type,
        event_id=event_id,
        action=action,
        extra={
            "status": service.status,
            "cancel_at_period_end": service.cancel_at_period_end,
            "current_period_end": service.current_period_end.isoformat()
            if service.current_period_end
            else None,
        },
    )

    return {
        "handled": True,
        "reason": action,
        "event_type": event_type,
        "organization_service_id": service.id,
        "paypal_event_id": event_id,
        "status": service.status,
    }


def simulate_activate_pending_service(
    service: OrganizationService,
    *,
    paypal_subscription_id: str = "I-SIMULATED",
) -> OrganizationService:
    """
    Development/test helper: PENDING → ACTIVE without PayPal.

    Raises PermissionError when simulation is not allowed (production default).
    """
    if not billing_simulation_allowed():
        raise PermissionError(
            "Billing simulation is disabled. Set BILLING_SIMULATION_ENABLED=true "
            "only in non-production environments."
        )
    if service.status != OrganizationService.Status.PENDING:
        raise ValueError(
            f"Can only simulate activation from PENDING (got {service.status})."
        )
    return activate_organization_service(
        service,
        paypal_subscription_id=paypal_subscription_id,
    )
