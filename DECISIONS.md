# Decisions log

## 2026-11-10 15:21 IST — offline-first hybrid classifier

- Commit: `3789c0b`
- Decision: combine BM25 retrieval over all 18,375 MMS titles, high-signal diagnosis rules, and leave-one-out retrieval over the supplied labeled notes. Alternatives: title-only lookup, API-only coding, or external training data. Chosen because no-key execution is mandatory and API access is budget/time constrained.
- Evidence: offline development score was 21.2/75; leave-one-out retrieval recall@24 was 33/60. The supplied notes and titles are the only added data. A 1,000-title synthetic test reached 0.891 top-1 and 1.000 top-3, which is catalogue lookup validation, not clinical accuracy.
- Revisit: expand terminology from licensed WHO ICD-11 index data and evaluate on an independent clinical dataset if permitted.

## 2026-11-10 15:21 IST — constrained model reranking

- Commit: `3789c0b`
- Decision: use optional OpenAI/Anthropic API reranking only over a retrieved candidate set; keep model-free fallback, a 600-call cap, estimated $4.50 budget cap, 18-second request timeout, and 50-minute model deadline. Alternatives: full-catalogue prompting or no model API. Candidate-only output limits hallucinations and token cost.
- Evidence: API code path builds and is covered by response parsing and catalogue validation tests, but no API key was used, so real provider behavior/cost remains unmeasured.
- Revisit: benchmark candidate recall and actual provider billing before setting production defaults.

## 2026-11-10 15:21 IST — audit feature

- Commit: `3789c0b`
- Decision: add opt-in JSONL audit with confidence, code evidence, and selection source; do not include full note text or change required prediction rows. Alternative: embed rationale in scorer output. Kept separate to preserve exact grader contract and reduce unnecessary note retention.
- Evidence: contract test confirms one audit row per successfully coded note while predictions contain only `id` and `codes`.
- Revisit: validate confidence calibration on a larger labeled set before presenting confidence to clinicians.

## 2026-11-10 20:07 IST — Docker bind mount compatibility

- Commit: `3789c0b`
- Decision: add SELinux `Z` labels to input/output bind mounts. Alternative: remove labels and rely on host defaults. The exact Compose command first failed to read `/in/notes.jsonl` with `Permission denied`; rerun succeeded after relabeling.
- Evidence: image build succeeded and exact `docker compose run coder /in/notes.jsonl /out/predictions.jsonl` emitted 3 valid rows.
- Revisit: confirm `Z` behavior on the grading host; remove only if that host rejects the option.

## 2026-11-11 11:46 IST — independent review and load-test limits

- Commit: `67dd999`
- Decision: keep implementation moving after review providers failed, but report the review as incomplete rather than claiming approval. Hermes delegation selected unsupported `gpt-6-sol` under the Codex account; direct OpenCode Go `deepseek-v4.1-flash#max` review timed out without a verdict. Self-review amended the plan with bundle checks, candidate leakage exclusion, API caps, and mount/network acceptance.
- Evidence: read-only local tests and the 3-note Docker smoke passed. The 600-note Docker run remained CPU-bound at 151 output rows when checked; stopping its container required approval and was blocked. Do not claim the 60-minute acceptance test passed.
- Revisit: obtain an independent DeepSeek review and rerun the complete 600-note test after the active test container finishes or receives approval to stop.

## 2026-11-11 18:32 IST — full code review found a quadratic hot path

- Commit: `3b15632`
- Decision: fix the padding code before any accuracy work. The old line padded predictions from `(fallback, *sorted(catalogue.codes))` while testing membership against a list that grows to 18,373 entries, so every note paid an O(n^2) scan.
- Evidence: per-stage timing measured `extend` at ~4,300 ms per row against ~5 ms for ranking; the 600-note run reached only ~200 rows in 16 minutes. After the fix 600 notes complete in 2.6 s. The 60-minute cap was at genuine risk.
- Revisit: treat this as the reason perf budgets belong in CI, not in a manual pre-submission check.

## 2026-11-11 18:32 IST — ranking precision changes

