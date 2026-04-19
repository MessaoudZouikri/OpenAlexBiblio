"""
Logging utilities for the bibliometric pipeline.
Provides structured, file-per-agent logging with JSON audit trail support.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional


def setup_logger(
    name: str,
    log_dir: str = "logs",
    level: str = "INFO",
    console: bool = True,
) -> logging.Logger:
    """
    Configure a named logger that writes to both file and console.

    Args:
        name: Agent/module name (used for log filename)
        log_dir: Directory for log files
        level: Logging level string
        console: Whether to also log to stdout

    Returns:
        Configured logger instance
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers on re-initialization
    if logger.handlers:
        logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    log_path = Path(log_dir) / f"{name}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


class AuditTrail:
    """
    Records a structured JSON audit trail for a pipeline run.
    Each step appends an entry with timing, parameters, and results.
    """

    def __init__(self, run_id: str, log_dir: str = "logs"):
        self.run_id = run_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.trail_path = self.log_dir / f"pipeline_run_{run_id}.json"
        self.entries: list[Dict[str, Any]] = []
        self._start_time = datetime.now(UTC).isoformat()

    def record(
        self,
        step: str,
        status: str,  # "success" | "failure" | "warning"
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        metrics: Optional[Dict] = None,
        error: Optional[str] = None,
        duration_s: Optional[float] = None,
    ) -> None:
        entry = {
            "step": step,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_s": duration_s,
            "inputs": inputs or {},
            "outputs": outputs or {},
            "metrics": metrics or {},
            "error": error,
        }
        self.entries.append(entry)
        self._flush()

    def _flush(self) -> None:
        payload = {
            "run_id": self.run_id,
            "started_at": self._start_time,
            "updated_at": datetime.now(UTC).isoformat(),
            "entries": self.entries,
        }
        with open(self.trail_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def finalize(self, overall_status: str) -> None:
        payload = {
            "run_id": self.run_id,
            "started_at": self._start_time,
            "finished_at": datetime.now(UTC).isoformat(),
            "overall_status": overall_status,
            "entries": self.entries,
        }
        with open(self.trail_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
