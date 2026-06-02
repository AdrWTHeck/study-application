from domain.notes.rendering import render_side


def test_basic_front_substitution():
    front = render_side("{{Front}}", {"Front": "Hello", "Back": "World"})
    assert "Hello" in front and "World" not in front


def test_basic_back_shows_both():
    back = render_side("{{Front}}<hr>{{Back}}", {"Front": "Hello", "Back": "World"})
    assert "Hello" in back and "World" in back


def test_cloze_front_hides_answer():
    front = render_side("{{cloze:Text}}", {"Text": "The {{c1::sun}} is hot"}, reveal=False)
    assert "[...]" in front and "sun" not in front


def test_cloze_back_reveals_answer():
    back = render_side("{{cloze:Text}}", {"Text": "The {{c1::sun}} is hot"}, reveal=True)
    assert "sun" in back


def test_cloze_hint_shown_on_front():
    front = render_side("{{cloze:Text}}", {"Text": "The {{c1::sun::star}} is hot"}, reveal=False)
    assert "[star]" in front and "sun" not in front
