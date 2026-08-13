"""
Directory placement for Explore Communities (geo scope + category).

Uses existing Organization.geographic_scope, service_area, and
primary_subcategory — does not introduce parallel placement models.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from .directory_service import (
    SCOPE_META,
    serialize_area,
    serialize_category,
    service_area_for_scope,
)
from .models import GeographicArea, Organization, OrgCategory


class PlacementError(ValidationError):
    """Invalid directory placement payload."""


PLACEMENT_SCOPES = (
    Organization.GeographicScope.INTERNATIONAL,
    Organization.GeographicScope.NATIONAL,
    Organization.GeographicScope.STATE_PROVINCE,
    Organization.GeographicScope.LOCAL,
)


def area_ancestry(area: GeographicArea | None) -> list[GeographicArea]:
    chain: list[GeographicArea] = []
    current = area
    while current is not None:
        chain.append(current)
        current = current.parent
    return list(reversed(chain))


def _load_area(area_id, *, expected_type: str | None = None, label: str = "Area"):
    if area_id in (None, ""):
        return None
    try:
        area_id = int(area_id)
    except (TypeError, ValueError) as exc:
        raise PlacementError(f"Invalid {label.lower()} id.") from exc
    area = GeographicArea.objects.filter(pk=area_id, is_active=True).first()
    if not area:
        raise PlacementError(f"{label} not found.")
    if expected_type and area.area_type != expected_type:
        raise PlacementError(f"{label} has the wrong geographic type.")
    return area


def resolve_placement_areas(
    *,
    geographic_scope: str,
    country_id=None,
    state_id=None,
    county_id=None,
) -> dict:
    scope = (geographic_scope or "").strip()
    if scope not in PLACEMENT_SCOPES:
        raise PlacementError(
            "geographic_scope must be international, national, state_province, or local."
        )

    country = _load_area(
        country_id, expected_type=GeographicArea.AreaType.COUNTRY, label="Country"
    )
    state = _load_area(
        state_id, expected_type=GeographicArea.AreaType.ADMIN1, label="State"
    )
    county = _load_area(
        county_id, expected_type=GeographicArea.AreaType.ADMIN2, label="County"
    )

    if state and country and state.parent_id != country.id:
        raise PlacementError("State does not belong to the selected country.")
    if county and state and county.parent_id != state.id:
        raise PlacementError("County does not belong to the selected state.")
    if county and country and not state:
        # Infer state from county parent when only county+country provided.
        if county.parent and county.parent.parent_id == country.id:
            state = county.parent
        else:
            raise PlacementError("County does not belong to the selected country.")

    steps = SCOPE_META[scope]["geo_steps"]
    if "country" in steps and not country:
        raise PlacementError("Country is required for this geographic scope.")
    if "state" in steps and not state:
        raise PlacementError("State is required for this geographic scope.")
    if "county" in steps and not county:
        raise PlacementError("County is required for this geographic scope.")

    service_area = service_area_for_scope(
        scope, country=country, state=state, county=county
    )
    return {
        "geographic_scope": scope,
        "country": country,
        "state": state,
        "county": county,
        "service_area": service_area,
    }


def resolve_subcategory(subcategory_id) -> OrgCategory:
    if subcategory_id in (None, ""):
        raise PlacementError("Subcategory is required.")
    try:
        subcategory_id = int(subcategory_id)
    except (TypeError, ValueError) as exc:
        raise PlacementError("Invalid subcategory id.") from exc
    subcategory = (
        OrgCategory.objects.filter(
            pk=subcategory_id,
            is_active=True,
            parent__isnull=False,
            parent__is_active=True,
        )
        .select_related("parent")
        .first()
    )
    if not subcategory:
        raise PlacementError("Select a valid directory subcategory.")
    return subcategory


def apply_directory_placement(
    organization: Organization,
    *,
    geographic_scope: str,
    primary_subcategory_id,
    country_id=None,
    state_id=None,
    county_id=None,
) -> Organization:
    resolved = resolve_placement_areas(
        geographic_scope=geographic_scope,
        country_id=country_id,
        state_id=state_id,
        county_id=county_id,
    )
    subcategory = resolve_subcategory(primary_subcategory_id)

    organization.geographic_scope = resolved["geographic_scope"]
    organization.service_area = resolved["service_area"]
    organization.primary_subcategory = subcategory
    organization.save(
        update_fields=[
            "geographic_scope",
            "service_area",
            "primary_subcategory",
            # Organization has no updated_at; only these fields.
        ]
    )
    return organization


def serialize_directory_placement(organization: Organization) -> dict:
    subcategory = organization.primary_subcategory
    category = None
    if subcategory is not None and subcategory.parent_id:
        category = subcategory.parent

    service_area = organization.service_area
    ancestry = area_ancestry(service_area)
    geo_names = [a.name for a in ancestry]
    category_names = []
    if category:
        category_names.append(category.name)
    if subcategory:
        category_names.append(subcategory.name)

    breadcrumb = geo_names + category_names
    is_complete = bool(
        organization.geographic_scope
        and (
            organization.geographic_scope == Organization.GeographicScope.INTERNATIONAL
            or organization.service_area_id
        )
        and organization.primary_subcategory_id
    )

    if geo_names and category_names:
        summary = f"{geo_names[-1]} • {' → '.join(category_names)}"
    elif geo_names:
        summary = " → ".join(geo_names)
    elif category_names:
        summary = " → ".join(category_names)
    else:
        summary = ""

    country = state = county = None
    for area in ancestry:
        if area.area_type == GeographicArea.AreaType.COUNTRY:
            country = area
        elif area.area_type == GeographicArea.AreaType.ADMIN1:
            state = area
        elif area.area_type == GeographicArea.AreaType.ADMIN2:
            county = area

    return {
        "geographic_scope": organization.geographic_scope or "",
        "service_area": serialize_area(service_area),
        "country": serialize_area(country),
        "state": serialize_area(state),
        "county": serialize_area(county),
        "primary_category": serialize_category(category) if category else None,
        "primary_subcategory": serialize_category(subcategory) if subcategory else None,
        "breadcrumb": breadcrumb,
        "summary": summary,
        "is_complete": is_complete,
    }
