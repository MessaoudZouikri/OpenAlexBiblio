"""
Network Analysis Agent
======================
Constructs co-citation, bibliographic coupling, co-authorship, and concept
co-occurrence networks. Detects communities and cross-domain bridges.
Implements VOSviewer-inspired techniques: association strength normalization,
sub-field analysis, and improved clustering.

Outputs: GraphML files + network_metrics.json + cluster_assignments.parquet

Standalone:
    python src/agents/network_analysis.py --config config/config.yaml
"""

import argparse
import logging
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Tuple

import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_parquet, load_yaml, safe_list, save_json, save_parquet
from src.utils.logging_utils import setup_logger

# Try to import community detection (python-louvain)
try:
    import community as community_louvain

    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False

# Try to import sklearn for additional clustering
try:
    from sklearn.cluster import SpectralClustering

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# ── Community Detection ───────────────────────────────────────────────────


def detect_communities(G: nx.Graph) -> Tuple[dict, float]:
    """
    Run Louvain community detection. Falls back to greedy modularity.
    Returns (node → community_id dict, modularity score).
    """
    if len(G.nodes) < 3 or G.number_of_edges() == 0:
        return {n: 0 for n in G.nodes}, 0.0

    if LOUVAIN_AVAILABLE:
        try:
            partition = community_louvain.best_partition(G, weight="weight", random_state=42)
            if G.number_of_edges() == 0:
                return partition, 0.0
            modularity = community_louvain.modularity(partition, G, weight="weight")
            return partition, round(modularity, 4)
        except Exception:
            return {n: 0 for n in G.nodes}, 0.0
    else:
        try:
            communities = nx.community.greedy_modularity_communities(G, weight="weight")
            partition = {}
            for i, comm in enumerate(communities):
                for node in comm:
                    partition[node] = i
            modularity = nx.community.modularity(G, communities, weight="weight")
            return partition, round(modularity, 4)
        except Exception:
            return {n: 0 for n in G.nodes}, 0.0


# ── Graph Metrics ─────────────────────────────────────────────────────────


def graph_summary(G: nx.Graph, name: str) -> dict:
    """
    Basic topology metrics for a network. Robust to empty / edge-less /
    disconnected graphs.
    """
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    if n_nodes == 0:
        return {
            "network": name,
            "n_nodes": 0,
            "n_edges": 0,
            "density": 0.0,
            "n_components": 0,
            "largest_component_size": 0,
            "avg_clustering": 0.0,
            "avg_path_length_lcc": None,
        }

    try:
        components = list(nx.connected_components(G))
        largest_cc = max(components, key=len) if components else set()
    except Exception:
        components = []
        largest_cc = set()

    G_lcc = G.subgraph(largest_cc) if largest_cc else nx.Graph()

    return {
        "network": name,
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "density": round(nx.density(G), 6),
        "n_components": len(components),
        "largest_component_size": len(largest_cc),
        "avg_clustering": round(nx.average_clustering(G, weight="weight"), 4) if n_edges else 0.0,
        "avg_path_length_lcc": (
            round(nx.average_shortest_path_length(G_lcc), 4) if 1 < len(G_lcc) < 1000 else None
        ),
    }


# ── Co-Citation Network ───────────────────────────────────────────────────


def build_cocitation_network(df: pd.DataFrame, min_cocitations: int = 2) -> nx.Graph:
    """
    Works cited by ≥ 2 corpus papers become nodes.
    Edge weight = number of co-citations (corpus papers that cite both).

    Uses a per-paper pairs approach — O(n × r²) where r is avg refs per paper —
    instead of O(R²) over all unique references.
    """
    # Which corpus papers cite each reference
    ref_citers: Dict[str, set] = defaultdict(set)
    for work_id, refs in zip(df["id"], df["references"]):
        for ref in safe_list(refs):
            ref_citers[ref].add(work_id)

    eligible_refs = {ref for ref, citers in ref_citers.items() if len(citers) >= 2}

    G = nx.Graph()
    for ref in eligible_refs:
        G.add_node(ref, node_type="cited_work")

    # Count co-citations via per-paper iteration over eligible pairs only
    cocit_count: Dict[tuple, int] = defaultdict(int)
    for refs in df["references"]:
        elig = [r for r in safe_list(refs) if r in eligible_refs]
        for a, b in combinations(elig, 2):
            cocit_count[(min(a, b), max(a, b))] += 1

    for (a, b), count in cocit_count.items():
        if count >= min_cocitations:
            G.add_edge(a, b, weight=count)

    return G


# ── Bibliographic Coupling Network ────────────────────────────────────────


