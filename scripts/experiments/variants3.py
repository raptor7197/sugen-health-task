"""Compare ranking configs on the full dev set and on two fixed halves.

The headline number is always the supplied scorer's SCORE. The halves come from
score.py's own per-note output and exist only to check a config is not fitting noise.
"""
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

VARIANTS: dict[str, dict] = {
    "locked": {},
    "prf1": {"use_prf": True, "prf_weight": 1.0},
    "prf2": {"use_prf": True, "prf_weight": 2.0},
    "prf4": {"use_prf": True, "prf_weight": 4.0},
    "prf2d3": {"use_prf": True, "prf_weight": 2.0, "prf_docs": 3},
}


def official(pred: Path) -> tuple[float, float, float, list[dict]]:
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


def half_scores(notes: list[dict], total_weight: float = 75.0) -> tuple[float, float]:
    ordered = sorted(notes, key=lambda row: row["id"])
    scores = []
    for half in (ordered[0::2], ordered[1::2]):
        top1 = sum(row["top1"] for row in half) / len(half)
        top3 = sum(row["top3"] for row in half) / len(half)
        scores.append(total_weight * (2 / 3 * top1 + 1 / 3 * top3))
    return scores[0], scores[1]


def main() -> None:
    catalogue = Catalogue.load(MMS)
    rows = [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for name, kwargs in VARIANTS.items():
        pred = ROOT / f"out/exp3_{name}.jsonl"
        run(str(DEV), str(pred), MMS, api_enabled=False, coder=Coder(catalogue, rows, **kwargs))
        total, top1, top3, notes = official(pred)
        half_a, half_b = half_scores(notes)
        results.append((min(half_a, half_b), total, top1, top3, name))
        print(f"{name:22s} score={total:5.1f} top1={top1:.3f} top3={top3:.3f} halves={half_a:5.1f}/{half_b:5.1f}", flush=True)
    print("\nranked by worst half")
    for worst, total, top1, top3, name in sorted(results, reverse=True):
        print(f"  worst_half={worst:5.1f} score={total:5.1f} top1={top1:.3f} top3={top3:.3f}  {name}")


if __name__ == "__main__":
    main()
