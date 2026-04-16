# Code Quality & Consistency Analysis
## Bibliometric Pipeline — April 16, 2026

---

## PART 1: CODE CONSISTENCY & RELIABILITY CHECK

### 1.1 Overall Architecture
**Status**: ✅ **EXCELLENT**

The pipeline follows a clean agent-based architecture with:
- **Single Responsibility**: Each agent handles one specific task
- **Stateless Design**: All state persisted to disk via IO utils (no in-memory coupling)
- **Configuration-Driven**: YAML-based configuration for all thresholds
- **Deterministic Paths**: 3-stage classification ensures reproducibility

**Strengths**:
- Clear separation of concerns (agents/, utils/, config/)
- Comprehensive logging at every stage
- Robust error handling with fallbacks
- Type hints throughout (PEP 484 compliance)
- Docstrings on all major functions

---

### 1.2 Code Quality Issues & Recommendations

#### ✅ **GOOD: High Consistency**

| File | Assessment | Notes |
|------|-----------|-------|
| `prototype_store.py` | Excellent | Well-documented, unit-normalized vectors, proper persistence |
| `classification.py` | Excellent | 3-stage architecture well-implemented, clear routing logic |
| `network_analysis.py` | Excellent | VOSviewer-inspired techniques, robust community detection |
| `io_utils.py` | Excellent | Atomic checkpoint saves, type-safe file operations |
| `logging_utils.py` | Excellent | Structured logging, consistent format |

#### ⚠️ **AREAS FOR IMPROVEMENT**

1. **Data Cleaning (data_cleaning.py)**
   - **Issue**: Duplicate constant definitions (DOMAIN_SUBCATEGORY, SUBCATEGORY_KEYWORD_MAP)
   - **Lines**: 45-71 in data_cleaning.py vs. Lines 56-64 in classification.py
   - **Impact**: Maintenance burden if taxonomy changes
   - **Recommendation**: Move to `src/utils/taxonomy.py` (shared module)

2. **Safe List Helper**
   - **Issue**: `safe_list()` defined in multiple files
   - **Locations**: data_cleaning.py, network_analysis.py, bibliometric_analysis.py
   - **Recommendation**: Centralize in `io_utils.py` (already imported from there in some files)

3. **Missing Validation**
   - **Issue**: Parquet files assume columns exist without explicit schema checking
   - **Locations**: network_analysis.py line 139, bibliometric_analysis.py line 80-81
   - **Recommendation**: Add validation decorator at load time

4. **Error Handling in Network Analysis**
   - **Issue**: `G.degree(node, weight="weight")` can fail if node not in graph
   - **Location**: network_analysis.py lines 619-635
   - **Recommendation**: Add `.get()` or defensive check

---

### 1.3 Dependency Analysis

**Status**: ✅ **GOOD** — Well-managed dependencies

| Tier | Package | Version | Risk |
|------|---------|---------|------|
| Core | pandas, numpy, scipy | Latest | Low |
| Network | networkx, python-louvain | 3.1, 0.16 | Low |
| Embedding | sentence-transformers, torch | 2.7+, 2.2+ | Medium (GPU/MPS) |
| Optional | scikit-learn, hdbscan | Latest | Low |

**Concern**: `torch` device detection could be more robust for cross-platform deployment.

---

### 1.4 Logging Quality

**Status**: ✅ **GOOD**

- Structured logging with format: `timestamp | level | logger_name | message`
- All major decision points logged
- Debug mode available
- JSON structured logs in `logs/` directory for auditability

**Suggestion**: Consider adding span IDs for multi-step operations to trace workflow.

---

## PART 2: DOMAIN TAXONOMY & CLASSIFICATION ORIGIN

### 2.1 Where Does the Taxonomy Come From?

**Answer**: **HAND-CRAFTED PROTOTYPES** (Not from OpenAlex)

The domain taxonomy is **explicitly defined** in `prototype_store.py`:

```python
SEED_TEXTS: Dict[str, List[str]] = {
    "Political Science::comparative_politics": [...],
    "Political Science::political_theory": [...],
    # ... 20 subcategories total
}
```

