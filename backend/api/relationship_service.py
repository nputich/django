"""
Organization relationships: request → inbox → accept/decline → end.

Kinds:
  parent_child     from = parent, to = child   (one parent per child)
  umbrella_member  from = licensor, to = member (one licensor per member;
                   created by umbrella-license redemption, not by hand)
  partner          symmetric
  sponsor          from = sponsor, to = sponsored org

Relationships never grant admin rights or data access by themselves.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from api.inbox_service import get_organization_mailbox
from api.models import (
    Conversation,
    ConversationParticipant,
    InboxMessage,
    Organization,
    OrganizationRelationship,
)

Kind = OrganizationRelationship.Kind
Status = OrganizationRelationship.Status

REQUEST_TTL_DAYS = 30

# Settings UI sends a user-facing "direction"; map to (kind, my_role).
# my_role: "from" means the requesting org is the upper party.
DIRECTION_MAP = {
    "parent_of": (Kind.PARENT_CHILD, "from"),
    "child_of": (Kind.PARENT_CHILD, "to"),
    "partner": (Kind.PARTNER, "from"),
    "sponsor_of": (Kind.SPONSOR, "from"),
    "sponsored_by": (Kind.SPONSOR, "to"),
}

DIRECTION_LABELS = {
    "parent_of": "Parent organization of",
    "child_of": "Chapter / member of",
    "partner": "Partner with",
    "sponsor_of": "Sponsor of",
    "sponsored_by": "Sponsored by",
}


class RelationshipError(ValueError):
    def __init__(self, message: str, *, code: str = "relationship_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #


def _open_q() -> Q:
    return Q(status__in=OrganizationRelationship.OPEN_STATUSES)


def relationships_for(organization: Organization):
    return OrganizationRelationship.objects.filter(
        Q(from_organization=organization) | Q(to_organization=organization)
    ).select_related(
        "from_organization",
        "to_organization",
        "initiated_by_organization",
    )


def accepted_parent(organization: Organization) -> Organization | None:
    row = (
        OrganizationRelationship.objects.filter(
            kind=Kind.PARENT_CHILD,
            to_organization=organization,
            status=Status.ACCEPTED,
        )
        .select_related("from_organization")
        .first()
    )
    return row.from_organization if row else None


def accepted_children(organization: Organization, *, public_only: bool = False):
    qs = OrganizationRelationship.objects.filter(
        kind=Kind.PARENT_CHILD,
        from_organization=organization,
        status=Status.ACCEPTED,
    ).select_related("to_organization")
    if public_only:
        qs = qs.filter(public=True)
    return [r.to_organization for r in qs]


def accepted_partners(organization: Organization, *, public_only: bool = False):
    qs = OrganizationRelationship.objects.filter(
        kind=Kind.PARTNER, status=Status.ACCEPTED
    ).filter(Q(from_organization=organization) | Q(to_organization=organization))
    if public_only:
        qs = qs.filter(public=True)
    return [r.counterpart_of(organization) for r in qs.select_related(
        "from_organization", "to_organization"
    )]


def accepted_sponsors(organization: Organization, *, public_only: bool = False):
    qs = OrganizationRelationship.objects.filter(
        kind=Kind.SPONSOR, to_organization=organization, status=Status.ACCEPTED
    ).select_related("from_organization")
    if public_only:
        qs = qs.filter(public=True)
    return [r.from_organization for r in qs]


def accepted_umbrella_licensor(organization: Organization) -> Organization | None:
    row = (
        OrganizationRelationship.objects.filter(
            kind=Kind.UMBRELLA_MEMBER,
            to_organization=organization,
            status=Status.ACCEPTED,
        )
        .select_related("from_organization")
        .first()
    )
    return row.from_organization if row else None


def _org_ref(org: Organization) -> dict:
    return {"id": org.id, "name": org.name, "slug": org.slug}


def public_relationships_payload(organization: Organization) -> dict:
    """Hub / directory display. Respects the per-relationship ``public`` flag."""
    parent_row = (
        OrganizationRelationship.objects.filter(
            kind=Kind.PARENT_CHILD,
            to_organization=organization,
            status=Status.ACCEPTED,
            public=True,
        )
        .select_related("from_organization")
        .first()
    )
    return {
        "parent": _org_ref(parent_row.from_organization) if parent_row else None,
        "chapters": [_org_ref(o) for o in accepted_children(organization, public_only=True)],
        "partners": [_org_ref(o) for o in accepted_partners(organization, public_only=True)],
        "sponsors": [_org_ref(o) for o in accepted_sponsors(organization, public_only=True)],
    }


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #


def _is_ancestor(candidate: Organization, of_org: Organization) -> bool:
    """True if ``candidate`` appears anywhere above ``of_org`` in parent_child links."""
    seen: set[int] = set()
    current = of_org
    while current is not None and current.id not in seen:
        seen.add(current.id)
        parent = accepted_parent(current)
        if parent is None:
            return False
        if parent.id == candidate.id:
            return True
        current = parent
    return False


def _pending_parent_exists(child: Organization) -> bool:
    return OrganizationRelationship.objects.filter(
        kind=Kind.PARENT_CHILD, to_organization=child
    ).filter(_open_q()).exists()


def _duplicate_exists(kind: str, a: Organization, b: Organization) -> bool:
    qs = OrganizationRelationship.objects.filter(kind=kind).filter(_open_q())
    if kind == Kind.PARTNER:
        return qs.filter(
            Q(from_organization=a, to_organization=b)
            | Q(from_organization=b, to_organization=a)
        ).exists()
    return qs.filter(from_organization=a, to_organization=b).exists()


def _validate_new(kind: str, from_org: Organization, to_org: Organization) -> None:
    if from_org.id == to_org.id:
        raise RelationshipError(
            "An organization cannot have a relationship with itself.",
            code="self_relationship",
        )
    for org in (from_org, to_org):
        if org.status != Organization.Status.ACTIVE or not org.is_active:
            raise RelationshipError(
                f"{org.name} is not an active organization.", code="org_inactive"
            )
    if _duplicate_exists(kind, from_org, to_org):
        raise RelationshipError(
            "A pending or active relationship of this type already exists.",
            code="duplicate_relationship",
        )
    if kind in (Kind.PARENT_CHILD, Kind.UMBRELLA_MEMBER):
        if kind == Kind.PARENT_CHILD and _pending_parent_exists(to_org):
            raise RelationshipError(
                f"{to_org.name} already has a parent organization (or a pending request).",
                code="parent_exists",
            )
        if kind == Kind.UMBRELLA_MEMBER and OrganizationRelationship.objects.filter(
            kind=Kind.UMBRELLA_MEMBER, to_organization=to_org
        ).filter(_open_q()).exists():
            raise RelationshipError(
                f"{to_org.name} is already covered by an umbrella license.",
                code="umbrella_exists",
            )
        # from_org would become an ancestor of to_org; refuse if to_org is
        # already above from_org (cycle).
        if _is_ancestor(to_org, from_org):
            raise RelationshipError(
                "This would create a circular parent/child chain.",
                code="cycle",
            )


# --------------------------------------------------------------------------- #
# Inbox helpers
# --------------------------------------------------------------------------- #


def _post_message(
    *,
    conversation: Conversation | None,
    sender_org: Organization,
    recipient_org: Organization,
    subject: str,
    body: str,
) -> Conversation:
    sender_mailbox = get_organization_mailbox(sender_org)
    recipient_mailbox = get_organization_mailbox(recipient_org)
    now = timezone.now()
    if conversation is None:
        conversation = Conversation.objects.create(subject=subject[:200])
    for mailbox, read_at in ((sender_mailbox, now), (recipient_mailbox, None)):
        ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            mailbox=mailbox,
            defaults={
                "folder": ConversationParticipant.Folder.PRIMARY,
                "last_read_at": read_at,
            },
        )
    InboxMessage.objects.create(
        conversation=conversation,
        sender_mailbox=sender_mailbox,
        subject=subject[:200],
        body=body,
        status=InboxMessage.Status.SENT,
        sent_at=now,
    )
    conversation.updated_at = now
    conversation.save(update_fields=["updated_at"])
    return conversation


def _kind_sentence(rel: OrganizationRelationship) -> str:
    f, t = rel.from_organization.name, rel.to_organization.name
    if rel.kind == Kind.PARENT_CHILD:
        return f"{f} as the parent organization of {t}"
    if rel.kind == Kind.UMBRELLA_MEMBER:
        return f"{t} as a member of {f}'s umbrella license"
    if rel.kind == Kind.SPONSOR:
        return f"{f} as a sponsor of {t}"
    return f"{f} and {t} as partners"


def _relationship_subject(rel: OrganizationRelationship) -> str:
    return f"Relationship request: {rel.get_kind_display()}"


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #


@transaction.atomic
def request_relationship(
    *,
    requesting_org: Organization,
    target_org: Organization,
    direction: str,
    user: User | None,
    note: str = "",
    public: bool = True,
) -> OrganizationRelationship:
    """Create a pending relationship and send the request to the target inbox."""
    try:
        kind, my_role = DIRECTION_MAP[direction]
    except KeyError as exc:
        raise RelationshipError("Unknown relationship type.", code="invalid_kind") from exc

    if my_role == "from":
        from_org, to_org = requesting_org, target_org
    else:
        from_org, to_org = target_org, requesting_org

    _validate_new(kind, from_org, to_org)

    rel = OrganizationRelationship.objects.create(
        kind=kind,
        status=Status.PENDING,
        from_organization=from_org,
        to_organization=to_org,
        initiated_by_organization=requesting_org,
        requested_by=user,
        note=(note or "").strip()[:500],
        public=bool(public),
        expires_at=timezone.now() + timedelta(days=REQUEST_TTL_DAYS),
    )

    body = (
        f"{requesting_org.name} would like to establish a relationship: "
        f"{_kind_sentence(rel)}.\n\n"
        "Relationships appear on organization hubs and make it easier to share "
        "meeting and survey results, but do not grant admin access or data access "
        "on their own.\n\n"
        "Use the Accept or Decline buttons above to respond."
    )
    if rel.note:
        body += f"\n\nMessage from {requesting_org.name}: {rel.note}"

    rel.conversation = _post_message(
        conversation=None,
        sender_org=requesting_org,
        recipient_org=target_org,
        subject=_relationship_subject(rel),
        body=body,
    )
    rel.save(update_fields=["conversation"])
    return rel


def _sync_parent_pointer(rel: OrganizationRelationship) -> None:
    if rel.kind != Kind.PARENT_CHILD:
        return
    child = rel.to_organization
    if rel.status == Status.ACCEPTED:
        if child.parent_organization_id != rel.from_organization_id:
            child.parent_organization = rel.from_organization
            child.save(update_fields=["parent_organization"])
    elif child.parent_organization_id == rel.from_organization_id:
        child.parent_organization = None
        child.save(update_fields=["parent_organization"])


def _require_pending(rel: OrganizationRelationship) -> None:
    expire_if_due(rel)
    if rel.status != Status.PENDING:
        raise RelationshipError(
            f"This request is no longer pending ({rel.get_status_display()}).",
            code="not_pending",
        )


def expire_if_due(rel: OrganizationRelationship) -> bool:
    if (
        rel.status == Status.PENDING
        and rel.expires_at
        and rel.expires_at <= timezone.now()
    ):
        rel.status = Status.EXPIRED
        rel.save(update_fields=["status"])
        return True
    return False


@transaction.atomic
def accept_relationship(
    rel: OrganizationRelationship, *, acting_org: Organization, user: User | None
) -> OrganizationRelationship:
    _require_pending(rel)
    if acting_org.id != rel.recipient_organization.id:
        raise RelationshipError(
            "Only the organization that received this request can accept it.",
            code="not_recipient",
        )
    # Re-validate: another parent may have been accepted while this was pending.
    kind = rel.kind
    if kind == Kind.PARENT_CHILD and accepted_parent(rel.to_organization):
        raise RelationshipError(
            f"{rel.to_organization.name} already has a parent organization.",
            code="parent_exists",
        )
    if kind in (Kind.PARENT_CHILD, Kind.UMBRELLA_MEMBER) and _is_ancestor(
        rel.to_organization, rel.from_organization
    ):
        raise RelationshipError(
            "This would create a circular parent/child chain.", code="cycle"
        )

    now = timezone.now()
    rel.status = Status.ACCEPTED
    rel.responded_by = user
    rel.responded_at = now
    rel.save(update_fields=["status", "responded_by", "responded_at"])
    _sync_parent_pointer(rel)

    _post_message(
        conversation=rel.conversation,
        sender_org=acting_org,
        recipient_org=rel.counterpart_of(acting_org),
        subject=_relationship_subject(rel),
        body=f"{acting_org.name} accepted: {_kind_sentence(rel)}.",
    )
    return rel


@transaction.atomic
def decline_relationship(
    rel: OrganizationRelationship, *, acting_org: Organization, user: User | None
) -> OrganizationRelationship:
    _require_pending(rel)
    if acting_org.id != rel.recipient_organization.id:
        raise RelationshipError(
            "Only the organization that received this request can decline it.",
            code="not_recipient",
        )
    rel.status = Status.DECLINED
    rel.responded_by = user
    rel.responded_at = timezone.now()
    rel.save(update_fields=["status", "responded_by", "responded_at"])
    _post_message(
        conversation=rel.conversation,
        sender_org=acting_org,
        recipient_org=rel.counterpart_of(acting_org),
        subject=_relationship_subject(rel),
        body=f"{acting_org.name} declined the relationship request.",
    )
    return rel


@transaction.atomic
def cancel_request(
    rel: OrganizationRelationship, *, acting_org: Organization, user: User | None
) -> OrganizationRelationship:
    """Requester withdraws its own pending request."""
    _require_pending(rel)
    if acting_org.id != rel.initiated_by_organization_id:
        raise RelationshipError(
            "Only the requesting organization can withdraw this request.",
            code="not_requester",
        )
    rel.status = Status.ENDED
    rel.ended_at = timezone.now()
    rel.ended_by_organization = acting_org
    rel.responded_by = user
    rel.save(update_fields=["status", "ended_at", "ended_by_organization", "responded_by"])
    _post_message(
        conversation=rel.conversation,
        sender_org=acting_org,
        recipient_org=rel.counterpart_of(acting_org),
        subject=_relationship_subject(rel),
        body=f"{acting_org.name} withdrew the relationship request.",
    )
    return rel


@transaction.atomic
def end_relationship(
    rel: OrganizationRelationship, *, acting_org: Organization, user: User | None
) -> OrganizationRelationship:
    """Either side ends an accepted relationship; the other side is notified."""
    if rel.status != Status.ACCEPTED:
        raise RelationshipError("This relationship is not active.", code="not_active")
    if acting_org.id not in (rel.from_organization_id, rel.to_organization_id):
        raise RelationshipError("You are not part of this relationship.", code="not_party")
    rel.status = Status.ENDED
    rel.ended_at = timezone.now()
    rel.ended_by_organization = acting_org
    rel.save(update_fields=["status", "ended_at", "ended_by_organization"])
    _sync_parent_pointer(rel)
    _post_message(
        conversation=rel.conversation,
        sender_org=acting_org,
        recipient_org=rel.counterpart_of(acting_org),
        subject=_relationship_subject(rel),
        body=f"{acting_org.name} ended the relationship: {_kind_sentence(rel)}.",
    )
    return rel


def set_public(
    rel: OrganizationRelationship, *, acting_org: Organization, public: bool
) -> OrganizationRelationship:
    if acting_org.id not in (rel.from_organization_id, rel.to_organization_id):
        raise RelationshipError("You are not part of this relationship.", code="not_party")
    rel.public = bool(public)
    rel.save(update_fields=["public"])
    return rel


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #


def describe_for(rel: OrganizationRelationship, organization: Organization) -> str:
    """Short label from ``organization``'s point of view."""
    other = rel.counterpart_of(organization)
    if rel.kind == Kind.PARENT_CHILD:
        if rel.from_organization_id == organization.id:
            return f"Parent of {other.name}"
        return f"Chapter / member of {other.name}"
    if rel.kind == Kind.UMBRELLA_MEMBER:
        if rel.from_organization_id == organization.id:
            return f"{other.name} uses your umbrella license"
        return f"Covered by {other.name}'s umbrella license"
    if rel.kind == Kind.SPONSOR:
        if rel.from_organization_id == organization.id:
            return f"Sponsor of {other.name}"
        return f"Sponsored by {other.name}"
    return f"Partner with {other.name}"


