"""
Organization billing API.

Stage 5: checkout may create a PayPal subscription (still PENDING locally).
Browser return/confirm never activates entitlements.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .billing_plans import (
    PlanResolutionError,
    list_available_plans,
    public_plan_payload,
    resolve_paypal_checkout_plan,
)
from .billing_service import (
    CheckoutError,
    confirm_paypal_subscription_return,
    get_current_service_summary,
    get_pending_checkout,
    serialize_organization_service,
    start_pending_checkout,
)
from .models import Organization
from .org_access import get_admin_organization
from .paypal_client import (
    PayPalError,
    paypal_checkout_enabled,
    paypal_mode,
    verify_webhook_signature,
)


def _require_admin_org(request, slug):
    try:
        organization = get_admin_organization(request.user, slug)
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )
    from .organization_lifecycle import ensure_organization_lifecycle

    ensure_organization_lifecycle(organization)
    if organization.status == Organization.Status.CLOSED:
        return None, Response(
            {
                "detail": "This organization is closed. New paid subscriptions cannot be started.",
                "code": "organization_closed",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return organization, None


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
                "paypal_mode": paypal_mode(),
                "paypal_sandbox": paypal_mode() == "sandbox",
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

    Called after PayPal browser return. Attaches the subscription id and, when
    PayPal reports ACTIVE/APPROVED, activates the local entitlement (covers
    localhost where webhooks cannot be delivered).
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
            service, activated, paypal_status = confirm_paypal_subscription_return(
                organization=organization,
                subscription_id=subscription_id,
                billing_reference=billing_reference,
            )
        except CheckoutError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        effective = organization.get_current_service_level()
        if activated:
            detail = (
                "Your PayPal subscription is active. CommuniB has updated this "
                "organization's paid service."
            )
        elif paypal_status:
            detail = (
                f"Subscription recorded (PayPal status: {paypal_status}). "
                "Paid service activates when PayPal reports ACTIVE."
            )
        else:
            detail = (
                "Subscription submitted. CommuniB is confirming with PayPal."
            )

        return Response(
            {
                "detail": detail,
                "pending_service": serialize_organization_service(service),
                "service": serialize_organization_service(service),
                "effective_service_level": effective,
                "entitlement_changed": activated,
                "activated": activated,
                "paypal_status": paypal_status or None,
                "paypal_contacted": bool(paypal_status),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class PayPalWebhookView(APIView):
    """
    POST /api/billing/paypal/webhook/

    PayPal server-to-server notifications. Signature verified before apply.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        import json
        import logging

        from .billing_service import handle_paypal_webhook_event

        logger = logging.getLogger(__name__)

        try:
            if isinstance(request.data, dict) and request.data:
                event = request.data
            else:
                event = json.loads(request.body.decode("utf-8") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return Response(
                {"detail": "Invalid JSON body.", "code": "invalid_json"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = {key: value for key, value in request.headers.items()}
        try:
            ok = verify_webhook_signature(headers=headers, event=event)
        except PayPalError as exc:
            logger.warning("PayPal webhook verify error: %s (%s)", exc, exc.code)
            http_status = status.HTTP_400_BAD_REQUEST
            if exc.code == "paypal_webhook_not_configured":
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            elif exc.code == "paypal_unreachable":
                http_status = status.HTTP_502_BAD_GATEWAY
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=http_status,
            )

        if not ok:
            return Response(
                {
                    "detail": "Webhook signature verification failed.",
                    "code": "paypal_webhook_invalid",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = handle_paypal_webhook_event(event)
        # Always 200 after successful verify so PayPal does not retry forever
        # for unknown subscription ids (e.g. tests / other apps).
        return Response({"ok": True, **result}, status=status.HTTP_200_OK)
