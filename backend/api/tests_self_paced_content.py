from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.content_media import normalize_content_config, survey_disclosure_payload, video_embed_payload
from api.meeting_service import (
    create_initial_session,
    create_meeting_slides,
    finalize_self_paced_responses,
    join_session,
    participant_slide_answers,
    submit_issue_card_responses,
    submit_slide_response,
)
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
        billing_reference=f"SP-{org.id}",
        started_at=timezone.now(),
    )
    return org


class ContentMediaHelpersTests(APITestCase):
    def test_youtube_embed(self):
        embed = video_embed_payload("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(embed["provider"], "youtube")
        self.assertIn("youtube.com/embed/dQw4w9WgXcQ", embed["embed_url"])

    def test_rejects_unknown_video_host(self):
        self.assertIsNone(video_embed_payload("https://evil.example/video.mp4"))


class SelfPacedAndContentTests(APITestCase):
    def setUp(self):
        self.org = _org("Pace Org")
        self.admin = User.objects.create_user("pace_admin", password="Pass1234!")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN
        )
        ResourceType.objects.get_or_create(slug="meeting", defaults={"name": "Meeting", "is_active": True})

    def test_self_paced_allows_non_current_slide(self):
        meeting = Meeting.objects.create(
            organization=self.org,
            title="Self paced",
            allow_self_paced=True,
            results_visible_to_community=False,
            minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        )
        create_meeting_slides(
            meeting,
            [
                {
                    "slide_type": "content",
                    "title": "Watch this",
                    "body": "Hello",
                    "video_url": "https://youtu.be/dQw4w9WgXcQ",
                },
                {"slide_type": "standard", "prompt": "Q1", "question_format": "text"},
            ],
        )
        session = create_initial_session(meeting)
        session.status = "live"
        session.started_at = timezone.now()
        # Host is on disclosure (first slide)
        first = meeting.slides.order_by("order", "id").first()
        session.current_slide = first
        session.save()
        attendance = join_session(meeting, session)
        q = meeting.slides.get(slide_type="standard")
        # Answering a non-current question succeeds when self-paced
        submit_slide_response(meeting, session, attendance, q, raw_response="hi")
        content = meeting.slides.get(slide_type="content")
        cfg = normalize_content_config(content.config)
        self.assertEqual(cfg["video_embed"]["provider"], "youtube")

    def test_organizer_paced_still_blocks(self):
        meeting = Meeting.objects.create(
            organization=self.org,
            title="Host paced",
            allow_self_paced=False,
            results_visible_to_community=False,
            minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        )
        create_meeting_slides(
            meeting,
            [
                {"slide_type": "standard", "prompt": "Q1", "question_format": "text"},
                {"slide_type": "standard", "prompt": "Q2", "question_format": "text"},
            ],
        )
        session = create_initial_session(meeting)
        session.status = "live"
        session.started_at = timezone.now()
        slides = list(meeting.slides.filter(slide_type="standard").order_by("order"))
        session.current_slide = slides[0]
        session.save()
        attendance = join_session(meeting, session)
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            submit_slide_response(meeting, session, attendance, slides[1], raw_response="nope")

    def test_self_paced_issue_card_reload_and_resubmit(self):
        meeting = Meeting.objects.create(
            organization=self.org,
            title="Issues",
            allow_self_paced=True,
            results_visible_to_community=False,
            minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        )
        create_meeting_slides(
            meeting,
            [{"slide_type": "political_issue_card", "prompt": "Top issues"}],
        )
        session = create_initial_session(meeting)
        session.status = "live"
        session.started_at = timezone.now()
        session.save()
        attendance = join_session(meeting, session)
        slide = meeting.slides.get(slide_type="political_issue_card")
        submit_issue_card_responses(
            meeting,
            session,
            attendance,
            slide,
            [
                {"text": "Housing", "importance_order": 1},
                {"text": "Transit", "importance_order": 2},
            ],
        )
        loaded = participant_slide_answers(session, attendance, slide)
        self.assertEqual(
            [row["text"] for row in loaded["issues"]],
            ["Housing", "Transit"],
        )
        submit_issue_card_responses(
            meeting,
            session,
            attendance,
            slide,
            [{"text": "Schools", "importance_order": 1}],
        )
        reloaded = participant_slide_answers(session, attendance, slide)
        self.assertEqual([row["text"] for row in reloaded["issues"]], ["Schools"])

    def test_finalize_requires_all_slides(self):
        meeting = Meeting.objects.create(
            organization=self.org,
            title="Finalize",
            allow_self_paced=True,
            results_visible_to_community=False,
            minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        )
        create_meeting_slides(
            meeting,
            [
                {"slide_type": "standard", "prompt": "Q1", "question_format": "text"},
                {"slide_type": "standard", "prompt": "Q2", "question_format": "text"},
            ],
        )
        session = create_initial_session(meeting)
        session.status = "live"
        session.started_at = timezone.now()
        session.save()
        attendance = join_session(meeting, session)
        disclosure = meeting.slides.filter(slide_type="participant_info").first()
        if disclosure:
            from api.meeting_service import submit_participant_profile

            submit_participant_profile(attendance, disclosure, {})
        slides = list(meeting.slides.filter(slide_type="standard").order_by("order"))
        submit_slide_response(meeting, session, attendance, slides[0], raw_response="one")
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            finalize_self_paced_responses(meeting, session, attendance)
        submit_slide_response(meeting, session, attendance, slides[1], raw_response="two")
        attendance = finalize_self_paced_responses(meeting, session, attendance)
        self.assertIsNotNone(attendance.responses_finalized_at)


class SurveyFlowTests(APITestCase):
    def test_disclosure_and_demographic_order(self):
        org = _org("Survey Flow")
        survey = Survey.objects.create(organization=org, title="S", is_anonymous=True)
        SurveyQuestion.objects.create(
            survey=survey, order=1, text="ZIP?", question_type="text", is_demographic=True
        )
        SurveyQuestion.objects.create(
            survey=survey, order=2, text="Main Q", question_type="text", is_demographic=False
        )
        SurveyQuestion.objects.create(
            survey=survey,
            order=0,
            text="Intro",
            question_type="content",
            config={"body": "Watch first", "video_url": "https://youtu.be/dQw4w9WgXcQ"},
        )
        from api.content_media import ordered_survey_questions

        ordered = ordered_survey_questions(list(survey.questions.all()))
        self.assertEqual([q.text for q in ordered], ["Intro", "Main Q", "ZIP?"])
        disc = survey_disclosure_payload(survey)
        self.assertIn("anonymous", disc["text"].lower())
