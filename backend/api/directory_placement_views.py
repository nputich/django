"""Organization directory placement (Explore Communities) API."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .directory_placement import (
    PlacementError,
    apply_directory_placement,
    serialize_directory_placement,
)
from .models import Organization
from .org_access import get_admin_organization, get_primary_community_code


class OrganizationDirectoryPlacementView(APIView):
    """
    GET / PATCH directory placement for an organization the user administers.

    PATCH body:
      geographic_scope, primary_subcategory_id,
      optional country_id / state_id / county_id
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        organization = (
            Organization.objects.select_related(
                "service_area",
                "service_area__parent",
                "service_area__parent__parent",
                "primary_subcategory",
                "primary_subcategory__parent",
            ).get(pk=organization.pk)
        )
        code = get_primary_community_code(organization)
        return Response(
            {
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
                "community_code": code.code if code else None,
                "directory_placement": serialize_directory_placement(organization),
            }
        )

    def patch(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        geographic_scope = data.get("geographic_scope") or data.get("geographicScope")
        subcategory_id = data.get("primary_subcategory_id") or data.get(
            "primarySubcategoryId"
        )
        if not geographic_scope or subcategory_id in (None, ""):
            return Response(
                {
                    "detail": "geographic_scope and primary_subcategory_id are required.",
                    "code": "directory_placement_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            apply_directory_placement(
                organization,
                geographic_scope=geographic_scope,
                primary_subcategory_id=subcategory_id,
                country_id=data.get("country_id", data.get("countryId")),
                state_id=data.get("state_id", data.get("stateId")),
                county_id=data.get("county_id", data.get("countyId")),
            )
        except PlacementError as exc:
            messages = getattr(exc, "messages", None) or [str(exc)]
            return Response(
                {
                    "detail": "; ".join(str(m) for m in messages),
                    "code": "invalid_directory_placement",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = (
            Organization.objects.select_related(
                "service_area",
                "service_area__parent",
                "service_area__parent__parent",
                "primary_subcategory",
                "primary_subcategory__parent",
            ).get(pk=organization.pk)
        )
        code = get_primary_community_code(organization)
        return Response(
            {
                "detail": "Directory placement saved.",
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
                "community_code": code.code if code else None,
                "directory_placement": serialize_directory_placement(organization),
            }
        )
