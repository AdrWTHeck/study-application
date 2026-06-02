# Accessibility Integration Plan

> Status: **Planning — awaiting sign-off.**
> Last updated: 2026-05-31
> Source of intent: `final project- cs3801-1.pdf` (the proposal). Companion to
> [`OVERHAUL_PLAN.md`](OVERHAUL_PLAN.md).

This document **operationalizes the accessibility intent written in the proposal.**
Every requirement below traces to a specific statement in the PDF, then becomes a
concrete integration decision with testable acceptance criteria. The proposal is
the director; this is the execution spec.

Where the proposal states an *intent* but not a *mechanism*, the chosen mechanism is
marked **[impl choice]** so it can be redirected.

---

## 1. Directing Principles (from the proposal)

These five quotes set the non-negotiable frame. Everything else serves them.

1. **Accessibility-first, not an add-on.**
   > *"a redesign of Anki into an accessibility-first study application, rather than an
   > add-on or a menu of hidden settings."*
   → Accessibility is the **default structure**, surfaced at setup, on by default.

2. **Inclusion over efficiency and density.**
   > *"the system prioritizes accessibility over UI density and efficiency … users may
   > see fewer elements on screen at once and may navigate more slowly, but the system
   > becomes more equitable."*
   → Slower/sparser is an **accepted, intended tradeoff**, not a regression.

3. **Plan it from the beginning.**
   > *"plan accessibility from the beginning, because retrofitting it later is usually
   > more difficult and more likely to produce incomplete support."*
   → Accessibility lands in **Phase 1**, and is in the Definition of Done for every view.

4. **Preserve advanced users without re-excluding them.**
   > *"preserve advanced options while keeping them separate from the accessibility-first
   > study flow."*
   → Dual mode (see OVERHAUL_PLAN §2). Power features never intrude on the default flow.

5. **Autonomy + privacy as accessibility-adjacent ethics.**
   > *"generated content should be editable, clearly labeled … a study aid rather than a
   > source of truth"* and *"local storage and offline processing."*
   → No bulk generation; labeled editable drafts only. Fully local/offline, stated plainly.

---

## 2. User Groups → Barriers → Integration

The proposal names the people this is *for*. Each row: the group, the barrier it quotes,
and how the build answers it.

| Group (named in PDF) | Barrier (quoted/paraphrased) | Integration response |
|---|---|---|
| **Visually impaired** | *"struggle to read small text or low-contrast screens"* | Font scaling, high-contrast themes (dark+light), full TTS, screen-reader labeling. |
| **Dyslexic / reading difficulty** | *"may need font adjustments, spacing, or text-to-speech support"* | Dyslexia-friendly font option, adjustable line/letter/word spacing, TTS on all content. |
| **Cognitive overload / attention** | *"discouraged by the overwhelming amount of buttons, menus, and organizational decisions"* | Accessibility-First default: fewer controls per screen, one task at a time, reduced choices, advanced complexity hidden. |
| **Elderly** | *"benefit from flashcards but find the interface too technical"* | Large targets, plain navigation, guided flows, generous spacing, no jargon. |
| **K-12 / younger** | *"may not know how to structure decks or use spaced repetition properly"* | In-context guidance, sensible defaults, guided deck/card creation; SRS works without configuration. |
| **Overwhelmed students** | *"already overwhelmed by schoolwork"* | Low-friction defaults; nothing required to configure before studying. |
| **Motor / keyboard-reliant** | implied by screen-reader + *"navigate more slowly"* | Full keyboard operability, visible focus, no time-pressure required. |

---

## 3. Accessibility Requirements (traceable, testable)

Grouped by pillar. Each has an ID, the proposal basis, the integration, acceptance
criteria, the relevant WCAG 2.1 reference **[impl choice: target level AA]**, and the
phase it lands in.

### VIS — Vision / Low-vision

**VIS-01 — Adjustable font scaling**
- Basis: *"Adjustable font scaling for readability."*
- Integration: global `font_scale` token multiplies every type step; all layouts use
  relative spacing so text never clips or overlaps when scaled. Reachable from onboarding,
  Settings, and a quick control.
