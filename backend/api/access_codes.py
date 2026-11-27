"""
Access-code grants for organization service levels (no PayPal).

Temporary: validates COMMUNIB_BASIC_ACCESS_CODE from settings/env.
Structured so a future AccessCode catalog / admin UI can replace the
env-based check without changing OrganizationService or cancel paths.
"""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .billing_plans import SERVICE_LEVEL_BASIC, SERVICE_LEVEL_LABELS
from .billing_service import (
    CheckoutError,
    activate_organization_service,
    create_pending_organization_service,
    get_active_organization_service,
    next_billing_reference,
)
from .models import AccessCodeRedemption, Organization, OrganizationService
from .plan_limits import BASIC_ACCESS_CODE_DURATION_MONTHS, add_calendar_months


class AccessCodeError(CheckoutError):
    """Invalid or unusable access code."""


def normalize_access_code(raw: str | None) -> str:
    return (raw or "").strip().upper()


def basic_access_code_configured() -> bool:
    return bool((getattr(settings, "COMMUNIB_BASIC_ACCESS_CODE", "") or "").strip())


def _configured_basic_access_code() -> str:
    return normalize_access_code(getattr(settings, "COMMUNIB_BASIC_ACCESS_CODE", ""))


def access_code_period_end(*, started_at=None):
    """When complimentary Basic from an access code expires."""
    base = started_at or timezone.now()
    return add_calendar_months(base, BASIC_ACCESS_CODE_DURATION_MONTHS)


def validate_temporary_basic_access_code(code: str) -> str:
    """
    Server-side validation for the temporary Basic code.
    Returns normalized code on success.
    """
    normalized = normalize_access_code(code)
    expected = _configured_basic_access_code()
    if not expected:
        raise AccessCodeError(
            "Access code redemption is not available.",
            code="access_code_disabled",
        )
    if not normalized or normalized != expected:
        raise AccessCodeError(
            "That access code is not valid.",
            code="invalid_access_code",
        )
    return normalized


@transaction.atomic
def redeem_basic_access_code(
    *,
    organization: Organization,
    user,
    code: str,
) -> tuple[OrganizationService, AccessCodeRedemption]:
    """
    Activate BASIC for an organization via access code (no PayPal).

    - billing_source=ACCESS_CODE
    - paypal_subscription_id left empty
    - records AccessCodeRedemption (one redemption per org+code)
    - Basic lasts BASIC_ACCESS_CODE_DURATION_MONTHS, then expires
    """
    normalized = validate_temporary_basic_access_code(code)

    active = get_active_organization_service(organization)
    if active and active.status == OrganizationService.Status.ACTIVE:
        raise AccessCodeError(
            "This organization already has an active paid service. "
            "Cancel it before redeeming an access code.",
            code="active_subscription_exists",
        )

    if AccessCodeRedemption.objects.filter(
        organization=organization,
        code=normalized,
    ).exists():
        raise AccessCodeError(
            "This organization has already redeemed that access code.",
            code="access_code_already_redeemed",
        )

    now = timezone.now()
    # Abandon any pending PayPal checkouts for this org.
    OrganizationService.objects.filter(
        organization=organization,
        status=OrganizationService.Status.PENDING,
        billing_source=OrganizationService.BillingSource.PAYPAL,
    ).update(
        status=OrganizationService.Status.CANCELLED,
        cancelled_at=now,
    )

    service = create_pending_organization_service(
        organization=organization,
        service_level=SERVICE_LEVEL_BASIC,
        billing_source=OrganizationService.BillingSource.ACCESS_CODE,
        paypal_plan_id="",
        billing_reference=next_billing_reference(organization),
        requested_by=user,
    )
    service = activate_organization_service(service)
    service.paypal_subscription_id = ""
    service.cancelled_at = None
    service.current_period_end = access_code_period_end(started_at=service.started_at)
    # Expire automatically when the complimentary window ends (no PayPal renewal).
    service.cancel_at_period_end = True
    service.save(
        update_fields=[
            "paypal_subscription_id",
            "cancel_at_period_end",
            "cancelled_at",
            "current_period_end",
            "updated_at",
        ]
    )

    try:
        redemption = AccessCodeRedemption.objects.create(
            code=normalized,
            organization=organization,
            redeemed_by=user if getattr(user, "is_authenticated", False) else None,
            organization_service=service,
            service_level=SERVICE_LEVEL_BASIC,
            notes=(
                f"Temporary env-based Basic access code "
                f"({BASIC_ACCESS_CODE_DURATION_MONTHS} months)"
            ),
        )
    except IntegrityError as exc:
        raise AccessCodeError(
            "This organization has already redeemed that access code.",
            code="access_code_already_redeemed",
        ) from exc

    return service, redemption


def serialize_access_code_activation(
    service: OrganizationService,
    *,
    redemption: AccessCodeRedemption | None = None,
) -> dict:
    return {
        "service_level": service.service_level,
        "name": SERVICE_LEVEL_LABELS.get(service.service_level, service.service_level),
        "status": service.status,
        "billing_source": service.billing_source,
        "billing_reference": service.billing_reference,
        "paypal_subscription_id": service.paypal_subscription_id or None,
        "started_at": service.started_at,
        "current_period_end": service.current_period_end,
        "cancel_at_period_end": service.cancel_at_period_end,
        "redemption_id": redemption.id if redemption else None,
    }