**Key Facts**:
1. **Seeds are curated, not auto-generated** (lines 1-228 in prototype_store.py)
2. **No dependency on OpenAlex schema** — used only as data source
3. **Canonical descriptions** written by domain experts to capture intellectual identity
4. **21 total subcategories** across 4 domains:
   - Political Science: 7 subcategories
   - Economics: 4 subcategories  
   - Sociology: 4 subcategories
   - Other: 6 subcategories

### 2.2 Classification Pipeline

**Three-Stage Process** (deterministic + selective LLM):

```
Stage 1: Rule-Based (100% of corpus)
├─ Input: OpenAlex concepts + keyword matching
├─ Output: Domain + confidence score
└─ Threshold: If confidence >= 0.75 → ACCEPT

    ↓ (confidence < 0.75)

Stage 2: Embedding Similarity (fallback)
├─ Input: Title + abstract + OpenAlex concepts → dense vector
├─ Cosine similarity to prototype centroids
├─ If score >= 0.80 → ACCEPT
├─ If 0.55 <= score < 0.80 → forward to LLM
└─ If score < 0.55 → flag as outlier

    ↓ (0.55-0.80 range)

Stage 3: LLM (selective, ~10-30%)
├─ Input: Text + embedding hints (top-3 matches)
├─ Output: Final domain + confidence
└─ Only for genuinely ambiguous cases
```

---

## PART 3: IMPROVING THE CROSS-DOMAIN BIBLIOGRAPHIC COUPLING MATRIX

### 3.1 Problem Statement

**Current Implementation** (network_analysis.py, lines 263-276):

```python
def cross_domain_matrix(G_bibcoupling: nx.Graph, domain_map: Dict[str, str]) -> dict:
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    matrix = {d: {d2: 0 for d2 in domains} for d in domains}

    for a, b, data in G_bibcoupling.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = data.get("weight", 1)
        matrix[da][db] = matrix[da].get(db, 0) + w  # Raw counts
        if da != db:
            matrix[db][da] = matrix[db].get(da, 0) + w
```

**Issues**:
1. **Raw edge counts** without normalization (biased by domain size)
2. **No statistical meaning** — difficult to interpret "X shared references"
3. **Symmetry violation** — double-counts intra-domain connections
4. **Field-size bias** — large fields appear more connected

---

### 3.2 Recommended Interpretable Metrics

#### **Metric 1: Normalized Association Strength (VOSviewer-style)**
```
AS(i,j) = (observed_ij) / (expected_ij)

expected_ij = (degree_i * degree_j) / total_weight

Interpretation:
- AS > 1.0 : Stronger connection than expected by chance
- AS ≈ 1.0 : Random connection
- AS < 1.0 : Weaker connection than expected
```

**Code to add**:
```python
def association_strength_normalized(G: nx.Graph, domain_map: Dict[str, str]) -> dict:
    """Normalized association strength between domains."""
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    matrix_observed = {d: {d2: 0 for d2 in domains} for d in domains}
    domain_degrees = {d: 0 for d in domains}
    
    # Count connections
    for a, b, data in G.edges(data=True):
        da, db = domain_map.get(a, "Other"), domain_map.get(b, "Other")
        w = data.get("weight", 1)
        matrix_observed[da][db] += w
        domain_degrees[da] += w
    
    total_weight = sum(domain_degrees.values())
    matrix_expected = {}
    for d1 in domains:
        matrix_expected[d1] = {}
        for d2 in domains:
            expected = (domain_degrees[d1] * domain_degrees[d2]) / total_weight if total_weight > 0 else 0
            matrix_expected[d1][d2] = expected
    
    matrix_as = {}
    for d1 in domains:
        matrix_as[d1] = {}
        for d2 in domains:
            observed = matrix_observed[d1][d2]
            expected = matrix_expected[d1][d2]
            if expected > 0:
                matrix_as[d1][d2] = round(observed / expected, 3)
            else:
                matrix_as[d1][d2] = 0.0
    
    return matrix_as
```