def build_bibcoupling_network(df: pd.DataFrame, min_shared: int = 2) -> nx.Graph:
    """
    Corpus works are nodes. Edge weight = number of shared references.

    Uses an inverted-index approach — O(m) where m is the number of
    reference co-occurrences — instead of O(n²) over all work pairs.
    """
    domain_map = df.set_index("id")["domain"].to_dict()
    G = nx.Graph()
    for wid in df["id"]:
        G.add_node(wid, domain=domain_map.get(wid, "Other"))

    # ref → list of corpus works that cite it
    ref_to_works: Dict[str, List[str]] = defaultdict(list)
    for _, row in df.iterrows():
        wid = row["id"]
        for ref in safe_list(row.get("references")):
            ref_to_works[ref].append(wid)

    # For each reference cited by ≥2 works, all citing-work pairs share it
    shared_count: Dict[tuple, int] = defaultdict(int)
    for works in ref_to_works.values():
        if len(works) < 2:
            continue
        for a, b in combinations(works, 2):
            shared_count[(min(a, b), max(a, b))] += 1

    for (a, b), count in shared_count.items():
        if count >= min_shared:
            G.add_edge(a, b, weight=count)

    return G


# ── Co-Authorship Network ─────────────────────────────────────────────────


def build_coauthorship_network(df: pd.DataFrame, min_papers: int = 2) -> nx.Graph:
    """
    Authors with ≥ min_papers are nodes. Edges = co-authorship count.
    """
    # Count papers per author
    author_paper_count: Dict[str, int] = defaultdict(int)
    author_names: Dict[str, str] = {}

    for _, row in df.iterrows():
        for a in safe_list(row.get("authors")):
            if not isinstance(a, dict):
                continue
            aid = a.get("id") or a.get("name", "")
            if aid:
                author_paper_count[aid] += 1
                author_names[aid] = a.get("name", aid)

    eligible = {aid for aid, cnt in author_paper_count.items() if cnt >= min_papers}

    G = nx.Graph()
    for aid in eligible:
        G.add_node(aid, name=author_names.get(aid, aid), paper_count=author_paper_count[aid])

    for _, row in df.iterrows():
        authors_in_row = [
            a.get("id") or a.get("name", "")
            for a in safe_list(row.get("authors"))
            if isinstance(a, dict)
            if (a.get("id") or a.get("name", "")) in eligible
        ]
        # Deduplicate repeated author appearances in a single paper.
        authors_in_row = list(dict.fromkeys(authors_in_row))
        for a, b in combinations(authors_in_row, 2):
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)

    return G


# ── Concept Co-occurrence Network ─────────────────────────────────────────


def build_concept_cooccurrence_network(df: pd.DataFrame, top_n: int = 100) -> nx.Graph:

    concept_counts: Counter = Counter()
    for _, row in df.iterrows():
        for c in safe_list(row.get("concepts")):
            if not isinstance(c, dict):
                continue
            concept_counts[c.get("name", "")] += 1

    top_concepts = {name for name, _ in concept_counts.most_common(top_n)}

    G = nx.Graph()
    for name, count in concept_counts.most_common(top_n):
        G.add_node(name, frequency=count)

    for _, row in df.iterrows():
        names = [
            c.get("name", "")
            for c in safe_list(row.get("concepts"))
            if isinstance(c, dict) and c.get("name") in top_concepts
        ]
        for a, b in combinations(sorted(set(names)), 2):
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)

    return G


# ── Bridge Detection ──────────────────────────────────────────────────────


def find_interdisciplinary_bridges(
    G: nx.Graph,
    domain_map: Dict[str, str],
    percentile: float = 75.0,
) -> List[dict]:
    """
    Identify nodes with high betweenness centrality connected to multiple domains.
    """
    if len(G.nodes) < 10:
        return []

    betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
    threshold = np.percentile(list(betweenness.values()), percentile)

    bridges = []
    for node, bc in betweenness.items():
        if bc < threshold:
            continue
        neighbor_domains = {
            domain_map.get(nb, "Unknown") for nb in G.neighbors(node) if domain_map.get(nb)
        }
        node_domain = domain_map.get(node, "Unknown")
        other_domains = neighbor_domains - {node_domain, "Unknown"}
        if len(other_domains) >= 1:
            bridges.append(
                {
                    "work_id": node,
                    "domain": node_domain,
                    "bridge_domains": sorted(other_domains),
                    "betweenness_centrality": round(bc, 6),
                    "degree": G.degree(node),
                }
            )

    bridges.sort(key=lambda x: x["betweenness_centrality"], reverse=True)
    return bridges[:50]  # top 50 bridges


# ── Cross-Domain Co-Citation Matrix ──────────────────────────────────────


