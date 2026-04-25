# Quick Reference

## Taxonomy & Classification

**Is the domain taxonomy from OpenAlex?**
No — it is hand-curated using expert knowledge and literature analysis. The 4 domains and 20
subcategories are defined in `src/utils/taxonomy.py`, which is the single source of truth
for all keywords, concept mappings, and seed texts.

**Are subcategories fixed in advance or derived from the search results?**
They are defined in advance. Classification uses a 3-stage pipeline (rule-based → SPECTER2
embedding → selective LLM) to assign each paper to one of the pre-defined subcategories.

**How do I propose new subcategories or update keyword mappings?**
Open an issue or pull request with your proposed changes. To apply changes from a CSV file:

```bash
# Preview what will change (dry-run is on by default)
python scripts/update_taxonomy.py --input feedback.csv

# Apply when satisfied
python scripts/update_taxonomy.py --input feedback.csv --apply
```

CSV format: `Action, Domain, Subcategory, Keywords, Seed Texts, Rationale`

Only two files need to change for a taxonomy update:
`src/utils/taxonomy.py` and `src/utils/prototype_store.py`

---

## Cross-Domain Coupling Metrics

Raw shared-reference counts alone are hard to interpret — large domains will always have
high counts regardless of genuine connection strength. The pipeline therefore computes
4 normalized metrics:

| Metric | Full name | Meaning | Range |
|--------|-----------|---------|-------|
| **AS** | Association Strength | Observed coupling / expected coupling | > 0 (1.0 = random) |
| **CSI** | Coupling Strength Index | Shared refs / min(domain size) | ≥ 0 |
| **Jaccard** | Jaccard Similarity | Shared intellectual foundation | 0–1 |
| **IDCR** | Inter-Domain Coupling Ratio | Fraction of coupling that crosses domains | 0–1 |

For detailed formulas and interpretation examples, see
[`docs/development/ENHANCED_METRICS.md`](../development/ENHANCED_METRICS.md).

---

## Key Files

| File | Purpose |
|------|---------|
| `src/utils/taxonomy.py` | Single source of truth for all domains, subcategories, keywords, and seed texts |
| `src/utils/metrics.py` | Canonical, independently-testable implementations of the 4 coupling metrics |
| `scripts/update_taxonomy.py` | Applies researcher feedback from a CSV file to the taxonomy |
