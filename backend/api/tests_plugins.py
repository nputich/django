import io
import zipfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.models import Organization, OrganizationMembership, PluginInstall, VoterFile
from api.voter_nc import retain_voter_files


SAMPLE = (
    "county_desc\tncid\tlast_name\tfirst_name\tres_street_address\tvoter_status_desc\tparty_cd\n"
    "WAKE\tAA1\tDOE\tJANE\t1 MAIN ST\tACTIVE\tDEM\n"
    "WAKE\tAA2\tSMITH\tJOHN\t2 OAK ST\tACTIVE\tREP\n"
    "DURHAM\tAA3\tLEE\tANN\t3 PINE ST\tINACTIVE\tUNA\n"
    "WAKE\t\tNOID\tSKIP\t9 BAD ST\tACTIVE\tDEM\n"
)

OTHER = (
    "county_desc\tncid\tlast_name\tfirst_name\tres_street_address\tvoter_status_desc\tparty_cd\n"
    "WAKE\tAA1\tDOE\tJANET\t1 MAIN ST\tACTIVE\tDEM\n"
    "DURHAM\tAA3\tLEE\tANN\t3 PINE ST\tINACTIVE\tUNA\n"
    "WAKE\tAA4\tNGUYEN\tKIM\t4 ELM ST\tACTIVE\tDEM\n"
)


