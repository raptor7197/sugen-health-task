"""Recall ceiling analysis: where does the gold code sit in the candidate list?"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from coder.catalog import Catalogue
from coder.engine import Coder, _query_tokens

ROOT = Path(__file__).resolve().parents[2]
cat = Catalogue.load(ROOT / "public/data/mms-2026-01.json")
rows = [json.loads(line) for line in (ROOT / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
coder = Coder(cat, rows)

buckets = {"rank1": 0, "rank2-3": 0, "rank4-10": 0, "rank11-24": 0, "rank25-64": 0, "absent": 0}
for row in rows:
    gold = set(row["gold"])
    ranked = [item.code for item in coder._rank(_query_tokens(row["text"], coder.anchor_weight, coder.use_lexicon, coder.use_post_negation))]
    codes, _ = coder.predict(row["text"], row["id"])
    positions = [ranked.index(g) + 1 for g in gold if g in ranked]
    best = min(positions) if positions else None
    if best is None:
        buckets["absent"] += 1
    elif best == 1:
        buckets["rank1"] += 1
    elif best <= 3:
        buckets["rank2-3"] += 1
    elif best <= 10:
        buckets["rank4-10"] += 1
    elif best <= 24:
        buckets["rank11-24"] += 1
    else:
        buckets["rank25-64"] += 1
    if not (gold & set(codes[:3])):
        pass

total = len(rows)
print("gold position in BM25 candidate list (before post-processing):")
for name, count in buckets.items():
    print(f"  {name:10s} {count:3d}  {count / total:.3f}")
reachable = total - buckets["absent"]
print(f"\nrecall in top-64: {reachable}/{total} = {reachable/total:.3f}")
print(f"recall in top-24: {reachable - buckets['rank25-64']}/{total} = {(reachable - buckets['rank25-64'])/total:.3f}")
print(f"oracle top-3 score if ranking were perfect within top-24: "
      f"{75 * (2/3 * ((reachable - buckets['rank25-64'])/total) + 1/3 * ((reachable - buckets['rank25-64'])/total)):.1f} / 75")
