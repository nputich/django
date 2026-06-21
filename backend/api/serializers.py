from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (
    AccessCode,
    Meeting,
    Note,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    BoardPost,
    Survey,
    SurveyQuestion,
    SurveyAnswer,
)
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "password"]
        extra_kwargs = {"password": {"write_only": True}}
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title", "content", "created_at", "author"]
        extra_kwargs = {"author": {"read_only": True}}
class SurveyQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestion
        fields = ["id", "order", "text", "question_type", "choices"]
class SurveyDetailSerializer(serializers.ModelSerializer):
    questions = SurveyQuestionSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    class Meta:
        model = Survey
        fields = [
            "id",
            "title",
            "description",
            "organization_name",
            "is_anonymous",
            "questions",
        ]
class SurveyAnswerInputSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    value = serializers.CharField()
class SurveySubmitSerializer(serializers.Serializer):
    response_session = serializers.CharField(max_length=64)
    answers = SurveyAnswerInputSerializer(many=True)
class OrganizationHubSurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ["id", "title", "description"]
class OrganizationHubMeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = []
class OrganizationHubSerializer(serializers.ModelSerializer):
    surveys = serializers.SerializerMethodField()
    meetings = serializers.SerializerMethodField()
    has_board = serializers.SerializerMethodField()
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "surveys",
            "meetings",
            "has_board",
        ]
    def get_surveys(self, obj):
        qs = obj.surveys.filter(is_active=True)
        return OrganizationHubSurveySerializer(qs, many=True).data
    def get_meetings(self, obj):
        from .models import Meeting
        qs = Meeting.objects.filter(organization=obj, status__in=["scheduled", "live"])
        return [
            {
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "access_mode": m.access_mode,
            }
            for m in qs
        ]
    def get_has_board(self, obj):
        return hasattr(obj, "board")


class MyOrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "description", "is_verified", "role"]

    def get_role(self, obj):
        user = self.context["request"].user
        membership = OrganizationMembership.objects.filter(
            organization=obj, user=user
        ).first()
        return membership.role if membership else None


class DashboardAccessCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessCode
        fields = ["id", "code", "label", "is_active", "is_primary"]


class DashboardSurveySerializer(serializers.ModelSerializer):
    access_codes = DashboardAccessCodeSerializer(many=True, read_only=True)

    class Meta:
        model = Survey
        fields = [
            "id",
            "title",
            "description",
            "is_active",
            "is_anonymous",
            "created_at",
            "access_codes",
        ]


class DashboardMeetingSerializer(serializers.ModelSerializer):
    access_codes = DashboardAccessCodeSerializer(many=True, read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "access_mode",
            "status",
            "created_at",
            "access_codes",
        ]


class OrganizationDashboardSerializer(serializers.ModelSerializer):
    surveys = DashboardSurveySerializer(many=True, read_only=True)
    meetings = DashboardMeetingSerializer(many=True, read_only=True)

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "description", "is_verified", "surveys", "meetings"]


class SurveyQuestionCreateSerializer(serializers.Serializer):
    order = serializers.IntegerField(min_value=0, default=0)
    text = serializers.CharField()
    question_type = serializers.ChoiceField(
        choices=SurveyQuestion.QuestionType.choices,
        default=SurveyQuestion.QuestionType.TEXT,
    )
    choices = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )


class DashboardSurveyCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_anonymous = serializers.BooleanField(default=True)
    access_code = serializers.CharField(
        required=False, allow_blank=True, max_length=32
    )
    label = serializers.CharField(required=False, allow_blank=True, max_length=200)
    search_description = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
    questions = SurveyQuestionCreateSerializer(many=True, min_length=1)


class DashboardMeetingCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    access_mode = serializers.ChoiceField(
        choices=Meeting.AccessMode.choices,
        default=Meeting.AccessMode.PUBLIC,
    )
    access_code = serializers.CharField(
        required=False, allow_blank=True, max_length=32
    )
    label = serializers.CharField(required=False, allow_blank=True, max_length=200)
    search_description = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )


class ContactSubmissionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=254)
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField(max_length=2000)