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
