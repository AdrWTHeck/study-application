# config/constants.py
# All configurable values for the Study Application.
# No magic numbers anywhere else in the codebase (FR-INF-04).

# ---------------------------------------------------------------------------
# Answer evaluation
# ---------------------------------------------------------------------------
FUZZY_ACCEPT_THRESHOLD: int = 80    # score >= this → correct
FUZZY_HINT_THRESHOLD: int = 60      # score in [hint, accept) → "Did you mean?"

# ---------------------------------------------------------------------------
# Dictionary search
# ---------------------------------------------------------------------------
DICTIONARY_FUZZY_THRESHOLD: int = 75

# ---------------------------------------------------------------------------
# Text segmentation
# ---------------------------------------------------------------------------
MIN_SEGMENT_WORD_COUNT: int = 8     # segments below this are discarded

# ---------------------------------------------------------------------------
# Text cleaning patterns (regex strings applied during PDF extraction)
# ---------------------------------------------------------------------------
CLEANING_PATTERNS: list[str] = [
    r"^\d+$",           # lone page numbers
    r"^Page \d+ of \d+$",
    r"\s{3,}",          # excessive whitespace
]

# ---------------------------------------------------------------------------
# Database backups
# ---------------------------------------------------------------------------
ROLLING_BACKUP_COUNT: int = 2

# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------
AUDIO_FORMAT: str = "wav"
AUDIO_MAX_DURATION_SECONDS: int = 300

# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------
TTS_DEFAULT_RATE: int = 150         # words per minute

# ---------------------------------------------------------------------------
# Font size
# ---------------------------------------------------------------------------
FONT_SIZE_MIN: int = 10
FONT_SIZE_MAX: int = 24
FONT_SIZE_STEP: int = 2
FONT_SIZE_DEFAULT: int = 12

# ---------------------------------------------------------------------------
# Dictionary panel
# ---------------------------------------------------------------------------
DICTIONARY_SHORTCUT_DEFAULT: str = "Ctrl+D"

# ---------------------------------------------------------------------------
# MCQ generation
# ---------------------------------------------------------------------------
MCQ_MIN_DISTRACTORS: int = 2        # below this, question is discarded
MCQ_TARGET_DISTRACTORS: int = 3

# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------
PDF_RENDER_DPI: int = 150

# ---------------------------------------------------------------------------
# Card category — New step intervals (minutes)
# Step 0 = 1 min, step 1 = 10 min.
# Both fit within a session → 2 consecutive Goods possible in one session.
# ---------------------------------------------------------------------------
NEW_STEPS_MINUTES: list[int] = [1, 10]

# ---------------------------------------------------------------------------
# Card category — Learning step intervals (minutes)
# Step 0 = 1 day (1440 min), step 1 = 4 days (5760 min).
# ---------------------------------------------------------------------------
LEARNING_STEPS_MINUTES: list[int] = [1440, 5760]

# ---------------------------------------------------------------------------
# Card category — Graduation intervals
# ---------------------------------------------------------------------------
GRADUATING_INTERVAL_DAYS: int = 1   # first Review interval after Learning Good×2
EASY_GRADUATION_INTERVAL_DAYS: int = 4  # Review interval when Easy in Learning

# ---------------------------------------------------------------------------
# Card category — Review scheduling
# ---------------------------------------------------------------------------
HARD_INTERVAL_MULTIPLIER: float = 1.2
EASY_BONUS_MULTIPLIER: float = 1.3
EASE_FACTOR_MIN: float = 1.3
EASE_FACTOR_DEFAULT: float = 2.5
EASE_FACTOR_HARD_DELTA: float = -0.15
EASE_FACTOR_EASY_DELTA: float = 0.15

# ---------------------------------------------------------------------------
# Card session
# ---------------------------------------------------------------------------
AGAIN_REQUEUE_MINUTES: int = 10     # re-queue delay for Very Hard (Learning/Review)
NEW_CARDS_PER_SESSION: int = 20

# ---------------------------------------------------------------------------
# Test session
# ---------------------------------------------------------------------------
COMPREHENSIVE_TEST_MAX_QUESTIONS: int = 50

# ---------------------------------------------------------------------------
# Score bar chart thresholds (percent)
# ---------------------------------------------------------------------------
SCORE_BAR_GREEN_THRESHOLD: int = 70
SCORE_BAR_AMBER_THRESHOLD: int = 40
