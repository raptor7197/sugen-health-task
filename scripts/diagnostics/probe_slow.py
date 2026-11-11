import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.engine import Coder

root = Path(__file__).resolve().parents[1]
notes = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
coder = Coder(Catalogue.load(root / "public/data/mms-2026-01.json"), notes)

slow = []
for index in range(3):
    for note in notes:
        note_id = f"p-{index}-{note['id']}"
        start = time.monotonic()
        coder.predict(note["text"], note_id)
        elapsed = time.monotonic() - start
        if elapsed > 0.05:
            slow.append((round(elapsed, 3), note_id))
print("slow_calls", slow[:15])
print("total_slow", len(slow))