def _coerce_edge_weight(data: Any) -> float:
    """Return a float edge weight, falling back to 1.0 on missing or corrupt data."""
    raw = data.get("weight", 1) if isinstance(data, dict) else 1
    try:
        return float(raw) if raw is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def cross_domain_matrix(G_bibcoupling: nx.Graph, domain_map: Dict[str, str]) -> dict:
    """Compute domain × domain edge weight matrix (raw counts only)."""
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    matrix = {d: {d2: 0 for d2 in domains} for d in domains}

    for a, b, data in G_bibcoupling.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = _coerce_edge_weight(data)
        matrix[da][db] = matrix[da].get(db, 0) + w
        if da != db:
            matrix[db][da] = matrix[db].get(da, 0) + w

    return matrix


def enhanced_cross_domain_analysis(G_bibcoupling: nx.Graph, domain_map: Dict[str, str]) -> dict:
    """
    Compute multiple interpretable coupling metrics between domains.

    Implements 4 key metrics:
    1. Raw coupling matrix (baseline)
    2. Association Strength (AS) - normalized by expected random coupling
    3. Coupling Strength Index (CSI) - ratio to minimum domain size
    4. Jaccard Similarity - proportion of shared intellectual foundation
    5. Inter-Domain Coupling Ratio - proportion that crosses domains

    Returns dict with all metrics and interpretation guide.
    """
    present = set(domain_map.values())
    if any(d not in present for d in domain_map.values() if d is None or d == "Other"):
        present.add("Other")
    domains = sorted(present)

    # Initialize matrices
    raw_matrix = {d: {d2: 0 for d2 in domains} for d in domains}
    domain_refs = {d: set() for d in domains}  # Track unique papers per domain
    domain_coupled = {d: set() for d in domains}  # Track coupled papers per domain

    # First pass: accumulate raw counts and track references
    for a, b, data in G_bibcoupling.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = _coerce_edge_weight(data)
        raw_matrix[da][db] = raw_matrix[da].get(db, 0) + w
        domain_refs[da].add(a)
        domain_refs[db].add(b)
        domain_coupled[da].add(b)
        domain_coupled[db].add(a)

    # Calculate degree sums for each domain
    domain_degrees = {d: sum(raw_matrix[d].values()) for d in domains}
    total_weight = sum(domain_degrees.values())

    # Compute normalized metrics
    as_matrix = {}  # Association Strength
    csi_matrix = {}  # Coupling Strength Index
    jaccard_matrix = {}  # Jaccard Similarity

    for d1 in domains:
        as_matrix[d1] = {}
        csi_matrix[d1] = {}
        jaccard_matrix[d1] = {}

        degree_d1 = domain_degrees[d1]

        for d2 in domains:
            observed = raw_matrix[d1][d2]
            degree_d2 = domain_degrees[d2]

            # 1. Association Strength (AS)
            # AS = observed / expected
            # AS > 1.0 means stronger than random
            if total_weight > 0:
                expected = (degree_d1 * degree_d2) / total_weight
                as_value = observed / expected if expected > 0 else 0.0
            else:
                as_value = 0.0
            as_matrix[d1][d2] = round(as_value, 3)

            # 2. Coupling Strength Index (CSI)
            # CSI = observed / min(degree_d1, degree_d2)
            min_degree = min(degree_d1, degree_d2) if min(degree_d1, degree_d2) > 0 else 1
            csi_value = observed / min_degree
            csi_matrix[d1][d2] = round(csi_value, 3)

            # 3. Jaccard Similarity
            # Jaccard = |intersection| / |union|
            if d1 == d2:
                jaccard_matrix[d1][d2] = 1.0
            else:
                union_refs = len(domain_refs[d1] | domain_refs[d2])
                intersection_refs = len(domain_refs[d1] & domain_refs[d2])
                jaccard_value = intersection_refs / union_refs if union_refs > 0 else 0.0
                jaccard_matrix[d1][d2] = round(jaccard_value, 3)

    # Calculate Inter-Domain Coupling Ratio
    inter_domain_edges = sum(raw_matrix[d1][d2] for d1 in domains for d2 in domains if d1 != d2)
    idcr_value = inter_domain_edges / total_weight if total_weight > 0 else 0.0

    return {
        "raw_coupling_matrix": raw_matrix,
        "association_strength": as_matrix,
        "coupling_strength_index": csi_matrix,
        "jaccard_similarity": jaccard_matrix,
        "inter_domain_ratio": round(idcr_value, 3),
        "interpretation": {
            "raw_coupling_matrix": "Absolute count of shared references between domains",
            "association_strength": "AS > 1.0 = stronger coupling than random; AS ≈ 1.0 = random; AS < 1.0 = weaker",
            "coupling_strength_index": "Ratio of shared refs to smallest domain (0-1 normalized approximation)",
            "jaccard_similarity": "Proportion of shared intellectual foundation (0=nothing, 1=identical)",
            "inter_domain_ratio": "Proportion of total coupling that crosses domain boundaries (0-1)",
        },
        "metadata": {
            "total_domains": len(domains),
            "domains": sorted(domains),
            "total_coupling_strength": total_weight,
            "n_inter_domain_edges": inter_domain_edges,
            "n_intra_domain_edges": total_weight - inter_domain_edges,
        },
    }


