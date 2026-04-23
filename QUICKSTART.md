# Quick Start — Production Run

> This guide gets you from a fresh clone to a real production run in under 10 minutes of setup.
> For full context on every option, see the [README](README.md).
> For a conceptual walkthrough of what each step does, see the [Tutorial](BIBLIOMETRIC_PIPELINE_TUTORIAL.md).

---

## Prerequisites

Before running:

| Requirement | Check |
|-------------|-------|
| Python 3.10+ virtual environment activated | `python --version` |
| Dependencies installed | `pip install -r requirements.txt` |
| Internet access to OpenAlex | `curl -s https://api.openalex.org/works?per-page=1` |
| SPECTER2 weights (auto-downloaded on first run, ~440 MB) | `python scripts/check_setup.py` |
| Ollama running (optional — Stage 3 LLM disambiguation only) | `ollama list` |

**Verify your environment in one command:**

```bash
python scripts/check_setup.py --verbose
```

This checks Python version, all dependencies, SPECTER2 embedding model availability, Ollama connectivity, and config file validity. Fix any reported issues before proceeding.

---

## Step 1 — Switch `config/config.yaml` to full mode

```yaml
pipeline:
  mode: "full"
  full_max_records: 10000   # Recommended for a first real run (≈25 min download)
                            # Set to null for all ~57,000 matching records (≈3 hrs)
  min_year: 1980
```

**Recommendation:** start with `full_max_records: 10000` rather than `null`. You get a real,
non-synthetic corpus of 10K papers in about 25 minutes, and can validate quality before committing
to the full multi-hour download.

---

## Step 2 — Set your email in `config/openalex.yaml`

```yaml
api:
  polite_email: "your.email@institution.edu"
```

OpenAlex gives identified users 10 requests/second (vs. 5 for anonymous). This halves
your download time at no cost. The email is only used in the HTTP `User-Agent` header.

---

## Step 3 — (Optional) Verify Ollama

The classification agent uses a local LLM **only for Stage 3** — papers where SPECTER2 embedding
confidence falls in the ambiguous 0.60–0.82 range, typically 10–30% of the corpus. If Ollama is
unavailable, those papers fall back to the best embedding result; the pipeline never halts.

```bash
ollama list        # confirm your model is present (e.g. qwen2.5:7b)
ollama ps          # confirm it is loaded or will auto-load on demand
```

If you want to change the model, edit `config/llm.yaml`.

---

## Step 4 — Reset the checkpoint

The pipeline tracks completed steps in `checkpoints/pipeline_state.json`.
If you previously ran a test, this file marks steps as done — delete it so the full run starts fresh.

```bash
rm -f checkpoints/pipeline_state.json
```

---

## Step 5 — Run

```bash
python src/agents/orchestrator.py --config config/config.yaml
```

Progress is logged to the console and to `logs/`. Each step writes its output to disk before
the next one starts, so the run is fully resumable.

---

## Step 6 — Resume if interrupted

The pipeline is checkpoint-based. If it stops at any step, re-run the exact same command:

```bash
python src/agents/orchestrator.py --config config/config.yaml
```

It picks up from the last completed step automatically. To force a restart from a specific step:

```bash
python src/agents/orchestrator.py --config config/config.yaml --from-step classification
```

---

## Step 7 — Find your outputs

```
data/outputs/reports/report.html      ← Open this in a browser for a visual summary
data/outputs/figures/                 ← 6 PNG charts (publication trends, authors, domains…)
data/outputs/networks/                ← GraphML files — open in VOSviewer or Gephi
data/processed/                       ← All JSON metrics + classified_works.parquet
logs/                                  ← Per-agent logs for debugging
```

---

## Expected runtimes

These are approximate wall-clock times on a standard laptop with `full_max_records: 10000`.

| Step | ~Time |
|------|-------|
| data_collection | 15–25 min (API rate limits) |
| data_cleaning + bibliometric_analysis | < 2 min |
| classification (SPECTER2 + selective LLM) | 15–30 min |
| network_analysis | 2–5 min |
| visualization + validators | < 2 min |
| **Total (10K records)** | **~1 hour** |

For the full corpus (~57K records): allow ~3–4 hours for data collection, then ~2 hours for
processing (classification and network analysis dominate). Total wall-clock ~5–6 hours.

---

## Test vs. full mode at a glance

| | Test mode | Full mode (10K) | Full mode (all) |
|--|-----------|-----------------|-----------------|
| Records | ~200 (synthetic) | ~10,000 (real) | ~57,000 (real) |
| API calls | None (offline) | ~50 pages | ~285 pages |
| Runtime | ~5 min | ~1 hr | ~5–6 hrs |
| Network edges | A few hundred | Tens of thousands | Hundreds of thousands |
| Output quality | For validation only | Publication-ready | Publication-ready |

---

## Verify the run completed

After the pipeline finishes, run the consistency check:

```bash
python tests/test_pipeline_consistency.py
```

All 76 checks should pass. Any warning indicates a data quality issue worth investigating
before using the results in a publication.
