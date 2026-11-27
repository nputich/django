"""
Meeting result sharing + the mandatory disclosure / demographics slide.

Rules (decided with the product owner):
  * Every meeting has a participant_info slide first. It carries the
    generated disclosure text and any demographic fields the organizer adds.
  * Sharing is explicit per meeting, per organization.
  * A share declared BEFORE the meeting first starts, and still active, gives
    the recipient FULL data (every stored row, keyed by the random per-meeting
    participant UUID). Anything granted after the start, or revoked later,
    gives AGGREGATE data (buckets and totals) only.
  * Relationships never imply sharing.
"""

from __future__ import annotations

from collections import Counter, OrderedDict

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import (
    Meeting,
    MeetingResponse,
    MeetingShare,
    MeetingSlide,
    Organization,
)

ANONYMOUS_POLICY = (
    "We do not store your name, email, or account with your answers. "
    "A random ID keeps your answers together for this meeting only. "
    "Organizers can still read the answers and any details you provide. "
    "Demographic comparisons are only shown when every group is large enough "
    "so no one is singled out."
)

NON_ANONYMOUS_POLICY = (
    "This meeting is not anonymous. Organizers may connect your answers to your "
    "account or what you enter on this screen. "
    "Demographic comparisons are only shown when every group is large enough "
    "so no one is singled out."
)


