"""
Unit tests for src/agents/orchestrator.py
Tests focus on pure logic (get_start_index, step definitions) and
dry-run / mocked-subprocess execution paths.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.orchestrator import (
    ALL_STEP_NAMES,
    STEP_DEFINITIONS,
    get_start_index,
    run_step,
)


# ── ALL_STEP_NAMES / STEP_DEFINITIONS ────────────────────────────────────────


@pytest.mark.unit
def test_all_step_names_is_list_of_strings():
    assert isinstance(ALL_STEP_NAMES, list)
    assert all(isinstance(s, str) for s in ALL_STEP_NAMES)


@pytest.mark.unit
def test_step_definitions_length_matches_names():
    assert len(STEP_DEFINITIONS) == len(ALL_STEP_NAMES)


@pytest.mark.unit
def test_step_definitions_tuples_have_three_elements():
    for step in STEP_DEFINITIONS:
        assert len(step) == 3


@pytest.mark.unit
def test_required_steps_present():
    required = {
        "data_collection",
        "data_cleaning",
        "bibliometric_analysis",
        "classification",
        "network_analysis",
        "visualization",
    }
    assert required <= set(ALL_STEP_NAMES)


@pytest.mark.unit
def test_validation_steps_present():
    validation_steps = [s for s in ALL_STEP_NAMES if s.startswith("validate_")]
    assert len(validation_steps) >= 4


@pytest.mark.unit
def test_step_order_data_before_cleaning():
    assert ALL_STEP_NAMES.index("data_collection") < ALL_STEP_NAMES.index("data_cleaning")


@pytest.mark.unit
def test_step_order_cleaning_before_analysis():
    assert ALL_STEP_NAMES.index("data_cleaning") < ALL_STEP_NAMES.index("bibliometric_analysis")


@pytest.mark.unit
def test_step_order_analysis_before_classification():
    assert ALL_STEP_NAMES.index("bibliometric_analysis") < ALL_STEP_NAMES.index("classification")


@pytest.mark.unit
def test_step_order_classification_before_network():
    assert ALL_STEP_NAMES.index("classification") < ALL_STEP_NAMES.index("network_analysis")


@pytest.mark.unit
def test_no_duplicate_step_names():
    assert len(ALL_STEP_NAMES) == len(set(ALL_STEP_NAMES))


# ── get_start_index ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_get_start_index_first_step():
    assert get_start_index(ALL_STEP_NAMES[0]) == 0


@pytest.mark.unit
def test_get_start_index_last_step():
    last = ALL_STEP_NAMES[-1]
    assert get_start_index(last) == len(ALL_STEP_NAMES) - 1


@pytest.mark.unit
def test_get_start_index_data_cleaning():
    idx = get_start_index("data_cleaning")
    assert idx > 0


@pytest.mark.unit
def test_get_start_index_invalid_step_raises():
    with pytest.raises(ValueError, match="Unknown step"):
        get_start_index("nonexistent_step")


@pytest.mark.unit
def test_get_start_index_error_message_contains_valid_steps():
    with pytest.raises(ValueError, match="data_collection"):
        get_start_index("bad_step")


# ── run_step (dry_run=True) ───────────────────────────────────────────────────


@pytest.fixture
def mock_logger():
    logger = MagicMock()
    return logger


@pytest.mark.unit
def test_run_step_dry_run_returns_true(mock_logger, tmp_path):
    success, duration = run_step(
        step_name="data_collection",
        module_path="src.agents.data_collection",
        extra_args=[],
        config_path="config/config.yaml",
        logger=mock_logger,
        dry_run=True,
        logs_dir=str(tmp_path),
    )
    assert success is True
    assert duration == 0.0


@pytest.mark.unit
def test_run_step_dry_run_logs_skip(mock_logger, tmp_path):
    run_step(
        step_name="data_collection",
        module_path="src.agents.data_collection",
        extra_args=[],
        config_path="config/config.yaml",
        logger=mock_logger,
        dry_run=True,
        logs_dir=str(tmp_path),
    )
    logged_messages = [str(call) for call in mock_logger.info.call_args_list]
    assert any("DRY RUN" in msg for msg in logged_messages)


@pytest.mark.unit
def test_run_step_dry_run_does_not_create_log_file(mock_logger, tmp_path):
    run_step(
        step_name="data_collection",
        module_path="src.agents.data_collection",
        extra_args=[],
        config_path="config/config.yaml",
        logger=mock_logger,
        dry_run=True,
        logs_dir=str(tmp_path),
    )
    assert not (tmp_path / "data_collection_subprocess.log").exists()


# ── run_step (mocked subprocess) ──────────────────────────────────────────────


@pytest.mark.unit
def test_run_step_success(mock_logger, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "All good"
    mock_result.stderr = ""

    with patch("src.agents.orchestrator.subprocess.run", return_value=mock_result):
        success, duration = run_step(
            step_name="data_cleaning",
            module_path="src.agents.data_cleaning",
            extra_args=[],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    assert success is True
    assert duration >= 0.0


@pytest.mark.unit
def test_run_step_failure(mock_logger, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "ModuleNotFoundError: no module"

    with patch("src.agents.orchestrator.subprocess.run", return_value=mock_result):
        success, duration = run_step(
            step_name="data_cleaning",
            module_path="src.agents.data_cleaning",
            extra_args=[],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    assert success is False


@pytest.mark.unit
def test_run_step_writes_subprocess_log(mock_logger, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "output here"
    mock_result.stderr = ""

    with patch("src.agents.orchestrator.subprocess.run", return_value=mock_result):
        run_step(
            step_name="classification",
            module_path="src.agents.classification",
            extra_args=[],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    log_file = tmp_path / "classification_subprocess.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "output here" in content


@pytest.mark.unit
def test_run_step_logs_cmd_in_subprocess_log(mock_logger, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("src.agents.orchestrator.subprocess.run", return_value=mock_result):
        run_step(
            step_name="classification",
            module_path="src.agents.classification",
            extra_args=["--flag", "val"],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    content = (tmp_path / "classification_subprocess.log").read_text()
    assert "src.agents.classification" in content


@pytest.mark.unit
def test_run_step_file_not_found_returns_false(mock_logger, tmp_path):
    with patch(
        "src.agents.orchestrator.subprocess.run",
        side_effect=FileNotFoundError("no such file"),
    ):
        success, duration = run_step(
            step_name="data_collection",
            module_path="src.agents.data_collection",
            extra_args=[],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    assert success is False


@pytest.mark.unit
def test_run_step_exception_returns_false(mock_logger, tmp_path):
    with patch(
        "src.agents.orchestrator.subprocess.run",
        side_effect=RuntimeError("unexpected"),
    ):
        success, duration = run_step(
            step_name="data_collection",
            module_path="src.agents.data_collection",
            extra_args=[],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    assert success is False


@pytest.mark.unit
def test_run_step_extra_args_passed_to_subprocess(mock_logger, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return mock_result

    with patch("src.agents.orchestrator.subprocess.run", side_effect=fake_run):
        run_step(
            step_name="validate_raw",
            module_path="src.agents.validation.validators",
            extra_args=["--validator", "data", "--stage", "D1"],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    assert "--validator" in captured["cmd"]
    assert "D1" in captured["cmd"]
