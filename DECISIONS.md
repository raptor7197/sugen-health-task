# Decisions log

## 2026-11-11 14:25 IST — offline-first hybrid classifier

- Commit: `c483d76cdac4c72861aad63c0eacea47367efb84`
- Decision: combine BM25 retrieval over all 18,375 MMS titles, high-signal diagnosis rules, and leave-one-out retrieval over the supplied labeled notes. Alternatives: title-only lookup, API-only coding, or external training data. Chosen because no-key execution is mandatory and API access is budget/time constrained.
- Evidence: offline development score was 21.2/75; leave-one-out retrieval recall@24 was 33/60. The supplied notes and titles are the only added data. A 1,000-title synthetic test reached 0.891 top-1 and 1.000 top-3, which is catalogue lookup validation, not clinical accuracy.
- Revisit: expand terminology from licensed WHO ICD-11 index data and evaluate on an independent clinical dataset if permitted.

## 2026-11-11 14:25 IST — constrained model reranking

- Commit: `c483d76cdac4c72861aad63c0eacea47367efb84`
- Decision: use optional OpenAI/Anthropic API reranking only over a retrieved candidate set; keep model-free fallback, a 600-call cap, estimated $4.50 budget cap, 18-second request timeout, and 50-minute model deadline. Alternatives: full-catalogue prompting or no model API. Candidate-only output limits hallucinations and token cost.
- Evidence: API code path builds and is covered by response parsing and catalogue validation tests, but no API key was used, so real provider behavior/cost remains unmeasured.
- Revisit: benchmark candidate recall and actual provider billing before setting production defaults.

## 2026-11-11 14:25 IST — audit feature

- Commit: `c483d76cdac4c72861aad63c0eacea47367efb84`
- Decision: add opt-in JSONL audit with confidence, code evidence, and selection source; do not include full note text or change required prediction rows. Alternative: embed rationale in scorer output. Kept separate to preserve exact grader contract and reduce unnecessary note retention.
- Evidence: contract test confirms one audit row per successfully coded note while predictions contain only `id` and `codes`.
- Revisit: validate confidence calibration on a larger labeled set before presenting confidence to clinicians.

## 2026-11-11 14:25 IST — Docker bind mount compatibility

- Commit: `c483d76cdac4c72861aad63c0eacea47367efb84`
- Decision: add SELinux `Z` labels to input/output bind mounts. Alternative: remove labels and rely on host defaults. The exact Compose command first failed to read `/in/notes.jsonl` with `Permission denied`; rerun succeeded after relabeling.
- Evidence: image build succeeded and exact `docker compose run coder /in/notes.jsonl /out/predictions.jsonl` emitted 3 valid rows.
- Revisit: confirm `Z` behavior on the grading host; remove only if that host rejects the option.

## 2026-11-11 14:50 IST — independent review and load-test limits

- Commit: `e483dae445097ff6cd2ba3766fd3fc1095cc8e6b`
- Decision: keep implementation moving after review providers failed, but report the review as incomplete rather than claiming approval. Hermes delegation selected unsupported `gpt-6-sol` under the Codex account; direct OpenCode Go `deepseek-v4.1-flash#max` review timed out without a verdict. Self-review amended the plan with bundle checks, candidate leakage exclusion, API caps, and mount/network acceptance.
- Evidence: read-only local tests and the 3-note Docker smoke passed. The 600-note Docker run remained CPU-bound at 151 output rows when checked; stopping its container required approval and was blocked. Do not claim the 60-minute acceptance test passed.
- Revisit: obtain an independent DeepSeek review and rerun the complete 600-note test after the active test container finishes or receives approval to stop.
