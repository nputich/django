from django.contrib.auth.models import User
from rest_framework import serializers
from .board_service import can_delete_org_post, can_delete_org_reply
from .models import (
    AccessCode,
    BoardPost,
    BoardPostReply,
    Meeting,
    MeetingSession,
    MeetingSlide,
    Note,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    PersonalBoardPost,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    UserProfile,
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
        qs = Meeting.objects.filter(
            organization=obj, status__in=["scheduled", "live", "paused"]
        ).order_by("scheduled_start_at", "-created_at")
        return [
            {
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "access_mode": m.access_mode,
                "status": m.status,
                "scheduled_start_at": m.scheduled_start_at,
                "is_anonymous": m.is_anonymous,
            }
            for m in qs
        ]
    def get_has_board(self, obj):
        return hasattr(obj, "board")


class MyOrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_verified",
            "role",
            "status",
        ]

    def get_role(self, obj):
        user = self.context["request"].user
        membership = OrganizationMembership.objects.filter(
            organization=obj, user=user
        ).first()
        return membership.role if membership else None


class CreateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=5000, required=False, allow_blank=True, default=""
    )

    def validate_name(self, value):
        name = (value or "").strip()
        if len(name) < 2:
            raise serializers.ValidationError("Enter an organization name.")
        return name


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


class DashboardSurveyDetailSerializer(serializers.ModelSerializer):
    questions = SurveyQuestionSerializer(many=True, read_only=True)
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
            "questions",
            "access_codes",
        ]


class MeetingSlideSerializer(serializers.ModelSerializer):
    participant_fields = serializers.SerializerMethodField()

    class Meta:
        model = MeetingSlide
        fields = [
            "id",
            "order",
            "slide_type",
            "title",
            "prompt",
            "question_format",
            "choices",
            "config",
            "participant_fields",
            "is_active",
        ]

    def get_participant_fields(self, obj):
        if obj.slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO:
            return obj.config.get("fields", [])
        return []


class MeetingDetailSerializer(serializers.ModelSerializer):
    slides = MeetingSlideSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)
    community_code = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "organization_name",
            "organization_slug",
            "access_mode",
            "status",
            "scheduled_start_at",
            "allow_start_early",
            "is_anonymous",
            "ai_mode",
            "community_code",
            "slides",
        ]

    def get_community_code(self, obj):
        code = obj.access_codes.filter(is_active=True, is_primary=True).first()
        if not code:
            code = obj.access_codes.filter(is_active=True).first()
        return code.code if code else None


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
            "scheduled_start_at",
            "allow_start_early",
            "is_anonymous",
            "ai_mode",
            "created_at",
            "access_codes",
        ]


class OrganizationDashboardSerializer(serializers.ModelSerializer):
    surveys = DashboardSurveySerializer(many=True, read_only=True)
    meetings = DashboardMeetingSerializer(many=True, read_only=True)
    board = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    lifecycle = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_verified",
            "status",
            "surveys",
            "meetings",
            "board",
            "capabilities",
            "lifecycle",
        ]

    def get_board(self, obj):
        if not hasattr(obj, "board"):
            return None
        return OrganizationBoardPublicSerializer(obj.board).data

    def get_capabilities(self, obj):
        from .feature_entitlements import get_organization_capabilities

        return get_organization_capabilities(obj)

    def get_lifecycle(self, obj):
        from .organization_lifecycle import serialize_lifecycle

        return serialize_lifecycle(obj)


def _profile_picture_url(profile, request):
    if not profile or not profile.profile_picture:
        return None
    if request:
        return request.build_absolute_uri(profile.profile_picture.url)
    return profile.profile_picture.url


def serialize_post_author(user, request):
    profile = getattr(user, "profile", None)
    if profile is None:
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": profile.display_name if profile else "",
        "profile_picture_url": _profile_picture_url(profile, request),
    }


def build_me_payload(user, request):
    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)
    except Exception:
        # Fail soft if profile tables are mid-migration or unavailable.
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": "",
            "city": "",
            "state": "",
            "phone": "",
            "contact_email": "",
            "profile_picture_url": None,
            "extra_data": {},
            "profile_complete": bool(user.username),
            "required_fields": ["display_name", "username"],
        }
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": profile.display_name,
        "city": profile.city,
        "state": profile.state,
        "phone": profile.phone,
        "contact_email": profile.contact_email,
        "profile_picture_url": _profile_picture_url(profile, request),
        "extra_data": profile.extra_data,
        "profile_complete": profile.is_complete,
        "required_fields": ["display_name", "username"],
    }


class UserProfileUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    display_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    contact_email = serializers.CharField(max_length=254, required=False, allow_blank=True)
    profile_picture = serializers.ImageField(required=False)
    clear_profile_picture = serializers.BooleanField(required=False, default=False)

    def validate_contact_email(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        return serializers.EmailField().run_validation(value)

    def validate_username(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Username is required.")
        return value


class BoardPostCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    body = serializers.CharField()


class BoardPostReplyCreateSerializer(serializers.Serializer):
    body = serializers.CharField()


class BoardPostReplySerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = BoardPostReply
        fields = ["id", "body", "author", "can_delete", "created_at", "updated_at"]

    def get_author(self, obj):
        return serialize_post_author(obj.author, self.context.get("request"))

    def get_can_delete(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        return can_delete_org_reply(obj, user)


class BoardPostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    replies = BoardPostReplySerializer(many=True, read_only=True)
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = BoardPost
        fields = [
            "id",
            "title",
            "body",
            "author",
            "can_delete",
            "created_at",
            "updated_at",
            "replies",
        ]

    def get_author(self, obj):
        return serialize_post_author(obj.author, self.context.get("request"))

    def get_can_delete(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        return can_delete_org_post(obj, user)


class PersonalBoardPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalBoardPost
        fields = ["id", "title", "body", "created_at", "updated_at"]


class OrganizationBoardPublicSerializer(serializers.ModelSerializer):
    posting_mode_label = serializers.CharField(
        source="get_posting_mode_display", read_only=True
    )

    class Meta:
        model = OrganizationBoard
        fields = ["id", "title", "posting_mode", "posting_mode_label"]


class OrganizationBoardSettingsSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    posting_mode = serializers.ChoiceField(
        choices=OrganizationBoard.PostingMode.choices, required=False
    )


class InboxComposeSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    body = serializers.CharField()
    to_username = serializers.CharField(required=False, allow_blank=True)
    to_organization_slug = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        username = (attrs.get("to_username") or "").strip()
        org_slug = (attrs.get("to_organization_slug") or "").strip()
        attrs["to_username"] = username or None
        attrs["to_organization_slug"] = org_slug or None
        if bool(attrs["to_username"]) == bool(attrs["to_organization_slug"]):
            raise serializers.ValidationError(
                "Provide exactly one of to_username or to_organization_slug."
            )
        if not (attrs.get("body") or "").strip():
            raise serializers.ValidationError({"body": "Message body is required."})
        return attrs


class InboxDraftSaveSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)
    to_username = serializers.CharField(required=False, allow_blank=True)
    to_organization_slug = serializers.CharField(required=False, allow_blank=True)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if "to_username" in attrs:
            attrs["to_username"] = (attrs.get("to_username") or "").strip() or None
        if "to_organization_slug" in attrs:
            attrs["to_organization_slug"] = (
                attrs.get("to_organization_slug") or ""
            ).strip() or None
        username = attrs.get("to_username")
        org_slug = attrs.get("to_organization_slug")
        if username is not None or org_slug is not None:
            if bool(username) == bool(org_slug):
                raise serializers.ValidationError(
                    "Provide exactly one of to_username or to_organization_slug."
                )
        return attrs


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


class DashboardSurveyUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_anonymous = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class SurveyAppendQuestionsSerializer(serializers.Serializer):
    questions = SurveyQuestionCreateSerializer(many=True, min_length=1)


class ParticipantInfoFieldCreateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    label = serializers.CharField(max_length=200)
    required = serializers.BooleanField(default=False)
    field_type = serializers.ChoiceField(
        choices=["text", "single_select", "multi_select"]
    )
    options = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )


class MeetingSlideCreateSerializer(serializers.Serializer):
    order = serializers.IntegerField(min_value=0, default=0)
    slide_type = serializers.ChoiceField(choices=MeetingSlide.SlideType.choices)
    title = serializers.CharField(required=False, allow_blank=True, max_length=300)
    prompt = serializers.CharField(required=False, allow_blank=True)
    question_format = serializers.ChoiceField(
        choices=MeetingSlide.QuestionFormat.choices,
        required=False,
        allow_blank=True,
    )
    choices = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    fields = ParticipantInfoFieldCreateSerializer(many=True, required=False, default=list)

    def validate(self, attrs):
        slide_type = attrs["slide_type"]
        prompt = attrs.get("prompt", "").strip()
        title = attrs.get("title", "").strip()
        question_format = attrs.get("question_format", "")
        choices = attrs.get("choices") or []
        fields = attrs.get("fields") or []

        if slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO:
            if not fields:
                raise serializers.ValidationError(
                    {"fields": "Participant info slides need at least one field."}
                )
            keys = [f["key"] for f in fields]
            if len(keys) != len(set(keys)):
                raise serializers.ValidationError(
                    {"fields": "Field keys must be unique within the slide."}
                )
            for field in fields:
                if field["field_type"] in ("single_select", "multi_select") and not field.get("options"):
                    raise serializers.ValidationError(
                        {"fields": f"Select field '{field['key']}' needs options."}
                    )
        elif slide_type == MeetingSlide.SlideType.STANDARD:
            if not prompt and not title:
                raise serializers.ValidationError(
                    {"prompt": "Standard slides need a prompt or title."}
                )
            if not question_format:
                raise serializers.ValidationError(
                    {"question_format": "Standard slides require a question format."}
                )
            if question_format in (
                MeetingSlide.QuestionFormat.SINGLE_CHOICE,
                MeetingSlide.QuestionFormat.MULTI_CHOICE,
            ) and len(choices) < 2:
                raise serializers.ValidationError(
                    {"choices": "Choice questions need at least two options."}
                )
        elif slide_type in (
            MeetingSlide.SlideType.ISSUE_CARD,
            MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
        ):
            if not prompt and not title:
                raise serializers.ValidationError(
                    {"prompt": "Issue card slides need a prompt or title."}
                )
        return attrs


class DashboardMeetingCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    access_mode = serializers.ChoiceField(
        choices=Meeting.AccessMode.choices,
        default=Meeting.AccessMode.PUBLIC,
    )
    scheduled_start_at = serializers.DateTimeField(required=False, allow_null=True)
    allow_start_early = serializers.BooleanField(default=False)
    is_anonymous = serializers.BooleanField(default=False)
    ai_mode = serializers.ChoiceField(
        choices=Meeting.AIMode.choices,
        default=Meeting.AIMode.NONE,
    )
    access_code = serializers.CharField(
        required=False, allow_blank=True, max_length=32
    )
    label = serializers.CharField(required=False, allow_blank=True, max_length=200)
    search_description = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
    slides = MeetingSlideCreateSerializer(many=True, min_length=1)


class DashboardMeetingUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    scheduled_start_at = serializers.DateTimeField(required=False, allow_null=True)
    allow_start_early = serializers.BooleanField(required=False)
    is_anonymous = serializers.BooleanField(required=False)
    ai_mode = serializers.ChoiceField(choices=Meeting.AIMode.choices, required=False)
    slides = MeetingSlideCreateSerializer(many=True, required=False)


class MeetingSessionPublicSerializer(serializers.ModelSerializer):
    current_slide = MeetingSlideSerializer(read_only=True)
    attendance_count = serializers.IntegerField(read_only=True)
    current_slide_response_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MeetingSession
        fields = [
            "id",
            "session_number",
            "status",
            "current_slide",
            "started_at",
            "attendance_count",
            "current_slide_response_count",
        ]


class MeetingJoinSerializer(serializers.Serializer):
    private_code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    attendance_id = serializers.UUIDField(required=False)


class MeetingProfileSubmitSerializer(serializers.Serializer):
    attendance_id = serializers.UUIDField()
    slide_id = serializers.IntegerField()
    fields = serializers.DictField()


class MeetingRespondSerializer(serializers.Serializer):
    attendance_id = serializers.UUIDField()
    slide_id = serializers.IntegerField()
    raw_response = serializers.CharField(required=False, allow_blank=True, default="")
    selected_options = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    issues = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=False,
    )

    def validate_issues(self, value):
        if not value:
            return value
        cleaned = []
        for item in value:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            order = item.get("importance_order")
            payload = {"text": text}
            if order is not None:
                try:
                    payload["importance_order"] = int(order)
                except (TypeError, ValueError) as exc:
                    raise serializers.ValidationError(
                        "importance_order must be a positive integer."
                    ) from exc
                if payload["importance_order"] < 1:
                    raise serializers.ValidationError(
                        "importance_order must be at least 1."
                    )
            cleaned.append(payload)
        if not cleaned:
            raise serializers.ValidationError("Each issue must include non-empty text.")
        return cleaned


class MeetingLeaveSerializer(serializers.Serializer):
    attendance_id = serializers.UUIDField()


class MeetingStartSerializer(serializers.Serializer):
    slide_id = serializers.IntegerField(required=False)


class MeetingGoToSlideSerializer(serializers.Serializer):
    slide_id = serializers.IntegerField()


class MeetingRestartSerializer(serializers.Serializer):
    slide_id = serializers.IntegerField(required=False)


class MeetingAddSlidesSerializer(serializers.Serializer):
    slides = MeetingSlideCreateSerializer(many=True, min_length=1)


class ContactSubmissionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=254)
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField(max_length=2000)