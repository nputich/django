"""Create organizations owned by the requesting user (admin membership)."""

from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from .models import Organization, OrganizationMembership


def unique_organization_slug(name: str) -> str:
    base = slugify(name)[:180] or "organization"
    slug = base
    n = 2
    while Organization.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug = f"{base[: 200 - len(suffix)]}{suffix}"
        n += 1
    return slug


@transaction.atomic
def create_organization_for_user(*, user, name: str, description: str = "") -> Organization:
    from .organization_lifecycle import find_closed_name_conflicts

    conflicts = find_closed_name_conflicts(name)
    if conflicts:
        closed = conflicts[0]
        raise ValueError(
            {
                "code": "closed_organization_exists",
                "detail": (
                    "This organization previously existed on CommuniB. "
                    "If you represent this organization, you can request access or restoration."
                ),
                "organization": {
                    "id": closed.id,
                    "name": closed.name,
                    "slug": closed.slug,
                    "status": closed.status,
                },
            }
        )

    org = Organization.objects.create(
        name=name.strip(),
        slug=unique_organization_slug(name),
        description=(description or "").strip(),
        is_active=True,
        status=Organization.Status.ACTIVE,
        is_verified=False,
    )
    OrganizationMembership.objects.create(
        organization=org,
        user=user,
        role=OrganizationMembership.Role.OWNER,
    )
    return org
