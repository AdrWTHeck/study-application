# Study App — Second Iteration Overhaul Plan

> Status: **Planning — awaiting sign-off.** No implementation has begun.
> Last updated: 2026-05-31

Clean-rebuild specification for the CS3801 final project: an **Accessibility-First
Redesign of Anki** (Adrian Perez-Gonzales + Kanishq Nileshbhai Viradiya). This is
a value-sensitive-design / ACM-ethics project — it is graded on *ethical reasoning
made visible in the software*, not just on features working. Every decision below
is checked against that mandate. Implementation does not start until this is
approved.

---

## 1. Vision & Ethical Mandate

The thesis is a deliberate critique of Anki: mainstream study tools prioritize
**efficiency and information density**, which raises barriers for visually
impaired, dyslexic, cognitively overloaded, elderly, and K-12 learners. This
redesign **prioritizes accessibility and inclusion over efficiency and density.**

Governing ethical commitments (ACM Code of Ethics — well-being, avoid harm, avoid
discrimination, autonomy), each mapped to a concrete build obligation:

| Commitment | Build obligation |
|---|---|
| Inclusion over speed/density | Fewer controls per screen; clearer spacing; **one task at a time**. |
| Accessibility is structural, not hidden | Surfaced at **first-run onboarding**; on by default — never buried in a settings menu only. |
| Privacy | **Local/offline storage only**; no cloud, no telemetry. Made visible to the user. |
| Learner autonomy | Any generated content is **editable and clearly labeled** as an aid, never a source of truth. |
| Don't exclude advanced users either | Power features are **preserved but separated** into an Advanced mode. |

Target users: visually impaired, dyslexic, attention-difficulty/cognitive-overload,
elderly, K-12 — explicitly **not** the expert/efficient user.

---

## 2. Dual-Mode Architecture (the governing design principle)

Quoted from the proposal: *"the system will preserve advanced options while keeping
them separate from the accessibility-first study flow."* This is the spine of the
whole app and resolves the tension between an accessibility-first default and the
powerful features chosen (full custom note types, richer views).

**Accessibility-First mode — the DEFAULT**
- Low-density, generously spaced, large targets.
- Guided, single-focus screens ("one task at a time") — wizard-style create/review flows.
- Only **preset note types** (Basic, Cloze) are exposed.
- Simplified Dashboard: one or two priorities, not a dense grid.
- TTS, high-contrast, font scaling, dyslexia-friendly options immediately reachable.

**Advanced mode — opt-in**
- Higher-density multi-pane views (the dense Dashboard mockup belongs here).
- **Custom note-type creation/editing**, card templates, bulk operations.
- Power keyboard shortcuts, batch tools.

Implementation: mode is a single setting that swaps **density token sets** (§8) and
toggles feature visibility. It is *not* two codebases — same views, mode-aware
composition. Mode is chosen during onboarding and switchable anytime.

---

## 3. Accessibility Requirements (core scope — NOT deferred)

> **Authoritative spec:** [`ACCESSIBILITY_INTEGRATION.md`](ACCESSIBILITY_INTEGRATION.md)
> operationalizes the proposal's accessibility intent into traceable, testable
> requirements (IDs, acceptance criteria, WCAG refs, phase mapping). The list below
> is the summary; that document directs the build.

These are rubric-required and treated as first-class deliverables, woven across all phases:

- **Text-to-speech for flashcards *and* interface elements** (read-focused-control, read-card).
- **Adjustable font scaling** (global, via tokens).
- **High-contrast themes — dark *and* light** (shipped, not deferred).
- **Dyslexia-friendly options**: font choice (e.g. OpenDyslexic/Atkinson), adjustable
  line-height and letter/word spacing.
- **Screen-reader compatibility**: Qt accessibility — every interactive widget gets an
  accessible name/role/description; correct focus order; full keyboard navigation.
- **Simplified interface mode** (= Accessibility-First default, §2).
- **First-run accessibility onboarding** that sets mode, theme, font scale, and TTS.
- **Visible privacy posture**: a plain-language "your data stays on this device" statement.

Accessibility is part of the **Definition of Done** for every view: keyboard-navigable,
screen-reader-labeled, contrast-checked, TTS-reachable.

---

## 4. Locked Decisions

