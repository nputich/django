"""Seed the shared question-tag catalog and backfill question_key."""

import hashlib
import re
import unicodedata

from django.db import migrations

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def _key(text):
    value = unicodedata.normalize("NFKC", text or "").casefold()
    value = _PUNCT.sub(" ", value)
    value = _WS.sub(" ", value).strip()
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:40] if value else ""


PURPOSE = [
    ("concern", "Concern", "Something people are worried about"),
    ("priority", "Priority", "What people want addressed first"),
    ("success", "Success / win", "Things that are going well"),
    ("idea", "Idea / suggestion", "Proposed solutions or changes"),
    ("need", "Need / request", "Specific asks for help or resources"),
    ("barrier", "Barrier / obstacle", "What gets in the way"),
    ("feedback", "Feedback on services", "Reactions to programs or services"),
    ("satisfaction", "Satisfaction", "How happy people are with something"),
    ("support-opposition", "Support / opposition", "For or against a proposal"),
    ("awareness", "Awareness", "Whether people know about something"),
    ("question-for-leaders", "Question for leadership", "Questions aimed at decision makers"),
    ("action-commitment", "Action commitment", "What people are willing to do"),
    ("demographic", "Demographic", "Who is in the room"),
]

AUDIENCE = [
    ("candidate-meeting", "Candidate meeting"),
    ("town-hall", "Town hall"),
    ("parents", "Parents"),
    ("students", "Students"),
    ("teachers", "Teachers / educators"),
    ("youth", "Youth"),
    ("seniors", "Seniors"),
    ("veterans", "Veterans"),
    ("black-community", "Black community"),
    ("latino-community", "Latino / Hispanic community"),
    ("aapi-community", "Asian American / Pacific Islander community"),
    ("indigenous-community", "Indigenous community"),
    ("immigrant-community", "Immigrant community"),
    ("faith-community", "Faith community"),
    ("lgbtq-community", "LGBTQ+ community"),
    ("disability-community", "Disability community"),
    ("women", "Women"),
    ("small-business", "Small business owners"),
    ("union-labor", "Union / labor"),
    ("healthcare-workers", "Healthcare workers"),
    ("rural", "Rural residents"),
    ("neighborhood", "Neighborhood association"),
    ("new-residents", "New residents"),
    ("volunteers", "Volunteers"),
    ("members", "Members"),
    ("donors", "Donors"),
    ("precinct", "Precinct / ward"),
]

TOPIC = [
    ("housing", "Housing & affordability"),
    ("education", "Education & schools"),
    ("public-safety", "Public safety & policing"),
    ("healthcare", "Healthcare access"),
    ("mental-health", "Mental health"),
    ("substance-use", "Substance use"),
    ("jobs-economy", "Jobs & economy"),
    ("wages-labor", "Wages & labor"),
    ("workforce-training", "Workforce training"),
    ("small-business-support", "Small business support"),
    ("transportation", "Transportation & roads"),
    ("traffic-parking", "Traffic & parking"),
    ("transit", "Public transit"),
    ("environment-climate", "Environment & climate"),
    ("water-quality", "Water quality"),
    ("energy-costs", "Energy costs"),
    ("taxes-budget", "Taxes & budget"),
    ("infrastructure", "Infrastructure & utilities"),
    ("broadband", "Broadband & technology"),
    ("voting-elections", "Voting & elections"),
    ("government-transparency", "Government transparency"),
    ("immigration", "Immigration"),
    ("childcare-families", "Childcare & families"),
    ("aging", "Seniors & aging"),
    ("homelessness", "Homelessness"),
    ("parks-recreation", "Parks & recreation"),
    ("zoning-development", "Zoning & development"),
    ("agriculture-food", "Agriculture & food"),
    ("food-security", "Food security"),
    ("civil-rights-equity", "Civil rights & equity"),
    ("gun-policy", "Gun policy"),
    ("reproductive-health", "Reproductive health"),
    ("criminal-justice", "Criminal justice"),
    ("veterans-services", "Veterans services"),
    ("disaster-preparedness", "Disaster preparedness"),
    ("libraries-culture", "Libraries & culture"),
    ("youth-programs", "Youth programs"),
    ("public-health", "Public health"),
    ("animal-services", "Animal services"),
    ("sanitation", "Trash & sanitation"),
    ("noise-nuisance", "Noise & nuisance"),
    ("community-events", "Community events"),
    ("disability-access", "Accessibility"),
    ("policing-reform", "Policing reform"),
    ("cost-of-living", "Cost of living"),
]


def seed(apps, schema_editor):
    QuestionTag = apps.get_model("api", "QuestionTag")
    rows = []
    for slug, label, desc in PURPOSE:
        rows.append(QuestionTag(organization=None, slug=slug, label=label, category="purpose", description=desc))
    for slug, label in AUDIENCE:
        rows.append(QuestionTag(organization=None, slug=slug, label=label, category="audience"))
    for slug, label in TOPIC:
        rows.append(QuestionTag(organization=None, slug=slug, label=label, category="topic"))
    existing = set(
        QuestionTag.objects.filter(organization__isnull=True).values_list("slug", flat=True)
    )
    QuestionTag.objects.bulk_create([r for r in rows if r.slug not in existing])

    MeetingSlide = apps.get_model("api", "MeetingSlide")
    for slide in MeetingSlide.objects.all().only("id", "slide_type", "prompt", "title"):
        if slide.slide_type in ("standard", "issue_card", "political_issue_card"):
            key = _key(slide.prompt or slide.title)
        else:
            key = ""
        MeetingSlide.objects.filter(pk=slide.pk).update(question_key=key)

    SurveyQuestion = apps.get_model("api", "SurveyQuestion")
    for q in SurveyQuestion.objects.all().only("id", "text"):
        SurveyQuestion.objects.filter(pk=q.pk).update(question_key=_key(q.text))


def unseed(apps, schema_editor):
    QuestionTag = apps.get_model("api", "QuestionTag")
    QuestionTag.objects.filter(organization__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0027_question_tags_and_sharing"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
