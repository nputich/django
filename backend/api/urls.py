from django.urls import path
from . import views
urlpatterns = [
    path("notes/", views.NoteListCreate.as_view(), name="note-list"),
    path("notes/delete/<int:pk>/", views.NoteDelete.as_view(), name="delete-note"),
    path("codes/<str:query>/resolve/", views.ResolveCodeView.as_view(), name="resolve-code"),
    path("surveys/<int:pk>/", views.SurveyDetailView.as_view(), name="survey-detail"),
    path("surveys/<int:pk>/submit/", views.SurveySubmitView.as_view(), name="survey-submit"),
    path("organizations/<slug:slug>/hub/", views.OrganizationHubView.as_view(), name="org-hub"),
]