from django.core.management.base import BaseCommand

from api.meeting_ai import process_meeting_ai
from api.models import Meeting


class Command(BaseCommand):
    help = "Run AI enrichment on meeting responses (issue/political cards)."

    def add_arguments(self, parser):
        parser.add_argument("meeting_id", type=int)
        parser.add_argument(
            "--session-id",
            default="all",
            help="Session id or 'all' (default).",
        )

    def handle(self, *args, **options):
        meeting = Meeting.objects.get(pk=options["meeting_id"])
        outcome = process_meeting_ai(meeting, options["session_id"])
        self.stdout.write(self.style.SUCCESS(str(outcome)))
