from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api.access_codes import redeem_basic_access_code
from api.billing_service import get_current_service_level, request_cancel_paid_service
from api.models import (
    AccessCodeRedemption,
    Organization,
    OrganizationMembership,
    OrganizationService,
)


@override_settings(COMMUNIB_BASIC_ACCESS_CODE="SUPERBASIC")
class AccessCodeRedeemApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Access Code Org",
            slug="access-code-org",
        )
        self.admin = User.objects.create_user(username="acadmin", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.OWNER,
        )
        self.url = f"/api/organizations/{self.org.slug}/billing/access-code/"
        self.billing_url = f"/api/organizations/{self.org.slug}/billing/"

    def test_billing_exposes_enabled_flag_not_code(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(self.billing_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["basic_access_code_enabled"])
        blob = str(res.data).upper()
        self.assertNotIn("SUPERBASIC", blob)

    def test_redeem_activates_basic_without_paypal(self):
        self.client.force_authenticate(user=self.admin)
        with patch("api.billing_service.create_subscription") as mock_create:
            res = self.client.post(
                self.url,
                {"access_code": "superbasic", "service_level": "BASIC"},
                format="json",
            )
        mock_create.assert_not_called()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["activated"])
        self.assertFalse(res.data["paypal_contacted"])
        self.assertEqual(res.data["billing_source"], "ACCESS_CODE")
        self.assertEqual(res.data["effective_service_level"], "BASIC")
        self.assertEqual(get_current_service_level(self.org), "BASIC")

        service = OrganizationService.objects.get(
            id=res.data["service"]["id"]
        )
        self.assertEqual(service.service_level, "BASIC")
        self.assertEqual(service.status, OrganizationService.Status.ACTIVE)
        self.assertEqual(
            service.billing_source, OrganizationService.BillingSource.ACCESS_CODE
        )
        self.assertEqual(service.paypal_subscription_id, "")

        redemption = AccessCodeRedemption.objects.get(organization=self.org)
        self.assertEqual(redemption.code, "SUPERBASIC")
        self.assertEqual(redemption.redeemed_by_id, self.admin.id)
        self.assertEqual(redemption.organization_service_id, service.id)

    def test_invalid_code_rejected(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            self.url, {"access_code": "WRONG"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "invalid_access_code")
        self.assertEqual(get_current_service_level(self.org), "FREE")

    def test_cannot_redeem_twice_for_same_org(self):
        self.client.force_authenticate(user=self.admin)
        first = self.client.post(
            self.url, {"access_code": "SUPERBASIC"}, format="json"
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        # Cancel so active check is not the failure mode.
        service = OrganizationService.objects.get(id=first.data["service"]["id"])
        service.status = OrganizationService.Status.CANCELLED
        service.cancel_at_period_end = False
        service.save(update_fields=["status", "cancel_at_period_end", "updated_at"])

        second = self.client.post(
            self.url, {"access_code": "SUPERBASIC"}, format="json"
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "access_code_already_redeemed")

    @patch("api.paypal_client.cancel_subscription")
    def test_cancel_access_code_service_skips_paypal(self, mock_cancel):
        service, _ = redeem_basic_access_code(
            organization=self.org,
            user=self.admin,
            code="SUPERBASIC",
        )
        updated = request_cancel_paid_service(service, actor=self.admin)
        mock_cancel.assert_not_called()
        self.assertTrue(updated.cancel_at_period_end)
        self.assertEqual(
            updated.billing_source, OrganizationService.BillingSource.ACCESS_CODE
        )
        self.assertEqual(updated.paypal_subscription_id, "")


@override_settings(COMMUNIB_BASIC_ACCESS_CODE="")
class AccessCodeDisabledTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name="No Code Org", slug="no-code-org")
        self.admin = User.objects.create_user(username="nocodeadmin", password="pass")
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.OWNER,
        )

    def test_disabled_when_env_empty(self):
        self.client.force_authenticate(user=self.admin)
        billing = self.client.get(f"/api/organizations/{self.org.slug}/billing/")
        self.assertFalse(billing.data["basic_access_code_enabled"])
        res = self.client.post(
            f"/api/organizations/{self.org.slug}/billing/access-code/",
            {"access_code": "SUPERBASIC"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "access_code_disabled")
