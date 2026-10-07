"""Map Search APIs + account-level YouTube channel management."""

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.board_service import is_org_member
from api.discovery_service import (
    refresh_listing_eligibility,
    refresh_user_discovery_listings,
    search_listed_members,
    serialize_discovery_member,
    serialize_youtube_channel,
    update_channel_profile,
    user_has_verified_youtube,
)
from api.models import Organization, OrganizationMembership, YouTubeChannelLink
from api.youtube_service import (
    build_oauth_authorize_url,
    exchange_code_for_tokens,
    make_oauth_state,
    parse_oauth_state,
    record_youtube_refresh,
    sync_user_channels,
    upsert_channels_for_user,
    youtube_oauth_configured,
    youtube_refresh_guard,
)


def _get_org(slug: str) -> Organization:
    return get_object_or_404(Organization, slug=slug)


def _require_member(org: Organization, user) -> OrganizationMembership | None:
    return (
        OrganizationMembership.objects.filter(organization=org, user=user)
        .select_related("user", "user__profile")
        .first()
    )


def _frontend_base() -> str:
    return getattr(settings, "FRONTEND_BASE_URL", "http://localhost:10001").rstrip("/")


def _oauth_redirect_uri(request) -> str:
    return (
        getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or ""
    ).strip() or request.build_absolute_uri("/api/youtube/oauth/callback/")


class OrganizationDiscoveryMetaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org = _get_org(slug)
        membership = _require_member(org, request.user)
        return Response(
            {
                "discovery_enabled": bool(org.discovery_enabled),
                "fields": org.discovery_fields or [],
                "is_member": membership is not None,
            }
        )


class OrganizationDiscoveryMeView(APIView):
    """Membership status for Map Search (setup lives on Account settings)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org = _get_org(slug)
        if not org.discovery_enabled:
            return Response(
                {"detail": "Map Search is not enabled for this organization."},
                status=status.HTTP_404_NOT_FOUND,
            )
        membership = _require_member(org, request.user)
        if membership is None:
            return Response(
                {
                    "detail": "Join this organization to use Map Search.",
                    "is_member": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh_listing_eligibility(membership)
        membership.refresh_from_db()
        channels = list(YouTubeChannelLink.objects.filter(user=request.user))
        return Response(
            {
                "is_member": True,
                "listed": membership.discovery_listed,
                "youtube_verified": user_has_verified_youtube(request.user),
                "has_located_channel": any(
                    c.lat is not None and c.lng is not None for c in channels
                ),
                "card": serialize_discovery_member(
                    membership, youtube_links=channels
                ),
            }
        )


class OrganizationDiscoverySearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org = _get_org(slug)
        if not org.discovery_enabled:
            return Response(
                {"detail": "Map Search is not enabled for this organization."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not is_org_member(org, request.user):
            return Response(
                {
                    "detail": "Join this organization to use Map Search.",
                    "is_member": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        results = search_listed_members(org, params=request.query_params)
        return Response({"results": results, "count": len(results)})


# --- Account-level YouTube (CommuniBetter user account) ---


class MeYouTubeView(APIView):
    """List connected channels + OAuth status for Account settings."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        channels = list(
            YouTubeChannelLink.objects.filter(user=request.user).order_by(
                "-subscriber_count", "title"
            )
        )
        return Response(
            {
                "youtube_oauth_configured": youtube_oauth_configured(),
                "channels": [serialize_youtube_channel(c) for c in channels],
            }
        )


class MeYouTubeOAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not youtube_oauth_configured():
            return Response(
                {
                    "detail": (
                        "YouTube verification is not configured "
                        "(GOOGLE_OAUTH_CLIENT_ID / SECRET)."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        state = make_oauth_state(user_id=request.user.id, return_to="account")
        url = build_oauth_authorize_url(
            state=state, redirect_uri=_oauth_redirect_uri(request)
        )
        return Response({"authorize_url": url})


class MeYouTubeRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_has_verified_youtube(request.user):
            return Response(
                {"detail": "Connect YouTube first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        links = list(YouTubeChannelLink.objects.filter(user=request.user))
        allowed, guard_meta = youtube_refresh_guard(request.user)
        if not allowed:
            return Response(
                {
                    "refreshed": False,
                    "cached": True,
                    "detail": guard_meta.get("detail"),
                    "retry_after_seconds": guard_meta.get("retry_after_seconds", 0),
                    "refreshes_remaining_today": guard_meta.get(
                        "refreshes_remaining_today", 0
                    ),
                    "channels": [serialize_youtube_channel(c) for c in links],
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if not youtube_oauth_configured():
            return Response(
                {
                    "detail": "YouTube OAuth is not configured; cannot refresh live stats.",
                    "refreshed": False,
                    "cached": True,
                    "channels": [serialize_youtube_channel(c) for c in links],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        refreshed = sync_user_channels(request.user)
        record_youtube_refresh(request.user)
        refresh_user_discovery_listings(request.user)
        _, after_meta = youtube_refresh_guard(request.user)
        return Response(
            {
                "refreshed": True,
                "cached": False,
                "refreshes_remaining_today": after_meta.get(
                    "refreshes_remaining_today", 0
                ),
                "channels": [serialize_youtube_channel(c) for c in refreshed],
            }
        )


class MeYouTubeChannelUpdateView(APIView):
    """Update state, ZIP, and tags for one connected channel."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, channel_id):
        link = YouTubeChannelLink.objects.filter(
            user=request.user, channel_id=channel_id
        ).first()
        if link is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        kwargs = {}
        if "state" in request.data:
            kwargs["state"] = request.data.get("state")
        if "zip_code" in request.data:
            kwargs["zip_code"] = request.data.get("zip_code")
        if "tags" in request.data:
            kwargs["tags"] = request.data.get("tags")
        if not kwargs:
            return Response(
                {"detail": "Provide state, zip_code, and/or tags."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_channel_profile(link, **kwargs)
        link.refresh_from_db()
        refresh_user_discovery_listings(request.user)
        return Response(serialize_youtube_channel(link))


class MeYouTubeDevStubView(APIView):
    """Local-only stub channel for Account settings without Google OAuth."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if (getattr(settings, "APP_ENV", "local") or "local").lower() not in (
            "local",
            "dev",
            "development",
        ):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if youtube_oauth_configured():
            return Response(
                {"detail": "Use Google OAuth to verify YouTube in this environment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        channel_id = (request.data.get("channel_id") or "UC_LOCAL_STUB").strip()
        title = (request.data.get("title") or "Local test channel").strip()
        try:
            subs = int(request.data.get("subscriber_count") or 0)
        except (TypeError, ValueError):
            subs = 0
        link, _ = YouTubeChannelLink.objects.update_or_create(
            user=request.user,
            channel_id=channel_id[:64],
            defaults={
                "title": title[:255],
                "subscriber_count": subs,
                "custom_url": "",
                "thumbnail_url": "",
            },
        )
        refresh_user_discovery_listings(request.user)
        return Response(serialize_youtube_channel(link))


class YouTubeOAuthCallbackView(APIView):
    """Browser redirect target after Google consent — returns to Account settings."""

    permission_classes = []
    authentication_classes = []

    def get(self, request):
        from django.contrib.auth import get_user_model
        from django.shortcuts import redirect

        error = request.query_params.get("error")
        parsed = parse_oauth_state(request.query_params.get("state") or "")
        frontend_base = _frontend_base()
        fail_url = f"{frontend_base}/account?youtube=error"

        if error or not parsed:
            return redirect(fail_url)

        code = request.query_params.get("code")
        if not code:
            return redirect(fail_url)

        try:
            tokens = exchange_code_for_tokens(
                code=code, redirect_uri=_oauth_redirect_uri(request)
            )
            access = tokens.get("access_token")
            refresh = tokens.get("refresh_token") or ""
            User = get_user_model()
            user = User.objects.get(pk=parsed["uid"])
            upsert_channels_for_user(
                user, access_token=access, refresh_token=refresh
            )
            refresh_user_discovery_listings(user)
        except Exception:
            return redirect(fail_url)

        return redirect(f"{frontend_base}/account?youtube=connected")
