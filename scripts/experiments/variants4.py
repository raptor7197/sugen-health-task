"""Measure the who index-term integration with the supplied scorer.

Run this after build_terms.py has produced data/icd11_terms.json.gz.
"""
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


def load_terms() -> dict[str, list[str]]:
    if not TERMS.exists():
        raise SystemExit("missing data/icd11_terms.json.gz, run build_terms.py first")
    with gzip.open(TERMS, "rt", encoding="utf-8") as stream:
        return json.load(stream)["codes"]


def official(pred: Path) -> tuple[float, float, float]:
    out = subprocess.run(
        [sys.executable, str(ROOT / "public/score.py"), "--gold", str(DEV), "--pred", str(pred),
         "--mms", str(MMS)],
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
    catalogue = Catalogue.load(MMS)
    rows = [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]
    terms = load_terms()
    print(f"terms for {len(terms)} codes")

    variants = {
        "no_terms": {"terms": None},
        "phrases_only": {"terms": terms, "use_terms_index": False},
        "index_only": {"terms": terms, "use_terms_phrases": False},
        "both": {"terms": terms},
        "both_r1": {"terms": terms, "title_repeat": 1},
        "both_r3": {"terms": terms, "title_repeat": 3},
    }
    for name, kwargs in variants.items():
        pred = ROOT / f"out/terms_{name}.jsonl"
        coder = Coder(catalogue, rows, **kwargs)
        run(str(DEV), str(pred), MMS, api_enabled=False, coder=coder)
        total, top1, top3 = official(pred)
        print(f"{name:14s} score={total:5.1f} top1={top1:.3f} top3={top3:.3f}", flush=True)


if __name__ == "__main__":
    main()
