"""
Unit tests for src/utils/metrics.py
All tests operate on in-memory NetworkX graphs — no file I/O, no external APIs.
"""

import networkx as nx
import pytest

from src.utils.metrics import (
    compute_association_strength,
    compute_coupling_strength_index,
    compute_domain_reach,
    compute_inter_domain_coupling_ratio,
    compute_jaccard_similarity,
    enhanced_cross_domain_analysis,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_graph():
    """
    4-node graph spanning 2 domains (PS / Econ):
      node1(PS) --5-- node2(Econ)
      node1(PS) --3-- node3(PS)
      node2(Econ) --2-- node4(Econ)
      node3(PS) --1-- node4(Econ)
    """
    G = nx.Graph()
    G.add_edge("node1", "node2", weight=5)
    G.add_edge("node1", "node3", weight=3)
    G.add_edge("node2", "node4", weight=2)
    G.add_edge("node3", "node4", weight=1)
    domain_map = {
        "node1": "PS",
        "node2": "Econ",
        "node3": "PS",
        "node4": "Econ",
    }
    return G, domain_map


@pytest.fixture
def empty_graph():
    G = nx.Graph()
    G.add_nodes_from(["a", "b"])
    domain_map = {"a": "PS", "b": "Econ"}
    return G, domain_map


@pytest.fixture
def single_domain_graph():
    G = nx.Graph()
    G.add_edge("a", "b", weight=4)
    G.add_edge("b", "c", weight=2)
    domain_map = {"a": "PS", "b": "PS", "c": "PS"}
    return G, domain_map


# ── compute_association_strength ─────────────────────────────────────────────


@pytest.mark.unit
def test_association_strength_returns_all_domain_pairs(simple_graph):
    G, dm = simple_graph
    result = compute_association_strength(G, dm)
    assert set(result.keys()) == {"PS", "Econ"}
    assert set(result["PS"].keys()) == {"PS", "Econ"}


@pytest.mark.unit
def test_association_strength_positive_values(simple_graph):
    G, dm = simple_graph
    result = compute_association_strength(G, dm)
    for d1 in result:
        for d2, val in result[d1].items():
            assert val >= 0.0


@pytest.mark.unit
def test_association_strength_empty_graph_returns_zeros(empty_graph):
    G, dm = empty_graph
    result = compute_association_strength(G, dm)
    for d1 in result:
        for d2, val in result[d1].items():
            assert val == 0.0


@pytest.mark.unit
def test_association_strength_cross_domain_above_one(simple_graph):
    """Cross-domain PS-Econ coupling should be stronger than random (AS > 1)."""
    G, dm = simple_graph
    result = compute_association_strength(G, dm)
    assert result["PS"]["Econ"] > 1.0


@pytest.mark.unit
def test_association_strength_single_domain(single_domain_graph):
    G, dm = single_domain_graph
    result = compute_association_strength(G, dm)
    assert "PS" in result
    assert result["PS"]["PS"] > 0


# ── compute_coupling_strength_index ──────────────────────────────────────────


@pytest.mark.unit
def test_csi_returns_correct_structure(simple_graph):
    G, dm = simple_graph
    result = compute_coupling_strength_index(G, dm)
    assert set(result.keys()) == {"PS", "Econ"}
    for d1 in result:
        assert set(result[d1].keys()) == {"PS", "Econ"}


@pytest.mark.unit
def test_csi_values_non_negative(simple_graph):
    """CSI is non-negative but not bounded to 1 (can exceed 1 when coupling > min degree)."""
    G, dm = simple_graph
    result = compute_coupling_strength_index(G, dm)
    for d1 in result:
        for d2, val in result[d1].items():
            assert val >= 0.0


@pytest.mark.unit
def test_csi_empty_graph_all_zero(empty_graph):
    G, dm = empty_graph
    result = compute_coupling_strength_index(G, dm)
    for d1 in result:
        for val in result[d1].values():
            assert val == 0.0


# ── compute_jaccard_similarity ───────────────────────────────────────────────


@pytest.mark.unit
def test_jaccard_diagonal_is_one(simple_graph):
    G, dm = simple_graph
    result = compute_jaccard_similarity(G, dm)
    for d in result:
        assert result[d][d] == 1.0


@pytest.mark.unit
def test_jaccard_cross_domain_nonzero_when_coupled(simple_graph):
    """Cross-domain Jaccard is non-zero when edges exist between the two domains."""
    G, dm = simple_graph
    result = compute_jaccard_similarity(G, dm)
    # simple_graph has cross-domain edges, so coupling-weight Jaccard > 0
    assert result["PS"]["Econ"] > 0.0
    assert result["Econ"]["PS"] > 0.0


@pytest.mark.unit
def test_jaccard_cross_domain_zero_no_cross_edges():
    """Jaccard is 0 when there are no edges between the two domains."""
    G = nx.Graph()
    G.add_edge("a", "b", weight=2)  # both PS
    G.add_edge("c", "d", weight=3)  # both Econ
    dm = {"a": "PS", "b": "PS", "c": "Econ", "d": "Econ"}
    result = compute_jaccard_similarity(G, dm)
    assert result["PS"]["Econ"] == 0.0
    assert result["Econ"]["PS"] == 0.0


@pytest.mark.unit
def test_jaccard_range(simple_graph):
    G, dm = simple_graph
    result = compute_jaccard_similarity(G, dm)
    for d1 in result:
        for val in result[d1].values():
            assert 0.0 <= val <= 1.0


# ── compute_inter_domain_coupling_ratio ──────────────────────────────────────


@pytest.mark.unit
def test_idcr_between_zero_and_one(simple_graph):
    G, dm = simple_graph
    result = compute_inter_domain_coupling_ratio(G, dm)
    assert 0.0 <= result <= 1.0


@pytest.mark.unit
def test_idcr_empty_graph_returns_zero(empty_graph):
    G, dm = empty_graph
    result = compute_inter_domain_coupling_ratio(G, dm)
    assert result == 0.0


@pytest.mark.unit
def test_idcr_single_domain_returns_zero(single_domain_graph):
    G, dm = single_domain_graph
    result = compute_inter_domain_coupling_ratio(G, dm)
    assert result == 0.0


@pytest.mark.unit
def test_idcr_cross_domain_edges_increase_ratio(simple_graph):
    """Graph has both intra- and inter-domain edges, so 0 < IDCR < 1."""
    G, dm = simple_graph
    result = compute_inter_domain_coupling_ratio(G, dm)
    assert 0.0 < result < 1.0


@pytest.mark.unit
def test_idcr_all_cross_domain():
    """Graph with only cross-domain edges should give IDCR = 1.0."""
    G = nx.Graph()
    G.add_edge("a", "b", weight=3)
    dm = {"a": "PS", "b": "Econ"}
    result = compute_inter_domain_coupling_ratio(G, dm)
    assert result == 1.0


# ── compute_domain_reach ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_domain_reach_keys(simple_graph):
    G, dm = simple_graph
    result = compute_domain_reach(G, dm)
    assert set(result.keys()) == {"PS", "Econ"}


@pytest.mark.unit
def test_domain_reach_has_required_fields(simple_graph):
    G, dm = simple_graph
    result = compute_domain_reach(G, dm)
    required = {
        "unique_connected_domains",
        "reach_breadth",
        "intra_domain_weight",
        "inter_domain_weight",
        "inter_domain_ratio",
    }
    for d in result:
        assert required <= set(result[d].keys())


@pytest.mark.unit
def test_domain_reach_breadth_between_zero_and_one(simple_graph):
    G, dm = simple_graph
    result = compute_domain_reach(G, dm)
    for d in result:
        assert 0.0 <= result[d]["reach_breadth"] <= 1.0


@pytest.mark.unit
def test_domain_reach_inter_ratio_between_zero_and_one(simple_graph):
    G, dm = simple_graph
    result = compute_domain_reach(G, dm)
    for d in result:
        assert 0.0 <= result[d]["inter_domain_ratio"] <= 1.0


@pytest.mark.unit
def test_domain_reach_single_domain_zero_inter(single_domain_graph):
    G, dm = single_domain_graph
    result = compute_domain_reach(G, dm)
    assert result["PS"]["inter_domain_weight"] == 0
    assert result["PS"]["inter_domain_ratio"] == 0


# ── enhanced_cross_domain_analysis ───────────────────────────────────────────


@pytest.mark.unit
def test_enhanced_analysis_has_all_keys(simple_graph):
    G, dm = simple_graph
    result = enhanced_cross_domain_analysis(G, dm)
    expected_keys = {
        "raw_coupling_matrix",
        "association_strength",
        "coupling_strength_index",
        "jaccard_similarity",
        "inter_domain_coupling_ratio",
        "domain_reach",
        "interpretation",
        "statistical_summary",
    }
    assert expected_keys <= set(result.keys())


@pytest.mark.unit
def test_enhanced_analysis_statistical_summary(simple_graph):
    G, dm = simple_graph
    result = enhanced_cross_domain_analysis(G, dm)
    stats = result["statistical_summary"]
    assert stats["n_nodes"] == 4
    assert stats["n_edges"] == 4
    assert stats["total_weight"] == 11
    assert stats["n_domains"] == 2


@pytest.mark.unit
def test_enhanced_analysis_raw_matrix_non_negative(simple_graph):
    G, dm = simple_graph
    result = enhanced_cross_domain_analysis(G, dm)
    matrix = result["raw_coupling_matrix"]
    for d1 in matrix:
        for val in matrix[d1].values():
            assert val >= 0


@pytest.mark.unit
def test_enhanced_analysis_idcr_matches_standalone(simple_graph):
    G, dm = simple_graph
    standalone = compute_inter_domain_coupling_ratio(G, dm)
    enhanced = enhanced_cross_domain_analysis(G, dm)
    assert enhanced["inter_domain_coupling_ratio"] == standalone


@pytest.mark.unit
def test_enhanced_analysis_network_density(simple_graph):
    G, dm = simple_graph
    result = enhanced_cross_domain_analysis(G, dm)
    density = result["statistical_summary"]["network_density"]
    assert 0.0 <= density <= 1.0
