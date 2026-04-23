# Agent: Network Analysis

## Role
Constructs and analyzes bibliometric networks: co-citation, bibliographic coupling, co-authorship, and keyword co-occurrence. Identifies intellectual clusters and cross-domain bridges.

## Inputs
- `data/processed/classified_works.parquet`
- `config/config.yaml`

## Outputs
- `data/outputs/networks/cocitation_network.graphml`
- `data/outputs/networks/bibcoupling_network.graphml`
- `data/outputs/networks/coauthorship_network.graphml`
- `data/outputs/networks/keyword_cooccurrence_network.graphml`
- `data/processed/network_metrics.json` — Node-level and graph-level metrics
- `data/processed/cluster_assignments.parquet` — Work → cluster mapping
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
- Edges: number of shared references
- Normalization: cosine similarity on reference vectors
- Minimum coupling strength: 0.1 (configurable)
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

## Cross-Domain Co-Citation Analysis
- Build domain×domain co-citation matrix
- Cell [i,j] = number of cross-domain co-citation pairs
- Visualized as heatmap (passed to Visualization agent)
- Stored in `network_metrics.json` under `cross_domain_matrix`

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
