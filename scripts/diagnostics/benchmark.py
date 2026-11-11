import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.engine import Coder

root = Path(__file__).resolve().parents[1]
catalogue = Catalogue.load(root / "public/data/mms-2026-01.json")
rows = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
coder = Coder(catalogue, rows)
for row in rows:
    start = time.monotonic()
    coder.predict(row["text"], row["id"])
    elapsed = time.monotonic() - start
    print(f"{row['id']} {elapsed:.4f}s", flush=True)
