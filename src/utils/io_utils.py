"""
I/O utilities: checkpoint management, file discovery, schema helpers.
All pipeline state is persisted to disk — no in-memory cross-agent state.
"""
import json
import os
import glob
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


# ── Checkpoint Management ──────────────────────────────────────────────────

CHECKPOINT_FILE = "checkpoints/pipeline_state.json"


def load_checkpoint(path: str = CHECKPOINT_FILE) -> Dict[str, Any]:
    """Load existing pipeline state; return empty state if not found."""
    if Path(path).exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"completed_steps": [], "run_id": None, "last_updated": None}


def save_checkpoint(state: Dict[str, Any], path: str = CHECKPOINT_FILE) -> None:
    """Persist pipeline state to disk atomically."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(UTC).isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def mark_step_complete(
    step_name: str,
    outputs: Optional[Dict] = None,
    path: str = CHECKPOINT_FILE,
) -> None:
    """Mark a pipeline step as successfully completed."""
    state = load_checkpoint(path)
    if step_name not in state["completed_steps"]:
        state["completed_steps"].append(step_name)
    state.setdefault("step_outputs", {})[step_name] = outputs or {}
    save_checkpoint(state, path)


def is_step_complete(step_name: str, path: str = CHECKPOINT_FILE) -> bool:
    """Return True if step has been marked complete in the checkpoint."""
    state = load_checkpoint(path)
    return step_name in state.get("completed_steps", [])


def reset_from_step(step_name: str, all_steps: List[str], path: str = CHECKPOINT_FILE) -> None:
    """Remove step and all downstream steps from completed list."""
    state = load_checkpoint(path)
    try:
        idx = all_steps.index(step_name)
    except ValueError:
        return
    steps_to_remove = set(all_steps[idx:])
    state["completed_steps"] = [
        s for s in state.get("completed_steps", []) if s not in steps_to_remove
    ]
    save_checkpoint(state, path)


# ── File Discovery ─────────────────────────────────────────────────────────

def latest_file(directory: str, pattern: str) -> Optional[Path]:
    """Return the most recently modified file matching a glob pattern."""
    matches = glob.glob(os.path.join(directory, pattern))
    if not matches:
        return None
    return Path(max(matches, key=os.path.getmtime))


def timestamped_path(directory: str, prefix: str, ext: str) -> Path:
    """Generate a timestamped output file path."""
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return Path(directory) / f"{prefix}_{ts}.{ext}"


# ── Parquet Helpers ────────────────────────────────────────────────────────

def save_parquet(df: pd.DataFrame, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")


def load_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path, engine="pyarrow")


# ── JSON Helpers ───────────────────────────────────────────────────────────

def save_json(data: Any, path: str, indent: int = 2) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Config Loading ─────────────────────────────────────────────────────────

def load_yaml(path: str) -> Dict:
    """Load YAML config file. Requires PyYAML."""
    import yaml
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ── Array-safe list coercion ───────────────────────────────────────────────

def safe_list(val) -> list:
    """Coerce a value to Python list — handles numpy arrays, None, scalars from parquet."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    try:
        return list(val)
    except Exception:
        return []
