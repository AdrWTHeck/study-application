from data.models import Question, QuestionAnswer, QuestionOption
from data.models.testing import MCQ, SHORT_ANSWER, TRUE_FALSE
from domain.testing.grading import grade


def _mcq():
    q = Question(type=MCQ, prompt="Capital of France?")
    q.options = [
        QuestionOption(text="Paris", is_correct=True),
        QuestionOption(text="London", is_correct=False),
    ]
    return q


def _short(answer="mitochondria"):
    q = Question(type=SHORT_ANSWER, prompt="Powerhouse of the cell?")
    q.answers = [QuestionAnswer(accepted_text=answer)]
    return q


def test_mcq_correct_and_incorrect():
    assert grade(_mcq(), "Paris") == (True, 100.0)
    assert grade(_mcq(), "London") == (False, 0.0)


def test_mcq_is_case_insensitive():
    assert grade(_mcq(), "  paris ")[0] is True


def test_true_false():
    q = Question(type=TRUE_FALSE)
    q.options = [QuestionOption(text="True", is_correct=True),
                 QuestionOption(text="False", is_correct=False)]
    assert grade(q, "True")[0] is True
    assert grade(q, "False")[0] is False


def test_short_answer_exact_normalized():
    assert grade(_short(), "Mitochondria ") == (True, 100.0)


def test_short_answer_far_miss_fails():
    assert grade(_short(), "nucleus", 80)[0] is False


def test_threshold_controls_strictness():
    # "mito" vs "mitochondria" ≈ 50% similarity.
    assert grade(_short(), "mito", 30)[0] is True
    assert grade(_short(), "mito", 90)[0] is False


def test_no_accepted_answers():
    q = Question(type=SHORT_ANSWER)
    q.answers = []
    assert grade(q, "anything") == (False, 0.0)
