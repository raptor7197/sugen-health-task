"""For each ranking failure, show what each signal said about gold versus the winner."""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from coder.catalog import Catalogue
from coder.engine import Coder, _query_tokens, _body_counts, _anchor_counts, _clip, STOP

ROOT = Path(__file__).resolve().parents[2]
cat = Catalogue.load(ROOT / "public/data/mms-2026-01.json")
with gzip.open(ROOT / "data/icd11_terms.json.gz", "rt", encoding="utf-8") as stream:
    terms = json.load(stream)["codes"]
rows = {json.loads(line)["id"]: json.loads(line) for line in (ROOT / "public/data/dev_notes.jsonl").read_text().splitlines() if line.strip()}
coder = Coder(cat, list(rows.values()), terms=terms)

CASES = {
    "dev-026": "DA09.60", "dev-019": "1D80.0", "dev-023": "FA01.Z",
    "dev-055": "BA40.1", "dev-056": "JA63.2", "dev-058": "BD90.0",
    "dev-044": "5A21.0", "dev-011": "1C62.0", "dev-012": "1F86.0",
}


def features(text: str, code: str) -> dict:
    safe = _clip(text)
    raw = [t for t in coder._tokens(safe) if t not in STOP]
    note_norm = " " + " ".join(raw) + " "
    bm = {item.code: (rank + 1, item.score) for rank, item in enumerate(coder._rank(_query_tokens(safe, coder.anchor_weight, coder.use_lexicon, coder.use_post_negation)))}
    phrase = any(f" {p} " in note_norm for p in coder.phrases.get(code, ()))
    bigrams = 0
    for i in range(len(raw) - 1):
        if code in coder.bigrams.get(f"{raw[i]} {raw[i+1]}", ()):
            bigrams += 1
    anchor = _anchor_counts(safe, 1.0, coder.use_lexicon)
    anchor_hits = sum(anchor.get(t, 0) for t in coder.title_text.get(code, "").split())
    return {"rank": bm.get(code, (999, 0.0))[0], "bm25": round(bm.get(code, (0, 0.0))[1], 2),
            "phrase": phrase, "bigrams": bigrams, "anchor_hits": anchor_hits}


for note_id, gold in CASES.items():
    row = rows[note_id]
    codes, audit = coder.predict(row["text"], note_id)
    winner = codes[0]
    print(f"\n=== {note_id} gold={gold} ({cat.categories[gold].title[:44]})")
    print(f"    predicted {codes}")
    print(f"    gold   {features(row['text'], gold)}")
    print(f"    winner {winner} {features(row['text'], winner)} ({cat.categories[winner].title[:38]})")
    print(f"    sources {audit['sources']}")