@override_settings(VOTER_PARSE_INLINE=True)
class PluginWarehouseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="person", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.org = Organization.objects.create(name="Civic Org", slug="civic-org")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
        )
        self.client.force_authenticate(self.user)

    def test_personal_and_org_installs_are_separate(self):
        catalog = self.client.get(reverse("me-plugins"))
        self.assertEqual(catalog.status_code, status.HTTP_200_OK)
        keys = [row["key"] for row in catalog.data["plugins"]]
        self.assertIn("nc_voter_powerquery", keys)
        self.assertFalse(catalog.data["plugins"][0]["installed"])

        added = self.client.post(
            reverse("me-plugins"),
            {"key": "nc_voter_powerquery", "comment": "County chair, need the roll."},
            format="json",
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)
        self.assertEqual(added.data["status"], "pending")
        self.assertEqual(added.data["request_comment"], "County chair, need the roll.")
        self.assertFalse(
            PluginInstall.objects.filter(plugin__key="nc_voter_powerquery", organization=self.org).exists()
        )

        org_added = self.client.post(
            reverse("org-plugins", kwargs={"slug": self.org.slug}),
            {"key": "nc_voter_powerquery"},
            format="json",
        )
        self.assertEqual(org_added.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            PluginInstall.objects.filter(plugin__key="nc_voter_powerquery").count(),
            2,
        )

        self.client.force_authenticate(self.other)
        denied = self.client.get(reverse("org-plugins", kwargs={"slug": self.org.slug}))
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def _approve_personal(self):
        PluginInstall.objects.filter(
            plugin__key="nc_voter_powerquery", user=self.user
        ).update(status="approved")

    def _upload(self, url, text, source="owner_upload"):
        payload = {"file": io.BytesIO(text.encode("utf-8")), "source": source}
        payload["file"].name = "voters.txt"
        return self.client.post(url, payload, format="multipart")

    def test_parse_compare_query_list_and_county_packet(self):
        self.client.post(reverse("me-plugins"), {"key": "nc_voter_powerquery"}, format="json")
        self._approve_personal()
        uploaded = self._upload(reverse("me-voter-files"), SAMPLE)
        self.assertEqual(uploaded.status_code, status.HTTP_201_CREATED)
        self.assertEqual(uploaded.data["status"], VoterFile.Status.READY)
        self.assertEqual(uploaded.data["row_count"], 3)
        self.assertEqual(uploaded.data["rows_skipped"], 1)
        file_a = uploaded.data["id"]

        self.client.force_authenticate(self.staff)
        official = self._upload(reverse("voter-official-file"), OTHER)
        self.assertEqual(official.status_code, status.HTTP_201_CREATED)
        file_b = official.data["id"]

        self.client.force_authenticate(self.user)
        hidden = self.client.get(reverse("me-voter-files"))
        ids = {row["id"] for row in hidden.data["files"]}
        self.assertIn(file_b, ids)

        self.client.force_authenticate(self.other)
        blocked = self._upload(reverse("me-voter-files"), SAMPLE)
        self.assertEqual(blocked.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.user)
        compared = self.client.post(
            reverse("me-voter-compare"),
            {"file_a": file_a, "file_b": file_b, "county": "WAKE"},
            format="json",
        )
        self.assertEqual(compared.status_code, status.HTTP_200_OK)
        self.assertEqual(compared.data["only_in_a_count"], 1)
        self.assertEqual(compared.data["only_in_b_count"], 1)
        self.assertEqual(compared.data["changed_count"], 1)

        queried = self.client.post(
            reverse("me-voter-query", kwargs={"file_id": file_a}),
            {"county": "DURHAM", "filters": [{"field": "party", "op": "eq", "value": "UNA"}]},
            format="json",
        )
        self.assertEqual(queried.data["count"], 1)
        self.assertEqual(queried.data["rows"][0]["ncid"], "AA3")

        exported = self.client.post(
            reverse("me-voter-export", kwargs={"file_id": file_a}),
            {"county": "WAKE"},
            format="json",
        )
        self.assertEqual(exported.status_code, status.HTTP_200_OK)
        self.assertIn("AA1", exported.content.decode())

        listing = "ncid,last_name,first_name\nAA2,SMITH,JOHN\nZZ9,NOBODY,HERE\n"
        matched_file = self._upload(reverse("me-voter-files"), listing, source="comparison_list")
        self.assertEqual(matched_file.data["status"], "ready")
        match = self.client.post(
            reverse("me-voter-match"),
            {"file_id": file_a, "list_id": matched_file.data["id"]},
            format="json",
        )
        self.assertEqual(match.data["matched_count"], 1)
        self.assertEqual(match.data["unmatched_count"], 1)

        packet = self.client.post(
            reverse("me-voter-county-packets"),
            {"file_a": file_a, "file_b": file_b, "missing_side": "only_in_a"},
            format="json",
        )
        self.assertEqual(packet.status_code, status.HTTP_200_OK)
        archive = zipfile.ZipFile(io.BytesIO(packet.content))
        names = archive.namelist()
        self.assertTrue(any(name.startswith("WAKE") for name in names))
        wake = archive.read([name for name in names if name.startswith("WAKE")][0]).decode()
        self.assertIn("AA2", wake)

    def test_bad_header_fails_parse(self):
        self.client.post(reverse("me-plugins"), {"key": "nc_voter_powerquery"}, format="json")
        self._approve_personal()
        bad = self._upload(reverse("me-voter-files"), "name,city\nA,B\n")

    def test_only_communibetter_state_or_national_admins_review(self):
        asked = self.client.post(
            reverse("me-plugins"),
            {"key": "nc_voter_powerquery", "comment": "Please approve."},
            format="json",
        )
        install_id = PluginInstall.objects.get(plugin__key="nc_voter_powerquery", user=self.user).id
        hidden = self.client.get(reverse("org-plugin-access-requests", kwargs={"slug": self.org.slug}))
        self.assertEqual(hidden.status_code, status.HTTP_403_FORBIDDEN)

        state = Organization.objects.create(
            name="Communibetter North Carolina",
            slug="communibetter-north-carolina-test",
            is_communibetter=True,
            geographic_scope=Organization.GeographicScope.STATE_PROVINCE,
        )
        OrganizationMembership.objects.create(
            organization=state,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
        )
        queue = self.client.get(reverse("org-plugin-access-requests", kwargs={"slug": state.slug}))
        self.assertEqual(queue.status_code, status.HTTP_200_OK)
        self.assertEqual(queue.data["requests"][0]["request_comment"], "Please approve.")

        county = Organization.objects.create(
            name="Communibetter Forsyth",
            slug="communibetter-forsyth-test",
            is_communibetter=True,
            geographic_scope=Organization.GeographicScope.LOCAL,
        )
        OrganizationMembership.objects.create(
            organization=county,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
        )
        county_view = self.client.get(reverse("org-plugin-access-requests", kwargs={"slug": county.slug}))
        self.assertEqual(county_view.status_code, status.HTTP_403_FORBIDDEN)

        decided = self.client.post(
            reverse("org-plugin-access-decision", kwargs={"slug": state.slug, "pk": install_id}),
            {"decision": "approve", "comment": "Confirmed chair."},
            format="json",
        )
        self.assertEqual(decided.status_code, status.HTTP_200_OK)
        self.assertEqual(decided.data["decision_comment"], "Confirmed chair.")
        self.assertEqual(decided.data["status"], "approved")
        self.assertEqual(asked.data["status"], "pending")

    def test_official_retention_keeps_two_ready_files(self):
        from django.utils import timezone

        files = []
        for index in range(3):
            item = VoterFile.objects.create(
                source=VoterFile.Source.OFFICIAL,
                original_filename=f"ncvoter_{index}.txt",
                stored_path="",
                status=VoterFile.Status.READY,
                row_count=1,
                parsed_at=timezone.now(),
                is_current_official=index == 2,
            )
            files.append(item)
        retain_voter_files(files[-1])
        remaining = list(
            VoterFile.objects.filter(source=VoterFile.Source.OFFICIAL).order_by("id").values_list("id", flat=True)
        )
        self.assertEqual(remaining, [files[1].id, files[2].id])
        self.assertTrue(VoterFile.objects.get(pk=files[2].id).is_current_official)
