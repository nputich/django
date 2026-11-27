from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Measure,
    Organization,
    OrganizationMembership,
    PluginDefinition,
    PluginInstall,
)


class MeasureReadingPluginTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Readers", slug="readers", status=Organization.Status.ACTIVE)
        self.admin = User.objects.create_user("reader_admin", password="Pass1234!")
        self.member = User.objects.create_user("reader_member", password="Pass1234!")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Role.ADMIN
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member, role=OrganizationMembership.Role.MEMBER
        )
        plugin, _created = PluginDefinition.objects.get_or_create(
            key="measure_reading",
            defaults={
                "name": "Measure Reading",
                "audience": "organization",
                "enabled": True,
            },
        )
        PluginInstall.objects.create(
            plugin=plugin,
            organization=self.org,
            status=PluginInstall.Status.APPROVED,
            installed_by=self.admin,
        )
        self.client.force_authenticate(self.admin)

    @patch("api.measure_views.summarize_text", return_value="Funds bridge repair.")
    @patch("api.measure_views.bill_text", return_value="SECTION 1. The state shall repair bridges.")
    @patch(
        "api.measure_views.bill_history",
        return_value={
            "title": "Bridge Repair",
            "source_url": "https://www.ncleg.gov/BillLookUp/2025/H2",
        },
    )
    def test_draft_can_be_edited_and_locks_when_voting_starts(self, _history, _text, _summary):
        created = self.client.post(
            reverse("org-measures", kwargs={"slug": self.org.slug}),
            {"session_year": 2025, "chamber": "H", "bill_number": 2},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["summary"], "Funds bridge repair.")
        measure_id = created.data["id"]

        edited = self.client.patch(
            reverse("org-measure", kwargs={"slug": self.org.slug, "pk": measure_id}),
            {"body": "SECTION 1. Counties shall repair bridges."},
            format="json",
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        self.assertIn("Counties", edited.data["body"])

        self.client.post(
            reverse("org-measure-members", kwargs={"slug": self.org.slug, "pk": measure_id}),
            {"user_id": self.member.id, "label": "Alex"},
            format="json",
        )
        self.client.force_authenticate(self.admin)
        self.client.post(reverse("org-measure-voting", kwargs={"slug": self.org.slug, "pk": measure_id}))
        locked = self.client.patch(
            reverse("org-measure", kwargs={"slug": self.org.slug, "pk": measure_id}),
            {"body": "nope"},
            format="json",
        )
        self.assertEqual(locked.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.member)
        proposed = self.client.post(
            reverse("org-measure-revisions", kwargs={"slug": self.org.slug, "pk": measure_id}),
            {"body": "SECTION 1. Counties shall fund bridges."},
            format="json",
        )
        self.assertEqual(proposed.status_code, status.HTTP_200_OK)
        self.assertIn("-SECTION 1. Counties shall repair bridges.", proposed.data["diff"])
        self.assertTrue(proposed.data["members"][0]["has_revision"])
        self.assertEqual(Measure.objects.get(pk=measure_id).status, "voting")
