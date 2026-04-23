"""
Unit tests for src/agents/validation/validators.py
Uses tmp_path for all file I/O — no external services.
"""

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src.agents.validation.validators import (
    _check,
    _make_report,
    validate_classification,
    validate_data,
    validate_network,
    validate_statistical,
)


# ── Config helper ─────────────────────────────────────────────────────────────


@pytest.fixture
def cfg(tmp_path):
    raw = tmp_path / "raw"
    clean = tmp_path / "clean"
    proc = tmp_path / "processed"
    logs = tmp_path / "logs"
    outputs = tmp_path / "outputs"
    for d in (raw, clean, proc, logs, outputs):
        d.mkdir(parents=True)
    return {
        "paths": {
            "data_raw": str(raw),
            "data_clean": str(clean),
            "data_processed": str(proc),
            "logs": str(logs),
            "outputs": str(outputs),
        }
    }


# ── _make_report ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_make_report_default_pass():
    r = _make_report("test_agent")
    assert r["status"] == "PASS"
    assert r["errors"] == []
    assert r["warnings"] == []
    assert r["agent"] == "test_agent"


@pytest.mark.unit
def test_make_report_with_stage():
    r = _make_report("data_validator", stage="D1")
    assert r["stage"] == "D1"


@pytest.mark.unit
def test_make_report_has_timestamp():
    r = _make_report("a")
    assert "timestamp" in r and r["timestamp"]


# ── _check ────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_passing_does_not_add_error():
    r = _make_report("a")
    _check(r, "my_check", True, "all good")
    assert r["status"] == "PASS"
    assert len(r["errors"]) == 0
    assert r["checks"][0]["passed"] is True


@pytest.mark.unit
def test_check_failing_sets_fail_status():
    r = _make_report("a")
    _check(r, "my_check", False, "something broke")
    assert r["status"] == "FAIL"
    assert "my_check" in r["errors"][0]


@pytest.mark.unit
def test_check_warning_does_not_set_fail():
    r = _make_report("a")
    _check(r, "warn_check", False, "advisory only", is_error=False)
    assert r["status"] == "PASS"
    assert len(r["warnings"]) == 1
    assert len(r["errors"]) == 0


@pytest.mark.unit
def test_check_appends_to_checks_list():
    r = _make_report("a")
    _check(r, "c1", True)
    _check(r, "c2", False, "bad", is_error=False)
    assert len(r["checks"]) == 2


# ── validate_data ─────────────────────────────────────────────────────────────


def _make_raw_parquet(raw_dir: str) -> None:
    df = pd.DataFrame(
        {
            "id": [f"https://openalex.org/W{i}" for i in range(1, 4)],
            "title": ["Title A", "Title B", "Title C"],
            "year": [2018, 2020, 2022],
            "cited_by_count": [10, 5, 0],
            "authors": [[], [], []],
            "concepts": [
                [{"display_name": "Populism"}],
                [{"display_name": "Economics"}],
                [{"display_name": "Sociology"}],
            ],
            "references": [[], [], []],
            "abstract": ["Abstract A " * 5, "Abstract B " * 5, "Abstract C " * 5],
        }
    )
    df.to_parquet(Path(raw_dir) / "openalex_raw_20240101.parquet", engine="pyarrow")


def _make_clean_parquet(clean_dir: str) -> None:
    df = pd.DataFrame(
        {
            "id": [f"https://openalex.org/W{i}" for i in range(1, 4)],
            "title": ["Title A", "Title B", "Title C"],
            "year": [2018, 2020, 2022],
            "cited_by_count": [10, 5, 0],
            "authors": [[], [], []],
            "concepts": [[], [], []],
            "references": [[], [], []],
            "abstract": ["Abstract A " * 5, "Abstract B " * 5, "Abstract C " * 5],
            "has_abstract": [True, True, True],
            "has_concepts": [False, False, False],
            "author_count": [1, 1, 1],
            "domain_preliminary": ["Political Science", "Economics", "Sociology"],
            "decade": [2010, 2020, 2020],
            "country_list": [[], [], []],
        }
    )
    df.to_parquet(Path(clean_dir) / "openalex_clean.parquet", engine="pyarrow")


@pytest.mark.unit
def test_validate_data_d1_pass(cfg, tmp_path):
    _make_raw_parquet(cfg["paths"]["data_raw"])
    report = validate_data(cfg, stage="D1")
    assert report["status"] == "PASS"
    assert report["n_records"] == 3


