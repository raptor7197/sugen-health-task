import random
from pathlib import Path
from coder.catalog import Catalogue
from coder.engine import Coder

root = Path(__file__).resolve().parents[1]
catalogue = Catalogue.load(root / "public/data/mms-2026-01.json")
coder = Coder(catalogue)
rows = list(catalogue.categories.values())
selected = random.Random(20261111).sample(rows, min(1000, len(rows)))
hits = {1: 0, 3: 0}
for category in selected:
    ranked = coder._rank(category.title)
    predictions = [item.code for item in ranked[:3]]
    hits[1] += bool(predictions and predictions[0] == category.code)
    hits[3] += category.code in predictions
print(f"synthetic_title_queries={len(selected)} seed=20261111")
print(f"title_exact_top1={hits[1] / len(selected):.3f}")
print(f"title_exact_top3={hits[3] / len(selected):.3f}")
print("This sanity check is not a clinical-accuracy estimate.")
