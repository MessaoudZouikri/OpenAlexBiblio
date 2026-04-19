"""
Enhanced Cross-Domain Metrics
=============================
Produces interpretable coupling matrices with direct statistical meaning.

Metrics computed:
1. Association Strength (VOSviewer-style): Observed/Expected ratio
2. Coupling Strength Index: Shared refs / min(domain_degree)
3. Jaccard Similarity: Shared intellectual foundation (0-1 scale)
4. Inter-Domain Ratio: Proportion of cross-domain connections
5. Domain Coverage: Fields with most interdisciplinary reach

Each metric has direct interpretation for researchers.
"""

from typing import Dict, Set

import networkx as nx


def compute_association_strength(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> Dict[str, Dict[str, float]]:
    """
    Association Strength (AS) normalization: Observed / Expected ratio.

    AS > 1.0   : Coupling stronger than random expectation
    AS = 1.0   : Random coupling
    AS < 1.0   : Coupling weaker than random expectation

    Based on VOSviewer methodology.
    """
    domains = sorted(set(domain_map.values()))

    # Count observed connections by domain pair
    observed = {d: {d2: 0 for d2 in domains} for d in domains}
    degrees = {d: 0.0 for d in domains}

    for a, b, data in G.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = float(data.get("weight", 1))

        observed[da][db] += w
        degrees[da] += w

    total_weight = sum(degrees.values())
    if total_weight == 0:
        return {d: {d2: 0.0 for d2 in domains} for d in domains}

    # Compute association strength
    as_matrix = {}
    for d1 in domains:
        as_matrix[d1] = {}
        for d2 in domains:
            obs = observed[d1][d2]
            exp = (degrees[d1] * degrees[d2]) / total_weight

            if exp > 0:
                as_value = obs / exp
            else:
                as_value = 0.0

            as_matrix[d1][d2] = round(as_value, 3)

    return as_matrix


def compute_coupling_strength_index(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> Dict[str, Dict[str, float]]:
    """
    Coupling Strength Index (CSI): Shared refs / min(domain_size).

    CSI = shared_refs / min(degree_i, degree_j)

    Interpretation:
    - High CSI (>0.5) : Strong coupling given domain sizes
    - Medium CSI (0.1-0.5) : Moderate coupling
    - Low CSI (<0.1) : Weak coupling
    """
    domains = sorted(set(domain_map.values()))

    # Count connections
    observed = {d: {d2: 0 for d2 in domains} for d in domains}
    degrees = {d: 0 for d in domains}

    for a, b, data in G.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = int(data.get("weight", 1))

        observed[da][db] += w
        degrees[da] += w

    csi_matrix = {}
    for d1 in domains:
        csi_matrix[d1] = {}
        for d2 in domains:
            obs = observed[d1][d2]
            min_degree = min(degrees[d1], degrees[d2])

            if min_degree > 0:
                csi = obs / min_degree
            else:
                csi = 0.0

            csi_matrix[d1][d2] = round(csi, 3)

    return csi_matrix


def compute_jaccard_similarity(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> Dict[str, Dict[str, float]]:
    """
    Jaccard Similarity: |Intersection| / |Union| of reference sets.

    Jaccard = (shared_refs_ij) / (refs_i + refs_j - shared_refs_ij)

    Range: 0 to 1

    Interpretation:
    - 1.0  : Identical reference base
    - 0.5  : 50% of intellectual foundation shared
    - 0.0  : No shared references

    This metric captures the "intellectual distance" between domains.
    """
    domains = sorted(set(domain_map.values()))

    # Collect references by domain
    domain_refs: Dict[str, Set[str]] = {d: set() for d in domains}

    for node in G.nodes():
        domain = domain_map.get(node, "Other")
        domain_refs[domain].add(node)

    jaccard_matrix = {}
    for d1 in domains:
        jaccard_matrix[d1] = {}
        for d2 in domains:
            refs_1 = domain_refs[d1]
            refs_2 = domain_refs[d2]

            if d1 == d2:
                jaccard = 1.0
            else:
                intersection = len(refs_1 & refs_2)
                union = len(refs_1 | refs_2)

                if union > 0:
                    jaccard = intersection / union
                else:
                    jaccard = 0.0

            jaccard_matrix[d1][d2] = round(jaccard, 3)

    return jaccard_matrix


def compute_inter_domain_coupling_ratio(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> float:
    """
    Inter-Domain Coupling Ratio (IDCR).

    IDCR = (edges between different domains) / (total edges)

    Range: 0 to 1

    Interpretation:
    - IDCR > 0.3 : Highly interdisciplinary field
    - IDCR 0.1-0.3 : Moderately interdisciplinary
    - IDCR < 0.1 : Siloed, domain-specific field
    """
    total_weight = 0.0
    inter_weight = 0.0

    for a, b, data in G.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = float(data.get("weight", 1))

        total_weight += w
        if da != db:
            inter_weight += w

    if total_weight == 0:
        return 0.0

    return round(inter_weight / total_weight, 3)


def compute_domain_reach(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> Dict[str, dict]:
    """
    Domain Reach: How many other domains does each domain connect to?

    Metrics per domain:
    - unique_connected_domains: Number of other domains this domain couples with
    - reach_breadth: Fraction of possible cross-domain connections realized
    - total_cross_domain_weight: Total strength of connections to other domains
    - intra_domain_weight: Total strength of within-domain connections
    """
    domains = sorted(set(domain_map.values()))
    n_domains = len(domains)

    reach = {}
    for d in domains:
        reach[d] = {
            "connected_domains": set(),
            "intra_weight": 0.0,
            "inter_weight": 0.0,
        }

    for a, b, data in G.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = float(data.get("weight", 1))

        if da == db:
            reach[da]["intra_weight"] += w
        else:
            reach[da]["inter_weight"] += w
            reach[db]["inter_weight"] += w
            reach[da]["connected_domains"].add(db)
            reach[db]["connected_domains"].add(da)

    # Compute metrics
    result = {}
    for d in domains:
        n_connected = len(reach[d]["connected_domains"])
        max_possible = n_domains - 1

        result[d] = {
            "unique_connected_domains": n_connected,
            "reach_breadth": round(n_connected / max_possible, 3) if max_possible > 0 else 0,
            "intra_domain_weight": int(reach[d]["intra_weight"]),
            "inter_domain_weight": int(reach[d]["inter_weight"]),
            "inter_domain_ratio": (
                round(
                    reach[d]["inter_weight"]
                    / (reach[d]["intra_weight"] + reach[d]["inter_weight"]),
                    3,
                )
                if (reach[d]["intra_weight"] + reach[d]["inter_weight"]) > 0
                else 0
            ),
        }

    return result


def enhanced_cross_domain_analysis(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> dict:
    """
    Comprehensive cross-domain analysis with multiple interpretable metrics.

    Returns:
        Dictionary with:
        - raw_coupling_matrix: Absolute edge weights
        - association_strength: Normalized AS > 1 means stronger than random
        - coupling_strength_index: Shared refs / min domain size
        - jaccard_similarity: Shared intellectual foundation (0-1)
        - inter_domain_ratio: Global interdisciplinarity measure
        - domain_reach: Per-domain connectivity metrics
        - statistical_summary: Summary statistics
    """
    return {
        "raw_coupling_matrix": _raw_coupling_matrix(G, domain_map),
        "association_strength": compute_association_strength(G, domain_map),
        "coupling_strength_index": compute_coupling_strength_index(G, domain_map),
        "jaccard_similarity": compute_jaccard_similarity(G, domain_map),
        "inter_domain_coupling_ratio": compute_inter_domain_coupling_ratio(G, domain_map),
        "domain_reach": compute_domain_reach(G, domain_map),
        "interpretation": {
            "raw_coupling_matrix": "Absolute count of shared references (raw data)",
            "association_strength": "Normalized coupling; AS > 1 = stronger than random, AS < 1 = weaker",
            "coupling_strength_index": "Ratio of shared refs to minimum domain size; high CSI = strong relative coupling",
            "jaccard_similarity": "Fraction of shared intellectual foundation (0-1); high = similar reference bases",
            "inter_domain_coupling_ratio": "Global measure: proportion of coupling across domain boundaries (0-1)",
            "domain_reach": "Per-domain connectivity: breadth, intra/inter weights, and ratios",
        },
        "statistical_summary": _compute_statistics(G, domain_map),
    }


def _raw_coupling_matrix(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> Dict[str, Dict[str, int]]:
    """Compute raw coupling counts by domain pair."""
    domains = sorted(set(domain_map.values()))
    matrix = {d: {d2: 0 for d2 in domains} for d in domains}

    for a, b, data in G.edges(data=True):
        da = domain_map.get(a, "Other")
        db = domain_map.get(b, "Other")
        w = int(data.get("weight", 1))
        matrix[da][db] += w

    return matrix


def _compute_statistics(
    G: nx.Graph,
    domain_map: Dict[str, str],
) -> dict:
    """Compute summary statistics for the coupling network."""
    domains = list(set(domain_map.values()))
    n_domains = len(domains)

    # Count edges and weights
    total_edges = G.number_of_edges()
    total_weight = sum(data.get("weight", 1) for _, _, data in G.edges(data=True))

    # Count intra vs inter domain edges
    intra_edges = 0
    inter_edges = 0
    for a, b, data in G.edges(data=True):
        if domain_map.get(a, "Other") == domain_map.get(b, "Other"):
            intra_edges += int(data.get("weight", 1))
        else:
            inter_edges += int(data.get("weight", 1))

    # Domain sizes
    domain_sizes = {d: sum(1 for node, dom in domain_map.items() if dom == d) for d in domains}

    return {
        "n_domains": n_domains,
        "n_nodes": G.number_of_nodes(),
        "n_edges": total_edges,
        "total_weight": int(total_weight),
        "intra_domain_weight": int(intra_edges),
        "inter_domain_weight": int(inter_edges),
        "average_weight_per_edge": round(total_weight / total_edges, 2) if total_edges > 0 else 0,
        "interdisciplinarity_index": round(
            inter_edges / total_weight if total_weight > 0 else 0, 3
        ),
        "domain_sizes": domain_sizes,
        "network_density": round(nx.density(G), 4),
    }
