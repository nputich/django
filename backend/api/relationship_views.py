"""Org admin API for organization relationships (request / accept / decline / end)."""

from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Organization, OrganizationRelationship
from .org_access import get_admin_organization
from .relationship_service import (
    RelationshipError,
    accept_relationship,
    cancel_request,
    decline_relationship,
    end_relationship,
    request_relationship,
    serialize_relationship,
    set_public,
    settings_payload,
)

_NOT_ADMIN = Response(
    {"detail": "Organization not found or you are not an admin."},
    status=status.HTTP_404_NOT_FOUND,
)


def _error(exc: RelationshipError):
    http = status.HTTP_400_BAD_REQUEST
    if exc.code in {"not_recipient", "not_requester", "not_party"}:
        http = status.HTTP_403_FORBIDDEN
    return Response({"detail": exc.message, "code": exc.code}, status=http)


def _admin_org(request, slug):
    try:
        return get_admin_organization(request.user, slug), None
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )


def _get_rel(organization: Organization, pk) -> OrganizationRelationship:
    return get_object_or_404(
        OrganizationRelationship.objects.filter(
            Q(from_organization=organization) | Q(to_organization=organization)
        ).select_related(
            "from_organization", "to_organization", "initiated_by_organization"
        ),
        pk=pk,
    )


class OrganizationRelationshipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        return Response(settings_payload(organization))

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        target_slug = (request.data.get("target_slug") or "").strip()
        direction = (request.data.get("direction") or "").strip()
        note = request.data.get("note") or ""
        public = request.data.get("public", True)
        if not target_slug:
            return Response(
                {"detail": "Choose an organization.", "code": "target_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target = Organization.objects.filter(
            slug=target_slug, is_active=True, status=Organization.Status.ACTIVE
        ).first()
        if not target:
            return Response(
                {"detail": "That organization was not found.", "code": "target_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            rel = request_relationship(
                requesting_org=organization,
                target_org=target,
                direction=direction,
                user=request.user,
                note=note,
                public=str(public).lower() not in ("0", "false", "no"),
            )
        except RelationshipError as exc:
            return _error(exc)
        return Response(
            serialize_relationship(rel, for_organization=organization),
            status=status.HTTP_201_CREATED,
        )


class OrganizationRelationshipDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        rel = _get_rel(organization, pk)
        if "public" not in request.data:
            return Response(
                {"detail": "Nothing to update."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            rel = set_public(
                rel,
                acting_org=organization,
                public=str(request.data.get("public")).lower() not in ("0", "false", "no"),
            )
        except RelationshipError as exc:
            return _error(exc)
        return Response(serialize_relationship(rel, for_organization=organization))


class _RelationshipActionView(APIView):
    permission_classes = [IsAuthenticated]
    action = None

    def post(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        rel = _get_rel(organization, pk)
        try:
            rel = self.action(rel, acting_org=organization, user=request.user)
        except RelationshipError as exc:
            return _error(exc)
        return Response(serialize_relationship(rel, for_organization=organization))


class OrganizationRelationshipAcceptView(_RelationshipActionView):
    action = staticmethod(accept_relationship)


class OrganizationRelationshipDeclineView(_RelationshipActionView):
    action = staticmethod(decline_relationship)


class OrganizationRelationshipWithdrawView(_RelationshipActionView):
    action = staticmethod(cancel_request)


class OrganizationRelationshipEndView(_RelationshipActionView):
    action = staticmethod(end_relationship)


class OrganizationLookupView(APIView):
    """Typeahead for choosing another org (active orgs only, excludes self)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        exclude = (request.query_params.get("exclude") or "").strip()
        if len(q) < 2:
            return Response({"results": []})
        qs = Organization.objects.filter(
            is_active=True, status=Organization.Status.ACTIVE
        ).filter(Q(name__icontains=q) | Q(slug__icontains=q))
        if exclude:
            qs = qs.exclude(slug=exclude)
        return Response(
            {
                "results": [
                    {"id": o.id, "name": o.name, "slug": o.slug}
                    for o in qs.order_by("name")[:10]
                ]
            }
        )
