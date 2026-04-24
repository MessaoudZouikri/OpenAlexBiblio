"""
Unit tests for src/utils/io_utils.py
Uses tmp_path fixtures — no pipeline files touched.
"""

import os
import time

import pandas as pd
import pytest

from src.utils.io_utils import (
    latest_file,
    load_checkpoint,
    load_json,
    load_parquet,
    load_yaml,
    mark_step_complete,
    reset_from_step,
    safe_list,
    save_checkpoint,
    save_json,
    save_parquet,
    timestamped_path,
    validate_dataframe_schema,
)


# ── Checkpoint helpers ────────────────────────────────────────────────────────


def test_load_checkpoint_missing_file(tmp_path):
    state = load_checkpoint(str(tmp_path / "missing.json"))
    assert state["completed_steps"] == []
    assert state["run_id"] is None


def test_save_and_load_checkpoint(tmp_path):
    path = str(tmp_path / "state.json")
    state = {"completed_steps": ["data_collection"], "run_id": "abc", "last_updated": None}
    save_checkpoint(state, path)
    loaded = load_checkpoint(path)
    assert loaded["completed_steps"] == ["data_collection"]
    assert loaded["run_id"] == "abc"


def test_save_checkpoint_removes_stale_tmp(tmp_path):
    path = str(tmp_path / "state.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("stale")
    state = {"completed_steps": [], "run_id": None, "last_updated": None}
    save_checkpoint(state, path)
    assert not os.path.exists(tmp)


def test_mark_step_complete(tmp_path):
    path = str(tmp_path / "state.json")
    mark_step_complete("data_collection", {"rows": 100}, path)
    state = load_checkpoint(path)
    assert "data_collection" in state["completed_steps"]
    assert state["step_outputs"]["data_collection"]["rows"] == 100


def test_mark_step_complete_idempotent(tmp_path):
    path = str(tmp_path / "state.json")
    mark_step_complete("step_a", {}, path)
    mark_step_complete("step_a", {}, path)
    state = load_checkpoint(path)
    assert state["completed_steps"].count("step_a") == 1


def test_reset_from_step(tmp_path):
    path = str(tmp_path / "state.json")
    all_steps = ["a", "b", "c", "d"]
    for s in all_steps:
        mark_step_complete(s, {}, path)
    reset_from_step("c", all_steps, path)
    state = load_checkpoint(path)
    assert "a" in state["completed_steps"]
    assert "b" in state["completed_steps"]
    assert "c" not in state["completed_steps"]
    assert "d" not in state["completed_steps"]


def test_reset_from_step_unknown_step(tmp_path):
    path = str(tmp_path / "state.json")
    mark_step_complete("a", {}, path)
    reset_from_step("nonexistent", ["a", "b"], path)
    state = load_checkpoint(path)
    assert "a" in state["completed_steps"]


# ── latest_file ───────────────────────────────────────────────────────────────


def test_latest_file_returns_most_recent(tmp_path):
    old = tmp_path / "file_20240101.parquet"
    new = tmp_path / "file_20240201.parquet"
    old.write_text("old")
    time.sleep(0.01)
    new.write_text("new")
    result = latest_file(str(tmp_path), "file_*.parquet")
    assert result.name == "file_20240201.parquet"


def test_latest_file_no_matches(tmp_path):
    assert latest_file(str(tmp_path), "*.parquet") is None


# ── timestamped_path ──────────────────────────────────────────────────────────


def test_timestamped_path_format(tmp_path):
    p = timestamped_path(str(tmp_path), "raw", "parquet")
    assert p.suffix == ".parquet"
    assert p.name.startswith("raw_")
    assert str(tmp_path) in str(p)


# ── Parquet helpers ───────────────────────────────────────────────────────────


def test_save_and_load_parquet(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = str(tmp_path / "test.parquet")
    save_parquet(df, path)
    loaded = load_parquet(path)
    assert list(loaded.columns) == ["a", "b"]
    assert len(loaded) == 2


def test_load_parquet_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_parquet(str(tmp_path / "missing.parquet"))


def test_load_parquet_required_columns(tmp_path):
    df = pd.DataFrame({"a": [1]})
    path = str(tmp_path / "test.parquet")
    save_parquet(df, path)
    with pytest.raises(ValueError, match="Missing required columns"):
        load_parquet(path, required_columns=["a", "b"])


def test_load_parquet_required_columns_ok(tmp_path):
    df = pd.DataFrame({"a": [1], "b": [2]})
    path = str(tmp_path / "test.parquet")
    save_parquet(df, path)
    loaded = load_parquet(path, required_columns=["a"])
    assert "a" in loaded.columns


# ── validate_dataframe_schema ─────────────────────────────────────────────────


def test_validate_schema_ok():
    df = pd.DataFrame({"a": [1], "b": [2]})
    assert validate_dataframe_schema(df, ["a", "b"]) is True


def test_validate_schema_missing():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_dataframe_schema(df, ["a", "b"])


# ── JSON helpers ──────────────────────────────────────────────────────────────


def test_save_and_load_json(tmp_path):
    data = {"key": "value", "numbers": [1, 2, 3]}
    path = str(tmp_path / "data.json")
    save_json(data, path)
    loaded = load_json(path)
    assert loaded == data


def test_save_json_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "nested" / "dir" / "data.json")
    save_json({"x": 1}, path)
    assert os.path.exists(path)


# ── YAML loading ──────────────────────────────────────────────────────────────


def test_load_yaml(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("key: value\nnumber: 42\n")
    result = load_yaml(str(yaml_path))
    assert result["key"] == "value"
    assert result["number"] == 42


# ── safe_list ─────────────────────────────────────────────────────────────────


def test_safe_list_none():
    assert safe_list(None) == []


def test_safe_list_plain_list():
    assert safe_list([1, 2, 3]) == [1, 2, 3]


def test_safe_list_dict():
    assert safe_list({"a": 1}) == [{"a": 1}]


def test_safe_list_tuple():
    assert safe_list((1, 2)) == [1, 2]


def test_safe_list_scalar_string():
    assert safe_list("abc") == ["a", "b", "c"]
