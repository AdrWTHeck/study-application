# Phase 6 — Feature Expansion (planning notes)

> Status: **planning + wiring in progress.** These features are to be built
> *before* image occlusion, FSRS, and the final quality pass. Each entry lists
> what it is, data-model impact, UI surface, accessibility notes, and scope.
> Recommended build order is in §0; independent/foundational items come first.

## 0. Recommended build order
1. **Note flags / labels** (§6.1) — foundational, self-contained, improves the card browser.
2. **Cramming deck** (§6.10) — self-contained, high value, reuses the review flow.
3. **Text / Markdown sources** (§6.4) — extends the Library/sources.
4. **Lyrics / Poetry cloze generator** (§6.5) — extends note creation.
5. **Comprehensive test split** (§6.9) — extends the testing module.
6. **Deadline tracker calendar** (§6.6) — new model + page; feeds dashboard.
7. **Achievements** (§6.8) — new model + screen; feeds dashboard.
8. **Pomodoro companion + diagnostic + encouragement** (§6.3) — large subsystem.
9. **Customizable dashboard widgets** (§6.7) — last, since it surfaces the others' data.
- **Media in cards** (§6.2) — future; pairs with image occlusion.

---

## 6.1 Note flags / labels (customizable, color-coded)
**What:** user-defined *status* flags on notes — e.g. Incomplete, Confusing
definition, Needs example, Wrong — each with a name + color, editable in
Settings. Distinct from the existing organizational tags (these are quality/work
flags). Shown as colored chips in the card/notes browser; filterable; assignable
via right-click.
**Data:** `NoteFlag(id, name, color, ordinal, is_builtin)` + `note_flags`(note_id,
flag_id) assoc. Seed defaults. (Reuses the chip styling from StateBadges.)
**UI:** Settings → "Note flags" editor (add / rename / recolor / delete).
Notes browser → flag chips + "Filter by flag" + right-click assign/remove.
**A11y:** chips carry text + color (never color alone, VIS-03); editor keyboard-navigable.
**Scope:** small-medium. *(Wiring started — data/service first.)*

## 6.2 Media in note cards (images / screenshots) — FUTURE
**What:** attach images to note fields; grid layout with auto-fitting. ("Needs
example" flag links here.)
**Data:** media files under app-data/media; reference stored in field value
(e.g. `[img:filename]`) or a `note_media` table. Rendering shows scaled images.
**Scope:** medium; pairs naturally with image occlusion. Deferred.

## 6.3 Pomodoro companion (timer + diagnostic + pet/tree + encouragement)
**What:** a study-session companion.
- **Pomodoro timer**: study/break cycles; configurable lengths.
- **Diagnostic sweep**: a sidebar panel (like the dictionary tab) that lists note
  fronts and asks a simple self-confidence question ("Confident with this?"
  — phrasing TBD). Used to bookend a session (start + end). Self-rating, not
  graded recall; feeds a lightweight confidence signal.
- **Companion growth**: a pet or tree whose appearance levels up with consistency
  (streak) and improving performance over time.
- **Encouragement**: randomized pool of premeditated responses (switch/case);
  adjustable phrase set + colors in Settings.
- **Feed animation**: after a completed session, feed the pet a cookie (eat +
  crumbs animation).
**Data:** `CompanionState(level, xp, kind, last_fed_at)`; encouragement phrase
list in settings; diagnostic results optionally logged.
**A11y:** companion/animations are decorative — never block flow; respect reduced
motion; encouragement is supportive, not pressuring.
**Scope:** large — break into: companion-state model → encouragement → diagnostic
sweep → pomodoro integration → animations (last).

## 6.4 Text & Markdown files as standalone notes/sources
**What:** import `.txt` / `.md` as a standalone source/note. Parse structure
markers (`[]`, `""`, `**`, `//`, `/* */`, `;`, `?`) to segment/format — to be
refined. Later: auto-generate questions from the parsed structure.
**Data:** extend `SourceDocument` to accept text/markdown (a `kind` field:
pdf | text | markdown); a markdown/text extractor parallel to the PDF one.
**UI:** Library "Import text/markdown"; reader renders markdown (Qt rich text).
Organization options reuse §6.1/source tags.
**Scope:** medium.

## 6.5 Lyrics / Poetry cloze generator
**What:** paste a poem, lyrics, or speech → generate a cloze study deck.
Each line becomes a prompt whose cloze hides the **next** line (line-completion
drill). Configurable clozes per line. Weak lines surface quickly via SRS.
**Data:** uses the existing **Cloze** note type; a generator splits on lines and
builds cloze notes (`{{c1::next line}}`).
**UI:** Cards → "Generate from text" → paste box + options (lines per question)
→ creates a deck.
**Scope:** small-medium.

## 6.6 Deadline tracker calendar (real exams)
**What:** a calendar page for exam deadlines. Assign decks to a deadline; compute
**daily study targets** (cards/reviews per day to finish by the date); adapt to
new cards, reviews done, skipped days, and vacation ranges. Show progress in the
Deck Browser, Dashboard, and Review screen. Smart sorting + a focus mode.
**Goal:** fast/easy date setting + deck tracking for deadlines.
**Data:** `Deadline(id, name, date, focus)`, `deadline_decks`(deadline, deck),
`vacation_days`; a target-computation service (remaining work ÷ days left,
skipping vacations).
**UI:** new "Calendar" surface (nav item or under Dashboard); per-deck target
badges; review-screen "X to stay on track".
**Scope:** large (model + scheduling math + multiple UI touch-points).

## 6.7 Customizable dashboard widgets (grid)
**What:** a grid dashboard with movable/resizable widgets, with a simple default
board. Widgets: sticky note (text), bar graph (most-studied decks + time), recent
test results, pie (cards by category/state), recent achievement, quick functions,
soonest deadline, tests due, login/streak tracker.
**Data:** dashboard layout config (widget list + positions/sizes) in settings; a
widget framework (each widget = a small QWidget with a data feed).
**A11y:** keyboard-reorderable; each widget labeled; simplified default in
Accessibility-First mode.
**Scope:** large — do last (depends on achievements §6.8, deadlines §6.6, stats).

## 6.8 Achievement screen
**What:** medals / cats / quotes / albums. Each achievement = a representative
symbol (trophy) + a title + a mini descriptor. Unlocked by milestones (streaks,
totals, scores, retention).
**Data:** `Achievement(id, code, title, descriptor, symbol, unlocked_at)`;
unlock-evaluation service run after sessions.
**UI:** Achievements screen (grid of earned/locked); dashboard "recent
achievement" widget.
**Scope:** medium.

## 6.9 Comprehensive test split
**What:** select **multiple test decks** → one combined session that reveals your
weakest area, ending with a **bar graph** of understanding per deck/category.
**Data:** reuses questions/results; a multi-deck session + per-deck/category
score aggregation. (Score bar chart component needed.)
**UI:** Tests → "Comprehensive test" → pick decks → quiz → category bar-graph
results.
**Scope:** medium.

## 6.10 Cramming deck (no-tracking copy)
**What:** for a card deck, start a **cram session** on a temporary copy with **no
SRS tracking**. Rudimentary structure: **Pass / Fail / Retry** — Retry sends the
card back into the queue (≈10 cards back). Nothing is persisted to the real
cards' scheduling.
**Data:** none persisted — an in-memory cram controller over a snapshot of the
deck's cards.
**UI:** Cards → deck → "Cram" → simple pass/fail/retry review; ends with a quick
summary. Reuses the review screen styling.
**A11y:** clearly labeled as practice that doesn't affect scheduling.
**Scope:** small-medium.
