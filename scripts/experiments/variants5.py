"""Tune the remaining weights now that who index terms are in the index."""
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


def official(pred: Path) -> tuple[float, float, float]:
    out = subprocess.run(
        [sys.executable, str(ROOT / "public/score.py"), "--gold", str(DEV), "--pred", str(pred), "--mms", str(MMS)],
        capture_output=True, text=True, check=True,
    ).stdout
    top1 = top3 = total = 0.0
    for line in out.splitlines():
        if line.startswith("slice"):
            top1 = float(line.split("top1")[1].split()[0])
            top3 = float(line.split("top3")[1].split()[0])
        if line.startswith("SCORE"):
            total = float(line.split()[1])
    return total, top1, top3


def main() -> None:
    with gzip.open(TERMS, "rt", encoding="utf-8") as stream:
        terms = json.load(stream)["codes"]
    catalogue = Catalogue.load(MMS)
    rows = [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]

    variants = {
        "phrase12": {"phrase_bonus": 12.0},
        "phrase16": {"phrase_bonus": 16.0},
        "phrase20": {"phrase_bonus": 20.0},
        "phrase30": {"phrase_bonus": 30.0},
        "phrase12_b09": {"phrase_bonus": 12.0, "bm25_b": 0.9},
        "phrase16_b09": {"phrase_bonus": 16.0, "bm25_b": 0.9},
        "phrase12_k15": {"phrase_bonus": 12.0, "bm25_k1": 1.5},
        "phrase16_bg12": {"phrase_bonus": 16.0, "bigram_weight": 12.0},
    }
    for name, extra in variants.items():
        kwargs = {"terms": terms, **extra}
        pred = ROOT / f"out/tune_{name}.jsonl"
        run(str(DEV), str(pred), MMS, api_enabled=False, coder=Coder(catalogue, rows, **kwargs))
        total, top1, top3 = official(pred)
        print(f"{name:12s} score={total:5.1f} top1={top1:.3f} top3={top3:.3f}", flush=True)


if __name__ == "__main__":
    main()
