from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from api.models import VoterFile
from api.voter_nc import parse_voter_file


class Command(BaseCommand):
    help = (
        "Load a North Carolina statewide voter extract into the database. "
        "After it is ready, older official files are deleted and the previous "
        "ready file is kept for comparison."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to ncvoter_Statewide.txt or a zip of it.")
        parser.add_argument(
            "--submitted-by",
            default="",
            help="Username recorded as the submitter. Optional.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        user = None
        username = (options["submitted_by"] or "").strip()
        if username:
            user = User.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"No user named {username}.")
        voter_file = VoterFile.objects.create(
            install=None,
            source=VoterFile.Source.OFFICIAL,
            original_filename=path.name,
            stored_path=str(path),
            submitted_by=user,
            is_current_official=False,
            status=VoterFile.Status.QUEUED,
        )
        self.stdout.write(f"Parsing {path.name} as voter file {voter_file.id}.")
        parse_voter_file(voter_file.id)
        voter_file.refresh_from_db()
        if voter_file.status != VoterFile.Status.READY:
            raise CommandError(voter_file.error or "Parse failed.")
        self.stdout.write(
            self.style.SUCCESS(
                f"Ready: {voter_file.row_count} rows. "
                "The current file and the previous ready file are kept. Older official files are removed."
            )
        )
