from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.inbox_service import (
    get_organization_mailbox,
    get_personal_mailbox,
    list_conversations_for_mailbox,
)
from api.models import (
    ConversationParticipant,
    InboxMessage,
    Organization,
    OrganizationMembership,
)


class UnifiedInboxTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Pass1234!")
        self.bob = User.objects.create_user("bob", password="Pass1234!")
        self.org = Organization.objects.create(
            name="Forsyth Example", slug="forsyth-example", is_active=True
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.alice,
            role=OrganizationMembership.Role.ADMIN,
        )
        self.me_inbox = reverse("me-inbox")
        self.me_drafts = reverse("me-inbox-drafts")
        self.org_inbox = reverse("org-inbox", kwargs={"slug": self.org.slug})
        self.org_drafts = reverse("org-inbox-drafts", kwargs={"slug": self.org.slug})

    def test_personal_and_org_share_same_message_tables(self):
        self.client.force_authenticate(self.bob)
        res = self.client.post(
            self.me_inbox,
            {
                "subject": "Hello org",
                "body": "Can we partner?",
                "to_organization_slug": self.org.slug,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Bob sees it in primary (sent).
        bob_box = get_personal_mailbox(self.bob)
        bob_primary = list(
            list_conversations_for_mailbox(
                bob_box, folder=ConversationParticipant.Folder.PRIMARY
            )
        )
        self.assertEqual(len(bob_primary), 1)

        # Org sees first contact in unknown inbox.
        org_box = get_organization_mailbox(self.org)
        org_unknown = list(
            list_conversations_for_mailbox(
                org_box, folder=ConversationParticipant.Folder.UNKNOWN
            )
        )
        self.assertEqual(len(org_unknown), 1)
        self.assertEqual(InboxMessage.objects.filter(status="sent").count(), 1)

    def test_draft_save_and_send(self):
        self.client.force_authenticate(self.alice)
        draft = self.client.post(
            self.me_drafts,
            {
                "subject": "Draft to Bob",
                "body": "Still writing…",
                "to_username": "bob",
            },
            format="json",
        )
        self.assertEqual(draft.status_code, status.HTTP_201_CREATED)
        draft_id = draft.data["id"]
        self.assertEqual(
            InboxMessage.objects.get(pk=draft_id).status, InboxMessage.Status.DRAFT
        )

        patch = self.client.patch(
            reverse("me-inbox-draft-detail", kwargs={"pk": draft_id}),
            {"subject": "Draft to Bob", "body": "Ready to send.", "to_username": "bob"},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)

        sent = self.client.post(
            reverse("me-inbox-draft-send", kwargs={"pk": draft_id}), format="json"
        )
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertEqual(
            InboxMessage.objects.get(pk=draft_id).status, InboxMessage.Status.SENT
        )

        # Bob gets it in unknown (no prior contact).
        self.client.force_authenticate(self.bob)
        unknown = self.client.get(self.me_inbox, {"folder": "unknown"})
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(len(unknown.data["conversations"]), 1)

        conversation_id = unknown.data["conversations"][0]["id"]
        accept = self.client.post(
            reverse("me-inbox-accept", kwargs={"pk": conversation_id}), format="json"
        )
        self.assertEqual(accept.status_code, status.HTTP_200_OK)
        primary = self.client.get(self.me_inbox, {"folder": "primary"})
        self.assertEqual(len(primary.data["conversations"]), 1)

    def test_ban_hides_from_blocked_user(self):
        self.client.force_authenticate(self.bob)
        sent = self.client.post(
            self.me_inbox,
            {
                "subject": "Hi",
                "body": "Hello alice",
                "to_username": "alice",
            },
            format="json",
        )
        self.assertEqual(sent.status_code, status.HTTP_201_CREATED)
        conversation_id = sent.data["id"]

        self.client.force_authenticate(self.alice)
        ban = self.client.post(
            reverse("me-inbox-ban", kwargs={"pk": conversation_id}), format="json"
        )
        self.assertEqual(ban.status_code, status.HTTP_200_OK)

        # Bob can no longer see the thread or message Alice.
        self.client.force_authenticate(self.bob)
        unknown = self.client.get(self.me_inbox, {"folder": "unknown"})
        self.assertEqual(unknown.data["conversations"], [])
        blocked_send = self.client.post(
            self.me_inbox,
            {
                "subject": "Again",
                "body": "Still here",
                "to_username": "alice",
            },
            format="json",
        )
        self.assertEqual(blocked_send.status_code, status.HTTP_400_BAD_REQUEST)

    def test_read_keeps_conversation_in_folder(self):
        self.client.force_authenticate(self.bob)
        sent = self.client.post(
            self.me_inbox,
            {
                "subject": "Keep me",
                "body": "I should stay after read",
                "to_username": "alice",
            },
            format="json",
        )
        conversation_id = sent.data["id"]

        self.client.force_authenticate(self.alice)
        before = self.client.get(self.me_inbox, {"folder": "unknown"})
        self.assertEqual(len(before.data["conversations"]), 1)
        self.assertTrue(before.data["conversations"][0]["unread"])

        detail = self.client.get(
            reverse("me-inbox-conversation", kwargs={"pk": conversation_id})
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        after = self.client.get(self.me_inbox, {"folder": "unknown"})
        self.assertEqual(len(after.data["conversations"]), 1)
        self.assertFalse(after.data["conversations"][0]["unread"])
