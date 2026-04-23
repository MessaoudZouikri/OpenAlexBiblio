# Agent: Classification Validation

## Role
Verifies the quality and consistency of classification outputs before network analysis.

## Inputs
- `data/processed/classified_works.parquet`
- `data/processed/classification_report.json`

## Outputs
- `logs/validation_classification.json`
- Pipeline signal: PASS / FAIL

## Validation Rules
- [ ] All records have non-null `domain` assignment
- [ ] All domains in approved taxonomy list
- [ ] All subcategories valid for their parent domain
- [ ] `domain_confidence` in [0.0, 1.0] for all records
- [ ] LLM-classified records: confidence distribution not uniformly high (>0.95 for >80% = suspicious)
- [ ] Cross-check: rule-based vs LLM agreement rate ≥ 60% (warn if below)
- [ ] "Other/interdisciplinary" rate ≤ 40% (warn if above — suggests poor concept coverage)
- [ ] Classification source distribution logged

## LLM Anti-Hallucination Checks
- [ ] LLM responses that were invalid JSON → count and rate
- [ ] LLM responses with out-of-taxonomy labels → count and rate
- [ ] Suspiciously uniform subcategory assignments (>50% same subcategory → flag)

## PASS/FAIL Logic
- FAIL: null domains > 5% of records
- FAIL: invalid taxonomy labels present
- WARN: LLM failure rate > 20%
- WARN: Other/interdisciplinary > 40%

---

# Agent: Network Validation

## Role
Verifies structural integrity of constructed networks before visualization.

## Inputs
- `data/outputs/networks/*.graphml`
- `data/processed/network_metrics.json`

## Outputs
- `logs/validation_network.json`
- Pipeline signal: PASS / FAIL

## Validation Rules
- [ ] Each GraphML file is valid and parseable
- [ ] Nodes have required attributes: `id`, `domain` (where applicable)
- [ ] No self-loops in co-citation and bibliographic coupling networks
- [ ] Weights are non-negative
- [ ] Metrics JSON contains all expected keys
- [ ] Community assignments cover ≥ 90% of nodes
- [ ] Betweenness centrality values in [0, 1]
- [ ] Bridge nodes: domain list contains valid domains only

## PASS/FAIL Logic
- FAIL: any network file is unreadable
- FAIL: > 10% nodes missing required attributes
- WARN: isolated nodes > 50% of network (suggests too-strict thresholds)

---

# Agent: Statistical Validation

## Role
Verifies statistical consistency of bibliometric metrics. Checks for known patterns in bibliometric literature to detect anomalies.

## Inputs
- `data/processed/bibliometric_summary.json`
- `data/processed/top_authors.json`
- `data/processed/publication_trends.json`

## Outputs
- `logs/validation_statistical.json`
- Pipeline signal: PASS / WARN (statistical issues never hard-fail)

## Validation Rules

### Lotka's Law
- [ ] Author productivity should follow inverse square law (α ≈ 2)
- [ ] Measure fit (R²) and report deviation

### Bradford's Law
- [ ] Journal zones should roughly follow 1:n:n² pattern
- [ ] Report if distribution is anomalous

### Citation Distribution
- [ ] Should be approximately log-normal / power-law
- [ ] Flag if mean >> median (expected, but extremes suspicious)
- [ ] Flag negative skew (unusual in bibliometrics)

### Temporal Coherence
- [ ] Year-on-year growth should not exceed 500% (flag if so)
- [ ] No records with year > current_year + 1

## PASS/FAIL Logic
- Statistical issues produce WARN only (never halt pipeline)
- All warnings included in final report
