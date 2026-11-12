"""Validate a predictions file against the grader contract."""
import json
import sys

sys.path.insert(0, "/home/krxsna/dev/SugenEngTest")
from coder.catalog import Catalogue, normalize_code

pred_path, input_path, mms_path = sys.argv[1], sys.argv[2], sys.argv[3]
valid = Catalogue.load(mms_path).codes
input_ids = []
with open(input_path, encoding="utf-8") as stream:
    for line in stream:
        if line.strip():
            input_ids.append(str(json.loads(line)["id"]))
rows = []
with open(pred_path, encoding="utf-8") as stream:
    for line in stream:
        if line.strip():
            rows.append(json.loads(line))
out_ids = [str(row["id"]) for row in rows]
problems = []
if len(rows) != len(input_ids):
    problems.append(f"row count {len(rows)} != input {len(input_ids)}")
if len(set(out_ids)) != len(out_ids):
    problems.append("duplicate output ids")
missing = set(input_ids) - set(out_ids)
if missing:
    problems.append(f"{len(missing)} input ids missing")
for row in rows:
    codes = row.get("codes")
    if not isinstance(codes, list) or not 1 <= len(codes) <= 3:
        problems.append(f"bad codes field for {row.get('id')}")
        continue
    if len(set(codes)) != len(codes):
        problems.append(f"duplicate codes for {row.get('id')}")
    for code in codes:
        if normalize_code(code) not in valid:
            problems.append(f"invalid code {code} for {row.get('id')}")
print(f"rows={len(rows)} unique_ids={len(set(out_ids))} invalid_codes={sum('invalid' in p for p in problems)}")
print("PROBLEMS" if problems else "CONTRACT_OK")
for problem in problems[:10]:
    print(" -", problem)
