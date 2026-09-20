from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Organization,
    OrganizationMembership,
    OrganizationRelationship,
)
from api.relationship_service import (
    RelationshipError,
    accept_relationship,
    request_relationship,
)


def _org(name):
    return Organization.objects.create(
        name=name, slug=name.lower().replace(" ", "-"), is_active=True
    )


def _admin(org, username):
    user = User.objects.create_user(username, password="Pass1234!")
    OrganizationMembership.objects.create(
        organization=org, user=user, role=OrganizationMembership.Role.ADMIN
    )
    return user


class RelationshipFlowTests(APITestCase):
    def setUp(self):
        self.parent = _org("State Party")
        self.child = _org("County Chapter")
        self.other = _org("Other Group")
        self.parent_admin = _admin(self.parent, "parent_admin")
        self.child_admin = _admin(self.child, "child_admin")
        self.other_admin = _admin(self.other, "other_admin")

    def _list_url(self, org):
        return reverse("org-relationships", kwargs={"slug": org.slug})

    def _action_url(self, org, rel_id, action):
        return reverse(
            f"org-relationship-{action}", kwargs={"slug": org.slug, "pk": rel_id}
        )

    def test_request_accept_syncs_parent_and_posts_inbox_messages(self):
        self.client.force_authenticate(self.parent_admin)
        res = self.client.post(
            self._list_url(self.parent),
            {"target_slug": self.child.slug, "direction": "parent_of", "note": "Join us"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        rel_id = res.data["id"]
        self.assertEqual(res.data["status"], "pending")
        self.assertTrue(res.data["can_withdraw"])
        self.assertFalse(res.data["can_respond"])

        # Child sees it as incoming and can accept via the inbox thread.
        self.client.force_authenticate(self.child_admin)
        listing = self.client.get(self._list_url(self.child))
        self.assertEqual(len(listing.data["incoming_pending"]), 1)
        self.assertTrue(listing.data["incoming_pending"][0]["can_respond"])

        conv_id = res.data["conversation_id"]
        thread = self.client.get(
            reverse("org-inbox-conversation", kwargs={"slug": self.child.slug, "pk": conv_id})
        )
        self.assertEqual(thread.status_code, status.HTTP_200_OK)
        self.assertEqual(thread.data["relationship"]["id"], rel_id)
        self.assertTrue(thread.data["relationship"]["can_respond"])
        self.assertIn("Join us", thread.data["messages"][0]["body"])

        accept = self.client.post(self._action_url(self.child, rel_id, "accept"))
        self.assertEqual(accept.status_code, status.HTTP_200_OK, accept.data)
        self.assertEqual(accept.data["status"], "accepted")

        self.child.refresh_from_db()
        self.assertEqual(self.child.parent_organization_id, self.parent.id)

        # Acceptance posted a follow-up message in the same thread.
        thread = self.client.get(
            reverse("org-inbox-conversation", kwargs={"slug": self.child.slug, "pk": conv_id})
        )
        self.assertEqual(len(thread.data["messages"]), 2)
        self.assertFalse(thread.data["relationship"]["can_respond"])

        # Public hub shows it.
        hub = self.client.get(reverse("org-hub", kwargs={"slug": self.child.slug}))
        self.assertEqual(hub.data["relationships"]["parent"]["slug"], self.parent.slug)
        hub = self.client.get(reverse("org-hub", kwargs={"slug": self.parent.slug}))
        self.assertEqual(hub.data["relationships"]["chapters"][0]["slug"], self.child.slug)

    def test_only_recipient_can_accept(self):
        self.client.force_authenticate(self.parent_admin)
        res = self.client.post(
            self._list_url(self.parent),
            {"target_slug": self.child.slug, "direction": "parent_of"},
            format="json",
        )
        rel_id = res.data["id"]
        # Requester cannot accept its own request.
        forbidden = self.client.post(self._action_url(self.parent, rel_id, "accept"))
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        # Unrelated org cannot even see it.
        self.client.force_authenticate(self.other_admin)
        missing = self.client.post(self._action_url(self.other, rel_id, "accept"))
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_decline_and_end_clear_parent_pointer(self):
        rel = request_relationship(
            requesting_org=self.child,
            target_org=self.parent,
            direction="child_of",
            user=self.child_admin,
        )
        self.assertEqual(rel.from_organization, self.parent)
        self.assertEqual(rel.to_organization, self.child)

        self.client.force_authenticate(self.parent_admin)
        declined = self.client.post(self._action_url(self.parent, rel.id, "decline"))
        self.assertEqual(declined.status_code, status.HTTP_200_OK)
        self.assertEqual(declined.data["status"], "declined")

        # A new request can be made after decline, then accepted and ended.
        rel2 = request_relationship(
            requesting_org=self.child,
            target_org=self.parent,
            direction="child_of",
            user=self.child_admin,
        )
        accept_relationship(rel2, acting_org=self.parent, user=self.parent_admin)
        self.child.refresh_from_db()
        self.assertEqual(self.child.parent_organization_id, self.parent.id)

        self.client.force_authenticate(self.child_admin)
        ended = self.client.post(self._action_url(self.child, rel2.id, "end"))
        self.assertEqual(ended.status_code, status.HTTP_200_OK)
        self.child.refresh_from_db()
        self.assertIsNone(self.child.parent_organization_id)

    def test_guards_single_parent_duplicate_and_cycle(self):
        rel = request_relationship(
            requesting_org=self.parent,
            target_org=self.child,
            direction="parent_of",
            user=self.parent_admin,
        )
        # Second parent for the same child while pending.
        with self.assertRaises(RelationshipError) as ctx:
            request_relationship(
                requesting_org=self.other,
                target_org=self.child,
                direction="parent_of",
                user=self.other_admin,
            )
        self.assertEqual(ctx.exception.code, "parent_exists")

        accept_relationship(rel, acting_org=self.child, user=self.child_admin)

        # Duplicate partner request either direction.
        request_relationship(
            requesting_org=self.parent,
            target_org=self.other,
            direction="partner",
            user=self.parent_admin,
        )
        with self.assertRaises(RelationshipError) as ctx:
            request_relationship(
                requesting_org=self.other,
                target_org=self.parent,
                direction="partner",
                user=self.other_admin,
            )
        self.assertEqual(ctx.exception.code, "duplicate_relationship")

        # Cycle: child cannot become parent of its own parent.
        with self.assertRaises(RelationshipError) as ctx:
            request_relationship(
                requesting_org=self.child,
                target_org=self.parent,
                direction="parent_of",
                user=self.child_admin,
            )
        self.assertIn(ctx.exception.code, {"cycle", "parent_exists"})

        # Self relationship.
        with self.assertRaises(RelationshipError):
            request_relationship(
                requesting_org=self.parent,
                target_org=self.parent,
                direction="partner",
                user=self.parent_admin,
            )

    def test_private_relationship_hidden_from_hub(self):
        rel = request_relationship(
            requesting_org=self.parent,
            target_org=self.other,
            direction="sponsor_of",
            user=self.parent_admin,
            public=False,
        )
        accept_relationship(rel, acting_org=self.other, user=self.other_admin)
        hub = self.client.get(reverse("org-hub", kwargs={"slug": self.other.slug}))
        self.assertEqual(hub.data["relationships"]["sponsors"], [])

        self.client.force_authenticate(self.other_admin)
        res = self.client.patch(
            reverse(
                "org-relationship-detail",
                kwargs={"slug": self.other.slug, "pk": rel.id},
            ),
            {"public": True},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        hub = self.client.get(reverse("org-hub", kwargs={"slug": self.other.slug}))
        self.assertEqual(hub.data["relationships"]["sponsors"][0]["slug"], self.parent.slug)

    def test_withdraw_pending_request(self):
        rel = request_relationship(
            requesting_org=self.parent,
            target_org=self.child,
            direction="parent_of",
            user=self.parent_admin,
        )
        self.client.force_authenticate(self.parent_admin)
        res = self.client.post(self._action_url(self.parent, rel.id, "withdraw"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "ended")
        self.assertEqual(
            OrganizationRelationship.objects.filter(
                status__in=OrganizationRelationship.OPEN_STATUSES
            ).count(),
            0,
        )

    def test_lookup_excludes_self_and_requires_two_chars(self):
        self.client.force_authenticate(self.parent_admin)
        res = self.client.get(reverse("org-lookup"), {"q": "c", "exclude": self.parent.slug})
        self.assertEqual(res.data["results"], [])
        res = self.client.get(reverse("org-lookup"), {"q": "co", "exclude": self.parent.slug})
        slugs = {r["slug"] for r in res.data["results"]}
        self.assertIn(self.child.slug, slugs)
        self.assertNotIn(self.parent.slug, slugs)
