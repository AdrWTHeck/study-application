"""Render a card template + field values to an HTML fragment for QTextBrowser.

Supports ``{{Field}}`` substitution and ``{{cloze:Field}}`` for cloze fields,
whose values contain ``{{c1::answer::hint}}`` markup. The front hides the answer
(showing the hint or ``[...]``); the back reveals it. Qt's rich-text engine
renders the HTML4/CSS2 subset — no browser engine needed.
"""
from __future__ import annotations

import html
import re

_PLACEHOLDER = re.compile(r"\{\{(cloze:)?([^}:]+)\}\}")
_CLOZE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.+?))?\}\}")


def _process_cloze(text: str, reveal: bool) -> str:
    def repl(match: re.Match) -> str:
        answer, hint = match.group(2), match.group(3)
        if reveal:
            return f"<b>[{html.escape(answer)}]</b>"
        return f"[{html.escape(hint)}]" if hint else "[...]"

    return _CLOZE.sub(repl, text)


def render_side(
    template_html: str,
    values: dict[str, str],
    *,
    css: str = "",
    reveal: bool = False,
) -> str:
    """Return an HTML fragment for one side of a card.

    ``reveal=False`` renders the front (cloze hidden); ``True`` the back.
    """

    def repl(match: re.Match) -> str:
        is_cloze = bool(match.group(1))
        name = match.group(2).strip()
        value = values.get(name, "")
        if is_cloze:
            return _process_cloze(value, reveal)
        return value

    body = _PLACEHOLDER.sub(repl, template_html)
    style = f"<style>{css}</style>" if css else ""
    return f'{style}<div class="card">{body}</div>'