@pytest.mark.unit
def test_validate_data_d1_missing_file(cfg):
    report = validate_data(cfg, stage="D1")
    assert report["status"] == "FAIL"
    assert any("file_exists" in e for e in report["errors"])


@pytest.mark.unit
def test_validate_data_d2_pass(cfg):
    _make_clean_parquet(cfg["paths"]["data_clean"])
    report = validate_data(cfg, stage="D2")
    assert report["status"] == "PASS"


@pytest.mark.unit
def test_validate_data_d2_missing_file(cfg):
    report = validate_data(cfg, stage="D2")
    assert report["status"] == "FAIL"


@pytest.mark.unit
def test_validate_data_writes_json(cfg):
    _make_raw_parquet(cfg["paths"]["data_raw"])
    validate_data(cfg, stage="D1")
    log_file = Path(cfg["paths"]["logs"]) / "validation_data_D1.json"
    assert log_file.exists()
    data = json.loads(log_file.read_text())
    assert data["agent"] == "data_validator"


@pytest.mark.unit
def test_validate_data_negative_citations(cfg):
    df = pd.DataFrame(
        {
            "id": ["https://openalex.org/W1"],
            "title": ["T1"],
            "year": [2020],
            "cited_by_count": [-5],
            "authors": [[]],
            "concepts": [[]],
            "references": [[]],
            "abstract": ["x" * 30],
        }
    )
    df.to_parquet(Path(cfg["paths"]["data_raw"]) / "openalex_raw_test.parquet", engine="pyarrow")
    report = validate_data(cfg, stage="D1")
    assert any("citations_non_negative" in e for e in report["errors"])


# ── validate_statistical ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_validate_statistical_missing_files(cfg):
    report = validate_statistical(cfg)
    assert any("file_exists" in c["name"] and not c["passed"] for c in report["checks"])


@pytest.mark.unit
def test_validate_statistical_with_valid_files(cfg):
    proc = Path(cfg["paths"]["data_processed"])
    (proc / "bibliometric_summary.json").write_text(json.dumps({"n_records": 500}))
    (proc / "publication_trends.json").write_text(
        json.dumps({"annual": [{"year": 2020, "count": 100, "yoy_growth_pct": 10}]})
    )
    (proc / "top_authors.json").write_text(json.dumps({"lotka_alpha": 2.1, "lotka_r2": 0.85}))
    report = validate_statistical(cfg)
    assert report["status"] == "PASS"
    assert all(c["passed"] for c in report["checks"] if "file_exists" in c["name"])


@pytest.mark.unit
def test_validate_statistical_writes_json(cfg):
    validate_statistical(cfg)
    assert (Path(cfg["paths"]["logs"]) / "validation_statistical.json").exists()


@pytest.mark.unit
def test_validate_statistical_extreme_yoy(cfg):
    proc = Path(cfg["paths"]["data_processed"])
    (proc / "bibliometric_summary.json").write_text(json.dumps({"n_records": 100}))
    (proc / "publication_trends.json").write_text(
        json.dumps({"annual": [{"year": 2020, "count": 500, "yoy_growth_pct": 600}]})
    )
    (proc / "top_authors.json").write_text(json.dumps({}))
    report = validate_statistical(cfg)
    assert any("no_extreme_yoy_spike" in c["name"] and not c["passed"] for c in report["checks"])


# ── validate_classification ───────────────────────────────────────────────────


def _make_classified_parquet(proc_dir: str) -> None:
    df = pd.DataFrame(
        {
            "id": ["https://openalex.org/W1", "https://openalex.org/W2"],
            "domain": ["Political Science", "Economics"],
            "subcategory": ["radical_right", "political_economy"],
            "domain_confidence": [0.85, 0.92],
            "domain_source": ["llm", "embedding"],
        }
    )
    df.to_parquet(Path(proc_dir) / "classified_works.parquet", engine="pyarrow")


@pytest.mark.unit
def test_validate_classification_pass(cfg):
    _make_classified_parquet(cfg["paths"]["data_processed"])
    report = validate_classification(cfg)
    assert report["status"] == "PASS"
    assert report["n_records"] == 2


@pytest.mark.unit
def test_validate_classification_missing_file(cfg):
    report = validate_classification(cfg)
    assert report["status"] == "FAIL"


