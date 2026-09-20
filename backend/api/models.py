from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
class Note(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
    def __str__(self):
        return self.title
class GeographicArea(models.Model):
    """Reusable geographic reference node (country → admin1 → admin2 / region)."""

    class AreaType(models.TextChoices):
        COUNTRY = "country", "Country"
        ADMIN1 = "admin1", "State / Province / Territory"
        ADMIN2 = "admin2", "County / County-equivalent"
        LOCALITY = "locality", "City / Locality"
        # Regional multi-area nodes (Piedmont Triad, etc.) — seed later; hide in UI for now.
        REGION = "region", "Regional area"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    area_type = models.CharField(max_length=20, choices=AreaType.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    external_code = models.CharField(max_length=32, blank=True, db_index=True)
    name_search = models.CharField(max_length=220, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["area_type", "parent", "name_search"]),
            models.Index(fields=["country_code", "area_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "slug"],
                condition=models.Q(parent__isnull=False),
                name="uniq_geo_parent_slug",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(parent__isnull=True),
                name="uniq_geo_root_slug",
            ),
        ]
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name_search = (self.name or "").casefold()
        super().save(*args, **kwargs)


class OrgCategory(models.Model):
    """Directory taxonomy: top-level categories and subcategories (parent set)."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "org categories"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "slug"],
                condition=models.Q(parent__isnull=False),
                name="uniq_orgcategory_parent_slug",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(parent__isnull=True),
                name="uniq_orgcategory_root_slug",
            ),
        ]

    def __str__(self):
        if self.parent_id:
            return f"{self.parent.name} / {self.name}"
        return self.name

    @property
    def is_subcategory(self) -> bool:
        return self.parent_id is not None


class Organization(models.Model):
    class GeographicScope(models.TextChoices):
        INTERNATIONAL = "international", "International"
        NATIONAL = "national", "National"
        STATE_PROVINCE = "state_province", "State / Province"
        # Regional scope supported in data model; UI hides it until regions are seeded.
        REGIONAL = "regional", "Regional"
        LOCAL = "local", "Local"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSURE_PENDING = "closure_pending", "Closure pending"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Legacy visibility flag; kept in sync with status (False when closed).",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_organizations",
    )
    closure_effective_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    restored_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="restored_organizations",
    )

    # Directory dimensions (kept separate from HQ / affiliation).
    geographic_scope = models.CharField(
        max_length=20,
        choices=GeographicScope.choices,
        blank=True,
        default="",
    )
    # Where the org appears in the geography-first directory (service area).
    service_area = models.ForeignKey(
        GeographicArea,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizations_serving",
    )
    # Optional physical / headquarters place (not used to infer scope).
    headquarters_area = models.ForeignKey(
        GeographicArea,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizations_headquartered",
    )
    headquarters_city = models.CharField(max_length=120, blank=True)
    headquarters_address = models.CharField(max_length=255, blank=True)

    # Primary classification: store subcategory; category is subcategory.parent.
    primary_subcategory = models.ForeignKey(
        OrgCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizations",
    )

    # Optional affiliation hierarchy — does NOT grant admin permissions.
    parent_organization = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_organizations",
    )

    search_aliases = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name

    @property
    def primary_category(self):
        if self.primary_subcategory_id and self.primary_subcategory.parent_id:
            return self.primary_subcategory.parent
        return None

    def get_current_service_level(self) -> str:
        """Authoritative effective service level (FREE when no active paid entitlement)."""
        from .billing_service import get_current_service_level

        return get_current_service_level(self)


class ResourceType(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name
class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="org_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        unique_together = ("organization", "user")

    def __str__(self):
        return f"{self.user.username} @ {self.organization.name} ({self.role})"


class OrganizationService(models.Model):
    """
    Billing entitlement for an organization.

    Organizations without an ACTIVE paid entitlement resolve to FREE.
    Do not require a row for the free tier.
    """

    class ServiceLevel(models.TextChoices):
        FREE = "FREE", "Organization (Free)"
        STARTER = "STARTER", "Starter"
        BASIC = "BASIC", "Basic"
        COMMUNITY = "COMMUNITY", "Community"
        COMMUNITY_PLUS = "COMMUNITY_PLUS", "Community Plus"
        ENTERPRISE = "ENTERPRISE", "Enterprise"

    class BillingSource(models.TextChoices):
        FREE = "FREE", "Free"
        PAYPAL = "PAYPAL", "PayPal"
        ACCESS_CODE = "ACCESS_CODE", "Access code"
        ADMIN_GRANT = "ADMIN_GRANT", "Administrative grant"
        ENTERPRISE_CONTRACT = "ENTERPRISE_CONTRACT", "Enterprise contract"
        UMBRELLA_LICENSE = "UMBRELLA_LICENSE", "Umbrella license"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        PAYMENT_FAILED = "PAYMENT_FAILED", "Payment failed"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="services",
    )
    requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_organization_services",
        help_text="User who started this checkout or entitlement request.",
    )
    service_level = models.CharField(max_length=32, choices=ServiceLevel.choices)
    billing_source = models.CharField(
        max_length=32,
        choices=BillingSource.choices,
        default=BillingSource.FREE,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    paypal_plan_id = models.CharField(max_length=64, blank=True, default="")
    paypal_subscription_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    billing_reference = models.CharField(
        max_length=64,
        unique=True,
        help_text="Opaque CommuniB billing reference (e.g. COMMUNIB-SUB-000184-00001).",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="When True, keep ACTIVE paid access until current_period_end, then expire.",
    )
    umbrella_license = models.ForeignKey(
        "UmbrellaLicense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="member_services",
        help_text="Set when this entitlement is granted by another org's umbrella license.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "service_level", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.organization.slug} {self.service_level} "
            f"{self.status} ({self.billing_reference})"
        )


class UmbrellaLicense(models.Model):
    """
    A paid organization's shareable code that lets other orgs run on its plan.

    Members get an ``OrganizationService`` with billing_source=UMBRELLA_LICENSE
    mirroring the licensor's level, plus an accepted ``umbrella_member``
    relationship. All metered usage by members counts against the licensor's
    pooled usage period.
    """

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="umbrella_license"
    )
    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)
    max_members = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank = no cap on member organizations."
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"umbrella:{self.organization_id}:{self.code}"


class OrganizationUsagePeriod(models.Model):
    """
    Append-only billing-period usage counters for an organization.

    Do not wipe these rows when a period rolls; create a new row instead.
    Attendee counts are not stored here — they are derived from MeetingAttendance.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="usage_periods",
    )
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField()
    service_level = models.CharField(max_length=32)
    survey_submissions_used = models.PositiveIntegerField(default=0)
    meetings_started_used = models.PositiveIntegerField(default=0)
    ai_meeting_runs_used = models.PositiveIntegerField(default=0)
    board_posts_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "period_start"],
                name="uniq_org_usage_period_start",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "-period_start"]),
        ]

    def __str__(self):
        return f"{self.organization_id} {self.period_start.date()} {self.service_level}"


