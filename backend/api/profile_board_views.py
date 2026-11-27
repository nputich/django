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
    OrganizationMembership,
    PersonalBoardPost,
    UserProfile,
)
from api.org_access import get_admin_organization
from api.profile_fields import (
    get_visibility_map,
    normalize_visibility,
    personal_field_value,
    sync_display_name,
)
from api.serializers import (
    BoardPostCreateSerializer,
    BoardPostReplyCreateSerializer,
    BoardPostReplySerializer,
    BoardPostSerializer,
    BoardPollVoteSerializer,
    OrganizationBoardSettingsSerializer,
    OrganizationBoardPublicSerializer,
    OrganizationMemberProfileSerializer,
    OrganizationWallIdentitySerializer,
    organization_wall_identity,
    PersonalBoardPostSerializer,
    PersonalBoardSettingsSerializer,
    UserProfileUpdateSerializer,
    build_me_payload,
    serialize_post_author,
)
from api.usage_service import CapacityDenied, capacity_denied_response
from api.wall_service import (
    create_org_wall_post,
    create_personal_wall_post,
    vote_org_poll,
    vote_personal_poll,
)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_me_payload(request.user, request))


class PublicUserProfileView(APIView):
    """Public account card — fields filtered by visibility + membership prefs."""

    permission_classes = [AllowAny]

    def get(self, request, username):
        from api.profile_fields import build_public_profile_payload

        user = get_object_or_404(User, username__iexact=username)
        # If the profile owner banned the viewer, hide the account.
        if getattr(request.user, "is_authenticated", False):
            from api.inbox_service import get_personal_mailbox, is_blocked

            owner_box = get_personal_mailbox(user)
            viewer_box = get_personal_mailbox(request.user)
            if is_blocked(blocker=owner_box, blocked=viewer_box):
                return Response(
                    {"detail": "Account not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(build_public_profile_payload(user, request))


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
            "first_name",
            "last_name",
            "city",
            "state",
            "zip_code",
            "phone",
            "contact_email",
        ]
        for field in profile_fields:
            if field in data:
                setattr(profile, field, data[field])

        vis_raw = data.get("field_visibility", request.data.get("field_visibility"))
        if isinstance(vis_raw, str):
            import json

            try:
                vis_raw = json.loads(vis_raw)
            except json.JSONDecodeError:
                vis_raw = None
        if isinstance(vis_raw, dict):
            merged = get_visibility_map(profile.field_visibility)
            for key, value in vis_raw.items():
                merged[str(key)] = normalize_visibility(value, field_key=str(key))
            merged["username"] = normalize_visibility(None, field_key="username")
            profile.field_visibility = merged

        if "profile_picture" in request.FILES:
            profile.profile_picture = request.FILES["profile_picture"]
        else:
            clear_val = data.get("clear_profile_picture", request.data.get("clear_profile_picture"))
            if str(clear_val).lower() in ("true", "1", "yes"):
                if profile.profile_picture:
                    profile.profile_picture.delete(save=False)
                profile.profile_picture = None

        if "first_name" in data or "last_name" in data or not (profile.display_name or "").strip():
            sync_display_name(profile)

        if "show_memberships_on_profile" in data:
            profile.show_memberships_on_profile = bool(
                data["show_memberships_on_profile"]
            )
        else:
            raw_show = request.data.get("show_memberships_on_profile")
            if raw_show is not None:
                profile.show_memberships_on_profile = str(raw_show).lower() in (
                    "true",
                    "1",
                    "yes",
                )

        profile.save()
        return Response(build_me_payload(user, request))


class PersonalBoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        board = get_personal_board(request.user)
        posts = board.posts.prefetch_related("poll_options", "poll_votes").all()
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
        post = create_personal_wall_post(board=board, data=serializer.validated_data)
        post = (
            PersonalBoardPost.objects.prefetch_related("poll_options", "poll_votes")
            .get(pk=post.pk)
        )
        return Response(
            PersonalBoardPostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PersonalBoardSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        board = get_personal_board(request.user)
        serializer = PersonalBoardSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "title" in data:
            data["title"] = (data["title"] or "").strip()
        for field, value in data.items():
            setattr(board, field, value)
        board.save()
        return Response({"id": board.id, "title": board.title})


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
            board.posts.select_related("author__profile", "meeting__organization")
            .prefetch_related(
                "replies__author__profile",
                "poll_options",
                "poll_votes",
                "meeting__summaries",
                "meeting__expected_attendances",
            )
            .all()
        )
        return Response(
            {
                "organization_id": organization.id,
                "organization_name": organization.name,
                "organization_slug": organization.slug,
                "wall_identity": organization_wall_identity(organization, request),
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
        try:
            post = create_org_wall_post(
                board=board, author=request.user, data=serializer.validated_data
            )
        except CapacityDenied as exc:
            return capacity_denied_response(exc)
        post = (
            BoardPost.objects.select_related("author__profile")
            .prefetch_related("replies", "poll_options", "poll_votes")
            .get(pk=post.pk)
        )
        return Response(
            BoardPostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationBoardSettingsView(APIView):
    """Admin: read/update wall visibility and posting mode."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        board = get_org_board(organization)
        return Response(
            {
                "organization_id": organization.id,
                "organization_name": organization.name,
                "organization_slug": organization.slug,
                "board": OrganizationBoardPublicSerializer(board).data,
            }
        )

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
        data = serializer.validated_data
        if "title" in data:
            data["title"] = (data["title"] or "").strip()
        for field, value in data.items():
            setattr(board, field, value)
        board.save()
        return Response(
            {
                "organization_id": organization.id,
                "organization_name": organization.name,
                "organization_slug": organization.slug,
                "board": OrganizationBoardPublicSerializer(board).data,
            }
        )


class OrganizationWallIdentityView(APIView):
    """Admin: set organization account / wall profile fields."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    TEXT_FIELDS = (
        "public_username",
        "first_name",
        "last_name",
        "city",
        "state",
        "zip_code",
        "phone",
        "contact_email",
    )

    def get(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(organization_wall_identity(organization, request))

    def patch(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OrganizationWallIdentitySerializer(
            data=request.data,
            partial=True,
            context={"organization": organization},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in self.TEXT_FIELDS:
            if field in data:
                setattr(organization, field, data[field])
        vis_raw = request.data.get("field_visibility")
        if isinstance(vis_raw, str):
            import json

            try:
                vis_raw = json.loads(vis_raw)
            except json.JSONDecodeError:
                vis_raw = None
        if isinstance(vis_raw, dict):
            merged = get_visibility_map(organization.field_visibility)
            for key, value in vis_raw.items():
                merged[str(key)] = normalize_visibility(value, field_key=str(key))
            organization.field_visibility = merged
        if "profile_picture" in request.FILES:
            organization.profile_picture = request.FILES["profile_picture"]
        elif data.get("clear_profile_picture"):
            if organization.profile_picture:
                organization.profile_picture.delete(save=False)
            organization.profile_picture = None
        organization.save()
        return Response(organization_wall_identity(organization, request))


class OrganizationMemberProfileView(APIView):
    """Member: values shared with one organization (Account settings)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    TEXT_FIELDS = (
        "username",
        "first_name",
        "last_name",
        "city",
        "state",
        "zip_code",
        "phone",
        "contact_email",
    )

    def patch(self, request, slug):
        membership = (
            OrganizationMembership.objects.filter(
                user=request.user,
                organization__slug=slug,
            )
            .exclude(organization__status=Organization.Status.CLOSED)
            .select_related("organization")
            .first()
        )
        if membership is None:
            return Response(
                {"detail": "Organization not found or you are not a member."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OrganizationMemberProfileSerializer(
            data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shared = (
            dict(membership.shared_profile)
            if isinstance(membership.shared_profile, dict)
            else {}
        )

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        use_personal = data.get("use_personal") or []
        # FormData may send a single string instead of a list.
        if isinstance(use_personal, str):
            use_personal = [use_personal]
        for key in use_personal:
            personal_val = personal_field_value(profile, key, request)
            if key == "profile_picture":
                if personal_val:
                    shared[key] = personal_val
            elif personal_val is not None:
                shared[key] = personal_val

        for field in self.TEXT_FIELDS:
            if field in data:
                shared[field] = data[field]

        username_val = (shared.get("username") or "").strip()
        if not username_val:
            username_val = (request.user.username or "").strip()
            shared["username"] = username_val
        if not username_val:
            return Response(
                {"username": ["Username is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        shared["username"] = username_val

        if "profile_picture" in request.FILES:
            # Store uploaded member pic under org-scoped path via temp URL string —
            # reuse personal upload path pattern on membership JSON as absolute URL.
            from django.core.files.storage import default_storage
            from django.utils.text import get_valid_filename
            import uuid

            upload = request.FILES["profile_picture"]
            path = default_storage.save(
                f"org_member_profiles/{membership.organization_id}/{uuid.uuid4().hex}_{get_valid_filename(upload.name)}",
                upload,
            )
            url = default_storage.url(path)
            shared["profile_picture"] = (
                request.build_absolute_uri(url) if request else url
            )
        elif data.get("clear_profile_picture"):
            shared["profile_picture"] = ""
        elif "profile_picture" in data and data["profile_picture"] is not None:
            shared["profile_picture"] = data["profile_picture"]

        vis_raw = request.data.get("field_visibility")
        if isinstance(vis_raw, str):
            import json

            try:
                vis_raw = json.loads(vis_raw)
            except json.JSONDecodeError:
                vis_raw = None
        if isinstance(vis_raw, dict):
            merged = get_visibility_map(membership.field_visibility)
            for key, value in vis_raw.items():
                merged[str(key)] = normalize_visibility(value, field_key=str(key))
            merged["username"] = normalize_visibility(None, field_key="username")
            membership.field_visibility = merged

        if "show_membership_on_profile" in data:
            membership.show_on_profile = bool(data["show_membership_on_profile"])
        else:
            raw_show = request.data.get("show_membership_on_profile")
            if raw_show is not None:
                membership.show_on_profile = str(raw_show).lower() in (
                    "true",
                    "1",
                    "yes",
                )

        membership.shared_profile = shared
        membership.save()
        from api.serializers import organization_account_field_sections

        sections = organization_account_field_sections(request.user, request)
        section = next(
            (s for s in sections if s["organization_slug"] == slug),
            None,
        )
        return Response(section or {"detail": "Saved."})


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


class OrganizationBoardPollVoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        organization = get_object_or_404(Organization, slug=slug, is_active=True)
        board = get_org_board(organization)
        if not can_view_org_board(board, request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        post = get_object_or_404(BoardPost, pk=pk, board=board)
        serializer = BoardPollVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote_org_poll(
            post=post,
            user=request.user,
            option_id=serializer.validated_data["option_id"],
        )
        post = (
            BoardPost.objects.select_related("author__profile")
            .prefetch_related("replies__author__profile", "poll_options", "poll_votes")
            .get(pk=post.pk)
        )
        return Response(BoardPostSerializer(post, context={"request": request}).data)


class PersonalBoardPollVoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(
            PersonalBoardPost.objects.select_related("board"),
            pk=pk,
            board__user=request.user,
        )
        serializer = BoardPollVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote_personal_poll(
            post=post,
            user=request.user,
            option_id=serializer.validated_data["option_id"],
        )
        post = PersonalBoardPost.objects.prefetch_related(
            "poll_options", "poll_votes"
        ).get(pk=post.pk)
        return Response(
            PersonalBoardPostSerializer(post, context={"request": request}).data
        )
