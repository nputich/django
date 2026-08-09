"""Directory helpers: geography filters, org search, taxonomy serialization."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from api.models import GeographicArea, Organization, OrgCategory

# "city" is a directory browse level (not an Organization.GeographicScope value).
DIRECTORY_SCOPE_CITY = "city"

# Regional is supported on Organization.GeographicScope but hidden from directory UI.
DIRECTORY_SCOPES = (
    Organization.GeographicScope.INTERNATIONAL,
    Organization.GeographicScope.NATIONAL,
    Organization.GeographicScope.STATE_PROVINCE,
    Organization.GeographicScope.LOCAL,
    DIRECTORY_SCOPE_CITY,
)

SCOPE_META = {
    Organization.GeographicScope.INTERNATIONAL: {
        "label": "Global",
        "geo_steps": [],
    },
    Organization.GeographicScope.NATIONAL: {
        "label": "National",
        "geo_steps": ["country"],
    },
    Organization.GeographicScope.STATE_PROVINCE: {
        "label": "State",
        "geo_steps": ["country", "state"],
    },
    Organization.GeographicScope.LOCAL: {
        "label": "County / Region",
        "geo_steps": ["country", "state", "county"],
    },
    DIRECTORY_SCOPE_CITY: {
        "label": "City / Local",
        "geo_steps": ["country", "state", "county", "locality"],
    },
    # Hidden until regional areas are populated:
    # Organization.GeographicScope.REGIONAL: {
    #     "label": "Regional",
    #     "geo_steps": ["country", "state", "region"],
    # },
}

# Public directory API uses state/county; DB stores GIS admin1/admin2 codes.
AREA_TYPE_PUBLIC_TO_DB = {
    "country": GeographicArea.AreaType.COUNTRY,
    "state": GeographicArea.AreaType.ADMIN1,
    "county": GeographicArea.AreaType.ADMIN2,
    "locality": GeographicArea.AreaType.LOCALITY,
    # Accept legacy GIS names from older clients.
    "admin1": GeographicArea.AreaType.ADMIN1,
    "admin2": GeographicArea.AreaType.ADMIN2,
}

AREA_TYPE_DB_TO_PUBLIC = {
    GeographicArea.AreaType.COUNTRY: "country",
    GeographicArea.AreaType.ADMIN1: "state",
    GeographicArea.AreaType.ADMIN2: "county",
    GeographicArea.AreaType.LOCALITY: "locality",
    GeographicArea.AreaType.REGION: "region",
}


def serialize_area(area: GeographicArea | None) -> dict | None:
    if not area:
        return None
    return {
        "id": area.id,
        "name": area.name,
        "slug": area.slug,
        "area_type": AREA_TYPE_DB_TO_PUBLIC.get(area.area_type, area.area_type),
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


def search_localities(
    *,
    parent_id: int,
    query: str = "",
    limit: int = 40,
) -> list[dict]:
    """Return locality areas, falling back to distinct HQ city names under a county."""
    from django.utils.text import slugify

    areas = search_areas(
        area_type=GeographicArea.AreaType.LOCALITY,
        parent_id=parent_id,
        query=query,
        limit=limit,
    )
    if areas:
        return [serialize_area(area) for area in areas]

    q = (query or "").strip().casefold()
    cities: dict[str, str] = {}
    for name in (
        Organization.objects.filter(
            is_active=True,
            service_area_id=parent_id,
        )
        .exclude(headquarters_city="")
        .values_list("headquarters_city", flat=True)
        .distinct()
    ):
        label = (name or "").strip()
        if not label:
            continue
        if q and q not in label.casefold():
            continue
        slug = slugify(label)
        if slug and slug not in cities:
            cities[slug] = label
        if len(cities) >= limit:
            break

    return [
        {
            "id": f"city:{slug}",
            "name": name,
            "slug": slug,
            "area_type": "locality",
            "country_code": "",
            "external_code": "",
            "parent_id": parent_id,
        }
        for slug, name in sorted(cities.items(), key=lambda item: item[1].casefold())
    ]


def resolve_area_path(
    *,
    country_slug: str = "",
    state_slug: str = "",
    county_slug: str = "",
    locality_slug: str = "",
) -> dict[str, GeographicArea | None]:
    country = None
    state = None
    county = None
    locality = None
    if country_slug:
        country = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.COUNTRY,
            slug=country_slug,
            parent__isnull=True,
        ).first()
    if country and state_slug:
        state = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.ADMIN1,
            slug=state_slug,
            parent=country,
        ).first()
    if state and county_slug:
        county = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.ADMIN2,
            slug=county_slug,
            parent=state,
        ).first()
    if county and locality_slug:
        locality = GeographicArea.objects.filter(
            is_active=True,
            area_type=GeographicArea.AreaType.LOCALITY,
            slug=locality_slug,
            parent=county,
        ).first()
    return {
        "country": country,
        "state": state,
        "county": county,
        "locality": locality,
    }


def service_area_for_scope(
    scope: str,
    *,
    country: GeographicArea | None = None,
    state: GeographicArea | None = None,
    county: GeographicArea | None = None,
    locality: GeographicArea | None = None,
) -> GeographicArea | None:
    if scope == Organization.GeographicScope.INTERNATIONAL:
        return None
    if scope == Organization.GeographicScope.NATIONAL:
        return country
    if scope == Organization.GeographicScope.STATE_PROVINCE:
        return state
    if scope == Organization.GeographicScope.LOCAL:
        return county
    if scope == DIRECTORY_SCOPE_CITY:
        return locality or county
    if scope == Organization.GeographicScope.REGIONAL:
        return None
    return None


def organizations_for_directory(
    *,
    scope: str,
    country: GeographicArea | None = None,
    state: GeographicArea | None = None,
    county: GeographicArea | None = None,
    locality: GeographicArea | None = None,
    locality_slug: str = "",
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

    if scope == DIRECTORY_SCOPE_CITY:
        # City browse uses local-scoped orgs, filtered to a locality / city name.
        qs = qs.filter(geographic_scope=Organization.GeographicScope.LOCAL)
        if locality is not None:
            qs = qs.filter(service_area=locality)
        elif county is not None and locality_slug:
            from django.utils.text import slugify

            matched_ids = [
                org.id
                for org in qs.filter(service_area=county).exclude(headquarters_city="")
                if slugify(org.headquarters_city) == locality_slug
            ]
            qs = qs.filter(id__in=matched_ids)
        else:
            return qs.none()
    else:
        if scope:
            qs = qs.filter(geographic_scope=scope)

        area = service_area_for_scope(
            scope,
            country=country,
            state=state,
            county=county,
            locality=locality,
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