class AiUsageEvent(models.Model):
    """Internal AI cost/quota event. Customer dashboards do not show tokens."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="ai_usage_events",
    )
    meeting = models.ForeignKey(
        "Meeting",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_usage_events",
    )
    usage_period = models.ForeignKey(
        OrganizationUsagePeriod,
        on_delete=models.CASCADE,
        related_name="ai_usage_events",
    )
    provider = models.CharField(max_length=32, blank=True, default="")
    consumed_run = models.BooleanField(default=False)
    success = models.BooleanField(default=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["usage_period", "meeting"]),
        ]

    def __str__(self):
        return f"ai {self.organization_id} meeting={self.meeting_id} run={self.consumed_run}"


class AccessCodeRedemption(models.Model):
    """
    History of access-code grants (complimentary / promo / temp codes).

    Temporary codes (e.g. SUPERBASIC from env) are validated in application
    code; this table records who redeemed what for which organization.
    Future AccessCode catalog rows can link here without changing callers.
    """

    code = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Normalized access code that was redeemed (uppercase).",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="access_code_redemptions",
    )
    redeemed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_code_redemptions",
    )
    organization_service = models.ForeignKey(
        OrganizationService,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_code_redemptions",
    )
    service_level = models.CharField(
        max_length=32,
        choices=OrganizationService.ServiceLevel.choices,
    )
    redeemed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Reserved for a future AccessCode catalog FK / metadata.
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-redeemed_at", "-id"]
        indexes = [
            models.Index(fields=["organization", "code"]),
            models.Index(fields=["code", "-redeemed_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="uniq_access_code_redemption_per_org_code",
            )
        ]

    def __str__(self):
        return f"{self.code} → {self.organization_id} ({self.service_level})"


class Survey(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="surveys"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    aggregate_sharing_notice = models.BooleanField(
        default=True,
        help_text=(
            "Tell respondents that anonymous combined results may be shared with "
            "policymakers and decision makers not listed in the disclosure."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SurveyQuestion(models.Model):
    class QuestionType(models.TextChoices):
        TEXT = "text", "Text"
        CHOICE = "choice", "Multiple choice"
        CONTENT = "content", "Content (text / media)"

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)
    text = models.TextField(blank=True, default="")
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.TEXT
    )
    choices = models.JSONField(default=list, blank=True)
    is_demographic = models.BooleanField(
        default=False,
        help_text="Demographic questions are shown after the main survey questions.",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="For content blocks: body, banner_url, video_url.",
    )
    question_key = models.CharField(
        max_length=40,
        blank=True,
        default="",
        db_index=True,
        help_text="Normalized hash of the question text; groups the same question across surveys/meetings.",
    )

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        from api.question_identity import question_key_for

        if self.question_type == self.QuestionType.CONTENT:
            self.question_key = ""
        else:
            self.question_key = question_key_for(self.text)
        super().save(*args, **kwargs)

    def __str__(self):
        return (self.text or self.question_type)[:50]
class SurveyAnswer(models.Model):
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE)
    response_session = models.CharField(max_length=64, db_index=True)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class SurveySubmission(models.Model):
    """One completed survey response (not per-question)."""

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="submissions"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="survey_submissions",
    )
    usage_period = models.ForeignKey(
        OrganizationUsagePeriod,
        on_delete=models.CASCADE,
        related_name="survey_submissions",
    )
    response_session = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "response_session"],
                name="uniq_survey_response_session",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "usage_period"]),
        ]

    def __str__(self):
        return f"survey {self.survey_id} session {self.response_session}"


class Meeting(models.Model):
    class AccessMode(models.TextChoices):
        PUBLIC = "public", "Public"
        SEMI_PUBLIC = "semi_public", "Semi-public"
        PRIVATE = "private", "Private"

    class AIMode(models.TextChoices):
        NONE = "none", "No AI"
        SELF_HOSTED = "self_hosted", "Self-Hosted AI"
        PAID = "paid", "Paid AI Model"

    class MinutesCreator(models.TextChoices):
        ORGANIZER_ONLY = "organizer_only", "Organizer only"
        ORGANIZER_OR_ATTENDEES = "organizer_or_attendees", "Organizer or attendees"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="meetings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True, default="")
    access_mode = models.CharField(
        max_length=20, choices=AccessMode.choices, default=AccessMode.PUBLIC
    )
    private_code_hash = models.CharField(max_length=128, blank=True)
    scheduled_start_at = models.DateTimeField(null=True, blank=True)
    scheduled_end_at = models.DateTimeField(null=True, blank=True)
    allow_start_early = models.BooleanField(default=False)
    is_anonymous = models.BooleanField(default=False)
    allow_self_paced = models.BooleanField(
        default=False,
        help_text=(
            "When True, participants may answer any slide without waiting for the "
            "organizer to advance. Default is organizer-paced."
        ),
    )
    ai_mode = models.CharField(
        max_length=20, choices=AIMode.choices, default=AIMode.NONE
    )
    results_visible_to_community = models.BooleanField(
        default=False,
        help_text="When True, eligible users may view meeting results after the meeting ends.",
    )
    minutes_creator = models.CharField(
        max_length=32,
        choices=MinutesCreator.choices,
        default=MinutesCreator.ORGANIZER_ONLY,
    )
    aggregate_sharing_notice = models.BooleanField(
        default=True,
        help_text=(
            "Show participants that anonymous combined results may be shared with "
            "policymakers and decision makers not listed on the disclosure screen."
        ),
    )
    status = models.CharField(max_length=20, default="scheduled")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class MeetingShare(models.Model):
    """
    Grant another organization access to a meeting's results.

    Access level is derived, never chosen:
      * declared before the meeting first started and still active → FULL
        (every stored row, keyed by the random per-meeting participant UUID)
      * granted after the meeting started, or later revoked → AGGREGATE
        (buckets and totals only)
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    class Access(models.TextChoices):
        FULL = "full", "Full data"
        AGGREGATE = "aggregate", "Buckets and totals"

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="shares")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="meetings_shared_with_us"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    declared_before_start = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "organization"], name="uniq_meeting_share_per_org"
            )
        ]
        indexes = [models.Index(fields=["organization", "status"])]

    @property
    def effective_access(self) -> str:
        if self.status == self.Status.ACTIVE and self.declared_before_start:
            return self.Access.FULL
        return self.Access.AGGREGATE

    def __str__(self):
        return f"meeting {self.meeting_id} → org {self.organization_id} [{self.status}]"


