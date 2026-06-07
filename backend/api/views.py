from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import AccessCode, Organization, Survey, SurveyAnswer, SurveyQuestion
from .serializers import (
    NoteSerializer,
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
    def get(self, request, query):
        q = query.strip()
        if not q:
            return Response(
                {"detail": "Enter a code.", "results": []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        codes = (
            AccessCode.objects.filter(code__iexact=q, is_active=True)
            .select_related(
                "organization",
                "resource_type",
                "survey",
                "meeting",
            )
            .order_by("sort_order", "id")
        )
        now = timezone.now()
        results = []
        for access_code in codes:
            if access_code.expires_at and access_code.expires_at < now:
                continue
            item = build_access_code_result(access_code)
            if item:
                results.append(item)
        results.sort(
            key=lambda r: (
                not r["is_primary"],
                not r["is_verified"],
                r["sort_order"],
                r["label"].lower(),
            )
        )
        if not results:
            return Response(
                {"detail": "No results.", "query": q, "match_count": 0, "results": []},
                status=status.HTTP_404_NOT_FOUND,
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