# A Bibliometric Analysis Pipeline Using OpenAlex Data

[![Tests](https://github.com/MessaoudZouikri/OpenAlexBiblio/actions/workflows/tests.yml/badge.svg)](https://github.com/MessaoudZouikri/OpenAlexBiblio/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/MessaoudZouikri/OpenAlexBiblio/graph/badge.svg)](https://codecov.io/gh/MessaoudZouikri/OpenAlexBiblio)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-green.svg)](CITATION.cff)

A modular, reproducible, multi-agent bibliometric pipeline for the study of
**populism**, **populist**, and **populists** using the [OpenAlex](https://openalex.org) database.

---

**New user?** → [Quick Start](QUICKSTART.md) (10 min setup)
**Want to understand the pipeline?** → [Tutorial](BIBLIOMETRIC_PIPELINE_TUTORIAL.md) (30 min)
**Full documentation?** → [docs/INDEX.md](docs/INDEX.md)
**Want to contribute?** → [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Repository Contents

This Git repository contains everything needed to install and run the bibliometric pipeline:

### ✅ Included Files
- **Source code** (`src/`): All Python agents and utility functions
- **Configuration templates** (`config/`): YAML files for customization
- **Documentation** (`README.md`, `BIBLIOMETRIC_PIPELINE_TUTORIAL.md`, `agents/*.md`)
- **Agent specifications** (`agents/`): Detailed markdown docs for each component
- **Tests** (`tests/`): Synthetic data generation for testing
- **Setup files** (`requirements.txt`, `pyproject.toml`): Dependencies and packaging
- **Scripts** (`scripts/`): Setup verification utilities

### ❌ Excluded Files (via .gitignore)
- **Data files** (`data/`): Large generated datasets (Parquet, JSON)
- **Logs** (`logs/`): Runtime log files
- **Checkpoints** (`checkpoints/`): Pipeline state files
- **Outputs** (`*.graphml`, `*.png`, `*.html`): Generated visualizations
- **Cache** (`__pycache__/`, `.venv/`): Python bytecode and virtual environments

### 📦 Installation
Users can clone this repository and immediately run the pipeline with their own data collection and analysis.

---

## 📚 Documentation Hub

We maintain comprehensive documentation for different audiences. Visit the **[Documentation Hub](docs/INDEX.md)** to find:

- **👨‍💻 For Developers**: Code quality analysis, architecture review, implementation roadmap
- **🔬 For Researchers**: Domain taxonomy enrichment guides, contribution templates
- **👥 For Users**: Quick reference guides, visualization tutorials, common questions
- **📧 For Citation**: How to cite this package with maintainer information

**Quick-Start Docs** (in root):
- 📖 [README.md](README.md) — You are here
- 🚀 [QUICKSTART.md](QUICKSTART.md) — Installation & first run
- 📝 [BIBLIOMETRIC_PIPELINE_TUTORIAL.md](BIBLIOMETRIC_PIPELINE_TUTORIAL.md) — Hands-on tutorial

---

## Architecture

```
bibliometric_pipeline/
├── agents/                    ← Agent specifications (.md)
│   ├── orchestrator.md
│   ├── data_collection.md
│   ├── data_cleaning.md
│   ├── bibliometric_analysis.md
│   ├── classification.md
│   ├── network_analysis.md
│   └── validation/
│       ├── data_validation.md
│       └── validation_agents.md
├── src/
│   ├── agents/
│   │   ├── orchestrator.py        ← Pipeline coordinator (checkpoints, retry)
│   │   ├── data_collection.py     ← OpenAlex API + dedup + abstract reconstruction
│   │   ├── data_cleaning.py       ← Normalization, derivation, rule-based domain labeling
│   │   ├── bibliometric_analysis.py  ← h/g-index, Lotka, Bradford, co-occurrence
│   │   ├── classification.py      ← 3-stage: rule-based → SPECTER2 embedding → LLM (Ollama)
│   │   ├── network_analysis.py    ← 4 network types + community detection + bridges
│   │   ├── visualization.py       ← 6 publication-ready figures + HTML report
│   │   └── validation/
│   │       └── validators.py      ← 4 independent validators
│   └── utils/
│       ├── openalex_client.py     ← Paginated API client
│       ├── llm_client.py          ← Ollama client + JSON validation
│       ├── io_utils.py            ← Checkpoints, parquet, safe_list helper
│       └── logging_utils.py       ← Structured logging + audit trail
├── config/
│   ├── config.yaml                ← Global pipeline config
│   ├── openalex.yaml              ← Query params + concept→domain map
│   └── llm.yaml                   ← Ollama endpoint + prompt templates
├── tests/
│   └── generate_test_data.py      ← Synthetic OpenAlex data for offline testing
└── requirements.txt
```

### Execution DAG

```
data_collection → validate_raw(D1) → data_cleaning → validate_clean(D2)
   → bibliometric_analysis → validate_statistical
   → classification → validate_classification
   → network_analysis → validate_network
   → visualization
```

---

## Prerequisites

- Python 3.10 or later
- Network access to [api.openalex.org](https://api.openalex.org) (free, no API key required)
- **SPECTER2** citation embedding model — the primary classification engine; downloaded automatically (~440 MB) on first run via `sentence-transformers` (already in `requirements.txt`)
- [Ollama](https://ollama.ai) with a local model — **optional**, used only for Stage 3 LLM disambiguation (~10–30% of papers); the pipeline runs fully without it

---

## Setup

### 1. Python environment

```bash
python -m venv .venv
source .venv/bin/activate         # Linux/macOS
.venv\Scripts\activate            # Windows

pip install -r requirements.txt
```

### 2. Classification models

**SPECTER2** (primary embedding model) is installed automatically via `requirements.txt` (`sentence-transformers`, `torch`, `peft`). It downloads ~440 MB of model weights on first run and auto-detects GPU (CUDA/MPS) or falls back to CPU. No manual setup required.

**Ollama** (local LLM, optional) is used only for Stage 3 — disambiguating the ~10–30% of papers where SPECTER2 confidence is inconclusive. The pipeline runs fully without it.

Install [Ollama](https://ollama.ai) and pull a model:
```bash
ollama pull qwen2.5:7b            # Recommended (~5 GB VRAM)
# or: ollama pull llama3.2:3b     # Lighter alternative
```

Edit `config/llm.yaml` to match your model name if different.

### 3. Configure your email for OpenAlex polite pool

Edit `config/openalex.yaml`:
```yaml
api:
  polite_email: "your.email@institution.edu"
```

**Advanced Query Configuration**:
The pipeline supports boolean search operators for comprehensive literature searches:
```yaml
queries:
  keywords:
    - term: "populism OR populist OR populists OR far-right"  # Multiple search terms
      field: "title_and_abstract.search"
  filters:
    type: "article OR book-chapter OR dissertation OR preprint"  # Multiple types
    from_publication_date: "1980-01-01"
    to_publication_date: null   # null = no upper bound
    open_access_only: false
```

**Supported Publication Types**: article, book-chapter, dissertation, preprint, book, dataset, and more.

### 4. Tune network thresholds (optional)

Edit `config/config.yaml` to override the automatic threshold selection:
```yaml
network:
  min_shared_refs: null   # null = auto-scale by corpus size (recommended)
  min_cocitations: null   # null = auto-scale by corpus size (recommended)
  vos_threshold: 1.0      # Association-strength cutoff for VOSviewer-style filtering
  subfield_analysis: false
```

Auto-scaling rules:

| Corpus size | min_shared_refs / min_cocitations |
|-------------|-----------------------------------|
| < 5,000 records | 2 |
| 5,000 – 14,999 | 3 |
| 15,000 – 29,999 | 5 |
| ≥ 30,000 | 10 |

Override with an explicit integer to fix the threshold regardless of corpus size.

---

## Running the Pipeline

### Full pipeline (production)

```bash
# Ensure you're in the project root
cd bibliometric_pipeline

python src/agents/orchestrator.py --config config/config.yaml
```

### Test mode (synthetic data, no API required)

```bash
python tests/generate_test_data.py --n 150
python src/agents/orchestrator.py --config config/config.yaml
```

### Resume from a specific step

```bash
python src/agents/orchestrator.py --from-step classification
```

### Run individual agents

```bash
python -m src.agents.data_collection   --config config/config.yaml
python -m src.agents.data_cleaning     --config config/config.yaml
python -m src.agents.bibliometric_analysis --config config/config.yaml
python -m src.agents.classification    --config config/config.yaml --llm-config config/llm.yaml
python -m src.agents.network_analysis  --config config/config.yaml
python -m src.agents.visualization     --config config/config.yaml

# Validators
python -m src.agents.validation.validators --validator data --stage D1
python -m src.agents.validation.validators --validator statistical
python -m src.agents.validation.validators --validator classification
python -m src.agents.validation.validators --validator network
```

### Dry run (show steps without executing)

```bash
python src/agents/orchestrator.py --dry-run
```

---

## Outputs

| File | Description |
|------|-------------|
| `data/raw/openalex_raw_*.parquet` | Raw OpenAlex records |
| `data/clean/openalex_clean.parquet` | Cleaned, normalized, enriched records |
| `data/processed/bibliometric_summary.json` | h-index, g-index, totals |
| `data/processed/publication_trends.json` | Annual/decadal counts |
| `data/processed/citation_stats.json` | Full citation distribution |
| `data/processed/top_authors.json` | Author productivity + Lotka's law |
| `data/processed/top_journals.json` | Journal output + Bradford zones |
| `data/processed/classified_works.parquet` | Full dataset + domain + subcategory |
| `data/processed/network_metrics.json` | Graph-level metrics + cross-domain matrix |
| `data/processed/cluster_assignments.parquet` | Node centrality + community IDs |
| `data/processed/interdisciplinary_bridges.json` | Cross-domain bridge nodes |
| `data/outputs/networks/*.graphml` | 4 bibliometric networks |
| `data/outputs/figures/*.png` | 6 publication-ready figures |
| `data/outputs/reports/report.html` | Integrated visual report |
| `logs/pipeline_run_*.json` | Full audit trail per run |
| `checkpoints/pipeline_state.json` | Step completion state |

---

## Domain Taxonomy

| Domain | Subcategories |
|--------|--------------|
| Political Science | comparative_politics, political_theory, electoral_politics, democratic_theory, radical_right, latin_american_politics, european_politics |
| Economics | political_economy, redistribution, trade_globalization, financial_crisis |
| Sociology | social_movements, identity_politics, media_communication, culture_values |
| Other | international_relations, history, psychology, geography, interdisciplinary |

---

## Classification Strategy

Classification uses a **three-stage hybrid approach**, designed to minimise LLM calls while maintaining accuracy:

1. **Stage 1 — Rule-based** (deterministic, zero compute): OpenAlex concept IDs + keyword scoring → domain and subcategory. Papers with confidence ≥ 0.75 are accepted immediately.
2. **Stage 2 — SPECTER2 embedding** (fast, local): Paper content is encoded into a 768-dimensional vector and compared to per-subcategory centroids built from the taxonomy seed texts. Confidence ≥ 0.82 → final; confidence < 0.60 → low-signal, assigned to `Other`.
3. **Stage 3 — LLM** (selective): Triggered only for papers where embedding confidence falls in the ambiguous [0.60–0.82] band — roughly 10–30% of the corpus. Uses a local Ollama model. All outputs are validated against the taxonomy before acceptance; invalid or hallucinated labels fall back to `Other/interdisciplinary`.

Calling an LLM on all 54,000 papers would take many hours of wall-clock time. By reserving Stage 3 for only the ambiguous 10–30% that rules and embeddings could not confidently classify, total classification time is reduced significantly — roughly **15–30 minutes on GPU hardware** (CUDA or Apple MPS) or **2–3 hours on CPU-only** for a 10,000-paper corpus — with no loss of accuracy on the clear cases.

> **Runtime depends on your hardware.** SPECTER2 embedding inference (Stage 2) is the dominant cost and runs 5–10× faster on a GPU. See [QUICKSTART.md](QUICKSTART.md#expected-runtimes) for measured per-step timings.

---

## Anti-Hallucination Design

- All LLM outputs validated (JSON schema + taxonomy membership)
- Invalid responses retry up to 3× then fall back to rule-based
- Classification source tracked per record (`domain_source` column)
- Disagreement between rule and LLM is logged in `classification_notes`
- Statistical validators flag suspiciously uniform LLM confidence

---

## Session Isolation

Each agent is a **stateless processing unit**:
- Input: file path(s) + config
- Output: file path(s)
- No memory between sessions
- Checkpoints in `checkpoints/pipeline_state.json` allow full session reset between steps

---

## Scaling to Full Dataset

See [QUICKSTART.md](QUICKSTART.md) for the complete step-by-step production checklist.

**Minimum changes required in `config/config.yaml`**:
```yaml
pipeline:
  mode: "full"
  full_max_records:10000   # Start here; set null for all ~57,000 records
  min_year: 1980
```

**Always reset the checkpoint before a full run**:
```bash
rm -f checkpoints/pipeline_state.json
python src/agents/orchestrator.py --config config/config.yaml
```

Network thresholds scale automatically with corpus size — no manual code edits required.
See the `network:` section in `config/config.yaml` to override if needed.

---

## Validated Test Run (200 synthetic records)

| Metric | Value |
|--------|-------|
| Corpus h-index | 39 |
| Corpus g-index | 82 |
| Total citations | 7,069 |
| Political Science share | ~58% |
| Economics share | ~27% |
| Sociology share | ~13% |
| Bib. coupling edges | 5,669+ |
| Cross-domain bridges | 38+ |
| Bradford Zone 1 journals | 4 |
| All pipeline steps | ✅ PASS (76/76 checks) |

To reproduce this validation:

```bash
python tests/generate_test_data.py --n 200
rm -f checkpoints/pipeline_state.json
python src/agents/orchestrator.py --config config/config.yaml
python tests/test_pipeline_consistency.py
```

---

## Citation

If you use this pipeline in your research, please cite it:

**BibTeX:**
```bibtex
@software{zouikri2026bibliometric,
  author = {Zouikri, Messaoud},
  title = {A Bibliometric Analysis Pipeline Using OpenAlex Data},
  year = {2026},
  month = {04},
  version = {1.1.0},
  url = {https://github.com/MessaoudZouikri/OpenAlexBiblio},
  contact = {econoPoPop@proton.me}
}
```

**APA:**  
Zouikri, M. (2026). A Bibliometric Analysis Pipeline Using OpenAlex Data (Version 1.1.0) [Software]. 
Retrieved from https://github.com/MessaoudZouikri/OpenAlexBiblio

**GitHub Citation Feature:**  
Use the "Cite this repository" button on GitHub for additional citation formats.

---

## Contact & Feedback

**Maintainer:** Messaoud Zouikri  
**Email:** econoPoPop@proton.me  
**Repository:** https://github.com/MessaoudZouikri/OpenAlexBiblio

**Feedback, bug reports, or collaboration inquiries?** Reach out at **econoPoPop@proton.me**

---

## License

This project is licensed under the **GPL-3.0 License** — see [LICENSE](LICENSE) for details.

