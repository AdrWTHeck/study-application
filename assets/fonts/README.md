# Bundled fonts (RDG-01)

Fonts placed **directly in this folder** (`.ttf`/`.otf`) are loaded automatically
at startup by `ui/theme/fonts.py` (recursively, skipping any
`For Professional Use Only` / `__MACOSX` subfolders) and become the
accessibility-first default. The default family is **Atkinson Hyperlegible**.

If no bundled font is found, the app falls back safely to a system sans face
(Segoe UI / Arial / …) — no missing-glyph rendering.

## What is committed
- **Atkinson Hyperlegible** (original, "Print-and-Web") — the four desktop
  `.ttf` styles at the top of this folder. This font is **free for all use**
  (including embedding and redistribution) under the Atkinson Hyperlegible Font
  License, so it ships with the app.

## What is kept local only (NOT committed)
The following are git-ignored (see `.gitignore`) and remain on your machine:
- **Atkinson Hyperlegible Mono** and **Atkinson Hyperlegible Next** desktop
  `.otf` — free for **personal use**. They load locally if present, but are not
  redistributed with the app to stay clear of their professional-use terms.
- Any `For Professional Use Only` material (web/variable/source files) — these
  require a professional license and have been removed from this folder.

## Adding another font (e.g. OpenDyslexic)
Drop the `.ttf`/`.otf` directly in `assets/fonts/`. OpenDyslexic is SIL OFL 1.1
(free, redistributable) — a good additional option. Then select it in Settings.
