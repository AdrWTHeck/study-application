# FSRS Feasibility Spike

> **Superseded:** FSRS is now the **only** scheduler — SM-2 has been removed. The
> historical spike below is kept for context.
>
> Date: 2026-05-31 · Verdict: **FEASIBLE — low-risk drop-in.** Spike run against
> the live venv (Python 3.14). FSRS remains *future/optional*; SM-2 still ships
> first (see [OVERHAUL_PLAN.md](OVERHAUL_PLAN.md)).

## Verdict
Adopting FSRS later is straightforward and cheap. The official package schedules
with zero heavy dependencies, is MIT-licensed, and its card fields map cleanly to
a small set of DB columns. No architectural rework is needed if Phase 2 builds the
SRS layer behind an interface (as planned) and includes a few extra card columns.

## Package
- **`fsrs`** (py-fsrs), version **6.3.1**, implementing **FSRS-6**.
- Repo: https://github.com/open-spaced-repetition/py-fsrs · PyPI: https://pypi.org/project/fsrs/
- Pure-Python wheel, **22 KB**. Maintained (open-spaced-repetition org).

## License — MIT
- The package is **MIT licensed** (confirmed in the installed package metadata).
- MIT is permissive: free to use, modify, distribute, sublicense, and sell. The
  **only obligation** is to include the copyright + permission notice in our
  distribution (i.e. ship py-fsrs's LICENSE text with the packaged app — a small
  attribution line/file).
- Fully compatible with our offline, packaged, redistributable app. The FSRS
  *algorithm* itself is also open and free.

## Dependencies — verified lightweight
- Base install pulled **only `typing-extensions`** (already in our venv).
- The spike printed: **`heavy modules imported by scheduling: none`** — no
  PyTorch / NumPy / pandas touched during scheduling.
- The optional **optimizer** (personalizing weights from review history) is a
  separate extra: `pip install "fsrs[optimizer]"`, which *does* pull PyTorch. We
  would **not** bundle that — defaults work out of the box (below).

## API (confirmed working)
```python
from fsrs import Scheduler, Card, Rating
scheduler = Scheduler()              # FSRS-6 default weights, no training needed
card = Card()                        # new card, due immediately
card, review_log = scheduler.review_card(card, Rating.Good)   # 1=Again 2=Hard 3=Good 4=Easy
card.due                             # tz-aware UTC datetime of next review
scheduler.get_card_retrievability(card)   # current recall probability (0–1)
```
Our existing rating buttons (Again/Hard/Good/Easy) already line up 1:1 with
`Rating`.

## Card fields to persist (`Card.to_dict()`)
```
card_id, state, step, stability, difficulty, due, last_review
```
- `state`: 1=Learning, 2=Review, 3=Relearning (a never-reviewed card → treat as
  our "New").
- `stability`, `difficulty`: the FSRS memory model (floats).
- `due`, `last_review`: tz-aware UTC datetimes — store as UTC.

Observed behavior in the spike (sanity check): an *Again* dropped stability
2.31 → 0.78 and raised difficulty 2.1 → 7.4; a later *Easy* recovered it — i.e.
the model responds correctly.

## Integration with our base
1. **SRS interface (Phase 2):** define `SrsEngine` with `new_card()` and
   `review(state, rating, now) -> state`. Provide `Sm2Engine` (default) and, later,
   `FsrsEngine` wrapping py-fsrs. Selectable in Settings ("both, selectable").
2. **Card model columns (add now, cheap):** keep a *superset* so either engine
   works without migration —
   - shared (drive UI counts + due queries): `srs_state`, `due_date`, `last_review`, `reps`, `lapses`
   - SM-2: `ease_factor`, `interval`
   - FSRS: `stability`, `difficulty`, `step`
   Nullable; the active engine writes its own fields. This keeps New/Learning/
   Review counts and "due today" queries fast and engine-agnostic.
3. **`review_log`** (already planned) records each rating + timestamps + elapsed —
   exactly what the optional optimizer needs later.
4. **Defaults vs optimization:** ship FSRS-6 default weights (verified to schedule
   with no setup). Personalization is optional and deferrable — via a separate
   tool or a small NumPy optimizer — never bundling PyTorch into the main app.

## Packaging note
A 22 KB pure-Python package with no binary deps is trivial to include in the
PyInstaller one-folder build. Adoption = add `fsrs` to `requirements.txt`.

## Risks / watch-items
- Store all FSRS datetimes as **UTC** (they're tz-aware).
- FSRS state model differs slightly from SM-2 (adds Relearning) — the shared
  `srs_state` mapping handles this.
- Keep SM-2 the default; make FSRS an explicit opt-in so behavior never changes
  under a user unexpectedly.

## Spike hygiene
`fsrs` was installed only to run this spike and has been **uninstalled** to keep
the venv matching `requirements.txt`. Re-add it when we actually adopt FSRS.
