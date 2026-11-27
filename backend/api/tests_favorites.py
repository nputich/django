from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.models import Organization, OrganizationFavorite


class OrganizationFavoriteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="person", password="pass")
        self.org = Organization.objects.create(name="River Club", slug="river-club")

    def test_star_lists_on_home_and_unstar_removes(self):
        self.client.force_authenticate(self.user)
        add = self.client.post(reverse("org-favorite", kwargs={"slug": "river-club"}))
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)
        self.assertTrue(add.data["is_favorite"])

        listed = self.client.get(reverse("my-favorites"))
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual([row["slug"] for row in listed.data["favorites"]], ["river-club"])

        hub = self.client.get(reverse("org-hub", kwargs={"slug": "river-club"}))
        self.assertTrue(hub.data["is_favorite"])

        again = self.client.post(reverse("org-favorite", kwargs={"slug": "river-club"}))
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(OrganizationFavorite.objects.filter(user=self.user).count(), 1)

        removed = self.client.delete(reverse("org-favorite", kwargs={"slug": "river-club"}))
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertFalse(removed.data["is_favorite"])
        self.assertEqual(self.client.get(reverse("my-favorites")).data["favorites"], [])

    def test_guest_hub_is_not_favorited(self):
        hub = self.client.get(reverse("org-hub", kwargs={"slug": "river-club"}))
        self.assertEqual(hub.status_code, status.HTTP_200_OK)
        self.assertFalse(hub.data["is_favorite"])
