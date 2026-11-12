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

## 2026-11-12 21:18 IST — who index terms, and the connection that made them affordable

- Commit: `fd1b772`
- Decision: fetch index terms for all 18,375 categories from the WHO ICD API (client id supplied by the user, credentials kept out of the repository) and ship them as one gzipped artefact built at build time. Options considered: a model-generated synonym dump (no key, hallucination risk), UMLS (needs a licence application), and staying title-only at 35.8.
- Evidence: dev score 35.8 to 44.2, top-1 0.433 to 0.533, top-3 0.567 to 0.700; gold in the top-24 candidates rose from 43/60 to 48/60, so the ceiling moved from 53.7 to 60.0. Fetch was 703 ms per request with one connection each (215 minutes projected); reusing one connection per thread cut it to 224 ms and completed 18,375 codes in six minutes at six threads, with no failures.
- Revisit: french, portuguese, arabic and chinese are the same one-command extension; they were deliberately not fetched because the brief caps the deliverable and the Spanish probe already showed the mechanism works.

## 2026-11-12 21:20 IST — phrase credit retuned, stability preferred over the peak

- Commit: `fd1b772`
- Decision: set phrase credit to 20 with `b = 1.0` rather than the higher-scoring 16-with-`b = 0.9`. Options: 12, 16, 20, 30, and the `b`/`k1` combinations around them.
- Evidence: 16 with `b = 0.9` scored 45.8 but split 40.8/50.8 across halves; 20 with `b = 1.0` scored 44.2 and split 43.3/45.0. One note is 1.5 points on 60 notes, so a 1.6-point peak on a 10-point spread is noise.
- Revisit: re-tune on a larger labelled set where half-split spread is meaningful.

## 2026-11-12 21:24 IST — spanish terms, and what they bought

- Commit: `fd1b772`
- Decision: ship english and spanish index terms together in one artefact rather than english only. Spanish is a proxy for the brief's "not always in english" slice; the same fetch returns any WHO language, so this is the mechanism, not a claim about the hidden distribution.
- Evidence: ten dev notes hand-translated into spanish, scored against their original gold codes: top-1 0.20 with english terms only, top-3 0.20; top-1 0.60, top-3 0.70 with spanish terms added. English dev score was unaffected by the merge (44.2).
- Revisit: the sample is ten notes; treat it as evidence the mechanism works, not a slice-b score.

## 2026-11-12 21:30 IST — the terms loader only worked for absolute paths

- Commit: `fd1b772`
- Decision: resolve the mms path before deriving the artefact location, so relative and absolute invocations load the same file. Caught before shipping, not after.
- Evidence: the CLI scored 35.0 while the experiment harness, which passed the term map directly, scored 44.2. The difference was the loader computing `public/data/` instead of the repository root for a relative path; `Path.resolve()` fixed it and the CLI then reproduced 44.2 exactly.
- Revisit: none needed, but the mismatch is why the CLI and the harness must be cross-checked rather than trusting one of them.

## 2026-11-12 21:45 IST — scope cut back to the brief

- Commit: this commit (`docs: cut readme to the brief's one page and log the terminology work`)
- Decision: stop fetching extra languages and cut the README back to the brief's one-page limit. The README had grown to 12 KB across ten sections, which the brief does not allow; extra languages were the same one-command extension as Spanish, not new capability.
- Evidence: brief section "Deliverable" item 2 says "A README of one page at most" and lists four required points; the rewritten file covers those four plus a mermaid diagram and the run command.
- Revisit: if the reviewer wants depth, the reasoning lives in this log and in `scripts/experiments/`, not in the README.

## 2026-11-12 22:20 IST — precision fixes worth 4.1 points

- Commit: `bdce1ed`
- Decision: weight a shared title bigram by how rare that pair is across the release, raise phrase credit to 30, loosen length normalisation to `b = 0.9`, and keep 16 phrases per code in the matcher. Options: leave the additive weights alone at 44.2, or fit weights per feature.
- Evidence: bigram rarity 44.2 to 45.0; phrase credit 30 with `b = 0.9` to 47.5; 16 phrases to 48.3, split halves 46.7/50.0. Diagnosis first: of the nine notes losing with gold already in the top-24, three were won by a single generic bigram ("death from direct obstetric cause" over gestational diabetes) and two by a short phrase match ("torticollis" over mumps).
- Revisit: rarity normalisation is a proxy for information content; a proper idf over pairs would be the principled version.

## 2026-11-12 22:24 IST — what lost this round

- Commit: `bdce1ed`
- Decision: reject four further ideas rather than ship them.
- Evidence: phrase credit scaled down for short phrases 44.2 to 40.8 (short phrases were doing real work); multiplying the phrase bonus when the phrase sits inside the assessment span 47.5 to 45.8 to 46.7 at 1.5x and 2x; rules scored relative to the current top rather than an absolute 100 was exactly neutral, so the absolute stays; top 128 candidates instead of 64 scored 46.2; neighbour weight and anchor weight moved nothing at all.
- Revisit: the anchor-span idea should work with a better span detector than "the line after `dx:`"; it was measured on a weak implementation of the idea.