---

#### **Metric 2: Jaccard Similarity (Co-citation Networks)**
```
Jaccard(D_i, D_j) = |References_shared| / |References_union|

Range: 0 to 1
Interpretation:
- 1.0  : Perfect overlap (identical reference base)
- 0.5  : 50% shared intellectual foundation
- 0.0  : No common references
```

---

#### **Metric 3: Coupling Strength Index**
```
CSI(D_i, D_j) = shared_refs / min(refs_i, refs_j)

Interpretation:
- High CSI: Fields tightly coupled through citations
- Low CSI:  Minimal cross-domain influence
```

---

#### **Metric 4: Inter-Domain Coupling Ratio**
```
IDCR = inter_domain_edges / total_edges

Interpretation:
- High IDCR (>0.3): Highly interdisciplinary field
- Low IDCR (<0.1):  Siloed domains
```

---

### 3.3 Proposed Enhanced Matrix

```python
def enhanced_cross_domain_analysis(G_bibcoupling: nx.Graph, domain_map: Dict[str, str]) -> dict:
    """Compute multiple interpretable coupling metrics."""
    domains = sorted(set(domain_map.values()))
    
    # 1. Raw counts (for reference)
    raw_matrix = {d: {d2: 0 for d2 in domains} for d in domains}
    
    # 2. Association strength (normalized)
    as_matrix = {}
    
    # 3. Coupling strength index
    csi_matrix = {}
    
    # 4. Jaccard similarity
    jaccard_matrix = {}
    
    # 5. Coverage metrics
    domain_refs = {d: set() for d in domains}
    domain_coupled = {d: set() for d in domains}
    
    for a, b, data in G_bibcoupling.edges(data=True):
        da, db = domain_map.get(a, "Other"), domain_map.get(b, "Other")
        w = data.get("weight", 1)
        
        raw_matrix[da][db] = raw_matrix[da].get(db, 0) + w
        domain_coupled[da].add(b)
        domain_refs[da].add(a)
    
    # Compute normalized metrics
    total_weight = sum(sum(row.values()) for row in raw_matrix.values())
    
    for d1 in domains:
        as_matrix[d1] = {}
        csi_matrix[d1] = {}
        jaccard_matrix[d1] = {}
        
        degree_d1 = sum(raw_matrix[d1].values())
        
        for d2 in domains:
            observed = raw_matrix[d1][d2]
            
            # Association strength
            degree_d2 = sum(raw_matrix[d2].values())
            expected = (degree_d1 * degree_d2) / total_weight if total_weight > 0 else 0.001
            as_matrix[d1][d2] = round(observed / expected, 3) if expected > 0 else 0
            
            # Coupling strength index
            min_degree = min(degree_d1, degree_d2) if min(degree_d1, degree_d2) > 0 else 1
            csi_matrix[d1][d2] = round(observed / min_degree, 3)
            
            # Jaccard (for same domain = 1.0)
            if d1 == d2:
                jaccard_matrix[d1][d2] = 1.0
            else:
                union_refs = len(domain_refs[d1] | domain_refs[d2])
                intersection_refs = len(domain_refs[d1] & domain_refs[d2])
                jaccard_matrix[d1][d2] = round(intersection_refs / union_refs, 3) if union_refs > 0 else 0
    
    return {
        "raw_coupling_matrix": raw_matrix,
        "association_strength": as_matrix,
        "coupling_strength_index": csi_matrix,
        "jaccard_similarity": jaccard_matrix,
        "inter_domain_ratio": round(
            sum(raw_matrix[d1][d2] for d1 in domains for d2 in domains if d1 != d2) / 
            total_weight if total_weight > 0 else 0, 3
        ),
        "interpretation": {
            "raw_coupling_matrix": "Absolute count of shared references",
            "association_strength": "AS > 1.0 means stronger than random; AS < 1.0 means weaker",
            "coupling_strength_index": "Ratio of shared refs to minimum domain size",
            "jaccard_similarity": "Proportion of shared intellectual foundation (0-1)",
            "inter_domain_ratio": "Proportion of coupling that crosses domains (0-1)"
        }
    }
```

