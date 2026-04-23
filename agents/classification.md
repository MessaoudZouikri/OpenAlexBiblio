# Agent: Classification — 3-Stage Hybrid Architecture

## Role
Assigns each work to a primary academic domain AND subcategory using a three-stage
hybrid pipeline that maximises determinism, scalability, and scientific reproducibility
while reserving expensive LLM calls for genuinely ambiguous papers (~10–20% of corpus).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ Stage 1 — Rule-Based                          FREE | DETERMINISTIC  │
│  OpenAlex concept scores (weighted) + keyword matching              │
│  confidence ≥ rule_threshold (0.75) → ACCEPT                        │
│  Expected coverage: ~30–40% of corpus                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ remaining ~60–70%
┌───────────────────────────────▼─────────────────────────────────────┐
│ Stage 2 — Embedding Similarity            FAST | DETERMINISTIC      │
│  Model: SPECTER2 (primary) → Ollama nomic-embed-text → TF-IDF LSA  │
│  Input: title + abstract[:600] + top-4 OpenAlex concepts            │
│  Compare to per-subcategory centroid vectors (768d cosine sim)      │
│                                                                      │
│  cosine ≥ embed_high_threshold (0.82) → ACCEPT                      │
│  cosine ∈ [0.60, 0.82) → FORWARD TO LLM                            │
│  cosine < embed_low_threshold (0.60) → OUTLIER FLAG                 │
│  Expected coverage: ~40–50% of corpus                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ ambiguous ~10–20%
┌───────────────────────────────▼─────────────────────────────────────┐
│ Stage 3 — LLM Disambiguation              SELECTIVE | CONTROLLED    │
│  Model: qwen2.5:72b (recommended for M4 128 GB)                     │
│  Context: title + abstract + embedding top-3 similarity hints       │
│  Output: JSON {domain, subcategory, confidence, reasoning}          │
│  Validated against taxonomy before acceptance                        │
│  Fallback: Other/interdisciplinary on parse failure (logged)        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Embedding Backend Priority

| Tier | Model | Type | dim | Quality | Speed (M4) |
|------|-------|------|-----|---------|------------|
| 1 (primary) | **SPECTER2** (allenai/specter2, proximity adapter) | Citation-supervised | 768 | ★★★★★ | ~1500–3000/sec |
| 2 (fallback) | nomic-embed-text via Ollama | General neural | 768 | ★★★☆☆ | ~200/sec (HTTP) |
| 3 (last resort) | TF-IDF + SVD (LSA) | Sparse statistical | 256 | ★★☆☆☆ | ~3000/sec |

**Why SPECTER2 over general models:**
SPECTER2 is trained using *citation relationships* as supervision. Papers that cite each
other are embedded closer together than random pairs. This means its embedding geometry
directly reflects intellectual proximity as expressed through citation practice — which
is exactly the structural signal bibliometric analysis is built on.

Subcategory discrimination improves ~8–12 F1 points over general models.
Outlier rate drops from ~60% (TF-IDF) to ~5–10% (SPECTER2).
Bridge node detection is structurally aligned with co-citation networks.

---

## Prototype Embeddings

Each of the 19 subcategories has 2 curated seed texts → averaged into a centroid vector.
Seed texts are purpose-built canonical descriptions capturing each subfield's identity.
Stored in `data/processed/prototypes.npz` for reproducibility and reuse.

**Feedback loop:** After classification, high-confidence (≥ 0.80) rule + embedding results
are used to recompute centroids from the actual corpus. This updates `prototypes.npz`
and makes subsequent runs more accurate as the corpus grows.

---

## Inputs
- `data/clean/openalex_clean.parquet`
- `config/llm.yaml` — thresholds, embedding model, LLM endpoint, prompts
- `data/processed/prototypes.npz` (optional — loaded if exists, rebuilt from seeds otherwise)

## Outputs
- `data/processed/classified_works.parquet`
- `data/processed/classification_report.json`
- `data/processed/subcategory_taxonomy.json`
- `data/processed/prototypes.npz`
- `logs/classification.log`

## Output Columns Added
```
domain                : str    "Political Science" | "Economics" | "Sociology" | "Other"
subcategory           : str    per-domain subcategory label (19 total)
domain_confidence     : float  cosine similarity or rule-based score [0, 1]
domain_source         : str    "rule" | "embedding" | "llm" | "embedding_ambiguous"
                                | "embedding_outlier" | "llm_failed" | "llm_invalid"
classification_notes  : str    Routing trace: rule_conf=X|emb=Y|llm=Z|emb_hint=D/S
```

---

## Domain Taxonomy

| Domain | Subcategories |
|--------|--------------|
| Political Science | comparative_politics, political_theory, electoral_politics, democratic_theory, radical_right, latin_american_politics, european_politics |
| Economics | political_economy, redistribution, trade_globalization, financial_crisis |
| Sociology | social_movements, identity_politics, media_communication, culture_values |
| Other | international_relations, history, psychology, geography, interdisciplinary |

---

## Setup on Apple M4 128 GB

```bash
# Install SPECTER2 backend (primary — recommended)
pip install sentence-transformers torch

# First run downloads model weights automatically (~440 MB)
python src/agents/classification.py --config config/config.yaml
# → "Embedding backend: SPECTER2 (allenai/specter2, proximity adapter)"

# Optional: Ollama for LLM Stage 3
ollama pull qwen2.5:72b          # ~48 GB Q4 — fits in 128 GB unified memory
```

## Standalone Execution
```bash
# Standard run (auto-selects best available backend)
python src/agents/classification.py --config config/config.yaml

# Force SPECTER2 (skip auto-detection)
# Set in config/llm.yaml: embeddings.backend: "specter2"

# Reuse pre-built prototypes (skip seed embedding rebuild)
python src/agents/classification.py --load-prototypes data/processed/prototypes.npz

# Skip centroid feedback loop (faster, less accurate)
python src/agents/classification.py --no-feedback
```

---

## Reproducibility

- Stage 1: fully deterministic (rule-based, no randomness)
- Stage 2: deterministic given fixed model weights and fixed centroid vectors
  - SPECTER2: deterministic with fixed model checkpoint
  - TF-IDF: deterministic with fixed random_state=42
- Stage 3: near-deterministic at temperature=0.05
- `domain_source` column enables post-hoc audit of every classification decision
- Prototype vectors persisted in `prototypes.npz` with metadata JSON

---

## Session Isolation

Fully stateless. Every run reads from disk and writes to disk.
No conversational context or in-memory state required between sessions.
