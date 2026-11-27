from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase

from api.billing_plans import SERVICE_LEVEL_BASIC
from api.billing_service import (
    activate_organization_service,
    create_pending_organization_service,
    get_current_service_level,
)
from api.models import (
    Organization,
    OrganizationAuditEvent,
    OrganizationMembership,
)
from api.organization_lifecycle import close_organization


class OrganizationLifecycleApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass")
        self.admin = User.objects.create_user("admin2", password="pass")
        self.member = User.objects.create_user("member", password="pass")
        self.org = Organization.objects.create(
            name="Forsyth County Democratic Party",
            slug="forsyth-county-democratic-party",
            status=Organization.Status.ACTIVE,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
        )
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
        self.client.force_authenticate(self.owner)

    def test_sole_owner_cannot_cancel_ownership(self):
        OrganizationMembership.objects.filter(user=self.admin).delete()
        url = reverse("org-ownership-cancel", kwargs={"slug": self.org.slug})
        res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "sole_owner")

    def test_transfer_then_cancel_ownership(self):
        transfer = reverse("org-ownership-transfer", kwargs={"slug": self.org.slug})
        res = self.client.post(
            transfer, {"new_owner_user_id": self.admin.id}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(
            OrganizationMembership.objects.get(
                organization=self.org, user=self.admin
            ).role,
            OrganizationMembership.Role.OWNER,
        )
        self.assertEqual(
            OrganizationMembership.objects.get(
                organization=self.org, user=self.owner
            ).role,
            OrganizationMembership.Role.ADMIN,
        )
        self.assertTrue(
            OrganizationAuditEvent.objects.filter(
                organization=self.org,
                event_type=OrganizationAuditEvent.EventType.OWNERSHIP_TRANSFERRED,
            ).exists()
        )

    def test_admin_cannot_close(self):
        self.client.force_authenticate(self.admin)
        url = reverse("org-close", kwargs={"slug": self.org.slug})
        res = self.client.post(
            url, {"confirmation_name": self.org.name}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_close_free_organization(self):
        url = reverse("org-close", kwargs={"slug": self.org.slug})
        res = self.client.post(
            url, {"confirmation_name": self.org.name}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.CLOSED)
        self.assertFalse(self.org.is_active)

        # Duplicate create blocked
        create_url = reverse("organization-create")
        blocked = self.client.post(
            create_url,
            {"name": "Forsyth County Democratic Party"},
            format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(blocked.data["code"], "closed_organization_exists")

    def test_cancel_paid_service_keeps_org_active(self):
        pending = create_pending_organization_service(
            organization=self.org, service_level=SERVICE_LEVEL_BASIC
        )
        activate_organization_service(pending)
        svc = pending
        svc.current_period_end = timezone.now() + timedelta(days=14)
        svc.save(update_fields=["current_period_end"])

        url = reverse("org-billing-cancel", kwargs={"slug": self.org.slug})
        res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.ACTIVE)
        self.assertEqual(get_current_service_level(self.org), SERVICE_LEVEL_BASIC)
        svc.refresh_from_db()
        self.assertTrue(svc.cancel_at_period_end)
        self.assertEqual(svc.status, svc.Status.ACTIVE)

    def test_close_paid_schedules_closure(self):
        pending = create_pending_organization_service(
            organization=self.org, service_level=SERVICE_LEVEL_BASIC
        )
        activate_organization_service(pending)
        pending.current_period_end = timezone.now() + timedelta(days=10)
        pending.save(update_fields=["current_period_end"])

        url = reverse("org-close", kwargs={"slug": self.org.slug})
        res = self.client.post(
            url, {"confirmation_name": self.org.name}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.CLOSURE_PENDING)
        self.assertTrue(self.org.is_active)

        cancel = reverse("org-cancel-closure", kwargs={"slug": self.org.slug})
        res2 = self.client.post(cancel, {}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.ACTIVE)

    def test_staff_can_restore(self):
        close_organization(
            self.org, actor=self.owner, confirmation_name=self.org.name
        )
        staff = User.objects.create_user("staffer", password="pass", is_staff=True)
        self.client.force_authenticate(staff)
        url = reverse("admin-org-restore", kwargs={"slug": self.org.slug})
        res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, Organization.Status.ACTIVE)
        self.assertTrue(self.org.is_active)
