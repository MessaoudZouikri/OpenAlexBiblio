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
import sys
from collections import defaultdict, Counter
from datetime import datetime, UTC
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple
import math

import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_parquet, save_parquet, save_json, load_yaml, safe_list
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
    from sklearn.metrics import silhouette_score
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
    largest_cc = max(nx.connected_components(G), key=len) if G.nodes else set()
    G_lcc = G.subgraph(largest_cc)
    return {
        "network": name,
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "density": round(nx.density(G), 6),
        "n_components": nx.number_connected_components(G),
        "largest_component_size": len(largest_cc),
        "avg_clustering": round(nx.average_clustering(G, weight="weight"), 4),
        "avg_path_length_lcc": (
            round(nx.average_shortest_path_length(G_lcc), 4)
            if len(G_lcc) > 1 and len(G_lcc) < 1000
            else None
        ),
    }


# ── Co-Citation Network ───────────────────────────────────────────────────

def build_cocitation_network(df: pd.DataFrame, min_cocitations: int = 2) -> nx.Graph:
    """
    Works cited by ≥ 2 corpus papers become nodes.
    Edge weight = number of co-citations.
    """
    # Build inverted index: ref → set of corpus papers that cite it
    ref_citers: Dict[str, set] = defaultdict(set)
    for work_id, refs in zip(df["id"], df["references"]):
        for ref in safe_list(refs):
            ref_citers[ref].add(work_id)

    # Only keep refs cited by ≥ 2 papers
    shared_refs = {ref: citers for ref, citers in ref_citers.items() if len(citers) >= 2}

    G = nx.Graph()
    for ref, citers in shared_refs.items():
        G.add_node(ref, node_type="cited_work")

    for ref_a, ref_b in combinations(shared_refs.keys(), 2):
        shared = shared_refs[ref_a] & shared_refs[ref_b]
        if len(shared) >= min_cocitations:
            G.add_edge(ref_a, ref_b, weight=len(shared))

    return G


# ── Bibliographic Coupling Network ────────────────────────────────────────

def build_bibcoupling_network(df: pd.DataFrame, min_shared: int = 2) -> nx.Graph:
    """
    Corpus works are nodes. Edge weight = number of shared references.
    """
    G = nx.Graph()
    work_ids = df["id"].tolist()
    ref_sets = {row["id"]: set(safe_list(row.get("references"))) for _, row in df.iterrows()}
    domain_map = df.set_index("id")["domain"].to_dict()

    for wid in work_ids:
        G.add_node(wid, domain=domain_map.get(wid, "Other"))

    for a, b in combinations(work_ids, 2):
        shared = ref_sets.get(a, set()) & ref_sets.get(b, set())
        if len(shared) >= min_shared:
            G.add_edge(a, b, weight=len(shared))

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
            if not isinstance(a, dict): continue
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
        for a, b in combinations(authors_in_row, 2):
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)

    return G


# ── Concept Co-occurrence Network ─────────────────────────────────────────

def build_concept_cooccurrence_network(df: pd.DataFrame, top_n: int = 100) -> nx.Graph:
    from collections import Counter
    concept_counts: Counter = Counter()
    for _, row in df.iterrows():
        for c in safe_list(row.get("concepts")):
            if not isinstance(c, dict): continue
            concept_counts[c.get("name", "")] += 1

    top_concepts = {name for name, _ in concept_counts.most_common(top_n)}

    G = nx.Graph()
    for name, count in concept_counts.most_common(top_n):
        G.add_node(name, frequency=count)

    for _, row in df.iterrows():
        names = [c.get("name", "") for c in safe_list(row.get("concepts")) if isinstance(c, dict) and c.get("name") in top_concepts]
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
            domain_map.get(nb, "Unknown")
            for nb in G.neighbors(node)
            if domain_map.get(nb)
        }
        node_domain = domain_map.get(node, "Unknown")
        other_domains = neighbor_domains - {node_domain, "Unknown"}
        if len(other_domains) >= 1:
            bridges.append({
                "work_id": node,
                "domain": node_domain,
                "bridge_domains": sorted(other_domains),
                "betweenness_centrality": round(bc, 6),
                "degree": G.degree(node),
            })

    bridges.sort(key=lambda x: x["betweenness_centrality"], reverse=True)
    return bridges[:50]  # top 50 bridges


