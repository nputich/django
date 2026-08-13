"""Create organizations owned by the requesting user (owner membership)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .directory_placement import PlacementError, apply_directory_placement
from .models import Organization, OrganizationMembership
from .org_access import assign_community_code


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
def create_organization_for_user(
    *,
    user,
    name: str,
    description: str = "",
    community_code: str | None = None,
    geographic_scope: str | None = None,
    country_id=None,
    state_id=None,
    county_id=None,
    primary_subcategory_id=None,
) -> Organization:
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

    try:
        assign_community_code(org, community_code=community_code)
    except ValidationError as exc:
        raise ValueError(
            {
                "code": "invalid_community_code",
                "detail": "; ".join(exc.messages)
                if hasattr(exc, "messages")
                else str(exc),
            }
        ) from exc

    # Directory placement is required so the org can appear in Explore Communities.
    if not geographic_scope or primary_subcategory_id in (None, ""):
        raise ValueError(
            {
                "code": "directory_placement_required",
                "detail": (
                    "Choose where this organization should appear in Explore "
                    "Communities (location and category)."
                ),
            }
        )

    try:
        apply_directory_placement(
            org,
            geographic_scope=geographic_scope,
            primary_subcategory_id=primary_subcategory_id,
            country_id=country_id,
            state_id=state_id,
            county_id=county_id,
        )
    except PlacementError as exc:
        messages = getattr(exc, "messages", None) or [str(exc)]
        raise ValueError(
            {
                "code": "invalid_directory_placement",
                "detail": "; ".join(str(m) for m in messages),
            }
        ) from exc

    return org
