"""Owner-side share management + recipient-side shared results."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .meeting_export import MEETING_DF_COLUMNS, build_meeting_df, csv_http_response, render_csv
from .meeting_sharing import (
    AGGREGATE_CSV_COLUMNS,
    SharingError,
    aggregate_csv_rows,
    aggregate_results,
    disclosure_payload,
    get_share_for_recipient,
    grant_share,
    list_shares,
    meeting_has_started,
    revoke_share,
    serialize_share,
    shares_for_recipient,
)
from .models import Meeting, MeetingShare, Organization
from .org_access import get_admin_organization


def _admin_org(request, slug):
    try:
        return get_admin_organization(request.user, slug), None
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )


def _error(exc: SharingError):
    http = status.HTTP_400_BAD_REQUEST
    if exc.code == "not_shared":
        http = status.HTTP_404_NOT_FOUND
    if exc.code == "duplicate_share":
        http = status.HTTP_409_CONFLICT
    return Response({"detail": exc.message, "code": exc.code}, status=http)


def _owner_payload(meeting: Meeting) -> dict:
    return {
        "meeting_id": meeting.id,
        "has_started": meeting_has_started(meeting),
        "aggregate_sharing_notice": meeting.aggregate_sharing_notice,
        "shares": list_shares(meeting),
        "disclosure": disclosure_payload(meeting),
    }


class MeetingSharesView(APIView):
    """Owner: GET shares + disclosure preview; POST {organization_slug} to grant."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
        return Response(_owner_payload(meeting))

    def post(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
        target_slug = (request.data.get("organization_slug") or "").strip()
        target = Organization.objects.filter(slug=target_slug).first()
        if not target:
            return Response(
                {"detail": "That organization was not found.", "code": "target_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            grant_share(meeting=meeting, organization=target, user=request.user)
        except SharingError as exc:
            return _error(exc)
        return Response(_owner_payload(meeting), status=status.HTTP_201_CREATED)

    def patch(self, request, slug, pk):
        """Toggle the aggregate-sharing notice sentence."""
        organization, err = _admin_org(request, slug)
        if err:
            return err
        meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
        if "aggregate_sharing_notice" in request.data:
            meeting.aggregate_sharing_notice = str(request.data["aggregate_sharing_notice"]).lower() not in (
                "0",
                "false",
                "no",
            )
            meeting.save(update_fields=["aggregate_sharing_notice"])
        return Response(_owner_payload(meeting))


class MeetingShareRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk, share_pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
        share = get_object_or_404(MeetingShare, pk=share_pk, meeting=meeting)
        revoke_share(share, user=request.user)
        return Response(_owner_payload(meeting))


class SharedMeetingsListView(APIView):
    """Recipient: meetings other organizations shared with us."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        items = []
        for share in shares_for_recipient(organization):
            m = share.meeting
            items.append(
                {
                    **serialize_share(share),
                    "meeting": {
                        "id": m.id,
                        "title": m.title,
                        "status": m.status,
                        "is_anonymous": m.is_anonymous,
                        "scheduled_start_at": m.scheduled_start_at,
                        "started_at": m.started_at,
                        "ended_at": m.ended_at,
                        "organization": {"name": m.organization.name, "slug": m.organization.slug},
                    },
                }
            )
        return Response({"organization": {"name": organization.name, "slug": organization.slug}, "shared": items})


class SharedMeetingResultsView(APIView):
    """
    Recipient: results for one shared meeting.

    ?export=csv → FULL access downloads every stored row (anonymous participant
    UUID included); AGGREGATE access downloads buckets and totals.
    (``format`` is reserved by DRF's renderer negotiation, hence ``export``.)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, slug, meeting_pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        try:
            share = get_share_for_recipient(organization, meeting_pk)
        except SharingError as exc:
            return _error(exc)
        meeting = share.meeting
        access = share.effective_access
        fmt = (request.query_params.get("export") or "json").lower()

        if fmt == "csv":
            if access == MeetingShare.Access.FULL:
                rows = build_meeting_df(meeting, "all")
                return csv_http_response(
                    f"shared-meeting-{meeting.id}-full.csv", render_csv(rows, MEETING_DF_COLUMNS)
                )
            rows = aggregate_csv_rows(meeting)
            return csv_http_response(
                f"shared-meeting-{meeting.id}-aggregate.csv", render_csv(rows, AGGREGATE_CSV_COLUMNS)
            )

        payload = aggregate_results(meeting)
        payload["share"] = serialize_share(share)
        payload["access"] = access
        if access == MeetingShare.Access.FULL:
            rows = build_meeting_df(meeting, "all")
            payload["full_rows"] = rows
            payload["full_columns"] = MEETING_DF_COLUMNS
        return Response(payload)
