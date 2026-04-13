# Bibliometric Pipeline — Populism Studies

A modular, reproducible, multi-agent bibliometric pipeline for the study of
**populism**, **populist**, and **populists** using the [OpenAlex](https://openalex.org) database.

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
│   │   ├── classification.py      ← 2-stage: rule-based → LLM (Ollama)
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

## Setup

### 1. Python environment

```bash
python -m venv .venv
source .venv/bin/activate         # Linux/macOS
.venv\Scripts\activate            # Windows

pip install -r requirements.txt
```

### 2. Local LLM (optional but recommended)

Install [Ollama](https://ollama.ai) and pull a model:
```bash
ollama pull qwen2.5:7b            # Recommended
# or: ollama pull llama3.2:3b     # Lighter alternative
```

Edit `config/llm.yaml` to match your model name if different.

### 3. Configure your email for OpenAlex polite pool

Edit `config/openalex.yaml`:
```yaml
api:
  polite_email: "your.email@institution.edu"
```

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

Classification uses a **two-stage hybrid approach**:

1. **Stage 1 — Rule-based** (deterministic): OpenAlex concept IDs → domain scoring + keyword matching → subcategory. Confidence ≥ 0.6 → final.
2. **Stage 2 — LLM** (semantic, Ollama): triggered when confidence < 0.6 or no concepts available. Structured JSON output with validation. Fallback to `Other/interdisciplinary` on failure.

All LLM outputs are validated against the taxonomy before acceptance.

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

Change `config/config.yaml`:
```yaml
pipeline:
  mode: "full"            # was "test"
  full_max_records: 50000
```

For datasets > 10k records, network construction may require:
```yaml
# In code: bibcoupling min_shared threshold raised to 3-5
# coauthorship min_papers raised to 3
```

---

## Validated Test Run (150 synthetic records)

| Metric | Value |
|--------|-------|
| Corpus h-index | 39 |
| Corpus g-index | 82 |
| Total citations | 7,069 |
| Political Science share | 58.7% |
| Economics share | 26.7% |
| Sociology share | 12.7% |
| Bib. coupling edges | 5,669 |
| Cross-domain bridges | 38 |
| Bradford Zone 1 journals | 4 |
| All pipeline steps | ✅ PASS |
