from api.content_media import normalize_content_config
from api.models import Survey, SurveyQuestion
from api.question_tags import apply_payload_tags


def create_survey_questions(
    survey: Survey, question_payloads: list[dict], *, base_order: int = 0, user=None
) -> list[SurveyQuestion]:
    created: list[SurveyQuestion] = []
    for index, question in enumerate(question_payloads):
        qtype = question.get("question_type", SurveyQuestion.QuestionType.TEXT)
        config = {}
        if qtype == SurveyQuestion.QuestionType.CONTENT:
            config = normalize_content_config(
                {
                    "body": question.get("body") or "",
                    "banner_url": question.get("banner_url") or "",
                    "video_url": question.get("video_url") or "",
                }
            )
        row = SurveyQuestion.objects.create(
            survey=survey,
            order=question.get("order", base_order + index),
            text=question.get("text") or "",
            question_type=qtype,
            choices=question.get("choices", []),
            is_demographic=bool(question.get("is_demographic"))
            and qtype != SurveyQuestion.QuestionType.CONTENT,
            config=config,
        )
        if qtype != SurveyQuestion.QuestionType.CONTENT:
            apply_payload_tags(
                organization=survey.organization, survey_question=row, payload=question, user=user
            )
        created.append(row)
    return created


def append_survey_questions(
    survey: Survey, question_payloads: list[dict], *, user=None
) -> list[SurveyQuestion]:
    max_order = (
        survey.questions.order_by("-order").values_list("order", flat=True).first()
    )
    return create_survey_questions(
        survey, question_payloads, base_order=(max_order or 0) + 1, user=user
    )
