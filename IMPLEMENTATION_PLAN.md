# ICD-11 Coding System Implementation Plan

> **For Hermes:** Implement sequentially with test-first slices and independent review.

**Goal:** Build a reproducible, Docker-runnable ICD-11 note coder that emits up to three valid MMS codes for every input note, with strong deterministic fallback and optional capped model assistance.

**Architecture:** Package a Python CLI and full ICD-11 MMS release data. Use local BM25 title retrieval, high-signal clinical phrases, and leave-one-out TF-IDF retrieval over the provided labeled notes. Add optional capped OpenAI/Anthropic candidate reranking with strict code validation and offline fallback. Flush each result as it is written. Add an opt-in evidence/confidence audit that does not change scorer output.

**Tech Stack:** Python, standard library-first, Docker Compose, pytest/unittest, supplied `score.py` and MMS 2026-01 data.

---

## Context and assumptions

- Authoritative requirements: `public/BRIEF.md`, `public/score.py`, `public/data/mms-2026-01.json`, and `public/data/dev_notes.jsonl`.
- Intake folder has the public assignment pack but no existing application or Git repository. Keep source at repository root and preserve supplied materials under `public/`.
- Run must work offline without API keys. Only model API calls may be made at runtime when keys exist.
- Do not claim a hidden-set score. Report measured dev score and clearly label any estimate.
- Optional evidence audit is extra output; default predictions remain exactly the scorer's `id` and `codes` contract.

## Sequential tasks

### Task 1: Establish baseline and repository scaffolding

**Files:** `README.md`, `DECISIONS.md`, `Dockerfile`, `docker-compose.yml`, `coder/`, `tests/`.

Capture data shape, score baseline, Python/runtime availability, and preserve exact source data. Initialize Git before implementation, commit each meaningful change, and keep timestamped decisions linked to code commits. Create and verify the final Git bundle.

### Task 2: Input/output and catalogue contracts

Write tests first for JSONL parsing, duplicate/missing IDs, valid-code filtering, maximum-three output, malformed input handling, and safe write-as-you-go behavior. Implement strict catalogue loader and streaming CLI; test exact Docker command contract.

### Task 3: Deterministic hybrid ranker

Write failing tests for diagnosis phrases, negation/unsupported detail, leave-one-out training-note retrieval, multilingual tokens where supported, and invalid-code exclusion. Implement BM25 title retrieval plus similarity search over labeled development notes; exclude the current note by ID during dev evaluation and record retrieval candidate recall@k. Treat unsupported languages as an explicit limitation, not a capability claim.

### Task 4: Optional model enrichment

Write tests for absent keys, valid/invalid JSON, timeouts, candidate-only code selection, 600-call/$4.50 estimated-spend ceilings, and fallback. Use only the supplied provider APIs, their standard HTTPS proxy support, and a 50-minute API deadline; send no note text to third-party services in no-key mode.

### Task 5: Beyond-brief evidence audit

Add `--audit <path>` that records the selected codes, confidence/margin, matched terms or rule, and model/local source for each note. Keep audit separate from scoring output and ensure no note text or secrets leak into logs.

### Task 6: Evaluation and tuning

Run the supplied scorer on all 60 development notes with the model disabled, plus leave-one-out candidate recall. Add a deterministic 1,000-code MMS title-to-code sanity evaluation beyond the 60 notes; label it synthetic, not clinical performance. Report chapter/style breakdown only when sample sizes support it. Do not claim hidden slice-B performance as measured.

### Task 7: Container and clean-clone acceptance

Build from a clean clone and stage grader-style input at `in/notes.jsonl`. Run exact command `docker compose run coder /in/notes.jsonl /out/predictions.jsonl` with keys unset, then verify IDs, schema, distinct valid codes, line count, exact scorer result, writable output mount, and zero missing predictions. Separately check proxy/API environment passthrough when credentials exist.

### Task 8: Independent review and final handoff

Review source, privacy, runtime cap, metric claims, README's one-page/data-provenance/AI-error/hours fields, and the actual bundle. Verify `git bundle verify` and run the bundle clone acceptance test. Use DeepSeek V4.1 Flash through OpenCode Go at maximum thinking for independent plan/code review when available; record any provider failure honestly. Finish with launch prerequisites: Docker, optional provider key, HTTPS proxy if required, API spend confirmation, real hours count, and target recipient for bundle/email.
