import json
import tempfile
import time
import unittest
from pathlib import Path

from coder.catalog import Catalogue, normalize_code
from coder.cli import ModelReranker, _extract_codes, _valid_codes, run
from coder.engine import Coder

ROOT = Path(__file__).resolve().parents[1]
MMS = ROOT / "public/data/mms-2026-01.json"


class CatalogueContractTests(unittest.TestCase):
    def test_normalizes_codes_like_official_scorer(self):
        self.assertEqual(normalize_code(" 1f40.z&XK8G "), "1F40.Z")
        self.assertEqual(normalize_code("CA40.Z/XK8G"), "CA40.Z")

    def test_loads_every_category_in_release(self):
        catalogue = Catalogue.load(MMS)
        self.assertEqual(len(catalogue.codes), 18375)
        self.assertIn("1F40.Z", catalogue.codes)

    def test_rejects_empty_catalogue(self):
        with self.assertRaises(ValueError):
            Catalogue([])


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = Catalogue.load(MMS)
        cls.coder = Coder(cls.catalogue)

    def test_returns_three_distinct_catalogue_codes(self):
        codes, audit = self.coder.predict("Culture confirmed Salmonella Typhi enteric fever.")
        self.assertEqual(len(codes), 3)
        self.assertEqual(len(set(codes)), 3)
        self.assertTrue(all(code in self.catalogue.codes for code in codes))
        self.assertIn("confidence", audit)

    def test_high_signal_clinical_alias_beats_lexical_noise(self):
        codes, _ = self.coder.predict("P. falciparum trophozoites seen. Uncomplicated falciparum malaria.")
        self.assertEqual(codes[0], "1F40.Z")

    def test_negated_finding_does_not_drive_the_code(self):
        note = "32F fever, sore body, runny nose, mild cough x2/7. mRDT NEG. Dx viral URTI, malaria excluded."
        codes, _ = self.coder.predict(note)
        self.assertNotEqual(codes[0], "1F4Z")
        self.assertNotIn("1F4Z", codes)

    def test_negation_does_not_swallow_screening_clauses(self):
        codes, _ = self.coder.predict(
            "11yo boy, painful swelling both sides of jaw in front of the ears x2/7, fever, "
            "pain on chewing. Not vaccinated vs mumps. Testes normal, no headache. Dx mumps."
        )
        self.assertEqual(codes[0], "1D80.0")

    def test_empty_note_still_gets_valid_fallback(self):
        codes, audit = self.coder.predict("")
        self.assertTrue(codes)
        self.assertTrue(all(code in self.catalogue.codes for code in codes))
        self.assertEqual(audit["sources"][codes[0]], "fallback")

    def test_rerank_accepts_postcoordinated_stem_and_drops_unknown(self):
        codes = self.coder.rerank("malaria", ["1F40.Z&XK8G", "NOT-A-CODE"])
        self.assertEqual(codes[0], "1F40.Z")

    def test_lay_term_reaches_the_catalogue_concept(self):
        codes, _ = self.coder.predict("27F vaginal thrush, thick white discharge, no odour.")
        self.assertEqual(codes[0], "1F23.10")

    def test_multiword_concept_beats_unrelated_fever_codes(self):
        codes, _ = self.coder.predict("Fever, cough, and investigation shows respiratory tuberculosis confirmed.")
        self.assertEqual(codes[0], "1B10.0")

    def test_post_negation_suppresses_excluded_diagnosis(self):
        codes, _ = self.coder.predict("Fever and body aches. Malaria excluded on smear. Dengue ruled out.")
        self.assertNotIn("1F40.Z", codes)
        self.assertNotIn("1F4Z", codes)


class TrainingLeakageTests(unittest.TestCase):
    def test_leave_one_out_never_reuses_current_note_label(self):
        catalogue = Catalogue.load(MMS)
        row = {"id": "same-note", "text": "A rare test note", "gold": ["1F40.Z"]}
        coder = Coder(catalogue, [row])
        from coder.engine import _query_tokens

        self.assertEqual(coder._example_matches(_query_tokens(row["text"]), exclude_id=row["id"]), [])

    def test_rerank_passes_note_id_so_dev_label_is_not_leaked(self):
        catalogue = Catalogue.load(MMS)
        row = {"id": "leak-check", "text": "unusual presentation zzz", "gold": ["1F40.Z"]}
        coder = Coder(catalogue, [row])
        with_id = coder.rerank(row["text"], [], note_id="leak-check")
        self.assertNotEqual(with_id[0], "1F40.Z")


class CliContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = Catalogue.load(MMS)
        cls.spare = tuple(sorted(cls.catalogue.codes))

    def test_padding_to_three_is_not_quadratic(self):
        start = time.monotonic()
        for _ in range(200):
            codes = _valid_codes(["1F40.Z"], self.catalogue, self.spare)
            self.assertEqual(len(codes), 3)
        self.assertLess(time.monotonic() - start, 1.0, "padding regressed to a per-note catalogue scan")

    def test_model_parser_handles_prose_and_rejects_garbage(self):
        self.assertEqual(_extract_codes("not-json"), [])
        self.assertEqual(_extract_codes('Sure: {"codes": ["1F40.Z"]} done'), ["1F40.Z"])
        self.assertEqual(_extract_codes('{"other": 1}'), [])
        self.assertEqual(_extract_codes('{"codes": [1, null]}'), [])

    def test_run_writes_one_prediction_per_unique_id_with_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "notes.jsonl"
            output = base / "predictions.jsonl"
            audit = base / "audit.jsonl"
            source.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "x1", "text": "Falciparum malaria confirmed."}),
                        json.dumps({"id": "x2", "text": "Type 2 diabetes mellitus."}),
                        json.dumps({"id": "x1", "text": "duplicate id"}),
                        "{not json",
                        json.dumps({"text": "missing id"}),
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stats = run(str(source), str(output), str(MMS), str(audit), api_enabled=False)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            audits = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["id"] for row in rows], ["x1", "x2"])
            self.assertEqual(len(audits), 2)
            self.assertEqual(stats["duplicates"], 1)
            self.assertEqual(stats["malformed"], 2)
            for row in rows:
                self.assertTrue(1 <= len(row["codes"]) <= 3)
                self.assertTrue(all(code in self.catalogue.codes for code in row["codes"]))

    def test_run_preserves_ids_that_are_not_strings(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "notes.jsonl"
            output = base / "predictions.jsonl"
            source.write_text(json.dumps({"id": 42, "text": "asthma attack"}) + "\n", encoding="utf-8")
            run(str(source), str(output), str(MMS), api_enabled=False)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["id"], "42")


if __name__ == "__main__":
    unittest.main()
