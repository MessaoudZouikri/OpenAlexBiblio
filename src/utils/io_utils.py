"""
I/O utilities: checkpoint management, file discovery, schema helpers.
All pipeline state is persisted to disk — no in-memory cross-agent state.
"""

import fcntl
import glob
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# ── Checkpoint Management ──────────────────────────────────────────────────

CHECKPOINT_FILE = "checkpoints/pipeline_state.json"


def _checkpoint_lock_path(path: str) -> str:
    return path + ".lock"


def load_checkpoint(path: str = CHECKPOINT_FILE) -> Dict[str, Any]:
    """Load existing pipeline state; return empty state if not found."""
    # Remove stale .tmp left by a previously interrupted write
    tmp = path + ".tmp"
    if Path(tmp).exists():
        try:
            os.remove(tmp)
        except OSError:
            pass
    if Path(path).exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"completed_steps": [], "run_id": None, "last_updated": None}


def save_checkpoint(state: Dict[str, Any], path: str = CHECKPOINT_FILE) -> None:
    """Persist pipeline state to disk atomically."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def mark_step_complete(
    step_name: str,
    outputs: Optional[Dict] = None,
    path: str = CHECKPOINT_FILE,
) -> None:
    """Mark a pipeline step as successfully completed (file-lock protected)."""
    lock_path = _checkpoint_lock_path(path)
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            state = load_checkpoint(path)
            if step_name not in state["completed_steps"]:
                state["completed_steps"].append(step_name)
            state.setdefault("step_outputs", {})[step_name] = outputs or {}
            save_checkpoint(state, path)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


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
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path(directory) / f"{prefix}_{ts}.{ext}"


# ── Parquet Helpers ────────────────────────────────────────────────────────


def save_parquet(df: pd.DataFrame, path: str) -> None:
    """Save DataFrame to parquet file with automatic directory creation."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")


def load_parquet(path: str, required_columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Load parquet file with optional schema validation.

    Args:
        path: Path to parquet file
        required_columns: List of column names that must be present

    Returns:
        DataFrame

    Raises:
        ValueError: If required columns are missing
        FileNotFoundError: If file doesn't exist
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")

    df = pd.read_parquet(path, engine="pyarrow")

    # Validate schema if required columns specified
    if required_columns:
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Missing required columns in {path}: {missing_cols}. " f"Found: {list(df.columns)}"
            )

    return df


def validate_dataframe_schema(df: pd.DataFrame, required_columns: List[str]) -> bool:
    """
    Validate that a DataFrame has all required columns.

    Args:
        df: DataFrame to validate
        required_columns: List of column names required

    Returns:
        True if all columns present, False otherwise

    Raises:
        ValueError: If columns are missing
    """
    missing_cols = set(required_columns) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}. " f"Found: {list(df.columns)}")
    return True


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
    if isinstance(val, dict):
        return [val]
    try:
        return list(val)
    except Exception:
        return []
