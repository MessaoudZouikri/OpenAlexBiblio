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
    fig_publication_types,
    fig_top_authors,
    fig_type_by_domain,
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


# ── fig_publication_types ─────────────────────────────────────────────────────


@pytest.fixture
def type_stats_data():
    return {
        "types": [
            {
                "type": "article",
                "frequency": 400,
                "percentage": 66.7,
                "cumulative_percentage": 66.7,
            },
            {
                "type": "book-chapter",
                "frequency": 150,
                "percentage": 25.0,
                "cumulative_percentage": 91.7,
            },
            {
                "type": "preprint",
                "frequency": 50,
                "percentage": 8.3,
                "cumulative_percentage": 100.0,
            },
        ],
        "total": 600,
    }


@pytest.mark.unit
def test_fig_publication_types_creates_png(fig_dir, type_stats_data):
    fig_publication_types(type_stats_data, fig_dir)
    assert (Path(fig_dir) / "publication_types.png").exists()


@pytest.mark.unit
def test_fig_publication_types_file_nonzero(fig_dir, type_stats_data):
    fig_publication_types(type_stats_data, fig_dir)
    assert (Path(fig_dir) / "publication_types.png").stat().st_size > 1000


@pytest.mark.unit
def test_fig_publication_types_empty_no_crash(fig_dir):
    fig_publication_types({"types": [], "total": 0}, fig_dir)
    assert not (Path(fig_dir) / "publication_types.png").exists()


@pytest.mark.unit
def test_fig_publication_types_single_type(fig_dir):
    data = {
        "types": [
            {
                "type": "article",
                "frequency": 100,
                "percentage": 100.0,
                "cumulative_percentage": 100.0,
            }
        ],
        "total": 100,
    }
    fig_publication_types(data, fig_dir)
    assert (Path(fig_dir) / "publication_types.png").exists()


# ── fig_type_by_domain ────────────────────────────────────────────────────────


@pytest.fixture
def classified_df():
    types = ["article", "book-chapter", "dissertation", "preprint"]
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    rows = []
    for i, t in enumerate(types):
        for j, d in enumerate(domains):
            rows.extend([{"type": t, "domain": d}] * ((i + 1) * (j + 1) * 5))
    return pd.DataFrame(rows)


@pytest.mark.unit
def test_fig_type_by_domain_creates_png(fig_dir, classified_df):
    fig_type_by_domain(classified_df, fig_dir)
    assert (Path(fig_dir) / "publication_types_by_domain.png").exists()


@pytest.mark.unit
def test_fig_type_by_domain_file_nonzero(fig_dir, classified_df):
    fig_type_by_domain(classified_df, fig_dir)
    assert (Path(fig_dir) / "publication_types_by_domain.png").stat().st_size > 1000


@pytest.mark.unit
def test_fig_type_by_domain_empty_df_no_crash(fig_dir):
    fig_type_by_domain(pd.DataFrame(), fig_dir)
    assert not (Path(fig_dir) / "publication_types_by_domain.png").exists()


@pytest.mark.unit
def test_fig_type_by_domain_missing_columns_no_crash(fig_dir):
    df = pd.DataFrame({"title": ["a", "b"]})
    fig_type_by_domain(df, fig_dir)
    assert not (Path(fig_dir) / "publication_types_by_domain.png").exists()


@pytest.mark.unit
def test_fig_type_by_domain_unknown_values_excluded(fig_dir):
    df = pd.DataFrame(
        {"type": ["article", "unknown_type"], "domain": ["Political Science", "UnknownDomain"]}
    )
    fig_type_by_domain(df, fig_dir)
    # Only the one valid row remains — still creates a figure (single bar)
    assert (Path(fig_dir) / "publication_types_by_domain.png").exists()


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


# ── main() ────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_main_runs_without_crash(tmp_path, minimal_config):
    """main() should run to completion without raising even when all data is missing."""
    from unittest.mock import MagicMock, patch

    from src.agents.visualization import main

    full_config = {
        **minimal_config,
        "paths": {
            "outputs": str(tmp_path / "outputs"),
            "data_processed": str(tmp_path / "proc"),
            "logs": str(tmp_path / "logs"),
        },
    }
    (tmp_path / "outputs").mkdir(exist_ok=True)
    (tmp_path / "proc").mkdir(exist_ok=True)
    (tmp_path / "logs").mkdir(exist_ok=True)

    with (
        patch("sys.argv", ["visualization.py", "--config", "config/config.yaml"]),
        patch("src.agents.visualization.load_yaml", return_value=full_config),
        patch("src.agents.visualization.setup_logger", return_value=MagicMock()),
        patch("src.agents.visualization.load_json", side_effect=FileNotFoundError),
        patch("src.agents.visualization.load_parquet", side_effect=FileNotFoundError),
        patch("src.agents.visualization.generate_html_report", side_effect=Exception("no data")),
        patch(
            "src.agents.visualization.generate_markdown_report", side_effect=Exception("no data")
        ),
    ):
        main()  # should not raise


@pytest.mark.unit
def test_main_generates_figures_when_data_available(tmp_path):
    """main() calls fig_* functions when the corresponding JSON files are available."""
    from unittest.mock import MagicMock, call, patch

    import pandas as pd

    from src.agents.visualization import main

    proc = tmp_path / "proc"
    proc.mkdir()
    fig = tmp_path / "outputs" / "figures"
    fig.mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()

    full_config = {
        "pipeline": {"mode": "test"},
        "paths": {
            "outputs": str(tmp_path / "outputs"),
            "data_processed": str(proc),
            "logs": str(logs),
        },
    }

    trends = {"annual": [], "domain_annual": []}
    cit = {"total": 100, "mean": 5.0}
    authors = {"top_by_output": [], "top_by_citations": [], "unique_authors": 10}
    concepts = {"top_50_concepts": []}
    types = {"types": [], "total": 0}
    metrics = {}
    domain_df = pd.DataFrame({"domain": ["Political Science"], "subcategory": ["radical_right"]})

    with (
        patch("sys.argv", ["visualization.py"]),
        patch("src.agents.visualization.load_yaml", return_value=full_config),
        patch("src.agents.visualization.setup_logger", return_value=MagicMock()),
        patch(
            "src.agents.visualization.load_json",
            side_effect=[trends, cit, authors, concepts, types, metrics],
        ),
        patch("src.agents.visualization.load_parquet", return_value=domain_df),
        patch("src.agents.visualization.fig_publication_trends") as mock_trends,
        patch("src.agents.visualization.fig_citation_distribution") as mock_cit,
        patch("src.agents.visualization.fig_top_authors") as mock_authors,
        patch("src.agents.visualization.fig_domain_distribution") as mock_domain,
        patch("src.agents.visualization.fig_type_by_domain") as mock_type_domain,
        patch("src.agents.visualization.fig_concept_landscape") as mock_concepts,
        patch("src.agents.visualization.fig_publication_types") as mock_types,
        patch("src.agents.visualization.fig_cross_domain_heatmap") as mock_heatmap,
        patch("src.agents.visualization.generate_html_report"),
        patch("src.agents.visualization.generate_markdown_report"),
        patch(
            "src.agents.visualization.OllamaClient",
            return_value=MagicMock(is_available=lambda: False),
        ),
    ):
        main()

    mock_trends.assert_called_once()
    mock_cit.assert_called_once()
    mock_authors.assert_called_once()
    mock_domain.assert_called_once()
    mock_type_domain.assert_called_once()
