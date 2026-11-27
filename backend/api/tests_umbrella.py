from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.billing_service import get_current_service_level
from api.inbox_service import get_organization_mailbox
from api.models import (
    InboxMessage,
    Organization,
    OrganizationMembership,
    OrganizationRelationship,
    OrganizationService,
)
from api.umbrella_service import (
    UmbrellaError,
    create_license,
    normalize_umbrella_code,
    redeem_umbrella_code,
)
from api.usage_service import consume_board_post, get_or_create_usage_period, serialize_usage


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


def _paid(org, level="COMMUNITY"):
    return OrganizationService.objects.create(
        organization=org,
        service_level=level,
        billing_source=OrganizationService.BillingSource.PAYPAL,
        status=OrganizationService.Status.ACTIVE,
        billing_reference=f"COMMUNIB-SUB-{org.id:06d}-00001",
        started_at=timezone.now(),
    )


class UmbrellaLicenseTests(APITestCase):
    def setUp(self):
        self.licensor = _org("State Federation")
        self.member = _org("Local Chapter")
        self.other = _org("Other Org")
        self.licensor_admin = _admin(self.licensor, "lic_admin")
        self.member_admin = _admin(self.member, "mem_admin")
        self.other_admin = _admin(self.other, "oth_admin")
        self.backing = _paid(self.licensor)

    def test_normalize_code_variants(self):
        self.assertEqual(normalize_umbrella_code("umb-abcd-2345"), "UMB-ABCD-2345")
        self.assertEqual(normalize_umbrella_code("UMBABCD2345"), "UMB-ABCD-2345")
        self.assertEqual(normalize_umbrella_code(" abcd 2345 "), "UMB-ABCD-2345")

    def test_free_org_cannot_create_license(self):
        with self.assertRaises(UmbrellaError) as ctx:
            create_license(organization=self.other, user=self.other_admin)
        self.assertEqual(ctx.exception.code, "paid_plan_required")

    def test_redeem_grants_level_relationship_and_notifies_licensor(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        self.assertEqual(get_current_service_level(self.member), "FREE")

        self.client.force_authenticate(self.member_admin)
        res = self.client.post(
            reverse("org-umbrella-redeem", kwargs={"slug": self.member.slug}),
            {"umbrella_code": license.code.lower()},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["effective_service_level"], "COMMUNITY")
        self.assertEqual(res.data["coverage"]["licensor"]["slug"], self.licensor.slug)

        rel = OrganizationRelationship.objects.get(
            kind=OrganizationRelationship.Kind.UMBRELLA_MEMBER, to_organization=self.member
        )
        self.assertEqual(rel.status, "accepted")
        self.assertEqual(rel.from_organization, self.licensor)

        # FYI landed in the licensor's org inbox.
        licensor_box = get_organization_mailbox(self.licensor)
        self.assertTrue(
            InboxMessage.objects.filter(
                conversation__participants__mailbox=licensor_box,
                subject__icontains="joined your umbrella",
            ).exists()
        )

        # Billing page for the member shows coverage; for the licensor shows can_offer.
        billing = self.client.get(reverse("org-billing", kwargs={"slug": self.member.slug}))
        self.assertEqual(billing.data["umbrella"]["coverage"]["licensor"]["slug"], self.licensor.slug)
        self.assertTrue(billing.data["usage"]["pooled"])

        self.client.force_authenticate(self.licensor_admin)
        billing = self.client.get(reverse("org-billing", kwargs={"slug": self.licensor.slug}))
        self.assertTrue(billing.data["umbrella"]["can_offer"])
        self.assertTrue(billing.data["umbrella"]["has_license"])

    def test_usage_pools_against_licensor_and_records_member_breakdown(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        redeem_umbrella_code(organization=self.member, user=self.member_admin, code=license.code)

        consume_board_post(self.member)
        consume_board_post(self.member)
        consume_board_post(self.licensor)

        pool = get_or_create_usage_period(self.licensor)
        own = get_or_create_usage_period(self.member)
        self.assertEqual(pool.board_posts_used, 3)
        self.assertEqual(own.board_posts_used, 2)

        usage = serialize_usage(self.member)
        self.assertTrue(usage["pooled"])
        self.assertEqual(usage["service_level"], "COMMUNITY")
        self.assertEqual(usage["board_posts"]["used"], 3)
        self.assertEqual(usage["own_usage"]["board_posts"], 2)

        # Licensor portal lists the member with its own counters.
        self.client.force_authenticate(self.licensor_admin)
        portal = self.client.get(reverse("org-umbrella", kwargs={"slug": self.licensor.slug}))
        self.assertEqual(portal.status_code, status.HTTP_200_OK)
        self.assertEqual(portal.data["license"]["member_count"], 1)
        self.assertEqual(portal.data["members"][0]["organization"]["slug"], self.member.slug)
        self.assertEqual(portal.data["members"][0]["usage"]["board_posts"], 2)
        self.assertEqual(portal.data["pooled_usage"]["board_posts"]["used"], 3)

    def test_redeem_guards(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        with self.assertRaises(UmbrellaError) as ctx:
            redeem_umbrella_code(organization=self.member, user=None, code="UMB-NOPE-NOPE")
        self.assertEqual(ctx.exception.code, "invalid_umbrella_code")

        with self.assertRaises(UmbrellaError) as ctx:
            redeem_umbrella_code(organization=self.licensor, user=None, code=license.code)
        self.assertEqual(ctx.exception.code, "self_redemption")

        _paid(self.other, level="BASIC")
        with self.assertRaises(UmbrellaError) as ctx:
            redeem_umbrella_code(organization=self.other, user=None, code=license.code)
        self.assertEqual(ctx.exception.code, "active_subscription_exists")

        redeem_umbrella_code(organization=self.member, user=None, code=license.code)
        with self.assertRaises(UmbrellaError) as ctx:
            redeem_umbrella_code(organization=self.member, user=None, code=license.code)
        self.assertEqual(ctx.exception.code, "already_member")

        # Deactivated license refuses new members but keeps existing ones.
        license.is_active = False
        license.save()
        third = _org("Third Org")
        with self.assertRaises(UmbrellaError):
            redeem_umbrella_code(organization=third, user=None, code=license.code)
        self.assertEqual(get_current_service_level(self.member), "COMMUNITY")

    def test_remove_member_and_leave_drop_to_free(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        rel, _ = redeem_umbrella_code(
            organization=self.member, user=self.member_admin, code=license.code
        )
        self.client.force_authenticate(self.licensor_admin)
        res = self.client.post(
            reverse(
                "org-umbrella-remove-member",
                kwargs={"slug": self.licensor.slug, "pk": rel.id},
            )
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["members"], [])
        self.assertEqual(get_current_service_level(self.member), "FREE")

        # Rejoin, then member leaves on its own.
        redeem_umbrella_code(organization=self.member, user=self.member_admin, code=license.code)
        self.assertEqual(get_current_service_level(self.member), "COMMUNITY")
        self.client.force_authenticate(self.member_admin)
        res = self.client.post(reverse("org-umbrella-leave", kwargs={"slug": self.member.slug}))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(get_current_service_level(self.member), "FREE")

    def test_licensor_plan_lapse_drops_members(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        redeem_umbrella_code(organization=self.member, user=None, code=license.code)
        self.assertEqual(get_current_service_level(self.member), "COMMUNITY")

        self.backing.status = OrganizationService.Status.CANCELLED
        self.backing.save()
        self.assertEqual(get_current_service_level(self.member), "FREE")
        self.assertFalse(
            OrganizationRelationship.objects.filter(
                kind=OrganizationRelationship.Kind.UMBRELLA_MEMBER,
                to_organization=self.member,
                status="accepted",
            ).exists()
        )

    def test_level_change_mirrors_to_members(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        redeem_umbrella_code(organization=self.member, user=None, code=license.code)
        self.backing.service_level = "ENTERPRISE"
        self.backing.save()
        self.assertEqual(get_current_service_level(self.member), "ENTERPRISE")

    def test_rotate_code_invalidates_old(self):
        license = create_license(organization=self.licensor, user=self.licensor_admin)
        old = license.code
        self.client.force_authenticate(self.licensor_admin)
        res = self.client.post(reverse("org-umbrella-rotate", kwargs={"slug": self.licensor.slug}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotEqual(res.data["license"]["code"], old)
        with self.assertRaises(UmbrellaError):
            redeem_umbrella_code(organization=self.member, user=None, code=old)