class MeetingExpectedAttendance(models.Model):
    """RSVP / expected attendance — separate from actual MeetingAttendance."""

    class Status(models.TextChoices):
        GOING = "going", "Going"
        PENDING = "pending", "Pending"

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="expected_attendances"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="meeting_expected_attendances"
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "user"],
                name="unique_meeting_expected_attendance_per_user",
            )
        ]

    def __str__(self):
        return f"{self.meeting_id}:{self.user_id}:{self.status}"


class MeetingSummary(models.Model):
    """Meeting minutes / narrative summary with draft → publish lifecycle."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        PUBLISHED = "published", "Published"

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="summaries"
    )
    author = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    is_organizer_authored = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        verbose_name_plural = "Meeting summaries"

    def __str__(self):
        return f"{self.meeting_id}:{self.status}:{self.pk}"


class MeetingSlide(models.Model):
    """Ordered slide in a meeting deck (info, questions, issue cards)."""

    class SlideType(models.TextChoices):
        PARTICIPANT_INFO = "participant_info", "Participant information"
        CONTENT = "content", "Content (text / media)"
        STANDARD = "standard", "Standard question"
        ISSUE_CARD = "issue_card", "Issue card"
        POLITICAL_ISSUE_CARD = "political_issue_card", "Political issue card"

    class QuestionFormat(models.TextChoices):
        TEXT = "text", "Free text"
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTI_CHOICE = "multi_choice", "Multiple choice"

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="slides"
    )
    order = models.PositiveIntegerField(default=0)
    slide_type = models.CharField(max_length=30, choices=SlideType.choices)
    title = models.CharField(max_length=300, blank=True)
    prompt = models.TextField(blank=True)
    question_format = models.CharField(
        max_length=20,
        choices=QuestionFormat.choices,
        blank=True,
        default="",
    )
    choices = models.JSONField(default=list, blank=True)
    config = models.JSONField(default=dict, blank=True)
    question_key = models.CharField(
        max_length=40,
        blank=True,
        default="",
        db_index=True,
        help_text="Normalized hash of prompt/title; groups the same question across meetings.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    QUESTION_TYPES = ("standard", "issue_card", "political_issue_card")

    @property
    def is_question(self) -> bool:
        return self.slide_type in self.QUESTION_TYPES

    def save(self, *args, **kwargs):
        from api.question_identity import question_key_for

        self.question_key = (
            question_key_for(self.prompt or self.title) if self.is_question else ""
        )
        super().save(*args, **kwargs)

    def __str__(self):
        label = self.title or self.prompt or self.slide_type
        return f"{self.meeting.title} — {label[:50]}"


class MeetingSession(models.Model):
    """One run of a meeting (supports restart in later phases)."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="sessions"
    )
    session_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    current_slide = models.ForeignKey(
        MeetingSlide,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    started_from_slide = models.ForeignKey(
        MeetingSlide,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    attendee_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Snapshot of plan interactive-attendee cap when the session went live.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session_number", "-id"]
        unique_together = ("meeting", "session_number")

    def __str__(self):
        return f"{self.meeting.title} session #{self.session_number}"


class MeetingAttendance(models.Model):
    class Status(models.TextChoices):
        JOINED = "joined", "Joined"
        LEFT = "left", "Left"

    session = models.ForeignKey(
        MeetingSession, on_delete=models.CASCADE, related_name="attendances"
    )
    attendance_id = models.UUIDField(unique=True, db_index=True)
    participant_id = models.UUIDField(db_index=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.JOINED
    )

    class Meta:
        verbose_name_plural = "Meeting attendances"

    def __str__(self):
        return f"{self.session} — {self.participant_id}"


class ParticipantProfileValue(models.Model):
    """Voluntary participant info — stored separately from anonymous responses."""

    attendance = models.ForeignKey(
        MeetingAttendance, on_delete=models.CASCADE, related_name="profile_values"
    )
    field_key = models.CharField(max_length=100)
    field_label = models.CharField(max_length=200)
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("attendance", "field_key")


class MeetingQuestion(models.Model):
    """Legacy Q&A model — superseded by MeetingSlide in Phase 1+."""

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="questions"
    )
    text = models.TextField()
    asked_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MeetingResponse(models.Model):
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="responses"
    )
    session = models.ForeignKey(
        MeetingSession,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    slide = models.ForeignKey(
        MeetingSlide,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    attendance = models.ForeignKey(
        MeetingAttendance,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responses",
    )
    question = models.ForeignKey(
        MeetingQuestion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    participant_id = models.UUIDField(null=True, blank=True, db_index=True)
    raw_response = models.TextField(blank=True)
    selected_options = models.JSONField(default=list, blank=True)
    normalized_response = models.TextField(blank=True)
    normalization_status = models.CharField(max_length=20, default="pending")
    major_issue = models.CharField(max_length=200, blank=True)
    specific_issue = models.CharField(max_length=200, blank=True)
    issue_type = models.CharField(max_length=200, blank=True)
    classification_confidence = models.FloatField(null=True, blank=True)
    classification_status = models.CharField(max_length=20, default="pending")
    review_reason = models.TextField(blank=True)
    classified_raw_snapshot = models.TextField(
        blank=True,
        help_text="Raw response text at the last political classification run.",
    )
    classification_reprocess = models.BooleanField(default=False)
    classification_processed_at = models.DateTimeField(null=True, blank=True)
    importance_order = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Participant-ranked order on issue card slides (1 = highest importance).",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class MeetingResponseAI(models.Model):
    """AI enrichments — populated only when meeting.ai_mode is enabled."""

    response = models.OneToOneField(
        MeetingResponse, on_delete=models.CASCADE, related_name="ai"
    )
    ai_summary = models.TextField(blank=True)
    ai_tags = models.JSONField(default=list, blank=True)
    sentiment = models.CharField(max_length=50, blank=True)
    support_level = models.CharField(max_length=50, blank=True)
    opposition_level = models.CharField(max_length=50, blank=True)
    action_item = models.TextField(blank=True)
    decision_made = models.TextField(blank=True)
    unresolved_question = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class QuestionTag(models.Model):
    """
    Reporting tag for questions (meeting slides and survey questions).

    ``organization`` NULL = shared catalog available to everyone; otherwise a
    custom tag owned by one organization. Distinct from AI political
    classification — tags are organizer-assigned metadata for reporting.
    """

    class Category(models.TextChoices):
        PURPOSE = "purpose", "Purpose"
        AUDIENCE = "audience", "Audience / context"
        TOPIC = "topic", "Topic"
        CUSTOM = "custom", "Custom"

    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="question_tags",
    )
    slug = models.SlugField(max_length=80)
    label = models.CharField(max_length=120)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.CUSTOM
    )
    description = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="uniq_question_tag_per_org_slug"
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(organization__isnull=True),
                name="uniq_global_question_tag_slug",
            ),
        ]

    def __str__(self):
        scope = "global" if self.organization_id is None else f"org {self.organization_id}"
        return f"{self.label} ({scope})"


