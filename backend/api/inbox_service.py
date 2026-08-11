"""
Unified inbox for personal and organization mailboxes.

Same Conversation / InboxMessage models for both. Folders:
  - primary: known contacts / accepted threads
  - unknown: first contact from mailboxes you have not accepted yet
  - drafts: unsent messages owned by the mailbox (status=draft)
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from api.board_service import is_org_admin, is_org_member
from api.models import (
    Conversation,
    ConversationParticipant,
    InboxMessage,
    Mailbox,
    MailboxBlock,
    Organization,
)


def get_personal_mailbox(user: User) -> Mailbox:
    mailbox, _ = Mailbox.objects.get_or_create(
        user=user,
        defaults={"kind": Mailbox.Kind.PERSONAL},
    )
    return mailbox


def get_organization_mailbox(organization: Organization) -> Mailbox:
    mailbox, _ = Mailbox.objects.get_or_create(
        organization=organization,
        defaults={"kind": Mailbox.Kind.ORGANIZATION},
    )
    return mailbox


def mailbox_label(mailbox: Mailbox) -> dict:
    if mailbox.kind == Mailbox.Kind.ORGANIZATION and mailbox.organization_id:
        org = mailbox.organization
        return {
            "id": mailbox.id,
            "kind": mailbox.kind,
            "display_name": org.name,
            "username": None,
            "organization_slug": org.slug,
        }
    user = mailbox.user
    profile = getattr(user, "profile", None) if user else None
    return {
        "id": mailbox.id,
        "kind": mailbox.kind,
        "display_name": (profile.display_name if profile and profile.display_name else None)
        or (user.username if user else "Unknown"),
        "username": user.username if user else None,
        "organization_slug": None,
    }


def resolve_recipient_mailbox(
    *,
    to_username: str | None = None,
    to_organization_slug: str | None = None,
) -> Mailbox:
    username = (to_username or "").strip()
    org_slug = (to_organization_slug or "").strip()
    if bool(username) == bool(org_slug):
        raise ValidationError(
            "Provide exactly one of to_username or to_organization_slug."
        )
    if username:
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist as exc:
            raise ValidationError("No user found with that username.") from exc
        return get_personal_mailbox(user)
    org = Organization.objects.filter(slug=org_slug, is_active=True).first()
    if not org:
        raise ValidationError("Organization not found.")
    return get_organization_mailbox(org)


def _have_prior_accepted_contact(a: Mailbox, b: Mailbox) -> bool:
    """True if these mailboxes already share a primary (accepted) conversation."""
    a_primary = ConversationParticipant.objects.filter(
        mailbox=a, folder=ConversationParticipant.Folder.PRIMARY
    ).values_list("conversation_id", flat=True)
    return ConversationParticipant.objects.filter(
        mailbox=b,
        folder=ConversationParticipant.Folder.PRIMARY,
        conversation_id__in=a_primary,
    ).exists()


def _recipient_folder_for(sender: Mailbox, recipient: Mailbox) -> str:
    if _have_prior_accepted_contact(sender, recipient):
        return ConversationParticipant.Folder.PRIMARY
    # Org members messaging their own org land in primary.
    if (
        recipient.kind == Mailbox.Kind.ORGANIZATION
        and sender.kind == Mailbox.Kind.PERSONAL
        and sender.user_id
        and is_org_member(recipient.organization, sender.user)
    ):
        return ConversationParticipant.Folder.PRIMARY
    if (
        sender.kind == Mailbox.Kind.ORGANIZATION
        and recipient.kind == Mailbox.Kind.PERSONAL
        and recipient.user_id
        and is_org_member(sender.organization, recipient.user)
    ):
        return ConversationParticipant.Folder.PRIMARY
    return ConversationParticipant.Folder.UNKNOWN


def user_can_access_mailbox(user: User, mailbox: Mailbox) -> bool:
    if mailbox.kind == Mailbox.Kind.PERSONAL:
        return mailbox.user_id == user.id
    return is_org_admin(mailbox.organization, user)


def require_mailbox_access(user: User, mailbox: Mailbox) -> None:
    if not user_can_access_mailbox(user, mailbox):
        raise ValidationError("You do not have access to this inbox.")


def is_blocked(*, blocker: Mailbox, blocked: Mailbox) -> bool:
    return MailboxBlock.objects.filter(blocker=blocker, blocked=blocked).exists()


def either_blocks(a: Mailbox, b: Mailbox) -> bool:
    return MailboxBlock.objects.filter(
        Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)
    ).exists()


def blocked_mailbox_ids_for(mailbox: Mailbox) -> set[int]:
    """Mailboxes that this mailbox blocked, or that blocked this mailbox."""
    rows = MailboxBlock.objects.filter(
        Q(blocker=mailbox) | Q(blocked=mailbox)
    ).values_list("blocker_id", "blocked_id")
    ids: set[int] = set()
    for blocker_id, blocked_id in rows:
        if blocker_id == mailbox.id:
            ids.add(blocked_id)
        else:
            ids.add(blocker_id)
    return ids


def list_conversations_for_mailbox(mailbox: Mailbox, *, folder: str):
    folder = (folder or ConversationParticipant.Folder.PRIMARY).strip().lower()
    if folder not in {
        ConversationParticipant.Folder.PRIMARY,
        ConversationParticipant.Folder.UNKNOWN,
        ConversationParticipant.Folder.ARCHIVED,
    }:
        raise ValidationError("Invalid folder.")

    last_sent = (
        InboxMessage.objects.filter(
            conversation_id=OuterRef("conversation_id"),
            status=InboxMessage.Status.SENT,
        )
        .order_by("-sent_at", "-id")
        .values("body")[:1]
    )
    last_sent_at = (
        InboxMessage.objects.filter(
            conversation_id=OuterRef("conversation_id"),
            status=InboxMessage.Status.SENT,
        )
        .order_by("-sent_at", "-id")
        .values("sent_at")[:1]
    )

    blocked_ids = blocked_mailbox_ids_for(mailbox)
    qs = (
        ConversationParticipant.objects.filter(mailbox=mailbox, folder=folder)
        .select_related("conversation")
        .annotate(
            preview=Subquery(last_sent),
            last_message_at=Subquery(last_sent_at),
        )
        .order_by("-conversation__updated_at")
    )
    if not blocked_ids:
        return qs

    # Hide threads that include a blocked counterparty (ban = they cannot see you / you don't see them).
    hidden_conversation_ids = ConversationParticipant.objects.filter(
        mailbox_id__in=blocked_ids
    ).values_list("conversation_id", flat=True)
    return qs.exclude(conversation_id__in=hidden_conversation_ids)


def serialize_conversation_list_item(link: ConversationParticipant, mailbox: Mailbox) -> dict:
    conversation = link.conversation
    others = (
        ConversationParticipant.objects.filter(conversation=conversation)
        .exclude(mailbox=mailbox)
        .select_related("mailbox__user__profile", "mailbox__organization")
    )
    counterparties = [mailbox_label(p.mailbox) for p in others]
    unread = False
    if link.last_read_at is None:
        unread = InboxMessage.objects.filter(
            conversation=conversation,
            status=InboxMessage.Status.SENT,
        ).exclude(sender_mailbox=mailbox).exists()
    else:
        unread = InboxMessage.objects.filter(
            conversation=conversation,
            status=InboxMessage.Status.SENT,
            sent_at__gt=link.last_read_at,
        ).exclude(sender_mailbox=mailbox).exists()

    preview = getattr(link, "preview", None) or ""
    return {
        "id": conversation.id,
        "subject": conversation.subject,
        "folder": link.folder,
        "updated_at": conversation.updated_at,
        "last_message_at": getattr(link, "last_message_at", None),
        "preview": (preview or "")[:180],
        "unread": unread,
        "counterparties": counterparties,
    }


def inbox_summary(mailbox: Mailbox) -> dict:
    primary_unread = 0
    unknown_unread = 0
    for link in ConversationParticipant.objects.filter(mailbox=mailbox).exclude(
        folder=ConversationParticipant.Folder.ARCHIVED
    ):
        item = serialize_conversation_list_item(link, mailbox)
        if not item["unread"]:
            continue
        if link.folder == ConversationParticipant.Folder.UNKNOWN:
            unknown_unread += 1
        elif link.folder == ConversationParticipant.Folder.PRIMARY:
            primary_unread += 1

    drafts_count = InboxMessage.objects.filter(
        sender_mailbox=mailbox, status=InboxMessage.Status.DRAFT
    ).count()
    return {
        "mailbox": mailbox_label(mailbox),
        "primary_unread": primary_unread,
        "unknown_unread": unknown_unread,
        "drafts_count": drafts_count,
    }


def list_drafts(mailbox: Mailbox):
    return (
        InboxMessage.objects.filter(
            sender_mailbox=mailbox, status=InboxMessage.Status.DRAFT
        )
        .select_related("draft_to_mailbox__user__profile", "draft_to_mailbox__organization")
        .order_by("-updated_at")
    )


def serialize_draft(message: InboxMessage) -> dict:
    return {
        "id": message.id,
        "subject": message.subject,
        "body": message.body,
        "conversation_id": message.conversation_id,
        "to": mailbox_label(message.draft_to_mailbox) if message.draft_to_mailbox_id else None,
        "updated_at": message.updated_at,
        "created_at": message.created_at,
    }


def save_draft(
    *,
    mailbox: Mailbox,
    draft_id: int | None = None,
    subject: str | None = None,
    body: str | None = None,
    to_username: str | None = None,
    to_organization_slug: str | None = None,
    conversation_id: int | None = None,
) -> InboxMessage:
    to_mailbox = None
    if to_username or to_organization_slug:
        to_mailbox = resolve_recipient_mailbox(
            to_username=to_username,
            to_organization_slug=to_organization_slug,
        )
        if to_mailbox.id == mailbox.id:
            raise ValidationError("You cannot message your own mailbox.")
        if either_blocks(mailbox, to_mailbox):
            raise ValidationError("You cannot message this account.")

    conversation = None
    if conversation_id:
        link = ConversationParticipant.objects.filter(
            conversation_id=conversation_id, mailbox=mailbox
        ).first()
        if not link:
            raise ValidationError("Conversation not found in this inbox.")
        conversation = link.conversation

    if draft_id:
        draft = InboxMessage.objects.filter(
            pk=draft_id,
            sender_mailbox=mailbox,
            status=InboxMessage.Status.DRAFT,
        ).first()
        if not draft:
            raise ValidationError("Draft not found.")
        if subject is not None:
            draft.subject = (subject or "").strip()[:200]
        if body is not None:
            draft.body = body or ""
        if to_mailbox is not None:
            draft.draft_to_mailbox = to_mailbox
        if conversation is not None:
            draft.conversation = conversation
        draft.save()
        return draft

    return InboxMessage.objects.create(
        sender_mailbox=mailbox,
        draft_to_mailbox=to_mailbox,
        conversation=conversation,
        subject=(subject or "").strip()[:200],
        body=body or "",
        status=InboxMessage.Status.DRAFT,
    )


@transaction.atomic
def send_draft(mailbox: Mailbox, draft_id: int) -> Conversation:
    draft = (
        InboxMessage.objects.select_for_update()
        .filter(pk=draft_id, sender_mailbox=mailbox, status=InboxMessage.Status.DRAFT)
        .first()
    )
    if not draft:
        raise ValidationError("Draft not found.")
    body = (draft.body or "").strip()
    if not body:
        raise ValidationError("Message body is required to send.")

    conversation = draft.conversation
    recipient = draft.draft_to_mailbox

    if conversation is None:
        if recipient is None:
            raise ValidationError("Choose a recipient before sending.")
        if either_blocks(mailbox, recipient):
            raise ValidationError("You cannot message this account.")
        conversation = Conversation.objects.create(
            subject=(draft.subject or "").strip()[:200] or "Message"
        )
        ConversationParticipant.objects.create(
            conversation=conversation,
            mailbox=mailbox,
            folder=ConversationParticipant.Folder.PRIMARY,
            last_read_at=timezone.now(),
        )
        ConversationParticipant.objects.create(
            conversation=conversation,
            mailbox=recipient,
            folder=_recipient_folder_for(mailbox, recipient),
            last_read_at=None,
        )
        draft.conversation = conversation
    else:
        # Reply draft: ensure sender is a participant; recipient already on thread.
        others = ConversationParticipant.objects.filter(
            conversation=conversation
        ).exclude(mailbox=mailbox)
        for other in others:
            if either_blocks(mailbox, other.mailbox):
                raise ValidationError("You cannot message this account.")
        ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            mailbox=mailbox,
            defaults={
                "folder": ConversationParticipant.Folder.PRIMARY,
                "last_read_at": timezone.now(),
            },
        )
        if not conversation.subject and draft.subject:
            conversation.subject = draft.subject.strip()[:200]

    now = timezone.now()
    draft.status = InboxMessage.Status.SENT
    draft.sent_at = now
    draft.subject = draft.subject or conversation.subject
    draft.save()
    conversation.updated_at = now
    conversation.save(update_fields=["subject", "updated_at"])

    return conversation


@transaction.atomic
def send_new_message(
    *,
    mailbox: Mailbox,
    subject: str,
    body: str,
    to_username: str | None = None,
    to_organization_slug: str | None = None,
) -> Conversation:
    draft = save_draft(
        mailbox=mailbox,
        subject=subject,
        body=body,
        to_username=to_username,
        to_organization_slug=to_organization_slug,
    )
    return send_draft(mailbox, draft.id)


def delete_draft(mailbox: Mailbox, draft_id: int) -> None:
    deleted, _ = InboxMessage.objects.filter(
        pk=draft_id, sender_mailbox=mailbox, status=InboxMessage.Status.DRAFT
    ).delete()
    if not deleted:
        raise ValidationError("Draft not found.")


def get_conversation_for_mailbox(mailbox: Mailbox, conversation_id: int) -> ConversationParticipant:
    link = (
        ConversationParticipant.objects.filter(
            mailbox=mailbox, conversation_id=conversation_id
        )
        .select_related("conversation")
        .first()
    )
    if not link:
        raise ValidationError("Conversation not found in this inbox.")
    others = ConversationParticipant.objects.filter(
        conversation_id=conversation_id
    ).exclude(mailbox=mailbox)
    for other in others:
        if either_blocks(mailbox, other.mailbox):
            raise ValidationError("Conversation not found in this inbox.")
    return link


def mark_conversation_read(link: ConversationParticipant) -> None:
    """Mark read only — never move/delete the conversation."""
    link.last_read_at = timezone.now()
    link.save(update_fields=["last_read_at"])
    # Refresh so serializers see the updated timestamp.
    link.refresh_from_db()


def accept_unknown_conversation(mailbox: Mailbox, conversation_id: int) -> ConversationParticipant:
    link = get_conversation_for_mailbox(mailbox, conversation_id)
    if link.folder != ConversationParticipant.Folder.UNKNOWN:
        return link
    link.folder = ConversationParticipant.Folder.PRIMARY
    link.save(update_fields=["folder"])
    return link


def decline_unknown_conversation(mailbox: Mailbox, conversation_id: int) -> None:
    link = get_conversation_for_mailbox(mailbox, conversation_id)
    if link.folder != ConversationParticipant.Folder.UNKNOWN:
        raise ValidationError("Only unknown message requests can be declined this way.")
    link.folder = ConversationParticipant.Folder.ARCHIVED
    link.save(update_fields=["folder"])


def delete_conversation_for_mailbox(mailbox: Mailbox, conversation_id: int) -> None:
    """Remove this conversation from the current mailbox only."""
    link = get_conversation_for_mailbox(mailbox, conversation_id)
    conversation = link.conversation
    link.delete()
    if not ConversationParticipant.objects.filter(conversation=conversation).exists():
        conversation.delete()


@transaction.atomic
def ban_counterparty(mailbox: Mailbox, conversation_id: int) -> None:
    """
    Ban the other party in this conversation.
    They can no longer see or message this mailbox; shared threads leave both inboxes.
    """
    link = ConversationParticipant.objects.filter(
        mailbox=mailbox, conversation_id=conversation_id
    ).select_related("conversation").first()
    if not link:
        raise ValidationError("Conversation not found in this inbox.")

    others = list(
        ConversationParticipant.objects.filter(conversation=link.conversation)
        .exclude(mailbox=mailbox)
        .select_related("mailbox")
    )
    if not others:
        raise ValidationError("No counterpart to ban.")

    for other in others:
        MailboxBlock.objects.get_or_create(blocker=mailbox, blocked=other.mailbox)
        my_conv_ids = ConversationParticipant.objects.filter(
            mailbox=mailbox
        ).values_list("conversation_id", flat=True)
        shared_ids = list(
            ConversationParticipant.objects.filter(
                mailbox=other.mailbox, conversation_id__in=my_conv_ids
            ).values_list("conversation_id", flat=True)
        )
        ConversationParticipant.objects.filter(
            conversation_id__in=shared_ids,
            mailbox_id__in=[mailbox.id, other.mailbox_id],
        ).delete()
        for cid in shared_ids:
            if not ConversationParticipant.objects.filter(conversation_id=cid).exists():
                Conversation.objects.filter(pk=cid).delete()


def serialize_message(message: InboxMessage) -> dict:
    return {
        "id": message.id,
        "subject": message.subject,
        "body": message.body,
        "status": message.status,
        "sent_at": message.sent_at,
        "created_at": message.created_at,
        "sender": mailbox_label(message.sender_mailbox),
    }
