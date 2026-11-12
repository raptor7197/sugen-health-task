# ICD-11 outpatient coder

Batch system that maps outpatient consultation notes to ICD-11 MMS 2026-01 codes. It is offline-first: the local ranker produces every prediction, and the OpenAI/Anthropic adapter is optional. Every input id receives up to three distinct, catalogue-valid codes.

## Run

Put input at `in/notes.jsonl`, then run:

```sh
docker compose build
docker compose run coder /in/notes.jsonl /out/predictions.jsonl
```

With no API key the local path alone answers every note. Optional model reranking activates when `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set; `HTTPS_PROXY` is honoured by both SDKs. Bounds: `CODER_MODEL_DEADLINE_SECONDS` (default 3000), `CODER_MAX_MODEL_CALLS` (600), `CODER_MAX_USD` (4.50, an estimate, not provider billing). `CODER_PROVIDER` and `CODER_MODEL` override provider/model selection. API calls send note text to the chosen provider; do not run real patient data through it without the privacy and security approvals your organisation requires.

`--audit [PATH]` writes a sidecar JSONL with per-note confidence, evidence tokens, and decision source. It never changes the scored output and is off by default.

## How it ranks

1. **Clinical vocabulary layer** (`coder/lexicon.py`): systematic spelling folding (anaemia/anemia, oedema/edema, diarrhoea/diarrhea), about 60 standard abbreviations, and general lay synonyms (thrush to candidiasis, piles to haemorrhoid, shingles to zoster). Applied to both the catalogue titles and the note, so lay wording reaches catalogue vocabulary. Nothing here is derived from the labelled notes.
2. **BM25 over all 18,375 titles** with the assessment block (`A:`, `Dx:`, `Imp:`) weighted, and scoped negation so "malaria excluded" and "not vaccinated vs mumps" are handled correctly.
3. **Concept matching**: title bigrams and verbatim title phrases get explicit credit, so a multi-word diagnosis beats a single shared symptom word.
4. **Chapter priors**: findings (21/23/24) and traditional-medicine patterns (26) cannot outrank a documented disease.
5. **Parent/child specificity**, so a parent never beats its own child.
6. **Similarity to the supplied labelled notes**, excluding the note's own id.
7. Optional model rerank restricted to the retrieved candidates.

Tunable signals (coverage weighting, pseudo-relevance feedback, neighbour weight, tf saturation) exist in the code but are **off or at their measured value** because they lost on the dev set; the experiment scripts that decided this are in `scripts/experiments/`.

## Evaluation

```sh
python3 public/score.py --gold public/data/dev_notes.jsonl \
  --pred out/dev_predictions.jsonl --mms public/data/mms-2026-01.json
```

- Offline dev score: **35.8 / 75** (60 notes, top-1 0.433, top-3 0.567, zero missing, zero invalid).
- Leave-one-out candidate recall@24: **46/60**.
- Measured ceiling: the gold code appears in the top-24 candidates for only **43/60** notes, so even perfect ranking tops out near **53.7/75** with this retrieval.
- Runtime: 600 notes in ~12.6 s locally, far inside the 60-minute cap.
- `scripts/validate_predictions.py` checks the grader contract: every input id present, unique ids, 1-3 distinct catalogue-valid codes per row.

### Why the score is not higher

The scorer pays only for exact codes, two thirds of it on top-1, over 18,375 categories. A bag-of-words ranker over titles cannot bridge a note that says "trophozoites seen, mild splenic tip" to the code "Malaria due to Plasmodium falciparum": for 10 of the 60 dev notes the gold category shares almost no vocabulary with the note. That gap is semantic, not lexical. The two honest ways to close it are WHO's ICD-11 index terms/synonyms (the `id.who.int` API answers 401 without a registered client id, so it needs credentials) and model reranking over the candidates (needs a provider key plus the budget cap). Both are allowed by the brief; neither is exercised here.

Hidden slice-B performance is unmeasured. The 60 dev notes are one clinic's style; non-English notes and most chapters remain weakly covered, and no API-assisted run has been costed. Estimate: **~40/100, low confidence**.

## Data and decisions

No external dataset added: MMS 2026-01, dev notes, and the scorer all come from the assignment pack. The vocabulary layer is general clinical terminology written into `coder/lexicon.py`. `DECISIONS.md` logs each choice with its commit and the measurement that decided it.

Two places the tooling was wrong, both caught by measurement:

- A "pad to three codes" step filtered a sorted 18,375-code catalogue against a growing list: quadratic, 4.3 s per note, would have blown the runtime cap. Per-stage timing found it.
- The spelling fold stripped a trailing "s" from any word, turning "tuberculosis" into "tuberculosi" and "pertussis" into "pertussi". A lexicon test caught it.

Hours spent: [enter your actual total before submission]
