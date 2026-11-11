import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
rows = [json.loads(line) for line in (root / "public/data/dev_notes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
output = root / "in/notes.jsonl"
with open(output, "w", encoding="utf-8") as stream:
    for repeat in range(10):
        for row in rows:
            stream.write(json.dumps({"id": f"load-{repeat}-{row['id']}", "text": row["text"]}, ensure_ascii=False) + "\n")
print(f"wrote {len(rows) * 10} synthetic load-test notes to {output}")
