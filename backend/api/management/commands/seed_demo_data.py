import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    AccessCode,
    Meeting,
    MeetingSlide,
    MeetingSession,
    Organization,
    OrganizationBoard,
    OrganizationMembership,
    ResourceType,
    Survey,
    SurveyQuestion,
)
from api.meeting_service import create_initial_session, create_meeting_slides

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo users, organization, surveys, meetings, and access codes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete demo access codes and re-create them (keeps users and org).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_resource_types")

        superuser_username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        superuser_email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@communib.com")
        superuser_password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "CommunibAdmin2026!")

        if not User.objects.filter(username=superuser_username).exists():
            User.objects.create_superuser(
                username=superuser_username,
                email=superuser_email,
                password=superuser_password,
            )
            self.stdout.write(self.style.SUCCESS(f"Created superuser: {superuser_username}"))
        else:
            self.stdout.write(f"Superuser already exists: {superuser_username}")

        demo_users = [
            ("orgadmin", "orgadmin@example.com", "DemoOrgAdmin2026!"),
            ("member1", "member1@example.com", "DemoMember2026!"),
        ]
        for username, email, password in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user: {username}"))
            else:
                self.stdout.write(f"User already exists: {username}")

        org, _ = Organization.objects.get_or_create(
            slug="nc-dot",
            defaults={
                "name": "North Carolina DOT Community",
                "description": "Demo organization for road planning and community feedback.",
                "is_active": True,
                "is_verified": True,
            },
        )
        OrganizationBoard.objects.get_or_create(
            organization=org,
            defaults={"title": "NCDOT Community Board"},
        )

        orgadmin = User.objects.get(username="orgadmin")
        OrganizationMembership.objects.get_or_create(
            organization=org,
            user=orgadmin,
            defaults={"role": OrganizationMembership.Role.ADMIN},
        )
        member1 = User.objects.get(username="member1")
        OrganizationMembership.objects.get_or_create(
            organization=org,
            user=member1,
            defaults={"role": OrganizationMembership.Role.MEMBER},
        )

        survey_type = ResourceType.objects.get(slug="survey")
        meeting_type = ResourceType.objects.get(slug="meeting")
        org_type = ResourceType.objects.get(slug="organization")

        roads_survey, _ = Survey.objects.get_or_create(
            organization=org,
            title="Road Safety Feedback 2026",
            defaults={
                "description": "Share feedback on road safety improvements in your area.",
                "is_anonymous": True,
                "is_active": True,
            },
        )
        if not roads_survey.questions.exists():
            SurveyQuestion.objects.create(
                survey=roads_survey,
                order=1,
                text="Which road concern matters most to you?",
                question_type=SurveyQuestion.QuestionType.CHOICE,
                choices=["Potholes", "Traffic signals", "Sidewalks", "Speed limits"],
            )
            SurveyQuestion.objects.create(
                survey=roads_survey,
                order=2,
                text="Additional comments",
                question_type=SurveyQuestion.QuestionType.TEXT,
            )

        test_survey, _ = Survey.objects.get_or_create(
            organization=org,
            title="Test Survey",
            defaults={
                "description": "A short demo survey for testing code lookup.",
                "is_anonymous": True,
                "is_active": True,
            },
        )
        if not test_survey.questions.exists():
            SurveyQuestion.objects.create(
                survey=test_survey,
                order=1,
                text="How did you hear about this community?",
                question_type=SurveyQuestion.QuestionType.TEXT,
            )

        town_hall, created_town_hall = Meeting.objects.get_or_create(
            organization=org,
            title="Public Town Hall",
            defaults={
                "description": "Open community meeting — no login required.",
                "access_mode": Meeting.AccessMode.PUBLIC,
                "status": "scheduled",
                "allow_start_early": True,
                "is_anonymous": True,
                "ai_mode": Meeting.AIMode.SELF_HOSTED,
            },
        )
        if town_hall.ai_mode == Meeting.AIMode.NONE:
            town_hall.ai_mode = Meeting.AIMode.SELF_HOSTED
            town_hall.save(update_fields=["ai_mode"])
        if created_town_hall or not town_hall.slides.exists():
            town_hall.slides.all().delete()
            create_meeting_slides(
                town_hall,
                [
                    {
                        "order": 1,
                        "slide_type": MeetingSlide.SlideType.PARTICIPANT_INFO,
                        "title": "About you",
                        "fields": [
                            {
                                "key": "zip_code",
                                "label": "Zip Code",
                                "required": False,
                                "field_type": "text",
                                "options": [],
                            }
                        ],
                    },
                    {
                        "order": 2,
                        "slide_type": MeetingSlide.SlideType.STANDARD,
                        "prompt": "What transportation issue should we prioritize?",
                        "question_format": MeetingSlide.QuestionFormat.SINGLE_CHOICE,
                        "choices": ["Roads", "Buses", "Bikes", "Other"],
                    },
                    {
                        "order": 3,
                        "slide_type": MeetingSlide.SlideType.ISSUE_CARD,
                        "prompt": "Share a concern or idea for your community.",
                    },
                    {
                        "order": 4,
                        "slide_type": MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
                        "prompt": "What local government issue matters most to you? (e.g. roads, schools, taxes)",
                    },
                ],
            )
            if not town_hall.sessions.exists():
                create_initial_session(town_hall)
        elif not town_hall.slides.filter(
            slide_type=MeetingSlide.SlideType.POLITICAL_ISSUE_CARD
        ).exists():
            max_order = (
                town_hall.slides.order_by("-order").values_list("order", flat=True).first()
                or 0
            )
            create_meeting_slides(
                town_hall,
                [
                    {
                        "order": max_order + 1,
                        "slide_type": MeetingSlide.SlideType.POLITICAL_ISSUE_CARD,
                        "prompt": "What local government issue matters most to you? (e.g. roads, schools, taxes)",
                    },
                ],
            )

        Meeting.objects.get_or_create(
            organization=org,
            title="Semi-Public Planning Session",
            defaults={
                "description": "Planning session for registered community members.",
                "access_mode": Meeting.AccessMode.SEMI_PUBLIC,
                "status": "scheduled",
            },
        )

        if options["reset"]:
            AccessCode.objects.filter(organization=org).delete()

        code_specs = [
            {
                "code": "NCDOT",
                "resource_type": org_type,
                "label": "NCDOT Community Hub",
                "search_description": "Organization hub for North Carolina DOT programs",
                "is_primary": True,
                "sort_order": 0,
            },
            {
                "code": "ROADS2026",
                "resource_type": survey_type,
                "survey": roads_survey,
                "label": "Road Safety 2026",
                "search_description": "Road safety feedback survey for 2026",
                "sort_order": 1,
            },
            {
                "code": "TESTSURVEY",
                "resource_type": survey_type,
                "survey": test_survey,
                "label": "Test Survey",
                "search_description": "Demo survey for testing search",
                "sort_order": 2,
            },
            {
                "code": "TOWNHALL",
                "resource_type": meeting_type,
                "meeting": town_hall,
                "label": "Public Town Hall",
                "search_description": "Open community town hall meeting",
                "sort_order": 3,
            },
        ]

        for spec in code_specs:
            code = spec.pop("code")
            existing = AccessCode.objects.filter(code__iexact=code).first()
            if existing:
                for field, value in spec.items():
                    setattr(existing, field, value)
                existing.organization = org
                existing.is_active = True
                existing.save()
            else:
                AccessCode.objects.create(
                    code=code,
                    organization=org,
                    is_active=True,
                    **spec,
                )
            self.stdout.write(self.style.SUCCESS(f"Access code ready: {code}"))

        self.stdout.write(self.style.SUCCESS("Demo data seed complete."))
