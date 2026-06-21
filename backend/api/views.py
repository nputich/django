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
from .models import AccessCode, ContactSubmission, Meeting, Note, Organization, Survey, SurveyAnswer, SurveyQuestion
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
    DashboardSurveyCreateSerializer,
    MyOrganizationSerializer,
    NoteSerializer,
    OrganizationDashboardSerializer,
    OrganizationHubSerializer,
    SurveyDetailSerializer,
    SurveySubmitSerializer,
    UserSerializer,
)
class NoteListCreate(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Note.objects.filter(author=self.request.user)
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
class NoteDelete(generics.DestroyAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Note.objects.filter(author=self.request.user)
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
            status="scheduled",
        )
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