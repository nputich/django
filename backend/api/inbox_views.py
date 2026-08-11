"""HTTP API for the unified personal / organization inbox."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.inbox_service import (
    accept_unknown_conversation,
    ban_counterparty,
    decline_unknown_conversation,
    delete_conversation_for_mailbox,
    delete_draft,
    get_conversation_for_mailbox,
    get_organization_mailbox,
    get_personal_mailbox,
    inbox_summary,
    list_conversations_for_mailbox,
    list_drafts,
    mark_conversation_read,
    require_mailbox_access,
    save_draft,
    send_draft,
    send_new_message,
    serialize_conversation_list_item,
    serialize_draft,
    serialize_message,
)
from api.models import ConversationParticipant, InboxMessage, Organization
from api.org_access import get_admin_organization
from api.serializers import (
    InboxComposeSerializer,
    InboxDraftSaveSerializer,
)


def _validation_response(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    messages = getattr(exc, "messages", None)
    detail = messages[0] if messages else str(exc)
    return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class PersonalMailboxMixin:
    def get_mailbox(self, request):
        mailbox = get_personal_mailbox(request.user)
        require_mailbox_access(request.user, mailbox)
        return mailbox


class OrganizationMailboxMixin:
    def get_mailbox(self, request, slug):
        organization = get_admin_organization(request.user, slug)
        mailbox = get_organization_mailbox(organization)
        require_mailbox_access(request.user, mailbox)
        return mailbox


class InboxSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(inbox_summary(mailbox))


class InboxConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug=None):
        folder = request.query_params.get("folder", ConversationParticipant.Folder.PRIMARY)
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            links = list_conversations_for_mailbox(mailbox, folder=folder)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)

        return Response(
            {
                **inbox_summary(mailbox),
                "folder": folder,
                "conversations": [
                    serialize_conversation_list_item(link, mailbox) for link in links
                ],
            }
        )

    def post(self, request, slug=None):
        """Compose + send a new message (also creates an intermediate draft)."""
        serializer = InboxComposeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            conversation = send_new_message(
                mailbox=mailbox,
                subject=data.get("subject", ""),
                body=data["body"],
                to_username=data.get("to_username"),
                to_organization_slug=data.get("to_organization_slug"),
            )
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)

        link = get_conversation_for_mailbox(mailbox, conversation.id)
        return Response(
            serialize_conversation_list_item(link, mailbox),
            status=status.HTTP_201_CREATED,
        )


class InboxConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            link = get_conversation_for_mailbox(mailbox, pk)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)

        mark_conversation_read(link)
        messages = (
            InboxMessage.objects.filter(
                conversation=link.conversation, status=InboxMessage.Status.SENT
            )
            .select_related(
                "sender_mailbox__user__profile", "sender_mailbox__organization"
            )
            .order_by("sent_at", "id")
        )
        return Response(
            {
                **serialize_conversation_list_item(link, mailbox),
                "messages": [serialize_message(m) for m in messages],
            }
        )

    def delete(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            delete_conversation_for_mailbox(mailbox, pk)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InboxConversationBanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            ban_counterparty(mailbox, pk)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response({"detail": "User banned."}, status=status.HTTP_200_OK)


class InboxConversationAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            link = accept_unknown_conversation(mailbox, pk)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(serialize_conversation_list_item(link, mailbox))


class InboxConversationDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            decline_unknown_conversation(mailbox, pk)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InboxDraftListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        drafts = list_drafts(mailbox)
        return Response(
            {
                **inbox_summary(mailbox),
                "drafts": [serialize_draft(d) for d in drafts],
            }
        )

    def post(self, request, slug=None):
        serializer = InboxDraftSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            draft = save_draft(
                mailbox=mailbox,
                draft_id=data.get("id"),
                subject=data.get("subject", ""),
                body=data.get("body", ""),
                to_username=data.get("to_username"),
                to_organization_slug=data.get("to_organization_slug"),
                conversation_id=data.get("conversation_id"),
            )
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(serialize_draft(draft), status=status.HTTP_201_CREATED)


class InboxDraftDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, slug=None):
        serializer = InboxDraftSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            draft = save_draft(
                mailbox=mailbox,
                draft_id=pk,
                subject=data.get("subject") if "subject" in data else None,
                body=data.get("body") if "body" in data else None,
                to_username=data.get("to_username"),
                to_organization_slug=data.get("to_organization_slug"),
                conversation_id=data.get("conversation_id"),
            )
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(serialize_draft(draft))

    def delete(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            delete_draft(mailbox, pk)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InboxDraftSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, slug=None):
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            conversation = send_draft(mailbox, pk)
            link = get_conversation_for_mailbox(mailbox, conversation.id)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(
            serialize_conversation_list_item(link, mailbox),
            status=status.HTTP_200_OK,
        )


class InboxReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, slug=None):
        """Save a reply as draft (default) or send immediately when send=true."""
        body = (request.data.get("body") or "").strip()
        subject = (request.data.get("subject") or "").strip()
        send_now = str(request.data.get("send", "")).lower() in ("1", "true", "yes")
        try:
            mailbox = (
                OrganizationMailboxMixin().get_mailbox(request, slug)
                if slug
                else PersonalMailboxMixin().get_mailbox(request)
            )
            get_conversation_for_mailbox(mailbox, pk)
            draft = save_draft(
                mailbox=mailbox,
                subject=subject,
                body=body,
                conversation_id=pk,
            )
            if send_now:
                conversation = send_draft(mailbox, draft.id)
                link = get_conversation_for_mailbox(mailbox, conversation.id)
                messages = (
                    InboxMessage.objects.filter(
                        conversation=conversation, status=InboxMessage.Status.SENT
                    )
                    .select_related(
                        "sender_mailbox__user__profile",
                        "sender_mailbox__organization",
                    )
                    .order_by("sent_at", "id")
                )
                return Response(
                    {
                        **serialize_conversation_list_item(link, mailbox),
                        "messages": [serialize_message(m) for m in messages],
                    }
                )
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return _validation_response(exc)
        return Response(serialize_draft(draft), status=status.HTTP_201_CREATED)
