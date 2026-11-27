from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.directory_service import (
    AREA_TYPE_PUBLIC_TO_DB,
    DIRECTORY_SCOPES,
    SCOPE_META,
    organizations_for_directory,
    resolve_area_path,
    search_areas,
    search_localities,
    serialize_area,
    serialize_category,
    serialize_organization,
    service_area_for_scope,
)
from api.models import GeographicArea, OrgCategory


class DirectoryScopesView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        scopes = []
        for scope in DIRECTORY_SCOPES:
            meta = SCOPE_META[scope]
            scopes.append(
                {
                    "value": scope,
                    "label": meta["label"],
                    "geo_steps": meta["geo_steps"],
                }
            )
        return Response({"scopes": scopes})


class DirectoryGeoSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        area_type_raw = (request.query_params.get("area_type") or "").strip()
        area_type = AREA_TYPE_PUBLIC_TO_DB.get(area_type_raw)
        if not area_type:
            return Response(
                {
                    "detail": "area_type must be country, state, county, or locality."
                },
                status=400,
            )

        parent_raw = request.query_params.get("parent_id")
        parent_id = None
        if parent_raw not in (None, ""):
            try:
                parent_id = int(parent_raw)
            except (TypeError, ValueError):
                return Response({"detail": "Invalid parent_id."}, status=400)

        if area_type != GeographicArea.AreaType.COUNTRY and parent_id is None:
            return Response(
                {
                    "detail": "parent_id is required for state, county, and locality."
                },
                status=400,
            )

        query = request.query_params.get("q", "")
        country_code = request.query_params.get("country_code", "")
        try:
            limit = min(int(request.query_params.get("limit", 80)), 500)
        except (TypeError, ValueError):
            limit = 80

        if area_type == GeographicArea.AreaType.LOCALITY:
            results = search_localities(
                parent_id=parent_id,
                query=query,
                limit=limit,
            )
        else:
            areas = search_areas(
                area_type=area_type,
                parent_id=parent_id,
                query=query,
                country_code=country_code,
                limit=limit,
            )
            results = [serialize_area(area) for area in areas]

        return Response(
            {
                "area_type": area_type_raw
                if area_type_raw in {"country", "state", "county", "locality"}
                else {
                    GeographicArea.AreaType.ADMIN1: "state",
                    GeographicArea.AreaType.ADMIN2: "county",
                }.get(area_type, area_type_raw),
                "query": query,
                "results": results,
            }
        )


class DirectoryCategoriesView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        parent_slug = (request.query_params.get("parent") or "").strip()
        if parent_slug:
            parent = OrgCategory.objects.filter(
                slug=parent_slug, parent__isnull=True, is_active=True
            ).first()
            if not parent:
                return Response({"detail": "Category not found."}, status=404)
            children = OrgCategory.objects.filter(
                parent=parent, is_active=True
            ).order_by("sort_order", "name")
            return Response(
                {
                    "parent": serialize_category(parent),
                    "categories": [serialize_category(c) for c in children],
                }
            )

        roots = OrgCategory.objects.filter(
            parent__isnull=True, is_active=True
        ).order_by("sort_order", "name")
        return Response(
            {
                "parent": None,
                "categories": [serialize_category(c) for c in roots],
            }
        )


class DirectoryOrganizationsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        scope = (request.query_params.get("scope") or "").strip()
        if scope not in DIRECTORY_SCOPES:
            return Response(
                {
                    "detail": (
                        "scope must be international, national, "
                        "state_province, local, or city."
                    )
                },
                status=400,
            )

        country_slug = (request.query_params.get("country") or "").strip()
        # Prefer state/county; accept legacy admin1/admin2 query names.
        state_slug = (
            request.query_params.get("state")
            or request.query_params.get("admin1")
            or ""
        ).strip()
        county_slug = (
            request.query_params.get("county")
            or request.query_params.get("admin2")
            or ""
        ).strip()
        locality_slug = (request.query_params.get("locality") or "").strip()
        category_slug = (request.query_params.get("category") or "").strip()
        subcategory_slug = (request.query_params.get("subcategory") or "").strip()
        query = request.query_params.get("q", "")

        path = resolve_area_path(
            country_slug=country_slug,
            state_slug=state_slug,
            county_slug=county_slug,
            locality_slug=locality_slug,
        )
        country = path["country"]
        state = path["state"]
        county = path["county"]
        locality = path["locality"]

        steps = SCOPE_META[scope]["geo_steps"]
        if "country" in steps and country_slug and not country:
            return Response({"detail": "Country not found."}, status=404)
        if "state" in steps and state_slug and not state:
            return Response({"detail": "State not found."}, status=404)
        if "county" in steps and county_slug and not county:
            return Response({"detail": "County not found."}, status=404)

        required_ok = True
        if "country" in steps and not country:
            required_ok = False
        if "state" in steps and not state:
            required_ok = False
        if "county" in steps and not county:
            required_ok = False
        if "locality" in steps and not locality_slug:
            required_ok = False

        breadcrumb = [
            {"type": "scope", "value": scope, "label": SCOPE_META[scope]["label"]}
        ]
        if country:
            breadcrumb.append(
                {"type": "country", "value": country.slug, "label": country.name}
            )
        if state:
            breadcrumb.append(
                {"type": "state", "value": state.slug, "label": state.name}
            )
        if county:
            breadcrumb.append(
                {"type": "county", "value": county.slug, "label": county.name}
            )
        if locality_slug:
            locality_label = (
                locality.name
                if locality
                else locality_slug.replace("-", " ").title()
            )
            breadcrumb.append(
                {
                    "type": "locality",
                    "value": locality_slug,
                    "label": locality_label,
                }
            )

        category = None
        subcategory = None
        if category_slug:
            category = OrgCategory.objects.filter(
                slug=category_slug, parent__isnull=True, is_active=True
            ).first()
            if not category:
                return Response({"detail": "Category not found."}, status=404)
            breadcrumb.append(
                {"type": "category", "value": category.slug, "label": category.name}
            )
        if category and subcategory_slug:
            subcategory = OrgCategory.objects.filter(
                slug=subcategory_slug, parent=category, is_active=True
            ).first()
            if not subcategory:
                return Response({"detail": "Subcategory not found."}, status=404)
            breadcrumb.append(
                {
                    "type": "subcategory",
                    "value": subcategory.slug,
                    "label": subcategory.name,
                }
            )

        if not required_ok:
            return Response(
                {
                    "scope": scope,
                    "breadcrumb": breadcrumb,
                    "geo_complete": False,
                    "service_area": None,
                    "total": 0,
                    "organizations": [],
                    "empty_message": None,
                }
            )

        orgs = list(
            organizations_for_directory(
                scope=scope,
                country=country,
                state=state,
                county=county,
                locality=locality,
                locality_slug=locality_slug,
                category_slug=category_slug,
                subcategory_slug=subcategory_slug,
                query=query,
            )[:100]
        )
        area = service_area_for_scope(
            scope,
            country=country,
            state=state,
            county=county,
            locality=locality,
        )

        empty_message = None
        if not orgs:
            if subcategory_slug or category_slug:
                empty_message = "There is no group here yet"
            else:
                empty_message = "There are no organizations yet."

        return Response(
            {
                "scope": scope,
                "breadcrumb": breadcrumb,
                "geo_complete": True,
                "service_area": serialize_area(area),
                "category": serialize_category(category) if category else None,
                "subcategory": serialize_category(subcategory) if subcategory else None,
                "query": query,
                "total": len(orgs),
                "organizations": [serialize_organization(org) for org in orgs],
                "empty_message": empty_message,
            }
        )
