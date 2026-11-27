"""
PayPal REST helpers for subscription checkout (Stage 5).

Secrets must come from the environment / Secret Manager — never hard-code.
Browser success redirects must not activate CommuniB entitlements.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class PayPalError(Exception):
    def __init__(self, message: str, *, code: str = "paypal_error"):
        super().__init__(message)
        self.code = code


def paypal_mode() -> str:
    return (getattr(settings, "PAYPAL_MODE", "disabled") or "disabled").strip().lower()


def paypal_checkout_enabled() -> bool:
    if not getattr(settings, "PAYPAL_SUBSCRIPTIONS_ENABLED", False):
        return False
    if paypal_mode() not in {"sandbox", "live"}:
        return False
    client_id = (getattr(settings, "PAYPAL_CLIENT_ID", "") or "").strip()
    secret = (getattr(settings, "PAYPAL_CLIENT_SECRET", "") or "").strip()
    return bool(client_id and secret)


def paypal_api_base() -> str:
    if paypal_mode() == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _basic_auth_header(client_id: str, secret: str) -> str:
    import base64

    token = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def get_access_token() -> str:
    if not paypal_checkout_enabled():
        raise PayPalError(
            "PayPal checkout is not configured.",
            code="paypal_not_configured",
        )

    client_id = settings.PAYPAL_CLIENT_ID.strip()
    secret = settings.PAYPAL_CLIENT_SECRET.strip()
    url = f"{paypal_api_base()}/v1/oauth2/token"
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": _basic_auth_header(client_id, secret),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("PayPal OAuth failed status=%s", exc.code)
        raise PayPalError(
            "Could not authenticate with PayPal.",
            code="paypal_auth_failed",
        ) from exc
    except urllib.error.URLError as exc:
        raise PayPalError(
            "Could not reach PayPal.",
            code="paypal_unreachable",
        ) from exc

    token = payload.get("access_token")
    if not token:
        raise PayPalError("PayPal OAuth response missing access_token.", code="paypal_auth_failed")
    return token


def create_subscription(
    *,
    plan_id: str,
    custom_id: str,
    return_url: str,
    cancel_url: str,
    brand_name: str = "CommuniB",
) -> dict:
    """
    Create a PayPal subscription in APPROVAL_PENDING state.

    Returns:
      {
        "paypal_subscription_id": "I-...",
        "approve_url": "https://...",
        "status": "APPROVAL_PENDING",
        "raw": {...},
      }
    """
    access_token = get_access_token()
    url = f"{paypal_api_base()}/v1/billing/subscriptions"
    body = {
        "plan_id": plan_id,
        "custom_id": custom_id[:127],
        "application_context": {
            "brand_name": brand_name[:127],
            "locale": "en-US",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.warning("PayPal create subscription failed status=%s body=%s", exc.code, body_text[:500])
        raise PayPalError(
            "PayPal could not create the subscription.",
            code="paypal_create_failed",
        ) from exc
    except urllib.error.URLError as exc:
        raise PayPalError(
            "Could not reach PayPal.",
            code="paypal_unreachable",
        ) from exc

    subscription_id = payload.get("id") or ""
    approve_url = ""
    for link in payload.get("links") or []:
        if link.get("rel") == "approve":
            approve_url = link.get("href") or ""
            break

    if not subscription_id or not approve_url:
        raise PayPalError(
            "PayPal subscription response missing id or approve link.",
            code="paypal_create_failed",
        )

    return {
        "paypal_subscription_id": subscription_id,
        "approve_url": approve_url,
        "status": payload.get("status") or "",
        "raw": payload,
    }


def cancel_subscription(subscription_id: str, *, reason: str = "Cancelled by organization owner") -> dict:
    """
    Cancel a PayPal subscription (stops future renewals).
    Raises PayPalError without mutating CommuniB state — callers must not mark
    local cancellation successful if this fails.
    """
    sub_id = (subscription_id or "").strip()
    if not sub_id:
        raise PayPalError("Missing PayPal subscription id.", code="paypal_missing_id")

    token = get_access_token()
    url = f"{paypal_api_base()}/v1/billing/subscriptions/{urllib.parse.quote(sub_id)}/cancel"
    body = json.dumps({"reason": reason[:128]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw.strip() else {}
            return payload
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        # 422 often means already cancelled — treat as success for idempotency.
        if exc.code in (404, 422):
            logger.info(
                "PayPal cancel subscription treated as done status=%s body=%s",
                exc.code,
                body_text[:300],
            )
            return {"status": "CANCELLED", "idempotent": True}
        logger.warning(
            "PayPal cancel subscription failed status=%s body=%s",
            exc.code,
            body_text[:500],
        )
        raise PayPalError(
            "PayPal could not cancel the subscription. Please try again.",
            code="paypal_cancel_failed",
        ) from exc
    except urllib.error.URLError as exc:
        raise PayPalError(
            "Could not reach PayPal to cancel the subscription.",
            code="paypal_unreachable",
        ) from exc


def verify_webhook_signature(
    *,
    headers: dict,
    event: dict,
    webhook_id: str | None = None,
) -> bool:
    """
    Verify a PayPal webhook using /v1/notifications/verify-webhook-signature.

    headers should include PAYPAL-TRANSMISSION-* / PAYPAL-AUTH-ALGO / PAYPAL-CERT-URL
    (case-insensitive keys accepted).
    """
    wh_id = (webhook_id or getattr(settings, "PAYPAL_WEBHOOK_ID", "") or "").strip()
    if not wh_id:
        raise PayPalError(
            "PAYPAL_WEBHOOK_ID is not configured.",
            code="paypal_webhook_not_configured",
        )

    def _h(name: str) -> str:
        target = name.lower()
        for key, value in headers.items():
            if str(key).lower() == target:
                return (value or "").strip()
        return ""

    auth_algo = _h("PAYPAL-AUTH-ALGO")
    cert_url = _h("PAYPAL-CERT-URL")
    transmission_id = _h("PAYPAL-TRANSMISSION-ID")
    transmission_sig = _h("PAYPAL-TRANSMISSION-SIG")
    transmission_time = _h("PAYPAL-TRANSMISSION-TIME")
    if not all(
        [auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]
    ):
        raise PayPalError(
            "Missing PayPal webhook transmission headers.",
            code="paypal_webhook_headers_missing",
        )

    token = get_access_token()
    url = f"{paypal_api_base()}/v1/notifications/verify-webhook-signature"
    body = {
        "auth_algo": auth_algo,
        "cert_url": cert_url,
        "transmission_id": transmission_id,
        "transmission_sig": transmission_sig,
        "transmission_time": transmission_time,
        "webhook_id": wh_id,
        "webhook_event": event,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.warning(
            "PayPal verify webhook failed status=%s body=%s",
            exc.code,
            body_text[:500],
        )
        raise PayPalError(
            "PayPal could not verify the webhook signature.",
            code="paypal_webhook_verify_failed",
        ) from exc
    except urllib.error.URLError as exc:
        raise PayPalError(
            "Could not reach PayPal to verify the webhook.",
            code="paypal_unreachable",
        ) from exc

    status_value = (payload.get("verification_status") or "").upper()
    return status_value == "SUCCESS"


def get_subscription(subscription_id: str) -> dict:
    """Fetch subscription details (for billing period sync)."""
    sub_id = (subscription_id or "").strip()
    if not sub_id:
        raise PayPalError("Missing PayPal subscription id.", code="paypal_missing_id")
    token = get_access_token()
    url = f"{paypal_api_base()}/v1/billing/subscriptions/{urllib.parse.quote(sub_id)}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.warning(
            "PayPal get subscription failed status=%s body=%s",
            exc.code,
            body_text[:500],
        )
        raise PayPalError(
            "PayPal could not fetch the subscription.",
            code="paypal_subscription_fetch_failed",
        ) from exc
    except urllib.error.URLError as exc:
        raise PayPalError(
            "Could not reach PayPal.",
            code="paypal_unreachable",
        ) from exc