class QuestionTagLink(models.Model):
    """
    Tag ↔ question link within an organization.

    Scope is by ``question_key`` (normalized question text), so the same
    question asked in many meetings/surveys carries the tag everywhere —
    past and future. When ``slide`` or ``survey_question`` is set, the link
    applies to that single use only.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="question_tag_links"
    )
    tag = models.ForeignKey(QuestionTag, on_delete=models.CASCADE, related_name="links")
    question_key = models.CharField(max_length=40, db_index=True)
    slide = models.ForeignKey(
        MeetingSlide,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tag_links",
    )
    survey_question = models.ForeignKey(
        SurveyQuestion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tag_links",
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "question_key"]),
            models.Index(fields=["organization", "tag"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "tag", "question_key"],
                condition=models.Q(slide__isnull=True, survey_question__isnull=True),
                name="uniq_tag_link_org_wide",
            ),
            models.UniqueConstraint(
                fields=["tag", "slide"],
                condition=models.Q(slide__isnull=False),
                name="uniq_tag_link_slide",
            ),
            models.UniqueConstraint(
                fields=["tag", "survey_question"],
                condition=models.Q(survey_question__isnull=False),
                name="uniq_tag_link_survey_question",
            ),
        ]

    @property
    def is_org_wide(self) -> bool:
        return self.slide_id is None and self.survey_question_id is None


class PoliticalClassification(models.Model):
    """One path in a political issue taxonomy — multiple rows per response allowed."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI = "ai", "AI"

    response = models.ForeignKey(
        MeetingResponse, on_delete=models.CASCADE, related_name="political_classifications"
    )
    major_issue = models.CharField(max_length=200, blank=True)
    specific_issue = models.CharField(max_length=200, blank=True)
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.AI
    )
    confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserProfile(models.Model):
    """Extensible account profile; required fields gate dashboard access."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    profile_picture = models.ImageField(
        upload_to="profiles/", blank=True, null=True
    )
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.username

    @property
    def is_complete(self) -> bool:
        return bool(self.display_name.strip() and self.user.username.strip())


class PersonalBoard(models.Model):
    """Private posting board for a single user (restricted — owner only)."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="personal_board"
    )
    title = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s board"


