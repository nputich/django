from django.contrib import admin
from .models import (
    AccessCode,
    AccessCodeRedemption,
    BoardPost,
    ContactSubmission,
    GeographicArea,
    Meeting,
    MeetingAttendance,
    MeetingExpectedAttendance,
    MeetingQuestion,
    MeetingResponse,
    MeetingResponseAI,
    MeetingSession,
    MeetingShare,
    MeetingSlide,
    QuestionTag,
    QuestionTagLink,
    MeetingSummary,
    Note,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    OrganizationRelationship,
    OrganizationService,
    OrganizationUsagePeriod,
    AiUsageEvent,
    SurveySubmission,
    UmbrellaLicense,
    OrgCategory,
    ParticipantProfileValue,
    PersonalBoard,
    PersonalBoardPost,
    PoliticalClassification,
    ResourceType,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    UserProfile,
)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created_at")


@admin.register(GeographicArea)
class GeographicAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "area_type", "country_code", "external_code", "parent", "is_active")
    list_filter = ("area_type", "country_code", "is_active")
    search_fields = ("name", "slug", "external_code")
    raw_id_fields = ("parent",)


@admin.register(OrgCategory)
class OrgCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    raw_id_fields = ("parent",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "geographic_scope",
        "service_area",
        "primary_subcategory",
        "is_active",
        "is_verified",
    )
    list_filter = ("geographic_scope", "is_active", "is_verified")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = (
        "service_area",
        "headquarters_area",
        "primary_subcategory",
        "parent_organization",
    )


@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "is_active")


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role")


@admin.register(OrganizationRelationship)
class OrganizationRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "from_organization",
        "to_organization",
        "status",
        "initiated_by_organization",
        "public",
        "created_at",
        "responded_at",
        "ended_at",
    )
    list_filter = ("kind", "status", "public")
    search_fields = (
        "from_organization__name",
        "from_organization__slug",
        "to_organization__name",
        "to_organization__slug",
    )
    raw_id_fields = (
        "from_organization",
        "to_organization",
        "initiated_by_organization",
        "ended_by_organization",
        "requested_by",
        "responded_by",
        "conversation",
    )
    readonly_fields = ("created_at",)


@admin.register(OrganizationService)
class OrganizationServiceAdmin(admin.ModelAdmin):
    list_display = (
        "billing_reference",
        "organization",
        "service_level",
        "status",
        "billing_source",
        "paypal_subscription_id",
        "started_at",
        "created_at",
    )
    list_filter = ("service_level", "status", "billing_source")
    search_fields = (
        "billing_reference",
        "paypal_subscription_id",
        "paypal_plan_id",
        "organization__name",
        "organization__slug",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("organization", "requested_by")


@admin.register(QuestionTag)
class QuestionTagAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "category", "organization", "is_active", "created_at")
    list_filter = ("category", "is_active")
    search_fields = ("label", "slug", "organization__name")
    raw_id_fields = ("organization", "created_by")


@admin.register(QuestionTagLink)
class QuestionTagLinkAdmin(admin.ModelAdmin):
    list_display = ("tag", "organization", "question_key", "slide", "survey_question", "created_at")
    list_filter = ("tag__category",)
    search_fields = ("question_key", "tag__label", "organization__name")
    raw_id_fields = ("organization", "tag", "slide", "survey_question", "created_by")


@admin.register(MeetingShare)
class MeetingShareAdmin(admin.ModelAdmin):
    list_display = ("meeting", "organization", "status", "declared_before_start", "created_at", "revoked_at")
    list_filter = ("status", "declared_before_start")
    search_fields = ("meeting__title", "organization__name")
    raw_id_fields = ("meeting", "organization", "created_by", "revoked_by")


@admin.register(UmbrellaLicense)
class UmbrellaLicenseAdmin(admin.ModelAdmin):
    list_display = ("organization", "code", "is_active", "max_members", "created_at", "rotated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "organization__name", "organization__slug")
    raw_id_fields = ("organization", "created_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrganizationUsagePeriod)
class OrganizationUsagePeriodAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "service_level",
        "period_start",
        "period_end",
        "survey_submissions_used",
        "meetings_started_used",
        "ai_meeting_runs_used",
        "board_posts_used",
    )
    list_filter = ("service_level",)
    search_fields = ("organization__name", "organization__slug")
    raw_id_fields = ("organization",)


@admin.register(AiUsageEvent)
class AiUsageEventAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "meeting",
        "provider",
        "consumed_run",
        "success",
        "created_at",
    )
    list_filter = ("provider", "consumed_run", "success")
    raw_id_fields = ("organization", "meeting", "usage_period")