| Area | Decision | Notes |
|------|----------|-------|
| Build approach | **Full clean rebuild** | Port ideas/logic (SM-2), not code. |
| UI stack | **PyQt6** | Native; offline; non-browser; PyInstaller exe. |
| **App structure** | **Dual mode: Accessibility-First default + Advanced opt-in** | §2 — the governing principle. |
| SRS algorithm | **SM-2** | Port engine; add review log (stats + future FSRS). |
| Deck organization | **Flat + tags + favorites + category + color** | No nesting. |
| Card ↔ Test | **Linked but separate; card→question bridge only** | User-initiated, editable, **clearly labeled** conversion. No bulk auto-generation. |
| Note model | **Full custom note types** | Presets (Basic/Cloze) in default flow; **custom type creation gated to Advanced mode**. |
| Card rendering | **Qt rich-text (HTML4/CSS2 subset)** | QTextDocument/QTextBrowser + `{{Field}}`, token-styled. No Chromium. |
| Theme/token system | **Full design-token system** | Adds **density** and **contrast** axes (§8). |
| Themes shipped | **Dark + Light + High-contrast (dark & light) + custom** | High-contrast is **core**, not deferred. |
| Search | **FTS5 full-text + in-PDF Ctrl+F** | Unified index. |
| Dictionary | **Wiktionary (kaikki.org), built on first launch** | Prefix + FTS5; WordNet fallback. Not committed (OneDrive). |
| Testing | **pytest alongside each phase** + accessibility checks | |
| Packaging | **PyInstaller, one-folder** | Writable app-data dir; **fully local/offline**. |
| Existing data | **Fresh DB** | Old DB is scratch data only. |

### Removed from the previous iteration
- **Bulk/auto** question generation from PDF text (replaced by the labeled, editable card→question bridge).
- Fuzzy dictionary lookup (prefix + FTS; fuzzy only for short-answer grading).
- Hardcoded fonts/colors/spacing in per-view stylesheets.

---

## 5. Navigation (5 destinations)

1. **Dashboard** — simplified by default (top priorities + quick actions); dense grid in Advanced.
2. **Library** — PDF sources: viewer, highlights, bookmarks, notes, dictionary, highlight→card, in-PDF find.
3. **Cards** — notes/decks, card browser with SRS state badges, guided review.
4. **Tests** — test decks, manual question creation, quiz sessions, results/history.
5. **Search** — app-wide full-text (Ctrl+F global).

Settings reachable from sidebar bottom. Nav adapts to density tokens (larger targets/labels in Accessibility-First). A **first-run onboarding** precedes the first Dashboard view.

---

## 6. Target Project Structure

```
study application/
├── main.py                      # thin entry point
├── requirements.txt
├── app/
│   ├── main_window.py           # shell: sidebar + topbar + routed stack
│   ├── navigation.py            # 5-destination router
│   └── onboarding.py            # first-run accessibility setup flow
├── core/
│   ├── paths.py                 # app-data dir (frozen vs source)
│   ├── settings.py              # observable settings incl. mode/density/a11y
│   ├── startup.py               # dirs, engine, WAL, integrity, backup (ported)
│   ├── backup.py
│   └── events.py
├── data/
│   ├── db.py
│   ├── models/                  # ORM models (§7)
│   ├── repositories/
│   └── schema.py
├── domain/
│   ├── srs/                     # SM-2 engine, scheduler, review log
│   ├── notes/                   # note types, fields, templates, card gen, render
│   ├── decks/                   # deck/tag/favorite management
│   ├── testing/                 # quiz build, session, scoring, retest, card→question
│   ├── sources/                 # PDF ingest, extraction, render, highlights, notes
│   ├── search/                  # FTS index + query, in-PDF find
│   ├── dictionary/              # Wiktionary build + lookup
│   └── accessibility/           # TTS (UI + content), audio, a11y helpers
├── ui/
│   ├── theme/                   # tokens.py, theme_controller.py, qss_builder.py
│   ├── a11y/                    # accessible-widget helpers, focus/keyboard utils
│   ├── components/              # reusable widgets (mode-aware)
│   └── views/                   # dashboard, library, cards, tests, search, settings, onboarding
├── assets/                      # icons, fonts (dyslexia-friendly), seed note types, token sets
├── tools/                       # dictionary build script, dev utilities
├── tests/                       # pytest, incl. accessibility assertions
└── user_data/ (runtime only)    # DB, audio, backups, settings.json, wiktionary.db
```

