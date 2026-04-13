"""
Network Analysis Agent
======================
Constructs co-citation, bibliographic coupling, co-authorship, and concept
co-occurrence networks. Detects communities and cross-domain bridges.
Outputs: GraphML files + network_metrics.json + cluster_assignments.parquet

Standalone:
    python src/agents/network_analysis.py --config config/config.yaml
"""
import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime, UTC
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple

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


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Network Analysis Agent")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    logger = setup_logger("network_analysis", config["paths"]["logs"])
    logger.info("=== Network Analysis Agent starting ===")

    proc_dir = config["paths"]["data_processed"]
    net_dir = config["paths"]["outputs"] + "/networks"
    Path(net_dir).mkdir(parents=True, exist_ok=True)

    df = load_parquet(f"{proc_dir}/classified_works.parquet")
    logger.info("Loaded %d classified works", len(df))

    domain_map = df.set_index("id")["domain"].to_dict()
    metrics = {"timestamp": datetime.now(UTC).isoformat()}

    # ── 1. Bibliographic Coupling ────────────────────────────────────
    logger.info("Building bibliographic coupling network...")
    G_bib = build_bibcoupling_network(df, min_shared=2)
    logger.info("  Bib coupling: %d nodes, %d edges", G_bib.number_of_nodes(), G_bib.number_of_edges())
    if G_bib.number_of_nodes() >= 5:
        save_network(G_bib, f"{net_dir}/bibcoupling_network.graphml")
        partition, modularity = detect_communities(G_bib)
        metrics["bibcoupling"] = {**graph_summary(G_bib, "bibcoupling"), "modularity": modularity}
        metrics["cross_domain_matrix"] = cross_domain_matrix(G_bib, domain_map)

        # Cluster assignments
        cluster_rows = []
        bc = nx.betweenness_centrality(G_bib, weight="weight", normalized=True)
        pr = nx.pagerank(G_bib, weight="weight")
        for node in G_bib.nodes():
            cluster_rows.append({
                "work_id": node,
                "domain": domain_map.get(node, "Other"),
                "cluster_id": partition.get(node, -1),
                "betweenness_centrality": round(bc.get(node, 0.0), 6),
                "pagerank": round(pr.get(node, 0.0), 8),
                "degree": G_bib.degree(node),
            })
        df_clusters = pd.DataFrame(cluster_rows)
        save_parquet(df_clusters, f"{proc_dir}/cluster_assignments.parquet")
        logger.info("  Modularity: %.4f, Communities: %d", modularity, len(set(partition.values())))

    # ── 2. Co-Citation Network ────────────────────────────────────────
    logger.info("Building co-citation network...")
    G_cc = build_cocitation_network(df, min_cocitations=2)
    logger.info("  Co-citation: %d nodes, %d edges", G_cc.number_of_nodes(), G_cc.number_of_edges())
    if G_cc.number_of_nodes() >= 5:
        save_network(G_cc, f"{net_dir}/cocitation_network.graphml")
        _, cc_modularity = detect_communities(G_cc)
        metrics["cocitation"] = {**graph_summary(G_cc, "cocitation"), "modularity": cc_modularity}

    # ── 3. Co-Authorship Network ──────────────────────────────────────
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
        metrics["coauthorship"] = {**graph_summary(G_auth, "coauthorship"), "modularity": auth_modularity}

    # ── 4. Concept Co-occurrence Network ──────────────────────────────
    logger.info("Building concept co-occurrence network...")
    G_concept = build_concept_cooccurrence_network(df, top_n=100)
    logger.info("  Concept: %d nodes, %d edges", G_concept.number_of_nodes(), G_concept.number_of_edges())
    if G_concept.number_of_nodes() >= 5:
        save_network(G_concept, f"{net_dir}/keyword_cooccurrence_network.graphml")
        metrics["concept_cooccurrence"] = graph_summary(G_concept, "concept_cooccurrence")

    # ── 5. Bridge Detection ───────────────────────────────────────────
    if G_bib.number_of_nodes() >= 10:
        logger.info("Detecting interdisciplinary bridges...")
        bridges = find_interdisciplinary_bridges(G_bib, domain_map)
        metrics["interdisciplinary_bridges_count"] = len(bridges)
        save_json(bridges, f"{proc_dir}/interdisciplinary_bridges.json")
        logger.info("  Found %d bridge nodes", len(bridges))

    save_json(metrics, f"{proc_dir}/network_metrics.json")
    logger.info("=== Network Analysis Agent complete ===")


if __name__ == "__main__":
    main()
