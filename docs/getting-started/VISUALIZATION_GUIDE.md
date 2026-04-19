# Visualization Guide

The pipeline produces 6 publication-ready PNG figures and one self-contained HTML report.
All outputs land in `data/outputs/figures/` and `data/outputs/reports/`.

---

## Output Files

| File | Description |
|------|-------------|
| `publication_trends.png` | Annual publication counts with decade overlays and YoY growth rate |
| `citation_distribution.png` | Citation percentile bars with h-index and g-index markers |
| `top_authors.png` | Two-panel horizontal bar — top 20 by paper count and by total citations |
| `domain_distribution.png` | Pie chart of domain shares with top subcategories per domain |
| `concept_landscape.png` | Top 30 OpenAlex concepts by frequency |
| `cross_domain_heatmap.png` | 4-panel heatmap: raw coupling, association strength, Jaccard, IDCR |
| `report.html` | Single-file HTML report embedding all figures with metadata header |

---

## Viewing Outputs

```bash
# Open the HTML report in your browser (macOS)
open data/outputs/reports/report.html

# Linux
xdg-open data/outputs/reports/report.html

# Windows
start data/outputs/reports/report.html
```

---

## Customising Figures

All visualization code is in `src/agents/visualization.py`. Key parameters:

- **Figure size and DPI** — set via `figsize` and `dpi` arguments inside each `fig_*` function. Default DPI is 150 for screen; raise to 300 for print-ready export.
- **Colour palette** — modify the `PALETTE` dict at the top of `visualization.py`.
- **Top-N limits** — `fig_concept_landscape` shows top 30 by default; change the `top_n` parameter.
- **Cross-domain heatmap domains** — the 4 domain labels come from `bibliometric_analysis.py`; add domains there first.

---

## Network Visualizations (VOSviewer / Gephi)

The network agent writes GraphML files to `data/outputs/networks/`:

| File | Network type |
|------|-------------|
| `co_citation.graphml` | Co-citation network (shared citing papers) |
| `bibliographic_coupling.graphml` | Bibliographic coupling (shared references) |
| `co_authorship.graphml` | Co-authorship network |
| `concept_cooccurrence.graphml` | Concept co-occurrence network |

**Recommended tools:**
- [VOSviewer](https://www.vosviewer.com) — free, reads GraphML, best for cluster maps
- [Gephi](https://gephi.org) — free, full graph analytics, force-directed layouts

**Opening in VOSviewer:**
1. File → Open → VOSviewer network file
2. Choose GraphML format
3. Use weight field `weight` for edge thickness

---

## Regenerating Figures

To regenerate only the figures without rerunning the full pipeline:

```bash
python src/agents/visualization.py --config config/config.yaml
```

This reads from already-computed parquet files in `data/processed/` and rewrites all figures.

---

## Adding a Custom Figure

1. Add a `fig_my_plot(data: dict, fig_dir: str) -> None` function in `src/agents/visualization.py`
2. Call it from the `main()` function after the existing figure calls
3. It will automatically appear in the HTML report on the next run
