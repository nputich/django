"""Access rules for organization and personal posting boards."""

from __future__ import annotations

from django.contrib.auth.models import User

from api.models import (
    BoardPost,
    BoardPostReply,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    PersonalBoard,
    PersonalBoardPost,
)


def get_org_board(organization: Organization) -> OrganizationBoard:
    board, _ = OrganizationBoard.objects.get_or_create(organization=organization)
    return board


def get_personal_board(user: User) -> PersonalBoard:
    board, _ = PersonalBoard.objects.get_or_create(user=user)
    return board


def is_org_member(organization: Organization, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    return OrganizationMembership.objects.filter(
        organization=organization, user=user
    ).exists()


def is_org_admin(organization: Organization, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    return OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.ADMIN,
    ).exists()


def can_view_org_board(board: OrganizationBoard, user: User | None) -> bool:
    if board.posting_mode in (
        OrganizationBoard.PostingMode.PUBLIC,
        OrganizationBoard.PostingMode.RESTRICTED,
    ):
        return True
    return is_org_member(board.organization, user)


def can_post_org_board(board: OrganizationBoard, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if board.posting_mode == OrganizationBoard.PostingMode.RESTRICTED:
        return is_org_admin(board.organization, user)
    if board.posting_mode == OrganizationBoard.PostingMode.MEMBERS_ONLY:
        return is_org_member(board.organization, user)
    return True


def can_reply_org_board(board: OrganizationBoard, user: User | None) -> bool:
    return bool(user and user.is_authenticated and can_view_org_board(board, user))


def can_delete_org_post(post: BoardPost, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if post.author_id == user.id:
        return True
    return is_org_admin(post.board.organization, user)


def can_delete_org_reply(reply: BoardPostReply, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if reply.author_id == user.id:
        return True
    return is_org_admin(reply.post.board.organization, user)


def can_delete_personal_post(post: PersonalBoardPost, user: User | None) -> bool:
    return bool(user and user.is_authenticated and post.board.user_id == user.id)
