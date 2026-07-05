# StudyApp — Dev Reference & Troubleshooting

Quick references for running, testing, where data lives, and the gotchas we've
hit. Keep this updated as things change.

## Run the app
```
.venv\Scripts\python.exe main.py
```
- First launch shows the **accessibility onboarding wizard** (mode → theme → text
  size → speech), then the **Dashboard**.
- venv interpreter: `.venv\Scripts\python.exe` (PyQt6, SQLAlchemy, PyMuPDF, etc.
  installed here).

## Run the tests
```
.venv\Scripts\python.exe -m pytest        # 194 passing
```
- GUI tests run headless via `QT_QPA_PLATFORM=offscreen` (set in root `conftest.py`).
- Dev smoke renders (optional): `python tools\_smoke_app.py` → PNGs in `tools/_preview/`.

## Where data lives
- **Running from source (dev):** `user_data/` in the project root —
  `study_app.db` (+ `-wal`/`-shm`), `settings.json`, `audio/`, `backups/`, and
  `wiktionary.db` (built on first launch).
- **Packaged (PyInstaller, frozen):** per-user app data — on Windows
  `%APPDATA%\StudyApp\`. Never written beside the .exe.
- `user_data/` is **git-ignored** (never committed).

## ⚠ Stale-DB / schema gotcha  (the `no such column: cards.srs_state` crash)
- **Cause:** an existing `user_data/study_app.db` from *before* the rebuild.
  SQLAlchemy `create_all()` only creates **missing tables** — it does **not** add
  new columns to a table that already exists. So an old `cards` table is missing
  the new columns (`srs_state`, etc.) and queries fail at startup.
- **Cleared 2026-06-02:** the old DB + old-schema backups were moved to
  `user_data/_pre_rebuild_archive/` and the `-wal`/`-shm` removed. A fresh schema
  is created on the next launch (verified working).
- **To reset again manually:** close the app, then delete (or move) these and
  relaunch — they're recreated fresh:
  ```
  user_data\study_app.db   user_data\study_app.db-wal   user_data\study_app.db-shm
  ```
  (Also clear `user_data\backups\study_app_*.db` if they're old-schema.)
- **RECOMMENDED (not yet done):** add a schema-version guard in
  `core/startup.py` (via `PRAGMA user_version`) that auto-archives an
  incompatible DB and recreates it — this prevents the crash for a teammate who
  has their own old DB. Ask Claude to "add the startup schema-version guard."

## Fonts
- Bundled in `assets/fonts/` (Atkinson Hyperlegible originals, free for all use);
  loaded at startup, default family **Atkinson Hyperlegible**. Mono/Next
  personal-use files are git-ignored (local only).
- Headless/offscreen renders show **blank or box ("tofu") text** because that
  environment has no font rasterizer — this is NOT a bug; real Windows renders
  text fully.

## Dictionary
- `user_data/wiktionary.db` is built on first launch by `tools/build_dictionary.py`
  (kaikki data). Until built, lookups fall back to WordNet (if NLTK data present)
  or return nothing — degrades gracefully, never crashes.

## Git / checkpoint
- Branch: **`rebuild/phase-1-2`** (pushed to GitHub `AdrWTHeck/study-application`).
- A large body of work (5 phases + Phase 6 features) is **uncommitted** — commit a
  checkpoint when ready.
- Open the PR: run `gh auth login` once (gh 2.93.0 is installed), or use
  https://github.com/AdrWTHeck/study-application/pull/new/rebuild/phase-1-2

## Directory map
```
app/      shell (main_window), navigation, onboarding, context
core/     paths, settings, startup, backup, clock
data/     db, models/, repositories/, seed
domain/   srs, notes, decks, cards, testing, sources, dashboard, search,
          dictionary, accessibility
ui/       theme (tokens/qss/fonts), a11y, components, views/
docs/     plans, specs, and this reference
legacy/   old v1 code — reference only, not imported
tests/    pytest suite
tools/    dev smoke scripts + dictionary builder
```
