from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.directory_service import (
    DIRECTORY_SCOPES,
    SCOPE_META,
    organizations_for_directory,
    resolve_area_path,
    search_areas,
    serialize_area,
    serialize_category,
    serialize_organization,
    service_area_for_scope,
)
from api.models import GeographicArea, Organization, OrgCategory


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
        area_type = (request.query_params.get("area_type") or "").strip()
        if area_type not in {
            GeographicArea.AreaType.COUNTRY,
            GeographicArea.AreaType.ADMIN1,
            GeographicArea.AreaType.ADMIN2,
            # GeographicArea.AreaType.REGION,  # hidden until regional data exists
        }:
            return Response(
                {"detail": "area_type must be country, admin1, or admin2."},
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
                {"detail": "parent_id is required for admin1 and admin2."},
                status=400,
            )

        query = request.query_params.get("q", "")
        country_code = request.query_params.get("country_code", "")
        try:
            limit = min(int(request.query_params.get("limit", 40)), 100)
        except (TypeError, ValueError):
            limit = 40

        areas = search_areas(
            area_type=area_type,
            parent_id=parent_id,
            query=query,
            country_code=country_code,
            limit=limit,
        )
        return Response(
            {
                "area_type": area_type,
                "query": query,
                "results": [serialize_area(area) for area in areas],
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
                    "detail": "scope must be international, national, state_province, or local."
                },
                status=400,
            )

        country_slug = (request.query_params.get("country") or "").strip()
        admin1_slug = (request.query_params.get("admin1") or "").strip()
        admin2_slug = (request.query_params.get("admin2") or "").strip()
        category_slug = (request.query_params.get("category") or "").strip()
        subcategory_slug = (request.query_params.get("subcategory") or "").strip()
        query = request.query_params.get("q", "")

        path = resolve_area_path(
            country_slug=country_slug,
            admin1_slug=admin1_slug,
            admin2_slug=admin2_slug,
        )
        country = path["country"]
        admin1 = path["admin1"]
        admin2 = path["admin2"]

        steps = SCOPE_META[scope]["geo_steps"]
        if "country" in steps and country_slug and not country:
            return Response({"detail": "Country not found."}, status=404)
        if "admin1" in steps and admin1_slug and not admin1:
            return Response({"detail": "State / province not found."}, status=404)
        if "admin2" in steps and admin2_slug and not admin2:
            return Response({"detail": "Local area not found."}, status=404)

        required_ok = True
        if "country" in steps and not country:
            required_ok = False
        if "admin1" in steps and not admin1:
            required_ok = False
        if "admin2" in steps and not admin2:
            required_ok = False

        breadcrumb = [{"type": "scope", "value": scope, "label": SCOPE_META[scope]["label"]}]
        if country:
            breadcrumb.append(
                {"type": "country", "value": country.slug, "label": country.name}
            )
        if admin1:
            breadcrumb.append(
                {"type": "admin1", "value": admin1.slug, "label": admin1.name}
            )
        if admin2:
            breadcrumb.append(
                {"type": "admin2", "value": admin2.slug, "label": admin2.name}
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
                admin1=admin1,
                admin2=admin2,
                category_slug=category_slug,
                subcategory_slug=subcategory_slug,
                query=query,
            )[:100]
        )
        area = service_area_for_scope(
            scope, country=country, admin1=admin1, admin2=admin2
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
