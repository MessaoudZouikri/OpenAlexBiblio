"""
Unit tests for src/agents/network_analysis.py
Pure graph / DataFrame operations — no file I/O beyond tmp_path, no external APIs.
"""

from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

from src.agents.network_analysis import (
    _auto_min_shared,
    _coerce_edge_weight,
    apply_vos_thresholding,
    association_strength_normalization,
    build_bibcoupling_network,
    build_coauthorship_network,
    build_cocitation_network,
    build_concept_cooccurrence_network,
    build_subfield_bibcoupling_network,
    build_subfield_cocitation_network,
    cross_domain_matrix,
    detect_communities,
    enhanced_cross_domain_analysis,
    enhanced_graph_metrics,
    find_interdisciplinary_bridges,
    graph_summary,
    save_network,
    spectral_clustering,
    vos_layout,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_df():
    """5 papers with shared references, authors, concepts, domains."""
    return pd.DataFrame(
        {
            "id": ["W1", "W2", "W3", "W4", "W5"],
            "domain": [
                "Political Science",
                "Economics",
                "Political Science",
                "Sociology",
                "Other",
            ],
            "subcategory": [
                "radical_right",
                "political_economy",
                "radical_right",
                "social_movements",
                "other",
            ],
            "references": [
                ["R1", "R2", "R3"],
                ["R1", "R2", "R4"],
                ["R2", "R3", "R5"],
                ["R1", "R3"],
                ["R6"],
            ],
            "authors": [
                [{"id": "A1", "name": "Alice"}, {"id": "A2", "name": "Bob"}],
                [{"id": "A1", "name": "Alice"}, {"id": "A3", "name": "Carol"}],
                [{"id": "A2", "name": "Bob"}],
                [{"id": "A4", "name": "Dave"}],
                [{"id": "A1", "name": "Alice"}],
            ],
            "concepts": [
                [{"name": "Populism"}, {"name": "Democracy"}],
                [{"name": "Populism"}, {"name": "Economics"}],
                [{"name": "Democracy"}],
                [{"name": "Populism"}, {"name": "Democracy"}],
                [],
            ],
        }
    )


@pytest.fixture
def triangle_graph():
    """3-node fully connected weighted graph."""
    G = nx.Graph()
    G.add_edge("A", "B", weight=3)
    G.add_edge("B", "C", weight=2)
    G.add_edge("A", "C", weight=1)
    return G


@pytest.fixture
def star_graph():
    """5-node star (hub + 4 leaves)."""
    G = nx.Graph()
    for i in range(4):
        G.add_edge("hub", f"leaf{i}", weight=2)
    return G


@pytest.fixture
def disconnected_graph():
    """Two separate 3-cliques — 6 nodes, 6 edges, 2 components."""
    G = nx.Graph()
    G.add_edge("A", "B", weight=1)
    G.add_edge("B", "C", weight=1)
    G.add_edge("A", "C", weight=1)
    G.add_edge("X", "Y", weight=1)
    G.add_edge("Y", "Z", weight=1)
    G.add_edge("X", "Z", weight=1)
    return G


# ── _auto_min_shared ──────────────────────────────────────────────────────────


def test_auto_min_shared_small():
    assert _auto_min_shared(100) == 2


def test_auto_min_shared_boundary_5000():
    assert _auto_min_shared(4999) == 2
    assert _auto_min_shared(5000) == 3


def test_auto_min_shared_boundary_15000():
    assert _auto_min_shared(14999) == 3
    assert _auto_min_shared(15000) == 5


def test_auto_min_shared_boundary_30000():
    assert _auto_min_shared(29999) == 5
    assert _auto_min_shared(30000) == 10


def test_auto_min_shared_large():
    assert _auto_min_shared(100_000) == 10


# ── _coerce_edge_weight ───────────────────────────────────────────────────────


def test_coerce_edge_weight_dict_with_weight():
    assert _coerce_edge_weight({"weight": 5}) == 5.0


def test_coerce_edge_weight_dict_no_weight():
    assert _coerce_edge_weight({}) == 1.0


def test_coerce_edge_weight_non_dict():
    assert _coerce_edge_weight("hello") == 1.0


def test_coerce_edge_weight_none_value():
    assert _coerce_edge_weight({"weight": None}) == 1.0


def test_coerce_edge_weight_string_number():
    assert _coerce_edge_weight({"weight": "3.5"}) == 3.5


# ── graph_summary ─────────────────────────────────────────────────────────────


def test_graph_summary_empty():
    result = graph_summary(nx.Graph(), "empty")
    assert result["n_nodes"] == 0
    assert result["n_edges"] == 0
    assert result["network"] == "empty"


def test_graph_summary_single_node():
    G = nx.Graph()
    G.add_node("A")
    result = graph_summary(G, "single")
    assert result["n_nodes"] == 1
    assert result["n_edges"] == 0
    assert result["density"] == 0.0


def test_graph_summary_triangle(triangle_graph):
    result = graph_summary(triangle_graph, "triangle")
    assert result["n_nodes"] == 3
    assert result["n_edges"] == 3
    assert result["n_components"] == 1
    assert result["largest_component_size"] == 3
    assert result["density"] > 0.0


def test_graph_summary_disconnected(disconnected_graph):
    result = graph_summary(disconnected_graph, "disc")
    assert result["n_components"] == 2
    assert result["largest_component_size"] == 3


def test_graph_summary_no_edges_zero_clustering():
    G = nx.Graph()
    G.add_nodes_from(["A", "B", "C"])
    result = graph_summary(G, "no_edges")
    assert result["avg_clustering"] == 0.0


# ── detect_communities ────────────────────────────────────────────────────────


def test_detect_communities_empty():
    partition, modularity = detect_communities(nx.Graph())
    assert partition == {}
    assert modularity == 0.0


def test_detect_communities_no_edges():
    G = nx.Graph()
    G.add_nodes_from(["A", "B"])
    partition, modularity = detect_communities(G)
    assert modularity == 0.0


def test_detect_communities_triangle(triangle_graph):
    partition, modularity = detect_communities(triangle_graph)
    assert set(partition.keys()) == {"A", "B", "C"}
    assert isinstance(modularity, float)


def test_detect_communities_returns_all_nodes(disconnected_graph):
    partition, _ = detect_communities(disconnected_graph)
    assert set(partition.keys()) == set(disconnected_graph.nodes())


# ── build_cocitation_network ──────────────────────────────────────────────────


def test_build_cocitation_network_basic(simple_df):
    G = build_cocitation_network(simple_df, min_cocitations=2)
    # R1 cited by W1,W2,W4; R2 by W1,W2,W3; R3 by W1,W3,W4 → all eligible
    assert G.number_of_nodes() >= 3
    # (R1,R2) co-cited by W1 and W2 → weight=2
    assert G.has_edge("R1", "R2")
    assert G["R1"]["R2"]["weight"] == 2


def test_build_cocitation_network_threshold_respected(simple_df):
    # min_cocitations=3 → (R1,R2) co-cited by W1+W2 only = 2 < 3 → no edge
    G = build_cocitation_network(simple_df, min_cocitations=3)
    assert not G.has_edge("R1", "R2")


def test_build_cocitation_network_empty_refs():
    df = pd.DataFrame({"id": ["W1", "W2"], "references": [[], []]})
    G = build_cocitation_network(df)
    assert G.number_of_nodes() == 0
    assert G.number_of_edges() == 0


def test_build_cocitation_network_unique_refs_only(simple_df):
    # R4, R5, R6 are each cited by only 1 paper → not eligible → not in graph
    G = build_cocitation_network(simple_df)
    assert "R4" not in G.nodes()
    assert "R5" not in G.nodes()
    assert "R6" not in G.nodes()


# ── build_bibcoupling_network ─────────────────────────────────────────────────


def test_build_bibcoupling_network_basic(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=2)
    # W1 and W2 share R1 and R2 → weight=2 → edge exists
    assert G.has_edge("W1", "W2")
    assert G["W1"]["W2"]["weight"] == 2


def test_build_bibcoupling_network_domain_attributes(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    assert G.nodes["W1"]["domain"] == "Political Science"
    assert G.nodes["W2"]["domain"] == "Economics"


def test_build_bibcoupling_network_threshold_respected(simple_df):
    # W2 and W3 share only R2 → weight=1 < min_shared=2 → no edge
    G = build_bibcoupling_network(simple_df, min_shared=2)
    assert not G.has_edge("W2", "W3")


def test_build_bibcoupling_network_all_nodes_present(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    for wid in simple_df["id"]:
        assert wid in G.nodes()


def test_build_bibcoupling_network_empty_refs():
    df = pd.DataFrame(
        {
            "id": ["W1", "W2"],
            "domain": ["Political Science", "Economics"],
            "references": [[], []],
        }
    )
    G = build_bibcoupling_network(df)
    assert G.number_of_edges() == 0


# ── build_coauthorship_network ────────────────────────────────────────────────


def test_build_coauthorship_network_basic(simple_df):
    # A1 in W1,W2,W5; A2 in W1,W3 → both have ≥2 papers → eligible
    G = build_coauthorship_network(simple_df, min_papers=2)
    assert "A1" in G.nodes()
    assert "A2" in G.nodes()


def test_build_coauthorship_network_min_papers_threshold(simple_df):
    # A3 (1 paper) and A4 (1 paper) should be excluded
    G = build_coauthorship_network(simple_df, min_papers=2)
    assert "A3" not in G.nodes()
    assert "A4" not in G.nodes()


def test_build_coauthorship_network_edge_weight(simple_df):
    # A1 and A2 co-authored W1 only → weight=1
    G = build_coauthorship_network(simple_df, min_papers=2)
    assert G.has_edge("A1", "A2")
    assert G["A1"]["A2"]["weight"] == 1


def test_build_coauthorship_network_node_attributes(simple_df):
    G = build_coauthorship_network(simple_df, min_papers=2)
    assert G.nodes["A1"]["name"] == "Alice"
    assert G.nodes["A1"]["paper_count"] == 3


def test_build_coauthorship_network_no_eligible_authors():
    df = pd.DataFrame(
        {
            "id": ["W1"],
            "authors": [[{"id": "A1", "name": "Solo"}]],
        }
    )
    G = build_coauthorship_network(df, min_papers=2)
    assert G.number_of_nodes() == 0


# ── build_concept_cooccurrence_network ───────────────────────────────────────


def test_build_concept_cooccurrence_network_basic(simple_df):
    G = build_concept_cooccurrence_network(simple_df)
    assert "Populism" in G.nodes()
    assert "Democracy" in G.nodes()


def test_build_concept_cooccurrence_network_edge_weight(simple_df):
    G = build_concept_cooccurrence_network(simple_df)
    # Populism+Democracy co-occur in W1 and W4 → weight=2
    assert G.has_edge("Populism", "Democracy")
    assert G["Populism"]["Democracy"]["weight"] == 2


def test_build_concept_cooccurrence_network_top_n(simple_df):
    # top_n=2 → only 2 most common concepts kept
    G = build_concept_cooccurrence_network(simple_df, top_n=2)
    assert G.number_of_nodes() == 2


def test_build_concept_cooccurrence_network_no_concepts():
    df = pd.DataFrame({"id": ["W1"], "concepts": [[]]})
    G = build_concept_cooccurrence_network(df)
    assert G.number_of_nodes() == 0


# ── find_interdisciplinary_bridges ────────────────────────────────────────────


def test_find_bridges_too_few_nodes():
    G = nx.path_graph(5)
    result = find_interdisciplinary_bridges(G, {})
    assert result == []


def test_find_bridges_returns_list(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    result = find_interdisciplinary_bridges(G, domain_map, percentile=50.0)
    assert isinstance(result, list)
    for bridge in result:
        assert "work_id" in bridge
        assert "betweenness_centrality" in bridge


def test_find_bridges_sorted_by_betweenness(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    result = find_interdisciplinary_bridges(G, domain_map, percentile=0.0)
    if len(result) >= 2:
        assert result[0]["betweenness_centrality"] >= result[-1]["betweenness_centrality"]


# ── cross_domain_matrix ───────────────────────────────────────────────────────


def test_cross_domain_matrix_basic(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    matrix = cross_domain_matrix(G, domain_map)
    assert "Political Science" in matrix
    assert "Economics" in matrix


def test_cross_domain_matrix_symmetry(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    matrix = cross_domain_matrix(G, domain_map)
    ps = matrix["Political Science"]["Economics"]
    ec = matrix["Economics"]["Political Science"]
    assert ps == ec


def test_cross_domain_matrix_empty_graph():
    G = nx.Graph()
    matrix = cross_domain_matrix(G, {})
    # All counts should be zero
    for d1 in matrix:
        for d2 in matrix[d1]:
            assert matrix[d1][d2] == 0


# ── enhanced_cross_domain_analysis ────────────────────────────────────────────


def test_enhanced_cross_domain_analysis_keys(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    result = enhanced_cross_domain_analysis(G, domain_map)
    assert "raw_coupling_matrix" in result
    assert "association_strength" in result
    assert "coupling_strength_index" in result
    assert "jaccard_similarity" in result
    assert "inter_domain_ratio" in result
    assert "metadata" in result


def test_enhanced_cross_domain_analysis_idcr_range(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    result = enhanced_cross_domain_analysis(G, domain_map)
    idcr = result["inter_domain_ratio"]
    assert 0.0 <= idcr <= 1.0


def test_enhanced_cross_domain_analysis_jaccard_diagonal(simple_df):
    G = build_bibcoupling_network(simple_df, min_shared=1)
    domain_map = simple_df.set_index("id")["domain"].to_dict()
    result = enhanced_cross_domain_analysis(G, domain_map)
    jac = result["jaccard_similarity"]
    for d in jac:
        assert jac[d][d] == 1.0


def test_enhanced_cross_domain_analysis_empty_graph():
    G = nx.Graph()
    result = enhanced_cross_domain_analysis(G, {})
    assert result["inter_domain_ratio"] == 0.0


# ── save_network ──────────────────────────────────────────────────────────────


def test_save_network_creates_graphml(tmp_path, triangle_graph):
    path = str(tmp_path / "test.graphml")
    save_network(triangle_graph, path)
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_save_network_list_attributes_serialized(tmp_path):
    G = nx.Graph()
    G.add_node("A", tags=["x", "y"])
    G.add_node("B")
    G.add_edge("A", "B", weight=1)
    path = str(tmp_path / "list_attr.graphml")
    save_network(G, path)
    content = Path(path).read_text()
    assert "__list__x|y" in content


def test_save_network_roundtrip(tmp_path, triangle_graph):
    path = str(tmp_path / "roundtrip.graphml")
    save_network(triangle_graph, path)
    G2 = nx.read_graphml(path)
    assert G2.number_of_nodes() == triangle_graph.number_of_nodes()
    assert G2.number_of_edges() == triangle_graph.number_of_edges()


# ── association_strength_normalization ────────────────────────────────────────


def test_assoc_strength_zero_weight():
    G = nx.Graph()
    G.add_edge("A", "B", weight=0)
    G_norm = association_strength_normalization(G)
    # Zero total weight → returned unchanged
    assert G_norm.has_edge("A", "B")


def test_assoc_strength_updates_weights(triangle_graph):
    G_norm = association_strength_normalization(triangle_graph)
    for u, v, data in G_norm.edges(data=True):
        assert "original_weight" in data
        assert data["weight"] > 0


def test_assoc_strength_preserves_nodes(triangle_graph):
    G_norm = association_strength_normalization(triangle_graph)
    assert set(G_norm.nodes()) == set(triangle_graph.nodes())


# ── apply_vos_thresholding ────────────────────────────────────────────────────


def test_vos_thresholding_removes_weak_edges(triangle_graph):
    # Edge A-C has weight=1; threshold=1.5 → removed
    G_f = apply_vos_thresholding(triangle_graph, min_assoc_strength=1.5)
    assert not G_f.has_edge("A", "C")


def test_vos_thresholding_keeps_strong_edges(triangle_graph):
    # Edge A-B has weight=3 → kept with threshold=2
    G_f = apply_vos_thresholding(triangle_graph, min_assoc_strength=2.0)
    assert G_f.has_edge("A", "B")


def test_vos_thresholding_removes_isolated_nodes():
    G = nx.Graph()
    G.add_edge("A", "B", weight=0.5)
    G.add_edge("C", "D", weight=5.0)
    G_f = apply_vos_thresholding(G, min_assoc_strength=1.0)
    # A and B lose their only edge → isolated → removed
    assert "A" not in G_f.nodes()
    assert "B" not in G_f.nodes()
    assert G_f.has_edge("C", "D")


def test_vos_thresholding_zero_threshold(triangle_graph):
    G_f = apply_vos_thresholding(triangle_graph, min_assoc_strength=0.0)
    assert G_f.number_of_edges() == triangle_graph.number_of_edges()


# ── build_subfield networks ───────────────────────────────────────────────────


def test_subfield_cocitation_too_few_works(simple_df):
    # Only 1 paper has subcategory "social_movements" → < 5 → empty graph
    G = build_subfield_cocitation_network(simple_df, "social_movements")
    assert G.number_of_nodes() == 0


def test_subfield_cocitation_sufficient_works():
    rows = []
    for i in range(6):
        rows.append(
            {
                "id": f"W{i}",
                "subcategory": "radical_right",
                "domain": "Political Science",
                "references": [f"R{j}" for j in range(i, i + 3)],
            }
        )
    df = pd.DataFrame(rows)
    G = build_subfield_cocitation_network(df, "radical_right")
    assert isinstance(G, nx.Graph)


def test_subfield_bibcoupling_too_few_works(simple_df):
    G = build_subfield_bibcoupling_network(simple_df, "social_movements")
    assert G.number_of_nodes() == 0


def test_subfield_bibcoupling_sufficient_works():
    rows = []
    for i in range(6):
        rows.append(
            {
                "id": f"W{i}",
                "subcategory": "political_economy",
                "domain": "Economics",
                "references": ["R1", "R2", f"R{i + 10}"],
            }
        )
    df = pd.DataFrame(rows)
    G = build_subfield_bibcoupling_network(df, "political_economy")
    assert isinstance(G, nx.Graph)


# ── spectral_clustering ───────────────────────────────────────────────────────


def test_spectral_clustering_too_few_nodes(triangle_graph):
    # <10 nodes → falls back to detect_communities
    partition = spectral_clustering(triangle_graph)
    assert set(partition.keys()) == set(triangle_graph.nodes())


def test_spectral_clustering_returns_all_nodes(star_graph):
    # star_graph has 5 nodes → also <10 → fallback
    partition = spectral_clustering(star_graph)
    assert set(partition.keys()) == set(star_graph.nodes())


def test_spectral_clustering_large_connected():
    # 20-node ring → ≥10 nodes, sklearn available → runs spectral or fallback
    G = nx.cycle_graph(20)
    for u, v in G.edges():
        G[u][v]["weight"] = 1
    partition = spectral_clustering(G)
    assert len(partition) == 20


def test_spectral_clustering_disconnected_below_threshold():
    # Two equal 10-node cliques → LCC = 50% < default 95% → louvain fallback
    G = nx.Graph()
    for i in range(10):
        for j in range(i + 1, 10):
            G.add_edge(f"A{i}", f"A{j}", weight=1)
    for i in range(10):
        for j in range(i + 1, 10):
            G.add_edge(f"B{i}", f"B{j}", weight=1)
    partition = spectral_clustering(G, lcc_threshold=0.95)
    assert len(partition) == 20


# ── vos_layout ────────────────────────────────────────────────────────────────


def test_vos_layout_two_nodes():
    G = nx.Graph()
    G.add_edge("A", "B", weight=1)
    pos = vos_layout(G)
    assert "A" in pos and "B" in pos


def test_vos_layout_triangle(triangle_graph):
    pos = vos_layout(triangle_graph)
    assert set(pos.keys()) == set(triangle_graph.nodes())
    for node, coords in pos.items():
        assert len(coords) == 2


def test_vos_layout_empty():
    G = nx.Graph()
    pos = vos_layout(G)
    assert pos == {}


# ── enhanced_graph_metrics ────────────────────────────────────────────────────


def test_enhanced_graph_metrics_small_graph():
    G = nx.Graph()
    G.add_edge("A", "B", weight=1)
    result = enhanced_graph_metrics(G, "small")
    # <3 nodes → base metrics only
    assert result["n_nodes"] == 2
    assert "avg_degree" not in result


def test_enhanced_graph_metrics_triangle(triangle_graph):
    result = enhanced_graph_metrics(triangle_graph, "triangle")
    assert "avg_degree" in result
    assert "avg_edge_weight" in result
    assert result["avg_degree"] > 0


def test_enhanced_graph_metrics_empty():
    result = enhanced_graph_metrics(nx.Graph(), "empty")
    assert result["n_nodes"] == 0


def test_enhanced_graph_metrics_star(star_graph):
    result = enhanced_graph_metrics(star_graph, "star")
    assert "clustering_std" in result
    assert result["avg_degree"] > 0


# ── find_interdisciplinary_bridges ────────────────────────────────────────────


def test_find_bridges_too_small_returns_empty():
    G = nx.Graph()
    for i in range(5):
        G.add_node(f"N{i}")
    G.add_edge("N0", "N1", weight=1)
    domain_map = {f"N{i}": "Political Science" for i in range(5)}
    result = find_interdisciplinary_bridges(G, domain_map)
    assert result == []


def test_find_bridges_returns_list():
    G = nx.Graph()
    nodes = [f"N{i}" for i in range(15)]
    for n in nodes:
        G.add_node(n)
    for i in range(14):
        G.add_edge(nodes[i], nodes[i + 1], weight=1)
    domain_map = {f"N{i}": ("Political Science" if i < 8 else "Economics") for i in range(15)}
    result = find_interdisciplinary_bridges(G, domain_map)
    assert isinstance(result, list)


def test_find_bridges_cross_domain_nodes_detected():
    G = nx.Graph()
    nodes = [f"N{i}" for i in range(12)]
    for n in nodes:
        G.add_node(n)
    # Bridge: N5 connects political science cluster to economics cluster
    for i in range(5):
        G.add_edge(nodes[i], nodes[i + 1], weight=2)
    for i in range(6, 11):
        G.add_edge(nodes[i], nodes[i + 1], weight=2)
    G.add_edge("N5", "N6", weight=3)

    domain_map = {f"N{i}": ("Political Science" if i <= 5 else "Economics") for i in range(12)}
    result = find_interdisciplinary_bridges(G, domain_map)
    assert isinstance(result, list)
    if result:
        for bridge in result:
            assert "work_id" in bridge
            assert "betweenness_centrality" in bridge
            assert "bridge_domains" in bridge


def test_find_bridges_capped_at_50():
    """Result list never exceeds 50 entries."""
    G = nx.complete_graph(60)
    G = nx.relabel_nodes(G, {i: f"N{i}" for i in range(60)})
    for u, v in G.edges():
        G[u][v]["weight"] = 1
    domain_map = {f"N{i}": ("Political Science" if i < 30 else "Economics") for i in range(60)}
    result = find_interdisciplinary_bridges(G, domain_map, percentile=50.0)
    assert len(result) <= 50


# ── save_network (non-primitive attributes) ───────────────────────────────────


def test_save_network_with_list_attributes(tmp_path):
    """save_network must serialize list node/edge attrs to GraphML-safe strings."""
    G = nx.Graph()
    G.add_node("A", tags=["populism", "democracy"], score=0.9)
    G.add_node("B", tags=["economics"], score=0.7)
    G.add_edge("A", "B", weight=1, refs=["R1", "R2"])

    out = str(tmp_path / "test.graphml")
    save_network(G, out)

    import os

    assert os.path.exists(out)
    content = open(out).read()
    assert "__list__" in content


def test_save_network_with_non_primitive_attributes(tmp_path):
    """Non-list, non-primitive attrs (e.g. dicts) are repr()-ed safely."""
    G = nx.Graph()
    G.add_node("A", metadata={"key": "val"})
    G.add_edge("A", "B", weight=1, extra={"x": 1})

    out = str(tmp_path / "test2.graphml")
    save_network(G, out)

    import os

    assert os.path.exists(out)


def test_save_network_with_primitive_attributes(tmp_path):
    """Standard primitive attrs pass through without modification."""
    G = nx.Graph()
    G.add_node("A", domain="Political Science", count=5, weight=1.2, active=True)
    G.add_edge("A", "B", weight=2.5)

    out = str(tmp_path / "test3.graphml")
    save_network(G, out)

    import os

    assert os.path.exists(out)


# ── build_bibcoupling_network (no domain column) ──────────────────────────────


def test_build_bibcoupling_no_domain_column():
    """When df has no 'domain' column, all nodes default to 'Other'."""
    df = pd.DataFrame(
        {
            "id": ["W1", "W2", "W3"],
            "references": [["R1", "R2"], ["R1", "R2"], ["R3"]],
        }
    )
    G = build_bibcoupling_network(df, min_shared=2)
    assert G.has_node("W1")
    # W1 and W2 share 2 references → edge exists
    assert G.has_edge("W1", "W2")
    # Check that node domain defaults to 'Other'
    for node, data in G.nodes(data=True):
        assert data.get("domain") == "Other"


# ── build_coauthorship_network (edge already exists path) ─────────────────────


def test_build_coauthorship_edge_weight_increments():
    """When two papers share the same author pair, edge weight is accumulated."""
    df = pd.DataFrame(
        {
            "id": ["W1", "W2", "W3"],
            "authors": [
                [{"id": "A1", "name": "Alice"}, {"id": "A2", "name": "Bob"}],
                [{"id": "A1", "name": "Alice"}, {"id": "A2", "name": "Bob"}],
                [{"id": "A1", "name": "Alice"}, {"id": "A2", "name": "Bob"}],
            ],
        }
    )
    G = build_coauthorship_network(df, min_papers=1)
    assert G.has_edge("A1", "A2")
    assert G["A1"]["A2"]["weight"] == 3


def test_build_coauthorship_non_dict_author_skipped():
    """Non-dict entries in the authors list are silently skipped."""
    df = pd.DataFrame(
        {
            "id": ["W1"],
            "authors": [["not_a_dict", {"id": "A1", "name": "Alice"}]],
        }
    )
    G = build_coauthorship_network(df, min_papers=1)
    assert G.has_node("A1")
    assert "not_a_dict" not in G.nodes


# ── detect_communities (exception path) ──────────────────────────────────────


def test_detect_communities_exception_fallback(monkeypatch):
    """If greedy_modularity_communities raises, returns trivial partition."""
    import src.agents.network_analysis as na

    monkeypatch.setattr(na, "LOUVAIN_AVAILABLE", False)
    monkeypatch.setattr(nx.community, "greedy_modularity_communities", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail")))

    G = nx.Graph()
    G.add_nodes_from(["A", "B", "C"])
    G.add_edges_from([("A", "B"), ("B", "C")], weight=1)

    partition, modularity = na.detect_communities(G)
    assert isinstance(partition, dict)
    assert modularity == 0.0