class WallPostType(models.TextChoices):
    """Shared wall content types for personal and organization boards."""

    POST = "post", "Post"
    QUESTION = "question", "Question"
    POLL = "poll", "Poll"
    EVENT = "event", "Event"
    MEETING = "meeting", "Meeting"


class PersonalBoardPost(models.Model):
    board = models.ForeignKey(
        PersonalBoard, on_delete=models.CASCADE, related_name="posts"
    )
    post_type = models.CharField(
        max_length=20,
        choices=WallPostType.choices,
        default=WallPostType.POST,
    )
    title = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField(blank=True, default="")
    event_starts_at = models.DateTimeField(null=True, blank=True)
    event_ends_at = models.DateTimeField(null=True, blank=True)
    event_location = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class PersonalBoardPollOption(models.Model):
    post = models.ForeignKey(
        PersonalBoardPost, on_delete=models.CASCADE, related_name="poll_options"
    )
    text = models.CharField(max_length=200)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class PersonalBoardPollVote(models.Model):
    post = models.ForeignKey(
        PersonalBoardPost, on_delete=models.CASCADE, related_name="poll_votes"
    )
    option = models.ForeignKey(
        PersonalBoardPollOption, on_delete=models.CASCADE, related_name="votes"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"], name="unique_personal_poll_vote_per_user"
            )
        ]


