from django.contrib import admin
from .models import (
    AccessCode,
    BoardPost,
    Meeting,
    MeetingQuestion,
    MeetingResponse,
    Note,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    ResourceType,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    ContactSubmission,
)
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created_at")
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "is_verified")
    prepopulated_fields = {"slug": ("name",)}
@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "is_active")
@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role")
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
@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "access_mode", "status")
@admin.register(MeetingQuestion)
class MeetingQuestionAdmin(admin.ModelAdmin):
    list_display = ("meeting", "text", "is_active", "created_at")
@admin.register(MeetingResponse)
class MeetingResponseAdmin(admin.ModelAdmin):
    list_display = ("meeting", "question", "normalization_status", "created_at")
@admin.register(OrganizationBoard)
class OrganizationBoardAdmin(admin.ModelAdmin):
    list_display = ("organization", "title")
@admin.register(BoardPost)
class BoardPostAdmin(admin.ModelAdmin):
    list_display = ("board", "title", "author", "created_at")
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