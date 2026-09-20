"""Meeting wall RSVP, summary, and community results endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.board_service import is_org_admin
from api.meeting_access import get_latest_session
from api.meeting_analytics import get_slide_analytics, is_analyzable_slide
from api.meeting_wall import (
    can_create_meeting_minutes,
    can_publish_meeting_summary,
    can_view_meeting_results,
    participation_totals,
    published_summary,
    serialize_meeting_wall_card,
    set_expected_attendance,
)
from api.models import Meeting, MeetingSummary
from api.serializers import (
    MeetingExpectedAttendanceSerializer,
    MeetingSummaryWriteSerializer,
)


class MeetingRsvpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        meeting = get_object_or_404(
            Meeting.objects.select_related("organization"), pk=pk
        )
        serializer = MeetingExpectedAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data.get("status")
        status_value = (raw or "").strip().lower() or None
        try:
            row = set_expected_attendance(
                meeting=meeting, user=request.user, status=status_value
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "my_rsvp": row.status if row else None,
                "wall": serialize_meeting_wall_card(meeting, request.user),
            }
        )


class MeetingSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        meeting = get_object_or_404(
            Meeting.objects.select_related("organization"), pk=pk
        )
        published = published_summary(meeting)
        if not published:
            return Response(
                {"detail": "No published summary is available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "id": published.id,
                "body": published.body,
                "published_at": published.published_at,
                "meeting_id": meeting.id,
                "meeting_title": meeting.title,
            }
        )

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        meeting = get_object_or_404(
            Meeting.objects.select_related("organization"), pk=pk
        )
        if not can_create_meeting_minutes(meeting, request.user):
            return Response(
                {"detail": "You cannot create meeting minutes for this meeting."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = MeetingSummaryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        is_admin = is_org_admin(meeting.organization, request.user)
        desired = data.get("status", MeetingSummary.Status.DRAFT)

        if desired == MeetingSummary.Status.PUBLISHED:
            if not can_publish_meeting_summary(meeting, request.user):
                return Response(
                    {"detail": "Only organizers can publish the meeting summary."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            MeetingSummary.objects.filter(
                meeting=meeting, status=MeetingSummary.Status.PUBLISHED
            ).update(status=MeetingSummary.Status.DRAFT)
            row = MeetingSummary.objects.create(
                meeting=meeting,
                author=request.user,
                body=data["body"].strip(),
                status=MeetingSummary.Status.PUBLISHED,
                is_organizer_authored=True,
                published_at=timezone.now(),
            )
        else:
            if not is_admin and desired == MeetingSummary.Status.DRAFT:
                desired = MeetingSummary.Status.SUBMITTED
            if desired == MeetingSummary.Status.PUBLISHED:
                desired = MeetingSummary.Status.SUBMITTED
            row = MeetingSummary.objects.create(
                meeting=meeting,
                author=request.user,
                body=data["body"].strip(),
                status=desired,
                is_organizer_authored=is_admin,
                published_at=None,
            )

        return Response(
            {
                "id": row.id,
                "status": row.status,
                "body": row.body,
                "is_organizer_authored": row.is_organizer_authored,
                "published_at": row.published_at,
            },
            status=status.HTTP_201_CREATED,
        )


class MeetingSummaryPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, summary_id):
        meeting = get_object_or_404(
            Meeting.objects.select_related("organization"), pk=pk
        )
        if not can_publish_meeting_summary(meeting, request.user):
            return Response(
                {"detail": "Only organizers can publish the meeting summary."},
                status=status.HTTP_403_FORBIDDEN,
            )
        summary = get_object_or_404(MeetingSummary, pk=summary_id, meeting=meeting)
        MeetingSummary.objects.filter(
            meeting=meeting, status=MeetingSummary.Status.PUBLISHED
        ).exclude(pk=summary.pk).update(status=MeetingSummary.Status.DRAFT)
        summary.status = MeetingSummary.Status.PUBLISHED
        summary.published_at = timezone.now()
        summary.save(update_fields=["status", "published_at", "updated_at"])
        return Response(
            {
                "id": summary.id,
                "status": summary.status,
                "body": summary.body,
                "published_at": summary.published_at,
            }
        )


class MeetingCommunityResultsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        meeting = get_object_or_404(
            Meeting.objects.select_related("organization").prefetch_related("slides"),
            pk=pk,
        )
        if not can_view_meeting_results(meeting, request.user):
            return Response(
                {"detail": "Meeting results are not available."},
                status=status.HTTP_403_FORBIDDEN,
            )
        session = get_latest_session(meeting)
        slides_out = []
        if session:
            for slide in meeting.slides.filter(is_active=True).order_by("order", "id"):
                if not is_analyzable_slide(slide):
                    continue
                payload = get_slide_analytics(meeting, session, slide, limit=10)
                if payload.get("error"):
                    continue
                slides_out.append(
                    {
                        "slide_id": slide.id,
                        "title": slide.title or slide.prompt,
                        "slide_type": slide.slide_type,
                        "bars": payload.get("bars", []),
                        "respondent_count": payload.get("filtered_respondents"),
                    }
                )
        return Response(
            {
                "meeting_id": meeting.id,
                "title": meeting.title,
                "totals": participation_totals(meeting),
                "slides": slides_out,
            }
        )
