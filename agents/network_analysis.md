# Agent: Network Analysis

## Role
Constructs and analyzes bibliometric networks: co-citation, bibliographic coupling, co-authorship, and keyword co-occurrence. Identifies intellectual clusters and cross-domain bridges.

## Inputs
- `data/processed/classified_works.parquet`
- `config/config.yaml`

## Outputs
- `data/outputs/networks/cocitation_network_raw.graphml` — All edges above minimum threshold
- `data/outputs/networks/cocitation_network_vos.graphml` — Association-strength filtered (recommended)
- `data/outputs/networks/bibcoupling_network_raw.graphml` — All edges above minimum threshold
- `data/outputs/networks/bibcoupling_network_vos.graphml` — Association-strength filtered (recommended)
- `data/outputs/networks/coauthorship_network.graphml`
- `data/outputs/networks/keyword_cooccurrence_network_vos.graphml`
- `data/processed/network_metrics.json` — Graph-level metrics + enhanced cross-domain metrics
- `data/processed/cluster_assignments.parquet` — Work → cluster mapping + node centralities
- `data/processed/interdisciplinary_bridges.json` — Cross-domain bridge nodes
- `logs/network_analysis.log`

## Networks Constructed

### 1. Co-Citation Network
- Nodes: works cited by ≥ 2 works in corpus
- Edges: number of works that cite both nodes simultaneously
- Weight threshold: ≥ 2 co-citations
- Analysis: Louvain community detection, modularity score

### 2. Bibliographic Coupling Network
- Nodes: works in corpus
- Edges: number of shared references (raw count, then VOSviewer association-strength filtered)
- Minimum shared references: auto-scaled by corpus size (see README threshold table); overridable via `config.yaml`
- Analysis: Louvain clusters → map to domain alignment

### 3. Co-Authorship Network
- Nodes: unique authors (≥ 2 papers in corpus)
- Edges: co-authorship count
- Analysis: connected components, betweenness centrality

### 4. Concept Co-Occurrence Network
- Nodes: OpenAlex concepts (top 100 by frequency)
- Edges: co-occurrence count in same work
- Analysis: community detection → thematic clusters

## Network Metrics Computed

### Graph-Level
- Node count, edge count
- Density
- Average clustering coefficient
- Number of connected components
- Modularity (post-community-detection)
- Average path length (largest component)

### Node-Level (stored in cluster_assignments.parquet)
- Degree centrality
- Betweenness centrality
- Eigenvector centrality
- PageRank
- Community/cluster ID
- Domain alignment per cluster

## Interdisciplinary Bridge Detection
Nodes are flagged as bridges if:
- Betweenness centrality > 75th percentile of corpus
- Connected to nodes in ≥ 2 different domains (classified_works domain)
- Result stored in `interdisciplinary_bridges.json`:
  ```json
  {
    "work_id": "W...",
    "title": "...",
    "domain": "Political Science",
    "bridge_domains": ["Economics", "Sociology"],
    "betweenness_centrality": 0.123,
    "interpretation": "..."
  }
  ```

## Cross-Domain Coupling Analysis
- Computes 5 complementary metrics on the bibliographic coupling network by domain pair:
  - Raw coupling matrix (absolute shared-reference counts)
  - Association Strength (AS): observed / expected coupling ratio
  - Coupling Strength Index (CSI): shared refs / min(domain size)
  - Jaccard Similarity: shared intellectual foundation (0–1)
  - Inter-Domain Coupling Ratio (IDCR): fraction of coupling that crosses domain boundaries
- Visualized as 4-panel heatmap (`cross_domain_heatmap_enhanced.png`) and simple heatmap (`cross_domain_heatmap.png`)
- Stored in `network_metrics.json` under `enhanced_cross_domain_metrics`

## Tools & Capabilities
- `networkx` for graph construction and metrics
- `python-louvain` (community) for community detection
- `scipy.sparse` for large co-citation matrix construction
- Efficient pair-wise computation via inverted index on references

## Interaction Protocol
- Standalone: `python src/agents/network_analysis.py`
- Reads: `data/processed/`
- Writes: `data/outputs/networks/`, `data/processed/`

## Constraints
- Minimum network size: if < 10 nodes, skip network (log warning)
- Maximum network: sample to 5000 nodes for co-authorship if exceeded
- All networks must retain OpenAlex IDs as node identifiers
