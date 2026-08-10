from django.urls import path
from . import views
from . import profile_board_views
from . import directory_views
from . import billing_views

urlpatterns = [
    path("me/", profile_board_views.MeView.as_view(), name="me"),
    path("me/profile/", profile_board_views.MeProfileView.as_view(), name="me-profile"),
    path("me/board/", profile_board_views.PersonalBoardView.as_view(), name="me-board"),
    path(
        "me/board/posts/<int:pk>/",
        profile_board_views.PersonalBoardPostDeleteView.as_view(),
        name="me-board-post-delete",
    ),
    path("directory/scopes/", directory_views.DirectoryScopesView.as_view(), name="directory-scopes"),
    path("directory/geo/", directory_views.DirectoryGeoSearchView.as_view(), name="directory-geo"),
    path(
        "directory/categories/",
        directory_views.DirectoryCategoriesView.as_view(),
        name="directory-categories",
    ),
    path(
        "directory/organizations/",
        directory_views.DirectoryOrganizationsView.as_view(),
        name="directory-organizations",
    ),
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
        "organizations/<slug:slug>/billing/",
        billing_views.OrganizationBillingView.as_view(),
        name="org-billing",
    ),
    path(
        "organizations/<slug:slug>/billing/checkout-preview/",
        billing_views.OrganizationBillingCheckoutPreviewView.as_view(),
        name="org-billing-checkout-preview",
    ),
    path(
        "organizations/<slug:slug>/billing/checkout/",
        billing_views.OrganizationBillingCheckoutStartView.as_view(),
        name="org-billing-checkout-start",
    ),
    path(
        "organizations/<slug:slug>/billing/paypal/confirm/",
        billing_views.OrganizationBillingPayPalConfirmView.as_view(),
        name="org-billing-paypal-confirm",
    ),
    path(
        "organizations/<slug:slug>/surveys/",
        views.OrganizationSurveyCreateView.as_view(),
        name="org-survey-create",
    ),
    path(
        "organizations/<slug:slug>/surveys/<int:pk>/",
        views.OrganizationSurveyDetailView.as_view(),
        name="org-survey-detail",
    ),
    path(
        "organizations/<slug:slug>/surveys/<int:pk>/questions/",
        views.OrganizationSurveyAppendQuestionsView.as_view(),
        name="org-survey-append-questions",
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
        "organizations/<slug:slug>/meetings/<int:pk>/analytics/",
        views.OrganizationMeetingAnalyticsView.as_view(),
        name="org-meeting-analytics",
    ),
    path(
        "organizations/<slug:slug>/meetings/<int:pk>/analytics/classify/",
        views.OrganizationMeetingPoliticalClassifyView.as_view(),
        name="org-meeting-analytics-classify",
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
    path(
        "organizations/<slug:slug>/board/",
        profile_board_views.OrganizationBoardView.as_view(),
        name="org-board",
    ),
    path(
        "organizations/<slug:slug>/board/settings/",
        profile_board_views.OrganizationBoardSettingsView.as_view(),
        name="org-board-settings",
    ),
    path(
        "organizations/<slug:slug>/board/posts/<int:pk>/",
        profile_board_views.OrganizationBoardPostDeleteView.as_view(),
        name="org-board-post-delete",
    ),
    path(
        "organizations/<slug:slug>/board/posts/<int:pk>/replies/",
        profile_board_views.OrganizationBoardReplyView.as_view(),
        name="org-board-reply-create",
    ),
    path(
        "organizations/<slug:slug>/board/posts/<int:pk>/replies/<int:reply_pk>/",
        profile_board_views.OrganizationBoardReplyDeleteView.as_view(),
        name="org-board-reply-delete",
    ),
    path("contact/", views.ContactSubmitView.as_view(), name="contact-submit"),
]