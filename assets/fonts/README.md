# Bundled fonts (RDG-01)

Drop the dyslexia-friendly font files here as `.ttf` or `.otf`. They are loaded
automatically at startup by `ui/theme/fonts.py` and become selectable in
Settings. The accessibility-first default font is **Atkinson Hyperlegible**;
**OpenDyslexic** is offered as an alternative.

If neither is present, the app falls back safely to a system sans face
(Segoe UI / Arial / …) — no missing-glyph rendering.

## Recommended fonts to add (both are free / open-licensed)

| Font | License | Source |
|------|---------|--------|
| Atkinson Hyperlegible | OFL-style (Braille Institute) | https://brailleinstitute.org/freefont |
| OpenDyslexic | SIL OFL 1.1 | https://opendyslexic.org |

Place the regular (and optionally bold/italic) weights directly in this folder,
e.g.:

```
assets/fonts/AtkinsonHyperlegible-Regular.ttf
assets/fonts/AtkinsonHyperlegible-Bold.ttf
assets/fonts/OpenDyslexic-Regular.otf
```

These files are intentionally **not** committed binaries in this repo scaffold;
add them locally (and to the PyInstaller bundle) before release.
