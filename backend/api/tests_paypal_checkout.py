from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api.billing_plans import COMMUNIB_PAYPAL_PLANS, SERVICE_LEVEL_COMMUNITY
from api.billing_service import (
    activate_organization_service,
    create_pending_organization_service,
    get_current_service_level,
    start_pending_checkout,
)
from api.models import Organization, OrganizationMembership, OrganizationService


@override_settings(
    PAYPAL_MODE="sandbox",
    PAYPAL_SUBSCRIPTIONS_ENABLED=True,
    PAYPAL_CLIENT_ID="test-client",
    PAYPAL_CLIENT_SECRET="test-secret",
    FRONTEND_BASE_URL="http://localhost:10001",
)
class PayPalCheckoutApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="PayPal Checkout Org",
            slug="paypal-checkout-org",
        )
        self.admin = User.objects.create_user(username="paypaladmin", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.ADMIN,
        )
        self.url = f"/api/organizations/{self.org.slug}/billing/checkout/"
        self.confirm_url = f"/api/organizations/{self.org.slug}/billing/paypal/confirm/"

    @patch("api.billing_service.create_subscription")
    def test_checkout_creates_pending_and_returns_approve_url(self, mock_create):
        mock_create.return_value = {
            "paypal_subscription_id": "I-TESTSUB123",
            "approve_url": "https://www.sandbox.paypal.com/approve-test",
            "status": "APPROVAL_PENDING",
            "raw": {},
        }
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url,
            {"service_level": "COMMUNITY", "price": "1.00", "paypal_plan_id": "P-FAKE"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["paypal_contacted"])
        self.assertEqual(
            res.data["approve_url"],
            "https://www.sandbox.paypal.com/approve-test",
        )
        pending = res.data["pending_service"]
        self.assertEqual(pending["status"], "PENDING")
        self.assertEqual(pending["paypal_subscription_id"], "I-TESTSUB123")
        self.assertEqual(
            pending["paypal_plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        )
        self.assertEqual(res.data["effective_service_level"], "FREE")
        self.assertFalse(res.data["entitlement_changed"])

        _args, kwargs = mock_create.call_args
        self.assertEqual(
            kwargs["plan_id"],
            COMMUNIB_PAYPAL_PLANS[SERVICE_LEVEL_COMMUNITY]["plan_id"],
        )
        self.assertEqual(kwargs["custom_id"], pending["billing_reference"])

    @patch("api.billing_service.create_subscription")
    def test_confirm_does_not_activate(self, mock_create):
        mock_create.return_value = {
            "paypal_subscription_id": "I-CONFIRM1",
            "approve_url": "https://www.sandbox.paypal.com/approve",
            "status": "APPROVAL_PENDING",
            "raw": {},
        }
        self.client.force_authenticate(user=self.admin)
        start = self.client.post(
            self.url, {"service_level": "BASIC"}, format="json"
        )
        self.assertEqual(start.status_code, status.HTTP_201_CREATED)

        confirm = self.client.post(
            self.confirm_url,
            {"subscription_id": "I-CONFIRM1"},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.assertFalse(confirm.data["activated"])
        self.assertFalse(confirm.data["entitlement_changed"])
        self.assertEqual(confirm.data["effective_service_level"], "FREE")
        self.assertEqual(get_current_service_level(self.org), "FREE")

        row = OrganizationService.objects.get(
            paypal_subscription_id="I-CONFIRM1"
        )
        self.assertEqual(row.status, OrganizationService.Status.PENDING)

    def test_manual_success_query_cannot_activate_without_pending(self):
        """Visiting confirm without a real pending checkout fails safely."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.confirm_url,
            {"subscription_id": "I-RANDOM"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(get_current_service_level(self.org), "FREE")

    @override_settings(PAYPAL_SUBSCRIPTIONS_ENABLED=False)
    def test_disabled_paypal_stays_simulated(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url, {"service_level": "COMMUNITY"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res.data["paypal_contacted"])
        self.assertIsNone(res.data["approve_url"])
        self.assertEqual(res.data["pending_service"]["status"], "PENDING")
        self.assertEqual(res.data["effective_service_level"], "FREE")
