from django.core.management.base import BaseCommand
from api.models import ResourceType


class Command(BaseCommand):
    help = "Seed default resource types"

    def handle(self, *args, **options):
        types = [
            ("survey", "Survey"),
            ("meeting", "Meeting"),
            ("organization", "Organization"),
        ]
        for slug, name in types:
            obj, created = ResourceType.objects.get_or_create(
                slug=slug, defaults={"name": name}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {slug}"))
            else:
                self.stdout.write(f"Already exists: {slug}")