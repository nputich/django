from django.contrib.auth.models import User
from rest_framework import serializers
from .board_service import (
    can_delete_org_post,
    can_delete_org_reply,
    can_delete_personal_post,
)
from .models import (
    AccessCode,
    BoardPost,
    BoardPostReply,
    Meeting,
    MeetingSession,
    MeetingSlide,
    MeetingSummary,
    Note,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    PersonalBoardPost,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    UserProfile,
    WallPostType,
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
    content = serializers.SerializerMethodField()

    class Meta:
        model = SurveyQuestion
        fields = [
            "id",
            "order",
            "text",
            "question_type",
            "choices",
            "is_demographic",
            "config",
            "content",
        ]

    def get_content(self, obj):
        if obj.question_type != SurveyQuestion.QuestionType.CONTENT:
            return None
        from api.content_media import normalize_content_config

        return normalize_content_config(obj.config)


class SurveyQuestionAdminSerializer(SurveyQuestionSerializer):
    """Dashboard view of a question: includes reporting tags."""

    tags = serializers.SerializerMethodField()
    tag_ids = serializers.SerializerMethodField()

    class Meta(SurveyQuestionSerializer.Meta):
        fields = SurveyQuestionSerializer.Meta.fields + ["tags", "tag_ids"]

    def _tags(self, obj):
        if obj.question_type == SurveyQuestion.QuestionType.CONTENT:
            return []
        cache = self.context.setdefault("_sq_tags", {})
        if obj.id not in cache:
            from api.question_tags import tags_for_survey_question

            cache[obj.id] = tags_for_survey_question(obj)
        return cache[obj.id]

    def get_tags(self, obj):
        from api.question_tags import serialize_tag

        return [serialize_tag(t) for t in self._tags(obj)]

    def get_tag_ids(self, obj):
        return [t.id for t in self._tags(obj)]


class SurveyDetailSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    disclosure = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = [
            "id",
            "title",
            "description",
            "organization_name",
            "is_anonymous",
            "aggregate_sharing_notice",
            "disclosure",
            "questions",
        ]

    def get_disclosure(self, obj):
        from api.content_media import survey_disclosure_payload

        return survey_disclosure_payload(obj)

    def get_questions(self, obj):
        from api.content_media import ordered_survey_questions

        qs = list(obj.questions.all())
        return SurveyQuestionSerializer(ordered_survey_questions(qs), many=True).data
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
    board = serializers.SerializerMethodField()
    relationships = serializers.SerializerMethodField()

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
            "board",
            "relationships",
        ]

    def get_surveys(self, obj):
        qs = obj.surveys.filter(is_active=True)
        return OrganizationHubSurveySerializer(qs, many=True).data

    def get_relationships(self, obj):
        from api.relationship_service import public_relationships_payload

        return public_relationships_payload(obj)

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

    def get_board(self, obj):
        from api.board_service import can_view_org_board, get_org_board

        if not hasattr(obj, "board"):
            return None
        board = get_org_board(obj)
        request = self.context.get("request")
        user = request.user if request else None
        if not can_view_org_board(board, user):
            return {
                "title": board.title or obj.name,
                "hub_preview_count": board.hub_preview_count,
                "can_view": False,
                "posts": [],
            }
        limit = max(0, min(int(board.hub_preview_count or 0), 25))
        posts_qs = (
            board.posts.select_related("author__profile", "meeting__organization")
            .prefetch_related(
                "replies__author__profile",
                "poll_options",
                "poll_votes",
                "meeting__summaries",
                "meeting__expected_attendances",
            )
            .all()[:limit]
            if limit
            else board.posts.none()
        )
        return {
            "title": (board.title or "").strip() or obj.name,
            "hub_preview_count": board.hub_preview_count,
            "can_view": True,
            "posts": BoardPostSerializer(
                posts_qs, many=True, context=self.context
            ).data,
        }


class MyOrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    community_code = serializers.SerializerMethodField()
    directory_placement = serializers.SerializerMethodField()

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
            "community_code",
            "directory_placement",
        ]

    def get_role(self, obj):
        user = self.context["request"].user
        membership = OrganizationMembership.objects.filter(
            organization=obj, user=user
        ).first()
        return membership.role if membership else None

    def get_community_code(self, obj):
        from .org_access import get_primary_community_code

        row = get_primary_community_code(obj)
        return row.code if row else None

    def get_directory_placement(self, obj):
        from .directory_placement import serialize_directory_placement

        return serialize_directory_placement(obj)


class CreateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=5000, required=False, allow_blank=True, default=""
    )
    community_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    geographic_scope = serializers.ChoiceField(
        choices=[
            ("international", "International"),
            ("national", "National"),
            ("state_province", "State / Province"),
            ("local", "Local"),
        ],
        required=True,
    )
    country_id = serializers.IntegerField(required=False, allow_null=True)
    state_id = serializers.IntegerField(required=False, allow_null=True)
    county_id = serializers.IntegerField(required=False, allow_null=True)
    primary_subcategory_id = serializers.IntegerField(required=True)

    def validate_name(self, value):
        name = (value or "").strip()
        if len(name) < 2:
            raise serializers.ValidationError("Enter an organization name.")
        return name

    def validate_community_code(self, value):
        return (value or "").strip()


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
    questions = serializers.SerializerMethodField()
    access_codes = DashboardAccessCodeSerializer(many=True, read_only=True)
    disclosure = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = [
            "id",
            "title",
            "description",
            "is_active",
            "is_anonymous",
            "aggregate_sharing_notice",
            "disclosure",
            "created_at",
            "questions",
            "access_codes",
        ]

    def get_disclosure(self, obj):
        from api.content_media import survey_disclosure_payload

        return survey_disclosure_payload(obj)

    def get_questions(self, obj):
        from api.content_media import ordered_survey_questions

        qs = list(obj.questions.all())
        return SurveyQuestionAdminSerializer(
            ordered_survey_questions(qs), many=True, context=self.context
        ).data


class MeetingSlideSerializer(serializers.ModelSerializer):
    participant_fields = serializers.SerializerMethodField()
    disclosure = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    tag_ids = serializers.SerializerMethodField()
    added_live = serializers.SerializerMethodField()

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
            "disclosure",
            "content",
            "tags",
            "tag_ids",
            "added_live",
            "is_active",
        ]

    def get_participant_fields(self, obj):
        if obj.slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO:
            return obj.config.get("fields", [])
        return []

    def get_disclosure(self, obj):
        if obj.slide_type != MeetingSlide.SlideType.PARTICIPANT_INFO:
            return None
        from api.meeting_sharing import disclosure_payload

        return disclosure_payload(obj.meeting)

    def get_content(self, obj):
        if obj.slide_type != MeetingSlide.SlideType.CONTENT:
            return None
        from api.content_media import normalize_content_config

        return normalize_content_config(obj.config)

    def _tags(self, obj):
        if not obj.is_question:
            return []
        cache = self.context.setdefault("_slide_tags", {})
        if obj.id not in cache:
            from api.question_tags import tags_for_slide

            cache[obj.id] = tags_for_slide(obj)
        return cache[obj.id]

    def get_tags(self, obj):
        from api.question_tags import serialize_tag

        return [serialize_tag(t) for t in self._tags(obj)]

    def get_tag_ids(self, obj):
        return [t.id for t in self._tags(obj)]

    def get_added_live(self, obj):
        return bool((obj.config or {}).get("added_live"))


class MeetingDetailSerializer(serializers.ModelSerializer):
    slides = MeetingSlideSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)
    community_code = serializers.SerializerMethodField()
    wall = serializers.SerializerMethodField()
    published_summary = serializers.SerializerMethodField()
    can_create_summary = serializers.SerializerMethodField()
    can_view_results = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "location",
            "organization_name",
            "organization_slug",
            "access_mode",
            "status",
            "scheduled_start_at",
            "scheduled_end_at",
            "allow_start_early",
            "is_anonymous",
            "allow_self_paced",
            "ai_mode",
            "results_visible_to_community",
            "minutes_creator",
            "aggregate_sharing_notice",
            "community_code",
            "slides",
            "wall",
            "published_summary",
            "can_create_summary",
            "can_view_results",
            "started_at",
            "ended_at",
        ]

    def get_community_code(self, obj):
        code = obj.access_codes.filter(is_active=True, is_primary=True).first()
        if not code:
            code = obj.access_codes.filter(is_active=True).first()
        return code.code if code else None

    def _user(self):
        request = self.context.get("request")
        return request.user if request else None

    def get_wall(self, obj):
        from api.meeting_wall import serialize_meeting_wall_card

        return serialize_meeting_wall_card(obj, self._user())

    def get_published_summary(self, obj):
        from api.meeting_wall import published_summary

        row = published_summary(obj)
        if not row:
            return None
        return {
            "id": row.id,
            "body": row.body,
            "published_at": row.published_at,
            "updated_at": row.updated_at,
        }

    def get_can_create_summary(self, obj):
        from api.meeting_wall import can_create_meeting_minutes, published_summary

        if published_summary(obj):
            return False
        return can_create_meeting_minutes(obj, self._user())

    def get_can_view_results(self, obj):
        from api.meeting_wall import can_view_meeting_results

        return can_view_meeting_results(obj, self._user())


