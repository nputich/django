from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .contact_email import send_contact_notification
from .models import AccessCode, ContactSubmission, Meeting, MeetingAttendance, MeetingSession, MeetingSlide, Organization, Survey, SurveyAnswer, SurveyQuestion
from .meeting_access import (
    can_start_meeting,
    end_meeting_session,
    get_latest_session,
    get_slide_by_id,
    go_to_next_slide,
    go_to_previous_slide,
    go_to_slide,
    meeting_join_error,
    pause_meeting_session,
    restart_meeting_session,
    resume_meeting_session,
    session_is_joinable,
    start_meeting_session,
)
from .meeting_export import (
    MEETING_DF_COLUMNS,
    PROFILE_EXPORT_COLUMNS,
    build_meeting_df,
    build_profile_export,
    csv_http_response,
    meeting_export_summary,
    render_csv,
)
from .meeting_service import (
    append_meeting_slides,
    create_initial_session,
    create_meeting_slides,
    get_attendance,
    get_organizer_live_payload,
    get_session_stats,
    join_session,
    leave_attendance,
    participant_completed_slide_ids,
    replace_meeting_slides,
    submit_participant_profile,
    submit_issue_card_responses,
    submit_slide_response,
)
from .survey_service import append_survey_questions
from .meeting_analytics import get_slide_analytics, get_slide_analytics_compare
from .meeting_ai import process_meeting_ai, schedule_response_ai_processing
from .political_issue_classifier import classify_political_slide_responses
from .org_access import (
    get_admin_organization,
    get_resource_type,
    is_resource_code_available,
    normalize_access_code,
    resolve_access_code,
    user_admin_organizations,
    validate_access_code_format,
)
from .serializers import (
    ContactSubmissionSerializer,
    DashboardMeetingCreateSerializer,
    DashboardMeetingUpdateSerializer,
    DashboardSurveyCreateSerializer,
    DashboardSurveyDetailSerializer,
    DashboardSurveyUpdateSerializer,
    SurveyAppendQuestionsSerializer,
    MeetingDetailSerializer,
    MeetingJoinSerializer,
    MeetingLeaveSerializer,
    MeetingProfileSubmitSerializer,
    MeetingRespondSerializer,
    MeetingSessionPublicSerializer,
    MeetingStartSerializer,
    MeetingGoToSlideSerializer,
    MeetingRestartSerializer,
    MeetingAddSlidesSerializer,
    MyOrganizationSerializer,
    OrganizationDashboardSerializer,
    OrganizationHubSerializer,
    SurveyDetailSerializer,
    SurveySubmitSerializer,
    UserSerializer,
)


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


def build_access_code_result(access_code):
    org = access_code.organization
    type_slug = access_code.resource_type.slug
    label = access_code.label
    description = access_code.search_description
    path = "/"
    requires_login = False
    requires_private_code = False
    if type_slug == "survey" and access_code.survey_id:
        survey = access_code.survey
        label = label or survey.title
        description = description or survey.description or org.name
        path = f"/s/{survey.id}"
    elif type_slug == "meeting" and access_code.meeting_id:
        meeting = access_code.meeting
        label = label or meeting.title
        description = description or meeting.description or org.name
        path = f"/m/{meeting.id}"
        requires_login = meeting.access_mode in ("semi_public", "private")
        requires_private_code = meeting.access_mode == "private"
    elif type_slug == "organization":
        label = label or org.name
        description = description or org.description or "Organization hub"
        path = f"/org/{org.slug}/hub"
    else:
        return None
    return {
        "target_id": access_code.id,
        "code": access_code.code,
        "label": label,
        "description": description,
        "type": type_slug,
        "organization_name": org.name,
        "requires_login": requires_login,
        "requires_private_code": requires_private_code,
        "path": path,
        "sort_order": access_code.sort_order,
        "is_primary": access_code.is_primary,
        "is_verified": org.is_verified,
    }
class ResolveCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    MATCH_LIMIT = 10

    def get(self, request, query):
        q = query.strip().upper()
        if not q:
            return Response({"query": "", "match_count": 0, "results": []})

        codes = (
            AccessCode.objects.filter(code__istartswith=q, is_active=True)
            .select_related(
                "organization",
                "resource_type",
                "survey",
                "meeting",
            )
            .order_by("sort_order", "code", "id")
        )
        now = timezone.now()
        results = []
        for access_code in codes:
            if access_code.expires_at and access_code.expires_at < now:
                continue
            item = build_access_code_result(access_code)
            if item:
                results.append(item)
            if len(results) >= self.MATCH_LIMIT:
                break
        results.sort(
            key=lambda r: (
                not r["is_primary"],
                not r["is_verified"],
                r["sort_order"],
                r["code"],
            )
        )
        return Response(
            {
                "query": q,
                "match_count": len(results),
                "results": results,
            }
        )
class SurveyDetailView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, pk):
        survey = get_object_or_404(
            Survey.objects.select_related("organization").prefetch_related("questions"),
            pk=pk,
            is_active=True,
        )
        return Response(SurveyDetailSerializer(survey).data)
class SurveySubmitView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk, is_active=True)
        serializer = SurveySubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_session = serializer.validated_data["response_session"]
        answers = serializer.validated_data["answers"]
        question_ids = {a["question_id"] for a in answers}
        valid_questions = SurveyQuestion.objects.filter(survey=survey, id__in=question_ids)
        valid_map = {q.id: q for q in valid_questions}
        if len(valid_map) != len(question_ids):
            return Response(
                {"detail": "One or more questions are invalid for this survey."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for answer in answers:
            SurveyAnswer.objects.create(
                survey=survey,
                question=valid_map[answer["question_id"]],
                response_session=response_session,
                value=answer["value"],
            )
        return Response({"detail": "Survey submitted. Thank you!"}, status=status.HTTP_201_CREATED)
class OrganizationHubView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        return Response(OrganizationHubSerializer(organization).data)


class MyOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orgs = user_admin_organizations(request.user).order_by("name")
        serializer = MyOrganizationSerializer(
            orgs, many=True, context={"request": request}
        )
        return Response({"organizations": serializer.data})


class OrganizationDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        organization = Organization.objects.prefetch_related(
            Prefetch(
                "surveys",
                queryset=Survey.objects.order_by("-created_at").prefetch_related(
                    "access_codes"
                ),
            ),
            Prefetch(
                "meetings",
                queryset=Meeting.objects.order_by("-created_at").prefetch_related(
                    "access_codes"
                ),
            ),
            "board",
        ).get(pk=organization.pk)
        return Response(OrganizationDashboardSerializer(organization).data)


class AccessCodeCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("code", "").strip()
        type_slug = request.query_params.get("type", "").strip().lower()
        if type_slug not in ("survey", "meeting"):
            return Response(
                {"detail": "Query param 'type' must be 'survey' or 'meeting'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not code:
            return Response(
                {"detail": "Query param 'code' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            normalized = validate_access_code_format(code)
        except DjangoValidationError as exc:
            return Response(
                {
                    "available": False,
                    "normalized": normalize_access_code(code),
                    "reason": "invalid_format",
                    "detail": exc.messages[0],
                }
            )
        available = is_resource_code_available(normalized, type_slug)
        payload = {"available": available, "normalized": normalized}
        if not available:
            payload["reason"] = "already_in_use"
            payload["detail"] = "This access code is already in use by an active survey or meeting."
        return Response(payload)


class OrganizationSurveyCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DashboardSurveyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            code = resolve_access_code(data.get("access_code"), "survey")
            resource_type = get_resource_type("survey")
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        survey = Survey.objects.create(
            organization=organization,
            title=data["title"],
            description=data.get("description", ""),
            is_anonymous=data.get("is_anonymous", True),
            is_active=True,
        )
        for question in data["questions"]:
            SurveyQuestion.objects.create(
                survey=survey,
                order=question.get("order", 0),
                text=question["text"],
                question_type=question.get(
                    "question_type", SurveyQuestion.QuestionType.TEXT
                ),
                choices=question.get("choices", []),
            )
        access_code = AccessCode.objects.create(
            code=code,
            organization=organization,
            resource_type=resource_type,
            survey=survey,
            label=data.get("label") or survey.title,
            search_description=data.get("search_description")
            or survey.description
            or organization.name,
            is_primary=True,
            is_active=True,
        )
        return Response(
            {
                "survey": {
                    "id": survey.id,
                    "title": survey.title,
                    "description": survey.description,
                    "path": f"/s/{survey.id}",
                },
                "access_code": {
                    "id": access_code.id,
                    "code": access_code.code,
                    "label": access_code.label,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationSurveyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        survey = get_object_or_404(
            Survey.objects.prefetch_related("questions", "access_codes"),
            pk=pk,
            organization=organization,
        )
        return Response(DashboardSurveyDetailSerializer(survey).data)

    @transaction.atomic
    def patch(self, request, slug, pk):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        survey = get_object_or_404(Survey, pk=pk, organization=organization)
        serializer = DashboardSurveyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in ("title", "description", "is_anonymous", "is_active"):
            if field in data:
                setattr(survey, field, data[field])
        survey.save()
        survey = Survey.objects.prefetch_related("questions", "access_codes").get(pk=survey.pk)
        return Response(DashboardSurveyDetailSerializer(survey).data)


class OrganizationSurveyAppendQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        survey = get_object_or_404(Survey, pk=pk, organization=organization)
        serializer = SurveyAppendQuestionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        append_survey_questions(survey, serializer.validated_data["questions"])
        survey = Survey.objects.prefetch_related("questions", "access_codes").get(pk=survey.pk)
        return Response(
            {
                "detail": "Questions added.",
                "survey": DashboardSurveyDetailSerializer(survey).data,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationMeetingCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DashboardMeetingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            code = resolve_access_code(data.get("access_code"), "meeting")
            resource_type = get_resource_type("meeting")
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        meeting = Meeting.objects.create(
            organization=organization,
            title=data["title"],
            description=data.get("description", ""),
            access_mode=data.get("access_mode", Meeting.AccessMode.PUBLIC),
            scheduled_start_at=data.get("scheduled_start_at"),
            allow_start_early=data.get("allow_start_early", False),
            is_anonymous=data.get("is_anonymous", False),
            ai_mode=data.get("ai_mode", Meeting.AIMode.NONE),
            status="scheduled",
        )
        create_meeting_slides(meeting, data["slides"])
        create_initial_session(meeting)
        access_code = AccessCode.objects.create(
            code=code,
            organization=organization,
            resource_type=resource_type,
            meeting=meeting,
            label=data.get("label") or meeting.title,
            search_description=data.get("search_description")
            or meeting.description
            or organization.name,
            is_primary=True,
            is_active=True,
        )
        return Response(
            {
                "meeting": {
                    "id": meeting.id,
                    "title": meeting.title,
                    "description": meeting.description,
                    "access_mode": meeting.access_mode,
                    "scheduled_start_at": meeting.scheduled_start_at,
                    "allow_start_early": meeting.allow_start_early,
                    "is_anonymous": meeting.is_anonymous,
                    "ai_mode": meeting.ai_mode,
                    "path": f"/m/{meeting.id}",
                },
                "access_code": {
                    "id": access_code.id,
                    "code": access_code.code,
                    "label": access_code.label,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class MeetingDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        meeting = get_object_or_404(
            Meeting.objects.select_related("organization").prefetch_related(
                "slides", "access_codes"
            ),
            pk=pk,
        )
        return Response(MeetingDetailSerializer(meeting).data)


class OrganizationMeetingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        meeting = get_object_or_404(
            Meeting.objects.prefetch_related("slides", "access_codes"),
            pk=pk,
            organization=organization,
        )
        return Response(MeetingDetailSerializer(meeting).data)

    @transaction.atomic
    def patch(self, request, slug, pk):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
        if meeting.status in ("live", "paused"):
            return Response(
                {"detail": "Cannot edit a live or paused meeting. End it first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = DashboardMeetingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        for field in (
            "title",
            "description",
            "scheduled_start_at",
            "allow_start_early",
            "is_anonymous",
            "ai_mode",
        ):
            if field in data:
                setattr(meeting, field, data[field])
        meeting.save()

        if "slides" in data:
            replace_meeting_slides(meeting, data["slides"])
            session = meeting.sessions.order_by("-session_number").first()
            if session and session.status == MeetingSession.Status.SCHEDULED:
                first_slide = meeting.slides.filter(is_active=True).order_by("order", "id").first()
                session.current_slide = first_slide
                session.started_from_slide = first_slide
                session.save(update_fields=["current_slide", "started_from_slide"])

        meeting = Meeting.objects.prefetch_related("slides", "access_codes").get(pk=meeting.pk)
        return Response(MeetingDetailSerializer(meeting).data)


def _serialize_session(session: MeetingSession) -> dict:
    stats = get_session_stats(session)
    data = MeetingSessionPublicSerializer(session).data
    data["attendance_count"] = stats["attendance_count"]
    data["current_slide_response_count"] = stats["current_slide_response_count"]
    return data


def _get_org_meeting_admin(request, slug, pk):
    try:
        organization = get_admin_organization(request.user, slug)
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )
    meeting = get_object_or_404(Meeting, pk=pk, organization=organization)
    return meeting, None


def _control_session_response(meeting, session, detail: str):
    session = MeetingSession.objects.select_related("current_slide").get(pk=session.pk)
    return Response(
        {
            "detail": detail,
            "meeting_status": meeting.status,
            "session": _serialize_session(session),
            "live": get_organizer_live_payload(meeting, session),
        }
    )


class MeetingSessionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        meeting = get_object_or_404(Meeting, pk=pk)
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found for this meeting."}, status=404)
        session = MeetingSession.objects.select_related("current_slide").get(pk=session.pk)
        return Response(_serialize_session(session))


class MeetingJoinView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, pk):
        meeting = get_object_or_404(Meeting.objects.select_related("organization"), pk=pk)
        serializer = MeetingJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        private_code = serializer.validated_data.get("private_code", "")

        join_error = meeting_join_error(meeting, request.user, private_code)
        if join_error:
            return Response({"detail": join_error}, status=status.HTTP_403_FORBIDDEN)

        session = get_latest_session(meeting)
        if not session:
            session = create_initial_session(meeting)
        if not session_is_joinable(session):
            return Response(
                {"detail": "This meeting has not started yet.", "session_status": session.status},
                status=status.HTTP_409_CONFLICT,
            )

        user = request.user if request.user.is_authenticated else None

        existing_id = serializer.validated_data.get("attendance_id")
        if existing_id:
            attendance = MeetingAttendance.objects.filter(
                session=session,
                attendance_id=existing_id,
                status=MeetingAttendance.Status.JOINED,
            ).first()
            if attendance:
                completed_slide_ids = participant_completed_slide_ids(
                    session, attendance.participant_id
                )
                payload = {
                    "attendance_id": str(attendance.attendance_id),
                    "participant_id": str(attendance.participant_id),
                    "is_anonymous": meeting.is_anonymous,
                    "session": _serialize_session(session),
                    "completed_slide_ids": completed_slide_ids,
                    "rejoined": True,
                }
                if not meeting.is_anonymous and attendance.user:
                    payload["display_name"] = attendance.user.get_username()
                return Response(payload)

        attendance = join_session(meeting, session, user=user)
        completed_slide_ids = participant_completed_slide_ids(session, attendance.participant_id)

        payload = {
            "attendance_id": str(attendance.attendance_id),
            "participant_id": str(attendance.participant_id),
            "is_anonymous": meeting.is_anonymous,
            "session": _serialize_session(session),
            "completed_slide_ids": completed_slide_ids,
        }
        if not meeting.is_anonymous and user:
            payload["display_name"] = user.get_username()
        return Response(payload, status=status.HTTP_201_CREATED)


class MeetingProfileSubmitView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, pk):
        meeting = get_object_or_404(Meeting, pk=pk)
        serializer = MeetingProfileSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = get_latest_session(meeting)
        if not session or not session_is_joinable(session):
            return Response({"detail": "Meeting is not active."}, status=409)

        try:
            attendance = get_attendance(session, str(data["attendance_id"]))
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)

        slide = get_object_or_404(MeetingSlide, pk=data["slide_id"], meeting=meeting)
        try:
            submit_participant_profile(attendance, slide, data["fields"])
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)

        return Response({"detail": "Profile saved.", "slide_id": slide.id})


class MeetingRespondView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, pk):
        meeting = get_object_or_404(Meeting, pk=pk)
        serializer = MeetingRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = get_latest_session(meeting)
        if not session or not session_is_joinable(session):
            return Response({"detail": "Meeting is not active."}, status=409)

        try:
            attendance = get_attendance(session, str(data["attendance_id"]))
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)

        slide = get_object_or_404(MeetingSlide, pk=data["slide_id"], meeting=meeting)
        issues = data.get("issues")
        try:
            if issues and slide.slide_type in (
                MeetingSlide.SlideType.ISSUE_CARD,
                MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
            ):
                responses = submit_issue_card_responses(
                    meeting,
                    session,
                    attendance,
                    slide,
                    issues,
                )
                for response in responses:
                    schedule_response_ai_processing(response)
                return Response(
                    {
                        "detail": "Issues saved.",
                        "slide_id": slide.id,
                        "response_ids": [r.id for r in responses],
                        "issue_count": len(responses),
                        "ai_processing": meeting.ai_mode != Meeting.AIMode.NONE,
                    },
                    status=status.HTTP_201_CREATED,
                )

            response = submit_slide_response(
                meeting,
                session,
                attendance,
                slide,
                raw_response=data.get("raw_response", data.get("response_text", "")),
                selected_options=data.get("selected_options", []),
            )
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)

        schedule_response_ai_processing(response)

        return Response(
            {
                "detail": "Response saved.",
                "slide_id": slide.id,
                "response_id": response.id,
                "ai_processing": meeting.ai_mode != Meeting.AIMode.NONE,
            },
            status=status.HTTP_201_CREATED,
        )


class MeetingLeaveView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        meeting = get_object_or_404(Meeting, pk=pk)
        serializer = MeetingLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No active session."}, status=404)
        try:
            attendance = get_attendance(session, str(serializer.validated_data["attendance_id"]))
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        leave_attendance(attendance)
        return Response({"detail": "You have left the meeting."})


class OrganizationMeetingStartView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        serializer = MeetingStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = get_latest_session(meeting)
        if not session:
            session = create_initial_session(meeting)

        start_error = can_start_meeting(meeting, session)
        if start_error:
            return Response({"detail": start_error}, status=400)

        from_slide = None
        slide_id = serializer.validated_data.get("slide_id")
        if slide_id:
            try:
                from_slide = get_slide_by_id(meeting, slide_id)
            except MeetingSlide.DoesNotExist:
                return Response({"detail": "Invalid slide_id."}, status=400)

        try:
            session = start_meeting_session(meeting, session, from_slide=from_slide)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        return _control_session_response(meeting, session, "Meeting started.")


class OrganizationMeetingLiveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        session = MeetingSession.objects.select_related("current_slide").get(pk=session.pk)
        return Response(get_organizer_live_payload(meeting, session))


class OrganizationMeetingAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err

        slide_id = request.query_params.get("slide_id")
        if not slide_id:
            return Response({"detail": "slide_id is required."}, status=400)

        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)

        slide = get_object_or_404(MeetingSlide, pk=slide_id, meeting=meeting)
        split_field = request.query_params.get("split_field") or None
        split_value = request.query_params.get("split_value")
        split_compare = request.query_params.get("split_compare", "").lower() in (
            "1",
            "true",
            "yes",
        )
        include_individual = request.query_params.get(
            "include_individual", ""
        ).lower() in ("1", "true", "yes")
        if include_individual and settings.APP_ENV != "local":
            include_individual = False
        limit = request.query_params.get("limit", "10")
        try:
            limit_n = max(1, min(25, int(limit)))
        except ValueError:
            limit_n = 10

        use_compare = split_field and (
            split_compare
            or split_value is None
            or str(split_value).strip() == ""
        )
        if use_compare:
            payload = get_slide_analytics_compare(
                meeting,
                session,
                slide,
                split_field=split_field,
                limit=limit_n,
                include_individual=include_individual,
            )
        else:
            if split_field and split_value is None:
                split_value = ""
            payload = get_slide_analytics(
                meeting,
                session,
                slide,
                split_field=split_field,
                split_value=split_value,
                limit=limit_n,
                include_individual=include_individual,
            )
        if payload.get("error"):
            return Response({"detail": payload["error"]}, status=400)
        return Response(payload)


class OrganizationMeetingPoliticalClassifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err

        slide_id = request.query_params.get("slide_id") or request.data.get("slide_id")
        if not slide_id:
            return Response({"detail": "slide_id is required."}, status=400)

        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)

        slide = get_object_or_404(MeetingSlide, pk=slide_id, meeting=meeting)
        if slide.slide_type != MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
            return Response(
                {"detail": "Classification is only available for political issue cards."},
                status=400,
            )

        force = request.query_params.get("force", "").lower() in ("1", "true", "yes")
        if not force:
            force = bool(request.data.get("force"))

        outcome = classify_political_slide_responses(session, slide, force=force)
        status_code = 200 if outcome.get("status") != "error" else 500
        return Response(outcome, status=status_code)


class OrganizationMeetingPauseView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        try:
            session = pause_meeting_session(meeting, session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return _control_session_response(meeting, session, "Meeting paused.")


class OrganizationMeetingResumeView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        try:
            session = resume_meeting_session(meeting, session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return _control_session_response(meeting, session, "Meeting resumed.")


class OrganizationMeetingEndView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        try:
            session = end_meeting_session(meeting, session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if meeting.ai_mode != Meeting.AIMode.NONE:
            session_id = session.id
            transaction.on_commit(
                lambda: process_meeting_ai(meeting, str(session_id))
            )
        return _control_session_response(meeting, session, "Meeting ended.")


class OrganizationMeetingNextSlideView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        try:
            session = go_to_next_slide(meeting, session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return _control_session_response(meeting, session, "Advanced to next slide.")


class OrganizationMeetingPrevSlideView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        try:
            session = go_to_previous_slide(meeting, session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return _control_session_response(meeting, session, "Moved to previous slide.")


class OrganizationMeetingGoToSlideView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        serializer = MeetingGoToSlideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = get_latest_session(meeting)
        if not session:
            return Response({"detail": "No session found."}, status=404)
        try:
            slide = get_slide_by_id(meeting, serializer.validated_data["slide_id"])
            session = go_to_slide(meeting, session, slide)
        except MeetingSlide.DoesNotExist:
            return Response({"detail": "Invalid slide_id."}, status=400)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return _control_session_response(meeting, session, "Slide updated.")


class OrganizationMeetingRestartView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        serializer = MeetingRestartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = get_latest_session(meeting)
        if not session:
            session = create_initial_session(meeting)

        from_slide = None
        slide_id = serializer.validated_data.get("slide_id")
        if slide_id:
            try:
                from_slide = get_slide_by_id(meeting, slide_id)
            except MeetingSlide.DoesNotExist:
                return Response({"detail": "Invalid slide_id."}, status=400)

        try:
            session = restart_meeting_session(meeting, session, from_slide=from_slide)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return _control_session_response(meeting, session, "Meeting restarted.")


class OrganizationMeetingAddSlidesView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err
        session = get_latest_session(meeting)
        serializer = MeetingAddSlidesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slide_payloads = serializer.validated_data["slides"]
        append_meeting_slides(meeting, slide_payloads)

        if session and session.status in (
            MeetingSession.Status.LIVE,
            MeetingSession.Status.PAUSED,
        ):
            session = MeetingSession.objects.select_related("current_slide").get(pk=session.pk)
            return _control_session_response(meeting, session, "Slides added.")

        if session and session.status == MeetingSession.Status.SCHEDULED:
            first_slide = meeting.slides.filter(is_active=True).order_by("order", "id").first()
            if first_slide and not session.current_slide_id:
                session.current_slide = first_slide
                session.started_from_slide = first_slide
                session.save(update_fields=["current_slide", "started_from_slide"])

        meeting = Meeting.objects.prefetch_related("slides", "access_codes").get(pk=meeting.pk)
        return Response(
            {
                "detail": "Slides added.",
                "meeting": MeetingDetailSerializer(meeting).data,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationMeetingExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err

        export_type = request.query_params.get("type", "responses").lower()
        fmt = request.query_params.get("format", "json").lower()
        session_id = request.query_params.get("session_id", "all")

        if export_type == "summary":
            return Response(meeting_export_summary(meeting))

        if export_type == "profiles":
            rows = build_profile_export(meeting, session_id)
            columns = PROFILE_EXPORT_COLUMNS
            basename = f"meeting-{meeting.id}-profiles"
        else:
            rows = build_meeting_df(meeting, session_id)
            columns = MEETING_DF_COLUMNS
            basename = f"meeting-{meeting.id}-responses"

        if fmt == "csv":
            suffix = session_id if session_id != "all" else "all-sessions"
            filename = f"{basename}-session-{suffix}.csv"
            return csv_http_response(filename, render_csv(rows, columns))

        return Response(
            {
                "meeting_id": meeting.id,
                "meeting_title": meeting.title,
                "is_anonymous": meeting.is_anonymous,
                "session_id": session_id,
                "row_count": len(rows),
                "columns": columns,
                "rows": rows,
            }
        )


class OrganizationMeetingProcessAIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        meeting, err = _get_org_meeting_admin(request, slug, pk)
        if err:
            return err

        if meeting.ai_mode == Meeting.AIMode.NONE:
            return Response(
                {"detail": "AI mode is disabled for this meeting."},
                status=400,
            )

        session_id = request.data.get("session_id") or request.query_params.get("session_id", "all")
        outcome = process_meeting_ai(meeting, str(session_id))
        return Response(
            {
                "detail": "AI processing complete.",
                "ai_mode": meeting.ai_mode,
                **outcome,
            }
        )


class ContactSubmitView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ContactSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        name = data["name"].strip()
        email = data["email"].strip()
        subject = data["subject"].strip()
        message = data["message"].strip()
        ContactSubmission.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message,
        )
        try:
            send_contact_notification(
                name=name,
                email=email,
                subject=subject,
                message=message,
            )
        except Exception:
            if settings.DEBUG:
                pass
            else:
                return Response(
                    {"detail": "Your message was saved but email could not be sent. Please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        return Response(
            {"detail": "Thank you — your message has been sent."},
            status=status.HTTP_201_CREATED,
        )