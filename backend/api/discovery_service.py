"""Map Search / member discovery helpers."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

STREAMERS_INTERNATIONAL_SLUG = "streamers-international"

# Org-level discovery schema unused — tags/location live on YouTube channels (Account).
STREAMERS_DISCOVERY_FIELDS = []

# Approximate US state centroids (fallback when ZIP geocode fails).
US_STATE_CENTROIDS = {
    "AL": (32.806671, -86.791130),
    "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221),
    "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564),
    "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371),
    "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783),
    "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337),
    "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137),
    "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526),
    "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067),
    "LA": (31.169546, -91.867805),
    "ME": (44.693947, -69.381927),
    "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106),
    "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192),
    "MS": (32.741646, -89.678696),
    "MO": (38.456085, -92.288368),
    "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082),
    "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896),
    "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482),
    "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419),
    "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915),
    "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938),
    "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.511780),
    "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828),
    "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461),
    "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686),
    "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494),
    "WV": (38.491226, -80.954453),
    "WI": (44.268543, -89.616508),
    "WY": (42.755966, -107.302490),
    "DC": (38.907192, -77.036873),
}

STATE_NAME_TO_ABBR = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}


def normalize_state(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if len(upper) == 2 and upper in US_STATE_CENTROIDS:
        return upper
    return STATE_NAME_TO_ABBR.get(text.lower(), text)


def discovery_values(membership) -> dict:
    shared = membership.shared_profile if isinstance(membership.shared_profile, dict) else {}
    disc = shared.get("discovery")
    if isinstance(disc, dict):
        return dict(disc)
    return {}


def set_discovery_values(membership, values: dict) -> None:
    shared = (
        dict(membership.shared_profile)
        if isinstance(membership.shared_profile, dict)
        else {}
    )
    shared["discovery"] = values
    membership.shared_profile = shared


def required_fields_complete(organization, values: dict) -> bool:
    for field in organization.discovery_fields or []:
        if not field.get("required"):
            continue
        key = field.get("key")
        val = values.get(key)
        if field.get("type") == "multi_select":
            if not isinstance(val, list) or not val:
                return False
        else:
            if val is None or str(val).strip() == "":
                return False
    return True


def geocode_location(*, state: str = "", zip_code: str = "") -> tuple[float | None, float | None]:
    zip_code = (zip_code or "").strip()
    state_abbr = normalize_state(state)

    if zip_code:
        coords = _nominatim_geocode(f"{zip_code}, USA")
        if coords:
            return coords

    if state_abbr and state_abbr in US_STATE_CENTROIDS:
        return US_STATE_CENTROIDS[state_abbr]

    if state:
        coords = _nominatim_geocode(f"{state}, USA")
        if coords:
            return coords

    return None, None


def _nominatim_geocode(query: str) -> tuple[float, float] | None:
    try:
        params = urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": 1, "countrycodes": "us"}
        )
        req = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={"User-Agent": "CommuniBetterMapSearch/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        logger.exception("Nominatim geocode failed for %s", query)
    return None


def user_has_verified_youtube(user) -> bool:
    from api.models import YouTubeChannelLink

    return YouTubeChannelLink.objects.filter(user=user).exists()


def normalize_channel_tags(raw) -> list[str]:
    if isinstance(raw, str):
        items = [t.strip() for t in raw.split(",") if t.strip()]
    elif isinstance(raw, list):
        items = [str(t).strip() for t in raw if str(t).strip()]
    else:
        items = []
    seen = set()
    out = []
    for tag in items:
        tag = tag[:40]
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
        if len(out) >= 20:
            break
    return out


def apply_channel_location(link, *, state: str = "", zip_code: str = "") -> None:
    raw_state = (state or "").strip()
    state_abbr = normalize_state(raw_state) if raw_state else ""
    if state_abbr and state_abbr not in US_STATE_CENTROIDS:
        state_abbr = raw_state
    link.state = state_abbr
    link.zip_code = (zip_code or "").strip()
    lat, lng = geocode_location(state=link.state, zip_code=link.zip_code)
    link.lat = lat
    link.lng = lng


def update_channel_profile(link, *, state=None, zip_code=None, tags=None):
    fields = []
    if state is not None or zip_code is not None:
        apply_channel_location(
            link,
            state=link.state if state is None else state,
            zip_code=link.zip_code if zip_code is None else zip_code,
        )
        fields.extend(["state", "zip_code", "lat", "lng"])
    if tags is not None:
        link.tags = normalize_channel_tags(tags)
        fields.append("tags")
    if fields:
        link.save(update_fields=list(dict.fromkeys(fields)))
    return link


def refresh_user_discovery_listings(user) -> None:
    from api.models import OrganizationMembership

    memberships = OrganizationMembership.objects.filter(
        user=user, organization__discovery_enabled=True
    ).select_related("organization")
    for membership in memberships:
        refresh_listing_eligibility(membership)


def refresh_listing_eligibility(membership) -> bool:
    """Listed when Map Search is on and the member has a located YouTube channel."""
    org = membership.organization
    if not org.discovery_enabled:
        membership.discovery_listed = False
        membership.discovery_lat = None
        membership.discovery_lng = None
        membership.save(
            update_fields=["discovery_listed", "discovery_lat", "discovery_lng"]
        )
        return False

    from api.models import YouTubeChannelLink

    first = (
        YouTubeChannelLink.objects.filter(
            user=membership.user, lat__isnull=False, lng__isnull=False
        )
        .order_by("-subscriber_count")
        .first()
    )
    listed = first is not None
    membership.discovery_lat = first.lat if first else None
    membership.discovery_lng = first.lng if first else None
    membership.discovery_listed = listed
    membership.save(
        update_fields=["discovery_listed", "discovery_lat", "discovery_lng"]
    )
    return listed


def serialize_youtube_channel(link) -> dict[str, Any]:
    tags = link.tags if isinstance(link.tags, list) else []
    return {
        "channel_id": link.channel_id,
        "title": link.title,
        "custom_url": link.custom_url,
        "thumbnail_url": link.thumbnail_url,
        "subscriber_count": link.subscriber_count,
        "video_count": link.video_count,
        "state": link.state or "",
        "zip_code": link.zip_code or "",
        "lat": link.lat,
        "lng": link.lng,
        "tags": tags,
        "located": link.lat is not None and link.lng is not None,
        "last_synced_at": link.last_synced_at.isoformat() if link.last_synced_at else None,
        "url": (
            f"https://www.youtube.com/{link.custom_url}"
            if link.custom_url
            else f"https://www.youtube.com/channel/{link.channel_id}"
        ),
    }


def serialize_discovery_member(membership, *, youtube_links=None) -> dict[str, Any]:
    from api.control_numbers import (
        ensure_user_control_number,
        format_user_control_number,
    )
    from api.models import UserProfile, YouTubeChannelLink

    user = membership.user
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None
    control = ensure_user_control_number(profile) if profile else None

    if youtube_links is None:
        youtube_links = list(
            YouTubeChannelLink.objects.filter(user=user).order_by("-subscriber_count")
        )

    channels = [serialize_youtube_channel(c) for c in youtube_links]
    total_subs = sum((c.subscriber_count or 0) for c in youtube_links)
    total_videos = sum((c.video_count or 0) for c in youtube_links)
    located = [c for c in youtube_links if c.lat is not None and c.lng is not None]
    primary = located[0] if located else None
    tags = (
        primary.tags
        if primary and isinstance(primary.tags, list)
        else []
    )

    return {
        "membership_id": membership.id,
        "user_id": user.id,
        "username": user.username,
        "communibetter_id": format_user_control_number(control),
        "display_name": (profile.display_name if profile else "") or user.username,
        "state": (primary.state if primary else "") or "",
        "zip_code": (primary.zip_code if primary else "") or "",
        "tags": tags,
        "topics": tags,
        "lat": primary.lat if primary else membership.discovery_lat,
        "lng": primary.lng if primary else membership.discovery_lng,
        "youtube_channels": channels,
        "subscriber_count": total_subs,
        "video_count": total_videos,
    }


def serialize_discovery_channel(membership, link) -> dict[str, Any]:
    base = serialize_discovery_member(membership, youtube_links=[link])
    ch = serialize_youtube_channel(link)
    tags = link.tags if isinstance(link.tags, list) else []
    base.update(
        {
            "channel_id": link.channel_id,
            "channel_title": link.title,
            "state": link.state or "",
            "zip_code": link.zip_code or "",
            "lat": link.lat,
            "lng": link.lng,
            "tags": tags,
            "topics": tags,
            "subscriber_count": link.subscriber_count,
            "video_count": link.video_count,
            "youtube_channels": [ch],
        }
    )
    return base


def search_listed_members(organization, *, params: dict):
    """One result per located channel; filter by state/ZIP/tags."""
    from api.models import OrganizationMembership, YouTubeChannelLink

    qs = (
        OrganizationMembership.objects.filter(
            organization=organization,
            discovery_listed=True,
        )
        .select_related("user", "user__profile")
        .order_by("user__username")
    )

    state = normalize_state(params.get("state") or "")
    zip_code = (params.get("zip_code") or "").strip()
    if state and state not in US_STATE_CENTROIDS:
        state = ""

    tags_raw = params.get("tags") or params.get("topics") or ""
    if isinstance(tags_raw, str):
        want_tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]
    else:
        want_tags = [str(t).strip().lower() for t in (tags_raw or []) if str(t).strip()]

    bbox = params.get("bbox")
    west = south = east = north = None
    if bbox:
        try:
            west, south, east, north = [float(x) for x in str(bbox).split(",")]
        except (TypeError, ValueError):
            west = south = east = north = None

    members = list(qs[:500])
    user_ids = [m.user_id for m in members]
    links_by_user: dict[int, list] = {uid: [] for uid in user_ids}
    for link in YouTubeChannelLink.objects.filter(
        user_id__in=user_ids, lat__isnull=False, lng__isnull=False
    ):
        links_by_user.setdefault(link.user_id, []).append(link)

    results = []
    for m in members:
        for link in links_by_user.get(m.user_id, []):
            if state and normalize_state(link.state or "") != state:
                continue
            if zip_code and (link.zip_code or "").strip() != zip_code:
                continue
            if want_tags:
                channel_tags = {
                    str(t).strip().lower()
                    for t in (link.tags or [])
                    if str(t).strip()
                }
                if not set(want_tags).issubset(channel_tags):
                    continue
            if west is not None:
                if not (
                    south <= (link.lat or 0) <= north
                    and west <= (link.lng or 0) <= east
                ):
                    continue
            results.append(serialize_discovery_channel(m, link))
    return results


def ensure_streamers_international():
    from api.models import Organization

    org, created = Organization.objects.get_or_create(
        slug=STREAMERS_INTERNATIONAL_SLUG,
        defaults={
            "name": "Streamers International",
            "description": (
                "A global community for streamers to find each other by topic and location."
            ),
            "geographic_scope": Organization.GeographicScope.INTERNATIONAL,
            "discovery_enabled": True,
            "discovery_fields": STREAMERS_DISCOVERY_FIELDS,
            "is_verified": True,
        },
    )
    changed = []
    if not org.discovery_enabled:
        org.discovery_enabled = True
        changed.append("discovery_enabled")
    if org.discovery_fields != STREAMERS_DISCOVERY_FIELDS:
        org.discovery_fields = STREAMERS_DISCOVERY_FIELDS
        changed.append("discovery_fields")
    if org.geographic_scope != Organization.GeographicScope.INTERNATIONAL:
        org.geographic_scope = Organization.GeographicScope.INTERNATIONAL
        changed.append("geographic_scope")
    if changed:
        org.save(update_fields=changed)
    return org, created
