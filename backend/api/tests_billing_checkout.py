from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.billing_plans import COMMUNIB_PAYPAL_PLANS, SERVICE_LEVEL_COMMUNITY
from api.billing_service import (
    activate_organization_service,
    create_pending_organization_service,
    get_current_service_level,
)
from api.models import Organization, OrganizationMembership, OrganizationService


class PendingCheckoutApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Checkout Start Org",
            slug="checkout-start-org",
        )
        self.admin = User.objects.create_user(username="checkoutadmin", password="pass")
        self.member = User.objects.create_user(username="checkoutmember", password="pass")
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
        self.url = f"/api/organizations/{self.org.slug}/billing/checkout/"

    def test_admin_creates_pending_with_authoritative_plan(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url,
            {
                "service_level": "COMMUNITY",
                "price": "1.00",
                "paypal_plan_id": "P-FAKE",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        pending = res.data["pending_service"]
        self.assertEqual(pending["status"], "PENDING")
        self.assertEqual(pending["service_level"], "COMMUNITY")
        self.assertEqual(
            pending["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        )
        self.assertEqual(pending["requested_by_id"], self.admin.id)
        self.assertTrue(pending["billing_reference"].startswith("COMMUNIB-SUB-"))
        self.assertEqual(res.data["checkout"]["price"], "125.00")
        self.assertEqual(res.data["effective_service_level"], "FREE")
        self.assertFalse(res.data["paypal_contacted"])

        row = OrganizationService.objects.get(id=pending["id"])
        self.assertEqual(row.requested_by_id, self.admin.id)
        self.assertEqual(get_current_service_level(self.org), "FREE")

        billing = self.client.get(f"/api/organizations/{self.org.slug}/billing/")
        self.assertEqual(billing.status_code, status.HTTP_200_OK)
        self.assertEqual(
            billing.data["pending_checkout"]["billing_reference"],
            pending["billing_reference"],
        )

    def test_member_cannot_start_checkout(self):
        self.client.force_authenticate(user=self.member)
        res = self.client.post(self.url, {"service_level": "BASIC"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(OrganizationService.objects.count(), 0)

    def test_enterprise_rejected(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url, {"service_level": "ENTERPRISE"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "enterprise_contact_only")

    def test_active_paypal_blocks_new_checkout(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
            requested_by=self.admin,
        )
        activate_organization_service(pending, paypal_subscription_id="I-ACTIVE")

        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url, {"service_level": "BASIC"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data["code"], "active_subscription_exists")

    def test_new_checkout_cancels_previous_pending(self):
        self.client.force_authenticate(user=self.admin)
        first = self.client.post(
            self.url, {"service_level": "BASIC"}, format="json"
        )
        second = self.client.post(
            self.url, {"service_level": "COMMUNITY"}, format="json"
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

        old = OrganizationService.objects.get(id=first.data["pending_service"]["id"])
        new = OrganizationService.objects.get(id=second.data["pending_service"]["id"])
        self.assertEqual(old.status, OrganizationService.Status.CANCELLED)
        self.assertEqual(new.status, OrganizationService.Status.PENDING)
        self.assertEqual(new.service_level, "COMMUNITY")
