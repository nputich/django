import re
import secrets
import string

from django.core.exceptions import ValidationError

from .models import AccessCode, Organization, OrganizationMembership, ResourceType

CODE_PATTERN = re.compile(r"^[A-Z0-9-]{3,32}$")


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
    return Organization.objects.filter(
        memberships__user=user,
        memberships__role=OrganizationMembership.Role.ADMIN,
        is_active=True,
    ).distinct()


def get_admin_organization(user, slug: str) -> Organization:
    return Organization.objects.get(
        slug=slug,
        is_active=True,
        memberships__user=user,
        memberships__role=OrganizationMembership.Role.ADMIN,
    )


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
            raise ValidationError("This access code is already in use by an active survey or meeting.")
        return code
    return generate_access_code(type_slug)


def get_resource_type(slug: str) -> ResourceType:
    try:
        return ResourceType.objects.get(slug=slug, is_active=True)
    except ResourceType.DoesNotExist as exc:
        raise ValidationError(
            f"Resource type '{slug}' is not configured. Run seed_resource_types or add it in admin."
        ) from exc
