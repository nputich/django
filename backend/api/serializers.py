from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (
    Note,
    Survey,
    SurveyQuestion,
    SurveyAnswer,
    Organization,
    OrganizationBoard,
    BoardPost,
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