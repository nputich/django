from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.billing_plans import SERVICE_LEVEL_BASIC
from api.billing_service import (
    activate_organization_service,
    create_pending_organization_service,
)
from api.meeting_access import start_meeting_session
from api.meeting_service import create_initial_session
from api.models import (
    Meeting,
    MeetingAttendance,
    MeetingSlide,
    Organization,
    OrganizationMembership,
    OrganizationUsagePeriod,
    ResourceType,
    Survey,
    SurveyQuestion,
    SurveySubmission,
)
from api.plan_limits import PLAN_LIMITS, effective_limit, get_plan_limits
from api.usage_service import serialize_usage


class PlanLimitCatalogTests(APITestCase):
    def test_basic_published_caps(self):
        spec = get_plan_limits(SERVICE_LEVEL_BASIC)
        self.assertEqual(spec["survey_submission_limit"], 2000)
        self.assertEqual(spec["meetings_started_limit"], 10)
        self.assertEqual(spec["attendee_limit"], 200)
        self.assertEqual(spec["ai_meeting_runs_limit"], 3)
        self.assertEqual(effective_limit(spec, "meetings_started"), 10)

    def test_community_plus_meetings_use_abuse_cap(self):
        spec = get_plan_limits("COMMUNITY_PLUS")
        self.assertIsNone(spec["meetings_started_limit"])
        self.assertEqual(effective_limit(spec, "meetings_started"), 200)


class PlanLimitEnforcementTests(APITestCase):
    def setUp(self):
        for slug, name in (
            ("survey", "Survey"),
            ("meeting", "Meeting"),
            ("organization", "Organization"),
        ):
            ResourceType.objects.get_or_create(
                slug=slug, defaults={"name": name, "is_active": True}
            )
        self.user = User.objects.create_user(username="limitadmin", password="pass")
        self.org = Organization.objects.create(
            name="Limit Org",
            slug="limit-org",
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
        )
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_BASIC,
        )
        activate_organization_service(pending)
        self.client.force_authenticate(self.user)

    def test_dashboard_includes_usage(self):
        url = reverse("org-dashboard", kwargs={"slug": self.org.slug})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("usage", res.data)
        self.assertEqual(res.data["usage"]["survey_submissions"]["limit"], 2000)
        self.assertEqual(res.data["usage"]["meetings_started"]["used"], 0)

    def test_survey_submission_counts_once_per_session(self):
        survey = Survey.objects.create(
            organization=self.org, title="Cap Survey", is_active=True
        )
        question = SurveyQuestion.objects.create(
            survey=survey, order=1, text="Priority?", question_type="text"
        )
        url = reverse("survey-submit", kwargs={"pk": survey.pk})
        payload = {
            "response_session": "session-abc",
            "answers": [{"question_id": question.id, "value": "Roads"}],
        }
        first = self.client.post(url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(url, payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SurveySubmission.objects.filter(survey=survey).count(), 1)
        usage = serialize_usage(self.org)
        self.assertEqual(usage["survey_submissions"]["used"], 1)

    def test_survey_cap_blocks_new_sessions(self):
        survey = Survey.objects.create(
            organization=self.org, title="Tiny Cap", is_active=True
        )
        question = SurveyQuestion.objects.create(
            survey=survey, order=1, text="Q", question_type="text"
        )
        url = reverse("survey-submit", kwargs={"pk": survey.pk})
        patched = {**PLAN_LIMITS[SERVICE_LEVEL_BASIC], "survey_submission_limit": 1}
        with patch.dict(PLAN_LIMITS, {SERVICE_LEVEL_BASIC: patched}):
            ok = self.client.post(
                url,
                {
                    "response_session": "one",
                    "answers": [{"question_id": question.id, "value": "A"}],
                },
                format="json",
            )
            self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
            blocked = self.client.post(
                url,
                {
                    "response_session": "two",
                    "answers": [{"question_id": question.id, "value": "B"}],
                },
                format="json",
            )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(blocked.data["code"], "capacity_reached")
        self.assertEqual(blocked.data["metric"], "survey_submissions")

    def _live_meeting(self):
        meeting = Meeting.objects.create(
            organization=self.org,
            title="Live Cap Meeting",
            status="scheduled",
        )
        MeetingSlide.objects.create(
            meeting=meeting,
            order=1,
            slide_type=MeetingSlide.SlideType.STANDARD,
            prompt="Hello",
        )
        session = create_initial_session(meeting)
        start_meeting_session(meeting, session)
        return meeting

    def test_attendee_cap_blocks_extra_joins(self):
        meeting = self._live_meeting()
        session = meeting.sessions.order_by("-id").first()
        session.attendee_limit = 1
        session.save(update_fields=["attendee_limit"])
        url = reverse("meeting-join", kwargs={"pk": meeting.pk})
        first = self.client.post(url, {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        rejoin = self.client.post(
            url,
            {"attendance_id": first.data["attendance_id"]},
            format="json",
        )
        self.assertEqual(rejoin.status_code, status.HTTP_200_OK)
        self.assertTrue(rejoin.data.get("rejoined"))
        self.client.force_authenticate(user=None)
        blocked = self.client.post(url, {}, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(blocked.data["metric"], "attendees")
        self.assertEqual(
            MeetingAttendance.objects.filter(
                session__meeting=meeting, status=MeetingAttendance.Status.JOINED
            ).count(),
            1,
        )

    def test_meeting_start_cap(self):
        meeting = Meeting.objects.create(
            organization=self.org, title="Quota Meeting", status="scheduled"
        )
        MeetingSlide.objects.create(
            meeting=meeting,
            order=1,
            slide_type=MeetingSlide.SlideType.STANDARD,
            prompt="Hello",
        )
        url = reverse(
            "org-meeting-start", kwargs={"slug": self.org.slug, "pk": meeting.pk}
        )
        patched = {**PLAN_LIMITS[SERVICE_LEVEL_BASIC], "meetings_started_limit": 0}
        with patch.dict(PLAN_LIMITS, {SERVICE_LEVEL_BASIC: patched}):
            res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data["metric"], "meetings_started")
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, "scheduled")

    def test_board_post_cap_on_free_style_limit(self):
        url = reverse("org-board", kwargs={"slug": self.org.slug})
        patched = {**PLAN_LIMITS[SERVICE_LEVEL_BASIC], "board_posts_limit": 1}
        with patch.dict(PLAN_LIMITS, {SERVICE_LEVEL_BASIC: patched}):
            first = self.client.post(url, {"body": "Hello board"}, format="json")
            self.assertEqual(first.status_code, status.HTTP_201_CREATED)
            blocked = self.client.post(url, {"body": "Too many"}, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(blocked.data["metric"], "board_posts")
        self.assertEqual(
            OrganizationUsagePeriod.objects.get(organization=self.org).board_posts_used,
            1,
        )
