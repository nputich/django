"""Personal and org-shared profile field definitions + visibility."""

from __future__ import annotations

# Visibility: who can see a field value on profiles / sharing.
PUBLIC = "public"
ORG_ADMINS = "org_admins"  # shared with admins of orgs the user joins
PRIVATE = "private"

FIELD_VISIBILITY_ORDER = (PUBLIC, ORG_ADMINS, PRIVATE)

FIELD_VISIBILITY_META = {
    PUBLIC: {
        "label": "Public",
        "short": "Public",
        "description": "Shown on your public profile to everyone.",
    },
    ORG_ADMINS: {
        "label": "Share with org admins",
        "short": "Org admins",
        "description": "Visible to admins of organizations you join; not on your public profile.",
    },
    PRIVATE: {
        "label": "Private",
        "short": "Private",
        "description": "Only you can see this field.",
    },
}

DEFAULT_FIELD_VISIBILITY = PRIVATE
# Username must stay findable; always public (no toggle).
DEFAULT_VISIBILITY_BY_KEY = {
    "username": PUBLIC,
}

# Legacy values from earlier builds.
_LEGACY_VISIBILITY = {
    "hidden_all": PRIVATE,
    "hidden_to_public": PRIVATE,
    "org_only": ORG_ADMINS,
}

# Personal profile fields (Account settings).
PERSONAL_FIELD_DEFS = [
    {
        "key": "username",
        "label": "Username",
        "required": True,
        "field_type": "text",
        "has_visibility": False,
    },
    {
        "key": "first_name",
        "label": "First name",
        "required": False,
        "field_type": "text",
        "has_visibility": True,
    },
    {
        "key": "last_name",
        "label": "Last name",
        "required": False,
        "field_type": "text",
        "has_visibility": True,
    },
    {
        "key": "profile_picture",
        "label": "Profile picture",
        "required": False,
        "field_type": "image",
        "has_visibility": True,
    },
    {
        "key": "city",
        "label": "City",
        "required": False,
        "field_type": "text",
        "has_visibility": True,
    },
    {
        "key": "state",
        "label": "State",
        "required": False,
        "field_type": "text",
        "has_visibility": True,
    },
    {
        "key": "zip_code",
        "label": "ZIP",
        "required": False,
        "field_type": "text",
        "has_visibility": True,
    },
    {
        "key": "phone",
        "label": "Telephone",
        "required": False,
        "field_type": "tel",
        "has_visibility": True,
    },
    {
        "key": "contact_email",
        "label": "Email",
        "required": False,
        "field_type": "email",
        "has_visibility": True,
    },
]

# Fields an organization requests from members by default (shared on join).
DEFAULT_ORG_REQUESTED_MEMBER_FIELDS = [
    {
        "key": "username",
        "label": "Username",
        "required": True,
        "field_type": "text",
        "personal_key": "username",
    },
    {
        "key": "first_name",
        "label": "First name",
        "required": False,
        "field_type": "text",
        "personal_key": "first_name",
    },
    {
        "key": "last_name",
        "label": "Last name",
        "required": False,
        "field_type": "text",
        "personal_key": "last_name",
    },
    {
        "key": "city",
        "label": "City",
        "required": False,
        "field_type": "text",
        "personal_key": "city",
    },
    {
        "key": "state",
        "label": "State",
        "required": False,
        "field_type": "text",
        "personal_key": "state",
    },
    {
        "key": "zip_code",
        "label": "ZIP",
        "required": False,
        "field_type": "text",
        "personal_key": "zip_code",
    },
    {
        "key": "phone",
        "label": "Telephone",
        "required": False,
        "field_type": "tel",
        "personal_key": "phone",
    },
    {
        "key": "contact_email",
        "label": "Email",
        "required": False,
        "field_type": "email",
        "personal_key": "contact_email",
    },
    {
        "key": "profile_picture",
        "label": "Profile picture",
        "required": False,
        "field_type": "image",
        "personal_key": "profile_picture",
    },
]

# Organization account fields (admins edit the org itself).
ORG_ACCOUNT_FIELD_DEFS = [
    {
        "key": "profile_picture",
        "label": "Organization profile picture",
        "required": False,
        "field_type": "image",
    },
    {
        "key": "public_username",
        "label": "Organization @username",
        "required": False,
        "field_type": "slug",
        "help_text": "CommuniBetter shortcode used to find this org (e.g. StreamersInternational).",
    },
    {
        "key": "first_name",
        "label": "First name",
        "required": False,
        "field_type": "text",
        "help_text": "Contact first name for this organization.",
    },
    {
        "key": "last_name",
        "label": "Last name",
        "required": False,
        "field_type": "text",
        "help_text": "Contact last name for this organization.",
    },
    {
        "key": "city",
        "label": "City",
        "required": False,
        "field_type": "text",
    },
    {
        "key": "state",
        "label": "State",
        "required": False,
        "field_type": "text",
    },
    {
        "key": "zip_code",
        "label": "ZIP",
        "required": False,
        "field_type": "text",
    },
    {
        "key": "phone",
        "label": "Telephone",
        "required": False,
        "field_type": "tel",
    },
    {
        "key": "contact_email",
        "label": "Email",
        "required": False,
        "field_type": "email",
    },
]


