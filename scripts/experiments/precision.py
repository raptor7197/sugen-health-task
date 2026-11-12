"""Measure the three precision fixes: phrase length scaling, bigram rarity, relative rules."""
import gzip
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from coder.catalog import Catalogue
from coder.cli import run
from coder.engine import Coder

ROOT = Path(__file__).resolve().parents[2]
MMS = ROOT / "public/data/mms-2026-01.json"
DEV = ROOT / "public/data/dev_notes.jsonl"
TERMS = ROOT / "data/icd11_terms.json.gz"

BASE = {"bigram_idf": True, "phrase_bonus": 30.0, "bm25_b": 0.9}
VARIANTS = {
    "phrases16": {**BASE, "max_phrases": 16},
    "phrases20": {**BASE, "max_phrases": 20},
    "phrases24": {**BASE, "max_phrases": 24},
    "phrases16_b10": {**BASE, "max_phrases": 16, "bm25_b": 1.0},
    "phrases16_p40": {**BASE, "max_phrases": 16, "phrase_bonus": 40.0},
    "phrases16_k15": {**BASE, "max_phrases": 16, "bm25_k1": 1.5},
    "phrases16_bg10": {**BASE, "max_phrases": 16, "bigram_weight": 10.0},
}


def score(pred: Path) -> tuple[float, float, float, list[dict]]:
    per_note = pred.with_suffix(".pernote.jsonl")
    out = subprocess.run(
        [sys.executable, str(ROOT / "public/score.py"), "--gold", str(DEV), "--pred", str(pred),
         "--mms", str(MMS), "--per-note", str(per_note)],
        capture_output=True, text=True, check=True,
    ).stdout
    top1 = top3 = total = 0.0
    for line in out.splitlines():
        if line.startswith("slice"):
            top1 = float(line.split("top1")[1].split()[0])
            top3 = float(line.split("top3")[1].split()[0])
        if line.startswith("SCORE"):
            total = float(line.split()[1])
    notes = [json.loads(line) for line in per_note.read_text(encoding="utf-8").splitlines()]
    return total, top1, top3, notes


def halves(notes: list[dict]) -> tuple[float, float]:
    ordered = sorted(notes, key=lambda row: row["id"])
    out = []
    for half in (ordered[0::2], ordered[1::2]):
        top1 = sum(row["top1"] for row in half) / len(half)
        top3 = sum(row["top3"] for row in half) / len(half)
        out.append(75 * (2 / 3 * top1 + 1 / 3 * top3))
    return out[0], out[1]


def main() -> None:
    with gzip.open(TERMS, "rt", encoding="utf-8") as stream:
        terms = json.load(stream)["codes"]
    catalogue = Catalogue.load(MMS)
    rows = [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]
    for name, extra in VARIANTS.items():
        pred = ROOT / f"out/prec_{name}.jsonl"
        run(str(DEV), str(pred), MMS, api_enabled=False, coder=Coder(catalogue, rows, terms=terms, **extra))
        total, top1, top3, notes = score(pred)
        a, b = halves(notes)
        print(f"{name:22s} score={total:5.1f} top1={top1:.3f} top3={top3:.3f} halves={a:5.1f}/{b:5.1f}", flush=True)


if __name__ == "__main__":
    main()