class SharingError(ValueError):
    def __init__(self, message: str, *, code: str = "sharing_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# --------------------------------------------------------------------------- #
# Disclosure slide
# --------------------------------------------------------------------------- #


def _join_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def declared_share_names(meeting: Meeting) -> list[str]:
    return list(
        meeting.shares.filter(status=MeetingShare.Status.ACTIVE, declared_before_start=True)
        .select_related("organization")
        .order_by("organization__name")
        .values_list("organization__name", flat=True)
    )


def disclosure_text(meeting: Meeting) -> str:
    """Participant-facing text — keep short; details live behind the ? control."""
    parts: list[str] = []
    names = declared_share_names(meeting)
    if names:
        parts.append(f"Results may be shared with {_join_names(names)}.")
    if meeting.aggregate_sharing_notice:
        parts.append(
            "We may also share anonymous combined results with policymakers "
            "not listed here."
        )
    if meeting.is_anonymous:
        parts.append(
            "Anonymous meeting: we do not store your name with your answers. "
            "Organizers can still read the answers and any details you share. "
            "Demographic comparisons are only shown when every group is large enough "
            "so no one is singled out."
        )
    else:
        parts.append(
            "This meeting is not anonymous. Organizers may connect your answers to "
            "information you provide. "
            "Demographic comparisons are only shown when every group is large enough "
            "so no one is singled out."
        )
    return " ".join(parts)


def disclosure_payload(meeting: Meeting) -> dict:
    return {
        "text": disclosure_text(meeting),
        "is_anonymous": meeting.is_anonymous,
        "anonymity_policy": ANONYMOUS_POLICY if meeting.is_anonymous else NON_ANONYMOUS_POLICY,
        "shared_with": declared_share_names(meeting),
        "aggregate_sharing_notice": meeting.aggregate_sharing_notice,
    }


def ensure_disclosure_slide(meeting: Meeting) -> MeetingSlide:
    """
    Guarantee the first active slide is a participant_info slide flagged as the
    disclosure screen. Reuses the organizer's own participant_info slide when
    one exists (moving it first); otherwise inserts an empty one.
    """
    slides = list(meeting.slides.filter(is_active=True).order_by("order", "id"))
    info = next(
        (s for s in slides if s.slide_type == MeetingSlide.SlideType.PARTICIPANT_INFO), None
    )
    if info is None:
        info = MeetingSlide.objects.create(
            meeting=meeting,
            order=0,
            slide_type=MeetingSlide.SlideType.PARTICIPANT_INFO,
            title="Before we begin",
            prompt="",
            config={"fields": [], "disclosure": True},
        )
        slides.insert(0, info)
    else:
        config = dict(info.config or {})
        config["disclosure"] = True
        info.config = config
        info.save(update_fields=["config"])
        slides.remove(info)
        slides.insert(0, info)

    for index, slide in enumerate(slides):
        if slide.order != index:
            slide.order = index
            slide.save(update_fields=["order"])
    return info


# --------------------------------------------------------------------------- #
# Shares
# --------------------------------------------------------------------------- #


def meeting_has_started(meeting: Meeting) -> bool:
    return bool(meeting.started_at) or meeting.sessions.filter(started_at__isnull=False).exists()


def serialize_share(share: MeetingShare) -> dict:
    return {
        "id": share.id,
        "organization": {
            "id": share.organization.id,
            "name": share.organization.name,
            "slug": share.organization.slug,
        },
        "status": share.status,
        "declared_before_start": share.declared_before_start,
        "effective_access": share.effective_access,
        "effective_access_label": (
            "Full data" if share.effective_access == MeetingShare.Access.FULL else "Buckets and totals"
        ),
        "created_at": share.created_at,
        "revoked_at": share.revoked_at,
    }


def list_shares(meeting: Meeting) -> list[dict]:
    return [
        serialize_share(s)
        for s in meeting.shares.select_related("organization").order_by("organization__name")
    ]


@transaction.atomic
def grant_share(*, meeting: Meeting, organization: Organization, user: User | None) -> MeetingShare:
    if organization.id == meeting.organization_id:
        raise SharingError("You cannot share a meeting with your own organization.", code="self_share")
    if organization.status != Organization.Status.ACTIVE or not organization.is_active:
        raise SharingError("That organization is not active.", code="org_inactive")
    existing = MeetingShare.objects.filter(meeting=meeting, organization=organization).first()
    before = not meeting_has_started(meeting)
    if existing:
        if existing.status == MeetingShare.Status.ACTIVE:
            raise SharingError("Already shared with that organization.", code="duplicate_share")
        # Re-granting after a revoke never restores full access.
        existing.status = MeetingShare.Status.ACTIVE
        existing.declared_before_start = existing.declared_before_start and before
        existing.revoked_at = None
        existing.revoked_by = None
        existing.created_by = user
        existing.save(
            update_fields=["status", "declared_before_start", "revoked_at", "revoked_by", "created_by"]
        )
        return existing
    return MeetingShare.objects.create(
        meeting=meeting,
        organization=organization,
        declared_before_start=before,
        created_by=user,
    )


def revoke_share(share: MeetingShare, *, user: User | None) -> MeetingShare:
    if share.status == MeetingShare.Status.REVOKED:
        return share
    share.status = MeetingShare.Status.REVOKED
    share.revoked_at = timezone.now()
    share.revoked_by = user
    share.save(update_fields=["status", "revoked_at", "revoked_by"])
    return share


def shares_for_recipient(organization: Organization):
    return (
        MeetingShare.objects.filter(organization=organization)
        .select_related("meeting__organization")
        .order_by("-created_at")
    )


def get_share_for_recipient(organization: Organization, meeting_id) -> MeetingShare:
    share = shares_for_recipient(organization).filter(meeting_id=meeting_id).first()
    if not share:
        raise SharingError("This meeting has not been shared with your organization.", code="not_shared")
    return share


# --------------------------------------------------------------------------- #
# Results for recipients
# --------------------------------------------------------------------------- #


def _choice_counts(slide: MeetingSlide, responses) -> OrderedDict:
    counts: Counter = Counter()
    for r in responses:
        for opt in r.selected_options or []:
            counts[str(opt)] += 1
    ordered = OrderedDict()
    for opt in slide.choices or []:
        ordered[str(opt)] = counts.get(str(opt), 0)
    for opt, n in counts.items():
        ordered.setdefault(opt, n)
    return ordered


def aggregate_results(meeting: Meeting) -> dict:
    """Buckets and totals per question slide. Safe for AGGREGATE recipients."""
    slides = list(
        meeting.slides.filter(is_active=True)
        .exclude(slide_type=MeetingSlide.SlideType.PARTICIPANT_INFO)
        .order_by("order", "id")
    )
    responses_by_slide: dict[int, list] = {s.id: [] for s in slides}
    for r in MeetingResponse.objects.filter(meeting=meeting, slide__in=slides).only(
        "slide_id", "selected_options", "participant_id", "major_issue", "specific_issue", "issue_type"
    ):
        responses_by_slide.setdefault(r.slide_id, []).append(r)

    out = []
    for slide in slides:
        rows = responses_by_slide.get(slide.id, [])
        item = {
            "slide_id": slide.id,
            "order": slide.order,
            "slide_type": slide.slide_type,
            "question_format": slide.question_format,
            "prompt": slide.prompt or slide.title,
            "response_count": len(rows),
            "participant_count": len({r.participant_id for r in rows if r.participant_id}),
        }
        if slide.question_format in (
            MeetingSlide.QuestionFormat.SINGLE_CHOICE,
            MeetingSlide.QuestionFormat.MULTI_CHOICE,
        ):
            item["choice_counts"] = _choice_counts(slide, rows)
        if slide.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
            issues = Counter((r.major_issue or "Unclassified") for r in rows)
            item["issue_counts"] = dict(issues.most_common())
        out.append(item)

    total_participants = (
        MeetingResponse.objects.filter(meeting=meeting)
        .exclude(participant_id__isnull=True)
        .values("participant_id")
        .distinct()
        .count()
    )
    return {
        "meeting": {
            "id": meeting.id,
            "title": meeting.title,
            "organization": {"name": meeting.organization.name, "slug": meeting.organization.slug},
            "is_anonymous": meeting.is_anonymous,
            "status": meeting.status,
            "started_at": meeting.started_at,
            "ended_at": meeting.ended_at,
        },
        "participant_count": total_participants,
        "slides": out,
    }


AGGREGATE_CSV_COLUMNS = ["meeting_id", "meeting_title", "slide_order", "question_text", "bucket", "count"]


def aggregate_csv_rows(meeting: Meeting) -> list[dict]:
    data = aggregate_results(meeting)
    rows = []
    for s in data["slides"]:
        base = {
            "meeting_id": meeting.id,
            "meeting_title": meeting.title,
            "slide_order": s["order"],
            "question_text": s["prompt"],
        }
        rows.append({**base, "bucket": "TOTAL_RESPONSES", "count": s["response_count"]})
        for bucket, n in (s.get("choice_counts") or {}).items():
            rows.append({**base, "bucket": bucket, "count": n})
        for bucket, n in (s.get("issue_counts") or {}).items():
            rows.append({**base, "bucket": f"issue:{bucket}", "count": n})
    return rows
