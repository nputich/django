from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from api.billing_plans import SERVICE_LEVEL_COMMUNITY, SERVICE_LEVEL_FREE
from api.billing_service import (
    activate_organization_service,
    cancel_organization_service,
    create_pending_organization_service,
    get_current_service_level,
    simulate_activate_pending_service,
)
from api.models import Organization, OrganizationService


class OrganizationServiceResolverTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Forsyth Community Coalition",
            slug="forsyth-community-coalition",
        )
        self.user = User.objects.create_user(username="owner", password="pass")

    def test_free_when_no_entitlement(self):
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_FREE)
        self.assertEqual(self.org.get_current_service_level(), SERVICE_LEVEL_FREE)

    def test_pending_does_not_grant_paid_service(self):
        create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
        )
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_FREE)

    def test_activate_pending_grants_community(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
        )
        self.assertEqual(pending.status, OrganizationService.Status.PENDING)
        self.assertTrue(pending.billing_reference.startswith("COMMUNIB-SUB-"))

        activate_organization_service(pending, paypal_subscription_id="I-TEST")
        pending.refresh_from_db()

        self.assertEqual(pending.status, OrganizationService.Status.ACTIVE)
        self.assertEqual(pending.paypal_subscription_id, "I-TEST")
        self.assertIsNotNone(pending.started_at)
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_COMMUNITY)

    def test_cancel_returns_to_free_organization_intact(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
        )
        activate_organization_service(pending)
        cancel_organization_service(pending)
        pending.refresh_from_db()

        self.assertEqual(pending.status, OrganizationService.Status.CANCELLED)
        self.assertIsNotNone(pending.cancelled_at)
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_FREE)
        self.assertTrue(
            Organization.objects.filter(pk=self.org.pk, slug=self.org.slug).exists()
        )

    @override_settings(DEBUG=False, APP_ENV="production", BILLING_SIMULATION_ENABLED=False)
    def test_simulate_blocked_in_production(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
        )
        with self.assertRaises(PermissionError):
            simulate_activate_pending_service(pending)

    @override_settings(BILLING_SIMULATION_ENABLED=True, DEBUG=False, APP_ENV="production")
    def test_simulate_allowed_when_flag_enabled(self):
        pending = create_pending_organization_service(
            organization=self.org,
            service_level=SERVICE_LEVEL_COMMUNITY,
        )
        simulate_activate_pending_service(pending, paypal_subscription_id="I-SIM")
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_COMMUNITY)
