"""Demographic cell suppression for live results (k-anonymity style)."""

from django.utils import timezone
from rest_framework.test import APITestCase

from api.meeting_analytics import DEMOGRAPHIC_MIN_CELL_COUNT, get_slide_analytics_compare
from api.meeting_service import (
    create_initial_session,
    create_meeting_slides,
    join_session,
    submit_participant_profile,
    submit_slide_response,
)
from api.meeting_sharing import disclosure_text
from api.models import Meeting, Organization, OrganizationService


def _org():
    org = Organization.objects.create(name="Priv Org", slug="priv-org", is_active=True)
    OrganizationService.objects.create(
        organization=org,
        service_level="COMMUNITY",
        billing_source=OrganizationService.BillingSource.ADMIN_GRANT,
        status=OrganizationService.Status.ACTIVE,
        billing_reference="PRIV-1",
        started_at=timezone.now(),
    )
    return org


class DemographicSuppressionTests(APITestCase):
    def setUp(self):
        self.org = _org()
        self.meeting = Meeting.objects.create(
            organization=self.org,
            title="Privacy meeting",
            is_anonymous=True,
            allow_self_paced=True,
            results_visible_to_community=False,
            minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        )
        create_meeting_slides(
            self.meeting,
            [
                {
                    "slide_type": "participant_info",
                    "order": 0,
                    "fields": [
                        {
                            "key": "gender",
                            "label": "Gender",
                            "field_type": "single_select",
                            "options": ["Man", "Woman", "Other"],
                            "required": False,
                        }
                    ],
                },
                {
                    "slide_type": "standard",
                    "order": 1,
                    "prompt": "Top concern?",
                    "question_format": "single_choice",
                    "choices": ["Housing", "Schools"],
                },
            ],
        )
        self.session = create_initial_session(self.meeting)
        self.session.status = "live"
        self.session.started_at = timezone.now()
        self.session.save()
        self.info = self.meeting.slides.get(slide_type="participant_info")
        self.question = self.meeting.slides.get(slide_type="standard")

    def _person(self, gender, choice):
        att = join_session(self.meeting, self.session)
        submit_participant_profile(att, self.info, {"gender": gender})
        submit_slide_response(
            self.meeting, self.session, att, self.question, selected_options=[choice]
        )
        return att

    def test_disclosure_mentions_organizers_and_small_groups(self):
        text = disclosure_text(self.meeting)
        self.assertIn("Organizers can still read the answers", text)
        self.assertIn("every group is large enough", text)

    def test_compare_blocks_factor_when_any_group_is_small(self):
        # 6 women, 1 man — gender split blocked entirely; overall only
        for _ in range(6):
            self._person("Woman", "Housing")
        self._person("Man", "Schools")

        payload = get_slide_analytics_compare(
            self.meeting, self.session, self.question, split_field="gender"
        )
        self.assertTrue(payload["split_blocked"])
        self.assertEqual(payload["comparisons"], [])
        counts = {g["value"]: g["filtered_respondents"] for g in payload["group_counts"]}
        self.assertEqual(counts.get("Woman"), 6)
        self.assertEqual(counts.get("Man"), 1)
        suppressed = {g["value"] for g in payload["suppressed_groups"]}
        self.assertIn("Man", suppressed)
        self.assertEqual(payload["split"]["min_cell_count"], DEMOGRAPHIC_MIN_CELL_COUNT)
        self.assertEqual(payload["overall"]["filtered_respondents"], 7)
        self.assertTrue(len(payload["overall"]["bars"]) > 0)

    def test_compare_allows_split_when_all_groups_large_enough(self):
        for _ in range(6):
            self._person("Woman", "Housing")
        for _ in range(6):
            self._person("Man", "Schools")

        payload = get_slide_analytics_compare(
            self.meeting, self.session, self.question, split_field="gender"
        )
        self.assertFalse(payload["split_blocked"])
        shown = {c["value"] for c in payload["comparisons"]}
        self.assertEqual(shown, {"Woman", "Man"})
