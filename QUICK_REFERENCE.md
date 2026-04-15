## QUICK REFERENCE CARD

### Your Questions Answered

**Q: Domain taxonomy — created or from OpenAlex?**
A: HAND-CURATED, NOT from OpenAlex. Expert knowledge + literature analysis.

**Q: Are subcategories suggested at beginning or derived from search?**
A: SUGGESTED at beginning. 3-stage classification uses rule+embedding+LLM.

**Q: Source of definitions — internet/database?**
A: Curated from multiple scholarly sources. Reproducible in SEED_TEXTS.

**Q: Can we submit updated taxonomy to researchers?**
A: YES! Use TAXONOMY_UPDATE_TEMPLATE.md (CSV format)

**Q: Can we automate updates?**
A: YES! Run: `python scripts/update_taxonomy.py --input feedback.csv --apply`

**Q: Which files need changes for new taxonomy?**
A: Only 2: `src/utils/taxonomy.py` + `src/utils/prototype_store.py`

**Q: Can you make changes automatically?**
A: YES! Script validates and applies. See scripts/update_taxonomy.py

**Q: Format example for researchers?**
A: CSV with columns: Action, Domain, Subcategory, Keywords, Seed Texts, Rationale

---

### Coupling Matrix — New Solution

**Problem**: Raw counts have no meaning (347 shared refs → so what?)

**Solution**: 4 interpretable metrics:

| Metric | Meaning | Range |
|--------|---------|-------|
| **AS** | Stronger/weaker than random | 0.5-2.5 |
| **CSI** | Normalized by domain size | 0-1 |
| **JS** | Shared intellectual foundation | 0-1 |
| **IDCR** | % coupling across domains | 0-1 |

Each metric directly interpretable by researchers.

---

### Files Created

```
✅ CODE_QUALITY_ANALYSIS.md          (comprehensive review)
✅ TAXONOMY_UPDATE_TEMPLATE.md       (researcher CSV template)
✅ IMPLEMENTATION_SUMMARY.md         (4-phase roadmap)
✅ src/utils/taxonomy.py             (centralized taxonomy)
✅ src/utils/metrics.py              (4 coupling metrics)
✅ scripts/update_taxonomy.py        (automation script)
```

---

### Implementation Steps

1. **Today**: Change imports to use centralized `taxonomy.py`
2. **Week**: Integrate metrics + visualization
3. **Ongoing**: Collect researcher feedback → apply → re-run

---

### Key Files to Know

| File | Purpose | Lines |
|------|---------|-------|
| `src/utils/taxonomy.py` | Single taxonomy source | 230 |
| `src/utils/metrics.py` | Coupling analysis | 380 |
| `scripts/update_taxonomy.py` | Apply researcher feedback | 350 |
| `TAXONOMY_UPDATE_TEMPLATE.md` | CSV template for researchers | 200+ |

---

**Status**: Analysis ✅ | Code Ready ✅ | Documentation ✅

Ready to integrate!