class DashboardMeetingSerializer(serializers.ModelSerializer):
    access_codes = DashboardAccessCodeSerializer(many=True, read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "location",
            "access_mode",
            "status",
            "scheduled_start_at",
            "scheduled_end_at",
            "allow_start_early",
            "is_anonymous",
            "ai_mode",
            "results_visible_to_community",
            "minutes_creator",
            "created_at",
            "access_codes",
        ]


class OrganizationDashboardSerializer(serializers.ModelSerializer):
    surveys = DashboardSurveySerializer(many=True, read_only=True)
    meetings = DashboardMeetingSerializer(many=True, read_only=True)
    board = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()
    lifecycle = serializers.SerializerMethodField()
    community_code = serializers.SerializerMethodField()
    directory_placement = serializers.SerializerMethodField()

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
            "usage",
            "lifecycle",
            "community_code",
            "directory_placement",
        ]

    def get_board(self, obj):
        if not hasattr(obj, "board"):
            return None
        return OrganizationBoardPublicSerializer(obj.board).data

    def get_capabilities(self, obj):
        from .feature_entitlements import get_organization_capabilities

        return get_organization_capabilities(obj)

    def get_usage(self, obj):
        from .usage_service import serialize_usage

        return serialize_usage(obj)

    def get_lifecycle(self, obj):
        from .organization_lifecycle import serialize_lifecycle

        return serialize_lifecycle(obj)

    def get_community_code(self, obj):
        from .org_access import get_primary_community_code

        row = get_primary_community_code(obj)
        return row.code if row else None

    def get_directory_placement(self, obj):
        from .directory_placement import serialize_directory_placement

        return serialize_directory_placement(obj)


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
    post_type = serializers.ChoiceField(
        choices=WallPostType.choices, required=False, default=WallPostType.POST
    )
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)
    poll_options = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=True),
        required=False,
        allow_empty=True,
    )
    event_starts_at = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    event_ends_at = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    event_location = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    attachment = serializers.FileField(required=False, allow_null=True)


class BoardPostReplyCreateSerializer(serializers.Serializer):
    body = serializers.CharField()