@admin.register(AccessCodeRedemption)
class AccessCodeRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "organization",
        "service_level",
        "redeemed_by",
        "redeemed_at",
        "organization_service",
    )
    list_filter = ("service_level", "code")
    search_fields = (
        "code",
        "organization__name",
        "organization__slug",
        "redeemed_by__username",
    )
    readonly_fields = ("redeemed_at",)
    raw_id_fields = ("organization", "redeemed_by", "organization_service")


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 1


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "is_active")
    inlines = [SurveyQuestionInline]


@admin.register(SurveyAnswer)
class SurveyAnswerAdmin(admin.ModelAdmin):
    list_display = ("survey", "question", "response_session", "created_at")


@admin.register(SurveySubmission)
class SurveySubmissionAdmin(admin.ModelAdmin):
    list_display = ("survey", "organization", "response_session", "created_at")
    raw_id_fields = ("survey", "organization", "usage_period")


class MeetingSlideInline(admin.TabularInline):
    model = MeetingSlide
    extra = 1
    fields = ("order", "slide_type", "title", "prompt", "question_format", "is_active")


class MeetingSessionInline(admin.TabularInline):
    model = MeetingSession
    extra = 0
    readonly_fields = ("session_number", "status", "started_at", "ended_at", "created_at")
    fields = ("session_number", "status", "current_slide", "started_at", "ended_at")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "access_mode",
        "status",
        "scheduled_start_at",
        "results_visible_to_community",
        "minutes_creator",
        "is_anonymous",
        "ai_mode",
    )
    list_filter = (
        "status",
        "access_mode",
        "ai_mode",
        "is_anonymous",
        "results_visible_to_community",
        "minutes_creator",
    )
    inlines = [MeetingSlideInline, MeetingSessionInline]


@admin.register(MeetingExpectedAttendance)
class MeetingExpectedAttendanceAdmin(admin.ModelAdmin):
    list_display = ("meeting", "user", "status", "updated_at")
    list_filter = ("status",)


@admin.register(MeetingSummary)
class MeetingSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "status",
        "is_organizer_authored",
        "author",
        "published_at",
        "updated_at",
    )
    list_filter = ("status", "is_organizer_authored")


@admin.register(MeetingSlide)
class MeetingSlideAdmin(admin.ModelAdmin):
    list_display = ("meeting", "slide_type", "order", "title", "is_active")


@admin.register(MeetingSession)
class MeetingSessionAdmin(admin.ModelAdmin):
    list_display = ("meeting", "session_number", "status", "current_slide", "started_at")


@admin.register(MeetingAttendance)
class MeetingAttendanceAdmin(admin.ModelAdmin):
    list_display = ("session", "participant_id", "status", "joined_at", "left_at")


@admin.register(ParticipantProfileValue)
class ParticipantProfileValueAdmin(admin.ModelAdmin):
    list_display = ("attendance", "field_key", "field_label", "created_at")


@admin.register(MeetingQuestion)
class MeetingQuestionAdmin(admin.ModelAdmin):
    list_display = ("meeting", "text", "is_active", "created_at")


@admin.register(MeetingResponse)
class MeetingResponseAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "slide",
        "participant_id",
        "normalization_status",
        "classification_status",
        "created_at",
    )


@admin.register(MeetingResponseAI)
class MeetingResponseAIAdmin(admin.ModelAdmin):
    list_display = ("response", "sentiment", "confidence", "processed_at")


@admin.register(PoliticalClassification)
class PoliticalClassificationAdmin(admin.ModelAdmin):
    list_display = (
        "response",
        "major_issue",
        "specific_issue",
        "source",
    )


@admin.register(OrganizationBoard)
class OrganizationBoardAdmin(admin.ModelAdmin):
    list_display = ("organization", "title", "posting_mode")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "city", "state", "updated_at")
    search_fields = ("user__username", "display_name")


@admin.register(PersonalBoard)
class PersonalBoardAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "created_at")


@admin.register(PersonalBoardPost)
class PersonalBoardPostAdmin(admin.ModelAdmin):
    list_display = ("board", "post_type", "title", "created_at")
    list_filter = ("post_type",)


@admin.register(BoardPost)
class BoardPostAdmin(admin.ModelAdmin):
    list_display = ("board", "post_type", "title", "author", "created_at")
    list_filter = ("post_type",)


@admin.register(AccessCode)
class AccessCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "resource_type", "organization", "label", "is_primary", "is_active")
    list_filter = ("resource_type", "is_active")
    search_fields = ("code", "label", "organization__name")


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("name", "email", "subject", "message", "created_at")
