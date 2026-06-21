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
class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name
class ResourceType(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name
class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
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
        return f"{self.user.username} @ {self.organization.name}"
class Survey(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="surveys"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.title
class SurveyQuestion(models.Model):
    class QuestionType(models.TextChoices):
        TEXT = "text", "Text"
        CHOICE = "choice", "Multiple choice"
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)
    text = models.TextField()
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.TEXT
    )
    choices = models.JSONField(default=list, blank=True)
    class Meta:
        ordering = ["order", "id"]
    def __str__(self):
        return self.text[:50]
class SurveyAnswer(models.Model):
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE)
    response_session = models.CharField(max_length=64, db_index=True)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
class Meeting(models.Model):
    class AccessMode(models.TextChoices):
        PUBLIC = "public", "Public"
        SEMI_PUBLIC = "semi_public", "Semi-public"
        PRIVATE = "private", "Private"
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="meetings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    access_mode = models.CharField(
        max_length=20, choices=AccessMode.choices, default=AccessMode.PUBLIC
    )
    private_code_hash = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=20, default="scheduled")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.title
class MeetingQuestion(models.Model):
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
    question = models.ForeignKey(MeetingQuestion, on_delete=models.CASCADE)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    raw_text = models.TextField()
    normalized_text = models.TextField(blank=True)
    normalization_status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
class OrganizationBoard(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="board"
    )
    title = models.CharField(max_length=200, default="Message board")
    def __str__(self):
        return f"{self.organization.name} board"
class BoardPost(models.Model):
    board = models.ForeignKey(
        OrganizationBoard, on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
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