- Acceptance: at max scale, no view clips, truncates, or overlaps; reflow only. Min range
  ~100%–200%. (WCAG 1.4.4 Resize Text, 1.4.10 Reflow)
- Phase: 1

**VIS-02 — High-contrast themes (dark & light)**
- Basis: *"High contrast visual themes for better visibility."*
- Integration: dedicated high-contrast token palettes (not just darker neutrals); selectable
  at onboarding/Settings.
- Acceptance: text vs background ≥ 7:1 (AAA target for HC themes), UI/focus indicators ≥ 3:1;
  verified with a contrast check in tests. (WCAG 1.4.3/1.4.6/1.4.11)
- Phase: 1

**VIS-03 — No information by color alone**
- Basis: inclusive-visibility intent (low-vision/color-vision).
- Integration: SRS state badges, correctness, and status use icon/text + color, never color only.
- Acceptance: every state distinguishable in grayscale. (WCAG 1.4.1)
- Phase: 2+ (each view)

### RDG — Reading / Dyslexia

**RDG-01 — Dyslexia-friendly font option**
- Basis: *"users with dyslexia … may need font adjustments."*
- Integration: selectable font family incl. a dyslexia-oriented face **[impl choice: bundle
  OpenDyslexic or Atkinson Hyperlegible]**, applied globally via tokens.
- Acceptance: font switches app-wide live (no restart); bundled offline.
- Phase: 1

**RDG-02 — Adjustable spacing**
- Basis: *"font adjustments, spacing."*
- Integration: user-adjustable line-height and letter/word spacing tokens.
- Acceptance: spacing controls affect all text; layouts reflow without overlap.
  (WCAG 1.4.12 Text Spacing)
- Phase: 1

**RDG-03 — Plain language & readable extraction**
- Basis: *"clearer spacing,"* readable-by-default study screens.
- Integration: PDF text extraction splits on headings + whitespace so study text is spaced,
  not a wall (OVERHAUL_PLAN Phase 3); UI copy avoids jargon.
- Acceptance: extracted segments preserve structure; review screens are single-column, spaced.
- Phase: 3

### COG — Cognitive load / Attention

**COG-01 — One task at a time (guided flows)**
- Basis: *"guides the user through one task at a time."*
- Integration: Accessibility-First default uses single-focus screens / wizard-style
  create + review flows; no dense multi-pane unless Advanced.
- Acceptance: in default mode, each primary screen presents one main action; review shows one
  card at a time with clear next-step.
- Phase: 2 (review), 4 (test), 5 (dashboard)

**COG-02 — Reduced controls per screen**
- Basis: *"shows fewer controls at once,"* *"reduces clutter and cognitive load."*
- Integration: default mode hides advanced/bulk controls; secondary actions tucked behind
  clear, labeled affordances.
- Acceptance: default screens stay within a deliberate control budget; advanced tools only in Advanced mode.
- Phase: all view phases

**COG-03 — Sensible zero-config defaults & guidance**
- Basis: novices *"may not know how to structure decks or use spaced repetition."*
- Integration: SRS works with no setup; deck/card creation is guided with inline help;
  first card/deck creation offers a gentle walkthrough.
- Acceptance: a new user can create and review a card without opening Settings or docs.
- Phase: 2

### SR — Screen-reader compatibility

**SR-01 — Accessible names/roles on every interactive element**
- Basis: *"Improved compatibility with screen readers."*
- Integration: `ui/a11y/` conventions set `accessibleName`/`accessibleDescription` and proper
  roles on all controls; cards expose readable text to the a11y tree.
- Acceptance: a screen reader announces a meaningful name + role for every focusable control.
  (WCAG 4.1.2 Name, Role, Value)
- Test: **[impl choice]** NVDA + Windows Narrator passes on each view.
- Phase: 1 conventions; enforced every view

**SR-02 — Logical focus order & status announcements**
- Basis: assistive-interaction-by-default intent.
- Integration: deliberate tab order; live-region-style announcements for state changes
  (e.g., "Correct", "Card 3 of 20", "Saved").
