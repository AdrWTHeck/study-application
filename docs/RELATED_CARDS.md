# Related Cards — difficult test questions guide card review

A Phase-5 follow-on feature (deferred from Search). When a learner gets a test
question **wrong** (or scores low), the FTS5 search index is used to find the
note cards that teach the same material, and they are **surfaced** after the quiz
as "related cards to review". Optionally — and only on explicit consent — those
cards can be brought forward in the review queue.

## Why (thesis alignment)

This is the accessibility-first redesign's answer to "what do I study next?" —
instead of leaving the learner to figure out which cards relate to a question
they keep missing, the app guides them (COG-01: one clear next step; reduces the
cognitive load of self-directed remediation). It deliberately **does not**
silently re-optimise the schedule behind the learner's back:

- **AUT-01 (learner autonomy).** Generated guidance is a *study aid, not a source
  of truth*. Suggestions are surfaced and clearly framed as optional. Changing
  the schedule is an explicit, per-action, confirmed opt-in — **never automatic**.
- **PRV-01 (offline).** Everything runs against the local SQLite FTS index; no
  network.

## How it works

### 1. Related-cards lookup (`SearchService.related_notes`)

The unified FTS5 index (`search_index`) already stores `note`, `question`, and
`source` rows. The lookup restricts to `content_type = 'note'`, matches a
prefix-OR query built from the question's terms, and orders by FTS5 `rank`
(bm25 — most relevant first). It returns at most `limit` notes and can exclude
note ids already surfaced (e.g. an exact source-card link).

A note generates one or more cards (Basic → 1, Basic+Reversed → 2); they share
the note's deck. So "related cards" is surfaced at the **note** level (one row,
with a preview + deck), and a reschedule nudge acts on *all* of that note's cards.

### 2. Policy (`domain/testing/related_cards.py`)

`RelatedCardsService` ties the quiz results, the search index, and the cards
together:

- **Struggle detection.** A `QuestionResult` is a struggle when it was marked
  incorrect **or** its score (0–100) is below `low_score_threshold` (default
  60). The default sits below the grading pass mark (80), so by default only
  wrong answers surface; raising the bar lets "barely correct" answers surface
  too (partial-credit-ready).
- **"Repeatedly wrong" signal.** `miss_count(question_id)` counts every
  incorrect result for a question across *all* sessions. Suggestions are sorted
  most-missed first, then lowest score, so the weakest spots float to the top.
- **Term mining.** From a question: its prompt + accepted answers + (for
  choice questions) the **correct** option text. Distractors are excluded so a
  wrong option can't drag in unrelated notes.
- **Exact link first.** If a question was generated from a card (the card→
  question bridge sets `source_card_id`), that card's note is surfaced first and
  flagged `is_source` — it is definitionally about the same material.
- **`suggestions_for_session(session_id)` is a pure read.** It returns
  `QuestionStruggle`s (each with its `RelatedCard`s) and changes nothing.

### 3. Reschedule — opt-in only (`nudge_cards_due_now`)

The deliberately conservative, reversible-feeling reschedule:

- Moves a card's `due` **earlier only** (never later — surfacing should never
  punish).
- **Skips New cards** (already surfaced in the queue).
- **Never** alters `ease_factor` / `interval_days` / `srs_state` / `reps` — it
  changes *when* a card next appears, not the memory model's record of how well
  it is known. When the learner next reviews it, SM-2 proceeds normally.
- Callers MUST gate it behind explicit consent. The Tests view requires a button
  press + a plain-language confirmation ("…this only moves them earlier… it
  doesn't change how well you've learned them…").

### 4. UI (`ui/views/tests_view.py` results page)

After a quiz, below the score/accuracy/history:

- A **"Related cards to review"** section (shown only when there are
  suggestions, and only if `related_cards_enabled` is on). Each struggled
  question lists its related cards with a preview, the owning deck, and an
  "Open in Cards" button. "missed N times" is shown as **text**, not colour
  alone (VIS-03).
- A single opt-in **"Bring N related cards to the front of my next review"**
  button (hidden when there's nothing to bring forward), which confirms before
  calling `nudge_cards_due_now`.

## Settings

- `related_cards_enabled` (default **on**) — show the surface-only suggestions
  after a test. The reschedule is opt-in per action regardless of this toggle.

## Tests

- `tests/test_related_cards.py` — lookup ranking, struggle detection, miss
  count, source-card link, the low-score path, the earlier-only nudge, and a
  test that suggesting changes **no** scheduling.
- `tests/test_related_cards_ui.py` — the results section appears on a miss,
  hides when disabled or on a perfect score, and the confirmed nudge reschedules.

## Possible later work

- Deep-link "Open in Cards" to the *specific* deck (the codebase's `navigate`
  callback currently jumps to the section, matching the Search view).
- A persistent "needs review" flag on cards (vs. only post-quiz surfacing).
- Weight `miss_count` into FSRS difficulty when the FSRS engine lands.
