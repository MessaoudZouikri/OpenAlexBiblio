---
name: Pre-push cleanup — pending fixes
description: All 10 file edits needed before the GitHub push of OpenAlexBiblio, with exact content to write
type: project
---

## Context

Full pre-push audit was completed. 10 fixes identified and confirmed by user. License chosen: **GPL-3.0**. Changes must be applied one at a time (user preference). No commits — user does all git operations.

**Why:** Broken links on GitHub, license conflict, stale config paths, and misleading docs that reference non-existent files.

**How to apply:** Execute each fix in order. All are safe local file edits.

---

## Fix 1 — LICENSE (replace MIT with GPL-3.0)

File: `LICENSE` (root)
Action: Overwrite entire file with standard GPL-3.0 text.
Use the canonical FSF GPL-3.0 text (https://www.gnu.org/licenses/gpl-3.0.txt).
The current file contains MIT License text — completely replace it.

---

## Fix 2 — .gitignore (add .ruff_cache/)

File: `.gitignore` (root)
Action: Add `.ruff_cache/` entry.

Current last lines (around line 168-170):
```
# LLM model files (if downloaded locally)
models/
```

Add after `models/`:
```

# Ruff linter cache
.ruff_cache/
```

Note: `.idea/` and `.DS_Store` are already covered in .gitignore — no change needed there.

---

## Fix 3 — CITATION.cff (remove broken references block)

File: `CITATION.cff` (root)
Action: Remove the entire `references:` block (lines 36–43) which points to the non-existent `CODE_QUALITY_ANALYSIS.md`.

Remove this block:
```yaml
references:
  - authors:
      - family-names: "Zouikri"
        given-names: "Messaoud"
    title: "Comprehensive Code Quality Analysis, Domain Taxonomy, and Enhanced Metrics"
    type: report
    date-released: 2026-04-16
    url: "https://github.com/MessaoudZouikri/OpenAlexBiblio/blob/master/CODE_QUALITY_ANALYSIS.md"
```

---

## Fix 4 — config/config.yaml (fix broken validator script paths)

File: `config/config.yaml`
Action: Replace the 4 non-existent validator script paths with the real file.

Replace:
- `src/agents/validation/data_validator.py` → `src/agents/validation/validators.py`
- `src/agents/validation/statistical_validator.py` → `src/agents/validation/validators.py`
- `src/agents/validation/classification_validator.py` → `src/agents/validation/validators.py`
- `src/agents/validation/network_validator.py` → `src/agents/validation/validators.py`

The steps block (lines 51–86) should become:
```yaml
steps:
  - name: data_collection
    enabled: true
    script: "src/agents/data_collection.py"
  - name: validate_raw
    enabled: true
    script: "src/agents/validation/validators.py"
    stage: "D1"
  - name: data_cleaning
    enabled: true
    script: "src/agents/data_cleaning.py"
  - name: validate_clean
    enabled: true
    script: "src/agents/validation/validators.py"
    stage: "D2"
  - name: bibliometric_analysis
    enabled: true
    script: "src/agents/bibliometric_analysis.py"
  - name: validate_statistical
    enabled: true
    script: "src/agents/validation/validators.py"
  - name: classification
    enabled: true
    script: "src/agents/classification.py"
  - name: validate_classification
    enabled: true
    script: "src/agents/validation/validators.py"
  - name: network_analysis
    enabled: true
    script: "src/agents/network_analysis.py"
  - name: validate_network
    enabled: true
    script: "src/agents/validation/validators.py"
  - name: visualization
    enabled: true
    script: "src/agents/visualization.py"
```

---

## Fix 5 — CONTRIBUTING.md (remove broken taxonomy template reference)

File: `CONTRIBUTING.md` (root)
Action: Replace the broken link to the non-existent TAXONOMY_UPDATE_TEMPLATE.md.

Replace (lines 55–58):
```markdown
### Domain Taxonomy Contributions

The pipeline classifies papers into 4 domains and 21 subcategories. To propose new subcategories or modify keyword mappings:

1. Read [`docs/research/TAXONOMY_UPDATE_TEMPLATE.md`](docs/research/TAXONOMY_UPDATE_TEMPLATE.md)
2. Open an issue or pull request with your proposal and justification
```

With:
```markdown
### Domain Taxonomy Contributions

The pipeline classifies papers into 4 domains and 21 subcategories. To propose new subcategories or modify keyword mappings:

1. Review the current taxonomy in [`src/utils/taxonomy.py`](src/utils/taxonomy.py) — this is the single source of truth for all domains, subcategories, keywords, and seed texts.
2. Open an issue or pull request with your proposed changes and justification.
3. To apply changes automatically: `python scripts/update_taxonomy.py --input feedback.csv --apply`
```

---

## Fix 6 — docs/README.md (rewrite to remove all broken links)

File: `docs/README.md`
Action: Rewrite the entire file. The current version references 4 non-existent files and 2 non-existent folders (docs/research/, docs/metadata/).

New content:
```markdown
# Documentation Hub — Start Here

Welcome to the Bibliometric Pipeline documentation. This folder contains guides organized by audience and topic.

## Quick Start (Choose Your Path)

### New user or analyst
→ Start with [Getting Started Guides](./getting-started/)
- [QUICK_REFERENCE.md](./getting-started/QUICK_REFERENCE.md) — Common questions answered
- [VISUALIZATION_GUIDE.md](./getting-started/VISUALIZATION_GUIDE.md) — How to generate and interpret figures

### Developer or contributor
→ Start with [Development Guides](./development/)
- [ENHANCED_METRICS.md](./development/ENHANCED_METRICS.md) — Cross-domain coupling metrics explained
- [IMPLEMENTATION_ENHANCED_METRICS.md](./development/IMPLEMENTATION_ENHANCED_METRICS.md) — Implementation details

### All audiences
→ See [INDEX.md](./INDEX.md) for the complete navigation hub

---

## Folder Structure

\`\`\`
docs/
├── INDEX.md                              ← Full navigation hub
├── getting-started/
│   ├── QUICK_REFERENCE.md                Common questions and metrics reference
│   └── VISUALIZATION_GUIDE.md            Figure generation and interpretation
└── development/
    ├── ENHANCED_METRICS.md               4 cross-domain coupling metrics
    └── IMPLEMENTATION_ENHANCED_METRICS.md Implementation details

Root-level (key entry points):
├── CITATION.cff                          CFF citation metadata (parsed by GitHub)
├── CONTRIBUTING.md                       How to contribute code or taxonomy proposals
└── TESTING_STRATEGY.md                   Test suite design and coverage targets
\`\`\`

---

## Quick Links

| Need | Link | Time |
|------|------|------|
| Overview | [README.md](../README.md) | 10 min |
| Setup | [QUICKSTART.md](../QUICKSTART.md) | 5 min |
| Tutorial | [BIBLIOMETRIC_PIPELINE_TUTORIAL.md](../BIBLIOMETRIC_PIPELINE_TUTORIAL.md) | 45 min |
| Full Docs | [INDEX.md](./INDEX.md) | Varies |
| Metrics Reference | [ENHANCED_METRICS.md](./development/ENHANCED_METRICS.md) | 10 min |
| Common Questions | [QUICK_REFERENCE.md](./getting-started/QUICK_REFERENCE.md) | 5 min |
| Cite Us | [CITATION.cff](../CITATION.cff) | 2 min |

---

## Contact

- **Maintainer**: Messaoud Zouikri
- **Email**: econoPoPop@proton.me
- **GitHub**: https://github.com/MessaoudZouikri/OpenAlexBiblio
```

---

## Fix 7 — docs/INDEX.md (clean up 4 broken references)

File: `docs/INDEX.md`
Action: 4 targeted edits.

**Edit 7a** — Replace the "For Researchers" section that references non-existent TAXONOMY_UPDATE_TEMPLATE.md.

Replace:
```markdown
### 🔬 **For Researchers & Domain Experts**

Want to contribute to or modify the domain taxonomy? Need to enrich subcategories?

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [`research/TAXONOMY_UPDATE_TEMPLATE.md`](./research/TAXONOMY_UPDATE_TEMPLATE.md) | Current taxonomy overview with CSV template, examples, and submission process | 10 min |

**Key Module**: `src/utils/taxonomy.py` — Contains the taxonomy definitions and seed texts.

**What You'll Learn**:
- Current 4 domains × 21 subcategories structure
- How to propose new subcategories
- How to modify existing classifications
- Submission format and quality checklist
```

With:
```markdown
### 🔬 **For Researchers & Domain Experts**

Want to contribute to or modify the domain taxonomy? Need to enrich subcategories?

| Resource | Purpose | Read Time |
|----------|---------|-----------|
| [`src/utils/taxonomy.py`](../src/utils/taxonomy.py) | Single source of truth for all 4 domains, 21 subcategories, keywords, and seed texts | 10 min |
| [`scripts/update_taxonomy.py`](../scripts/update_taxonomy.py) | Automates applying taxonomy changes from a CSV feedback file | 5 min |

**To propose changes**: Open an issue or PR with a CSV in the format: `Action, Domain, Subcategory, Keywords, Seed Texts, Rationale`.
```

**Edit 7b** — Fix "For Citation" section — remove CITING.md row:

Replace:
```markdown
| [`../CITATION.cff`](../CITATION.cff) | Citation metadata in standard CFF format (GitHub auto-detects this) |
| [`../CITING.md`](../CITING.md) | How to cite this package in your work |
```

With:
```markdown
| [`../CITATION.cff`](../CITATION.cff) | Citation metadata in standard CFF format (GitHub auto-detects this) |
```

**Edit 7c** — Fix the Folder Structure diagram to show reality:

Replace the entire ```...``` folder block under "## 📁 Folder Structure" with:
```
docs/
├── INDEX.md                           ← You are here!
├── getting-started/
│   ├── QUICK_REFERENCE.md             Common questions and metrics reference
│   └── VISUALIZATION_GUIDE.md         How to create and interpret visualizations
└── development/
    ├── ENHANCED_METRICS.md            4 cross-domain coupling metrics explained
    └── IMPLEMENTATION_ENHANCED_METRICS.md  Implementation details

Root-level (key entry points):
├── CITATION.cff                       CFF citation metadata (parsed by GitHub)
├── CONTRIBUTING.md                    How to contribute code or taxonomy proposals
└── TESTING_STRATEGY.md                Test suite design and coverage targets
```

**Edit 7d** — Fix "Code Quality & Architecture" section:

Replace:
```markdown
### Code Quality & Architecture

- **Architecture Rating**: 9/10 (Excellent)
- **Key Strengths**: Agent-based design, stateless processing, comprehensive logging
- **Areas for Improvement**: Edge case handling, test coverage
- **Full Analysis**: [`development/CODE_QUALITY_ANALYSIS.md`](./development/CODE_QUALITY_ANALYSIS.md)
```

With:
```markdown
### Code Quality & Architecture

- **Architecture Rating**: 9/10 (Excellent)
- **Key Strengths**: Agent-based design, stateless processing, comprehensive logging
- **Areas for Improvement**: Edge case handling, test coverage
- **Source**: All agents in `src/agents/`, utilities in `src/utils/`
```

Also replace:
```markdown
- **Details**: See IMPLEMENTATION_SUMMARY.md metrics section
```
With:
```markdown
- **Details**: [`development/ENHANCED_METRICS.md`](./development/ENHANCED_METRICS.md)
```

Also in the Content Overview table, remove the Research row and fix Citation count:

Replace:
```markdown
| **Research** | 1 | Researchers, Domain Experts | Taxonomy enrichment and contribution guidelines |
| **Citation** | 2 | All | CITATION.cff and citation instructions |
```
With:
```markdown
| **Citation** | 1 | All | CITATION.cff (in root) |
```

---

## Fix 8 — docs/getting-started/QUICK_REFERENCE.md (remove stale dev-notes)

File: `docs/getting-started/QUICK_REFERENCE.md`
Action: 3 targeted edits.

**Edit 8a** — Fix Q&A line 15:

Replace:
```
A: YES! Use TAXONOMY_UPDATE_TEMPLATE.md (CSV format)
```
With:
```
A: YES! See `src/utils/taxonomy.py` for the current structure, then run `python scripts/update_taxonomy.py --input feedback.csv --apply`
```

**Edit 8b** — Remove the entire "Files Created" section (stale dev-planning content listing non-existent files):

Remove:
```markdown
### Files Created

```
✅ CODE_QUALITY_ANALYSIS.md          (comprehensive review)
✅ TAXONOMY_UPDATE_TEMPLATE.md       (researcher CSV template)
✅ IMPLEMENTATION_SUMMARY.md         (4-phase roadmap)
✅ src/utils/taxonomy.py             (centralized taxonomy)
✅ src/utils/metrics.py              (4 coupling metrics)
✅ scripts/update_taxonomy.py        (automation script)
```
```

**Edit 8c** — Remove the `TAXONOMY_UPDATE_TEMPLATE.md` row from "Key Files to Know" table:

Remove:
```markdown
| `TAXONOMY_UPDATE_TEMPLATE.md` | CSV template for researchers | 200+ |
```

---

## Fix 9 — docs/development/IMPLEMENTATION_ENHANCED_METRICS.md

File: `docs/development/IMPLEMENTATION_ENHANCED_METRICS.md`
Action: 2 targeted edits.

**Edit 9a** — Line 12:

Replace:
```
Section 3 of CODE_QUALITY_ANALYSIS.md proposed 4 new interpretable metrics for cross-domain bibliographic coupling. These have now been **fully integrated into the pipeline**.
```
With:
```
4 new interpretable metrics for cross-domain bibliographic coupling have been **fully integrated into the pipeline**.
```

**Edit 9b** — Line 272:

Replace:
```
- Section 3 of CODE_QUALITY_ANALYSIS.md (exact specifications)
```
With:
```
- See `docs/development/ENHANCED_METRICS.md` for full metric specifications
```

---

## Fix 10 — docs/development/ENHANCED_METRICS.md

File: `docs/development/ENHANCED_METRICS.md`
Action: 1 targeted edit.

Replace:
```
See: `IMPLEMENTATION_ENHANCED_METRICS.md` for technical details
See: `CODE_QUALITY_ANALYSIS.md` section 3 for theoretical background
```
With:
```
See: `IMPLEMENTATION_ENHANCED_METRICS.md` for technical details
```

---

## Status

- [ ] Fix 1 — LICENSE (GPL-3.0)
- [ ] Fix 2 — .gitignore (add .ruff_cache/)
- [ ] Fix 3 — CITATION.cff (remove broken references block)
- [ ] Fix 4 — config/config.yaml (fix validator paths)
- [ ] Fix 5 — CONTRIBUTING.md (taxonomy reference)
- [ ] Fix 6 — docs/README.md (full rewrite)
- [ ] Fix 7 — docs/INDEX.md (4 sub-edits)
- [ ] Fix 8 — docs/getting-started/QUICK_REFERENCE.md (3 sub-edits)
- [ ] Fix 9 — docs/development/IMPLEMENTATION_ENHANCED_METRICS.md (2 sub-edits)
- [ ] Fix 10 — docs/development/ENHANCED_METRICS.md (1 sub-edit)
