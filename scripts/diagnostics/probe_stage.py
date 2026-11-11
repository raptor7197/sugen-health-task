import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.engine import Coder

root = Path(__file__).resolve().parents[1]
notes = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
catalogue = Catalogue.load(root / "public/data/mms-2026-01.json")
coder = Coder(catalogue, notes)

with open(root / "out/scale_1.jsonl", encoding="utf-8") as source:
    for line_number, line in enumerate(source, 1):
        note = json.loads(line)
        t0 = time.monotonic()
        codes, audit = coder.predict(str(note["text"]), note["id"])
        t1 = time.monotonic()
        valid = [c for c in codes if c in catalogue.codes]
        t2 = time.monotonic()
        padded = (coder.fallback, *sorted(catalogue.codes))
        t3 = time.monotonic()
        valid.extend(c for c in padded if c not in valid)
        t4 = time.monotonic()
        payload = json.dumps({"id": note["id"], "codes": valid[:3]})
        t5 = time.monotonic()
        print(f"{line_number:3d} predict={1000*(t1-t0):7.1f} filter={1000*(t2-t1):5.1f} sort={1000*(t3-t2):7.1f} extend={1000*(t4-t3):7.1f} dump={1000*(t5-t4):5.1f} ms", flush=True)
        if line_number >= 12:
            break