---

### 3.4 Visualization Recommendations

**1. Heatmap with Multiple Scales**:
```python
fig, axes = plt.subplots(2, 2, figsize=(14, 12))

# Association strength (log scale for visibility)
sns.heatmap(as_matrix, annot=True, fmt='.2f', ax=axes[0,0], cmap='RdBu_r', center=1.0)
axes[0,0].set_title('Association Strength (AS > 1 = Stronger than random)')

# Coupling strength index
sns.heatmap(csi_matrix, annot=True, fmt='.3f', ax=axes[0,1], cmap='YlOrRd')
axes[0,1].set_title('Coupling Strength Index (0-1)')

# Jaccard similarity
sns.heatmap(jaccard_matrix, annot=True, fmt='.3f', ax=axes[1,0], cmap='Blues')
axes[1,0].set_title('Jaccard Similarity (0-1)')

# Raw counts
sns.heatmap(raw_matrix, annot=True, fmt='d', ax=axes[1,1], cmap='Greys')
axes[1,1].set_title('Raw Coupling Counts')
```

---

## PART 4: UPDATING DOMAIN TAXONOMY

### 4.1 Current Structure

**File**: `src/utils/prototype_store.py` (lines 39-228)

```python
SEED_TEXTS: Dict[str, List[str]] = {
    "Domain::subcategory": [
        "Seed text 1...",
        "Seed text 2...",
    ],
}
```

### 4.2 Modification Impact Analysis

To modify taxonomy, these files require changes:

| File | Changes Required | Effort |
|------|------------------|--------|
| `prototype_store.py` | Add/remove entries in SEED_TEXTS + SUBCATEGORY_TO_DOMAIN | Low |
| `classification.py` | Update DOMAIN_SUBCATEGORY, SUBCATEGORY_KEYWORDS | Low |
| `data_cleaning.py` | Update DOMAIN_SUBCATEGORY, SUBCATEGORY_KEYWORD_MAP | Low |
| Network analysis | No changes (reads from domain_map) | None |
| Visualization | No changes (auto-adapts to domains) | None |

### 4.3 Step-by-Step Update Process

**1. Create CSV template for researchers**:
```csv
domain,subcategory,keywords,seed_text_1,seed_text_2
Political Science,comparative_politics,"comparative, cross-national",<canonical description>,<example>
```

**2. Validation checklist**:
- ✓ Each subcategory has 2+ diverse seed texts
- ✓ Keywords are specific (not generic)
- ✓ Seed texts use technical vocabulary for that field
- ✓ No overlap between subcategories

**3. Update process** (automated):
```bash
python scripts/update_taxonomy.py --input researcher_taxonomy.csv --output src/utils/prototype_store.py
```

---

## RECOMMENDATIONS SUMMARY

### Critical (Do First)
1. ✅ **Centralize taxonomy** → `src/utils/taxonomy.py`
2. ✅ **Implement enhanced coupling metrics** → Add to network_analysis.py
3. ✅ **Add schema validation** → Check column existence at load time

### High Priority
4. ✅ **Create taxonomy update script** → Automate researcher feedback integration
5. ✅ **Add metadata to prototypes** → Track taxonomy version + creation date

### Medium Priority
6. ⚠️ **Improve error messages** → More context on failures
7. ⚠️ **Add telemetry** → Track classification decisions over time
8. ⚠️ **Performance profiling** → Identify bottlenecks in large corpus

---

## Files to Create / Modify

### New File: `src/utils/taxonomy.py`
```python
"""Centralized domain taxonomy management."""
# Shared DOMAIN_SUBCATEGORY, SUBCATEGORY_KEYWORDS, CONCEPT_DOMAIN_MAP
# Version: 1.0
# Last updated: 2026-04-16
```

### Modified Files
- `src/agents/network_analysis.py` → Add enhanced_cross_domain_analysis()
- `src/agents/visualization.py` → Add 4-panel heatmap
- `scripts/update_taxonomy.py` → New automation script

---


