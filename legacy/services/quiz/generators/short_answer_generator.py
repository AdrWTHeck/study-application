"""Short-answer question generator — targets definition, causal, and temporal sentences."""
from __future__ import annotations

import logging
import re

from . import ensure_nltk
from .base_generator import BaseGenerator

logger = logging.getLogger(__name__)

_MIN_TOKENS = 8
_CAUSE_WORDS = frozenset({
    "because", "since", "therefore", "thus", "hence", "consequently",
})
_YEAR_RE = re.compile(r"\b\d{4}\b")
_DEF_RE = re.compile(
    r"^(.+?)\s+(?:is|are|was|were|refers?\s+to|means?)\s+(.+)$",
    re.IGNORECASE,
)
_NP_GRAMMAR = r"NP: {<DT>?<JJ>*<NNP>+|<DT>?<JJ>*<NN.*>+}"


class ShortAnswerGenerator(BaseGenerator):
    """Produces free-text questions for three sentence patterns:

    1. Definition  — "What is X?"  answer = predicate
    2. Causal      — "Why is X significant?"  answer = full sentence
    3. Temporal    — "When did events related to X occur?"  answer = full sentence
    """

    def generate(self, segment: str) -> list[dict]:
        if not ensure_nltk():
            return []
        try:
            from nltk.tokenize import sent_tokenize, word_tokenize
            from nltk import pos_tag, RegexpParser
        except ImportError:
            logger.warning("NLTK not importable; ShortAnswerGenerator skipped.")
            return []

        chunker = RegexpParser(_NP_GRAMMAR)
        results: list[dict] = []

        for sentence in sent_tokenize(segment):
            sentence = sentence.strip()
            tokens = word_tokenize(sentence)
            if len(tokens) < _MIN_TOKENS:
                continue
            q = self._make_question(sentence, tokens, pos_tag, chunker)
            if q:
                results.append(q)
        return results

    def _make_question(self, sentence: str, tokens, pos_tag, chunker) -> dict | None:
        # Pattern 1: definition sentence — prefer this over other patterns
        m = _DEF_RE.match(sentence.rstrip("."))
        if m:
            subject = m.group(1).strip()
            predicate = m.group(2).strip().rstrip(".")
            if len(subject.split()) <= 5 and len(predicate.split()) >= 2:
                return {
                    "question_text": f"What is {subject}?",
                    "answer": predicate,
                    "type": "short_answer",
                    "distractors": None,
                }

        # Pattern 2: causal sentence
        lower = sentence.lower()
        if any(w in lower for w in _CAUSE_WORDS):
            subject = self._first_np(pos_tag(tokens), chunker)
            if subject:
                return {
                    "question_text": f"Why is {subject} significant in this context?",
                    "answer": sentence.rstrip(".") + ".",
                    "type": "short_answer",
                    "distractors": None,
                }

        # Pattern 3: temporal sentence containing a 4-digit year
        if _YEAR_RE.search(sentence):
            subject = self._first_np(pos_tag(tokens), chunker)
            if subject:
                return {
                    "question_text": f"When did events related to {subject} occur?",
                    "answer": sentence.rstrip(".") + ".",
                    "type": "short_answer",
                    "distractors": None,
                }

        return None

    @staticmethod
    def _first_np(tagged, chunker) -> str | None:
        tree = chunker.parse(tagged)
        for subtree in tree.subtrees(filter=lambda t: t.label() == "NP"):
            phrase = " ".join(w for w, _ in subtree.leaves()).strip()
            if phrase:
                return phrase
        return None

    def generator_type(self) -> str:
        return "rule_based"
