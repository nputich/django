from api.models import Survey, SurveyQuestion


def append_survey_questions(survey: Survey, question_payloads: list[dict]) -> list[SurveyQuestion]:
    max_order = (
        survey.questions.order_by("-order").values_list("order", flat=True).first()
    )
    base_order = (max_order or 0) + 1
    created: list[SurveyQuestion] = []
    for index, question in enumerate(question_payloads):
        created.append(
            SurveyQuestion.objects.create(
                survey=survey,
                order=question.get("order", base_order + index),
                text=question["text"],
                question_type=question.get(
                    "question_type", SurveyQuestion.QuestionType.TEXT
                ),
                choices=question.get("choices", []),
            )
        )
    return created