def normalize_visibility(value: str | None, *, field_key: str | None = None) -> str:
    # Username is always public — ignore stored overrides.
    if field_key == "username":
        return PUBLIC
    if value in _LEGACY_VISIBILITY:
        value = _LEGACY_VISIBILITY[value]
    if value in FIELD_VISIBILITY_META:
        return value
    if field_key and field_key in DEFAULT_VISIBILITY_BY_KEY:
        return DEFAULT_VISIBILITY_BY_KEY[field_key]
    return DEFAULT_FIELD_VISIBILITY


def next_visibility(value: str | None) -> str:
    current = normalize_visibility(value)
    idx = FIELD_VISIBILITY_ORDER.index(current)
    return FIELD_VISIBILITY_ORDER[(idx + 1) % len(FIELD_VISIBILITY_ORDER)]


def visibility_payload(value: str | None, *, field_key: str | None = None) -> dict:
    key = normalize_visibility(value, field_key=field_key)
    meta = FIELD_VISIBILITY_META[key]
    return {
        "value": key,
        "label": meta["label"],
        "short": meta["short"],
        "description": meta["description"],
    }


def get_visibility_map(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {str(k): normalize_visibility(v, field_key=str(k)) for k, v in raw.items()}


def field_visible_on_profile(visibility: str | None, *, field_key: str | None = None) -> bool:
    """Whether a field may appear on /u/<username> (public card)."""
    if field_key == "username":
        return True
    return normalize_visibility(visibility, field_key=field_key) == PUBLIC


def personal_field_value(profile, key: str, request=None):
    if key == "username":
        return profile.user.username if profile and profile.user_id else ""
    if key == "profile_picture":
        if not profile or not profile.profile_picture:
            return None
        try:
            url = profile.profile_picture.url
            return request.build_absolute_uri(url) if request else url
        except ValueError:
            return None
    if not profile:
        return ""
    return (getattr(profile, key, None) or "") if key != "profile_picture" else None


def sync_display_name(profile) -> str:
    parts = [
        (profile.first_name or "").strip(),
        (profile.last_name or "").strip(),
    ]
    name = " ".join(p for p in parts if p).strip()
    if name:
        profile.display_name = name
    return profile.display_name or ""


def build_public_profile_payload(user, request) -> dict:
    """Profile card for /u/<username>, filtered by field + membership visibility."""
    from api.control_numbers import (
        ensure_user_control_number,
        format_user_control_number,
    )
    from api.models import OrganizationMembership, UserProfile

    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)
    except Exception:
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.username,
            "profile_picture_url": None,
            "communibetter_id": None,
            "organizations": [],
        }

    control_number = ensure_user_control_number(profile)
    viewer = getattr(request, "user", None)
    viewer_auth = bool(viewer and getattr(viewer, "is_authenticated", False))
    vis_map = get_visibility_map(profile.field_visibility)

    def allow(key: str) -> bool:
        return field_visible_on_profile(vis_map.get(key), field_key=key)

    # Username + CommuniBetter ID are always present; other fields respect visibility.
    display_name = ""
    if allow("first_name") or allow("last_name"):
        parts = []
        if allow("first_name"):
            parts.append((profile.first_name or "").strip())
        if allow("last_name"):
            parts.append((profile.last_name or "").strip())
        display_name = " ".join(p for p in parts if p)
    if not display_name:
        display_name = user.username

    picture_url = None
    if allow("profile_picture"):
        picture_url = personal_field_value(profile, "profile_picture", request)

    payload = {
        "id": user.id,
        "username": user.username,
        "display_name": display_name,
        "profile_picture_url": picture_url,
        "control_number": control_number,
        "communibetter_id": format_user_control_number(control_number),
        "first_name": (profile.first_name or "").strip() if allow("first_name") else None,
        "last_name": (profile.last_name or "").strip() if allow("last_name") else None,
        "city": (profile.city or "").strip() if allow("city") else None,
        "state": (profile.state or "").strip() if allow("state") else None,
        "zip_code": (profile.zip_code or "").strip() if allow("zip_code") else None,
        "phone": (profile.phone or "").strip() if allow("phone") else None,
        "contact_email": (
            (profile.contact_email or "").strip() if allow("contact_email") else None
        ),
        "organizations": [],
        "viewer_authenticated": viewer_auth,
    }

    from api.models import Organization

    memberships = (
        OrganizationMembership.objects.filter(
            user=user,
            show_on_profile=True,
        )
        .exclude(organization__status=Organization.Status.CLOSED)
        .select_related("organization")
        .order_by("organization__name")
    )
    payload["organizations"] = [
        {
            "id": m.organization_id,
            "name": m.organization.name,
            "slug": m.organization.slug,
            "role": m.role,
        }
        for m in memberships
    ]

    return payload
