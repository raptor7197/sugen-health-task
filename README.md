# ICD-11 outpatient coder

Offline-first Python batch system for ICD-11 MMS 2026-01. It reads JSONL notes and writes up to three valid MMS codes per ID. Local BM25 title retrieval, high-signal clinical rules, and leave-one-out retrieval over the supplied 60-note training set run without keys. Optional OpenAI or Anthropic reranking uses only retrieved candidates and falls back locally on errors. No non-model runtime network access is needed.

## Run

Put input at `in/notes.jsonl`, then run:

```sh
docker compose build
docker compose run coder /in/notes.jsonl /out/predictions.jsonl
```

No-key mode always works. Optional API setup: export `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` and `HTTPS_PROXY` when required. Defaults: `gpt-4o-mini`, 600-call ceiling, estimated $4.50 budget ceiling, 18-second request timeout, 50-minute model-call deadline. Set `CODER_PROVIDER`, `CODER_MODEL`, `CODER_MAX_MODEL_CALLS`, `CODER_MAX_USD`, or `CODER_MODEL_DEADLINE_SECONDS` to override. Cost ceiling uses a conservative estimate, not provider-billed usage; verify actual spend before grading. API calls send note text to the selected provider. Do not use real patient data without required privacy, consent, retention, and security approvals.

Add `--audit` after the two paths to write `<output>.audit.jsonl` with code confidence, evidence tokens, and decision source. Audit stays separate from scorer output and does not include full note text.

## Evaluation

The supplied `public/score.py` reports offline dev score **21.2 / 75** (60 notes; top-1 0.267, top-3 0.317; zero missing or invalid codes). `scripts/evaluate_retrieval.py` reports leave-one-out candidate recall@24 of **33/60**. `scripts/evaluate_catalogue_titles.py` runs a deterministic 1,000-category title-to-code sanity check; it is not clinical accuracy. No hidden slice-B data exists here. Hidden score estimate: **about 30/100, low confidence**; non-English and broad chapter coverage remain weak, and API-assisted performance is unmeasured.

## Data and decisions

No external data added. MMS 2026-01, development notes, and scorer come from the supplied assignment pack. `DECISIONS.md` records implementation choices. The AI implementation initially ranked noise above confirmed falciparum malaria because title retrieval outweighed a high-signal diagnosis rule; a failing regression test exposed it, and clinical-rule priority fixed it.

Hours spent: [enter your actual total before submission]