- Acceptance: tab order matches visual/logical order; key status changes are announced.
  (WCAG 2.4.3, 4.1.3)
- Phase: each view

### KBD — Keyboard / Motor

**KBD-01 — Full keyboard operability**
- Basis: screen-reader + *"navigate more slowly"* (no reliance on speed/precision).
- Integration: every action reachable by keyboard; review ratings, nav, dialogs all keyable;
  global Ctrl+F search.
- Acceptance: a full study session (create → review → test) completes mouse-free.
  (WCAG 2.1.1 Keyboard)
- Phase: each view

**KBD-02 — Visible focus & adequate target size**
- Basis: elderly/low-vision/motor inclusion.
- Integration: high-visibility focus ring token; minimum target size in comfortable density.
- Acceptance: focus always visible; default-mode targets ≥ a set minimum.
  (WCAG 2.4.7, 2.5.5)
- Phase: 1 tokens; each view

**KBD-03 — No time pressure required**
- Basis: *"may navigate more slowly."*
- Integration: per-question test timers are **optional** and off by default in Accessibility-First;
  no auto-advance.
- Acceptance: nothing forces a time limit; timers are opt-in. (WCAG 2.2.1)
- Phase: 4

### TTS — Text-to-speech

**TTS-01 — Speak content**
- Basis: *"Full text-to-speech support for flashcards."*
- Integration: TTS on card fronts/backs, PDF text/segments, dictionary definitions.
- Acceptance: any study content is speakable from a clearly-labeled control; works offline.
- Phase: 1 service; wired 2–3

**TTS-02 — Speak interface elements**
- Basis: *"and interface elements."*
- Integration: optional "speak focused control" mode reads labels/values as focus moves
  (complements, not replaces, a real screen reader).
- Acceptance: with the mode on, focusing a control speaks its accessible name; toggle in onboarding/Settings.
- Phase: 1

### ONB — Structural / Onboarding (accessibility-first by default)

**ONB-01 — Accessibility at first-run setup**
- Basis: *"accessibility settings appear during setup,"* *"deeply integrated and easy to
  activate at any time."*
- Integration: first-launch onboarding sets mode (Accessibility-First default-selected),
  theme/contrast, font scale, dyslexia font, TTS. Accessible itself (keyboard + SR + TTS).
- Acceptance: a first-run user configures core accessibility before reaching the app; all of
  it is changeable later in Settings.
- Phase: 1

**ONB-02 — On by default, switchable anytime**
- Basis: *"easy to activate at any time,"* not *"hidden settings."*
- Integration: Accessibility-First is the default mode; a persistent, reachable control toggles
  mode and key a11y options without digging.
- Acceptance: default install behaves accessibility-first with no configuration; toggle is ≤ 1–2 steps away.
- Phase: 1

### AUT — Learner autonomy

**AUT-01 — Generated content is editable and labeled**
- Basis: *"generated content should be editable, clearly labeled … a study aid rather than a
  source of truth."*
- Integration: only the user-initiated card→question bridge; output is an editable **draft**
  with a visible "generated — review me" label (`is_generated_draft`). No bulk auto-gen.
- Acceptance: every generated item is editable before use and visibly labeled until confirmed.
- Phase: 4

### PRV — Privacy (visible, local-first)

**PRV-01 — Local/offline storage, stated plainly**
- Basis: *"local storage and offline processing,"* protecting *"sensitive study data."*
- Integration: all data in a local app-data dir; zero network except the one-time dictionary
  build; a plain-language privacy statement shown at onboarding.
- Acceptance: app is fully functional offline; no telemetry; privacy statement present and true.
- Phase: 1 (statement + paths); verified cross-cutting

---

## 4. The Accessibility-First Default Flow (concrete patterns)

How "by default" actually looks, so it's buildable and reviewable:

- **Single-column, single-focus screens**; one primary action, secondary actions de-emphasized.
- **Generous spacing** (comfortable density token set) and **large, clearly-labeled targets**.
- **Guided creation/review** (wizard-style) instead of dense forms.
- **Assistive controls always reachable**: TTS, contrast, font scale available from a consistent
  spot on every screen (not buried).
