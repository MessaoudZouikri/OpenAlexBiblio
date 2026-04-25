"""
Orchestrator Agent
==================
Central pipeline coordinator. Manages execution order, checkpointing,
partial re-runs, and audit trail. Stateless — all state is stored on disk.

Usage
-----
    python src/agents/orchestrator.py                             # full run
    python src/agents/orchestrator.py --from-step data_cleaning   # resume
    python src/agents/orchestrator.py --dry-run                   # preview
    python src/agents/orchestrator.py --list-steps                # enumerate
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import (
    is_step_complete,
    load_checkpoint,
    load_yaml,
    mark_step_complete,
    reset_from_step,
    save_checkpoint,
)
from src.utils.logging_utils import AuditTrail, setup_logger

STEP_TIMEOUT_S = 3600  # max seconds per pipeline step before it is killed

# ═══════════════════════════════════════════════════════════════════════════
# Step Definitions
# ═══════════════════════════════════════════════════════════════════════════
# Each step is (name, module_path, extra_args).
# Module paths use Python's dotted module notation, not filesystem paths.

STEP_DEFINITIONS: List[Tuple[str, str, List[str]]] = [
    ("data_collection", "src.agents.data_collection", []),
    ("validate_raw", "src.agents.validation.validators", ["--validator", "data", "--stage", "D1"]),
    ("data_cleaning", "src.agents.data_cleaning", []),
    (
        "validate_clean",
        "src.agents.validation.validators",
        ["--validator", "data", "--stage", "D2"],
    ),
    ("bibliometric_analysis", "src.agents.bibliometric_analysis", []),
    ("validate_statistical", "src.agents.validation.validators", ["--validator", "statistical"]),
    ("classification", "src.agents.classification", []),
    (
        "validate_classification",
        "src.agents.validation.validators",
        ["--validator", "classification"],
    ),
    ("network_analysis", "src.agents.network_analysis", []),
    ("validate_network", "src.agents.validation.validators", ["--validator", "network"]),
    ("visualization", "src.agents.visualization", []),
]

ALL_STEP_NAMES: List[str] = [s[0] for s in STEP_DEFINITIONS]


# ═══════════════════════════════════════════════════════════════════════════
# Step Execution
# ═══════════════════════════════════════════════════════════════════════════


def run_step(
    step_name: str,
    module_path: str,
    extra_args: List[str],
    config_path: str,
    logger: logging.Logger,
    dry_run: bool = False,
    logs_dir: str = "logs",
) -> Tuple[bool, float]:
    """
    Execute a single pipeline step via ``python -m``.

    Stdout/stderr are captured and written to ``logs/{step_name}_subprocess.log``
    so that failure tracebacks are preserved in the audit trail.

    Returns:
        (success, duration_seconds)
    """
    cmd = [sys.executable, "-m", module_path, "--config", config_path] + extra_args
    logger.info("▶ Step [%s]: %s", step_name, " ".join(cmd))

    if dry_run:
        logger.info("  [DRY RUN] skipping execution")
        return True, 0.0

    subprocess_log = Path(logs_dir) / f"{step_name}_subprocess.log"
    subprocess_log.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=STEP_TIMEOUT_S,
        )
        duration = time.time() - t0
        success = result.returncode == 0

        with open(subprocess_log, "w") as fh:
            fh.write(f"# cmd: {' '.join(cmd)}\n")
            fh.write(f"# rc: {result.returncode}\n\n")
            if result.stdout:
                fh.write("=== STDOUT ===\n")
                fh.write(result.stdout)
            if result.stderr:
                fh.write("\n=== STDERR ===\n")
                fh.write(result.stderr)

        if success:
            logger.info("  ✓ Step [%s] completed in %.1fs", step_name, duration)
        else:
            logger.error(
                "  ✗ Step [%s] FAILED (rc=%d) in %.1fs — see %s",
                step_name,
                result.returncode,
                duration,
                subprocess_log,
            )
            if result.stderr:
                # Echo last 20 lines of stderr directly into the orchestrator log
                tail = result.stderr.strip().splitlines()[-20:]
                logger.error("  stderr tail:\n%s", "\n".join(f"    {line}" for line in tail))
        return success, duration

    except FileNotFoundError as exc:
        duration = time.time() - t0
        logger.error("  ✗ Step [%s]: executable not found: %s", step_name, exc)
        return False, duration
    except subprocess.TimeoutExpired:
        duration = time.time() - t0
        logger.error(
            "  ✗ Step [%s] TIMED OUT after %ds — see %s", step_name, STEP_TIMEOUT_S, subprocess_log
        )
        return False, duration
    except Exception as exc:
        duration = time.time() - t0
        logger.error("  ✗ Step [%s] raised exception: %s", step_name, exc)
        return False, duration


def get_start_index(from_step: str) -> int:
    """Return the index of ``from_step`` in the ordered step list."""
    if from_step in ALL_STEP_NAMES:
        return ALL_STEP_NAMES.index(from_step)
    raise ValueError(f"Unknown step: {from_step!r}. Valid: {ALL_STEP_NAMES}")


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Entry
# ═══════════════════════════════════════════════════════════════════════════


def run_pipeline(
    config_path: str = "config/config.yaml",
    from_step: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """
    Execute the full pipeline (or resume from a specific step).

    Args:
        config_path: Path to the pipeline config YAML.
        from_step:   If provided, reset the checkpoint from this step and
                     begin execution here. Downstream steps are re-run.
        dry_run:     Log what would happen, but execute nothing.
        force:       Re-run steps even if the checkpoint marks them complete.

    Returns:
        True if every step succeeded, False on the first halting failure
        or if any non-halting step failed (partial success).
    """
    config = load_yaml(config_path)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger = setup_logger("orchestrator", config["paths"]["logs"])
    audit = AuditTrail(run_id, config["paths"]["logs"])

    logger.info("=" * 60)
    logger.info("BIBLIOMETRIC PIPELINE — Run ID: %s", run_id)
    logger.info(
        "Mode: %s | From: %s | DryRun: %s | Force: %s",
        config["pipeline"]["mode"],
        from_step or "start",
        dry_run,
        force,
    )
    logger.info("=" * 60)

    # ── Resolve starting position ────────────────────────────────────────
    start_idx = 0
    if from_step:
        start_idx = get_start_index(from_step)
        reset_from_step(from_step, ALL_STEP_NAMES)
        logger.info("Resetting checkpoint from step: %s", from_step)

    state = load_checkpoint()
    state["run_id"] = run_id
    save_checkpoint(state)

    # ── Execute steps ────────────────────────────────────────────────────
    overall_success = True
    failure_handling = config.get("failure", {}).get("on_validation_fail", "halt")
    agent_error_mode = config.get("failure", {}).get("on_agent_error", "halt")

    for i, (step_name, module_path, extra_args) in enumerate(STEP_DEFINITIONS):
        if i < start_idx:
            logger.info("  [SKIP] %s (before start step)", step_name)
            continue

        if not force and is_step_complete(step_name):
            logger.info("  [CACHED] %s — already complete", step_name)
            continue

        success, duration = run_step(
            step_name,
            module_path,
            extra_args,
            config_path,
            logger,
            dry_run,
            logs_dir=config["paths"]["logs"],
        )

        audit.record(
            step=step_name,
            status="success" if success else "failure",
            outputs={"duration_s": round(duration, 2)},
            duration_s=round(duration, 2),
        )

        if success:
            mark_step_complete(step_name)
            continue

        overall_success = False
        is_validation = step_name.startswith("validate_")
        should_halt = (is_validation and failure_handling == "halt") or (
            not is_validation and agent_error_mode == "halt"
        )
        if should_halt:
            logger.error("Pipeline HALTED at step: %s", step_name)
            audit.finalize("FAILED")
            return False
        logger.warning(
            "Step %s failed — continuing (failure_handling=warn)",
            step_name,
        )

    final_status = "SUCCESS" if overall_success else "PARTIAL"
    audit.finalize(final_status)
    logger.info("=" * 60)
    logger.info("Pipeline %s — Run ID: %s", final_status, run_id)
    logger.info("=" * 60)
    return overall_success


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bibliometric Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/agents/orchestrator.py                             Run full pipeline
  python src/agents/orchestrator.py --from-step data_cleaning   Resume from cleaning
  python src/agents/orchestrator.py --dry-run                   Show steps without running
  python src/agents/orchestrator.py --list-steps                List available steps
        """,
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--from-step", metavar="STEP", help="Start execution from this step (resets downstream)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-run even already-completed steps")
    parser.add_argument("--list-steps", action="store_true")
    args = parser.parse_args()

    if args.list_steps:
        print("\nAvailable pipeline steps:")
        for i, name in enumerate(ALL_STEP_NAMES, start=1):
            print(f"  {i:2d}. {name}")
        return

    success = run_pipeline(
        config_path=args.config,
        from_step=args.from_step,
        dry_run=args.dry_run,
        force=args.force,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
