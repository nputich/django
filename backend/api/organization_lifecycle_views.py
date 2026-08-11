"""Owner-facing organization ownership, subscription cancel, and close APIs."""

from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing_service import (
    CheckoutError,
    get_active_organization_service,
    get_current_service_summary,
    request_cancel_paid_service,
    serialize_organization_service,
)
from .models import Organization, OrganizationMembership
from .org_access import get_admin_organization, get_owner_organization
from .organization_lifecycle import (
    LifecycleError,
    cancel_my_ownership,
    cancel_organization_closure,
    close_organization,
    count_owners,
    ensure_organization_lifecycle,
    list_transfer_candidates,
    record_audit,
    restore_organization,
    serialize_lifecycle,
    transfer_ownership,
)
from .models import OrganizationAuditEvent
from .paypal_client import PayPalError


def _lifecycle_error_response(exc: LifecycleError | CheckoutError | PayPalError):
    code = getattr(exc, "code", "error")
    message = getattr(exc, "message", None) or str(exc)
    http = status.HTTP_400_BAD_REQUEST
    if code in {"not_owner", "not_staff"}:
        http = status.HTTP_403_FORBIDDEN
    if code == "paypal_cancel_failed" or code.startswith("paypal_"):
        http = status.HTTP_502_BAD_GATEWAY
    return Response({"detail": message, "code": code}, status=http)


class OrganizationOwnershipSettingsView(APIView):
    """GET ownership & organization settings payload for owners/admins."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ensure_organization_lifecycle(organization)
        membership = organization.memberships.filter(user=request.user).first()
        is_owner = bool(
            membership and membership.role == OrganizationMembership.Role.OWNER
        )
        owners = organization.memberships.filter(
            role=OrganizationMembership.Role.OWNER
        ).select_related("user")
        candidates = list_transfer_candidates(organization, exclude_user=request.user)
        active = get_active_organization_service(organization)
        return Response(
            {
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                    "description": organization.description,
                },
                "lifecycle": serialize_lifecycle(organization),
                "membership": {
                    "role": membership.role if membership else None,
                    "is_owner": is_owner,
                    "owner_count": count_owners(organization),
                },
                "owners": [
                    {
                        "user_id": m.user_id,
                        "username": m.user.username,
                    }
                    for m in owners
                ],
                "transfer_candidates": [
                    {
                        "user_id": m.user_id,
                        "username": m.user.username,
                        "role": m.role,
                    }
                    for m in candidates
                ],
                "billing": get_current_service_summary(organization),
                "active_service": serialize_organization_service(active),
            }
        )


class OrganizationOwnershipTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            organization = get_owner_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not the owner."},
                status=status.HTTP_404_NOT_FOUND,
            )
        target_id = request.data.get("new_owner_user_id")
        try:
            new_owner = User.objects.get(pk=target_id)
        except (User.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "Select an administrator to transfer ownership to.", "code": "invalid_target"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            transfer_ownership(organization, actor=request.user, new_owner=new_owner)
        except LifecycleError as exc:
            return _lifecycle_error_response(exc)
        return Response({"detail": "Ownership transferred.", "lifecycle": serialize_lifecycle(organization)})


class OrganizationOwnershipCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            organization = get_owner_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not the owner."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            cancel_my_ownership(organization, actor=request.user)
        except LifecycleError as exc:
            return _lifecycle_error_response(exc)
        return Response({"detail": "Your ownership has been canceled."})


class OrganizationSubscriptionCancelView(APIView):
    """Cancel paid service only — does not close the organization."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            organization = get_owner_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not the owner."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if organization.status == Organization.Status.CLOSED:
            return Response(
                {"detail": "This organization is closed.", "code": "organization_closed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        active = get_active_organization_service(organization)
        if not active:
            return Response(
                {"detail": "There is no active paid service to cancel.", "code": "no_active_service"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            service = request_cancel_paid_service(active, actor=request.user)
        except (CheckoutError, PayPalError) as exc:
            return _lifecycle_error_response(exc)

        period_end = service.current_period_end
        message = (
            "Your subscription has been canceled. Paid features remain available until "
            f"{period_end.date().isoformat()}."
            if period_end
            else "Your subscription has been canceled."
        )
        return Response(
            {
                "detail": message,
                "service": serialize_organization_service(service),
                "billing": get_current_service_summary(organization),
            }
        )


class OrganizationCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            organization = get_owner_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not the owner."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            organization = close_organization(
                organization,
                actor=request.user,
                confirmation_name=request.data.get("confirmation_name", ""),
            )
        except LifecycleError as exc:
            return _lifecycle_error_response(exc)

        lifecycle = serialize_lifecycle(organization)
        if organization.status == Organization.Status.CLOSURE_PENDING:
            when = organization.closure_effective_at
            detail = (
                "Your subscription has been canceled. Your organization will remain "
                f"active until {when.date().isoformat()} and will then be closed."
                if when
                else "Organization closure has been scheduled."
            )
        else:
            detail = "Organization closed."
        return Response({"detail": detail, "lifecycle": lifecycle})


class OrganizationCancelClosureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            organization = get_owner_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not the owner."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            organization = cancel_organization_closure(
                organization, actor=request.user
            )
        except LifecycleError as exc:
            return _lifecycle_error_response(exc)
        return Response(
            {
                "detail": "Scheduled organization closure has been canceled.",
                "lifecycle": serialize_lifecycle(organization),
            }
        )


class AdminOrganizationRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        if not request.user.is_staff:
            return Response(
                {"detail": "Only CommuniB administrators can restore organizations."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            organization = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            organization = restore_organization(organization, actor=request.user)
        except LifecycleError as exc:
            return _lifecycle_error_response(exc)
        return Response(
            {
                "detail": "Organization restored.",
                "lifecycle": serialize_lifecycle(organization),
            }
        )


class OrganizationClaimRequestView(APIView):
    """Record a claim/restoration request audit event (contact flow remains available)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            organization = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)
        if organization.status != Organization.Status.CLOSED:
            return Response(
                {"detail": "Claim requests apply to closed organizations.", "code": "not_closed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_audit(
            organization,
            actor=request.user,
            event_type=OrganizationAuditEvent.EventType.ORGANIZATION_CLAIM_REQUESTED,
            event_data={"message": (request.data.get("message") or "")[:2000]},
        )
        return Response(
            {
                "detail": (
                    "Your claim request was recorded. CommuniB staff will review it. "
                    "You can also use Contact with Claim Access for more detail."
                ),
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
            },
            status=status.HTTP_201_CREATED,
        )