class OrganizationBoard(models.Model):
    class PostingMode(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS_ONLY = "members_only", "Members only"
        RESTRICTED = "restricted", "Restricted (admin posts only)"

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="board"
    )
    title = models.CharField(max_length=200, blank=True, default="")
    posting_mode = models.CharField(
        max_length=20,
        choices=PostingMode.choices,
        default=PostingMode.PUBLIC,
    )
    hub_preview_count = models.PositiveSmallIntegerField(
        default=5,
        help_text="How many newest board posts to show on the public organization hub (0 hides the preview).",
    )

    def __str__(self):
        return f"{self.organization.name} board"


class BoardPost(models.Model):
    board = models.ForeignKey(
        OrganizationBoard, on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    post_type = models.CharField(
        max_length=20,
        choices=WallPostType.choices,
        default=WallPostType.POST,
    )
    title = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField(blank=True, default="")
    event_starts_at = models.DateTimeField(null=True, blank=True)
    event_ends_at = models.DateTimeField(null=True, blank=True)
    event_location = models.CharField(max_length=255, blank=True, default="")
    meeting = models.OneToOneField(
        "Meeting",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="wall_post",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class BoardPollOption(models.Model):
    post = models.ForeignKey(
        BoardPost, on_delete=models.CASCADE, related_name="poll_options"
    )
    text = models.CharField(max_length=200)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class BoardPollVote(models.Model):
    post = models.ForeignKey(
        BoardPost, on_delete=models.CASCADE, related_name="poll_votes"
    )
    option = models.ForeignKey(
        BoardPollOption, on_delete=models.CASCADE, related_name="votes"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"], name="unique_board_poll_vote_per_user"
            )
        ]


class BoardPostReply(models.Model):
    post = models.ForeignKey(BoardPost, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]


class Mailbox(models.Model):
    """
    Unified inbox identity for a personal account or an organization.

    Personal and org inboxes share the same Conversation / Message tables.
    """

    class Kind(models.TextChoices):
        PERSONAL = "personal", "Personal"
        ORGANIZATION = "organization", "Organization"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    user = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="mailbox",
    )
    organization = models.OneToOneField(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="mailbox",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="personal", user__isnull=False, organization__isnull=True)
                    | models.Q(
                        kind="organization",
                        user__isnull=True,
                        organization__isnull=False,
                    )
                ),
                name="mailbox_owner_matches_kind",
            )
        ]

    def __str__(self):
        if self.kind == self.Kind.PERSONAL and self.user_id:
            return f"mailbox:user:{self.user.username}"
        if self.organization_id:
            return f"mailbox:org:{self.organization.slug}"
        return f"mailbox:{self.pk}"

    @property
    def display_name(self) -> str:
        if self.kind == self.Kind.ORGANIZATION and self.organization_id:
            return self.organization.name
        if self.user_id:
            profile = getattr(self.user, "profile", None)
            if profile and profile.display_name:
                return profile.display_name
            return self.user.username
        return "Mailbox"


