import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.engine import Coder

root = Path(__file__).resolve().parents[1]
rows = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
coder = Coder(Catalogue.load(root / "public/data/mms-2026-01.json"), rows)
hits = {3: 0, 10: 0, 24: 0}
for row in rows:
    candidates = [item["code"] for item in coder.candidate_details(row["text"], limit=24, note_id=row["id"])]
    gold = set(row["gold"])
    for k in hits:
        hits[k] += bool(gold.intersection(candidates[:k]))
print(f"leave_one_out_recall_at_3={hits[3]}/{len(rows)}")
print(f"leave_one_out_recall_at_10={hits[10]}/{len(rows)}")
print(f"leave_one_out_recall_at_24={hits[24]}/{len(rows)}")
