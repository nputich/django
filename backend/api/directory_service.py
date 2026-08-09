"""Directory helpers: geography filters, org search, taxonomy serialization."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from api.models import GeographicArea, Organization, OrgCategory

# Regional is supported on Organization.GeographicScope but hidden from directory UI.
DIRECTORY_SCOPES = (
    Organization.GeographicScope.INTERNATIONAL,
    Organization.GeographicScope.NATIONAL,
    Organization.GeographicScope.STATE_PROVINCE,
    Organization.GeographicScope.LOCAL,
)

SCOPE_META = {
    Organization.GeographicScope.INTERNATIONAL: {
        "label": "International",
        "geo_steps": [],
    },
    Organization.GeographicScope.NATIONAL: {
        "label": "National",
        "geo_steps": ["country"],
    },
    Organization.GeographicScope.STATE_PROVINCE: {
        "label": "State / Province",
        "geo_steps": ["country", "admin1"],
    },
    Organization.GeographicScope.LOCAL: {
        "label": "Local",
        "geo_steps": ["country", "admin1", "admin2"],
    },
    # Hidden until regional areas are populated:
    # Organization.GeographicScope.REGIONAL: {
    #     "label": "Regional",
    #     "geo_steps": ["country", "admin1", "region"],
    # },
}


def serialize_area(area: GeographicArea | None) -> dict | None:
    if not area:
        return None
    return {
        "id": area.id,
        "name": area.name,
        "slug": area.slug,
        "area_type": area.area_type,
        "country_code": area.country_code,
        "external_code": area.external_code,
        "parent_id": area.parent_id,
    }


def serialize_category(category: OrgCategory) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "parent_id": category.parent_id,
        "sort_order": category.sort_order,
        "is_subcategory": category.is_subcategory,
    }


def serialize_organization(org: Organization) -> dict:
    subcategory = org.primary_subcategory
    category = subcategory.parent if subcategory and subcategory.parent_id else None
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "description": org.description,
        "is_verified": org.is_verified,
        "geographic_scope": org.geographic_scope,
        "service_area": serialize_area(org.service_area),
        "primary_category": serialize_category(category) if category else None,
        "primary_subcategory": serialize_category(subcategory) if subcategory else None,
        "parent_organization_id": org.parent_organization_id,
        "path": f"/org/{org.slug}/hub",
    }


def search_areas(
    *,
    area_type: str,
    parent_id: int | None = None,
    query: str = "",
    country_code: str = "",
    limit: int = 40,
) -> list[GeographicArea]:
    qs = GeographicArea.objects.filter(is_active=True, area_type=area_type)
    if parent_id is not None:
        qs = qs.filter(parent_id=parent_id)
    if country_code:
        qs = qs.filter(country_code__iexact=country_code)
    q = (query or "").strip().casefold()
    if q:
        qs = qs.filter(name_search__contains=q)
    return list(qs.order_by("sort_order", "name")[:limit])


def resolve_area_path(
    *,
    country_slug: str = "",
    admin1_slug: str = "",
    admin2_slug: str = "",
) -> dict[str, GeographicArea | None]:
    country = None
    admin1 = None
    admin2 = None
    if country_slug:
        country = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.COUNTRY,
            slug=country_slug,
            parent__isnull=True,
        ).first()
    if country and admin1_slug:
        admin1 = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.ADMIN1,
            slug=admin1_slug,
            parent=country,
        ).first()
    if admin1 and admin2_slug:
        admin2 = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.ADMIN2,
            slug=admin2_slug,
            parent=admin1,
        ).first()
    return {"country": country, "admin1": admin1, "admin2": admin2}


def service_area_for_scope(
    scope: str,
    *,
    country: GeographicArea | None = None,
    admin1: GeographicArea | None = None,
    admin2: GeographicArea | None = None,
) -> GeographicArea | None:
    if scope == Organization.GeographicScope.INTERNATIONAL:
        return None
    if scope == Organization.GeographicScope.NATIONAL:
        return country
    if scope == Organization.GeographicScope.STATE_PROVINCE:
        return admin1
    if scope == Organization.GeographicScope.LOCAL:
        return admin2
    if scope == Organization.GeographicScope.REGIONAL:
        return None
    return None


def organizations_for_directory(
    *,
    scope: str,
    country: GeographicArea | None = None,
    admin1: GeographicArea | None = None,
    admin2: GeographicArea | None = None,
    category_slug: str = "",
    subcategory_slug: str = "",
    query: str = "",
) -> QuerySet[Organization]:
    qs = Organization.objects.filter(is_active=True).select_related(
        "service_area",
        "primary_subcategory",
        "primary_subcategory__parent",
        "parent_organization",
    )

    if scope:
        qs = qs.filter(geographic_scope=scope)

    area = service_area_for_scope(
        scope, country=country, admin1=admin1, admin2=admin2
    )
    if scope == Organization.GeographicScope.INTERNATIONAL:
        pass
    elif area is not None:
        qs = qs.filter(service_area=area)
    else:
        # Incomplete geo path for this scope → no matches yet.
        return qs.none()

    if category_slug and subcategory_slug:
        qs = qs.filter(
            primary_subcategory__slug=subcategory_slug,
            primary_subcategory__parent__slug=category_slug,
            primary_subcategory__is_active=True,
            primary_subcategory__parent__is_active=True,
        )
    elif category_slug:
        qs = qs.filter(
            primary_subcategory__parent__slug=category_slug,
            primary_subcategory__parent__is_active=True,
            primary_subcategory__is_active=True,
        )

    q = (query or "").strip()
    if q:
        alias_q = Q()
        # JSON list of strings — Postgres supports icontains on JSON text cast via name/aliases.
        alias_q |= Q(search_aliases__icontains=q)
        qs = qs.filter(Q(name__icontains=q) | alias_q)

    return qs.order_by("name")
