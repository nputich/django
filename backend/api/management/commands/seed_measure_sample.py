from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from api.models import (
    Measure,
    MeasureMember,
    MeasureRevision,
    Organization,
    OrganizationMembership,
    PluginDefinition,
    PluginInstall,
)

BASE = """SECTION 1. The state shall repair public bridges.
SECTION 2. Counties shall report closed bridges each year.
SECTION 3. This act is effective when it becomes law.
"""

REVISION = """SECTION 1. Counties shall fund public bridge repair.
SECTION 2. Counties shall report closed bridges each year.
SECTION 3. This act is effective when it becomes law.
"""

EDITOR_REVISION = """SECTION 1. The state shall repair public bridges.
SECTION 2. Counties shall report closed bridges each quarter.
SECTION 3. This act is effective when it becomes law.
"""


class Command(BaseCommand):
    help = "Create a local Measure Reading sample organization, users, and one open measure."

    def handle(self, *args, **options):
        plugin, _created = PluginDefinition.objects.get_or_create(
            key="measure_reading",
            defaults={
                "name": "Measure Reading",
                "description": "Load a source into a measure and review member revisions.",
                "enabled": True,
                "audience": "organization",
                "requires_approval": False,
            },
        )
        admin, _created = User.objects.get_or_create(username="sample_reader")
        admin.set_password("SampleReading1")
        admin.save()
        guest, _created = User.objects.get_or_create(username="sample_guest")
        guest.set_password("SampleReading1")
        guest.save()
        editor, _created = User.objects.get_or_create(username="sample_editor")
        editor.set_password("SampleReading1")
        editor.save()
        org, _created = Organization.objects.get_or_create(
            slug="sample-readers",
            defaults={"name": "Sample Readers", "status": Organization.Status.ACTIVE},
        )
        OrganizationMembership.objects.get_or_create(
            organization=org, user=admin, defaults={"role": OrganizationMembership.Role.ADMIN}
        )
        OrganizationMembership.objects.get_or_create(
            organization=org, user=guest, defaults={"role": OrganizationMembership.Role.MEMBER}
        )
        OrganizationMembership.objects.get_or_create(
            organization=org, user=editor, defaults={"role": OrganizationMembership.Role.MEMBER}
        )
        install, _created = PluginInstall.objects.get_or_create(
            plugin=plugin,
            organization=org,
            defaults={"status": PluginInstall.Status.APPROVED, "installed_by": admin},
        )
        measure, _created = Measure.objects.get_or_create(
            install=install,
            external_key="sample:H:2",
            defaults={
                "organization": org,
                "source_key": "sample",
                "session_year": 2025,
                "bill_type": "h",
                "bill_number": 2,
                "title": "Sample bridge repair",
                "body": BASE,
                "summary": "This sample measure requires the state to repair public bridges and counties to report closures. It is local demo text, not a filed bill.",
                "source_url": "",
                "status": Measure.Status.VOTING,
                "passage_percent": 60,
                "created_by": admin,
            },
        )
        reader_seat, _created = MeasureMember.objects.get_or_create(
            measure=measure, user=admin, defaults={"label": "Reader", "color_index": 0}
        )
        MeasureMember.objects.get_or_create(
            measure=measure, user=guest, defaults={"label": "Guest", "color_index": 1}
        )
        editor_seat, _created = MeasureMember.objects.get_or_create(
            measure=measure, user=editor, defaults={"label": "Editor", "color_index": 2}
        )
        MeasureRevision.objects.update_or_create(
            measure=measure, member=reader_seat, defaults={"body": REVISION}
        )
        MeasureRevision.objects.update_or_create(
            measure=measure, member=editor_seat, defaults={"body": EDITOR_REVISION}
        )
        self.stdout.write(self.style.SUCCESS("Sample reading is ready."))
        self.stdout.write("Sign in as sample_reader / SampleReading1")
        self.stdout.write("Other account: sample_editor / SampleReading1")
        self.stdout.write("Organization slug: sample-readers")
        self.stdout.write(f"Measure id: {measure.id}")
