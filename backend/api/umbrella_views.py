"""Umbrella license API: licensor portal + member redeem/leave."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing_service import serialize_organization_service
from .models import Organization, OrganizationRelationship
from .org_access import get_admin_organization
from .umbrella_service import (
    UmbrellaError,
    create_license,
    get_license,
    license_portal_payload,
    member_coverage_payload,
    membership_of,
    redeem_umbrella_code,
    remove_member,
    rotate_code,
    set_license_active,
)


def _admin_org(request, slug):
    try:
        return get_admin_organization(request.user, slug), None
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )


def _error(exc: UmbrellaError):
    http = status.HTTP_400_BAD_REQUEST
    if exc.code in {"not_party"}:
        http = status.HTTP_403_FORBIDDEN
    if exc.code in {"active_subscription_exists", "already_member", "is_licensor"}:
        http = status.HTTP_409_CONFLICT
    if exc.code == "invalid_umbrella_code":
        http = status.HTTP_404_NOT_FOUND
    return Response({"detail": str(exc), "code": exc.code}, status=http)


class UmbrellaPortalView(APIView):
    """GET portal payload; POST creates (or re-activates) the license."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        return Response(license_portal_payload(organization))

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        try:
            create_license(organization=organization, user=request.user)
        except UmbrellaError as exc:
            return _error(exc)
        return Response(license_portal_payload(organization), status=status.HTTP_201_CREATED)


class UmbrellaRotateCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        license = get_license(organization)
        if not license:
            return Response(
                {"detail": "No umbrella license yet.", "code": "no_license"},
                status=status.HTTP_404_NOT_FOUND,
            )
        rotate_code(license)
        return Response(license_portal_payload(organization))


class UmbrellaSetActiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        license = get_license(organization)
        if not license:
            return Response(
                {"detail": "No umbrella license yet.", "code": "no_license"},
                status=status.HTTP_404_NOT_FOUND,
            )
        active = str(request.data.get("is_active", "true")).lower() not in ("0", "false", "no")
        set_license_active(license, active)
        return Response(license_portal_payload(organization))


class UmbrellaRemoveMemberView(APIView):
    """Licensor removes a member (rel id from the portal)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        rel = get_object_or_404(
            OrganizationRelationship.objects.select_related(
                "from_organization", "to_organization"
            ),
            pk=pk,
            kind=OrganizationRelationship.Kind.UMBRELLA_MEMBER,
            from_organization=organization,
        )
        try:
            remove_member(rel, acting_org=organization, user=request.user)
        except UmbrellaError as exc:
            return _error(exc)
        return Response(license_portal_payload(organization))


class UmbrellaRedeemView(APIView):
    """Member org enters an umbrella code on its Billing page."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        code = request.data.get("umbrella_code") or request.data.get("code") or ""
        try:
            rel, service = redeem_umbrella_code(
                organization=organization, user=request.user, code=code
            )
        except UmbrellaError as exc:
            return _error(exc)
        return Response(
            {
                "detail": (
                    f"You are now covered by {rel.from_organization.name}'s umbrella "
                    "license. Your usage counts against their pooled plan."
                ),
                "coverage": member_coverage_payload(organization),
                "service": serialize_organization_service(service),
                "effective_service_level": organization.get_current_service_level(),
                "entitlement_changed": True,
            }
        )


class UmbrellaLeaveView(APIView):
    """Member org leaves its umbrella license (drops to FREE)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        rel = membership_of(organization)
        if not rel:
            return Response(
                {"detail": "This organization is not covered by an umbrella license."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            remove_member(rel, acting_org=organization, user=request.user)
        except UmbrellaError as exc:
            return _error(exc)
        return Response(
            {
                "detail": "You left the umbrella license. This organization is now on the free plan.",
                "effective_service_level": organization.get_current_service_level(),
                "entitlement_changed": True,
            }
        )
