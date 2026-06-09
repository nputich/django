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
        "access-codes/check/",
        views.AccessCodeCheckView.as_view(),
        name="access-code-check",
    ),
]