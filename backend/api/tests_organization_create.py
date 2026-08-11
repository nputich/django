from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Organization, OrganizationMembership
from api.organization_create import unique_organization_slug


class OrganizationCreateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="creator", password="CreatorPass2026!"
        )
        self.url = reverse("organization-create")

    def test_requires_auth(self):
        res = self.client.post(self.url, {"name": "New Org"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creates_org_and_admin_membership(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(
            self.url,
            {"name": "Forsyth Example Organization", "description": "Local demo"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["name"], "Forsyth Example Organization")
        self.assertEqual(res.data["role"], "owner")
        self.assertTrue(res.data["slug"])
        org = Organization.objects.get(slug=res.data["slug"])
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=org,
                user=self.user,
                role=OrganizationMembership.Role.OWNER,
            ).exists()
        )
        self.assertTrue(hasattr(org, "board"))

    def test_unique_slug_collision(self):
        Organization.objects.create(name="Demo Org", slug="demo-org")
        self.assertEqual(unique_organization_slug("Demo Org"), "demo-org-2")

    def test_rejects_blank_name(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(self.url, {"name": " "}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
