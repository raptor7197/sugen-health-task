"""Measure ranking variants with the supplied scorer.

Every number comes from public/score.py on the full 60-note dev set. Weights are chosen
on the visible set, so the table is a dev score, not an estimate of hidden performance.
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
    "baseline": {},
    "no_lexicon": {"use_lexicon": False},
    "anchor5": {"anchor_weight": 5.0},
    "anchor2": {"anchor_weight": 2.0},
    "idf15": {"idf_power": 1.5},
    "idf20": {"idf_power": 2.0},
    "no_coverage": {"use_coverage": False},
    "no_diversity": {"use_diversity": False},
    "lex_anchor5_idf15": {"anchor_weight": 5.0, "idf_power": 1.5},
    "lex_anchor2_idf15": {"anchor_weight": 2.0, "idf_power": 1.5},
    "lex_idf15": {"idf_power": 1.5},
}


def score_of(pred: Path) -> tuple[float, float, float]:
    out = subprocess.run(
        [sys.executable, str(ROOT / "public/score.py"), "--gold", str(DEV), "--pred", str(pred), "--mms", str(MMS)],
        capture_output=True, text=True, check=True,
    ).stdout
    top1 = top3 = 0.0
    total = 0.0
    for line in out.splitlines():
        if line.startswith("slice"):
            top1 = float(line.split("top1")[1].split()[0])
            top3 = float(line.split("top3")[1].split()[0])
        if line.startswith("SCORE"):
            total = float(line.split()[1])
    return total, top1, top3


def main() -> None:
    catalogue = Catalogue.load(MMS)
    rows = [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for name, kwargs in VARIANTS.items():
        coder = Coder(catalogue, rows, **kwargs)
        pred = ROOT / f"out/exp_{name}.jsonl"
        run(str(DEV), str(pred), MMS, api_enabled=False, coder=coder)
        total, top1, top3 = score_of(pred)
        results.append((total, top1, top3, name))
        print(f"{name:22s} score={total:5.1f} top1={top1:.3f} top3={top3:.3f}", flush=True)
    print("\nranked by dev score")
    for total, top1, top3, name in sorted(results, reverse=True):
        print(f"  {total:5.1f}  top1={top1:.3f} top3={top3:.3f}  {name}")


if __name__ == "__main__":
    main()
