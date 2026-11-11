import cProfile
import io
import json
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.cli import run

root = Path(__file__).resolve().parents[1]
notes = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
source = root / "out/probe_in.jsonl"
with open(source, "w", encoding="utf-8") as stream:
    for index in range(3):
        for note in notes:
            stream.write(json.dumps({"id": f"p-{index}-{note['id']}", "text": note["text"]}, ensure_ascii=False) + "\n")

profiler = cProfile.Profile()
start = time.monotonic()
profiler.enable()
stats = run(str(source), str(root / "out/probe_out.jsonl"), str(root / "public/data/mms-2026-01.json"), api_enabled=False)
profiler.disable()
elapsed = time.monotonic() - start
print(f"rows={stats['input']} written={stats['written']} elapsed={elapsed:.2f}s per_row_ms={elapsed / max(1, stats['input']) * 1000:.1f}")
buffer = io.StringIO()
pstats.Stats(profiler, stream=buffer).sort_stats("cumulative").print_stats(14)
print(buffer.getvalue())