- Commit: `3b15632`
- Decision: add negation-aware query tokens (with scope breakers so "not vaccinated vs mumps" keeps mumps), a coverage factor so a one-token coincidence cannot beat a note-explaining candidate, a 0.55 discount for finding chapters 21/23/24, a 0.15 discount for traditional-medicine chapter 26, and parent/child specificity. Alternative considered: train a supervised classifier, rejected because 60 notes cannot support one.
- Evidence: dev score 21.2 to 25.4/75, top-3 0.317 to 0.383, leave-one-out recall@24 33/60 to 38/60. Every change was checked against the supplied scorer, and the negation window was tightened after a 3-token window wrongly suppressed the mumps code in "Not vaccinated vs mumps".
- Revisit: the coverage and chapter priors are priors, not fitted weights; revisit with a larger labelled set and per-chapter calibration.

## 2026-11-11 18:32 IST — scorer-exact normalisation and honesty fixes

- Commit: `3b15632`
- Decision: normalise every candidate with the scorer's own stem rule (split on `&` or `/`, uppercase) instead of `strip().upper()`, so `1F40.Z&XK8G` counts as `1F40.Z` rather than being discarded. Stop fabricating confidence after a model rerank; record the source instead. Pass `note_id` into reranking so the dev note's own gold is never re-added. Parse model JSON with `raw_decode` over balanced objects rather than a greedy regex.
- Evidence: new regression tests cover stem normalisation, malformed-model output, id preservation, duplicate ids, malformed rows, and the leakage path.
- Revisit: confidence is still an uncalibrated heuristic; it should be fitted against observed accuracy before anyone reads it clinically.

## 2026-11-12 13:09 IST — vocabulary layer and concept matching

- Commit: `9db8dc9`
- Decision: add `coder/lexicon.py` (systematic spelling folding, ~60 standard abbreviations, general lay synonyms) applied to catalogue titles and notes alike; add title-bigram and verbatim-title-phrase bonuses; refit BM25 `b` to 1.0 after fixing `avg_len` to use the same length measure as the scoring denominator.
- Options considered: WHO ICD-11 index terms (`id.who.int` returns 401 without a registered client id), a model-generated synonym dump (no key, and unbounded hallucination risk), and a supervised classifier (60 notes cannot support one).
- Evidence (all via `public/score.py`, 60 notes): lexicon 30.0 to 33.3; phrase bonus 30.0 to 32.9; bigrams at weight 8 plus b=1.0 to 35.8; dev score overall 25.4 to 35.8, top-1 0.317 to 0.433, top-3 0.383 to 0.567, leave-one-out recall@24 33/60 to 46/60. Split-half scores 35.8/35.8.
- Revisit: the lexicon is English-only. Non-English notes need translated index terms, which is exactly what the WHO API provides.

## 2026-11-12 13:09 IST — signals measured and rejected

- Commit: `9db8dc9`
- Decision: leave coverage weighting and pseudo-relevance feedback implemented but OFF, and keep the neighbour weight at 12 only because changing it makes no difference.
- Evidence: coverage made ranking worse once the lexicon landed (30.4 with, 33.3 without). Pseudo-relevance feedback dropped the score from 35.8 to 30.4 at weight 1 and 27.5 at weight 2, with unstable halves. `idf_power` above 1.0 collapsed to 19.6. `k1` 2.0 and 0.9 both lost.
- Revisit: PRF may work once candidate recall is higher; it expands a query using titles that are already wrong.

## 2026-11-12 13:09 IST — measured ceiling

- Commit: `9db8dc9`
- Decision: stop tuning lexical constants and document the ceiling instead of chasing decimal points. The gold code is inside the top-64 candidates for 50/60 notes and top-24 for 43/60, so perfect ranking would score about 53.7/75.
- Evidence: `scripts/diagnostics/ceiling.py`. Ten notes have gold sharing almost no vocabulary with the note text, which no lexical ranker can recover.
- Revisit: the remaining headroom needs WHO index terms/synonyms (API credentials) or model reranking over candidates (provider key plus the $6 cap). Both fit the brief and neither is measured here.
