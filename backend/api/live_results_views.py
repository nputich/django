"""Participant live-results endpoints and organizer release controls."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.live_results import (
    LiveResultsDenied,
    meeting_live_results,
    set_meeting_slide_released,
    set_survey_question_released,
    survey_live_results,
)
from api.meeting_access import get_latest_session
from api.meeting_service import get_organizer_live_payload
from api.models import Meeting, MeetingSession, MeetingSlide, Organization, Survey, SurveyQuestion
from api.org_access import get_admin_organization
from api.serializers import DashboardSurveyDetailSerializer, LiveResultsReleaseSerializer


def _optional_int(raw):
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _denied(exc: LiveResultsDenied) -> Response:
    return Response({"detail": exc.detail, "code": exc.code}, status=exc.status_code)


def _admin_org(request, slug):
    try:
        return get_admin_organization(request.user, slug), None
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )


class MeetingLiveResultsView(APIView):
    """Combined results for organizer-released slides, for joined participants."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        meeting = get_object_or_404(Meeting, pk=pk)
        session = get_latest_session(meeting)
        try:
            payload = meeting_live_results(
                meeting,
                session,
                attendance_id=request.query_params.get("attendance_id"),
                slide_id=_optional_int(request.query_params.get("slide_id")),
            )
        except LiveResultsDenied as exc:
            return _denied(exc)
        return Response(payload)


class OrganizationMeetingReleaseResultsView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
        serializer = LiveResultsReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "enabled" in data:
            meeting.live_results_for_participants = data["enabled"]
            meeting.save(update_fields=["live_results_for_participants"])

        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)

        if "item_id" in data:
            slide = get_object_or_404(MeetingSlide, pk=data["item_id"], meeting=meeting)
            try:
                set_meeting_slide_released(session, slide, data["released"])
            except DjangoValidationError as exc:
                return Response({"detail": exc.messages[0]}, status=400)

        session = MeetingSession.objects.select_related("current_slide").get(pk=session.pk)
        return Response(
            {
                "detail": "Live results updated.",
                "live": get_organizer_live_payload(meeting, session),
            }
        )


class SurveyLiveResultsView(APIView):
    """Combined results for organizer-released questions, for respondents who submitted."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        try:
            payload = survey_live_results(
                survey,
                response_session=request.query_params.get("response_session"),
                question_id=_optional_int(request.query_params.get("question_id")),
            )
        except LiveResultsDenied as exc:
            return _denied(exc)
        return Response(payload)


class OrganizationSurveyReleaseResultsView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        survey = get_object_or_404(Survey, pk=pk, organization=organization)
        serializer = LiveResultsReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "enabled" in data:
            survey.live_results_for_respondents = data["enabled"]
            survey.save(update_fields=["live_results_for_respondents"])

        if "item_id" in data:
            question = get_object_or_404(SurveyQuestion, pk=data["item_id"], survey=survey)
            try:
                set_survey_question_released(survey, question, data["released"])
            except DjangoValidationError as exc:
                return Response({"detail": exc.messages[0]}, status=400)

        survey = Survey.objects.prefetch_related("questions", "access_codes").get(pk=survey.pk)
        return Response(DashboardSurveyDetailSerializer(survey).data)
