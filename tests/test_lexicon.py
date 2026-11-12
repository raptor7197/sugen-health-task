import unittest

from coder.lexicon import canonical_tokens


class LexiconTests(unittest.TestCase):
    def test_spelling_variants_fold_to_one_token(self):
        folds = [
            ("anaemia", "anemia"),
            ("oedema", "edema"),
            ("diarrhoea", "diarrhea"),
            ("haemorrhage", "hemorrhage"),
            ("dysmenorrhoea", "dysmenorrhea"),
            ("tumour", "tumor"),
        ]
        for british, american in folds:
            self.assertEqual(canonical_tokens(british), canonical_tokens(american), (british, american))

    def test_abbreviations_expand_to_clinical_terms(self):
        self.assertIn("hypertension", canonical_tokens("pt has HTN"))
        self.assertIn("tuberculosis", canonical_tokens("PTB with cough"))

    def test_lay_terms_map_to_catalogue_vocabulary(self):
        # Canonical tokens are the folded forms the index uses, so British and American
        # spellings of the catalogue title converge on the same token.
        self.assertIn("candidiasis", canonical_tokens("vaginal thrush"))
        self.assertIn("hemorrhoid", canonical_tokens("piles for years"))
        self.assertIn("zoster", canonical_tokens("shingles on the flank"))

    def test_plural_and_case_are_normalised(self):
        self.assertEqual(canonical_tokens("Fevers"), canonical_tokens("fever"))

    def test_unknown_words_survive_untouched(self):
        self.assertIn("nyama", canonical_tokens("nyama choma"))


if __name__ == "__main__":
    unittest.main()
