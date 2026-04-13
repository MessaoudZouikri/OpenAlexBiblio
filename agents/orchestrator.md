# Agent: Orchestrator

## Role
Central coordinator of the bibliometric pipeline. Manages execution order, inter-agent communication, partial reruns, and logging. Does NOT perform data processing itself.

## Inputs
- `config/config.yaml` — Global pipeline configuration
- `checkpoints/pipeline_state.json` — Current execution state (created/updated by this agent)
- CLI arguments: `--mode [full|partial]`, `--from-step [step_name]`, `--dry-run`

## Outputs
- `checkpoints/pipeline_state.json` — Updated state after each step
- `logs/orchestrator.log` — Execution log with timestamps and step results
- `logs/pipeline_run_{timestamp}.json` — Full audit trail per run

## Responsibilities
1. Parse configuration and validate required parameters
2. Determine execution order based on dependency graph
3. Launch each agent as a subprocess or module call
4. Monitor success/failure of each step
5. On failure: log error, halt downstream steps, optionally trigger re-run
6. On success: update checkpoint, proceed to next step
7. Report final pipeline status

## Dependency Graph (Execution Order)
```
data_collection
      │
data_validation (D1)
      │
data_cleaning
      │
data_validation (D2)
      │
bibliometric_analysis
      │
statistical_validation
      │
classification
      │
classification_validation
      │
network_analysis
      │
network_validation
      │
visualization
```

## Tools & Capabilities
- Python `subprocess` / direct module imports
- File-based state management (JSON checkpoints)
- Structured logging (`logging` module)
- Step dependency resolver

## Interaction Protocol
- Communicates with agents via: shared file system (data/), config files
- Does NOT pass data in-memory between agents (stateless design)
- Each agent receives: input path + config path → produces output path
- On agent failure: reads stderr/stdout logs, records in audit trail

## Session Isolation
- This agent can be invoked in a fresh Claude session at any time
- Re-runs detect completed steps via `checkpoints/pipeline_state.json`
- `--from-step` flag allows resuming from any named step

## Constraints
- Must not assume previous conversational context
- Must produce deterministic execution given same config + data
