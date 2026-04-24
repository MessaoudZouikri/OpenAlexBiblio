# CLI Reference

Complete listing of every command-line flag accepted by the pipeline.
For a narrative walkthrough, see [QUICKSTART.md](../../QUICKSTART.md).

---

## How the checkpoint system works

**This is the most important thing to understand before running the orchestrator.**

Every time a pipeline step finishes successfully, its name is written to
`checkpoints/pipeline_state.json`. The next time you run the orchestrator,
it reads that file and **skips any step already listed there** — printing
`[CACHED] step_name — already complete` in the log.

This means:

- Running `python src/agents/orchestrator.py` a second time **does nothing**
  if all steps completed on the first run. No files are overwritten, no
  figures are regenerated. The command exits cleanly in seconds.
- If you add a new feature (e.g. a new figure in `visualization.py`) and
  want to see it, you must explicitly tell the orchestrator to re-run that
  step — it will not detect code changes on its own.

### Choosing the right command

| Situation | Command |
|---|---|
| First-ever run | `python src/agents/orchestrator.py` |
| Re-run **visualization only** (fastest) | `python src/agents/visualization.py --config config/config.yaml` |
| Re-run visualization via orchestrator | `python src/agents/orchestrator.py --from-step visualization` |
| Re-run from network analysis onward | `python src/agents/orchestrator.py --from-step network_analysis` |
| Re-run everything (full fresh run) | `python src/agents/orchestrator.py --force` |
| Pipeline was interrupted mid-way | `python src/agents/orchestrator.py` (resumes automatically) |
| See what would run without executing | `python src/agents/orchestrator.py --dry-run` |

### `--from-step` vs `--force`

- `--from-step STEP` — resets the checkpoint **from that step and all downstream
  steps**, then runs from there. Steps before it are untouched and still cached.
  Use this when you only changed or want to refresh a specific part of the pipeline.

- `--force` — ignores the checkpoint entirely and re-runs **every** step from the
  beginning. Use this only when you want a completely fresh pipeline run (e.g.
  after a data update or a config change that affects early steps). Note that
  `data_collection` re-fetches from the OpenAlex API and can take hours.

### Running agents directly (bypass the orchestrator)

Any agent can be run on its own without touching the checkpoint. This is the
fastest way to regenerate a single output:

```bash
# Regenerate all figures and reports without touching the checkpoint
python src/agents/visualization.py --config config/config.yaml

# Recompute bibliometric stats only
python src/agents/bibliometric_analysis.py --config config/config.yaml

# Recompute network metrics only
python src/agents/network_analysis.py --config config/config.yaml
```

Running an agent directly **does not update the checkpoint** — it only writes
its output files. Use this for iteration and exploration; use the orchestrator
for reproducible, audited runs.

---

## Orchestrator — main entry point

```
python src/agents/orchestrator.py [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Path to the main config file |
| `--from-step STEP` | *(start of pipeline)* | Start (or re-start) execution from a named step; all downstream checkpoints are reset |
| `--dry-run` | off | Print the execution plan without running any step |
| `--force` | off | Re-run every step even if already marked completed in the checkpoint |
| `--list-steps` | off | Print the ordered list of step names and exit |

**Available step names** (in execution order):

```
data_collection
validate_raw
data_cleaning
validate_clean
bibliometric_analysis
validate_statistical
classification
validate_classification
network_analysis
validate_network
visualization
```

**Examples:**

```bash
# Full run
python src/agents/orchestrator.py

# Preview what will run without executing
python src/agents/orchestrator.py --dry-run

# Resume from a specific step after an interruption
python src/agents/orchestrator.py --from-step classification

# Force a full re-run ignoring checkpoints
python src/agents/orchestrator.py --force

# List available step names (useful with --from-step)
python src/agents/orchestrator.py --list-steps
```

---

## Individual agents

Each agent can also be run standalone, independently of the orchestrator.
Useful for re-running a single step or debugging.

### Data collection

```
python -m src.agents.data_collection [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Main config |
| `--openalex-config PATH` | `config/openalex.yaml` | OpenAlex API config |
| `--test` | off | Fetch a small slice of records only (for smoke-testing without a full API run) |

---

### Data cleaning

```
python -m src.agents.data_cleaning [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Main config |
| `--input PATH` | *(auto-detected)* | Override the raw parquet path; useful when testing with a custom input file |

---

### Bibliometric analysis

```
python -m src.agents.bibliometric_analysis [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Main config |

---

### Classification

```
python -m src.agents.classification [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Main config |
| `--llm-config PATH` | `config/llm.yaml` | LLM config (model, endpoint, temperature) |
| `--no-feedback` | off | Disable the LLM feedback loop; classification uses SPECTER2 only |
| `--load-prototypes PATH` | *(recomputed)* | Load pre-computed prototype embeddings from a file, skipping the prototype-building step |

---

### Network analysis

```
python -m src.agents.network_analysis [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Main config |
| `--vos_threshold FLOAT` | *(from config)* | Minimum association strength threshold (VOSviewer style); overrides the value in config |
| `--subfield_analysis` | off | Run an additional sub-field level network analysis on top of the main domain network |

---

### Visualization

```
python -m src.agents.visualization [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | `config/config.yaml` | Main config |
| `--llm-config PATH` | `config/llm.yaml` | LLM config |

---

### Validators

```
python -m src.agents.validation.validators --validator VALIDATOR [OPTIONS]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--validator` | yes | Which validator to run: `data`, `statistical`, `classification`, `network` |
| `--stage` | no (default `D1`) | For `--validator data` only: `D1` validates raw data, `D2` validates cleaned data |
| `--config PATH` | no | Main config (default `config/config.yaml`) |

**Examples:**

```bash
python -m src.agents.validation.validators --validator data --stage D1
python -m src.agents.validation.validators --validator data --stage D2
python -m src.agents.validation.validators --validator statistical
python -m src.agents.validation.validators --validator classification
python -m src.agents.validation.validators --validator network
```

---

## Scripts

### check_setup.py — environment diagnostic

```
python scripts/check_setup.py [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--verbose`, `-v` | off | Show extended output (embedding shapes, sample norms, model details) |
| `--fix` | off | Attempt to install missing dependencies automatically (`pip install -r requirements.txt`) |
| `--ollama-endpoint URL` | `http://localhost:11434` | Custom Ollama server URL (useful when Ollama runs on a remote host or non-default port) |

Run this before every first run on a new machine:

```bash
python scripts/check_setup.py --verbose
```

---

### update_taxonomy.py — apply researcher feedback

```
python scripts/update_taxonomy.py --input FILE [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input PATH`, `-i PATH` | *(required)* | CSV file with taxonomy changes (columns: Action, Domain, Subcategory, Keywords, Seed Texts, Rationale) |
| `--dry-run` | **on by default** | Preview all changes without writing anything |
| `--apply` | off | Actually write changes to `src/utils/taxonomy.py` and `src/utils/prototype_store.py` |

Always preview before applying:

```bash
# Step 1 — inspect what will change
python scripts/update_taxonomy.py --input feedback.csv

# Step 2 — apply when satisfied
python scripts/update_taxonomy.py --input feedback.csv --apply
```
