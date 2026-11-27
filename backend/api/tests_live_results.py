from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from api.meeting_service import create_initial_session, create_meeting_slides, join_session, submit_slide_response
from api.models import (
    Meeting,
    MeetingSlide,
    Organization,
    OrganizationMembership,
    OrganizationService,
    ResourceType,
    Survey,
    SurveyQuestion,
)


def _org(name):
    org = Organization.objects.create(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    OrganizationService.objects.create(
        organization=org,
        service_level="COMMUNITY",
        billing_source=OrganizationService.BillingSource.ADMIN_GRANT,
        status=OrganizationService.Status.ACTIVE,
        billing_reference=f"LR-{org.id}",
        started_at=timezone.now(),
    )
    return org


class MeetingLiveResultsTests(APITestCase):
    def setUp(self):
        self.org = _org("Live Org")
        self.admin = User.objects.create_user("live_admin", password="Pass1234!")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN
        )
        ResourceType.objects.get_or_create(slug="meeting", defaults={"name": "Meeting", "is_active": True})
        self.meeting = Meeting.objects.create(
            organization=self.org,
            title="Debate",
            allow_self_paced=True,
            is_anonymous=True,
            live_results_for_participants=True,
            results_visible_to_community=False,
            minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        )
        create_meeting_slides(
            self.meeting,
            [
                {
                    "slide_type": "standard",
                    "prompt": "Support the apartments?",
                    "question_format": "single_choice",
                    "choices": ["Yes", "No"],
                },
                {"slide_type": "political_issue_card", "prompt": "Top issues"},
            ],
        )
        self.session = create_initial_session(self.meeting)
        self.session.status = "live"
        self.session.started_at = timezone.now()
        self.session.save()
        self.choice = self.meeting.slides.get(slide_type="standard")
        self.issue = self.meeting.slides.get(slide_type="political_issue_card")
        self.attendance = join_session(self.meeting, self.session)
        submit_slide_response(
            self.meeting, self.session, self.attendance, self.choice, selected_options=["Yes"]
        )
        self.url = f"/api/meetings/{self.meeting.id}/live-results/"
        self.release_url = (
            f"/api/organizations/{self.org.slug}/meetings/{self.meeting.id}/release-results/"
        )

    def _get(self, **params):
        params.setdefault("attendance_id", str(self.attendance.attendance_id))
        return self.client.get(self.url, params)

    def _release(self, slide, released=True):
        self.client.force_authenticate(self.admin)
        res = self.client.post(self.release_url, {"item_id": slide.id, "released": released}, format="json")
        self.client.force_authenticate(None)
        return res

    def test_disabled_meeting_denied(self):
        self.meeting.live_results_for_participants = False
        self.meeting.save()
        res = self._get()
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "disabled")

    def test_requires_attendance(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "join_required")

    def test_nothing_released_returns_empty(self):
        res = self._get()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["released_items"], [])
        self.assertIsNone(res.data["result"])

    def test_release_then_view_bars(self):
        res = self._release(self.choice)
        self.assertEqual(res.status_code, 200)
        released = [s for s in res.data["live"]["slides"] if s["results_released"]]
        self.assertEqual([s["id"] for s in released], [self.choice.id])

        res = self._get(slide_id=self.choice.id)
        self.assertEqual(res.status_code, 200)
        bars = {b["label"]: b["count"] for b in res.data["result"]["bars"]}
        self.assertEqual(bars, {"Yes": 1})
        self.assertEqual(res.data["result"]["ai"]["status"], "not_applicable")
        self.assertNotIn("individual_responses", res.data["result"])

    def test_unreleased_slide_denied(self):
        self._release(self.choice)
        res = self._get(slide_id=self.issue.id)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "not_released")

    def test_unrelease_hides_results(self):
        self._release(self.choice)
        self._release(self.choice, released=False)
        res = self._get()
        self.assertEqual(res.data["released_items"], [])

    def test_ai_status_for_political_slide(self):
        from api.meeting_service import submit_issue_card_responses

        submit_issue_card_responses(
            self.meeting, self.session, self.attendance, self.issue, [{"text": "Traffic"}]
        )
        self._release(self.issue)
        res = self._get(slide_id=self.issue.id)
        self.assertEqual(res.data["result"]["ai"]["status"], "disabled")

        self.meeting.ai_mode = Meeting.AIMode.PAID
        self.meeting.save()
        res = self._get(slide_id=self.issue.id)
        self.assertEqual(res.data["result"]["ai"]["status"], "pending")
        self.assertEqual(res.data["result"]["ai"]["pending"], 1)

    def test_enable_toggle_from_host(self):
        self.meeting.live_results_for_participants = False
        self.meeting.save()
        self.client.force_authenticate(self.admin)
        res = self.client.post(self.release_url, {"enabled": True}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["live"]["live_results_for_participants"])

    def test_non_admin_cannot_release(self):
        other = User.objects.create_user("outsider", password="Pass1234!")
        self.client.force_authenticate(other)
        res = self.client.post(self.release_url, {"item_id": self.choice.id}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_content_slide_cannot_be_released(self):
        create_meeting_slides(self.meeting, [{"slide_type": "content", "title": "Intro", "body": "Hi"}])
        content = self.meeting.slides.filter(slide_type=MeetingSlide.SlideType.CONTENT).first()
        res = self._release(content)
        self.assertEqual(res.status_code, 400)


class SurveyLiveResultsTests(APITestCase):
    def setUp(self):
        self.org = _org("Survey Live Org")
        self.admin = User.objects.create_user("survey_live_admin", password="Pass1234!")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN
        )
        self.survey = Survey.objects.create(
            organization=self.org, title="Pulse", live_results_for_respondents=True
        )
        self.q = SurveyQuestion.objects.create(
            survey=self.survey, order=1, text="Favorite?", question_type="choice", choices=["A", "B"]
        )
        self.demo = SurveyQuestion.objects.create(
            survey=self.survey, order=2, text="ZIP?", question_type="text", is_demographic=True
        )
        self.url = f"/api/surveys/{self.survey.id}/live-results/"
        self.release_url = (
            f"/api/organizations/{self.org.slug}/surveys/{self.survey.id}/release-results/"
        )

    def _submit(self, session, value):
        return self.client.post(
            f"/api/surveys/{self.survey.id}/submit/",
            {"response_session": session, "answers": [{"question_id": self.q.id, "value": value}]},
            format="json",
        )

    def test_requires_submission(self):
        res = self.client.get(self.url, {"response_session": "nobody"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "submit_required")

    def test_release_and_view(self):
        self.assertEqual(self._submit("s1", "A").status_code, 201)
        self.assertEqual(self._submit("s2", "B").status_code, 201)
        self.assertEqual(self._submit("s3", "A").status_code, 201)

        res = self.client.get(self.url, {"response_session": "s1"})
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["result"])

        self.client.force_authenticate(self.admin)
        res = self.client.post(self.release_url, {"item_id": self.q.id}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["participant_results_released_question_ids"], [self.q.id])
        self.client.force_authenticate(None)

        res = self.client.get(self.url, {"response_session": "s1"})
        bars = {b["label"]: b["count"] for b in res.data["result"]["bars"]}
        self.assertEqual(bars, {"A": 2, "B": 1})
        self.assertEqual(res.data["result"]["total_respondents"], 3)

    def test_demographic_question_never_released(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(self.release_url, {"item_id": self.demo.id}, format="json")
        self.assertEqual(res.status_code, 400)