# ── Cross-Domain Co-Citation Matrix ──────────────────────────────────────

def cross_domain_matrix(G_bibcoupling: nx.Graph, domain_map: Dict[str, str]) -> dict:
    """Compute domain × domain edge weight matrix."""
    domains = ["Political Science", "Economics", "Sociology", "Other"]
    matrix = {d: {d2: 0 for d2 in domains} for d in domains}

    for a, b, data in G_bibcoupling.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = data.get("weight", 1)
        matrix[da][db] = matrix[da].get(db, 0) + w
        if da != db:
            matrix[db][da] = matrix[db].get(da, 0) + w

    return matrix


# ── Save network safely ───────────────────────────────────────────────────

def save_network(G: nx.Graph, path: str) -> None:
    """Save graph as GraphML, converting non-serializable attributes."""
    G2 = G.copy()
    for n, data in G2.nodes(data=True):
        for k, v in data.items():
            if not isinstance(v, (str, int, float, bool)):
                data[k] = str(v)
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

def build_subfield_cocitation_network(df: pd.DataFrame, subcategory: str,
                                    min_cocitations: int = 2) -> nx.Graph:
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


def build_subfield_bibcoupling_network(df: pd.DataFrame, subcategory: str,
                                     min_shared: int = 2) -> nx.Graph:
    """
    Build bibliographic coupling network for works within a specific sub-category.
    """
    # Filter to works in this subcategory
    subcat_df = df[df["subcategory"] == subcategory].copy()
    if len(subcat_df) < 5:
        return nx.Graph()  # Too few works

    return build_bibcoupling_network(subcat_df, min_shared)


# ── Enhanced Clustering with Spectral Clustering ──────────────────────────

