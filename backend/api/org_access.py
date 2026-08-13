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
    elif type_slug == "organization":
        qs = qs.filter(
            resource_type__slug="organization",
            survey__isnull=True,
            meeting__isnull=True,
        )
    else:
        return False
    return not qs.exists()


def generate_access_code(type_slug: str) -> str:
    if type_slug == "organization":
        raise ValidationError(
            "Use generate_community_code() for organization community codes."
        )
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


def reserved_community_codes() -> set[str]:
    """Codes that must never be used as public Community Codes (billing, etc.)."""
    from django.conf import settings

    reserved = {"SUPERBASIC"}
    configured = (getattr(settings, "COMMUNIB_BASIC_ACCESS_CODE", "") or "").strip().upper()
    if configured:
        reserved.add(configured)
    return reserved


def is_community_code_available(code: str, *, exclude_organization_id: int | None = None) -> bool:
    normalized = normalize_access_code(code)
    if normalized in reserved_community_codes():
        return False
    qs = AccessCode.objects.filter(
        code__iexact=normalized,
        is_active=True,
        resource_type__slug="organization",
        survey__isnull=True,
        meeting__isnull=True,
    )
    if exclude_organization_id is not None:
        qs = qs.exclude(organization_id=exclude_organization_id)
    return not qs.exists()


def validate_community_code(
    raw_code: str,
    *,
    exclude_organization_id: int | None = None,
) -> str:
    code = validate_access_code_format(raw_code)
    if code in reserved_community_codes():
        raise ValidationError(
            "That code is reserved and cannot be used as a Community Code."
        )
    if not is_community_code_available(
        code, exclude_organization_id=exclude_organization_id
    ):
        raise ValidationError("That Community Code is already in use.")
    return code


def generate_community_code(organization_name: str) -> str:
    """
    Auto Community Code: initials (or name stem) + hyphen + 4 chars.
    Example: Forsyth County Democratic Party → FCDP-A7K2
    """
    words = re.findall(r"[A-Za-z0-9]+", organization_name or "")
    if len(words) >= 2:
        base = "".join(w[0] for w in words[:6]).upper()
    elif words:
        base = re.sub(r"[^A-Z0-9]", "", words[0].upper())[:8]
    else:
        base = "ORG"
    base = (base or "ORG")[:12]
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(40):
        suffix = "".join(secrets.choice(alphabet) for _ in range(4))
        candidate = f"{base}-{suffix}"
        if CODE_PATTERN.match(candidate) and is_community_code_available(candidate):
            return candidate
    raise ValidationError("Could not generate a unique Community Code. Try again.")


def get_primary_community_code(organization: Organization) -> AccessCode | None:
    return (
        AccessCode.objects.filter(
            organization=organization,
            resource_type__slug="organization",
            is_active=True,
            survey__isnull=True,
            meeting__isnull=True,
        )
        .order_by("-is_primary", "sort_order", "id")
        .first()
    )


def assign_community_code(
    organization: Organization,
    *,
    community_code: str | None = None,
) -> AccessCode:
    """Create the primary organization Community Code (AccessCode, type=organization)."""
    resource_type = get_resource_type("organization")
    if community_code and str(community_code).strip():
        code = validate_community_code(str(community_code))
    else:
        code = generate_community_code(organization.name)

    # Demote any existing primary org codes (should be none on create).
    AccessCode.objects.filter(
        organization=organization,
        resource_type=resource_type,
        is_primary=True,
    ).update(is_primary=False)

    return AccessCode.objects.create(
        code=code,
        organization=organization,
        resource_type=resource_type,
        label="Community Code",
        is_primary=True,
        is_active=True,
        sort_order=0,
    )
