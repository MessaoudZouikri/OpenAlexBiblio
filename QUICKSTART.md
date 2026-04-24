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

For a complete list of every CLI flag accepted by each script and agent, see [docs/getting-started/CLI_REFERENCE.md](docs/getting-started/CLI_REFERENCE.md).

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

Runtime is driven by three hardware tiers. On Apple Silicon, the 128 GB unified memory is
shared between CPU and GPU cores — PyTorch accesses the GPU via the **MPS backend**, which
is faster than CPU but slower than a dedicated NVIDIA CUDA card.

The figures below are **measured** on a real full-corpus run (57,422 records) on an
Apple Mac Pro with Apple Silicon (128 GB unified memory, MPS active).

| Step | CPU only | **Apple Silicon MPS (measured)** | NVIDIA CUDA (estimated) |
|------|----------|----------------------------------|-------------------------|
| data_collection | ~7 min | ~7 min | ~7 min |
| data_cleaning + bibliometric_analysis | < 1 min | < 1 min | < 1 min |
| classification (SPECTER2 + selective LLM) | ~6–8 hours | **~2h 20min** | ~20–30 min |
| network_analysis | ~30 min | **~20 min** | ~10 min |
| visualization + validators | < 2 min | < 2 min | < 2 min |
| **Total (~57K records)** | **~7–9 hours** | **~3 hours** | **~1 hour** |

> **Your results will vary.** Three factors dominate wall-clock time:
>
> - **GPU backend** — SPECTER2 embedding (Stage 2 of classification) is the single biggest
>   cost. Apple Silicon MPS gives a ~3× speedup over CPU; a dedicated NVIDIA CUDA GPU gives
>   ~5–10×. Run `python scripts/check_setup.py` to confirm which backend PyTorch will use
>   on your machine.
> - **Unified vs dedicated memory** — On Apple Silicon, the CPU and GPU share the same
>   physical memory pool (unified memory). There is no separate VRAM limit: the full capacity
>   (e.g. 128 GB) is available to both. On NVIDIA cards, VRAM is separate and limited
>   (typically 8–24 GB); models that exceed VRAM spill to system RAM and slow down sharply.
> - **Internet connection** — data collection fetches from the OpenAlex API and is not
>   affected by GPU or RAM. The 7-minute figure assumes a fast, stable connection; API
>   rate-limit throttling can extend this step.

---

## Test vs. full mode at a glance

| | Test mode | Full mode (~57K) |
|--|-----------|-----------------|
| Records | ~200 (synthetic) | ~57,000 (real) |
| API calls | None (offline) | ~285 pages |
| Runtime — CPU only | ~5 min | ~7–9 hours |
| Runtime — Apple Silicon MPS | ~5 min | **~3 hours** *(measured)* |
| Runtime — NVIDIA CUDA GPU | ~5 min | ~1 hour *(estimated)* |
| Network edges | A few hundred | Hundreds of thousands |
| Output quality | For validation only | Publication-ready |

---

## Setup Troubleshooting

### SPECTER2: `adapters` library required for full quality

SPECTER2 (`allenai/specter2`) uses the **AdapterHub** format, not PEFT/LoRA.
If `check_setup.py` reports the proximity adapter as NOT loaded, install the correct library:

```bash
pip install adapters
```

`peft` alone is not sufficient — it is only used as a last-resort fallback.
Without `adapters`, SPECTER2 runs in degraded mode (base model only), reducing subcategory
accuracy by ~5–8 F1 points and raising the outlier rate from ~5% to ~20–30%.

---

### macOS + external drive: `UnicodeDecodeError` on import

If you store the project on an **external drive** (e.g. exFAT or NTFS volume) and run on
**macOS**, the OS silently creates hidden `._*.py` resource-fork files alongside every Python
file. The `transformers` package reads all `.py` files in its `models/` directory at import
time and chokes on these binary files:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb0 ...
```

This does not happen on Windows or Linux, and does not happen when the project is on an
internal APFS drive.

**Fix — run once after any `pip install`:**

```bash
find .venv -name "._*.py" -delete
```

**Why it recurs:** every `pip install` unpacks a wheel and macOS immediately creates new
resource-fork files. Running the command above after each install keeps the environment clean.

---

## Verify the run completed

After the pipeline finishes, run the consistency check:

```bash
python tests/test_pipeline_consistency.py
```

All 76 checks should pass. Any warning indicates a data quality issue worth investigating
before using the results in a publication.
