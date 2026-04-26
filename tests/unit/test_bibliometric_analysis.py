"""
Unit tests for src/agents/bibliometric_analysis.py
Pure DataFrame operations — no file I/O, no external APIs.
"""

import pandas as pd
import pytest

from src.agents.bibliometric_analysis import (
    _extract_author_identity,
    author_productivity,
    author_productivity_metrics,
    citation_stats,
    compute_gindex,
    compute_hindex,
    concept_landscape,
    detect_self_citations,
    institution_analysis,
    journal_analysis,
    publication_trends,
    publication_type_stats,
    safe_div,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_df():
    return pd.DataFrame(
        {
            "id": ["W1", "W2", "W3", "W4", "W5"],
            "year": [2018, 2019, 2020, 2020, 2021],
            "cited_by_count": [10, 0, 5, 20, 3],
            "authors": [
                [{"id": "A1", "name": "Alice"}],
                [{"id": "A2", "name": "Bob"}],
                [{"id": "A1", "name": "Alice"}, {"id": "A3", "name": "Carol"}],
                [{"id": "A2", "name": "Bob"}],
                [{"id": "A1", "name": "Alice"}],
            ],
            "institutions": [
                [{"id": "I1", "name": "Univ A"}],
                [{"id": "I2", "name": "Univ B"}],
                [{"id": "I1", "name": "Univ A"}],
                [],
                [{"id": "I1", "name": "Univ A"}],
            ],
            "concepts": [
                [{"name": "Populism"}, {"name": "Democracy"}],
                [{"name": "Populism"}, {"name": "Economics"}],
                [{"name": "Democracy"}],
                [{"name": "Populism"}],
                [],
            ],
            "journal": ["Journal A", "Journal B", "Journal A", "", "Journal C"],
            "type": ["article", "book-chapter", "article", "preprint", "article"],
        }
    )


# ── compute_hindex ─────────────────────────────────────────────────────────────


def test_hindex_basic():
    assert compute_hindex([10, 8, 5, 4, 3]) == 4


def test_hindex_all_zeros():
    assert compute_hindex([0, 0, 0]) == 0


def test_hindex_single():
    assert compute_hindex([1]) == 1


def test_hindex_all_equal():
    assert compute_hindex([3, 3, 3, 3]) == 3


def test_hindex_early_break():
    # After h=2, the third paper (count=1) breaks the loop
    assert compute_hindex([5, 5, 1]) == 2


# ── compute_gindex ─────────────────────────────────────────────────────────────


def test_gindex_basic():
    # sorted: [10, 8, 5, 4] → cumsum: 10, 18, 23, 27 vs 1,4,9,16 → g=4
    assert compute_gindex([10, 8, 5, 4]) == 4


def test_gindex_all_zeros():
    assert compute_gindex([0, 0, 0]) == 0


def test_gindex_single_high():
    # cumsum after 1 paper = 100 >= 1^2 → g=1; no 2nd paper → g=1
    assert compute_gindex([100]) == 1


def test_gindex_early_break():
    # sorted: [10, 1] → cumsum[1]=10>=1 (g=1), cumsum[2]=11>=4 (g=2); no 3rd paper → g=2
    assert compute_gindex([10, 1]) == 2


# ── safe_div ───────────────────────────────────────────────────────────────────


def test_safe_div_normal():
    assert safe_div(10.0, 4.0) == 2.5


def test_safe_div_zero_denominator():
    assert safe_div(10.0, 0.0) == 0.0


def test_safe_div_custom_default():
    assert safe_div(5.0, 0.0, default=-1.0) == -1.0


# ── publication_trends ─────────────────────────────────────────────────────────


def test_publication_trends_basic(minimal_df):
    result = publication_trends(minimal_df)
    assert result["total_records"] == 5
    assert result["year_range"] == [2018, 2021]
    years = [r["year"] for r in result["annual"]]
    assert 2018 in years and 2021 in years


def test_publication_trends_empty():
    result = publication_trends(pd.DataFrame())
    assert result["total_records"] == 0
    assert result["annual"] == []
    assert result["year_range"] == [None, None]


def test_publication_trends_with_decade(minimal_df):
    minimal_df["decade"] = (minimal_df["year"] // 10) * 10
    result = publication_trends(minimal_df)
    assert len(result["decadal"]) > 0


def test_publication_trends_with_domain_preliminary(minimal_df):
    minimal_df["domain_preliminary"] = ["Pol.Sci"] * 5
    result = publication_trends(minimal_df)
    assert len(result["domain_annual"]) > 0


def test_publication_trends_no_domain_preliminary(minimal_df):
    result = publication_trends(minimal_df)
    assert result["domain_annual"] == []


# ── citation_stats ─────────────────────────────────────────────────────────────


def test_citation_stats_basic(minimal_df):
    result = citation_stats(minimal_df)
    assert result["n"] == 5
    assert result["total_citations"] == 38
    assert result["h_index"] == result["h_index_corpus"]
    assert result["g_index"] == result["g_index_corpus"]
    assert 0.0 <= result["zero_citation_rate"] <= 1.0


def test_citation_stats_empty():
    result = citation_stats(pd.DataFrame())
    assert result["total_citations"] == 0
    assert result["h_index"] == 0


def test_citation_stats_missing_column():
    df = pd.DataFrame({"id": ["W1"]})
    result = citation_stats(df)
    assert result["n"] == 0


def test_citation_stats_all_zeros():
    df = pd.DataFrame({"cited_by_count": [0, 0, 0]})
    result = citation_stats(df)
    assert result["zero_citation_rate"] == 1.0
    assert result["h_index"] == 0


def test_citation_stats_percentiles_present(minimal_df):
    result = citation_stats(minimal_df)
    assert "p50" in result["percentiles"]
    assert "p90" in result["percentiles"]


# ── _extract_author_identity ───────────────────────────────────────────────────


def test_extract_author_dict():
    aid, name = _extract_author_identity({"id": "A1", "name": "Alice"})
    assert aid == "A1"
    assert name == "Alice"


def test_extract_author_dict_no_id_uses_name():
    aid, name = _extract_author_identity({"name": "Bob"})
    assert aid == "Bob"
    assert name == "Bob"


def test_extract_author_string():
    aid, name = _extract_author_identity("Carol")
    assert aid == "Carol"
    assert name == "Carol"


def test_extract_author_unknown_type():
    aid, name = _extract_author_identity(42)
    assert aid == ""
    assert name == ""


# ── author_productivity ────────────────────────────────────────────────────────


def test_author_productivity_basic(minimal_df):
    result = author_productivity(minimal_df)
    assert result["unique_authors"] == 3  # Alice, Bob, Carol
    assert len(result["top_by_output"]) <= 20
    alice = next(a for a in result["top_by_output"] if a["name"] == "Alice")
    assert alice["paper_count"] == 3


def test_author_productivity_empty():
    df = pd.DataFrame({"authors": [[]], "cited_by_count": [0]})
    result = author_productivity(df)
    assert result["unique_authors"] == 0


def test_author_productivity_metrics_is_alias(minimal_df):
    assert author_productivity(minimal_df) == author_productivity_metrics(minimal_df)


def test_author_productivity_lotka_with_enough_authors():
    authors = [[{"id": f"A{i}", "name": f"Auth{i}"}] for i in range(20)]
    cited = [i % 5 for i in range(20)]
    df = pd.DataFrame({"authors": authors, "cited_by_count": cited})
    result = author_productivity(df)
    # With 20 single-paper authors freq dict has only 1 key → lotka skipped
    assert "lotka_alpha" in result


# ── detect_self_citations ──────────────────────────────────────────────────────


def test_detect_self_citations_basic():
    records = [
        {"citing_author": "Alice", "cited_authors": ["Alice", "Bob"]},
        {"citing_author": "Bob", "cited_authors": ["Alice", "Carol"]},
    ]
    counts = detect_self_citations(records)
    assert counts == [1, 0]


def test_detect_self_citations_empty_list():
    assert detect_self_citations([]) == []


def test_detect_self_citations_none_input():
    assert detect_self_citations(None) == []


def test_detect_self_citations_empty_citing_author():
    records = [{"citing_author": "", "cited_authors": ["Alice"]}]
    counts = detect_self_citations(records)
    assert counts == [0]


def test_detect_self_citations_case_insensitive():
    records = [{"citing_author": "ALICE", "cited_authors": ["alice"]}]
    counts = detect_self_citations(records)
    assert counts == [1]


# ── journal_analysis ───────────────────────────────────────────────────────────


def test_journal_analysis_basic(minimal_df):
    result = journal_analysis(minimal_df)
    assert result["unique_journals"] == 3  # Journal A, B, C (empty string excluded)
    top = result["top_by_output"]
    assert top[0]["paper_count"] >= top[-1]["paper_count"]


def test_journal_analysis_no_column():
    df = pd.DataFrame({"id": ["W1"]})
    result = journal_analysis(df)
    assert result["unique_journals"] == 0


def test_journal_analysis_empty_df():
    df = pd.DataFrame({"journal": [], "id": [], "cited_by_count": []})
    result = journal_analysis(df)
    assert result["unique_journals"] == 0


def test_journal_analysis_bradford_zones_present(minimal_df):
    result = journal_analysis(minimal_df)
    zones = result["bradford_zones"]
    assert "zone1_journals" in zones
    assert "zone2_journals" in zones
    assert "zone3_journals" in zones


# ── institution_analysis ───────────────────────────────────────────────────────


def test_institution_analysis_basic(minimal_df):
    result = institution_analysis(minimal_df)
    assert result["unique_institutions"] == 2
    top = result["top_by_output"]
    assert top[0]["id"] == "I1"  # Univ A appears 3 times
    assert top[0]["paper_count"] == 3


def test_institution_analysis_empty_institutions():
    df = pd.DataFrame({"institutions": [[]], "cited_by_count": [5]})
    result = institution_analysis(df)
    assert result["unique_institutions"] == 0


def test_institution_analysis_deduplicates_per_paper(minimal_df):
    # A paper with the same institution listed twice should count as 1
    df = pd.DataFrame(
        {
            "institutions": [[{"id": "I1", "name": "Univ A"}, {"id": "I1", "name": "Univ A"}]],
            "cited_by_count": [10],
        }
    )
    result = institution_analysis(df)
    assert result["top_by_output"][0]["paper_count"] == 1


# ── concept_landscape ─────────────────────────────────────────────────────────


def test_concept_landscape_basic(minimal_df):
    result = concept_landscape(minimal_df)
    top = result["top_50_concepts"]
    assert len(top) > 0
    # Populism appears in 3 papers
    populism = next(c for c in top if c["concept"] == "Populism")
    assert populism["count"] == 3


def test_concept_landscape_empty_concepts():
    df = pd.DataFrame({"concepts": [[]]})
    result = concept_landscape(df)
    assert result["top_50_concepts"] == []


def test_concept_landscape_cooccurrence_matrix(minimal_df):
    result = concept_landscape(minimal_df)
    matrix = result["cooccurrence_matrix_top20"]
    # Populism and Democracy co-occur in paper W1
    assert matrix.get("Populism", {}).get("Democracy", 0) >= 1


# ── publication_type_stats ─────────────────────────────────────────────────────


def test_publication_type_stats_basic(minimal_df):
    result = publication_type_stats(minimal_df)
    assert result["total"] == 5
    types = {r["type"] for r in result["types"]}
    assert "article" in types
    assert "book-chapter" in types


def test_publication_type_stats_percentages_sum_to_100(minimal_df):
    result = publication_type_stats(minimal_df)
    total_pct = sum(r["percentage"] for r in result["types"])
    assert abs(total_pct - 100.0) < 0.1


def test_publication_type_stats_cumulative_ends_at_100(minimal_df):
    result = publication_type_stats(minimal_df)
    last = result["types"][-1]["cumulative_percentage"]
    assert abs(last - 100.0) < 0.1


def test_publication_type_stats_no_type_column():
    df = pd.DataFrame({"id": ["W1"]})
    result = publication_type_stats(df)
    assert result["total"] == 0
    assert result["types"] == []


def test_publication_type_stats_empty_df():
    result = publication_type_stats(pd.DataFrame())
    assert result["total"] == 0


# ── main() ────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_main_runs_without_error(tmp_path):
    """main() should call all analysis functions and save JSON outputs."""
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    import pandas as pd

    from src.agents.bibliometric_analysis import main

    proc = tmp_path / "processed"
    proc.mkdir()
    clean = tmp_path / "clean"
    clean.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()

    config = {
        "paths": {
            "data_clean": str(clean),
            "data_processed": str(proc),
            "logs": str(logs),
        }
    }

    df = pd.DataFrame(
        {
            "id": ["W1", "W2"],
            "year": [2019, 2020],
            "cited_by_count": [5, 10],
            "authors": [[{"id": "A1", "name": "Alice"}], [{"id": "A2", "name": "Bob"}]],
            "journal": ["J1", "J2"],
            "institution": ["Inst1", "Inst2"],
            "concepts": [[], []],
            "type": ["article", "article"],
            "is_open_access": [True, False],
            "abstract": ["abstract one", "abstract two"],
        }
    )

    with (
        patch("sys.argv", ["bibliometric_analysis.py"]),
        patch("src.agents.bibliometric_analysis.load_yaml", return_value=config),
        patch("src.agents.bibliometric_analysis.setup_logger", return_value=MagicMock()),
        patch("src.agents.bibliometric_analysis.load_parquet", return_value=df),
        patch("src.agents.bibliometric_analysis.save_json") as mock_save_json,
    ):
        main()

    assert mock_save_json.call_count >= 6


@pytest.mark.unit
def test_main_saves_all_expected_outputs(tmp_path):
    """main() should save JSON for trends, citations, authors, journals, institutions, concepts, types."""
    from unittest.mock import MagicMock, call, patch

    import pandas as pd

    from src.agents.bibliometric_analysis import main

    config = {
        "paths": {
            "data_clean": str(tmp_path),
            "data_processed": str(tmp_path),
            "logs": str(tmp_path),
        }
    }

    df = pd.DataFrame(
        {
            "id": ["W1"],
            "year": [2020],
            "cited_by_count": [3],
            "authors": [[{"id": "A1", "name": "Alice"}]],
            "journal": ["J1"],
            "institution": ["Inst1"],
            "concepts": [[]],
            "type": ["article"],
            "is_open_access": [True],
            "abstract": ["abstract"],
        }
    )

    from pathlib import Path

    saved_paths = []

    def capture_save(data, path):
        saved_paths.append(Path(path).name)

    with (
        patch("sys.argv", ["bibliometric_analysis.py"]),
        patch("src.agents.bibliometric_analysis.load_yaml", return_value=config),
        patch("src.agents.bibliometric_analysis.setup_logger", return_value=MagicMock()),
        patch("src.agents.bibliometric_analysis.load_parquet", return_value=df),
        patch("src.agents.bibliometric_analysis.save_json", side_effect=capture_save),
    ):
        main()

    expected = {
        "publication_trends.json",
        "citation_stats.json",
        "top_authors.json",
        "top_journals.json",
        "top_institutions.json",
        "concept_landscape.json",
        "publication_types.json",
        "bibliometric_summary.json",
    }
    assert expected <= set(saved_paths)
