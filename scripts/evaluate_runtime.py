import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.cli import run

root = Path(__file__).resolve().parents[1]
notes = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
input_path = root / "out/benchmark_600.jsonl"
output_path = root / "out/benchmark_600_predictions.jsonl"
input_path.parent.mkdir(parents=True, exist_ok=True)
with open(input_path, "w", encoding="utf-8") as stream:
    for index in range(10):
        for note in notes:
            stream.write(json.dumps({"id": f"load-{index}-{note['id']}", "text": note["text"]}, ensure_ascii=False) + "\n")
start = time.monotonic()
stats = run(str(input_path), str(output_path), str(root / "public/data/mms-2026-01.json"), api_enabled=False)
elapsed = time.monotonic() - start
print(f"synthetic_notes={stats['input']} written={stats['written']} missing={stats['input'] - stats['written']} elapsed_seconds={elapsed:.2f} estimated_600_runtime_seconds={elapsed:.2f}")
