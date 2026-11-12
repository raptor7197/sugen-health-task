"""Recompute the numbers the readme quotes for the current defaults."""
import gzip
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.cli import run
from coder.engine import Coder, _query_tokens

ROOT = Path(__file__).resolve().parents[1]
MMS = ROOT / "public/data/mms-2026-01.json"
DEV = ROOT / "public/data/dev_notes.jsonl"
PRED = ROOT / "out/dev_predictions.jsonl"

with gzip.open(ROOT / "data/icd11_terms.json.gz", "rt", encoding="utf-8") as stream:
    terms = json.load(stream)["codes"]
catalogue = Catalogue.load(MMS)
rows = [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]
coder = Coder(catalogue, rows, terms=terms)
run(str(DEV), str(PRED), MMS, api_enabled=False, coder=coder)

per_note = PRED.with_suffix(".pernote.jsonl")
out = subprocess.run(
    [sys.executable, str(ROOT / "public/score.py"), "--gold", str(DEV), "--pred", str(PRED),
     "--mms", str(MMS), "--per-note", str(per_note)],
    capture_output=True, text=True, check=True,
).stdout
total = top1 = top3 = 0.0
for line in out.splitlines():
    if line.startswith("slice"):
        top1 = float(line.split("top1")[1].split()[0])
        top3 = float(line.split("top3")[1].split()[0])
    if line.startswith("SCORE"):
        total = float(line.split()[1])

notes = [json.loads(line) for line in per_note.read_text(encoding="utf-8").splitlines()]
ordered = sorted(notes, key=lambda row: row["id"])
halves = []
for half in (ordered[0::2], ordered[1::2]):
    h1 = sum(row["top1"] for row in half) / len(half)
    h3 = sum(row["top3"] for row in half) / len(half)
    halves.append(75 * (2 / 3 * h1 + 1 / 3 * h3))

reach24 = reach64 = 0
for row in rows:
    gold = set(row["gold"])
    ranked = [item.code for item in coder._rank(_query_tokens(row["text"], coder.anchor_weight, coder.use_lexicon, coder.use_post_negation))]
    if gold & set(ranked[:24]):
        reach24 += 1
    if gold & set(ranked[:64]):
        reach64 += 1

p = total / 75
print(json.dumps({
    "score": round(total, 1), "top1": round(top1, 3), "top3": round(top3, 3),
    "halves": [round(halves[0], 1), round(halves[1], 1)],
    "reach_top24": f"{reach24}/60", "reach_top64": f"{reach64}/60",
    "oracle": round(75 * reach24 / 60, 1),
    "estimate": f"{int(round(100 * p * 0.85))}-{int(round(100 * p))}",
}, indent=2))