@pytest.mark.unit
def test_validate_classification_invalid_domain(cfg):
    df = pd.DataFrame(
        {
            "id": ["W1"],
            "domain": ["InvalidDomain"],
            "subcategory": ["radical_right"],
            "domain_confidence": [0.9],
        }
    )
    df.to_parquet(
        Path(cfg["paths"]["data_processed"]) / "classified_works.parquet", engine="pyarrow"
    )
    report = validate_classification(cfg)
    assert any("all_domains_valid" in e for e in report["errors"])


@pytest.mark.unit
def test_validate_classification_confidence_out_of_range(cfg):
    df = pd.DataFrame(
        {
            "id": ["W1"],
            "domain": ["Political Science"],
            "subcategory": ["radical_right"],
            "domain_confidence": [1.5],
        }
    )
    df.to_parquet(
        Path(cfg["paths"]["data_processed"]) / "classified_works.parquet", engine="pyarrow"
    )
    report = validate_classification(cfg)
    assert any("confidence_in_range" in e for e in report["errors"])


@pytest.mark.unit
def test_validate_classification_writes_json(cfg):
    _make_classified_parquet(cfg["paths"]["data_processed"])
    validate_classification(cfg)
    assert (Path(cfg["paths"]["logs"]) / "validation_classification.json").exists()


# ── validate_network ──────────────────────────────────────────────────────────


def _write_graphml(path: Path, n_nodes: int = 4) -> None:
    G = nx.Graph()
    for i in range(n_nodes):
        G.add_node(f"W{i}")
    for i in range(n_nodes - 1):
        G.add_edge(f"W{i}", f"W{i+1}", weight=i + 1)
    nx.write_graphml(G, str(path))


def _make_network_files(cfg: dict) -> None:
    net_dir = Path(cfg["paths"]["outputs"]) / "networks"
    net_dir.mkdir(parents=True, exist_ok=True)
    _write_graphml(net_dir / "bibcoupling_network_vos.graphml")
    _write_graphml(net_dir / "cocitation_network_vos.graphml")
    _write_graphml(net_dir / "coauthorship_network.graphml")

    proc = Path(cfg["paths"]["data_processed"])
    metrics = {"bibcoupling": {"nodes": 4, "edges": 3}}
    (proc / "network_metrics.json").write_text(json.dumps(metrics))

    cluster_df = pd.DataFrame(
        {
            "work_id": ["W0", "W1", "W2", "W3"],
            "cluster_id_louvain": [0, 0, 1, 1],
            "betweenness_centrality": [0.1, 0.2, 0.05, 0.3],
        }
    )
    cluster_df.to_parquet(proc / "cluster_assignments.parquet", engine="pyarrow")


@pytest.mark.unit
def test_validate_network_pass(cfg):
    _make_network_files(cfg)
    report = validate_network(cfg)
    assert report["status"] == "PASS"


@pytest.mark.unit
def test_validate_network_missing_bibcoupling(cfg):
    net_dir = Path(cfg["paths"]["outputs"]) / "networks"
    net_dir.mkdir(parents=True)
    report = validate_network(cfg)
    assert report["status"] == "FAIL"
    assert any("file_exists_bibcoupling" in e for e in report["errors"])


@pytest.mark.unit
def test_validate_network_writes_json(cfg):
    _make_network_files(cfg)
    validate_network(cfg)
    assert (Path(cfg["paths"]["logs"]) / "validation_network.json").exists()


@pytest.mark.unit
def test_validate_network_bc_out_of_range(cfg):
    _make_network_files(cfg)
    proc = Path(cfg["paths"]["data_processed"])
    cluster_df = pd.DataFrame(
        {
            "work_id": ["W0", "W1"],
            "cluster_id_louvain": [0, 1],
            "betweenness_centrality": [1.5, 0.3],
        }
    )
    cluster_df.to_parquet(proc / "cluster_assignments.parquet", engine="pyarrow")
    report = validate_network(cfg)
    assert any("betweenness_centrality_in_range" in e for e in report["errors"])


@pytest.mark.unit
def test_validate_network_no_self_loops(cfg):
    _make_network_files(cfg)
    report = validate_network(cfg)
    self_loop_checks = [c for c in report["checks"] if "no_self_loops" in c["name"]]
    assert all(c["passed"] for c in self_loop_checks)
