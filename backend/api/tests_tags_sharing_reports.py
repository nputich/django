import uuid

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.meeting_service import (
    append_meeting_slides,
    create_initial_session,
    create_meeting_slides,
)
from api.meeting_sharing import (
    SharingError,
    disclosure_text,
    grant_share,
    revoke_share,
)
from api.models import (
    Meeting,
    MeetingResponse,
    MeetingShare,
    MeetingSlide,
    Organization,
    OrganizationMembership,
    OrganizationService,
    QuestionTag,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
)
from api.question_identity import question_key_for
from api.question_tags import (
    count_other_uses,
    create_custom_tag,
    set_tags,
    tags_for_slide,
    tags_for_survey_question,
)
from api.reporting_service import ReportFilters, build_report


def _org(name):
    org = Organization.objects.create(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    OrganizationService.objects.create(
        organization=org,
        service_level="COMMUNITY",
        billing_source=OrganizationService.BillingSource.PAYPAL,
        status=OrganizationService.Status.ACTIVE,
        billing_reference=f"COMMUNIB-SUB-{org.id:06d}-00001",
        started_at=timezone.now(),
    )
    return org


def _admin(org, username):
    user = User.objects.create_user(username, password="Pass1234!")
    OrganizationMembership.objects.create(
        organization=org, user=user, role=OrganizationMembership.Role.ADMIN
    )
    return user


def _meeting(org, title, slides):
    meeting = Meeting.objects.create(
        organization=org,
        title=title,
        results_visible_to_community=False,
        minutes_creator=Meeting.MinutesCreator.ORGANIZER_ONLY,
        is_anonymous=True,
    )
    create_meeting_slides(meeting, slides)
    create_initial_session(meeting)
    return meeting


def _respond(meeting, slide, text="", options=None, participant=None):
    session = meeting.sessions.first()
    return MeetingResponse.objects.create(
        meeting=meeting,
        session=session,
        slide=slide,
        participant_id=participant or uuid.uuid4(),
        raw_response=text or ", ".join(options or []),
        selected_options=options or [],
    )


CHOICE_Q = {
    "slide_type": "standard",
    "prompt": "What is your top concern?",
    "question_format": "single_choice",
    "choices": ["Housing", "Schools", "Safety"],
}
TEXT_Q = {"slide_type": "standard", "prompt": "What is going well?", "question_format": "text"}


class QuestionIdentityAndTagTests(APITestCase):
    def setUp(self):
        self.org = _org("Tag Org")
        self.admin = _admin(self.org, "tag_admin")
        self.client.force_authenticate(self.admin)

    def test_question_key_normalizes_text(self):
        self.assertEqual(question_key_for("What is your Top concern?"), question_key_for("what is your top concern"))
        self.assertNotEqual(question_key_for("A"), question_key_for("B"))
        self.assertEqual(question_key_for("   "), "")

    def test_catalog_seeded_and_custom_tags(self):
        res = self.client.get(reverse("org-question-tags", kwargs={"slug": self.org.slug}))
        self.assertEqual(res.status_code, 200)
        slugs = {t["slug"] for t in res.data["tags"]}
        self.assertIn("concern", slugs)
        self.assertIn("priority", slugs)
        self.assertIn("housing", slugs)

        res = self.client.post(
            reverse("org-question-tags", kwargs={"slug": self.org.slug}),
            {"label": "Precinct 12 canvass"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["is_custom"])
        # Other orgs don't see it.
        other = _org("Other Org")
        other_admin = _admin(other, "other_admin")
        self.client.force_authenticate(other_admin)
        res = self.client.get(reverse("org-question-tags", kwargs={"slug": other.slug}))
        self.assertNotIn("precinct-12-canvass", {t["slug"] for t in res.data["tags"]})

    def test_tag_applies_across_past_and_future_uses(self):
        m1 = _meeting(self.org, "January", [CHOICE_Q])
        m2 = _meeting(self.org, "February", [CHOICE_Q])
        s1 = m1.slides.get(slide_type="standard")
        s2 = m2.slides.get(slide_type="standard")
        self.assertEqual(s1.question_key, s2.question_key)

        concern = QuestionTag.objects.get(slug="concern", organization__isnull=True)
        uses = count_other_uses(self.org, s2.question_key, exclude_slide_id=s2.id)
        self.assertEqual(uses["meetings"], 1)

        # Tag from the February slide with scope=all → January is tagged too.
        res = self.client.put(
            reverse("org-meeting-slide-tags", kwargs={"slug": self.org.slug, "pk": m2.id, "slide_pk": s2.id}),
            {"tag_ids": [concern.id], "scope": "all"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([t.slug for t in tags_for_slide(s1)], ["concern"])

        # Future use picks it up automatically, even in a survey.
        survey = Survey.objects.create(organization=self.org, title="S")
        q = SurveyQuestion.objects.create(survey=survey, text="what is your top concern", question_type="choice", choices=["Housing"])
        self.assertEqual([t.slug for t in tags_for_survey_question(q)], ["concern"])

        # scope=this only touches one use.
        housing = QuestionTag.objects.get(slug="housing", organization__isnull=True)
        set_tags(organization=self.org, question_key=s1.question_key, tag_ids=[housing.id], scope="this", slide=s1)
        self.assertEqual({t.slug for t in tags_for_slide(s1)}, {"concern", "housing"})
        self.assertEqual({t.slug for t in tags_for_slide(s2)}, {"concern"})

    def test_tags_carried_on_create_payloads(self):
        concern = QuestionTag.objects.get(slug="concern", organization__isnull=True)
        m = _meeting(self.org, "With tags", [{**TEXT_Q, "tag_ids": [concern.id]}])
        slide = m.slides.get(slide_type="standard")
        self.assertEqual([t.slug for t in tags_for_slide(slide)], ["concern"])


class DisclosureSlideTests(APITestCase):
    def setUp(self):
        self.org = _org("Disclosure Org")
        self.admin = _admin(self.org, "disc_admin")
        self.partner = _org("Partner Org")
        self.client.force_authenticate(self.admin)

    def test_every_meeting_gets_disclosure_slide_first(self):
        m = _meeting(self.org, "No info slide", [TEXT_Q])
        first = m.slides.order_by("order", "id").first()
        self.assertEqual(first.slide_type, "participant_info")
        self.assertTrue(first.config.get("disclosure"))
        self.assertEqual(m.slides.count(), 2)

    def test_existing_info_slide_is_promoted_not_duplicated(self):
        m = _meeting(
            self.org,
            "Info later",
            [
                {**TEXT_Q, "order": 0},
                {
                    "slide_type": "participant_info",
                    "order": 1,
                    "fields": [{"key": "zip", "label": "ZIP", "field_type": "text", "required": False}],
                },
            ],
        )
        slides = list(m.slides.order_by("order", "id"))
        self.assertEqual(slides[0].slide_type, "participant_info")
        self.assertEqual(slides[0].config["fields"][0]["key"], "zip")
        self.assertEqual(m.slides.filter(slide_type="participant_info").count(), 1)

    def test_disclosure_text_reflects_sharing_and_anonymity(self):
        m = _meeting(self.org, "Shared", [TEXT_Q])
        text = disclosure_text(m)
        self.assertIn("anonymous meeting", text.lower())
        self.assertIn("organizers can still read", text.lower())
        self.assertIn("every group is large enough", text)

        grant_share(meeting=m, organization=self.partner, user=self.admin)
        text = disclosure_text(m)
        self.assertIn("Results may be shared with Partner Org.", text)

        m.aggregate_sharing_notice = False
        m.is_anonymous = False
        m.save()
        text = disclosure_text(m)
        self.assertNotIn("anonymous combined results", text)
        self.assertIn("not anonymous", text)
        self.assertIn("every group is large enough", text)

        # Serializer exposes it on the first slide.
        res = self.client.get(reverse("org-meeting-detail", kwargs={"slug": self.org.slug, "pk": m.id}))
        self.assertEqual(res.status_code, 200)
        first = res.data["slides"][0]
        self.assertEqual(first["slide_type"], "participant_info")
        self.assertIn("Partner Org", first["disclosure"]["text"])
        self.assertIn("Partner Org", first["disclosure"]["shared_with"])

    def test_api_create_injects_disclosure_and_shares(self):
        from api.models import ResourceType

        ResourceType.objects.get_or_create(slug="meeting", defaults={"name": "Meeting", "is_active": True})
        res = self.client.post(
            reverse("org-meeting-create", kwargs={"slug": self.org.slug}),
            {
                "title": "API meeting",
                "results_visible_to_community": False,
                "minutes_creator": "organizer_only",
                "share_with": [self.partner.slug],
                "slides": [TEXT_Q],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        m = Meeting.objects.get(pk=res.data["meeting"]["id"])
        self.assertEqual(m.slides.order_by("order").first().slide_type, "participant_info")
        share = m.shares.get()
        self.assertTrue(share.declared_before_start)
        self.assertEqual(share.effective_access, "full")


class SharingAccessTests(APITestCase):
    def setUp(self):
        self.org = _org("Owner Org")
        self.admin = _admin(self.org, "own_admin")
        self.partner = _org("Sponsor Org")
        self.partner_admin = _admin(self.partner, "spon_admin")
        self.meeting = _meeting(self.org, "Town hall", [CHOICE_Q, TEXT_Q])
        self.choice = self.meeting.slides.get(question_format="single_choice")
        self.text = self.meeting.slides.get(question_format="text")

    def _run_meeting(self):
        now = timezone.now()
        self.meeting.started_at = now
        self.meeting.status = "ended"
        self.meeting.save()
        session = self.meeting.sessions.first()
        session.started_at = now
        session.save()
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        _respond(self.meeting, self.choice, options=["Housing"], participant=p1)
        _respond(self.meeting, self.choice, options=["Housing"], participant=p2)
        _respond(self.meeting, self.text, text="The new park is great", participant=p1)

    def test_declared_before_gives_full_after_gives_aggregate(self):
        before = grant_share(meeting=self.meeting, organization=self.partner, user=self.admin)
        self.assertEqual(before.effective_access, MeetingShare.Access.FULL)
        self._run_meeting()

        late_org = _org("Late Org")
        late = grant_share(meeting=self.meeting, organization=late_org, user=self.admin)
        self.assertFalse(late.declared_before_start)
        self.assertEqual(late.effective_access, MeetingShare.Access.AGGREGATE)

        # Recipient with FULL sees rows incl. anonymous participant id.
        self.client.force_authenticate(self.partner_admin)
        res = self.client.get(
            reverse("org-shared-meeting-results", kwargs={"slug": self.partner.slug, "meeting_pk": self.meeting.id})
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["access"], "full")
        self.assertEqual(res.data["participant_count"], 2)
        choice_slide = next(s for s in res.data["slides"] if s["slide_id"] == self.choice.id)
        self.assertEqual(choice_slide["choice_counts"]["Housing"], 2)
        self.assertEqual(choice_slide["choice_counts"]["Schools"], 0)
        self.assertEqual(len(res.data["full_rows"]), 3)
        self.assertTrue(all(r["anonymous_participant_id"] for r in res.data["full_rows"]))

        csv_res = self.client.get(
            reverse("org-shared-meeting-results", kwargs={"slug": self.partner.slug, "meeting_pk": self.meeting.id}),
            {"export": "csv"},
        )
        self.assertEqual(csv_res["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("anonymous_participant_id", csv_res.content.decode())

        # Revoke → aggregate only, but still listed.
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            reverse(
                "org-meeting-share-revoke",
                kwargs={"slug": self.org.slug, "pk": self.meeting.id, "share_pk": before.id},
            )
        )
        self.assertEqual(res.status_code, 200)
        self.client.force_authenticate(self.partner_admin)
        res = self.client.get(
            reverse("org-shared-meeting-results", kwargs={"slug": self.partner.slug, "meeting_pk": self.meeting.id})
        )
        self.assertEqual(res.data["access"], "aggregate")
        self.assertNotIn("full_rows", res.data)
        csv_res = self.client.get(
            reverse("org-shared-meeting-results", kwargs={"slug": self.partner.slug, "meeting_pk": self.meeting.id}),
            {"export": "csv"},
        )
        body = csv_res.content.decode()
        self.assertIn("TOTAL_RESPONSES", body)
        self.assertNotIn("anonymous_participant_id", body)

        listing = self.client.get(reverse("org-shared-meetings", kwargs={"slug": self.partner.slug}))
        self.assertEqual(len(listing.data["shared"]), 1)
        self.assertEqual(listing.data["shared"][0]["effective_access"], "aggregate")

    def test_regrant_after_revoke_never_restores_full(self):
        share = grant_share(meeting=self.meeting, organization=self.partner, user=self.admin)
        revoke_share(share, user=self.admin)
        share = grant_share(meeting=self.meeting, organization=self.partner, user=self.admin)
        # Meeting has not started, so a fresh grant is "before"; but a revoke is sticky.
        self.assertTrue(share.declared_before_start)
        self._run_meeting()
        revoke_share(share, user=self.admin)
        share = grant_share(meeting=self.meeting, organization=self.partner, user=self.admin)
        self.assertFalse(share.declared_before_start)
        self.assertEqual(share.effective_access, "aggregate")

    def test_unshared_org_gets_404_and_self_share_blocked(self):
        stranger = _org("Stranger")
        stranger_admin = _admin(stranger, "stranger_admin")
        self.client.force_authenticate(stranger_admin)
        res = self.client.get(
            reverse("org-shared-meeting-results", kwargs={"slug": stranger.slug, "meeting_pk": self.meeting.id})
        )
        self.assertEqual(res.status_code, 404)
        with self.assertRaises(SharingError):
            grant_share(meeting=self.meeting, organization=self.org, user=self.admin)


class ReportingAndReuseTests(APITestCase):
    def setUp(self):
        self.org = _org("Report Org")
        self.admin = _admin(self.org, "rep_admin")
        self.client.force_authenticate(self.admin)
        self.m1 = _meeting(self.org, "Jan meeting", [CHOICE_Q, TEXT_Q])
        self.m2 = _meeting(self.org, "Feb meeting", [CHOICE_Q])
        c1 = self.m1.slides.get(question_format="single_choice")
        t1 = self.m1.slides.get(question_format="text")
        c2 = self.m2.slides.get(question_format="single_choice")
        _respond(self.m1, c1, options=["Housing"])
        _respond(self.m1, c1, options=["Schools"])
        _respond(self.m1, t1, text="Roads got fixed")
        _respond(self.m2, c2, options=["Housing"])
        survey = Survey.objects.create(organization=self.org, title="Survey")
        sq = SurveyQuestion.objects.create(
            survey=survey, text="What is your top concern?", question_type="choice", choices=CHOICE_Q["choices"]
        )
        SurveyAnswer.objects.create(survey=survey, question=sq, response_session="abc", value="Safety")
        self.concern = QuestionTag.objects.get(slug="concern", organization__isnull=True)
        set_tags(organization=self.org, question_key=c1.question_key, tag_ids=[self.concern.id], scope="all")

    def test_report_groups_same_question_across_meetings_and_surveys(self):
        report = build_report(self.org, ReportFilters())
        self.assertEqual(report["totals"]["questions"], 2)
        concern_q = next(q for q in report["questions"] if q["text"] == CHOICE_Q["prompt"])
        self.assertEqual(concern_q["times_asked"], {"meetings": 2, "surveys": 1})
        self.assertEqual(concern_q["responses"], 4)
        self.assertEqual(concern_q["choice_counts"], {"Housing": 2, "Schools": 1, "Safety": 1})
        self.assertEqual([t["slug"] for t in concern_q["tags"]], ["concern"])
        self.assertEqual(len(concern_q["months"]), len(report["months"]))

        tag_row = next(t for t in report["tags"] if t["tag"]["slug"] == "concern")
        self.assertEqual(tag_row["questions"], 1)
        self.assertEqual(tag_row["responses"], 4)

        filtered = build_report(self.org, ReportFilters(tag_ids={self.concern.id}))
        self.assertEqual(filtered["totals"]["questions"], 1)

        res = self.client.get(reverse("org-reports", kwargs={"slug": self.org.slug}), {"source": "surveys"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["totals"]["responses"], 1)
        csv_res = self.client.get(reverse("org-reports", kwargs={"slug": self.org.slug}), {"export": "csv"})
        self.assertIn("question_text", csv_res.content.decode())

    def test_editing_slides_preserves_responses(self):
        m = _meeting(self.org, "Preserve", [CHOICE_Q])
        slide = m.slides.get(slide_type="standard")
        r = _respond(m, slide, options=["Housing"])
        from api.meeting_service import replace_meeting_slides

        replace_meeting_slides(
            m,
            [
                {
                    "id": slide.id,
                    "slide_type": "standard",
                    "prompt": "What is your top concern?",
                    "question_format": "single_choice",
                    "choices": ["Housing", "Schools", "Safety", "Jobs"],
                }
            ],
            user=self.admin,
        )
        r.refresh_from_db()
        self.assertEqual(r.slide_id, slide.id)
        self.assertTrue(MeetingSlide.objects.filter(pk=slide.id, is_active=True).exists())
        self.assertEqual(
            m.slides.filter(is_active=True, slide_type="standard").get().choices[-1], "Jobs"
        )

        # Removing a question deactivates it; responses stay linked.
        replace_meeting_slides(
            m,
            [{"slide_type": "standard", "prompt": "Brand new", "question_format": "text"}],
            user=self.admin,
        )
        r.refresh_from_db()
        self.assertFalse(MeetingSlide.objects.get(pk=slide.id).is_active)
        self.assertEqual(r.slide_id, slide.id)

    def test_reusable_slides_split_planned_vs_live_added(self):
        session = self.m1.sessions.first()
        session.status = "live"
        session.started_at = timezone.now()
        session.save()
        append_meeting_slides(
            self.m1,
            [{"slide_type": "standard", "prompt": "Live follow-up?", "question_format": "text"}],
            added_live=True,
        )
        res = self.client.get(
            reverse("org-meeting-reusable-slides", kwargs={"slug": self.org.slug, "pk": self.m1.id})
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual({s["prompt"] for s in res.data["planned"]}, {CHOICE_Q["prompt"], TEXT_Q["prompt"]})
        self.assertEqual([s["prompt"] for s in res.data["live_added"]], ["Live follow-up?"])
        planned_concern = next(s for s in res.data["planned"] if s["prompt"] == CHOICE_Q["prompt"])
        self.assertEqual(planned_concern["tag_ids"], [self.concern.id])
        # Disclosure slide is never offered for reuse.
        self.assertFalse(any(s["slide_type"] == "participant_info" for s in res.data["planned"]))
