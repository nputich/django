import re
import secrets
import string

from django.core.exceptions import ValidationError

from .models import AccessCode, Organization, OrganizationMembership, ResourceType

CODE_PATTERN = re.compile(r"^[A-Z0-9-]{3,32}$")

ADMIN_ROLES = (
    OrganizationMembership.Role.OWNER,
    OrganizationMembership.Role.ADMIN,
)


def normalize_access_code(code: str) -> str:
    return code.strip().upper()


def validate_access_code_format(code: str) -> str:
    normalized = normalize_access_code(code)
    if not CODE_PATTERN.match(normalized):
        raise ValidationError(
            "Access code must be 3–32 characters and use only uppercase letters, numbers, and hyphens."
        )
    return normalized


def user_admin_organizations(user):
    """Orgs the user can manage (owner or admin), including closure_pending."""
    return (
        Organization.objects.filter(
            memberships__user=user,
            memberships__role__in=ADMIN_ROLES,
        )
        .exclude(status=Organization.Status.CLOSED)
        .distinct()
    )


def user_owned_organizations(user):
    return Organization.objects.filter(
        memberships__user=user,
        memberships__role=OrganizationMembership.Role.OWNER,
    ).distinct()


def get_admin_organization(user, slug: str, *, allow_closed: bool = False) -> Organization:
    """
    Owner or admin of an organization.
    Closed orgs are excluded unless allow_closed=True (restore / staff paths).
    """
    qs = Organization.objects.filter(
        slug=slug,
        memberships__user=user,
        memberships__role__in=ADMIN_ROLES,
    )
    if not allow_closed:
        qs = qs.exclude(status=Organization.Status.CLOSED)
    return qs.get()


def get_owner_organization(user, slug: str, *, allow_closed: bool = False) -> Organization:
    qs = Organization.objects.filter(
        slug=slug,
        memberships__user=user,
        memberships__role=OrganizationMembership.Role.OWNER,
    )
    if not allow_closed:
        qs = qs.exclude(status=Organization.Status.CLOSED)
    return qs.get()


def is_resource_code_available(code: str, type_slug: str) -> bool:
    normalized = normalize_access_code(code)
    qs = AccessCode.objects.filter(code__iexact=normalized, is_active=True)
    if type_slug == "survey":
        qs = qs.filter(survey__isnull=False)
    elif type_slug == "meeting":
        qs = qs.filter(meeting__isnull=False)
    else:
        return False
    return not qs.exists()


def generate_access_code(type_slug: str) -> str:
    prefix = "SURVEY" if type_slug == "survey" else "MEET"
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        candidate = f"{prefix}-{suffix}"
        if is_resource_code_available(candidate, type_slug):
            return candidate
    raise ValidationError("Could not generate a unique access code. Try again.")


def resolve_access_code(raw_code: str | None, type_slug: str) -> str:
    if raw_code and raw_code.strip():
        code = validate_access_code_format(raw_code)
        if not is_resource_code_available(code, type_slug):
            raise ValidationError(
                "This access code is already in use by an active survey or meeting."
            )
        return code
    return generate_access_code(type_slug)


def get_resource_type(slug: str) -> ResourceType:
    try:
        return ResourceType.objects.get(slug=slug, is_active=True)
    except ResourceType.DoesNotExist as exc:
        raise ValidationError(
            f"Resource type '{slug}' is not configured. Run seed_resource_types or add it in admin."
        ) from exc
