import json
import tempfile
import unittest
from pathlib import Path

from coder.catalog import Catalogue, normalize_code
from coder.engine import Coder
from coder.cli import ModelReranker, _extract_codes, run

ROOT = Path(__file__).resolve().parents[1]
MMS = ROOT / "public/data/mms-2026-01.json"


class CatalogTests(unittest.TestCase):
    def test_catalogue_normalizes_codes_like_official_scorer(self):
        self.assertEqual(normalize_code(" 1f40.z&XK8G "), "1F40.Z")

    def test_catalogue_has_all_18375_categories(self):
        catalogue = Catalogue.load(MMS)
        self.assertEqual(len(catalogue.codes), 18375)
        self.assertIn("1F40.Z", catalogue.codes)

    def test_candidates_are_valid_and_have_up_to_three_distinct_codes(self):
        coder = Coder(Catalogue.load(MMS))
        candidates, evidence = coder.predict("Culture confirmed Salmonella Typhi enteric fever.")
        self.assertEqual(len(candidates), 3)
        self.assertEqual(len(set(candidates)), 3)
        self.assertTrue(all(code in coder.catalogue.codes for code in candidates))
        self.assertTrue(evidence)

    def test_high_signal_clinical_alias_beats_lexical_noise(self):
        coder = Coder(Catalogue.load(MMS))
        candidates, _ = coder.predict("P. falciparum trophozoites seen. Uncomplicated falciparum malaria.")
        self.assertEqual(candidates[0], "1F40.Z")

    def test_leave_one_out_never_reuses_current_note_gold_label(self):
        catalogue = Catalogue.load(MMS)
        row = {"id": "same-note", "text": "A rare test note", "gold": ["1F40.Z"]}
        coder = Coder(catalogue, [row])
        self.assertEqual(coder._example_matches(row["text"], exclude_id=row["id"]), [])

    def test_model_response_parser_rejects_malformed_payload(self):
        self.assertEqual(_extract_codes("not-json"), [])
        self.assertEqual(_extract_codes('{"codes": ["1F40.Z"]}'), ["1F40.Z"])

    def test_model_reranker_only_returns_catalogue_codes(self):
        coder = Coder(Catalogue.load(MMS))
        self.assertEqual(coder.rerank("malaria", ["INVALID", "1F40.Z"])[0], "1F40.Z")


class RunContractTests(unittest.TestCase):
    def test_run_writes_one_valid_prediction_per_input_and_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "notes.jsonl"
            output = base / "predictions.jsonl"
            audit = base / "audit.jsonl"
            source.write_text(
                json.dumps({"id": "x1", "text": "Falciparum malaria confirmed."}) + "\n"
                + json.dumps({"id": "x2", "text": "Type 2 diabetes mellitus."}) + "\n",
                encoding="utf-8",
            )
            run(str(source), str(output), str(MMS), str(audit), api_enabled=False)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            audits = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["id"] for r in rows], ["x1", "x2"])
            self.assertTrue(all(1 <= len(r["codes"]) <= 3 for r in rows))
            self.assertEqual(len(audits), 2)
            valid = Catalogue.load(MMS).codes
            self.assertTrue(all(code in valid for row in rows for code in row["codes"]))

    def test_empty_or_unknown_note_still_gets_valid_fallback(self):
        coder = Coder(Catalogue.load(MMS))
        candidates, _ = coder.predict("")
        self.assertTrue(candidates)
        self.assertTrue(all(code in coder.catalogue.codes for code in candidates))


if __name__ == "__main__":
    unittest.main()
