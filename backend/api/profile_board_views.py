"""User profile and posting board API views."""

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.board_service import (
    can_delete_org_post,
    can_delete_org_reply,
    can_delete_personal_post,
    can_post_org_board,
    can_reply_org_board,
    can_view_org_board,
    get_org_board,
    get_personal_board,
    is_org_admin,
    is_org_member,
)
from api.models import (
    BoardPost,
    BoardPostReply,
    Organization,
    OrganizationBoard,
    PersonalBoardPost,
    UserProfile,
)
from api.org_access import get_admin_organization
from api.serializers import (
    BoardPostCreateSerializer,
    BoardPostReplyCreateSerializer,
    BoardPostReplySerializer,
    BoardPostSerializer,
    OrganizationBoardSettingsSerializer,
    OrganizationBoardPublicSerializer,
    PersonalBoardPostSerializer,
    UserProfileUpdateSerializer,
    build_me_payload,
)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_me_payload(request.user, request))


class MeProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileUpdateSerializer(
            data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        if "username" in data:
            new_username = data["username"].strip()
            if User.objects.exclude(pk=user.pk).filter(username=new_username).exists():
                return Response(
                    {"detail": "This username is already taken."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.username = new_username
            user.save(update_fields=["username"])

        profile_fields = [
            "display_name",
            "city",
            "state",
            "phone",
            "contact_email",
        ]
        for field in profile_fields:
            if field in data:
                setattr(profile, field, data[field])

        if "profile_picture" in request.FILES:
            profile.profile_picture = request.FILES["profile_picture"]
        else:
            clear_val = data.get("clear_profile_picture", request.data.get("clear_profile_picture"))
            if str(clear_val).lower() in ("true", "1", "yes"):
                if profile.profile_picture:
                    profile.profile_picture.delete(save=False)
                profile.profile_picture = None

        profile.save()
        return Response(build_me_payload(user, request))


class PersonalBoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        board = get_personal_board(request.user)
        posts = board.posts.select_related("board__user__profile").all()
        return Response(
            {
                "board_id": board.id,
                "title": board.title,
                "posting_mode": "restricted",
                "can_view": True,
                "can_post": True,
                "posts": PersonalBoardPostSerializer(
                    posts, many=True, context={"request": request}
                ).data,
            }
        )

    def post(self, request):
        board = get_personal_board(request.user)
        serializer = BoardPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = PersonalBoardPost.objects.create(
            board=board,
            title=serializer.validated_data["title"],
            body=serializer.validated_data["body"],
        )
        return Response(
            PersonalBoardPostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PersonalBoardPostDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        post = get_object_or_404(
            PersonalBoardPost.objects.select_related("board"),
            pk=pk,
            board__user=request.user,
        )
        if not can_delete_personal_post(post, request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationBoardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        board = get_org_board(organization)
        user = request.user if request.user.is_authenticated else None

        if not can_view_org_board(board, user):
            return Response(
                {"detail": "This board is for organization members only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        posts = (
            board.posts.select_related("author__profile")
            .prefetch_related("replies__author__profile")
            .all()
        )
        return Response(
            {
                "organization_id": organization.id,
                "organization_name": organization.name,
                "organization_slug": organization.slug,
                "board": OrganizationBoardPublicSerializer(board).data,
                "can_view": True,
                "can_post": can_post_org_board(board, user),
                "can_reply": can_reply_org_board(board, user),
                "is_member": is_org_member(organization, user),
                "is_admin": is_org_admin(organization, user),
                "posts": BoardPostSerializer(
                    posts, many=True, context={"request": request}
                ).data,
            }
        )

    def post(self, request, slug):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to post."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        board = get_org_board(organization)
        if not can_post_org_board(board, request.user):
            return Response(
                {"detail": "You do not have permission to post on this board."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BoardPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = BoardPost.objects.create(
            board=board,
            author=request.user,
            title=serializer.validated_data["title"],
            body=serializer.validated_data["body"],
        )
        return Response(
            BoardPostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationBoardSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        board = get_org_board(organization)
        serializer = OrganizationBoardSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(board, field, value)
        board.save()
        return Response(OrganizationBoardPublicSerializer(board).data)


class OrganizationBoardPostDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug, pk):
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        board = get_org_board(organization)
        post = get_object_or_404(BoardPost, pk=pk, board=board)
        if not can_delete_org_post(post, request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationBoardReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        board = get_org_board(organization)
        post = get_object_or_404(BoardPost, pk=pk, board=board)
        if not can_reply_org_board(board, request.user):
            return Response(
                {"detail": "You do not have permission to reply on this board."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BoardPostReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = BoardPostReply.objects.create(
            post=post,
            author=request.user,
            body=serializer.validated_data["body"],
        )
        return Response(
            BoardPostReplySerializer(reply, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationBoardReplyDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug, pk, reply_pk):
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        board = get_org_board(organization)
        post = get_object_or_404(BoardPost, pk=pk, board=board)
        reply = get_object_or_404(BoardPostReply, pk=reply_pk, post=post)
        if not can_delete_org_reply(reply, request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        reply.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
