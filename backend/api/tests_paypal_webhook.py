from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.billing_service import (
    create_pending_organization_service,
    get_current_service_level,
    handle_paypal_webhook_event,
)
from api.billing_plans import SERVICE_LEVEL_COMMUNITY
from api.models import Organization, OrganizationAuditEvent, OrganizationMembership, OrganizationService


WEBHOOK_HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
    "PAYPAL-TRANSMISSION-ID": "tx-1",
    "PAYPAL-TRANSMISSION-SIG": "sig",
    "PAYPAL-TRANSMISSION-TIME": "2026-01-01T00:00:00Z",
}


def _event(event_type, *, event_id, subscription_id, custom_id=None, next_billing=None):
    resource = {"id": subscription_id}
    if custom_id:
        resource["custom_id"] = custom_id
    if next_billing:
        resource["billing_info"] = {"next_billing_time": next_billing}
    return {
        "id": event_id,
        "event_type": event_type,
        "resource": resource,
    }


@override_settings(
    PAYPAL_MODE="sandbox",
    PAYPAL_SUBSCRIPTIONS_ENABLED=True,
    PAYPAL_CLIENT_ID="test-client",
    PAYPAL_CLIENT_SECRET="test-secret",
    PAYPAL_WEBHOOK_ID="WH-TEST",
)
class PayPalWebhookHandlerTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Webhook Org",
            slug="webhook-org",
        )
        self.user = User.objects.create_user(username="webadmin", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.ADMIN,
        )
        self.pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
            requested_by=self.user,
            paypal_plan_id="P-FAKE",
        )
        self.pending.paypal_subscription_id = "I-WEBHOOK-SUB"
        self.pending.save(update_fields=["paypal_subscription_id"])

    def test_activated_makes_service_active(self):
        period = (timezone.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-EVT-1",
                subscription_id="I-WEBHOOK-SUB",
                next_billing=period,
            )
        )
        self.pending.refresh_from_db()
        self.assertTrue(result["handled"])
        self.assertEqual(result["reason"], "activated")
        self.assertEqual(self.pending.status, OrganizationService.Status.ACTIVE)
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_COMMUNITY)
        self.assertFalse(self.pending.cancel_at_period_end)
        self.assertTrue(
            OrganizationAuditEvent.objects.filter(
                organization=self.org,
                event_type=OrganizationAuditEvent.EventType.PAYPAL_WEBHOOK,
                event_data__paypal_event_id="WH-EVT-1",
            ).exists()
        )

    def test_activated_by_custom_id_when_subscription_missing(self):
        self.pending.paypal_subscription_id = ""
        self.pending.save(update_fields=["paypal_subscription_id"])
        result = handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-EVT-CUSTOM",
                subscription_id="I-NEW-SUB",
                custom_id=self.pending.billing_reference,
            )
        )
        self.pending.refresh_from_db()
        self.assertEqual(result["reason"], "activated")
        self.assertEqual(self.pending.status, OrganizationService.Status.ACTIVE)
        self.assertEqual(self.pending.paypal_subscription_id, "I-NEW-SUB")

    def test_idempotent_same_event_id(self):
        event = _event(
            "BILLING.SUBSCRIPTION.ACTIVATED",
            event_id="WH-EVT-DUP",
            subscription_id="I-WEBHOOK-SUB",
        )
        first = handle_paypal_webhook_event(event)
        second = handle_paypal_webhook_event(event)
        self.assertEqual(first["reason"], "activated")
        self.assertEqual(second["reason"], "already_processed")
        self.assertEqual(
            OrganizationAuditEvent.objects.filter(
                organization=self.org,
                event_data__paypal_event_id="WH-EVT-DUP",
            ).count(),
            1,
        )

    def test_cancelled_keeps_active_until_period_end(self):
        handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-EVT-ACT",
                subscription_id="I-WEBHOOK-SUB",
                next_billing=(timezone.now() + timedelta(days=20)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            )
        )
        result = handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.CANCELLED",
                event_id="WH-EVT-CAN",
                subscription_id="I-WEBHOOK-SUB",
            )
        )
        self.pending.refresh_from_db()
        self.assertEqual(result["reason"], "cancel_at_period_end")
        self.assertEqual(self.pending.status, OrganizationService.Status.ACTIVE)
        self.assertTrue(self.pending.cancel_at_period_end)

    def test_suspended_cancels_immediately(self):
        handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-EVT-ACT2",
                subscription_id="I-WEBHOOK-SUB",
            )
        )
        result = handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.SUSPENDED",
                event_id="WH-EVT-SUS",
                subscription_id="I-WEBHOOK-SUB",
            )
        )
        self.pending.refresh_from_db()
        self.assertEqual(result["reason"], "suspended")
        self.assertEqual(self.pending.status, OrganizationService.Status.CANCELLED)

    def test_expired_marks_expired(self):
        handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-EVT-ACT3",
                subscription_id="I-WEBHOOK-SUB",
            )
        )
        result = handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.EXPIRED",
                event_id="WH-EVT-EXP",
                subscription_id="I-WEBHOOK-SUB",
            )
        )
        self.pending.refresh_from_db()
        self.assertEqual(result["reason"], "expired")
        self.assertEqual(self.pending.status, OrganizationService.Status.EXPIRED)

    def test_unknown_subscription_not_found(self):
        result = handle_paypal_webhook_event(
            _event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-EVT-MISS",
                subscription_id="I-UNKNOWN",
            )
        )
        self.assertFalse(result["handled"])
        self.assertEqual(result["reason"], "service_not_found")


@override_settings(
    PAYPAL_MODE="sandbox",
    PAYPAL_SUBSCRIPTIONS_ENABLED=True,
    PAYPAL_CLIENT_ID="test-client",
    PAYPAL_CLIENT_SECRET="test-secret",
    PAYPAL_WEBHOOK_ID="WH-TEST",
)
class PayPalWebhookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name="API WH Org", slug="api-wh-org")
        self.user = User.objects.create_user(username="apiwh", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.ADMIN,
        )
        self.pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
            requested_by=self.user,
            paypal_plan_id="P-FAKE",
        )
        self.pending.paypal_subscription_id = "I-API-SUB"
        self.pending.save(update_fields=["paypal_subscription_id"])
        self.url = "/api/billing/paypal/webhook/"

    @patch("api.billing_views.verify_webhook_signature", return_value=True)
    def test_webhook_post_activates(self, _mock_verify):
        res = self.client.post(
            self.url,
            data=_event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-API-1",
                subscription_id="I-API-SUB",
            ),
            format="json",
            headers=WEBHOOK_HEADERS,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])
        self.assertEqual(res.data["reason"], "activated")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, OrganizationService.Status.ACTIVE)

    @patch("api.billing_views.verify_webhook_signature", return_value=False)
    def test_invalid_signature_rejected(self, _mock_verify):
        res = self.client.post(
            self.url,
            data=_event(
                "BILLING.SUBSCRIPTION.ACTIVATED",
                event_id="WH-API-BAD",
                subscription_id="I-API-SUB",
            ),
            format="json",
            headers=WEBHOOK_HEADERS,
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, OrganizationService.Status.PENDING)

    def test_unauthenticated_allowed(self):
        with patch("api.billing_views.verify_webhook_signature", return_value=True):
            res = self.client.post(
                self.url,
                data=_event(
                    "BILLING.SUBSCRIPTION.ACTIVATED",
                    event_id="WH-API-ANON",
                    subscription_id="I-API-SUB",
                ),
                format="json",
                headers=WEBHOOK_HEADERS,
            )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
