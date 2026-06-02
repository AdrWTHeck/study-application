"""Build the offline Wiktionary dictionary DB from a kaikki.org JSONL dump.

Download the English extract once (this is the only network step in the app, and
it's optional — WordNet is the fallback):
    https://kaikki.org/dictionary/English/   →  kaikki.org-dictionary-English.jsonl

Usage:
    python tools/build_dictionary.py <input.jsonl> [output.db]

Default output is the app-data dictionary path. The repo lives in a OneDrive
folder, so the built DB is intentionally written to app-data (not committed).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.paths import get_app_paths  # noqa: E402
from domain.dictionary.builder import build_from_jsonl  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: build_dictionary.py <input.jsonl> [output.db]")
        return 2
    source = Path(argv[1])
    output = Path(argv[2]) if len(argv) > 2 else get_app_paths().dictionary_path
    count = build_from_jsonl(source, output)
    print(f"Built {count} senses -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
