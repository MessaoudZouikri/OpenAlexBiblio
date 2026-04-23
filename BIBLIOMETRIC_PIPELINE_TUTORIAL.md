# Bibliometric Pipeline Tutorial: Understanding Populism Research Through Data

> **Navigation**: [Quick Start](QUICKSTART.md) — [README](README.md) — [Agent Specs](agents/)

## Table of Contents
1. [Before You Start](#before-you-start)
2. [Introduction](#introduction)
3. [Pipeline Architecture Overview](#pipeline-architecture-overview)
4. [Step-by-Step Function Guide](#step-by-step-function-guide)
5. [Reading Your Results](#reading-your-results)
6. [Analysis Objectives and Function Applications](#analysis-objectives-and-function-applications)
7. [Practical Examples](#practical-examples)
8. [Troubleshooting and Best Practices](#troubleshooting-and-best-practices)

---

## Before You Start

**If you just want to run the pipeline**, skip this tutorial and go to [QUICKSTART.md](QUICKSTART.md).
Come back here when you want to understand *what the pipeline is doing and why*.

**If this is your first contact with bibliometrics**, start at the [Introduction](#introduction) below
and read from top to bottom — it builds concepts progressively.

**If you already know bibliometrics** and want to understand how a specific component works,
jump directly to the [Step-by-Step Function Guide](#step-by-step-function-guide).

---

## Introduction

Welcome to **A Bibliometric Analysis Pipeline Using OpenAlex Data**! This tutorial will guide you through understanding how this automated system collects, processes, and analyzes academic research on populism using the OpenAlex database.

### What is Bibliometric Analysis?
Bibliometric analysis studies patterns in academic literature through quantitative methods. For populism research, this means:
- **Tracking publication trends** over time
- **Identifying influential authors and journals**
- **Mapping research networks** and collaborations
- **Understanding citation patterns** and knowledge flows
- **Classifying research** into academic domains

### Who Should Use This Tutorial?
- **Researchers** studying populism who want to understand research patterns
- **Students** learning about bibliometric methods
- **Policy analysts** tracking academic discourse on populism
- **Librarians and information specialists** managing populism literature
- **Technical users** implementing or modifying the pipeline

### What You'll Learn
By the end of this tutorial, you'll understand:
- How the pipeline transforms raw data into insights
- What each function does and why it matters
- How to interpret the results for your research
- How to adapt the pipeline for other research topics

---

## Pipeline Architecture Overview

The pipeline is organized as a **modular workflow** with 11 execution steps — 6 processing agents and 5 validation checkpoints — each handled by specialized Python programs. Think of it as an assembly line where each station adds value to the data.

### The 11-Step Process

```
1. Data Collection → 2. Raw Data Validation → 3. Data Cleaning → 4. Clean Data Validation
   → 5. Bibliometric Analysis → 6. Statistical Validation
   → 7. Classification → 8. Classification Validation
   → 9. Network Analysis → 10. Network Validation
   → 11. Visualization
```

### Key Components

#### **Agents** (Main Processing Units)
- **Orchestrator**: Pipeline coordinator and checkpoint manager
- **Data Collection**: Retrieves research papers from OpenAlex
- **Data Cleaning**: Normalizes and enriches the raw data
- **Bibliometric Analysis**: Computes productivity and citation metrics
- **Classification**: Categorizes papers by academic domain and specialty
- **Network Analysis**: Builds and analyzes research collaboration networks
- **Visualization**: Creates publication-ready charts and reports
- **Validation**: Quality control at each stage

#### **Utilities** (Supporting Functions)
- **OpenAlex Client**: Handles API communication with the database
- **LLM Client**: Manages AI-powered classification
- **I/O Utils**: File management and data persistence
- **Logging Utils**: Audit trails and progress tracking

---

## Step-by-Step Function Guide

### 1. Orchestrator Agent (`orchestrator.py`)

**Purpose**: The "traffic controller" that manages the entire pipeline execution.

#### Key Functions:

**`run_pipeline()`**
- **What it does**: Executes the complete workflow from start to finish
- **Why it matters**: Ensures steps run in the correct order and handles failures gracefully
- **For users**: Provides a single command to run everything

**`run_step()`**
- **What it does**: Executes individual pipeline steps via Python modules
- **Parameters**: Step name, module path, configuration, logging
- **For users**: Enables partial re-runs if something fails midway

**`get_start_index()` & `reset_from_step()`**
- **What it does**: Allows resuming pipeline execution from any point
- **Use case**: If network analysis fails, you can restart just from that step

### 2. Data Collection Agent (`data_collection.py`)

**Purpose**: Gathers academic papers about populism from the OpenAlex database.

#### Key Functions:

**`run_collection()`**
- **What it does**: Orchestrates the entire data collection process
- **Inputs**: Configuration files specifying search terms and filters
- **Outputs**: Raw dataset in Parquet format + collection statistics

**Boolean Search Support**:
- **Search terms**: Support OR/AND operators like `"populism OR populist OR populists OR far-right"`
- **Type filters**: Support OR operations like `"article OR book-chapter OR dissertation OR preprint"`
- **Flexibility**: Unlimited number of terms and types supported
- **Efficiency**: Single boolean query is more efficient than multiple separate queries

**`OpenAlexClient.paginate_works()`** (from `openalex_client.py`)
- **What it does**: Handles API pagination to retrieve all matching papers
- **Why important**: OpenAlex returns results in pages; this ensures we get everything
- **Technical detail**: Implements polite API usage with rate limiting

**`OpenAlexClient.normalize_work()`**
- **What it does**: Standardizes the raw API response into a consistent format
- **Why important**: Different papers may have missing fields or varying formats
- **For researchers**: Ensures reliable data structure for later analysis

### 3. Data Cleaning Agent (`data_cleaning.py`)

**Purpose**: Transforms messy raw data into analysis-ready format.

#### Key Functions:

**`normalize_unicode()`**
- **What it does**: Fixes text encoding issues (accents, special characters)
- **Why important**: Academic papers often contain non-English characters
- **Example**: Converts "café" to proper Unicode format

**`rule_based_domain()`**
- **What it does**: Assigns academic domains using keyword matching
- **How it works**: Scans paper concepts and matches against domain-specific terms
- **Domains covered**: Political Science, Economics, Sociology, Other
- **For users**: Provides initial domain classification before AI refinement

**Main cleaning pipeline**:
- **Deduplication**: Removes duplicate papers
- **Field derivation**: Creates computed fields like decade, author count
- **Domain pre-labeling**: Initial categorization using rules
- **Quality enhancement**: Reconstructs abstracts, normalizes citations

### 4. Bibliometric Analysis Agent (`bibliometric_analysis.py`)

**Purpose**: Computes quantitative metrics about research productivity and impact.

#### Key Functions:

**`compute_hindex()` & `compute_gindex()`**
- **What they do**: Calculate author influence metrics
- **h-index**: An author has h-index h if they have h papers with at least h citations each
- **g-index**: Similar but gives more weight to highly-cited papers
- **For researchers**: Identifies the most influential scholars in populism studies

**`publication_trends()`**
- **What it does**: Analyzes how populism research has grown over time
- **Outputs**: Annual and decadal publication counts, growth rates
- **For users**: Shows whether populism research is becoming more or less popular

**`citation_stats()`**
- **What it does**: Analyzes citation patterns across the entire corpus
- **Includes**: Citation distribution, corpus-level h/g indices
- **For researchers**: Indicates the overall impact and interconnectedness of populism research

**`author_productivity()` & `journal_productivity()`**
- **What they do**: Rank authors and journals by publication output
- **Apply**: Lotka's Law (author productivity distribution) and Bradford's Law (journal concentration)
- **For users**: Identifies the most productive researchers and key publication venues

### 5. Classification Agent (`classification.py`)

**Purpose**: Categorizes each paper into specific academic domains and sub-specialties.

#### Key Functions:

**Stage 1 - Rule-based Classification**:
- **What it does**: Uses deterministic rules for high-confidence assignments
- **Method**: Matches paper concepts against predefined keyword lists
- **Speed**: Very fast, handles most papers automatically

**Stage 2 - Embedding Similarity**:
- **What it does**: Uses AI embeddings to find similar papers
- **How it works**: Converts paper content to numerical vectors for comparison
- **Purpose**: Handles papers that don't match clear keyword patterns

  > **What is an embedding?** Imagine representing a paper not as text but as a point in a
  > 768-dimensional space, where papers about similar topics end up near each other. This pipeline
  > uses **SPECTER2** (from AllenAI), a model specifically trained on scientific citation graphs —
  > meaning "near each other" here reflects *intellectual similarity*, not just word overlap.
  > A paper about "populism and economic redistribution" will land closer to economics papers than
  > a keyword-match alone would predict.
  >
  > If SPECTER2 is unavailable, the pipeline tries **Ollama embeddings** next (e.g.
  > `nomic-embed-text`, if Ollama is running), then falls back to **TF-IDF + LSA** (a classical,
  > always-available fallback). All three produce compatible vector representations; only the
  > semantic quality differs. The active backend is logged at startup.

**Stage 3 - LLM Classification** (when needed):
- **What it does**: Uses an AI language model (running locally via Ollama) for complex cases
- **When triggered**: When SPECTER2 embedding confidence falls in the ambiguous [0.60–0.82] band — roughly 10–30% of the corpus. Papers above 0.82 are accepted by Stage 2; papers below 0.60 are flagged as low-signal and assigned to `Other`.
- **What it produces**: A structured JSON response with domain, subcategory, and confidence
- **Validation**: Every LLM response is checked against the official taxonomy before acceptance;
  invalid or hallucinated labels are rejected and fall back to `Other/interdisciplinary`

  > **Why run the LLM locally?** Because the papers contain academic text, which cloud LLMs
  > may retain in training data. Using Ollama means your data never leaves your machine.

**`EmbeddingClient`** (from `embedding_client.py`):
- **What it does**: Generates numerical representations of paper content
- **Backend priority**: SPECTER2 (preferred, ~440 MB, downloads once) → Ollama `nomic-embed-text` (if Ollama is running) → TF-IDF + LSA (always available)
- **For users**: Enables intelligent grouping of similar research without manual labeling

### 6. Network Analysis Agent (`network_analysis.py`)

**Purpose**: Maps relationships between papers, authors, and concepts.

#### Key Functions:

**`build_cocitation_network()`**
- **What it does**: Creates network where papers are connected if they're cited together
- **Why important**: Shows which ideas cluster together in populism research
- **For researchers**: Reveals intellectual communities and research fronts

**`build_bibcoupling_network()`**
- **What it does**: Connects papers that share references
- **Why important**: Shows papers addressing similar topics
- **For researchers**: Identifies research communities working on related problems

**`build_coauthorship_network()`**
- **What it does**: Maps collaboration patterns between authors
- **Why important**: Shows which researchers work together
- **For researchers**: Reveals collaboration networks and research teams

**`association_strength_normalization()`** (VOSviewer-inspired)
- **What it does**: Adjusts link strengths to account for field differences
- **Why important**: Some fields cite more than others; this normalizes for fair comparison
- **For users**: Ensures network analysis isn't biased by citation culture differences

  > **Analogy**: Two papers each have 30 references. Paper A and B share 3 references in common.
  > Is that a strong connection? It depends: if both papers have only 5 references each, sharing 3
  > is very significant. If both have 200 references, sharing 3 is almost random overlap.
  > Association strength normalizes by the total reference counts, making comparisons fair across
  > fields with different citation cultures.

**Automatic threshold scaling**:
The minimum number of shared references required to draw an edge is scaled automatically:

| Corpus size | Threshold applied |
|-------------|------------------|
| < 5,000 papers | 2 shared references |
| 5,000 – 14,999 | 3 shared references |
| 15,000 – 29,999 | 5 shared references |
| ≥ 30,000 | 10 shared references |

This prevents the network from becoming a hairball on large corpora (57K papers could produce
1.6 billion candidate pairs without thresholding). You can override this in `config/config.yaml`
under the `network:` section.

**`detect_communities()`**
- **What it does**: Groups papers into research communities
- **Methods**: Louvain algorithm (primary) with spectral clustering option
- **For researchers**: Identifies distinct research clusters in populism studies

**`find_interdisciplinary_bridges()`**
- **What it does**: Identifies papers that connect different academic domains
- **Why important**: Shows cross-disciplinary research and knowledge transfer
- **For researchers**: Highlights boundary-spanning work in populism studies

### 7. Validation Agents (`validators.py`)

**Purpose**: Quality control and error detection at each pipeline stage.

#### Key Functions:

**`validate_data()`**
- **Stages**: D1 (raw data) and D2 (clean data)
- **Checks**: File existence, schema completeness, data quality
- **For users**: Ensures data integrity before expensive processing

**`validate_statistical()`**
- **What it does**: Checks bibliometric calculations for reasonableness
- **Validates**: h-index calculations, distribution shapes, outlier detection
- **For users**: Catches calculation errors or data corruption

**`validate_classification()`**
- **What it does**: Ensures domain assignments are consistent and valid
- **Checks**: Taxonomy compliance, confidence score distributions
- **For users**: Validates that AI classifications make sense

**`validate_network()`**
- **What it does**: Checks network construction and metrics
- **Validates**: Graph connectivity, community detection, centrality measures
- **For users**: Ensures network analysis is mathematically sound

### 8. Utility Functions

#### I/O Utilities (`io_utils.py`):

**`load_checkpoint()` & `save_checkpoint()`**
- **What they do**: Track pipeline progress and allow resuming interrupted runs
- **For users**: Never lose work if the pipeline crashes midway

**`safe_list()`**
- **What it does**: Converts various data types to Python lists safely
- **Why important**: Handles different data formats from various sources
- **For developers**: Prevents crashes from unexpected data types

#### Logging Utilities (`logging_utils.py`):

**`setup_logger()` & `AuditTrail`**
- **What they do**: Create detailed logs and audit trails
- **For users**: Full traceability of what happened and when
- **For debugging**: Complete record of pipeline execution

---

## Reading Your Results

Once the pipeline completes, open `data/outputs/reports/report.html` in your browser for an
integrated visual summary. Below is a guide to interpreting each key output.

### Publication trends (`publication_trends.json`)

```json
{ "annual": [{"year": 2016, "count": 312}, {"year": 2017, "count": 487}, ...] }
```

A spike in 2016–2018 reflects the real-world wave of populist electoral victories (Trump, Brexit,
Macron, etc.) and the academic response that followed. If your corpus shows no such spike, your
search terms may be too narrow or your `from_publication_date` too recent.

### Citation statistics (`citation_stats.json`)

Key figures to check:
- **`h_index_corpus`**: the field-level h-index. A value of 50 means 50 papers each have at least
  50 citations — a sign the field is mature and internally coherent.
- **`zero_citation_rate`**: if above 40–50%, a large portion of papers have never been cited.
  This is normal for a field with many recent publications (young papers haven't had time to
  accumulate citations).
- **`percentiles`**: compare p50 vs. p90 and p99. A large gap indicates a highly skewed
  distribution — a small number of papers receive most citations.

### Classification (`classified_works.parquet`)

Key columns to check in the Parquet file:
- **`domain_source`**: tells you *how* each paper was classified — `rule`, `embedding`, or `llm`.
  A high fraction of `llm` may indicate your keyword taxonomy needs tuning.
- **`confidence`**: scores near 0.5 mean borderline cases; near 1.0 means unambiguous.
- **`classification_notes`**: present when the rule and LLM stages disagreed — useful for
  auditing.

### Network files (`.graphml`)

Open the `_vos.graphml` files in [VOSviewer](https://www.vosviewer.com) (free) or
[Gephi](https://gephi.org) (free). The pipeline generates four networks:

| File | What it shows |
|------|--------------|
| `bibcoupling_network_vos.graphml` | Papers sharing references → research communities |
| `cocitation_network_vos.graphml` | Papers cited together → intellectual cores |
| `coauthorship_network.graphml` | Authors who collaborated → research teams |
| `keyword_cooccurrence_network_vos.graphml` | Concepts co-occurring → topic clusters |

The `_vos` versions have already been filtered by association strength; the `_raw` versions
retain all edges above the minimum threshold.

### Cluster assignments (`cluster_assignments.parquet`)

Each paper has:
- **`cluster_id_louvain`**: the community it belongs to (integer)
- **`betweenness_centrality`**: how often this paper lies on the shortest path between others.
  High betweenness = a bridge paper connecting communities.

Papers in `interdisciplinary_bridges.json` are those with high betweenness *and* cross-domain
connections — they are the best candidates for a literature review section on interdisciplinary
connections in populism research.

---

## Analysis Objectives and Function Applications

### Objective 1: Understanding Research Growth and Trends

**Functions involved**: `publication_trends()`, `citation_stats()`
**What you learn**: Is populism research expanding? When did it peak?
**Real-world application**: Policy makers can see if academic interest aligns with political events

### Objective 2: Identifying Key Researchers and Venues

**Functions involved**: `compute_hindex()`, `author_productivity()`, `journal_productivity()`
**What you learn**: Who are the most influential populism scholars? Where do they publish?
**Real-world application**: Graduate students can identify mentors and key journals

### Objective 3: Mapping Intellectual Communities

**Functions involved**: `detect_communities()`, `build_cocitation_network()`, `build_bibcoupling_network()`
**What you learn**: What are the main research clusters in populism studies?
**Real-world application**: Researchers can position their work within existing literature

### Objective 4: Understanding Cross-Disciplinary Connections

**Functions involved**: `find_interdisciplinary_bridges()`, `cross_domain_matrix()`
**What you learn**: How do different disciplines approach populism?
**Real-world application**: Interdisciplinary researchers can find collaboration opportunities

### Objective 5: Tracking Collaboration Patterns

**Functions involved**: `build_coauthorship_network()`, `spectral_clustering()`
**What you learn**: Which researchers collaborate? Are there isolated research groups?
**Real-world application**: Funding agencies can identify research networks needing support

### Objective 6: Quality Control and Reproducibility

**Functions involved**: All validation functions, `AuditTrail`, checkpoint system
**What you learn**: Can you trust the results? Can others reproduce your analysis?
**Real-world application**: Academic publishing requires reproducible methods

---

## Practical Examples

### Example 1: New Researcher Getting Started

**Scenario**: You're a PhD student starting research on populism in Europe.

**Pipeline functions to focus on**:
1. **Data Collection**: Get comprehensive dataset of European populism research
2. **Publication Trends**: See when European populism research took off
3. **Top Authors**: Identify key European scholars to follow
4. **Network Analysis**: Find research clusters and potential collaborators

**Key outputs to examine**:
- `publication_trends.json` (focus on European data)
- `top_authors.json` (filter for European institutions)
- `cocitation_network_vos.graphml` (visualize research communities)

**Configuration tip**: For comprehensive data collection, set `full_max_records: null` in `config.yaml` to download all matching articles (no artificial limits).

### Example 2: Policy Analyst Tracking Research Impact

**Scenario**: You work for a government agency monitoring populism research.

**Pipeline functions to focus on**:
1. **Citation Statistics**: Measure overall impact of populism research
2. **Cross-domain Analysis**: See how economics, political science, and sociology approach populism
3. **Interdisciplinary Bridges**: Identify research that connects theory to policy

**Key outputs to examine**:
- `citation_stats.json` (corpus-level impact metrics)
- `cross_domain_matrix` in `network_metrics.json`
- `interdisciplinary_bridges.json`

### Example 3: Journal Editor Planning Special Issue

**Scenario**: You're editing a journal and planning a populism special issue.

**Pipeline functions to focus on**:
1. **Journal Productivity**: Identify journals already publishing populism research
2. **Bradford Zones**: Find the "core" journals in the field
3. **Concept Co-occurrence**: See what topics are emerging

**Key outputs to examine**:
- `top_journals.json` (Bradford analysis)
- `concept_landscape.json` (emerging research themes)
- `keyword_cooccurrence_network_vos.graphml`

### Example 4: Librarian Building Research Collection

**Scenario**: You manage a library and want to develop a populism research collection.

**Pipeline functions to focus on**:
1. **Bibliometric Summary**: Get comprehensive field overview
2. **Domain Classification**: Understand the multidisciplinary nature
3. **Publication Trends**: See growth areas for collection development

**Key outputs to examine**:
- `bibliometric_summary.json` (field overview)
- `classified_works.parquet` (domain and subcategory assignments)
- `publication_trends.json` (growth areas)

---

## Troubleshooting and Best Practices

### Common Issues and Solutions

**Issue**: Pipeline fails at data collection with a connection error
**Cause**: OpenAlex is unreachable or rate-limiting your IP (anonymous pool).
**Solution**: Add your email to `config/openalex.yaml` under `polite_email`. Check connectivity
with `curl -s "https://api.openalex.org/works?per-page=1"`.

**Issue**: `classified_works.parquet` is stale (ID mismatch warnings from the consistency test)
**Cause**: You re-ran data collection or cleaning without re-running classification.
**Solution**: Run `python src/agents/classification.py --config config/config.yaml` to reclassify,
then re-run network analysis and visualization.

**Issue**: Classification assigns most papers to `Other/interdisciplinary`
**Cause**: The keyword taxonomy in `config/openalex.yaml` does not match the concepts in your corpus.
**Solution**: Open `data/processed/concept_landscape.json` and look at the top 50 concepts.
Add any missing high-frequency concepts to `domain_concepts` in `openalex.yaml`.

**Issue**: Network analysis takes a very long time on a large corpus
**Cause**: Bibliographic coupling is O(n²) — it checks every pair of papers.
**Solution**: The pipeline auto-scales thresholds, but you can raise them further in `config.yaml`:
```yaml
network:
  min_shared_refs: 5   # raise from auto-selected value
  min_cocitations: 5
```

**Issue**: `UnboundLocalError` or import error when running an agent directly
**Cause**: Running from a subdirectory instead of the project root.
**Solution**: Always run from `bibliometric_pipeline/`:
```bash
cd bibliometric_pipeline
python src/agents/classification.py --config config/config.yaml
```

**Issue**: LLM classification gives unexpected domains (hallucinated categories)
**Cause**: The LLM model returned a valid-looking but non-taxonomy label.
**Solution**: This is handled automatically — all LLM outputs are validated against the taxonomy
before acceptance. Check `classification_notes` in `classified_works.parquet` for cases
where the LLM was overridden.

**Issue**: Memory error during network analysis on a full corpus
**Cause**: Building the full adjacency matrix for 57K papers requires significant RAM.
**Solution**: Raise `min_shared_refs` and `min_cocitations` to 5 or 10 in `config.yaml`,
and set `subfield_analysis: false`.

### Best Practices for Researchers

1. **Start with test mode**: Use synthetic data to understand pipeline outputs
2. **Validate regularly**: Run validation steps to catch issues early
3. **Check logs**: Audit trails provide detailed execution information
4. **Use checkpoints**: Resume long-running pipelines without restarting
5. **Document modifications**: Track changes to configuration or code

### Best Practices for Developers

1. **Modular design**: Each agent is independent and testable
2. **Comprehensive logging**: Every decision is logged for debugging
3. **Data validation**: Multiple quality checks prevent garbage-in-garbage-out
4. **Configuration-driven**: Easy to adapt for different research topics
5. **Reproducible**: Same inputs always produce same outputs

### Adapting for Other Research Topics

The pipeline can be adapted for any research field by modifying:

1. **Search terms** in `config/openalex.yaml`
2. **Domain taxonomy** in classification configuration
3. **Keyword mappings** for subcategories
4. **Analysis thresholds** based on field norms

---

## Conclusion

This bibliometric pipeline transforms the challenge of understanding populism research from an overwhelming task into a structured, reproducible process. By breaking down complex analysis into modular functions, researchers can:

- **Track research evolution** through publication trends
- **Identify key contributors** via productivity metrics
- **Map intellectual landscapes** through network analysis
- **Ensure quality** through comprehensive validation

Whether you're a student exploring the field, a researcher positioning your work, or a policy analyst tracking academic discourse, this pipeline provides the tools to extract meaningful insights from the vast literature on populism.

The modular design ensures that each component can be understood and modified independently, while the comprehensive validation and logging systems maintain research integrity and reproducibility.

**Ready to run?** Follow the [Quick Start guide](QUICKSTART.md) to go from setup to a full
production run in under an hour.