- **Plain language**, icons + text labels (never icon-only for primary actions).
- **No required configuration** before studying; **no enforced timers**.
- Advanced/dense layouts and power tools exist only after switching to Advanced mode.

---

## 5. Definition of Done — per-view accessibility checklist

No view is "done" until all pass:

- [ ] Fully keyboard operable; visible focus; logical tab order. (KBD-01/02, SR-02)
- [ ] Every interactive element has an accessible name + role. (SR-01)
- [ ] Meaningful status changes are announced. (SR-02)
- [ ] Readable and non-overlapping at 200% font scale + increased spacing. (VIS-01, RDG-02)
- [ ] Passes contrast in standard **and** high-contrast themes. (VIS-02)
- [ ] No information conveyed by color alone. (VIS-03)
- [ ] Content is TTS-speakable; assistive controls reachable on-screen. (TTS-01/02)
- [ ] Default-mode control count stays within the cognitive-load budget. (COG-02)

---

## 6. Testing & Cross-Compatibility Plan

The proposal calls out *"cross-compatibility testing across different generations of devices."*
Plan **[impl choices noted]**:

- **Automated (pytest):** contrast-ratio checks on every theme; accessible-name presence on
  built widgets; font-scale reflow assertions; keyboard-path tests where feasible.
- **Manual screen-reader passes:** NVDA (primary) + Windows Narrator on each view.
- **Keyboard-only pass:** complete a create→review→test session with no mouse.
- **Font-scale / spacing stress:** verify reflow at max scale + max spacing.
- **Cross-generation devices:** test on a low-spec / older Windows machine and a current one
  (smaller screen, lower resolution, slower CPU) to honor the proposal's device-range claim.
- Accessibility regression check is part of every phase's exit criteria.

---

## 7. Phase Mapping (accessibility from the beginning)

| Phase | Accessibility deliverables |
|---|---|
| **1 — Foundation & A11y Spine** | Token axes (scale/contrast/spacing/density), high-contrast themes, dyslexia font, font scaling, spacing controls, TTS service (content + UI-focus mode), `ui/a11y` SR/keyboard conventions, **onboarding**, privacy statement, contrast/label tests. |
| **2 — Cards** | Guided one-card review, zero-config SRS, badges with icon+text, keyboard ratings, TTS on cards, novice guidance. |
| **3 — PDF/Sources** | Readable spaced extraction, keyboard + SR access to viewer/notes, TTS on text & definitions, accessible highlight→card. |
| **4 — Testing** | Optional (off-by-default) timers, keyboard/SR test flow, labeled editable generated drafts, TTS prompts. |
| **5 — Dashboard & Search** | Simplified default dashboard, accessible global search, SR result navigation. |
| **Cross-cutting** | Per-view DoD checklist, NVDA/Narrator passes, cross-generation device testing, offline/privacy verification. |

---

## 8. Traceability Summary

| Proposal intent | Requirement(s) |
|---|---|
| Full TTS for flashcards and interface | TTS-01, TTS-02 |
| Adjustable font scaling | VIS-01 |
| High-contrast themes | VIS-02 |
| Simplified interface / reduce clutter & cognitive load | COG-01, COG-02, COG-03, §4 |
| Screen-reader compatibility | SR-01, SR-02, KBD-01 |
| Accessibility appears at setup, not hidden, activate anytime | ONB-01, ONB-02 |
| Font adjustments + spacing (dyslexia) | RDG-01, RDG-02 |
| Readable-by-default study screens / clearer spacing | RDG-03, COG-01 |
| Navigate more slowly / no speed reliance | KBD-03, §1.2 |
| Generated content editable + labeled | AUT-01 |
| Local storage / offline privacy | PRV-01 |
| Plan accessibility from the beginning | §1.3, Phase 1 mapping |
| Preserve advanced options, separated | OVERHAUL_PLAN §2 (dual mode) |
| Cross-generation device testing | §6 |
