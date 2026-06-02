"""Multiple-choice question generator — matches "X is/are Y" definition sentences."""
from __future__ import annotations

import logging
import re

from config.constants import MCQ_MIN_DISTRACTORS, MCQ_TARGET_DISTRACTORS
from . import ensure_nltk
from .base_generator import BaseGenerator

logger = logging.getLogger(__name__)

# Matches sentences of the form "SUBJECT is/are/was/were/means/refers to PREDICATE"
_DEF_RE = re.compile(
    r"^(.+?)\s+(?:is|are|was|were|refers?\s+to|means?)\s+(.+)$",
    re.IGNORECASE,
)
_MAX_SUBJECT_WORDS = 6
_MIN_PREDICATE_WORDS = 3
_NP_GRAMMAR = r"NP: {<DT>?<JJ>*<NN.*>+}"


class MCQGenerator(BaseGenerator):
    """Generates MCQ questions from definition-pattern sentences.

    Correct answer: the predicate of the definition.
    Distractors: other NPs extracted from the same segment.
    Discarded if fewer than MCQ_MIN_DISTRACTORS distinct distractors exist.
    """

    def generate(self, segment: str) -> list[dict]:
        if not ensure_nltk():
            return []
        try:
            from nltk.tokenize import sent_tokenize, word_tokenize
            from nltk import pos_tag, RegexpParser
        except ImportError:
            logger.warning("NLTK not importable; MCQGenerator skipped.")
            return []

        distractor_pool = self._extract_nps(segment, word_tokenize, pos_tag,
                                            RegexpParser)
        results: list[dict] = []
        for sentence in sent_tokenize(segment):
            q = self._make_mcq(sentence.strip(), distractor_pool)
            if q:
                results.append(q)
        return results

    def _make_mcq(self, sentence: str, pool: list[str]) -> dict | None:
        m = _DEF_RE.match(sentence.rstrip("."))
        if not m:
            return None
        subject = m.group(1).strip()
        predicate = m.group(2).strip().rstrip(".")
        if len(subject.split()) > _MAX_SUBJECT_WORDS:
            return None
        if len(predicate.split()) < _MIN_PREDICATE_WORDS:
            return None

        lower_pred = predicate.lower()
        lower_subj = subject.lower()
        distractors = [
            np for np in pool
            if np.lower() not in (lower_pred, lower_subj)
            and len(np.split()) >= 2
        ][:MCQ_TARGET_DISTRACTORS]

        if len(distractors) < MCQ_MIN_DISTRACTORS:
            return None

        return {
            "question_text": f"What is {subject}?",
            "answer": predicate,
            "type": "mcq",
            "distractors": distractors,
        }

    @staticmethod
    def _extract_nps(text: str, word_tokenize, pos_tag, RegexpParser) -> list[str]:
        chunker = RegexpParser(_NP_GRAMMAR)
        tagged = pos_tag(word_tokenize(text))
        tree = chunker.parse(tagged)
        seen: set[str] = set()
        nps: list[str] = []
        for subtree in tree.subtrees(filter=lambda t: t.label() == "NP"):
            phrase = " ".join(w for w, _ in subtree.leaves())
            if phrase not in seen:
                seen.add(phrase)
                nps.append(phrase)
        return nps

    def generator_type(self) -> str:
        return "rule_based"
