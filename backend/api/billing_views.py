"""
Organization billing API.

Stage 5: checkout may create a PayPal subscription (still PENDING locally).
Browser return/confirm never activates entitlements.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing_plans import (
    PlanResolutionError,
    list_available_plans,
    public_plan_payload,
    resolve_paypal_checkout_plan,
)
from .billing_service import (
    CheckoutError,
    attach_paypal_subscription_id,
    get_current_service_summary,
    get_pending_checkout,
    serialize_organization_service,
    start_pending_checkout,
)
from .models import Organization
from .org_access import get_admin_organization
from .paypal_client import paypal_checkout_enabled


def _require_admin_org(request, slug):
    try:
        return get_admin_organization(request.user, slug), None
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )


def _ignored_client_price_fields(data) -> list[str]:
    return sorted(
        key
        for key in ("price", "paypal_plan_id", "paypalPlanId", "plan_id")
        if key in data
    )


def _checkout_mode() -> str:
    return "paypal" if paypal_checkout_enabled() else "simulated"


class OrganizationBillingView(APIView):
    """GET billing summary for an organization the user administers."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization, error = _require_admin_org(request, slug)
        if error:
            return error

        return Response(
            {
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
                "current_service": get_current_service_summary(organization),
                "pending_checkout": serialize_organization_service(
                    get_pending_checkout(organization)
                ),
                "can_manage_billing": True,
                "plans": [public_plan_payload(p) for p in list_available_plans()],
                "checkout_mode": _checkout_mode(),
            }
        )


class OrganizationBillingCheckoutPreviewView(APIView):
    """POST { service_level } — authoritative price/plan; no entitlement change."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, error = _require_admin_org(request, slug)
        if error:
            return error

        ignored = _ignored_client_price_fields(request.data)
        raw_level = request.data.get("service_level", request.data.get("serviceLevel"))
        try:
            resolved = resolve_paypal_checkout_plan(raw_level)
        except PlanResolutionError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
                "checkout": resolved,
                "ignored_client_fields": ignored,
                "entitlement_changed": False,
                "paypal_contacted": False,
                "mode": "preview",
            }
        )


class OrganizationBillingCheckoutStartView(APIView):
    """
    POST { service_level }

    Creates PENDING OrganizationService. If PayPal is enabled, creates a PayPal
    subscription and returns approve_url. Local status remains PENDING.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, error = _require_admin_org(request, slug)
        if error:
            return error

        ignored = _ignored_client_price_fields(request.data)
        raw_level = request.data.get("service_level", request.data.get("serviceLevel"))

        try:
            pending, resolved, paypal_meta = start_pending_checkout(
                organization=organization,
                user=request.user,
                service_level=raw_level,
            )
        except PlanResolutionError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CheckoutError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_409_CONFLICT
                if exc.code == "active_subscription_exists"
                else status.HTTP_400_BAD_REQUEST,
            )

        mode = "paypal_redirect" if paypal_meta.get("approve_url") else "pending_checkout"
        message = (
            "PayPal subscription created. Complete approval on PayPal. "
            "CommuniB will activate service after confirmation."
            if paypal_meta.get("contacted")
            else (
                "Checkout recorded as PENDING. PayPal is not configured in this "
                "environment, so no payment was started. Service is not active."
            )
        )

        return Response(
            {
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
                "checkout": resolved,
                "pending_service": serialize_organization_service(pending),
                "approve_url": paypal_meta.get("approve_url"),
                "ignored_client_fields": ignored,
                "entitlement_changed": False,
                "effective_service_level": organization.get_current_service_level(),
                "paypal_contacted": bool(paypal_meta.get("contacted")),
                "paypal_enabled": bool(paypal_meta.get("enabled")),
                "mode": mode,
                "message": message,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationBillingPayPalConfirmView(APIView):
    """
    POST { subscription_id }

    Called after PayPal browser return. Stores/verifies subscription id.
    Never activates service — webhooks do that later.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, error = _require_admin_org(request, slug)
        if error:
            return error

        subscription_id = (
            request.data.get("subscription_id")
            or request.data.get("subscriptionId")
            or ""
        )
        billing_reference = request.data.get("billing_reference") or request.data.get(
            "billingReference"
        )

        try:
            pending = attach_paypal_subscription_id(
                organization=organization,
                subscription_id=subscription_id,
                billing_reference=billing_reference,
            )
        except CheckoutError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": (
                    "Subscription submitted. Your PayPal subscription has been "
                    "received. CommuniB is confirming your subscription. Your "
                    "service will become active after confirmation."
                ),
                "pending_service": serialize_organization_service(pending),
                "effective_service_level": organization.get_current_service_level(),
                "entitlement_changed": False,
                "activated": False,
                "paypal_contacted": False,
            }
        )
