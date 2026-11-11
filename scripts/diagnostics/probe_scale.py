import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from coder.cli import run

root = Path(__file__).resolve().parents[2]
notes = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

for repeats in (1, 10):
    source = root / f"out/scale_{repeats}.jsonl"
    with open(source, "w", encoding="utf-8") as stream:
        for index in range(repeats):
            for note in notes:
                stream.write(json.dumps({"id": f"s{repeats}-{index}-{note['id']}", "text": note["text"]}, ensure_ascii=False) + "\n")
    start = time.monotonic()
    stats = run(str(source), str(root / f"out/scale_{repeats}_out.jsonl"), str(root / "public/data/mms-2026-01.json"), api_enabled=False)
    elapsed = time.monotonic() - start
    print(f"rows={stats['input']} elapsed={elapsed:.2f}s per_row_ms={elapsed / stats['input'] * 1000:.1f}", flush=True)
