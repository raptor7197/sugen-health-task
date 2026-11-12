"""Where are we losing points: gold present but mis-ranked, or absent entirely."""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from coder.catalog import Catalogue
from coder.engine import Coder, _query_tokens

ROOT = Path(__file__).resolve().parents[2]
cat = Catalogue.load(ROOT / "public/data/mms-2026-01.json")
with gzip.open(ROOT / "data/icd11_terms.json.gz", "rt", encoding="utf-8") as stream:
    terms = json.load(stream)["codes"]
rows = [json.loads(line) for line in (ROOT / "public/data/dev_notes.jsonl").read_text().splitlines() if line.strip()]
coder = Coder(cat, rows, terms=terms)

buckets = {"top1": 0, "rank2-3": 0, "rank4-10": 0, "rank11-24": 0, "rank25-64": 0, "absent": 0}
near = []
for row in rows:
    gold = set(row["gold"])
    query = _query_tokens(row["text"], coder.anchor_weight, coder.use_lexicon, coder.use_post_negation)
    ranked = [item.code for item in coder._rank(query)]
    codes, _ = coder.predict(row["text"], row["id"])
    positions = [ranked.index(g) + 1 for g in gold if g in ranked]
    best = min(positions) if positions else None
    if best is None:
        buckets["absent"] += 1
    elif best == 1:
        buckets["top1"] += 1
    elif best <= 3:
        buckets["rank2-3"] += 1
    elif best <= 10:
        buckets["rank4-10"] += 1
    elif best <= 24:
        buckets["rank11-24"] += 1
    else:
        buckets["rank25-64"] += 1
    if gold & set(codes[:3]):
        continue
    if best is not None and best <= 24:
        near.append((best, row["id"], sorted(gold), codes[:3]))

print("gold position in bm25 list:")
for name, count in buckets.items():
    print(f"  {name:9s} {count:3d}  {count/len(rows):.3f}")
print(f"\nfailures where gold IS in top-24 (fixable by ranking): {len(near)}")
for best, note_id, gold, pred in sorted(near):
    print(f"  {note_id} gold_rank={best:2d} gold={gold} pred={pred}")
