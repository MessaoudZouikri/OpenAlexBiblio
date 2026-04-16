# 📚 Documentation Hub — Bibliometric Pipeline

Welcome to the comprehensive documentation for the Bibliometric Pipeline project. This hub helps you find what you need based on your role and interests.

---

## 🎯 Quick Navigation by Audience

### 👨‍💻 **For Developers & Code Maintainers**

Want to understand the codebase, improve code quality, or contribute to development?

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [`development/CODE_QUALITY_ANALYSIS.md`](./development/CODE_QUALITY_ANALYSIS.md) | Complete code review, architecture analysis, specific issues with fixes | 15-20 min |
| [`development/IMPLEMENTATION_SUMMARY.md`](./development/IMPLEMENTATION_SUMMARY.md) | 4-phase implementation roadmap with timeline and effort estimates | 10 min |

**Start with**: CODE_QUALITY_ANALYSIS.md for the full picture.

---

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

---

### 👥 **For Users & Data Analysts**

Want to understand the metrics, run the pipeline, or analyze results?

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [`getting-started/QUICK_REFERENCE.md`](./getting-started/QUICK_REFERENCE.md) | Common questions, metrics explanations, usage examples | 5-10 min |
| [`getting-started/VISUALIZATION_GUIDE.md`](./getting-started/VISUALIZATION_GUIDE.md) | How to generate and interpret visualizations | 10 min |

**Root Level** (Quick Start):
- 📖 [`README.md`](../README.md) — Project overview and quick facts
- 🚀 [`QUICKSTART.md`](../QUICKSTART.md) — Installation and first run
- 📝 [`BIBLIOMETRIC_PIPELINE_TUTORIAL.md`](../BIBLIOMETRIC_PIPELINE_TUTORIAL.md) — Hands-on tutorial

---

### 📧 **For Citation & Attribution**

| Document | Purpose |
|----------|---------|
| [`metadata/CITATION.cff`](./metadata/CITATION.cff) | Citation metadata in standard CFF format |
| [`metadata/CITING.md`](./metadata/CITING.md) | How to cite this package in your work |

---

## 📁 Folder Structure

```
docs/
├── INDEX.md                           ← You are here!
├── getting-started/
│   ├── QUICK_REFERENCE.md             For users asking common questions
│   └── VISUALIZATION_GUIDE.md         How to create and interpret visualizations
├── development/
│   ├── CODE_QUALITY_ANALYSIS.md       Complete code review & architecture analysis
│   └── IMPLEMENTATION_SUMMARY.md      Implementation roadmap & phases
├── research/
│   └── TAXONOMY_UPDATE_TEMPLATE.md    For researchers enriching the taxonomy
└── metadata/
    ├── CITATION.cff                   CFF citation metadata
    └── CITING.md                      Citation guidelines
```

---

## 🔍 Documentation by Topic

### Domain Taxonomy & Classification

- **Current Structure**: 4 domains, 21 subcategories (hand-curated, not from OpenAlex)
- **Classification Method**: 3-stage (Rule-based → Embedding → Selective LLM)
- **Source Documents**:
  - [`research/TAXONOMY_UPDATE_TEMPLATE.md`](./research/TAXONOMY_UPDATE_TEMPLATE.md) — For proposals
  - `src/utils/taxonomy.py` — Implementation details

### Code Quality & Architecture

- **Architecture Rating**: 9/10 (Excellent)
- **Key Strengths**: Agent-based design, stateless processing, comprehensive logging
- **Areas for Improvement**: Edge case handling, test coverage
- **Full Analysis**: [`development/CODE_QUALITY_ANALYSIS.md`](./development/CODE_QUALITY_ANALYSIS.md)

### Enhanced Metrics & Indicators

- **New Metrics**: 4 interpretable coupling matrices with direct meaning
- **Comparison Framework**: Cross-domain bibliographic coupling with statistical validity
- **Details**: See IMPLEMENTATION_SUMMARY.md metrics section

### Installation & Usage

- **Quick Setup**: [`QUICKSTART.md`](../QUICKSTART.md) (root level)
- **Full Tutorial**: [`BIBLIOMETRIC_PIPELINE_TUTORIAL.md`](../BIBLIOMETRIC_PIPELINE_TUTORIAL.md) (root level)
- **Common Questions**: [`getting-started/QUICK_REFERENCE.md`](./getting-started/QUICK_REFERENCE.md)

---

## ❓ Can't Find What You're Looking For?

1. **Troubleshooting**: Check `QUICKSTART.md` in the root directory
2. **API Details**: See `agents/` folder specifications
3. **Contributing**: Open an issue on [GitHub](https://github.com/MessaoudZouikri/econoPoPop)
4. **Questions/Feedback**: Contact: **econoPoPop@proton.me**

---

## 📊 Content Overview

| Category | Files | Audience | Purpose |
|----------|-------|----------|---------|
| **Getting Started** | 2 | Users, Analysts | Quick reference and visualization guides |
| **Development** | 2 | Developers, Maintainers | Code quality analysis and implementation roadmap |
| **Research** | 1 | Researchers, Domain Experts | Taxonomy enrichment and contribution guidelines |
| **Metadata** | 2 | Citation & Attribution | How to cite and attribution information |

---

## 📝 Last Updated

- **Date**: April 16, 2026
- **Maintainer**: Messaoud Zouikri
- **Contact**: econoPoPop@proton.me

---

**Ready to dive in?** Choose your starting point above and let us know if you have feedback!

