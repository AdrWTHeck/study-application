"""Fill-in-the-blank question generator — rule-based, NLTK NP chunking."""
from __future__ import annotations

import logging
import re

from . import ensure_nltk
from .base_generator import BaseGenerator

logger = logging.getLogger(__name__)

_MIN_SENTENCE_TOKENS = 6
_MAX_ANSWER_WORDS = 5


class FillBlankGenerator(BaseGenerator):
    """Replaces the most salient noun phrase in each sentence with a blank.

    Prefers proper-noun phrases; falls back to the longest common NP.
    Skips sentences shorter than _MIN_SENTENCE_TOKENS tokens.
    """

    _GRAMMAR = r"NP: {<DT>?<JJ>*<NNP>+|<DT>?<JJ>*<NN.*>+}"

    def generate(self, segment: str) -> list[dict]:
        if not ensure_nltk():
            return []
        try:
            from nltk.tokenize import sent_tokenize, word_tokenize
            from nltk import pos_tag, RegexpParser
        except ImportError:
            logger.warning("NLTK not importable; FillBlankGenerator skipped.")
            return []

        chunker = RegexpParser(self._GRAMMAR)
        results: list[dict] = []

        for sentence in sent_tokenize(segment):
            sentence = sentence.strip()
            tokens = word_tokenize(sentence)
            if len(tokens) < _MIN_SENTENCE_TOKENS:
                continue

            tagged = pos_tag(tokens)
            tree = chunker.parse(tagged)

            candidates: list[tuple[str, bool, int]] = []
            for subtree in tree.subtrees(filter=lambda t: t.label() == "NP"):
                leaves = subtree.leaves()
                n = len(leaves)
                if not (1 <= n <= _MAX_ANSWER_WORDS):
                    continue
                phrase = " ".join(w for w, _ in leaves)
                has_proper = any(tag.startswith("NNP") for _, tag in leaves)
                candidates.append((phrase, has_proper, n))

            if not candidates:
                continue

            # Proper nouns first, then longest phrase
            candidates.sort(key=lambda x: (not x[1], -x[2]))
            target, _, _ = candidates[0]

            blank_q = sentence.replace(target, "___", 1)
            if blank_q == sentence:
                blank_q = re.sub(re.escape(target), "___", sentence, count=1,
                                 flags=re.IGNORECASE)
            if blank_q == sentence:
                continue

            results.append({
                "question_text": blank_q,
                "answer": target,
                "type": "fill_blank",
                "distractors": None,
            })

        return results

    def generator_type(self) -> str:
        return "rule_based"