---

## 7. Data Model (SQLite via SQLAlchemy)

### Note / Card system (Anki-style)
- **note_types**(id, name, css, is_builtin, created_at)
- **fields**(id, note_type_id, name, ordinal)
- **card_templates**(id, note_type_id, name, front_html, back_html, ordinal)
- **notes**(id, note_type_id, deck_id, created_at, modified_at)
- **note_field_values**(id, note_id, field_id, value) — normalized for query/FTS
- **cards**(id, note_id, template_id, deck_id, state[new|learning|review],
  ease_factor, interval, repetitions, lapses, learning_step_index, due_date, last_reviewed_at)
- **review_log**(id, card_id, rating, prev/new interval, prev/new ease, time_ms, reviewed_at)

Seed note types: **Basic**, **Basic + Reversed**, **Cloze** (Image Occlusion deferred).
Preset types are exposed in default mode; creating/editing types is Advanced-only.

### Decks & tags (flat)
- **decks**(id, name, type[card|test], is_favorite, category, color, created_at, modified_at)
- **tags**(id, name) · **note_tags**(note_id, tag_id) · **deck_tags**(deck_id, tag_id)

### Testing
- **questions**(id, deck_id, type[mcq|short_answer|fill_blank|true_false], prompt,
  explanation, source_card_id?, is_generated_draft[bool], created_at)
  — `source_card_id` + `is_generated_draft` implement the labeled, editable card→question bridge.
- **question_options**(id, question_id, text, is_correct, ordinal)
- **question_answers**(id, question_id, accepted_text)
- **quiz_sessions**(id, deck_id, status, settings_json, started_at, finished_at)
- **question_results**(id, session_id, question_id, user_response, is_correct, score, time_ms, answered_at)

### Sources / PDF
- **source_documents**(id, title, file_path, page_count, last_opened_page, last_opened_at, notes_text, created_at)
- **text_segments**(id, source_id, page, ordinal, kind[heading|body], text, bbox)
- **highlights**(id, source_id, page, quads_json, color, text, created_at)
- **bookmarks**(id, source_id, page, label, created_at)
- **deck_sources**(deck_id, source_id)

### Search & stats
- **search_index** — FTS5(content_type, content_id, title, body), maintained on writes.
- **daily_activity**(date, cards_reviewed, tests_taken, study_seconds) — streak from contiguous dates.

### Dictionary (`wiktionary.db` in app-data, built on first launch)
- **entries**(id, word, pos) · **senses**(entry_id, gloss, examples); index on `word`
  (prefix), FTS5 on `gloss`. Selective fields; optional zlib on long text. WordNet fallback.

### Accessibility state (settings.json, not DB)
- mode (accessibility|advanced), density, theme (incl. high-contrast), font_scale,
  font_family (dyslexia option), line_height, letter/word_spacing, tts_ui_enabled,
  tts_content_enabled, tts_rate/voice, onboarding_complete, short_answer_fuzzy_threshold.

---

## 8. Design-Token System (anti-drift + accessibility engine)

One source of truth that also powers the accessibility features.

- **tokens.py** — semantic tokens across axes:
  - *color* (semantic roles) — with **standard** and **high-contrast** palettes.
  - *typography* (family incl. dyslexia-friendly, size steps × **font_scale**, line-height, spacing).
  - *spacing & sizing & radii* — with **comfortable (accessibility)** vs **compact (advanced)** density sets.
- **theme_controller.py** — holds active palette + density + typography; applies user
  overrides; emits a change signal. Mode/contrast/scale are token-set swaps.
- **qss_builder.py** — compiles tokens → one global Qt stylesheet; widgets reference
  tokens via objectName/property selectors, never hardcoded values.
- Contrast palettes are checked against WCAG AA contrast ratios.

---

## 9. Phase Plan

Definition of Done per phase: working feature **+** pytest coverage **+** accessibility
pass (keyboard nav, screen-reader labels, contrast, TTS reachability) **+** an
HTML/Qt mockup sign-off for any new view (Accessibility-First variant first).

