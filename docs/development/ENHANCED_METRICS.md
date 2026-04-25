# Quick Reference: Enhanced Cross-Domain Coupling Metrics

## 🚀 What's New?

The pipeline now computes **4 interpretable metrics** instead of just raw coupling counts. These metrics provide direct meaning for research and comparison across domains.

---

## 📊 The 4 Metrics Explained

### 1. **Association Strength (AS)**

**What it means**: How much stronger/weaker is the coupling than expected by chance?

```
AS = observed_coupling / expected_coupling

AS > 1.0  → Stronger than random (interdisciplinary)
AS ≈ 1.0  → As expected by chance (random)
AS < 1.0  → Weaker than expected (isolated)
```

**Use case**: Find which domain pairs are genuinely connected vs. by chance

**Example**: 
- Political Science ↔ Economics: AS = 1.5 (strong genuine connection)
- Political Science ↔ Sociology: AS = 0.8 (less connected than random)

---

### 2. **Coupling Strength Index (CSI)**

**What it means**: How much do these domains share references relative to their size?

```
CSI = shared_references / min(domain_size_1, domain_size_2)

Range: 0 to ∞
Higher CSI → More proportional coupling
```

**Use case**: Compare coupling intensity fairly across differently-sized domains

**Example**:
- Large ↔ Large: CSI = 0.3 (moderate coupling)
- Small ↔ Large: CSI = 0.8 (intensive coupling relative to smaller field)

---

### 3. **Jaccard Similarity**

**What it means**: What proportion of the intellectual foundation is shared?

```
Jaccard = |shared_references| / |total_unique_references|

Range: 0 to 1
0   → No shared foundation
0.5 → 50% shared intellectual base
1.0 → Identical reference base
```

**Use case**: Understand scholarly overlap and conceptual alignment

**Example**:
- Political Science ↔ Economics: Jaccard = 0.35 (moderate overlap)
- Political Science ↔ Sociology: Jaccard = 0.42 (higher overlap)

---

### 4. **Inter-Domain Coupling Ratio (IDCR)**

**What it means**: How interdisciplinary is the entire literature?

```
IDCR = cross-domain_connections / total_connections

Range: 0 to 1
High IDCR (>0.3) → Highly interdisciplinary field
Low IDCR (<0.1)  → Siloed, isolated domains
```

**Use case**: Measure overall interdisciplinarity of the research landscape

**Example**:
- Populism studies: IDCR = 0.42 (42% of connections cross domains)
- Tells you: Populism research is moderately interdisciplinary

---

## 📈 Visualization

### 4-Panel Heatmap

```
┌─────────────────────────────────────────┐
│  Association Strength (AS)              │
│  Red/Blue = Stronger/Weaker than random │
│  Shows: Genuine interdisciplinary links │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Coupling Strength Index (CSI)          │
│  Yellow/Red = Low/High proportional     │
│  Shows: Relative coupling intensity     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Jaccard Similarity                     │
│  Blue = Shared intellectual foundation  │
│  Shows: Conceptual alignment            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Raw Coupling Counts                    │
│  Grey = Absolute shared references      │
│  Shows: Baseline comparison             │
└─────────────────────────────────────────┘
```

**Where to find**: `data/outputs/figures/cross_domain_heatmap_enhanced.png`

---

## 📁 Data Access

### In JSON Output

```json
{
  "enhanced_cross_domain_metrics": {
    "raw_coupling_matrix": {...},
    "association_strength": {...},
    "coupling_strength_index": {...},
    "jaccard_similarity": {...},
    "inter_domain_ratio": 0.42,
    "interpretation": {
      "association_strength": "AS > 1.0 means stronger than random",
      ...
    },
    "metadata": {
      "total_domains": 4,
      "domains": ["Political Science", "Economics", "Sociology", "Other"],
      "total_coupling_strength": 2845,
      "n_inter_domain_edges": 1196,
      "n_intra_domain_edges": 1649
    }
  }
}
```

**Location**: `data/processed/network_metrics.json`

### In Python

```python
import json

# Load metrics
with open('data/processed/network_metrics.json') as f:
    metrics = json.load(f)

# Get enhanced metrics
enhanced = metrics['enhanced_cross_domain_metrics']

# Access specific metrics
as_matrix = enhanced['association_strength']
jaccard_matrix = enhanced['jaccard_similarity']
idcr = enhanced['inter_domain_ratio']

# Print interpretation
print(enhanced['interpretation'])

# Get metadata
print(f"Interdisciplinarity: {idcr * 100:.1f}%")
```

