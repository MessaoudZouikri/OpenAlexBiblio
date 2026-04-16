# Domain Taxonomy Update Template
## For Research Collaboration: Enriching the Domain Taxonomy

This template is designed to collect structured feedback from domain experts to improve and expand the bibliometric pipeline's classification taxonomy.

---

## Instructions for Researchers

1. **Review the current taxonomy** at `src/utils/taxonomy.py`
2. **Identify gaps or improvements** in the existing subcategories
3. **Fill out one CSV row per new/modified subcategory**
4. **Include diverse seed texts** that capture the intellectual essence of each subcategory
5. **Add specific keywords** that distinguish this subcategory from others

---

## Current Taxonomy Overview

### Political Science (7 subcategories)
- `comparative_politics` — Cross-national comparative analysis of institutions, parties, electoral systems
- `political_theory` — Normative, conceptual, and theoretical frameworks for understanding populism
- `electoral_politics` — Voting behavior, electoral competition, campaign dynamics
- `democratic_theory` — Democratic backsliding, institutional erosion, illiberalism
- `radical_right` — Far-right parties, ethnonationalism, anti-immigration movements
- `latin_american_politics` — Populism in Latin America, pink tide, resource nationalism
- `european_politics` — Populism in Europe, Euroscepticism, illiberalism in EU member states

### Economics (4 subcategories)
- `political_economy` — Macroeconomic policy, fiscal redistribution under populist governments
- `redistribution` — Inequality, welfare state, social protection, demands for redistribution
- `trade_globalization` — Trade exposure, automation, protectionism, anti-globalization sentiment
- `financial_crisis` — 2008 crisis aftermath, austerity, economic grievances, unemployment shocks

### Sociology (4 subcategories)
- `social_movements` — Collective action, grassroots mobilization, protest movements
- `identity_politics` — Identity-based grievances, nationalism, ethnic boundaries, religious divisions
- `media_communication` — Media framing, social media amplification, disinformation, polarization
- `culture_values` — Cultural backlash, post-materialism, status anxiety, value conflicts

### Other (5 subcategories)
- `international_relations` — Foreign policy, geopolitics, multilateralism, populist diplomacy
- `history` — Historical antecedents of populism, long-term cycles, comparative historical analysis
- `psychology` — Psychological correlates of populism, authoritarianism, cognitive patterns
- `geography` — Urban-rural divides, regional inequality, place-based grievances, electoral geography
- `interdisciplinary` — Mixed-methods, literature reviews, synthesis across disciplines

---

## CSV Template

**Column Definitions**:

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| **Action** | `new` \| `modify` \| `split` \| `merge` | `new` | `new`=create, `modify`=improve existing, `split`=divide one into two, `merge`=combine |
| **Domain** | string | `Political Science` | One of: Political Science, Economics, Sociology, Other |
| **Subcategory** | string | `comparative_politics` | Lowercase, underscore-separated. Unique per domain. |
| **Keywords (comma-separated)** | string | `"comparative, cross-national, institutional design"` | 5-10 specific terms that distinguish this subcategory |
| **Seed Text 1** | string | `"Quantitative cross-country analysis of democratic institutions..."` | Canonical description (2-3 sentences). Capture core intellectual identity. |
| **Seed Text 2** | string | `"Comparative case study of electoral system effects..."` | Second seed text (2-3 sentences). Different angle than Seed Text 1. |
| **Rationale** | string | `"Current comparative_politics is too broad..."` | Why this change? What gap does it fill? |

---

## Example Rows

### Example 1: Add new subcategory

```csv
Action,Domain,Subcategory,Keywords (comma-separated),Seed Text 1,Seed Text 2,Rationale
new,Political Science,judicial_politics,"supreme court, judges, judicial independence, legal challenges, constitutional court","Analysis of how populist governments undermine judicial independence through appointment strategies and executive interference. Studies of constitutional courts defending against populist institutional capture.","Research on court-packing, dismissal of judges, and the politicization of legal systems in populist democracies.","Current democratic_theory mixes too many distinct phenomena. Judicial dynamics deserve own subcategory."
```

### Example 2: Modify existing subcategory