def spectral_clustering(G: nx.Graph, n_clusters: int = None) -> dict:
    """
    Apply spectral clustering for potentially better community detection.
    Falls back to Louvain if sklearn not available or fails.
    """
    if not SKLEARN_AVAILABLE or G.number_of_nodes() < 10:
        return detect_communities(G)[0]

    try:
        # Convert graph to adjacency matrix
        nodes = list(G.nodes())
        n = len(nodes)
        if n_clusters is None:
            n_clusters = min(max(2, int(math.sqrt(n / 2))), 20)

        # Create adjacency matrix
        adj_matrix = nx.to_numpy_array(G, weight="weight", nodelist=nodes)

        # Apply spectral clustering
        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            random_state=42
        )
        labels = clustering.fit_predict(adj_matrix)

        # Convert to partition dict
        partition = {nodes[i]: labels[i] for i in range(n)}
        return partition

    except Exception as e:
        logging.getLogger("network_analysis").warning(f"Spectral clustering failed: {e}")
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
        pos = nx.spring_layout(G, dim=dim, weight="weight", iterations=max_iter,
                             seed=42, scale=100)
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
    parser.add_argument("--vos_threshold", type=float, default=None,
                       help="Minimum association strength threshold (VOSviewer style). Overrides config.")
    parser.add_argument("--subfield_analysis", action="store_true",
                       help="Perform sub-field network analysis. Overrides config.")
    args = parser.parse_args()

    config = load_yaml(args.config)
    net_cfg = config.get("network", {})

    # Resolve thresholds: CLI flag > config > default
    vos_threshold     = args.vos_threshold if args.vos_threshold is not None else net_cfg.get("vos_threshold", 1.0)
    subfield_analysis = args.subfield_analysis or net_cfg.get("subfield_analysis", False)

    logger = setup_logger("network_analysis", config["paths"]["logs"])
    logger.info("=== Network Analysis Agent starting ===")
    logger.info("VOSviewer-inspired analysis: threshold=%.1f, subfield=%s",
                vos_threshold, subfield_analysis)

    proc_dir = config["paths"]["data_processed"]
    net_dir = config["paths"]["outputs"] + "/networks"
    Path(net_dir).mkdir(parents=True, exist_ok=True)

    df = load_parquet(f"{proc_dir}/classified_works.parquet")
    n = len(df)
    logger.info("Loaded %d classified works", n)

    # Auto-scale min_shared thresholds from config or corpus size
    cfg_min_shared = net_cfg.get("min_shared_refs")
    cfg_min_cocit  = net_cfg.get("min_cocitations")
    min_shared    = cfg_min_shared if cfg_min_shared is not None else _auto_min_shared(n)
    min_cocit     = cfg_min_cocit  if cfg_min_cocit  is not None else _auto_min_shared(n)
    logger.info("Thresholds — min_shared_refs=%d, min_cocitations=%d  (corpus n=%d)",
                min_shared, min_cocit, n)

    domain_map = df.set_index("id")["domain"].to_dict()
    subcategory_map = df.set_index("id")["subcategory"].to_dict()
    metrics = {"timestamp": datetime.now(UTC).isoformat()}

    # ── 1. Bibliographic Coupling ────────────────────────────────────
    logger.info("Building bibliographic coupling network...")
    G_bib = build_bibcoupling_network(df, min_shared=min_shared)
    logger.info("  Bib coupling: %d nodes, %d edges", G_bib.number_of_nodes(), G_bib.number_of_edges())

    if G_bib.number_of_nodes() >= 5:
        # Apply VOSviewer-style normalization and thresholding
        G_bib_norm = association_strength_normalization(G_bib)
        G_bib_filtered = apply_vos_thresholding(G_bib_norm, vos_threshold)

        logger.info("  After VOS filtering: %d nodes, %d edges",
                   G_bib_filtered.number_of_nodes(), G_bib_filtered.number_of_edges())

        # Save both versions
        save_network(G_bib, f"{net_dir}/bibcoupling_network_raw.graphml")
        save_network(G_bib_filtered, f"{net_dir}/bibcoupling_network_vos.graphml")

        # Use filtered network for analysis
        G_bib_analysis = G_bib_filtered if G_bib_filtered.number_of_nodes() >= 5 else G_bib

        # Enhanced clustering
        partition_louvain, modularity_louvain = detect_communities(G_bib_analysis)
        partition_spectral = spectral_clustering(G_bib_analysis)

        # Use the better clustering result
        partition = partition_louvain  # Default to Louvain
        modularity = modularity_louvain

        metrics["bibcoupling"] = enhanced_graph_metrics(G_bib_analysis, "bibcoupling")
        metrics["bibcoupling"]["modularity"] = modularity
        metrics["bibcoupling"]["vos_threshold"] = vos_threshold
        metrics["cross_domain_matrix"] = cross_domain_matrix(G_bib_analysis, domain_map)

        # Cluster assignments with enhanced metrics
        cluster_rows = []
        bc = nx.betweenness_centrality(G_bib_analysis, weight="weight", normalized=True)
        pr = nx.pagerank(G_bib_analysis, weight="weight")
        ec = nx.eigenvector_centrality(G_bib_analysis, weight="weight", max_iter=1000)

        for node in G_bib_analysis.nodes():
            cluster_rows.append({
                "work_id": node,
                "domain": domain_map.get(node, "Other"),
                "subcategory": subcategory_map.get(node, "Other"),
                "cluster_id_louvain": partition_louvain.get(node, -1),
                "cluster_id_spectral": partition_spectral.get(node, -1),
                "betweenness_centrality": round(bc.get(node, 0.0), 6),
                "pagerank": round(pr.get(node, 0.0), 8),
                "eigenvector_centrality": round(ec.get(node, 0.0), 6),
                "degree": G_bib_analysis.degree(node),
                "weighted_degree": G_bib_analysis.degree(node, weight="weight"),
            })

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

        logger.info("  After VOS filtering: %d nodes, %d edges",
                   G_cc_filtered.number_of_nodes(), G_cc_filtered.number_of_edges())

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

                save_network(G_sub_cc_filtered, f"{net_dir}/cocitation_{subcat.replace(' ', '_')}_vos.graphml")

                subfield_metrics[f"cocitation_{subcat}"] = {
                    **enhanced_graph_metrics(G_sub_cc_filtered, f"cocitation_{subcat}"),
                    "vos_threshold": vos_threshold
                }

            # Bibliographic coupling for this sub-field
            G_sub_bib = build_subfield_bibcoupling_network(df, subcat, min_shared=min_shared)
            if G_sub_bib.number_of_nodes() >= 5:
                G_sub_bib_norm = association_strength_normalization(G_sub_bib)
                G_sub_bib_filtered = apply_vos_thresholding(G_sub_bib_norm, vos_threshold)

                save_network(G_sub_bib_filtered, f"{net_dir}/bibcoupling_{subcat.replace(' ', '_')}_vos.graphml")

                _, sub_modularity = detect_communities(G_sub_bib_filtered)
                subfield_metrics[f"bibcoupling_{subcat}"] = {
                    **enhanced_graph_metrics(G_sub_bib_filtered, f"bibcoupling_{subcat}"),
                    "modularity": sub_modularity,
                    "vos_threshold": vos_threshold
                }

        if subfield_metrics:
            metrics["subfield_analysis"] = subfield_metrics
            logger.info("  Completed sub-field analysis for %d categories", len(subfield_metrics))

    # ── 4. Co-Authorship Network ──────────────────────────────────────
    logger.info("Building co-authorship network...")
    G_auth = build_coauthorship_network(df, min_papers=2)
    logger.info("  Co-authorship: %d nodes, %d edges", G_auth.number_of_nodes(), G_auth.number_of_edges())

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
    logger.info("  Concept: %d nodes, %d edges", G_concept.number_of_nodes(), G_concept.number_of_edges())

    if G_concept.number_of_nodes() >= 5:
        # Apply normalization to concept network too
        G_concept_norm = association_strength_normalization(G_concept)
        G_concept_filtered = apply_vos_thresholding(G_concept_norm, vos_threshold)

        save_network(G_concept_filtered, f"{net_dir}/keyword_cooccurrence_network_vos.graphml")
        metrics["concept_cooccurrence"] = enhanced_graph_metrics(G_concept_filtered, "concept_cooccurrence")
        metrics["concept_cooccurrence"]["vos_threshold"] = vos_threshold

    # ── 6. Bridge Detection ───────────────────────────────────────────
    if 'G_bib_analysis' in locals() and G_bib_analysis.number_of_nodes() >= 10:
        logger.info("Detecting interdisciplinary bridges...")
        bridges = find_interdisciplinary_bridges(G_bib_analysis, domain_map)
        metrics["interdisciplinary_bridges_count"] = len(bridges)
        save_json(bridges, f"{proc_dir}/interdisciplinary_bridges.json")
        logger.info("  Found %d bridge nodes", len(bridges))

    # ── 7. Network Layout Information ────────────────────────────────
    if 'G_bib_analysis' in locals() and G_bib_analysis.number_of_nodes() >= 5:
        logger.info("Computing VOS-inspired layout...")
        layout_2d = vos_layout(G_bib_analysis, dim=2)
        layout_3d = vos_layout(G_bib_analysis, dim=3)

        # Save layout information
        layout_data = {
            "layout_2d": {node: [round(x, 4), round(y, 4)] for node, (x, y) in layout_2d.items()},
            "layout_3d": {node: [round(x, 4), round(y, 4), round(z, 4)] for node, (x, y, z) in layout_3d.items()}
        }
        save_json(layout_data, f"{proc_dir}/network_layout.json")

    save_json(metrics, f"{proc_dir}/network_metrics.json")
    logger.info("=== Network Analysis Agent complete ===")
    logger.info("VOSviewer-inspired analysis completed with threshold %.1f", vos_threshold)


if __name__ == "__main__":
    main()
