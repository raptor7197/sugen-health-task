"""Split-half stability check for the shortlisted weighting configs."""
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

CONFIGS = {
    "phrase12": {"phrase_bonus": 12.0},
    "phrase16": {"phrase_bonus": 16.0},
    "phrase20": {"phrase_bonus": 20.0},
    "phrase16_b09": {"phrase_bonus": 16.0, "bm25_b": 0.9},
    "phrase12_k15": {"phrase_bonus": 12.0, "bm25_k1": 1.5},
}


def official(pred: Path) -> tuple[float, list[dict]]:
    per_note = pred.with_suffix(".pernote.jsonl")
    out = subprocess.run(
        [sys.executable, str(ROOT / "public/score.py"), "--gold", str(DEV), "--pred", str(pred),
         "--mms", str(MMS), "--per-note", str(per_note)],
        capture_output=True, text=True, check=True,
    ).stdout
    total = 0.0
    for line in out.splitlines():
        if line.startswith("SCORE"):
            total = float(line.split()[1])
    return total, [json.loads(line) for line in per_note.read_text(encoding="utf-8").splitlines()]


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
    for name, extra in CONFIGS.items():
        pred = ROOT / f"out/half_{name}.jsonl"
        run(str(DEV), str(pred), MMS, api_enabled=False, coder=Coder(catalogue, rows, terms=terms, **extra))
        total, notes = official(pred)
        a, b = halves(notes)
        print(f"{name:14s} score={total:5.1f} halves={a:5.1f}/{b:5.1f} spread={abs(a-b):4.1f}", flush=True)


if __name__ == "__main__":
    main()