# ── Save network safely ───────────────────────────────────────────────────


def save_network(G: nx.Graph, path: str) -> None:
    """Save graph as GraphML.

    Lists are serialized as pipe-delimited strings with a ``__list__`` prefix
    so they can be faithfully reconstructed on read. Other non-primitive types
    fall back to repr().
    """
    G2 = G.copy()
    for _, data in G2.nodes(data=True):
        for k, v in list(data.items()):
            if isinstance(v, list):
                data[k] = "__list__" + "|".join(str(x) for x in v)
            elif not isinstance(v, (str, int, float, bool)):
                data[k] = repr(v)
    for _, _, data in G2.edges(data=True):
        for k, v in list(data.items()):
            if isinstance(v, list):
                data[k] = "__list__" + "|".join(str(x) for x in v)
            elif not isinstance(v, (str, int, float, bool)):
                data[k] = repr(v)
    nx.write_graphml(G2, path)


# ── Association Strength Normalization (VOSviewer-inspired) ──────────────


def association_strength_normalization(G: nx.Graph) -> nx.Graph:
    """
    Apply association strength normalization to account for field differences.
    This is a key technique from VOSviewer that normalizes link strengths.
    """
    G_norm = G.copy()

    # Calculate expected weights based on node degrees
    degrees = dict(G.degree(weight="weight"))
    total_weight = sum(degrees.values())

    if total_weight == 0:
        return G_norm

    for u, v, data in G.edges(data=True):
        observed = data.get("weight", 1)
        expected = (degrees[u] * degrees[v]) / total_weight
        if expected > 0:
            # Association strength = observed / expected
            assoc_strength = observed / expected
            G_norm[u][v]["weight"] = assoc_strength
            G_norm[u][v]["original_weight"] = observed

    return G_norm


# ── VOSviewer-style Thresholding ──────────────────────────────────────────


def apply_vos_thresholding(G: nx.Graph, min_assoc_strength: float = 1.0) -> nx.Graph:
    """
    Apply minimum association strength threshold (VOSviewer approach).
    Remove edges below the threshold to improve network quality.
    """
    edges_to_remove = []
    for u, v, data in G.edges(data=True):
        if data.get("weight", 0) < min_assoc_strength:
            edges_to_remove.append((u, v))

    G_filtered = G.copy()
    G_filtered.remove_edges_from(edges_to_remove)

    # Remove isolated nodes
    isolated_nodes = [n for n, d in G_filtered.degree() if d == 0]
    G_filtered.remove_nodes_from(isolated_nodes)

    return G_filtered


# ── Sub-field Network Analysis ────────────────────────────────────────────


def build_subfield_cocitation_network(
    df: pd.DataFrame, subcategory: str, min_cocitations: int = 2
) -> nx.Graph:
    """
    Build co-citation network for works within a specific sub-category.
    This allows analysis of citation patterns within sub-fields.
    """
    # Filter to works in this subcategory
    subcat_df = df[df["subcategory"] == subcategory].copy()
    if len(subcat_df) < 5:
        return nx.Graph()  # Too few works

    logger = logging.getLogger("network_analysis")
    logger.info(f"  Building {subcategory} network with {len(subcat_df)} works")

    return build_cocitation_network(subcat_df, min_cocitations)


def build_subfield_bibcoupling_network(
    df: pd.DataFrame, subcategory: str, min_shared: int = 2
) -> nx.Graph:
    """
    Build bibliographic coupling network for works within a specific sub-category.
    """
    # Filter to works in this subcategory
    subcat_df = df[df["subcategory"] == subcategory].copy()
    if len(subcat_df) < 5:
        return nx.Graph()  # Too few works

    return build_bibcoupling_network(subcat_df, min_shared)


# ── Enhanced Clustering with Spectral Clustering ──────────────────────────