```csv
Action,Domain,Subcategory,Keywords (comma-separated),Seed Text 1,Seed Text 2,Rationale
modify,Economics,redistribution,"welfare chauvinism, immigrant exclusion, means-testing, targeted benefits, social protection","Welfare attitudes contingent on immigrant status. Study of how populist politics reshape social protection eligibility.","Research on exclusionary welfare nationalism and the targeting of social benefits to 'native' populations.","Current keywords miss key distinction: populist welfare is often redistributive BUT conditional on ethnic/national belonging."
```

### Example 3: Split existing subcategory

```csv
Action,Domain,Subcategory,Keywords (comma-separated),Seed Text 1,Seed Text 2,Rationale
split,Sociology,media_communication,communication_part,"media framing, agenda-setting, journalistic coverage, political communication, media trust","Research on how mainstream media covers populist movements. Studies of media logic and its effect on political narratives.","Media institutions and communication processes differ from digital/algorithmic content dissemination. Split warranted."
```

```csv
Action,Domain,Subcategory,Keywords (comma-separated),Seed Text 1,Seed Text 2,Rationale
split,Sociology,digital_communication,"social media, twitter, facebook, algorithmic amplification, echo chambers, online communities","Analysis of how populist movements mobilize supporters through social media platforms. Studies of algorithmic echo chambers and misinformation spread on Twitter/Facebook.","Digital platforms have distinct dynamics from traditional media. Deserves own subcategory for modern populism."
```

### Example 4: Merge two subcategories

```csv
Action,Domain,Subcategory,Keywords (comma-separated),Seed Text 1,Seed Text 2,Rationale
merge,Political Science,populist_leadership,"charismatic leadership, personalism, executive power, leader-follower bond, anti-pluralism","Charismatic leadership dynamics in populist movements. Analysis of how populist leaders personify 'the people' and bypass institutions.","Research on the outsider status of populist leaders, their media mastery, and their cultivation of direct leader-people bonds.","Current electoral_politics captures voting but misses the unique leadership dynamics of populism. New subcategory for populist leader studies."
```

---

## Submission Format

**Option A: CSV File**
```bash
# Save as: researcher_taxonomy_update_2026_04.csv
# Submit to: [email/repository]
```

Example CSV structure:
```csv
Action,Domain,Subcategory,Keywords (comma-separated),Seed Text 1,Seed Text 2,Rationale
new,Political Science,judicial_politics,"supreme court, judges, judicial independence, constitutional court, court-packing","...","...","..."
modify,Economics,redistribution,"welfare chauvinism, immigrant exclusion, means-testing, social protection, targeted benefits","...","...","..."
```

**Option B: Google Form** (if provided by team)
- Link: [TBD]

---

## Quality Checklist

Before submitting, verify:

- ✓ Each subcategory name is unique within its domain
- ✓ Keywords are specific (not generic like "research" or "study")
- ✓ Seed texts are 2-3 sentences each, canonical to the field
- ✓ Seed Text 1 and 2 are different angles/perspectives
- ✓ Rationale explains the intellectual gap
- ✓ No overlap with existing subcategories
- ✓ Subcategory names use lowercase + underscores (no spaces or hyphens)

---

## What Happens After Submission?

1. **Team review**: Core team evaluates proposals against:
   - Distinctness from existing categories
   - Coverage of literature in dataset
   - Scalability and generalizability
   
2. **Integration**: Approved changes incorporated into:
   - `src/utils/taxonomy.py`
   - `src/utils/prototype_store.py`
   - `src/agents/classification.py`
   
3. **Re-classification**: Pipeline re-run on corpus with updated taxonomy
   - New classification results saved
   - Audit trail maintained
   - Before/after comparison generated
   
4. **Feedback loop**: Results shared with researchers for iterative refinement

---

## Questions? Contact the Team

For clarifications on the current taxonomy, the classification process, or submission process:
- **Email**: [TBD]
- **GitHub Issues**: [TBD]
- **Documentation**: See `CODE_QUALITY_ANALYSIS.md` for technical details

---

## Appendix: Taxonomy Versioning

Each approved version is tagged and released:

```
src/utils/taxonomy.py
├── version: "1.0" (baseline hand-curated)
├── version: "1.1" (researcher feedback round 1)
├── version: "1.2" (researcher feedback round 2)
└── ... (tracked in git)
```

All versions are available in the repository for reproducibility.