class BoardPollVoteSerializer(serializers.Serializer):
    option_id = serializers.IntegerField()


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
    poll = serializers.SerializerMethodField()
    type_label = serializers.SerializerMethodField()
    meeting = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()

    class Meta:
        model = BoardPost
        fields = [
            "id",
            "post_type",
            "type_label",
            "title",
            "body",
            "event_starts_at",
            "event_ends_at",
            "event_location",
            "poll",
            "meeting",
            "attachment",
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

    def get_poll(self, obj):
        from api.wall_service import serialize_org_poll

        request = self.context.get("request")
        user = request.user if request else None
        return serialize_org_poll(obj, user)

    def get_meeting(self, obj):
        if obj.post_type != WallPostType.MEETING or not obj.meeting_id:
            return None
        from api.meeting_wall import serialize_meeting_wall_card

        request = self.context.get("request")
        user = request.user if request else None
        return serialize_meeting_wall_card(obj.meeting, user)

    def get_attachment(self, obj):
        from api.board_attachments import serialize_attachment

        return serialize_attachment(obj, self.context.get("request"))

    def get_type_label(self, obj):
        return {
            WallPostType.POST: "",
            WallPostType.QUESTION: "QUESTION",
            WallPostType.POLL: "POLL",
            WallPostType.EVENT: "EVENT",
            WallPostType.MEETING: "",
        }.get(obj.post_type, "")


class PersonalBoardPostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    poll = serializers.SerializerMethodField()
    type_label = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()

    class Meta:
        model = PersonalBoardPost
        fields = [
            "id",
            "post_type",
            "type_label",
            "title",
            "body",
            "event_starts_at",
            "event_ends_at",
            "event_location",
            "poll",
            "attachment",
            "author",
            "can_delete",
            "created_at",
            "updated_at",
        ]

    def get_author(self, obj):
        return serialize_post_author(obj.board.user, self.context.get("request"))

    def get_can_delete(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        return can_delete_personal_post(obj, user)

    def get_poll(self, obj):
        from api.wall_service import serialize_personal_poll

        request = self.context.get("request")
        user = request.user if request else None
        return serialize_personal_poll(obj, user)

    def get_attachment(self, obj):
        from api.board_attachments import serialize_attachment

        return serialize_attachment(obj, self.context.get("request"))

    def get_type_label(self, obj):
        return {
            WallPostType.POST: "",
            WallPostType.QUESTION: "QUESTION",
            WallPostType.POLL: "POLL",
            WallPostType.EVENT: "EVENT",
        }.get(obj.post_type, "")


class OrganizationBoardPublicSerializer(serializers.ModelSerializer):
    posting_mode_label = serializers.CharField(
        source="get_posting_mode_display", read_only=True
    )
    visibility_label = serializers.CharField(
        source="get_visibility_display", read_only=True
    )

    class Meta:
        model = OrganizationBoard
        fields = [
            "id",
            "title",
            "visibility",
            "visibility_label",
            "posting_mode",
            "posting_mode_label",
            "hub_preview_count",
        ]


class OrganizationBoardSettingsSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationBoard.Visibility.choices, required=False
    )
    posting_mode = serializers.ChoiceField(
        choices=OrganizationBoard.PostingMode.choices, required=False
    )
    hub_preview_count = serializers.IntegerField(
        required=False, min_value=0, max_value=25
    )


class PersonalBoardSettingsSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=200, required=False, allow_blank=True
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
    text = serializers.CharField(required=False, allow_blank=True, default="")
    question_type = serializers.ChoiceField(
        choices=SurveyQuestion.QuestionType.choices,
        default=SurveyQuestion.QuestionType.TEXT,
    )
    choices = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    is_demographic = serializers.BooleanField(required=False, default=False)
    body = serializers.CharField(required=False, allow_blank=True, default="")
    banner_url = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    video_url = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    tag_scope = serializers.ChoiceField(choices=["all", "this"], required=False, default="all")

    def validate(self, attrs):
        qtype = attrs.get("question_type") or SurveyQuestion.QuestionType.TEXT
        if qtype == SurveyQuestion.QuestionType.CONTENT:
            body = (attrs.get("body") or "").strip()
            banner = (attrs.get("banner_url") or "").strip()
            video = (attrs.get("video_url") or "").strip()
            title = (attrs.get("text") or "").strip()
            if not any([body, banner, video, title]):
                raise serializers.ValidationError(
                    {"body": "Content blocks need text, a banner, or a video."}
                )
            attrs["is_demographic"] = False
        elif not (attrs.get("text") or "").strip():
            raise serializers.ValidationError({"text": "Question text is required."})
        if qtype == SurveyQuestion.QuestionType.CHOICE and len(attrs.get("choices") or []) < 2:
            raise serializers.ValidationError(
                {"choices": "Choice questions need at least two options."}
            )
        return attrs


class DashboardSurveyCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_anonymous = serializers.BooleanField(default=True)
    aggregate_sharing_notice = serializers.BooleanField(required=False, default=True)
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
    aggregate_sharing_notice = serializers.BooleanField(required=False)


class SurveyAppendQuestionsSerializer(serializers.Serializer):
    questions = SurveyQuestionCreateSerializer(many=True, min_length=1)


class ParticipantInfoFieldCreateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    label = serializers.CharField(max_length=200)
    required = serializers.BooleanField(default=False)
    field_type = serializers.ChoiceField(
        choices=["text", "textarea", "single_select", "multi_select"]
    )
    options = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    def validate(self, attrs):
        label = (attrs.get("label") or "").strip()
        key = (attrs.get("key") or "").strip()
        if not key:
            base = "".join(
                ch if ch.isalnum() else "_" for ch in label.lower()
            ).strip("_")
            while "__" in base:
                base = base.replace("__", "_")
            key = (base[:50] if base else "field")
        attrs["key"] = key
        attrs["label"] = label
        return attrs


class MeetingSlideCreateSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
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
    body = serializers.CharField(required=False, allow_blank=True, default="")
    banner_url = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    video_url = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    tag_scope = serializers.ChoiceField(choices=["all", "this"], required=False, default="all")

    def validate(self, attrs):
        slide_type = attrs["slide_type"]
        prompt = attrs.get("prompt", "").strip()
        title = attrs.get("title", "").strip()
        question_format = attrs.get("question_format", "")
        choices = attrs.get("choices") or []
        fields = attrs.get("fields") or []

        if slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO:
            # A disclosure-only screen (no fields) is allowed; every meeting has one.
            keys = [f["key"] for f in fields]
            if len(keys) != len(set(keys)):
                raise serializers.ValidationError(
                    {"fields": "Field keys must be unique within the slide."}
                )
            for field in fields:
                if field["field_type"] in ("single_select", "multi_select"):
                    opts = field.get("options") or []
                    if len(opts) < 2:
                        raise serializers.ValidationError(
                            {
                                "fields": (
                                    f"Choice question '{field.get('label') or field['key']}' "
                                    "needs at least two options."
                                )
                            }
                        )
        elif slide_type == MeetingSlide.SlideType.CONTENT:
            body = (attrs.get("body") or "").strip()
            banner = (attrs.get("banner_url") or "").strip()
            video = (attrs.get("video_url") or "").strip()
            if not any([body, banner, video, title, prompt]):
                raise serializers.ValidationError(
                    {"body": "Content slides need text, a banner image, or a video link."}
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
    location = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    access_mode = serializers.ChoiceField(
        choices=Meeting.AccessMode.choices,
        default=Meeting.AccessMode.PUBLIC,
    )
    scheduled_start_at = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_end_at = serializers.DateTimeField(required=False, allow_null=True)
    allow_start_early = serializers.BooleanField(default=False)
    is_anonymous = serializers.BooleanField(default=False)
    allow_self_paced = serializers.BooleanField(required=False, default=False)
    ai_mode = serializers.ChoiceField(
        choices=Meeting.AIMode.choices,
        default=Meeting.AIMode.NONE,
    )
    results_visible_to_community = serializers.BooleanField(required=False, default=False)
    minutes_creator = serializers.ChoiceField(
        choices=Meeting.MinutesCreator.choices,
        required=False,
        default=Meeting.MinutesCreator.ORGANIZER_ONLY,
    )
    aggregate_sharing_notice = serializers.BooleanField(required=False, default=True)
    share_with = serializers.ListField(
        child=serializers.CharField(max_length=120), required=False, default=list
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
    location = serializers.CharField(required=False, allow_blank=True, max_length=255)
    scheduled_start_at = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_end_at = serializers.DateTimeField(required=False, allow_null=True)
    allow_start_early = serializers.BooleanField(required=False)
    is_anonymous = serializers.BooleanField(required=False)
    allow_self_paced = serializers.BooleanField(required=False)
    ai_mode = serializers.ChoiceField(choices=Meeting.AIMode.choices, required=False)
    results_visible_to_community = serializers.BooleanField(required=False)
    minutes_creator = serializers.ChoiceField(
        choices=Meeting.MinutesCreator.choices, required=False
    )
    aggregate_sharing_notice = serializers.BooleanField(required=False)
    slides = MeetingSlideCreateSerializer(many=True, required=False)


class MeetingExpectedAttendanceSerializer(serializers.Serializer):
    status = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=20
    )


class MeetingSummaryWriteSerializer(serializers.Serializer):
    body = serializers.CharField()
    status = serializers.ChoiceField(
        choices=MeetingSummary.Status.choices,
        required=False,
        default=MeetingSummary.Status.DRAFT,
    )


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