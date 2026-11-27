"""One-off: raise snapshotted session attendee_limit to at least 500."""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from api.models import MeetingSession  # noqa: E402


def main():
    qs = MeetingSession.objects.filter(
        attendee_limit__isnull=False, attendee_limit__lt=500
    )
    preview = list(qs.values_list("id", "attendee_limit")[:20])
    count = qs.count()
    updated = qs.update(attendee_limit=500)
    remaining = MeetingSession.objects.filter(
        attendee_limit__isnull=False, attendee_limit__lt=500
    ).count()
    print("preview=", preview)
    print("updated=", updated, "of", count, "rows with attendee_limit < 500")
    print("remaining_below_500=", remaining)


if __name__ == "__main__":
    main()