def serialize_relationship(
    rel: OrganizationRelationship, *, for_organization: Organization
) -> dict:
    expire_if_due(rel)
    other = rel.counterpart_of(for_organization)
    is_recipient = rel.recipient_organization.id == for_organization.id
    return {
        "id": rel.id,
        "kind": rel.kind,
        "kind_label": rel.get_kind_display(),
        "status": rel.status,
        "description": describe_for(rel, for_organization),
        "other_organization": _org_ref(other),
        "from_organization": _org_ref(rel.from_organization),
        "to_organization": _org_ref(rel.to_organization),
        "initiated_by_me": rel.initiated_by_organization_id == for_organization.id,
        "can_respond": rel.status == Status.PENDING and is_recipient,
        "can_withdraw": rel.status == Status.PENDING and not is_recipient,
        "can_end": rel.status == Status.ACCEPTED and rel.kind != Kind.UMBRELLA_MEMBER,
        "public": rel.public,
        "note": rel.note,
        "conversation_id": rel.conversation_id,
        "created_at": rel.created_at,
        "expires_at": rel.expires_at,
        "responded_at": rel.responded_at,
        "ended_at": rel.ended_at,
    }


def settings_payload(organization: Organization) -> dict:
    rows = list(relationships_for(organization))
    for row in rows:
        expire_if_due(row)
    active = [r for r in rows if r.status == Status.ACCEPTED]
    incoming = [
        r
        for r in rows
        if r.status == Status.PENDING and r.recipient_organization.id == organization.id
    ]
    outgoing = [
        r
        for r in rows
        if r.status == Status.PENDING and r.initiated_by_organization_id == organization.id
    ]
    history = [
        r for r in rows if r.status in (Status.DECLINED, Status.ENDED, Status.EXPIRED)
    ][:20]
    ser = lambda r: serialize_relationship(r, for_organization=organization)  # noqa: E731
    return {
        "organization": _org_ref(organization),
        "directions": [
            {"value": key, "label": label} for key, label in DIRECTION_LABELS.items()
        ],
        "active": [ser(r) for r in active],
        "incoming_pending": [ser(r) for r in incoming],
        "outgoing_pending": [ser(r) for r in outgoing],
        "history": [ser(r) for r in history],
    }


def conversation_relationship_payload(
    conversation: Conversation, *, viewer_org: Organization | None
) -> dict | None:
    """Attach relationship state to an inbox thread so the UI can show Accept/Decline."""
    rel = (
        OrganizationRelationship.objects.filter(conversation=conversation)
        .select_related(
            "from_organization", "to_organization", "initiated_by_organization"
        )
        .order_by("-id")
        .first()
    )
    if not rel:
        return None
    expire_if_due(rel)
    payload = {
        "id": rel.id,
        "kind": rel.kind,
        "kind_label": rel.get_kind_display(),
        "status": rel.status,
        "summary": _kind_sentence(rel),
        "recipient_organization": _org_ref(rel.recipient_organization),
        "can_respond": False,
    }
    if viewer_org is not None:
        payload["can_respond"] = (
            rel.status == Status.PENDING
            and rel.recipient_organization.id == viewer_org.id
        )
        payload["viewer_organization_slug"] = viewer_org.slug
    return payload
