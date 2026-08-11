"""
Free organizations retain READ access to historical engagement data.
Paid create/start/AI actions require Basic or higher.
"""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.billing_plans import SERVICE_LEVEL_BASIC, SERVICE_LEVEL_FREE
from api.billing_service import (
    activate_organization_service,
    cancel_organization_service,
    create_pending_organization_service,
)
from api.feature_entitlements import get_organization_capabilities
from api.models import Meeting, Organization, OrganizationMembership, ResourceType, Survey


class FeatureEntitlementApiTests(APITestCase):
    def setUp(self):
        for slug, name in (
            ("survey", "Survey"),
            ("meeting", "Meeting"),
            ("organization", "Organization"),
        ):
            ResourceType.objects.get_or_create(
                slug=slug, defaults={"name": name, "is_active": True}
            )
        self.user = User.objects.create_user(
            username="orgadmin", password="AdminPass2026!"
        )
        self.org = Organization.objects.create(
            name="Forsyth Free Org",
            slug="forsyth-free-org",
            description="History must remain visible",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.ADMIN,
        )
        self.meeting = Meeting.objects.create(
            organization=self.org,
            title="Neighborhood Listening Session",
            description="Past meeting",
            status="ended",
        )
        self.survey = Survey.objects.create(
            organization=self.org,
            title="Community Priorities Survey",
            description="Past survey",
            is_active=True,
        )
        self.client.force_authenticate(self.user)

    def test_free_capabilities_allow_view_deny_create(self):
        caps = get_organization_capabilities(self.org)
        self.assertEqual(caps["service_level"], SERVICE_LEVEL_FREE)
        self.assertTrue(caps["is_free"])
        self.assertTrue(caps["view_meetings"])
        self.assertTrue(caps["view_surveys"])
        self.assertTrue(caps["view_reports"])
        self.assertTrue(caps["view_historical_ai"])
        self.assertFalse(caps["create_meetings"])
        self.assertFalse(caps["start_meetings"])
        self.assertFalse(caps["create_surveys"])
        self.assertFalse(caps["run_new_ai_analysis"])

    def test_dashboard_exposes_capabilities_and_history(self):
        url = reverse("org-dashboard", kwargs={"slug": self.org.slug})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["capabilities"]["view_meetings"])
        self.assertFalse(res.data["capabilities"]["create_meetings"])
        titles = [m["title"] for m in res.data["meetings"]]
        self.assertIn("Neighborhood Listening Session", titles)
        survey_titles = [s["title"] for s in res.data["surveys"]]
        self.assertIn("Community Priorities Survey", survey_titles)

    def test_free_can_get_existing_meeting(self):
        url = reverse(
            "org-meeting-detail",
            kwargs={"slug": self.org.slug, "pk": self.meeting.pk},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], self.meeting.title)

    def test_free_can_get_existing_survey(self):
        url = reverse(
            "org-survey-detail",
            kwargs={"slug": self.org.slug, "pk": self.survey.pk},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], self.survey.title)

    def test_free_denied_create_meeting(self):
        url = reverse("org-meeting-create", kwargs={"slug": self.org.slug})
        res = self.client.post(
            url,
            {
                "title": "Should Not Create",
                "slides": [
                    {
                        "order": 1,
                        "slide_type": "standard",
                        "title": "Q1",
                        "prompt": "What matters?",
                        "question_format": "text",
                        "choices": [],
                        "fields": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(res.data.get("upgrade_required"))
        self.assertEqual(res.data.get("code"), "upgrade_required")
        self.assertFalse(
            Meeting.objects.filter(organization=self.org, title="Should Not Create").exists()
        )

    def test_free_denied_create_survey(self):
        url = reverse("org-survey-create", kwargs={"slug": self.org.slug})
        res = self.client.post(
            url,
            {
                "title": "Should Not Create Survey",
                "questions": [
                    {"order": 1, "text": "Priority?", "question_type": "text", "choices": []}
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(res.data.get("upgrade_required"))
        self.assertFalse(
            Survey.objects.filter(
                organization=self.org, title="Should Not Create Survey"
            ).exists()
        )

    def test_free_denied_start_meeting(self):
        scheduled = Meeting.objects.create(
            organization=self.org,
            title="Scheduled but locked",
            status="scheduled",
        )
        url = reverse(
            "org-meeting-start",
            kwargs={"slug": self.org.slug, "pk": scheduled.pk},
        )
        res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(res.data.get("upgrade_required"))
        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, "scheduled")

    def test_cancel_paid_keeps_history_locks_create(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_BASIC,
        )
        activate_organization_service(pending)
        caps_paid = get_organization_capabilities(self.org)
        self.assertTrue(caps_paid["create_meetings"])

        cancel_organization_service(pending)
        caps_free = get_organization_capabilities(self.org)
        self.assertEqual(caps_free["service_level"], SERVICE_LEVEL_FREE)
        self.assertFalse(caps_free["create_meetings"])
        self.assertTrue(
            Meeting.objects.filter(pk=self.meeting.pk, organization=self.org).exists()
        )
        self.assertTrue(
            Survey.objects.filter(pk=self.survey.pk, organization=self.org).exists()
        )
        self.assertTrue(
            Organization.objects.filter(pk=self.org.pk, slug=self.org.slug).exists()
        )

        detail = reverse(
            "org-meeting-detail",
            kwargs={"slug": self.org.slug, "pk": self.meeting.pk},
        )
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_200_OK)

        create_url = reverse("org-meeting-create", kwargs={"slug": self.org.slug})
        denied = self.client.post(
            create_url,
            {
                "title": "After cancel",
                "slides": [
                    {
                        "order": 1,
                        "slide_type": "standard",
                        "title": "Q",
                        "prompt": "Prompt",
                        "question_format": "text",
                        "choices": [],
                        "fields": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_basic_can_create_meeting(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_BASIC,
        )
        activate_organization_service(pending)
        url = reverse("org-meeting-create", kwargs={"slug": self.org.slug})
        res = self.client.post(
            url,
            {
                "title": "Paid Meeting",
                "slides": [
                    {
                        "order": 1,
                        "slide_type": "standard",
                        "title": "Welcome",
                        "prompt": "Share a thought",
                        "question_format": "text",
                        "choices": [],
                        "fields": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(
            res.status_code,
            status.HTTP_201_CREATED,
            msg=getattr(res, "data", res.content),
        )
        self.assertTrue(
            Meeting.objects.filter(organization=self.org, title="Paid Meeting").exists()
        )
