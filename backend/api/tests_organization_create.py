from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    AccessCode,
    GeographicArea,
    Organization,
    OrganizationMembership,
    OrgCategory,
    ResourceType,
)
from api.org_access import generate_community_code, validate_community_code
from api.organization_create import unique_organization_slug


class OrganizationCreateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="creator", password="CreatorPass2026!"
        )
        self.url = reverse("organization-create")
        ResourceType.objects.get_or_create(
            slug="organization", defaults={"name": "Organization", "is_active": True}
        )
        self.us = GeographicArea.objects.create(
            name="United States",
            slug="united-states",
            area_type=GeographicArea.AreaType.COUNTRY,
            country_code="US",
        )
        self.nc = GeographicArea.objects.create(
            name="North Carolina",
            slug="north-carolina",
            area_type=GeographicArea.AreaType.ADMIN1,
            parent=self.us,
            country_code="US",
        )
        self.forsyth = GeographicArea.objects.create(
            name="Forsyth County",
            slug="forsyth-county",
            area_type=GeographicArea.AreaType.ADMIN2,
            parent=self.nc,
            country_code="US",
        )
        self.politics = OrgCategory.objects.create(
            name="Politics", slug="politics", sort_order=1
        )
        self.parties = OrgCategory.objects.create(
            name="Political Parties",
            slug="political-parties",
            parent=self.politics,
            sort_order=1,
        )

    def _placement_payload(self, **overrides):
        payload = {
            "name": "Forsyth County Democratic Party",
            "description": "Local demo",
            "geographic_scope": "local",
            "country_id": self.us.id,
            "state_id": self.nc.id,
            "county_id": self.forsyth.id,
            "primary_subcategory_id": self.parties.id,
        }
        payload.update(overrides)
        return payload

    def test_requires_auth(self):
        res = self.client.post(self.url, {"name": "New Org"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creates_org_with_community_code_and_placement(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(
            self.url,
            self._placement_payload(community_code="FORSYTHDEMS"),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["name"], "Forsyth County Democratic Party")
        self.assertEqual(res.data["role"], "owner")
        self.assertEqual(res.data["community_code"], "FORSYTHDEMS")
        self.assertTrue(res.data["directory_placement"]["is_complete"])
        self.assertIn("Forsyth County", res.data["directory_placement"]["summary"])

        org = Organization.objects.get(slug=res.data["slug"])
        self.assertEqual(org.geographic_scope, "local")
        self.assertEqual(org.service_area_id, self.forsyth.id)
        self.assertEqual(org.primary_subcategory_id, self.parties.id)
        self.assertTrue(
            AccessCode.objects.filter(
                organization=org,
                code="FORSYTHDEMS",
                resource_type__slug="organization",
                is_primary=True,
            ).exists()
        )
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=org,
                user=self.user,
                role=OrganizationMembership.Role.OWNER,
            ).exists()
        )

    def test_generates_community_code_when_blank(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(self.url, self._placement_payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertTrue(res.data["community_code"])
        self.assertRegex(res.data["community_code"], r"^[A-Z0-9-]{3,32}$")

    def test_rejects_duplicate_community_code(self):
        self.client.force_authenticate(self.user)
        first = self.client.post(
            self.url,
            self._placement_payload(community_code="SHAREDCODE", name="Org One"),
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        second = self.client.post(
            self.url,
            self._placement_payload(community_code="sharedcode", name="Org Two"),
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_reserved_billing_code_as_community_code(self):
        self.client.force_authenticate(self.user)
        with self.settings(COMMUNIB_BASIC_ACCESS_CODE="SUPERBASIC"):
            res = self.client.post(
                self.url,
                self._placement_payload(community_code="SUPERBASIC"),
                format="json",
            )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unique_slug_collision(self):
        Organization.objects.create(name="Demo Org", slug="demo-org")
        self.assertEqual(unique_organization_slug("Demo Org"), "demo-org-2")

    def test_rejects_blank_name(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(
            self.url, self._placement_payload(name=" "), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dashboard_shows_code_and_placement(self):
        self.client.force_authenticate(self.user)
        created = self.client.post(
            self.url,
            self._placement_payload(community_code="DASHCODE1"),
            format="json",
        )
        slug = created.data["slug"]
        dash = self.client.get(f"/api/organizations/{slug}/dashboard/")
        self.assertEqual(dash.status_code, status.HTTP_200_OK)
        self.assertEqual(dash.data["community_code"], "DASHCODE1")
        self.assertTrue(dash.data["directory_placement"]["is_complete"])

    def test_patch_directory_placement(self):
        self.client.force_authenticate(self.user)
        created = self.client.post(
            self.url,
            self._placement_payload(community_code="PLACECODE"),
            format="json",
        )
        slug = created.data["slug"]
        education = OrgCategory.objects.create(
            name="Education", slug="education", sort_order=2
        )
        parents = OrgCategory.objects.create(
            name="Parent Organizations",
            slug="parent-organizations",
            parent=education,
        )
        res = self.client.patch(
            f"/api/organizations/{slug}/directory-placement/",
            {
                "geographic_scope": "state_province",
                "country_id": self.us.id,
                "state_id": self.nc.id,
                "primary_subcategory_id": parents.id,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        org = Organization.objects.get(slug=slug)
        self.assertEqual(org.geographic_scope, "state_province")
        self.assertEqual(org.service_area_id, self.nc.id)
        self.assertEqual(org.primary_subcategory_id, parents.id)

    def test_generate_community_code_helper(self):
        code = generate_community_code("Forsyth County Democratic Party")
        self.assertTrue(code.startswith("FCDP-") or code.startswith("F"))
        validate_community_code(code)
