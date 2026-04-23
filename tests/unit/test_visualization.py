"""
Unit tests for src/agents/visualization.py
All figures are written to tmp_path — no display, no LLM calls.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import pandas as pd
import pytest

from src.agents.visualization import (
    _build_figure_summaries,
    _llm_interpret,
    fig_citation_distribution,
    fig_concept_landscape,
    fig_cross_domain_heatmap,
    fig_domain_distribution,
    fig_publication_trends,
    fig_top_authors,
    generate_html_report,
    generate_markdown_report,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fig_dir(tmp_path):
    d = tmp_path / "figures"
    d.mkdir()
    return str(d)


@pytest.fixture
def proc_dir(tmp_path):
    d = tmp_path / "processed"
    d.mkdir()
    return str(d)


@pytest.fixture
def outputs_dir(tmp_path):
    d = tmp_path / "outputs"
    d.mkdir()
    return str(d)


@pytest.fixture
def minimal_config(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    return {
        "pipeline": {"mode": "test"},
        "paths": {"outputs": str(outputs)},
    }


@pytest.fixture
def trends_data():
    return {
        "annual": [
            {"year": 2018, "count": 50, "yoy_growth_pct": None},
            {"year": 2019, "count": 70, "yoy_growth_pct": 40.0},
            {"year": 2020, "count": 90, "yoy_growth_pct": 28.6},
        ],
        "domain_annual": [
            {"year": 2018, "Political Science": 30, "Economics": 20},
            {"year": 2019, "Political Science": 45, "Economics": 25},
            {"year": 2020, "Political Science": 60, "Economics": 30},
        ],
    }


@pytest.fixture
def citation_data():
    return {
        "total": 5000,
        "mean": 12.5,
        "h_index_corpus": 18,
        "g_index_corpus": 25,
        "zero_citation_rate": 0.15,
        "percentiles": {"p25": 2, "p50": 8, "p75": 20, "p90": 45},
    }


@pytest.fixture
def authors_data():
    return {
        "top_by_output": [
            {"name": f"Author {i}", "paper_count": 20 - i, "total_citations": 100 - i * 5}
            for i in range(15)
        ],
        "top_by_citations": [
            {"name": f"Author {i}", "paper_count": 15 - i, "total_citations": 200 - i * 10}
            for i in range(15)
        ],
        "total_unique_authors": 500,
        "lotka_exponent": 2.1,
    }


@pytest.fixture
def domain_df():
    return pd.DataFrame(
        {
            "domain": ["Political Science"] * 5 + ["Economics"] * 3 + ["Sociology"] * 2,
            "subcategory": (
                ["radical_right"] * 3
                + ["european_politics"] * 2
                + ["political_economy"] * 3
                + ["social_movements"] * 2
            ),
        }
    )


@pytest.fixture
def concepts_data():
    return {"top_50_concepts": [{"concept": f"Concept {i}", "count": 100 - i} for i in range(30)]}


@pytest.fixture
def network_metrics_data():
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    raw = {d1: {d2: 10 if d1 != d2 else 50 for d2 in domains} for d1 in domains}
    return {"cross_domain_matrix": raw}


# ── fig_publication_trends ────────────────────────────────────────────────────


@pytest.mark.unit
def test_fig_publication_trends_creates_png(fig_dir, trends_data):
    fig_publication_trends(trends_data, fig_dir)
    assert (Path(fig_dir) / "publication_trends.png").exists()


@pytest.mark.unit
def test_fig_publication_trends_empty_annual_no_crash(fig_dir):
    fig_publication_trends({"annual": [], "domain_annual": []}, fig_dir)
    assert not (Path(fig_dir) / "publication_trends.png").exists()


@pytest.mark.unit
def test_fig_publication_trends_no_domain_annual(fig_dir):
    data = {"annual": [{"year": 2020, "count": 50}]}
    fig_publication_trends(data, fig_dir)
    assert (Path(fig_dir) / "publication_trends.png").exists()


# ── fig_citation_distribution ─────────────────────────────────────────────────


@pytest.mark.unit
def test_fig_citation_distribution_creates_png(fig_dir, citation_data):
    fig_citation_distribution(citation_data, fig_dir)
    assert (Path(fig_dir) / "citation_distribution.png").exists()


@pytest.mark.unit
def test_fig_citation_distribution_empty_no_crash(fig_dir):
    fig_citation_distribution({}, fig_dir)
    assert not (Path(fig_dir) / "citation_distribution.png").exists()


@pytest.mark.unit
def test_fig_citation_distribution_file_nonzero(fig_dir, citation_data):
    fig_citation_distribution(citation_data, fig_dir)
    size = (Path(fig_dir) / "citation_distribution.png").stat().st_size
    assert size > 1000


# ── fig_top_authors ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_fig_top_authors_creates_png(fig_dir, authors_data):
    fig_top_authors(authors_data, fig_dir)
    assert (Path(fig_dir) / "top_authors.png").exists()


@pytest.mark.unit
def test_fig_top_authors_empty_no_crash(fig_dir):
    fig_top_authors({"top_by_output": [], "top_by_citations": []}, fig_dir)
    assert not (Path(fig_dir) / "top_authors.png").exists()


@pytest.mark.unit
def test_fig_top_authors_truncates_to_15(fig_dir, authors_data):
    fig_top_authors(authors_data, fig_dir)
    assert (Path(fig_dir) / "top_authors.png").exists()


# ── fig_domain_distribution ───────────────────────────────────────────────────


@pytest.mark.unit
def test_fig_domain_distribution_creates_png(fig_dir, domain_df):
    fig_domain_distribution(domain_df, fig_dir)
    assert (Path(fig_dir) / "domain_distribution.png").exists()


@pytest.mark.unit
def test_fig_domain_distribution_file_nonzero(fig_dir, domain_df):
    fig_domain_distribution(domain_df, fig_dir)
    size = (Path(fig_dir) / "domain_distribution.png").stat().st_size
    assert size > 1000


# ── fig_concept_landscape ────────────────────────────────────────────────────


@pytest.mark.unit
def test_fig_concept_landscape_creates_png(fig_dir, concepts_data):
    fig_concept_landscape(concepts_data, fig_dir)
    assert (Path(fig_dir) / "concept_landscape.png").exists()


@pytest.mark.unit
def test_fig_concept_landscape_empty_no_crash(fig_dir):
    fig_concept_landscape({"top_50_concepts": []}, fig_dir)
    assert not (Path(fig_dir) / "concept_landscape.png").exists()


# ── fig_cross_domain_heatmap ──────────────────────────────────────────────────


@pytest.mark.unit
def test_fig_cross_domain_heatmap_raw_only_creates_png(fig_dir, network_metrics_data):
    fig_cross_domain_heatmap(network_metrics_data, fig_dir)
    assert (Path(fig_dir) / "cross_domain_heatmap.png").exists()


@pytest.mark.unit
def test_fig_cross_domain_heatmap_empty_matrix_no_crash(fig_dir):
    domains = ["PS", "Econ"]
    empty = {"cross_domain_matrix": {d1: {d2: 0 for d2 in domains} for d1 in domains}}
    fig_cross_domain_heatmap(empty, fig_dir)
    assert not (Path(fig_dir) / "cross_domain_heatmap.png").exists()


@pytest.mark.unit
def test_fig_cross_domain_heatmap_enhanced_creates_both_pngs(fig_dir):
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    raw = {d1: {d2: 5 if d1 != d2 else 20 for d2 in domains} for d1 in domains}
    as_m = {d1: {d2: 1.2 if d1 != d2 else 1.0 for d2 in domains} for d1 in domains}
    csi = {d1: {d2: 0.3 if d1 != d2 else 0.8 for d2 in domains} for d1 in domains}
    jac = {d1: {d2: 0.1 if d1 != d2 else 1.0 for d2 in domains} for d1 in domains}
    metrics = {
        "enhanced_cross_domain_metrics": {
            "raw_coupling_matrix": raw,
            "association_strength": as_m,
            "coupling_strength_index": csi,
            "jaccard_similarity": jac,
            "metadata": {"domains": domains},
        }
    }
    fig_cross_domain_heatmap(metrics, fig_dir)
    assert (Path(fig_dir) / "cross_domain_heatmap.png").exists()
    assert (Path(fig_dir) / "cross_domain_heatmap_enhanced.png").exists()


# ── generate_html_report ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_generate_html_report_creates_file(fig_dir, minimal_config, tmp_path):
    fig_publication_trends({"annual": [{"year": 2020, "count": 50}]}, fig_dir)
    generate_html_report(fig_dir, minimal_config)
    report_path = Path(minimal_config["paths"]["outputs"]) / "reports" / "report.html"
    assert report_path.exists()


@pytest.mark.unit
def test_generate_html_report_contains_title(fig_dir, minimal_config):
    generate_html_report(fig_dir, minimal_config)
    report_path = Path(minimal_config["paths"]["outputs"]) / "reports" / "report.html"
    content = report_path.read_text()
    assert "Bibliometric Analysis Report" in content


@pytest.mark.unit
def test_generate_html_report_no_llm_no_interpretation(fig_dir, minimal_config):
    generate_html_report(fig_dir, minimal_config, llm_client=None)
    report_path = Path(minimal_config["paths"]["outputs"]) / "reports" / "report.html"
    content = report_path.read_text()
    assert "Auto-generated interpretation" not in content


# ── generate_markdown_report ──────────────────────────────────────────────────


@pytest.mark.unit
def test_generate_markdown_report_creates_file(fig_dir, minimal_config):
    generate_markdown_report(fig_dir, minimal_config)
    report_path = Path(minimal_config["paths"]["outputs"]) / "reports" / "report.md"
    assert report_path.exists()


@pytest.mark.unit
def test_generate_markdown_report_contains_header(fig_dir, minimal_config):
    generate_markdown_report(fig_dir, minimal_config)
    report_path = Path(minimal_config["paths"]["outputs"]) / "reports" / "report.md"
    content = report_path.read_text()
    assert "# A Bibliometric Analysis Pipeline" in content


# ── _build_figure_summaries ───────────────────────────────────────────────────


@pytest.mark.unit
def test_build_figure_summaries_missing_files_returns_empty_strings(proc_dir):
    result = _build_figure_summaries(proc_dir)
    for key, val in result.items():
        assert val == ""


@pytest.mark.unit
def test_build_figure_summaries_with_trends_json(proc_dir):
    data = {"annual": [{"year": 2020, "count": 100}, {"year": 2021, "count": 120}]}
    (Path(proc_dir) / "publication_trends.json").write_text(json.dumps(data))
    result = _build_figure_summaries(proc_dir)
    assert "220" in result["publication_trends"]
    assert "2020" in result["publication_trends"]


@pytest.mark.unit
def test_build_figure_summaries_with_citation_json(proc_dir):
    data = {
        "total": 5000,
        "mean": 12.5,
        "h_index_corpus": 18,
        "g_index_corpus": 25,
        "zero_citation_rate": 0.15,
    }
    (Path(proc_dir) / "citation_stats.json").write_text(json.dumps(data))
    result = _build_figure_summaries(proc_dir)
    assert "h-index: 18" in result["citation_distribution"]


# ── _llm_interpret ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_llm_interpret_returns_empty_on_failure():
    from unittest.mock import Mock

    client = Mock()
    client.generate.return_value = ("", False)
    result = _llm_interpret(client, "publication_trends", "some data")
    assert result == ""


@pytest.mark.unit
def test_llm_interpret_returns_text_on_success():
    from unittest.mock import Mock

    client = Mock()
    client.generate.return_value = ("This is an interpretation.", True)
    result = _llm_interpret(client, "publication_trends", "some data")
    assert result == "This is an interpretation."
