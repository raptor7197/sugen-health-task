"""Compile the fetched icd-11 caches into the artefact that ships in the image.

input : data/.cache/terms_<lang>.jsonl   (written by scripts/fetch_terms.py)
output: data/icd11_terms.json.gz         ({"codes": {code: [phrase, ...]}, "languages": [...]})

terms are whitespace-normalised, deduplicated per code and capped, so the artefact stays
small enough to sit inside the container image.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "public/data/mms-2026-01.json"
CACHE_DIR = ROOT / "data/.cache"
OUT = ROOT / "data/icd11_terms.json.gz"
LANGUAGES = ("en", "es", "fr", "pt")
MAX_TERMS = 60
MAX_TERM_CHARS = 120


def main() -> None:
    valid = {row["code"] for row in json.loads(CATALOGUE.read_text(encoding="utf-8"))}
    codes: dict[str, list[str]] = {}
    seen_languages: list[str] = []
    rows_per_language: dict[str, int] = {}

    for lang in LANGUAGES:
        path = CACHE_DIR / f"terms_{lang}.jsonl"
        if not path.exists():
            continue
        seen_languages.append(lang)
        count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            code = row.get("code")
            if code not in valid:
                continue
            bucket = codes.setdefault(code, [])
            for term in row.get("terms", []):
                term = " ".join(str(term).split())[:MAX_TERM_CHARS]
                if term and term not in bucket and len(bucket) < MAX_TERMS:
                    bucket.append(term)
            count += 1
        rows_per_language[lang] = count

    if not codes:
        raise SystemExit("no cache rows found; run scripts/fetch_terms.py first")

    payload = {
        "source": "who icd-11 mms 2026-01 linearization, index terms via id.who.int",
        "release": "2026-01",
        "languages": seen_languages,
        "codes": codes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))

    total = sum(len(value) for value in codes.values())
    print(f"languages={seen_languages} rows={rows_per_language}")
    print(f"codes={len(codes)}/{len(valid)} phrases={total} size={OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
