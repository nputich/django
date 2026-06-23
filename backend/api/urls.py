from django.urls import path
from . import views
urlpatterns = [
    path("notes/", views.NoteListCreate.as_view(), name="note-list"),
    path("notes/delete/<int:pk>/", views.NoteDelete.as_view(), name="delete-note"),
    path("codes/<str:query>/resolve/", views.ResolveCodeView.as_view(), name="resolve-code"),
    path("surveys/<int:pk>/", views.SurveyDetailView.as_view(), name="survey-detail"),
    path("surveys/<int:pk>/submit/", views.SurveySubmitView.as_view(), name="survey-submit"),
    path("organizations/<slug:slug>/hub/", views.OrganizationHubView.as_view(), name="org-hub"),
    path("me/organizations/", views.MyOrganizationsView.as_view(), name="my-organizations"),
    path(
        "organizations/<slug:slug>/dashboard/",
        views.OrganizationDashboardView.as_view(),
        name="org-dashboard",
    ),
    path(
        "organizations/<slug:slug>/surveys/",
        views.OrganizationSurveyCreateView.as_view(),
        name="org-survey-create",
    ),
    path(
        "organizations/<slug:slug>/meetings/",
        views.OrganizationMeetingCreateView.as_view(),
        name="org-meeting-create",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/",
        views.OrganizationMeetingDetailView.as_view(),
        name="org-meeting-detail",
    ),
    path("meetings/<int:pk>/", views.MeetingDetailView.as_view(), name="meeting-detail"),
    path("meetings/<int:pk>/session/", views.MeetingSessionView.as_view(), name="meeting-session"),
    path("meetings/<int:pk>/join/", views.MeetingJoinView.as_view(), name="meeting-join"),
    path("meetings/<int:pk>/profile/", views.MeetingProfileSubmitView.as_view(), name="meeting-profile"),
    path("meetings/<int:pk>/respond/", views.MeetingRespondView.as_view(), name="meeting-respond"),
    path("meetings/<int:pk>/leave/", views.MeetingLeaveView.as_view(), name="meeting-leave"),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/start/",
        views.OrganizationMeetingStartView.as_view(),
        name="org-meeting-start",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/live/",
        views.OrganizationMeetingLiveView.as_view(),
        name="org-meeting-live",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/pause/",
        views.OrganizationMeetingPauseView.as_view(),
        name="org-meeting-pause",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/resume/",
        views.OrganizationMeetingResumeView.as_view(),
        name="org-meeting-resume",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/end/",
        views.OrganizationMeetingEndView.as_view(),
        name="org-meeting-end",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/slides/next/",
        views.OrganizationMeetingNextSlideView.as_view(),
        name="org-meeting-next-slide",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/slides/prev/",
        views.OrganizationMeetingPrevSlideView.as_view(),
        name="org-meeting-prev-slide",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/slides/go/",
        views.OrganizationMeetingGoToSlideView.as_view(),
        name="org-meeting-go-slide",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/restart/",
        views.OrganizationMeetingRestartView.as_view(),
        name="org-meeting-restart",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/slides/add/",
        views.OrganizationMeetingAddSlidesView.as_view(),
        name="org-meeting-add-slides",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/export/",
        views.OrganizationMeetingExportView.as_view(),
        name="org-meeting-export",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/ai/process/",
        views.OrganizationMeetingProcessAIView.as_view(),
        name="org-meeting-ai-process",
    ),
    path(
        "access-codes/check/",
        views.AccessCodeCheckView.as_view(),
        name="access-code-check",
    ),
    path("contact/", views.ContactSubmitView.as_view(), name="contact-submit"),
]