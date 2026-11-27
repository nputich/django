"""
Simulate PENDING → ACTIVE for an OrganizationService (no PayPal).

Only works when billing_simulation_allowed() is true (DEBUG, local APP_ENV,
or BILLING_SIMULATION_ENABLED=true). Not exposed as a public API.
"""

from django.core.management.base import BaseCommand, CommandError

from api.billing_service import (
    billing_simulation_allowed,
    simulate_activate_pending_service,
)
from api.models import OrganizationService


class Command(BaseCommand):
    help = "Simulate activating a PENDING OrganizationService (dev/test only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "billing_reference",
            help="Billing reference, e.g. COMMUNIB-SUB-000184-00001",
        )

    def handle(self, *args, **options):
        if not billing_simulation_allowed():
            raise CommandError(
                "Billing simulation is disabled in this environment. "
                "Set BILLING_SIMULATION_ENABLED=true only for non-production use."
            )

        ref = options["billing_reference"]
        try:
            service = OrganizationService.objects.select_related("organization").get(
                billing_reference=ref
            )
        except OrganizationService.DoesNotExist as exc:
            raise CommandError(f"No OrganizationService with reference {ref!r}.") from exc

        try:
            updated = simulate_activate_pending_service(service)
        except (PermissionError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Activated {updated.billing_reference}: "
                f"{updated.organization.slug} → {updated.service_level} "
                f"(effective={updated.organization.get_current_service_level()})"
            )
        )