---

## 🔍 Interpretation Guide

### Reading the Matrices

**Association Strength Matrix**:
- Cells > 1.0 (red): Genuine cross-domain connections
- Cells ≈ 1.0 (white): Random connections
- Cells < 1.0 (blue): Less connected than expected

**Coupling Strength Index Matrix**:
- High values: Domains are tightly coupled relative to size
- Low values: Weak coupling relative to domain size
- Diagonal: Intra-domain couplings (usually highest)

**Jaccard Similarity Matrix**:
- High values: Domains share similar reference base
- Low values: Different scholarly traditions
- Diagonal: Always 1.0 (identical to self)

**Raw Counts**:
- Absolute numbers for reference
- Useful for checking total volume
- May be biased by domain size

---

## 💡 Example Interpretations

### Scenario 1: Strong AS, Low Jaccard

```
Political Science ↔ Economics:
  AS = 1.8 (much stronger than random)
  Jaccard = 0.25 (little shared foundation)

Interpretation:
→ These fields DO interact (AS>1)
→ But they use different references (low Jaccard)
→ Interaction is real but represents new bridges
```

### Scenario 2: High Jaccard, Moderate AS

```
Political Science ↔ Sociology:
  AS = 1.2 (somewhat stronger than random)
  Jaccard = 0.45 (significant shared foundation)

Interpretation:
→ These fields have common intellectual roots
→ But don't interact as much as expected
→ Potential for increased interdisciplinarity
```

### Scenario 3: Low IDCR

```
IDCR = 0.08 (only 8% cross-domain connections)

Interpretation:
→ This literature is quite siloed
→ Each domain mostly cites within domain
→ Opportunity to increase integration
```

---

## 🔧 Technical Details

### Association Strength Formula

```
AS(i,j) = observed_weight / expected_weight

Where:
  observed_weight = actual edges between domains i and j
  expected_weight = (degree_i × degree_j) / total_weight
```

**Advantage**: Removes field-size bias, shows true interdisciplinary connections

### Coupling Strength Index Formula

```
CSI(i,j) = shared_refs / min(refs_i, refs_j)
```

**Advantage**: Normalizes by smallest domain for fair comparison

### Jaccard Formula

```
Jaccard(i,j) = |shared_refs| / |all_refs|
```

**Advantage**: Measures proportion of shared intellectual foundation

---

## 📚 Research Applications

### 1. **Identifying Interdisciplinary Bridges**
Use AS > 1.5 to find strong cross-domain connections where you'd expect none

### 2. **Measuring Field Integration**
Use IDCR to track interdisciplinarity over time

### 3. **Comparing Research Areas**
Use CSI to fairly compare coupling across different-sized domains

### 4. **Understanding Scholarly Traditions**
Use Jaccard to see which fields share philosophical/theoretical roots

### 5. **Detecting Emerging Areas**
Look for increasing AS values over time in specific domain pairs

---

## 📄 Citation

When using these metrics, cite:

**Methodology**: VOSviewer-inspired association strength normalization
**Application**: A Bibliometric Analysis Pipeline Using OpenAlex Data

Full citation: See `CITATION.cff` (project root)

---

## ❓ FAQ

**Q: Why not just use raw counts?**
A: Raw counts are biased by domain size. Large fields naturally have more connections. These metrics normalize for fair comparison.

**Q: What if AS < 1.0?**
A: Means coupling is weaker than random chance. Domains are more isolated than expected given their size.

**Q: How do I interpret IDCR = 0.5?**
A: 50% of all connections cross domain boundaries. Very high interdisciplinarity.

**Q: Can I use these for time-series analysis?**
A: Yes! Compute metrics for different time periods and track how AS, Jaccard, and IDCR evolve.

**Q: Are these metrics suitable for publication?**
A: Yes! They're based on standard bibliometric literature and VOSviewer methodology.

---

## 📞 Questions?

See: `IMPLEMENTATION_ENHANCED_METRICS.md` for technical details

---

**Version**: 1.0
**Date**: April 16, 2026
**Status**: Production Ready ✅

