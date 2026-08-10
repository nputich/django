"""
Authoritative CommuniB service plan catalog (server-side).

The browser may submit a service_level only. It must never dictate price or
PayPal plan IDs — resolve those here.
"""

from __future__ import annotations


class PlanResolutionError(ValueError):
    """Invalid or non-checkoutable service level."""

    def __init__(self, message: str, *, code: str = "invalid_service_level"):
        super().__init__(message)
        self.code = code


SERVICE_LEVEL_FREE = "FREE"
SERVICE_LEVEL_BASIC = "BASIC"
SERVICE_LEVEL_COMMUNITY = "COMMUNITY"
SERVICE_LEVEL_COMMUNITY_PLUS = "COMMUNITY_PLUS"
SERVICE_LEVEL_ENTERPRISE = "ENTERPRISE"

# Effective entitlement when no ACTIVE paid OrganizationService exists.
DEFAULT_SERVICE_LEVEL = SERVICE_LEVEL_FREE

SERVICE_LEVEL_LABELS = {
    SERVICE_LEVEL_FREE: "Organization",
    SERVICE_LEVEL_BASIC: "Basic",
    SERVICE_LEVEL_COMMUNITY: "Community",
    SERVICE_LEVEL_COMMUNITY_PLUS: "Community Plus",
    SERVICE_LEVEL_ENTERPRISE: "Enterprise",
}

ALL_SERVICE_LEVELS = frozenset(SERVICE_LEVEL_LABELS.keys())

# Paid self-serve PayPal plans (Enterprise is contact-only; Free is default entitlement).
COMMUNIB_PAYPAL_PLANS = {
    SERVICE_LEVEL_BASIC: {
        "plan_id": "P-8VM62345PE9955234NJ4SHHA",
        "price": "49.99",
        "name": "CommuniB Basic",
    },
    SERVICE_LEVEL_COMMUNITY: {
        "plan_id": "P-6DH4658999088414HNJ4SI2Q",
        "price": "125.00",
        "name": "CommuniB Community",
    },
    SERVICE_LEVEL_COMMUNITY_PLUS: {
        "plan_id": "P-0HL011378K8966320NJ4SJWI",
        "price": "300.00",
        "name": "CommuniB Community Plus",
    },
}

# Display + checkout metadata for the Billing & Service UI.
COMMUNIB_SERVICE_PLANS = {
    SERVICE_LEVEL_BASIC: {
        "service_level": SERVICE_LEVEL_BASIC,
        "name": "Basic",
        "price": COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_BASIC]["price"],
        "price_display": "$49.99/month",
        "description": (
            "Dashboard tools and community engagement features for smaller organizations."
        ),
        "paypal_plan_id": COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_BASIC]["plan_id"],
        "checkout_mode": "paypal",
        "button_label": "Choose Basic",
    },
    SERVICE_LEVEL_COMMUNITY: {
        "service_level": SERVICE_LEVEL_COMMUNITY,
        "name": "Community",
        "price": COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["price"],
        "price_display": "$125/month",
        "description": (
            "Higher meeting, survey, participation, and reporting capacity for "
            "active local organizations."
        ),
        "paypal_plan_id": COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        "checkout_mode": "paypal",
        "button_label": "Choose Community",
    },
    SERVICE_LEVEL_COMMUNITY_PLUS: {
        "service_level": SERVICE_LEVEL_COMMUNITY_PLUS,
        "name": "Community Plus",
        "price": COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY_PLUS]["price"],
        "price_display": "$300/month",
        "description": (
            "High-capacity engagement tools for elected offices, regional "
            "organizations, and larger communities."
        ),
        "paypal_plan_id": COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY_PLUS]["plan_id"],
        "checkout_mode": "paypal",
        "button_label": "Choose Community Plus",
    },
    SERVICE_LEVEL_ENTERPRISE: {
        "service_level": SERVICE_LEVEL_ENTERPRISE,
        "name": "Enterprise",
        "price": None,
        "price_display": "Custom",
        "description": (
            "Custom limits, contracts, and support for counties, cities, "
            "statewide organizations, and large institutions."
        ),
        "paypal_plan_id": None,
        "checkout_mode": "contact",
        "button_label": "Contact Us",
    },
}

PAID_CHECKOUT_LEVELS = frozenset(COMMUNIB_PAYPAL_PLANS.keys())


def list_available_plans():
    """Plans shown on the Billing & Service page (paid + Enterprise)."""
    order = (
        SERVICE_LEVEL_BASIC,
        SERVICE_LEVEL_COMMUNITY,
        SERVICE_LEVEL_COMMUNITY_PLUS,
        SERVICE_LEVEL_ENTERPRISE,
    )
    return [COMMUNIB_SERVICE_PLANS[key] for key in order]


def get_plan(service_level: str):
    return COMMUNIB_SERVICE_PLANS.get(service_level)


def public_plan_payload(plan: dict) -> dict:
    """
    Catalog payload for the billing UI.

    Intentionally omits paypal_plan_id so the browser cannot treat a listed ID
    as something it may submit back to override checkout.
    """
    return {
        "service_level": plan["service_level"],
        "name": plan["name"],
        "price": plan["price"],
        "price_display": plan["price_display"],
        "description": plan["description"],
        "checkout_mode": plan["checkout_mode"],
        "button_label": plan["button_label"],
    }


def normalize_service_level(raw) -> str:
    if raw is None:
        raise PlanResolutionError("service_level is required.", code="missing_service_level")
    value = str(raw).strip().upper()
    if not value:
        raise PlanResolutionError("service_level is required.", code="missing_service_level")
    return value


def resolve_paypal_checkout_plan(service_level) -> dict:
    """
    Map a CommuniB service_level to the official PayPal plan + price.

    Rejects FREE, ENTERPRISE, and unknown levels. Never uses client-supplied
    price or plan_id arguments.
    """
    level = normalize_service_level(service_level)

    if level == SERVICE_LEVEL_FREE:
        raise PlanResolutionError(
            "Free Organization does not use PayPal checkout.",
            code="free_not_checkoutable",
        )

    if level == SERVICE_LEVEL_ENTERPRISE:
        raise PlanResolutionError(
            "Enterprise uses Contact Us, not self-serve PayPal checkout.",
            code="enterprise_contact_only",
        )

    paypal = COMMUNIB_PAYPAL_PLANS.get(level)
    display = COMMUNIB_SERVICE_PLANS.get(level)
    if not paypal or not display:
        raise PlanResolutionError(
            f"Unknown service level: {level}.",
            code="invalid_service_level",
        )

    return {
        "service_level": level,
        "name": display["name"],
        "display_name": paypal["name"],
        "price": paypal["price"],
        "price_display": display["price_display"],
        "paypal_plan_id": paypal["plan_id"],
        "checkout_mode": "paypal",
        "currency": "USD",
    }
