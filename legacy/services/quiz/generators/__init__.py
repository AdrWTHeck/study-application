"""Rule-based question generators — shared NLTK bootstrap."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_nltk_ready = False


def ensure_nltk() -> bool:
    """Download NLTK resources needed by the generators (idempotent).

    Handles both current resource names (punkt_tab,
    averaged_perceptron_tagger_eng) and legacy names so the code works
    across NLTK 3.7–3.9+.
    """
    global _nltk_ready
    if _nltk_ready:
        return True
    try:
        import nltk

        _downloads = [
            ("punkt_tab", "tokenizers/punkt_tab", "punkt"),
            ("averaged_perceptron_tagger_eng",
             "taggers/averaged_perceptron_tagger_eng",
             "averaged_perceptron_tagger"),
        ]
        for primary, path, fallback in _downloads:
            try:
                nltk.data.find(path)
            except LookupError:
                try:
                    nltk.download(primary, quiet=True)
                except Exception:
                    nltk.download(fallback, quiet=True)

        _nltk_ready = True
        return True
    except Exception:
        logger.warning("NLTK bootstrap failed; generators will be unavailable.")
        return False