### Phase 1 — Foundation & Accessibility Spine
- Project skeleton; app-data paths (frozen vs source).
- DB engine/session, base repository, schema bootstrap; ported startup/backup/WAL/integrity.
- Design-token system + ThemeController + QSS builder, incl. **density + high-contrast axes**.
- Settings model/persistence + Settings view (mode, theme incl. high-contrast, font scale,
  dyslexia font, spacing, TTS UI/content, short-answer fuzzy threshold, default timer).
- **First-run accessibility onboarding** (mode, theme, font scale, TTS).
- `ui/a11y/` helpers; TTS service (UI + content); screen-reader labeling conventions established.
- Main window shell: 5-destination sidebar + topbar + routed empty views, mode-aware.
- Dictionary: kaikki ingestion/build + lookup (prefix + FTS), WordNet fallback, Settings hook.
- *Tests:* settings persistence, token→QSS (incl. contrast/density), onboarding state, dict build/lookup, a11y label presence.

### Phase 2 — Note Cards
- Note-type system + seed presets; **custom type creation/editing gated to Advanced mode**.
- Note CRUD + card generation + Qt rich-text rendering (TTS-readable, scalable).
- Deck management: flat + tags + favorites + category + color; live-updating lists.
- Card browser: New/Learning/Review badges + counts; right-click CRUD; bulk ops (Advanced).
- SM-2 engine port + scheduler + review_log; **guided one-card-at-a-time** review with rating buttons + TTS.
- *Tests:* SM-2 transitions, card generation, count aggregation, deck/tag CRUD, review keyboard/TTS path.

### Phase 3 — PDF / Sources
- PDF viewer: render, zoom, fit, **scroll/page position save+restore**.
- Improved extraction: split on heading patterns + whitespace gaps → segments (readable spacing).
- Highlights (persist, color, erase) + bookmarks.
- Notes panel: per-source, **debounced auto-save**, append-from-dictionary.
- Dictionary panel (prefix search; no fuzzy); TTS on definitions.
- **Highlight → right-click → Create Note** (pre-filled; deck + preset note-type picker; cloze).
- **In-PDF Ctrl+F** find.
- Remove bulk auto question generation.
- *Tests:* extraction segmentation, highlight persistence, note autosave, find, keyboard access.

### Phase 4 — Testing Module
- Test deck management (shared deck system).
- Manual question creation/editor (mcq/short/fill-blank/true-false).
- **Card→question bridge**: one-click, produces an **editable draft clearly labeled** as generated.
- Quiz session: session + per-question timer (configurable); guided navigation; TTS prompts.
- Scoring incl. fuzzy short-answer matching (threshold from Settings).
- **Failed-question retest** mini-session.
- Results: score bar chart, time-per-question, accuracy by type; **history trend** per deck.
- *Tests:* scoring, fuzzy threshold, retest seeding, draft labeling, stats aggregation.

### Phase 5 — Dashboard & Search
- FTS5 unified index + maintenance across notes/questions/PDF text/source notes.
- Global Search view + app-wide Ctrl+F; navigate results to card/question/source.
- Dashboard: **simplified default** (top priorities + quick actions) and **dense Advanced variant**
  (due-today, new cards, deck-health, recent tests, activity graph, streak).
- daily_activity rollup + streak computation.
- *Tests:* FTS query correctness, streak/rollup logic, dashboard mode switch.

### Cross-cutting (continuous; finalized near the end)
- PyInstaller one-folder; verify PyMuPDF/PyAudio/spaCy/NLTK bundling + app-data writability when frozen.
- Visible privacy statement; confirm zero network calls except the one-time dictionary build.
- Accessibility regression checks each phase.

---

## 10. Open Items / To Revisit
- Image Occlusion note type — deferred; revisit after Phase 2.
- FSRS — out of scope; review_log keeps the door open.
- OCR for scanned PDFs — proposal lists as a *later* iteration; out of initial scope.
- Compiled (C/Rust) dictionary helper — only if Python profiling demands it.

---

## 11. Mockups
HTML previews (served from `mockups/`) for layout sign-off before each PyQt6 view.
For every view, the **Accessibility-First (default) variant is designed first**, then the
Advanced variant. The existing dense Dashboard mockup represents the **Advanced** variant;
a simplified default Dashboard mockup is still to be made.
