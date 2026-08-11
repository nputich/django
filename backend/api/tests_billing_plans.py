from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api.billing_plans import (
    COMMUNIB_PAYPAL_PLANS,
    COMMUNIB_PAYPAL_PLANS_SANDBOX,
    SERVICE_LEVEL_BASIC,
    SERVICE_LEVEL_COMMUNITY,
    SERVICE_LEVEL_COMMUNITY_PLUS,
    SERVICE_LEVEL_ENTERPRISE,
    SERVICE_LEVEL_FREE,
    PlanResolutionError,
    resolve_paypal_checkout_plan,
)
from api.models import Organization, OrganizationMembership


class PlanResolutionUnitTests(TestCase):
    @override_settings(PAYPAL_MODE="live")
    def test_basic_community_community_plus_map_correctly(self):
        basic = resolve_paypal_checkout_plan("BASIC")
        self.assertEqual(basic["price"], "49.99")
        self.assertEqual(
            basic["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_BASIC]["plan_id"],
        )

        community = resolve_paypal_checkout_plan("community")
        self.assertEqual(community["price"], "125.00")
        self.assertEqual(
            community["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        )

        plus = resolve_paypal_checkout_plan(SERVICE_LEVEL_COMMUNITY_PLUS)
        self.assertEqual(plus["price"], "300.00")
        self.assertEqual(
            plus["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY_PLUS]["plan_id"],
        )

    @override_settings(PAYPAL_MODE="sandbox")
    def test_sandbox_mode_uses_sandbox_plan_ids(self):
        basic = resolve_paypal_checkout_plan("BASIC")
        self.assertEqual(
            basic["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS_SANDBOX[SERVICE_LEVEL_BASIC]["plan_id"],
        )
        community = resolve_paypal_checkout_plan("COMMUNITY")
        self.assertEqual(
            community["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS_SANDBOX[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        )
        plus = resolve_paypal_checkout_plan(SERVICE_LEVEL_COMMUNITY_PLUS)
        self.assertEqual(
            plus["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS_SANDBOX[SERVICE_LEVEL_COMMUNITY_PLUS]["plan_id"],
        )

    def test_free_and_enterprise_rejected(self):
        with self.assertRaises(PlanResolutionError) as free_ctx:
            resolve_paypal_checkout_plan(SERVICE_LEVEL_FREE)
        self.assertEqual(free_ctx.exception.code, "free_not_checkoutable")

        with self.assertRaises(PlanResolutionError) as ent_ctx:
            resolve_paypal_checkout_plan(SERVICE_LEVEL_ENTERPRISE)
        self.assertEqual(ent_ctx.exception.code, "enterprise_contact_only")

    def test_unknown_rejected(self):
        with self.assertRaises(PlanResolutionError) as ctx:
            resolve_paypal_checkout_plan("GOLD")
        self.assertEqual(ctx.exception.code, "invalid_service_level")


class CheckoutPreviewApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Billing Preview Org",
            slug="billing-preview-org",
        )
        self.admin = User.objects.create_user(username="billadmin", password="pass")
        self.member = User.objects.create_user(username="billmember", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.ADMIN,
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
        )
        self.url = f"/api/organizations/{self.org.slug}/billing/checkout-preview/"

    @override_settings(PAYPAL_MODE="live")
    def test_admin_gets_authoritative_plan_ignoring_client_price(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url,
            {
                "service_level": "COMMUNITY",
                "price": "1.00",
                "paypal_plan_id": "P-FAKE",
                "paypalPlanId": "P-FAKE-2",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        checkout = res.data["checkout"]
        self.assertEqual(checkout["price"], "125.00")
        self.assertEqual(
            checkout["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        )
        self.assertIn("price", res.data["ignored_client_fields"])
        self.assertIn("paypal_plan_id", res.data["ignored_client_fields"])
        self.assertFalse(res.data["entitlement_changed"])
        self.assertFalse(res.data["paypal_contacted"])

    def test_enterprise_and_free_rejected(self):
        self.client.force_authenticate(user=self.admin)
        ent = self.client.post(
            self.url, {"service_level": "ENTERPRISE"}, format="json"
        )
        self.assertEqual(ent.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ent.data["code"], "enterprise_contact_only")

        free = self.client.post(self.url, {"service_level": "FREE"}, format="json")
        self.assertEqual(free.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(free.data["code"], "free_not_checkoutable")

    def test_member_cannot_preview(self):
        self.client.force_authenticate(user=self.member)
        res = self.client.post(
            self.url, {"service_level": "BASIC"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_billing_catalog_omits_paypal_plan_id(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(f"/api/organizations/{self.org.slug}/billing/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for plan in res.data["plans"]:
            self.assertNotIn("paypal_plan_id", plan)
