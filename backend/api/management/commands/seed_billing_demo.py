"""
Seed billing test organizations and entitlements for dashboard QA.

Usage:
  python manage.py seed_billing_demo
  python manage.py seed_billing_demo --reset
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from api.billing_plans import (
    SERVICE_LEVEL_BASIC,
    SERVICE_LEVEL_COMMUNITY,
    SERVICE_LEVEL_COMMUNITY_PLUS,
)
from api.billing_service import (
    activate_organization_service,
    cancel_organization_service,
    create_pending_organization_service,
)
from api.models import (
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    OrganizationService,
)

User = get_user_model()

ORGADMIN_USERNAME = "orgadmin"
ORGADMIN_PASSWORD = "DemoOrgAdmin2026!"

SEED_ORGS = (
    {
        "slug": "billing-free-demo",
        "name": "Billing Free Demo Org",
        "description": "Stage 2/3 test org with no paid entitlement (resolves to FREE).",
        "entitlement": None,
    },
    {
        "slug": "billing-pending-demo",
        "name": "Billing Pending Demo Org",
        "description": "Has a PENDING Community entitlement (still FREE until activated).",
        "entitlement": {"level": SERVICE_LEVEL_COMMUNITY, "state": "pending"},
    },
    {
        "slug": "billing-community-demo",
        "name": "Billing Community Active Demo",
        "description": "ACTIVE Community entitlement for dashboard billing QA.",
        "entitlement": {"level": SERVICE_LEVEL_COMMUNITY, "state": "active"},
    },
    {
        "slug": "billing-basic-cancelled-demo",
        "name": "Billing Basic Cancelled Demo",
        "description": "Had Basic ACTIVE then CANCELLED; effective service is FREE.",
        "entitlement": {"level": SERVICE_LEVEL_BASIC, "state": "cancelled"},
    },
    {
        "slug": "billing-community-plus-demo",
        "name": "Billing Community Plus Demo",
        "description": "ACTIVE Community Plus entitlement.",
        "entitlement": {"level": SERVICE_LEVEL_COMMUNITY_PLUS, "state": "active"},
    },
)


class Command(BaseCommand):
    help = "Seed billing demo organizations and OrganizationService rows for QA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete seeded billing org services (and recreate orgs/memberships).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username=ORGADMIN_USERNAME,
            defaults={"email": "orgadmin@example.com"},
        )
        if created:
            admin.set_password(ORGADMIN_PASSWORD)
            admin.save()
            self.stdout.write(self.style.SUCCESS(f"Created user: {ORGADMIN_USERNAME}"))
        else:
            self.stdout.write(f"User already exists: {ORGADMIN_USERNAME}")

        if options["reset"]:
            slugs = [o["slug"] for o in SEED_ORGS]
            deleted, _ = OrganizationService.objects.filter(
                organization__slug__in=slugs
            ).delete()
            self.stdout.write(f"Removed {deleted} OrganizationService row(s) for seed orgs.")

        for spec in SEED_ORGS:
            org, org_created = Organization.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if not org_created:
                org.name = spec["name"]
                org.description = spec["description"]
                org.is_active = True
                org.save(update_fields=["name", "description", "is_active"])

            OrganizationBoard.objects.get_or_create(
                organization=org,
                defaults={"title": f"{org.name} Board"},
            )
            OrganizationMembership.objects.get_or_create(
                organization=org,
                user=admin,
                defaults={"role": OrganizationMembership.Role.ADMIN},
            )

            # Replace entitlements for this org when resetting or when none match intent.
            if options["reset"]:
                OrganizationService.objects.filter(organization=org).delete()

            existing = OrganizationService.objects.filter(organization=org)
            if existing.exists() and not options["reset"]:
                level = org.get_current_service_level()
                self.stdout.write(
                    f"Org {org.slug}: kept existing services "
                    f"(effective={level})"
                )
                continue

            ent = spec["entitlement"]
            if not ent:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Org {org.slug}: no paid entitlement (effective=FREE)"
                    )
                )
                continue

            pending = create_pending_organization_service(
                organization=org,
                service_level=ent["level"],
            )
            if ent["state"] == "pending":
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Org {org.slug}: PENDING {ent['level']} "
                        f"({pending.billing_reference}); effective=FREE"
                    )
                )
                continue

            activate_organization_service(
                pending,
                paypal_subscription_id=f"I-SEED-{org.slug.upper()[:20]}",
            )
            if ent["state"] == "cancelled":
                cancel_organization_service(pending)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Org {org.slug}: CANCELLED {ent['level']}; effective=FREE"
                    )
                )
            else:
                pending.current_period_end = timezone.now() + timedelta(days=30)
                pending.save(update_fields=["current_period_end", "updated_at"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Org {org.slug}: ACTIVE {ent['level']} "
                        f"(effective={org.get_current_service_level()})"
                    )
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Billing demo seed complete."))
        self.stdout.write(f"Login: {ORGADMIN_USERNAME} / {ORGADMIN_PASSWORD}")
        self.stdout.write("Open /dashboard then Billing & Service on a seed org.")
