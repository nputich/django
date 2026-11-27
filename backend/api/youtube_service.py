"""YouTube Data API + Google OAuth for channel verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from django.conf import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

SCOPES = "https://www.googleapis.com/auth/youtube.readonly"


def youtube_oauth_configured() -> bool:
    return bool(
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        and getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    )


def _state_secret() -> bytes:
    return (
        getattr(settings, "GOOGLE_OAUTH_STATE_SECRET", "") or settings.SECRET_KEY
    ).encode("utf-8")


def make_oauth_state(*, user_id: int, return_to: str = "account", slug: str = "") -> str:
    payload = json.dumps(
        {
            "uid": user_id,
            "return_to": return_to or "account",
            "slug": slug or "",
            "ts": int(time.time()),
        },
        separators=(",", ":"),
    )
    sig = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return urllib.parse.quote(f"{payload}.{sig}", safe="")


def parse_oauth_state(state: str, *, max_age_seconds: int = 600) -> dict | None:
    try:
        raw = urllib.parse.unquote(state or "")
        payload, sig = raw.rsplit(".", 1)
        expected = hmac.new(
            _state_secret(), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        data = json.loads(payload)
        if int(time.time()) - int(data.get("ts") or 0) > max_age_seconds:
            return None
        return data
    except Exception:
        return None


def build_oauth_authorize_url(*, state: str, redirect_uri: str) -> str:
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(*, code: str, redirect_uri: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def refresh_access_token(refresh_token: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_mine_channels(access_token: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "part": "snippet,statistics",
            "mine": "true",
            "maxResults": 50,
        }
    )
    req = urllib.request.Request(
        f"{YOUTUBE_CHANNELS_URL}?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("items") or []


def upsert_channels_for_user(user, *, access_token: str, refresh_token: str = "") -> list:
    from api.models import YouTubeChannelLink

    items = fetch_mine_channels(access_token)
    now = datetime.now(timezone.utc)
    links = []
    for item in items:
        channel_id = item.get("id") or ""
        if not channel_id:
            continue
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        thumbs = snippet.get("thumbnails") or {}
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url") or ""
        subs = stats.get("subscriberCount")
        videos = stats.get("videoCount")
        try:
            subs_n = int(subs) if subs is not None else None
        except (TypeError, ValueError):
            subs_n = None
        try:
            videos_n = int(videos) if videos is not None else None
        except (TypeError, ValueError):
            videos_n = None

        existing_token = (
            YouTubeChannelLink.objects.filter(user=user, channel_id=channel_id)
            .values_list("refresh_token", flat=True)
            .first()
            or ""
        )
        link, _ = YouTubeChannelLink.objects.update_or_create(
            user=user,
            channel_id=channel_id,
            defaults={
                "title": (snippet.get("title") or "")[:255],
                "custom_url": (snippet.get("customUrl") or "")[:255],
                "thumbnail_url": thumb,
                "subscriber_count": subs_n,
                "video_count": videos_n,
                "last_synced_at": now,
                "refresh_token": refresh_token or existing_token,
            },
        )
        links.append(link)
    return links


def sync_user_channels(user) -> list:
    from api.models import YouTubeChannelLink

    if not youtube_oauth_configured():
        return list(YouTubeChannelLink.objects.filter(user=user))

    links = list(YouTubeChannelLink.objects.filter(user=user))
    tokens = {l.refresh_token for l in links if l.refresh_token}
    if not tokens:
        return links

    refreshed = []
    for token in tokens:
        try:
            tok = refresh_access_token(token)
            access = tok.get("access_token")
            if not access:
                continue
            refreshed.extend(
                upsert_channels_for_user(user, access_token=access, refresh_token=token)
            )
        except Exception:
            logger.exception("YouTube sync failed for user %s", user.pk)
    return refreshed or links


# Manual refresh abuse limits (user-initiated only).
REFRESH_MIN_INTERVAL_SECONDS = 60 * 60  # 1 hour between live Google calls
REFRESH_MAX_PER_DAY = 6


def youtube_refresh_guard(user) -> tuple[bool, dict]:
    """Return (allowed, meta). Does not call Google.

    On allow, caller must invoke ``record_youtube_refresh`` after a successful sync.
    """
    from datetime import datetime, timedelta, timezone

    from api.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=user)
    extra = dict(profile.extra_data) if isinstance(profile.extra_data, dict) else {}
    guard = dict(extra.get("youtube_refresh_guard") or {})
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    day = guard.get("day") or ""
    count = int(guard.get("count") or 0) if day == today else 0
    last_raw = guard.get("last_refresh_at")
    last_at = None
    if last_raw:
        try:
            last_at = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
        except ValueError:
            last_at = None

    if last_at is not None:
        elapsed = (now - last_at).total_seconds()
        if elapsed < REFRESH_MIN_INTERVAL_SECONDS:
            retry_after = int(REFRESH_MIN_INTERVAL_SECONDS - elapsed)
            return False, {
                "reason": "cooldown",
                "detail": (
                    f"You can refresh YouTube stats once per hour. "
                    f"Try again in about {max(1, retry_after // 60)} minute(s)."
                ),
                "retry_after_seconds": retry_after,
                "refreshes_remaining_today": max(0, REFRESH_MAX_PER_DAY - count),
            }

    if count >= REFRESH_MAX_PER_DAY:
        tomorrow = datetime(
            now.year, now.month, now.day, tzinfo=timezone.utc
        ) + timedelta(days=1)
        retry_after = int((tomorrow - now).total_seconds())
        return False, {
            "reason": "daily_cap",
            "detail": (
                f"YouTube refresh is limited to {REFRESH_MAX_PER_DAY} times per day. "
                "Try again tomorrow."
            ),
            "retry_after_seconds": retry_after,
            "refreshes_remaining_today": 0,
        }

    return True, {
        "refreshes_remaining_today": max(0, REFRESH_MAX_PER_DAY - count),
        "retry_after_seconds": 0,
    }


def record_youtube_refresh(user) -> None:
    """Record a successful live refresh against the per-user guard."""
    from datetime import datetime, timezone

    from api.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=user)
    extra = dict(profile.extra_data) if isinstance(profile.extra_data, dict) else {}
    guard = dict(extra.get("youtube_refresh_guard") or {})
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    count = int(guard.get("count") or 0) if guard.get("day") == today else 0
    extra["youtube_refresh_guard"] = {
        "day": today,
        "count": count + 1,
        "last_refresh_at": now.isoformat(),
    }
    profile.extra_data = extra
    profile.save(update_fields=["extra_data", "updated_at"])