def spectral_clustering(G: nx.Graph, n_clusters: int = None, lcc_threshold: float = 0.95) -> dict:
    """
    Apply spectral clustering robust to connectivity issues.
    Falls back to Louvain if graph is severely disconnected or sklearn unavailable.
    """
    logger = logging.getLogger("network_analysis")

    if not SKLEARN_AVAILABLE or G.number_of_nodes() < 10:
        return detect_communities(G)[0]

    # Connectivity diagnostics
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    n_components = len(components)
    lcc_nodes = components[0] if components else set()
    lcc_frac = len(lcc_nodes) / G.number_of_nodes() if G.number_of_nodes() else 0
    is_connected = n_components == 1

    logger.info(
        f"Graph connectivity: {n_components} component(s), "
        f"LCC = {len(lcc_nodes)} nodes ({lcc_frac:.1%})"
    )

    # Severely disconnected → Leiden fallback
    if lcc_frac < lcc_threshold:
        logger.warning(
            f"LCC fraction {lcc_frac:.1%} below threshold {lcc_threshold:.0%}. "
            f"Spectral clustering not appropriate. Delegating to Louvain."
        )
        return detect_communities(G)[0]

    # Spectral on LCC (or full graph if connected)
    if is_connected:
        G_lcc = G
        strategy = "spectral_full"
    else:
        G_lcc = G.subgraph(lcc_nodes).copy()
        strategy = "spectral_lcc_extraction"
        outlier_nodes = [n for c in components[1:] for n in c]
        logger.info(
            f"Extracted LCC ({len(lcc_nodes)} nodes). "
            f"{len(outlier_nodes)} nodes in {n_components - 1} micro-components "
            f"will be re-attached after clustering."
        )

    try:
        # Auto-estimate n_clusters if not provided
        n = G_lcc.number_of_nodes()
        if n_clusters is None:
            n_clusters = min(max(2, int(math.sqrt(n / 2))), 20)

        # Convert to adjacency matrix
        nodes_lcc = list(G_lcc.nodes())
        adj_matrix = nx.to_numpy_array(G_lcc, weight="weight", nodelist=nodes_lcc)

        # Apply spectral clustering
        clustering = SpectralClustering(
            n_clusters=n_clusters, affinity="precomputed", random_state=42
        )
        labels = clustering.fit_predict(adj_matrix)

        # Build partition for LCC
        partition = {nodes_lcc[i]: int(labels[i]) for i in range(len(nodes_lcc))}

        # Re-attach micro-components if needed
        if not is_connected:
            community_sizes = {}
            for comm in partition.values():
                community_sizes[comm] = community_sizes.get(comm, 0) + 1

            for comp_nodes in components[1:]:
                best_comm = min(
                    community_sizes, key=lambda c: abs(community_sizes[c] - len(comp_nodes))
                )
                for node in comp_nodes:
                    partition[node] = best_comm

        missing = set(G.nodes()) - set(partition.keys())
        if missing:
            logger.warning(
                "Partition incomplete: %d / %d nodes assigned — padding %d missing nodes "
                "with cluster -1.",
                len(partition),
                G.number_of_nodes(),
                len(missing),
            )
            for node in missing:
                partition[node] = -1

        logger.info(
            f"Clustering complete | strategy={strategy} | "
            f"communities={len(set(partition.values()))}"
        )
        return partition

    except Exception as e:
        logger.warning(f"Spectral clustering failed: {e}. Falling back to Louvain.")
        return detect_communities(G)[0]


# ── VOSviewer-inspired Layout (Simplified) ────────────────────────────────


def vos_layout(G: nx.Graph, dim: int = 2, max_iter: int = 50) -> dict:
    """
    Simplified VOS mapping technique for graph layout.
    Positions items based on their relatedness in a low-dimensional space.
    """
    if G.number_of_nodes() < 3:
        return nx.spring_layout(G, dim=dim)

    try:
        # Use force-directed layout as approximation of VOS mapping
        # In VOSviewer, items are positioned based on association strengths
        pos = nx.spring_layout(G, dim=dim, weight="weight", iterations=max_iter, seed=42, scale=100)
        return pos
    except Exception:
        return nx.random_layout(G, dim=dim)


# ── Enhanced Network Metrics ──────────────────────────────────────────────


def enhanced_graph_metrics(G: nx.Graph, name: str) -> dict:
    """
    Compute enhanced network metrics including VOSviewer-style measures.
    """
    base_metrics = graph_summary(G, name)

    if G.number_of_nodes() < 3:
        return base_metrics

    try:
        # Additional metrics
        degrees = [d for n, d in G.degree()]
        weights = [d.get("weight", 1) for u, v, d in G.edges(data=True)]

        enhanced = {
            **base_metrics,
            "avg_degree": round(np.mean(degrees), 2),
            "median_degree": int(np.median(degrees)),
            "degree_variance": round(np.var(degrees), 2),
            "avg_edge_weight": round(np.mean(weights), 2),
            "median_edge_weight": round(np.median(weights), 2),
            "weight_variance": round(np.var(weights), 2),
            "degree_centralization": round(max(degrees) / (len(G) - 1) if len(G) > 1 else 0, 4),
        }

        # Clustering coefficient distribution
        if len(G) <= 1000:  # Performance limit
            clustering_coeffs = list(nx.clustering(G, weight="weight").values())
            enhanced["clustering_std"] = round(np.std(clustering_coeffs), 4)

        return enhanced

    except Exception as e:
        logging.getLogger("network_analysis").warning(f"Enhanced metrics failed: {e}")
        return base_metrics