class MailboxBlock(models.Model):
    """
    Blocker mailbox bans blocked mailbox.
    Blocked party cannot message or view the blocker's account/conversations.
    """

    blocker = models.ForeignKey(
        Mailbox, on_delete=models.CASCADE, related_name="blocks_created"
    )
    blocked = models.ForeignKey(
        Mailbox, on_delete=models.CASCADE, related_name="blocks_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("blocker", "blocked")
        indexes = [
            models.Index(fields=["blocker", "blocked"]),
            models.Index(fields=["blocked", "blocker"]),
        ]

    def __str__(self):
        return f"block:{self.blocker_id}->{self.blocked_id}"


class Conversation(models.Model):
    subject = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class ConversationParticipant(models.Model):
    """Per-mailbox view of a conversation (folder + read state)."""

    class Folder(models.TextChoices):
        PRIMARY = "primary", "Inbox"
        UNKNOWN = "unknown", "Unknown / Message requests"
        ARCHIVED = "archived", "Archived"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    mailbox = models.ForeignKey(
        Mailbox, on_delete=models.CASCADE, related_name="conversation_links"
    )
    folder = models.CharField(
        max_length=20,
        choices=Folder.choices,
        default=Folder.PRIMARY,
        db_index=True,
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("conversation", "mailbox")
        indexes = [
            models.Index(fields=["mailbox", "folder", "-joined_at"]),
        ]


class InboxMessage(models.Model):
    """Unified message row — drafts and sent messages for any mailbox."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"

    conversation = models.ForeignKey(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_mailbox = models.ForeignKey(
        Mailbox, on_delete=models.CASCADE, related_name="sent_messages"
    )
    # Optional compose targeting before send (resolved into participants on send).
    draft_to_mailbox = models.ForeignKey(
        Mailbox,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="draft_targets",
    )
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["sender_mailbox", "status", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.status}:{self.pk}:{self.subject[:40]}"


class AccessCode(models.Model):
    code = models.CharField(max_length=32, db_index=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="codes"
    )
    resource_type = models.ForeignKey(ResourceType, on_delete=models.PROTECT)
    survey = models.ForeignKey(
        Survey, null=True, blank=True, on_delete=models.CASCADE, related_name="access_codes"
    )
    meeting = models.ForeignKey(
        Meeting, null=True, blank=True, on_delete=models.CASCADE, related_name="access_codes"
    )
    label = models.CharField(max_length=200, blank=True)
    search_description = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.code
    def clean(self):
        type_slug = self.resource_type.slug
        targets = [self.survey_id, self.meeting_id]
        if type_slug == "survey":
            if not self.survey_id:
                raise ValidationError("Survey codes must link to a survey.")
            if self.meeting_id:
                raise ValidationError("Survey codes cannot also link to a meeting.")
        elif type_slug == "meeting":
            if not self.meeting_id:
                raise ValidationError("Meeting codes must link to a meeting.")
            if self.survey_id:
                raise ValidationError("Meeting codes cannot also link to a survey.")
        elif type_slug == "organization":
            if self.survey_id or self.meeting_id:
                raise ValidationError("Organization codes cannot link to survey or meeting.")
            duplicate = AccessCode.objects.filter(
                code__iexact=self.code,
                is_active=True,
                resource_type__slug="organization",
                survey__isnull=True,
                meeting__isnull=True,
            ).exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError("This Community Code is already used by another organization.")
        else:
            raise ValidationError(f"Unsupported resource type: {type_slug}")
        if type_slug in ("survey", "meeting"):
            duplicate = AccessCode.objects.filter(
                code__iexact=self.code,
                is_active=True,
            ).exclude(pk=self.pk)
            if type_slug == "survey":
                duplicate = duplicate.filter(survey__isnull=False)
            else:
                duplicate = duplicate.filter(meeting__isnull=False)
            if duplicate.exists():
                raise ValidationError("This code is already used by another survey or meeting.")
    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)


class ContactSubmission(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.email}"
class OrganizationRelationship(models.Model):
    """
    Explicit, consent-based link between two organizations.

    Direction for hierarchical kinds: ``from_organization`` is the upper party
    (parent / licensor / sponsor); ``to_organization`` is the child / member /
    sponsored org. ``partner`` is symmetric — either order.

    Relationships never grant admin rights or data access by themselves.
    ``Organization.parent_organization`` is kept in sync from accepted
    ``parent_child`` rows for directory display.
    """

    class Kind(models.TextChoices):
        PARENT_CHILD = "parent_child", "Parent / child"
        UMBRELLA_MEMBER = "umbrella_member", "Umbrella license member"
        PARTNER = "partner", "Partner"
        SPONSOR = "sponsor", "Sponsor"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        ENDED = "ended", "Ended"
        EXPIRED = "expired", "Expired"

    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    from_organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="relationships_from"
    )
    to_organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="relationships_to"
    )
    initiated_by_organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="relationships_initiated",
        help_text="Which side sent the request; the other side must accept.",
    )
    requested_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    responded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ended_by_organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    conversation = models.ForeignKey(
        "Conversation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="relationships",
    )
    note = models.CharField(max_length=500, blank=True, default="")
    public = models.BooleanField(
        default=True, help_text="Show this relationship on public hubs / directory."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["from_organization", "kind", "status"],
                name="api_orgrel_from_kind_status",
            ),
            models.Index(
                fields=["to_organization", "kind", "status"],
                name="api_orgrel_to_kind_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(from_organization=models.F("to_organization")),
                name="orgrel_no_self_relationship",
            ),
        ]

    OPEN_STATUSES = (Status.PENDING, Status.ACCEPTED)

    def __str__(self):
        return (
            f"{self.kind}:{self.from_organization_id}->{self.to_organization_id}"
            f" [{self.status}]"
        )

    def counterpart_of(self, organization: "Organization") -> "Organization":
        if organization.id == self.from_organization_id:
            return self.to_organization
        return self.from_organization

    @property
    def recipient_organization(self) -> "Organization":
        return self.counterpart_of(self.initiated_by_organization)


class OrganizationAuditEvent(models.Model):
    """Append-only audit trail for ownership, billing, and closure actions."""

    class EventType(models.TextChoices):
        OWNERSHIP_TRANSFERRED = "ownership_transferred", "Ownership transferred"
        OWNERSHIP_CANCELED = "ownership_canceled", "Ownership canceled"
        SUBSCRIPTION_CANCEL_REQUESTED = (
            "subscription_cancel_requested",
            "Subscription cancel requested",
        )
        SUBSCRIPTION_CANCELED = "subscription_canceled", "Subscription canceled"
        PAYPAL_WEBHOOK = "paypal_webhook", "PayPal webhook"
        ORGANIZATION_CLOSURE_REQUESTED = (
            "organization_closure_requested",
            "Organization closure requested",
        )
        ORGANIZATION_CLOSURE_CANCELED = (
            "organization_closure_canceled",
            "Organization closure canceled",
        )
        ORGANIZATION_CLOSED = "organization_closed", "Organization closed"
        ORGANIZATION_RESTORED = "organization_restored", "Organization restored"
        ORGANIZATION_CLAIM_REQUESTED = (
            "organization_claim_requested",
            "Organization claim requested",
        )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organization_audit_events",
    )
    event_type = models.CharField(max_length=64, choices=EventType.choices, db_index=True)
    event_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["organization", "event_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.organization_id}:{self.event_type}:{self.pk}"