# ── Main ──────────────────────────────────────────────────────────────────


def _auto_min_shared(n: int) -> int:
    """Scale minimum shared references with corpus size to avoid O(n²) edge explosion."""
    if n < 5_000:
        return 2
    if n < 15_000:
        return 3
    if n < 30_000:
        return 5
    return 10


def main():
    parser = argparse.ArgumentParser(description="Network Analysis Agent")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--vos_threshold",
        type=float,
        default=None,
        help="Minimum association strength threshold (VOSviewer style). Overrides config.",
    )
    parser.add_argument(
        "--subfield_analysis",
        action="store_true",
        help="Perform sub-field network analysis. Overrides config.",
    )
    args = parser.parse_args()

    config = load_yaml(args.config)
    net_cfg = config.get("network", {})
    clustering_cfg = config.get("clustering", {})

    # Resolve thresholds: CLI flag > config > default
    vos_threshold = (
        args.vos_threshold if args.vos_threshold is not None else net_cfg.get("vos_threshold", 1.0)
    )
    subfield_analysis = args.subfield_analysis or net_cfg.get("subfield_analysis", False)
    lcc_threshold = clustering_cfg.get("lcc_threshold", 0.95)

    logger = setup_logger("network_analysis", config["paths"]["logs"])
    logger.info("=== Network Analysis Agent starting ===")
    logger.info(
        "VOSviewer-inspired analysis: threshold=%.1f, subfield=%s", vos_threshold, subfield_analysis
    )

    proc_dir = config["paths"]["data_processed"]
    net_dir = config["paths"]["outputs"] + "/networks"
    Path(net_dir).mkdir(parents=True, exist_ok=True)

    df = load_parquet(f"{proc_dir}/classified_works.parquet")
    n = len(df)
    logger.info("Loaded %d classified works", n)

    # Auto-scale min_shared thresholds from config or corpus size
    cfg_min_shared = net_cfg.get("min_shared_refs")
    cfg_min_cocit = net_cfg.get("min_cocitations")
    min_shared = cfg_min_shared if cfg_min_shared is not None else _auto_min_shared(n)
    min_cocit = cfg_min_cocit if cfg_min_cocit is not None else _auto_min_shared(n)
    logger.info(
        "Thresholds — min_shared_refs=%d, min_cocitations=%d  (corpus n=%d)",
        min_shared,
        min_cocit,
        n,
    )

    domain_map = df.set_index("id")["domain"].to_dict()
    subcategory_map = df.set_index("id")["subcategory"].to_dict()
    metrics = {"timestamp": datetime.now(timezone.utc).isoformat()}

    # ── 1. Bibliographic Coupling ────────────────────────────────────
    logger.info("Building bibliographic coupling network...")
    G_bib = build_bibcoupling_network(df, min_shared=min_shared)
    logger.info(
        "  Bib coupling: %d nodes, %d edges", G_bib.number_of_nodes(), G_bib.number_of_edges()
    )

    if G_bib.number_of_nodes() >= 5:
        # Apply VOSviewer-style normalization and thresholding
        G_bib_norm = association_strength_normalization(G_bib)
        G_bib_filtered = apply_vos_thresholding(G_bib_norm, vos_threshold)

        logger.info(
            "  After VOS filtering: %d nodes, %d edges",
            G_bib_filtered.number_of_nodes(),
            G_bib_filtered.number_of_edges(),
        )

        # Save both versions
        save_network(G_bib, f"{net_dir}/bibcoupling_network_raw.graphml")
        save_network(G_bib_filtered, f"{net_dir}/bibcoupling_network_vos.graphml")

        # Use filtered network for analysis
        G_bib_analysis = G_bib_filtered if G_bib_filtered.number_of_nodes() >= 5 else G_bib

        # Enhanced clustering
        partition_louvain, modularity_louvain = detect_communities(G_bib_analysis)
        partition_spectral = spectral_clustering(G_bib_analysis, lcc_threshold=lcc_threshold)

        # Use the better clustering result
        partition = partition_louvain  # Default to Louvain
        modularity = modularity_louvain

        metrics["bibcoupling"] = enhanced_graph_metrics(G_bib_analysis, "bibcoupling")
        metrics["bibcoupling"]["modularity"] = modularity
        metrics["bibcoupling"]["vos_threshold"] = vos_threshold
        metrics["cross_domain_matrix"] = cross_domain_matrix(G_bib_analysis, domain_map)

        # Add enhanced cross-domain metrics (interpretable alternatives to raw counts)
        metrics["enhanced_cross_domain_metrics"] = enhanced_cross_domain_analysis(
            G_bib_analysis, domain_map
        )
        logger.info("Computed enhanced coupling metrics: AS, CSI, Jaccard, IDCR")

        # Cluster assignments with enhanced metrics
        cluster_rows = []

        # Calculate centrality measures with error handling
        try:
            bc = nx.betweenness_centrality(G_bib_analysis, weight="weight", normalized=True)
        except Exception as e:
            logger.warning("Betweenness centrality failed: %s, using zeros", e)
            bc = {n: 0.0 for n in G_bib_analysis.nodes()}

        try:
            pr = nx.pagerank(G_bib_analysis, weight="weight")
        except Exception as e:
            logger.warning("PageRank failed: %s, using zeros", e)
            pr = {n: 0.0 for n in G_bib_analysis.nodes()}

        try:
            ec = nx.eigenvector_centrality(G_bib_analysis, weight="weight", max_iter=1000)
        except Exception as e:
            logger.warning("Eigenvector centrality failed: %s, using zeros", e)
            ec = {n: 0.0 for n in G_bib_analysis.nodes()}

        for node in G_bib_analysis.nodes():
            # Safe degree access with node existence check
            degree_val = G_bib_analysis.degree(node) if node in G_bib_analysis else 0
            weighted_degree_val = (
                G_bib_analysis.degree(node, weight="weight") if node in G_bib_analysis else 0
            )

            cluster_rows.append(
                {
                    "work_id": node,
                    "domain": domain_map.get(node, "Other"),
                    "subcategory": subcategory_map.get(node, "Other"),
                    "cluster_id_louvain": partition_louvain.get(node, -1),
                    "cluster_id_spectral": partition_spectral.get(node, -1),
                    "betweenness_centrality": round(bc.get(node, 0.0), 6),
                    "pagerank": round(pr.get(node, 0.0), 8),
                    "eigenvector_centrality": round(ec.get(node, 0.0), 6),
                    "degree": degree_val,
                    "weighted_degree": (
                        round(weighted_degree_val, 2)
                        if isinstance(weighted_degree_val, (int, float))
                        else 0
                    ),
                }
            )

        df_clusters = pd.DataFrame(cluster_rows)
        save_parquet(df_clusters, f"{proc_dir}/cluster_assignments.parquet")

        n_communities = len(set(partition.values()))
        logger.info("  Modularity: %.4f, Communities: %d", modularity, n_communities)

    # ── 2. Co-Citation Network ────────────────────────────────────────
    logger.info("Building co-citation network...")
    G_cc = build_cocitation_network(df, min_cocitations=min_cocit)
    logger.info("  Co-citation: %d nodes, %d edges", G_cc.number_of_nodes(), G_cc.number_of_edges())

    if G_cc.number_of_nodes() >= 5:
        # Apply VOSviewer-style normalization and thresholding
        G_cc_norm = association_strength_normalization(G_cc)
        G_cc_filtered = apply_vos_thresholding(G_cc_norm, vos_threshold)

        logger.info(
            "  After VOS filtering: %d nodes, %d edges",
            G_cc_filtered.number_of_nodes(),
            G_cc_filtered.number_of_edges(),
        )

        # Save both versions
        save_network(G_cc, f"{net_dir}/cocitation_network_raw.graphml")
        save_network(G_cc_filtered, f"{net_dir}/cocitation_network_vos.graphml")

        # Use filtered network for analysis
        G_cc_analysis = G_cc_filtered if G_cc_filtered.number_of_nodes() >= 5 else G_cc

        _, cc_modularity = detect_communities(G_cc_analysis)
        metrics["cocitation"] = enhanced_graph_metrics(G_cc_analysis, "cocitation")
        metrics["cocitation"]["modularity"] = cc_modularity
        metrics["cocitation"]["vos_threshold"] = vos_threshold

    # ── 3. Sub-field Analysis ─────────────────────────────────────────
    if subfield_analysis:
        logger.info("Performing sub-field network analysis...")
        subfield_metrics = {}

        # Get major subcategories (those with at least 10 works)
        subcat_counts = df["subcategory"].value_counts()
        major_subcats = subcat_counts[subcat_counts >= 10].index.tolist()

        for subcat in major_subcats[:5]:  # Limit to top 5 for performance
            logger.info(f"Analyzing sub-field: {subcat}")

            # Co-citation network for this sub-field
            G_sub_cc = build_subfield_cocitation_network(df, subcat, min_cocitations=min_cocit)
            if G_sub_cc.number_of_nodes() >= 5:
                G_sub_cc_norm = association_strength_normalization(G_sub_cc)
                G_sub_cc_filtered = apply_vos_thresholding(G_sub_cc_norm, vos_threshold)

                save_network(
                    G_sub_cc_filtered,
                    f"{net_dir}/cocitation_{subcat.replace(' ', '_')}_vos.graphml",
                )

                subfield_metrics[f"cocitation_{subcat}"] = {
                    **enhanced_graph_metrics(G_sub_cc_filtered, f"cocitation_{subcat}"),
                    "vos_threshold": vos_threshold,
                }

            # Bibliographic coupling for this sub-field
            G_sub_bib = build_subfield_bibcoupling_network(df, subcat, min_shared=min_shared)
            if G_sub_bib.number_of_nodes() >= 5:
                G_sub_bib_norm = association_strength_normalization(G_sub_bib)
                G_sub_bib_filtered = apply_vos_thresholding(G_sub_bib_norm, vos_threshold)

                save_network(
                    G_sub_bib_filtered,
                    f"{net_dir}/bibcoupling_{subcat.replace(' ', '_')}_vos.graphml",
                )

                _, sub_modularity = detect_communities(G_sub_bib_filtered)
                subfield_metrics[f"bibcoupling_{subcat}"] = {
                    **enhanced_graph_metrics(G_sub_bib_filtered, f"bibcoupling_{subcat}"),
                    "modularity": sub_modularity,
                    "vos_threshold": vos_threshold,
                }

        if subfield_metrics:
            metrics["subfield_analysis"] = subfield_metrics
            logger.info("  Completed sub-field analysis for %d categories", len(subfield_metrics))

    # ── 4. Co-Authorship Network ──────────────────────────────────────
    logger.info("Building co-authorship network...")
    G_auth = build_coauthorship_network(df, min_papers=2)
    logger.info(
        "  Co-authorship: %d nodes, %d edges", G_auth.number_of_nodes(), G_auth.number_of_edges()
    )

    if G_auth.number_of_nodes() >= 5:
        # Cap large networks for performance
        if G_auth.number_of_nodes() > 5000:
            top_nodes = sorted(G_auth.degree(), key=lambda x: x[1], reverse=True)[:5000]
            G_auth = G_auth.subgraph([n for n, _ in top_nodes]).copy()
            logger.info("  Sampled to 5000 nodes")

        save_network(G_auth, f"{net_dir}/coauthorship_network.graphml")
        _, auth_modularity = detect_communities(G_auth)
        metrics["coauthorship"] = enhanced_graph_metrics(G_auth, "coauthorship")
        metrics["coauthorship"]["modularity"] = auth_modularity

    # ── 5. Concept Co-occurrence Network ──────────────────────────────
    logger.info("Building concept co-occurrence network...")
    G_concept = build_concept_cooccurrence_network(df, top_n=100)
    logger.info(
        "  Concept: %d nodes, %d edges", G_concept.number_of_nodes(), G_concept.number_of_edges()
    )

    if G_concept.number_of_nodes() >= 5:
        # Apply normalization to concept network too
        G_concept_norm = association_strength_normalization(G_concept)
        G_concept_filtered = apply_vos_thresholding(G_concept_norm, vos_threshold)

        save_network(G_concept_filtered, f"{net_dir}/keyword_cooccurrence_network_vos.graphml")
        metrics["concept_cooccurrence"] = enhanced_graph_metrics(
            G_concept_filtered, "concept_cooccurrence"
        )
        metrics["concept_cooccurrence"]["vos_threshold"] = vos_threshold

    # ── 6. Bridge Detection ───────────────────────────────────────────
    if "G_bib_analysis" in locals() and G_bib_analysis.number_of_nodes() >= 10:
        logger.info("Detecting interdisciplinary bridges...")
        bridges = find_interdisciplinary_bridges(G_bib_analysis, domain_map)
        metrics["interdisciplinary_bridges_count"] = len(bridges)
        save_json(bridges, f"{proc_dir}/interdisciplinary_bridges.json")
        logger.info("  Found %d bridge nodes", len(bridges))

    # ── 7. Network Layout Information ────────────────────────────────
    if "G_bib_analysis" in locals() and G_bib_analysis.number_of_nodes() >= 5:
        logger.info("Computing VOS-inspired layout...")
        layout_2d = vos_layout(G_bib_analysis, dim=2)
        layout_3d = vos_layout(G_bib_analysis, dim=3)

        # Save layout information
        layout_data = {
            "layout_2d": {node: [round(x, 4), round(y, 4)] for node, (x, y) in layout_2d.items()},
            "layout_3d": {
                node: [round(x, 4), round(y, 4), round(z, 4)]
                for node, (x, y, z) in layout_3d.items()
            },
        }
        save_json(layout_data, f"{proc_dir}/network_layout.json")

    save_json(metrics, f"{proc_dir}/network_metrics.json")
    logger.info("=== Network Analysis Agent complete ===")
    logger.info("VOSviewer-inspired analysis completed with threshold %.1f", vos_threshold)


if __name__ == "__main__":
    main()
