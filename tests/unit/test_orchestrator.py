"""
Unit tests for src/agents/orchestrator.py
Tests focus on pure logic (get_start_index, step definitions) and
dry-run / mocked-subprocess execution paths.
"""

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


# ── run_step (TimeoutExpired) ─────────────────────────────────────────────────


@pytest.mark.unit
def test_run_step_timeout_returns_false(mock_logger, tmp_path):
    import subprocess

    with patch(
        "src.agents.orchestrator.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="python", timeout=3600),
    ):
        success, duration = run_step(
            step_name="network_analysis",
            module_path="src.agents.network_analysis",
            extra_args=[],
            config_path="config/config.yaml",
            logger=mock_logger,
            dry_run=False,
            logs_dir=str(tmp_path),
        )

    assert success is False
    assert duration >= 0.0


# ── run_pipeline ──────────────────────────────────────────────────────────────

_MINIMAL_CONFIG = {
    "pipeline": {"mode": "full"},
    "paths": {"logs": "logs"},
    "failure": {"on_validation_fail": "halt", "on_agent_error": "halt"},
}


def _make_pipeline_patches(
    step_results=None,
    is_complete=False,
    from_step_name=None,
):
    """Return a dict of patches needed to run run_pipeline in isolation."""
    if step_results is None:
        step_results = [(True, 0.1)] * 11  # one result per pipeline step

    patches = {
        "load_yaml": patch("src.agents.orchestrator.load_yaml", return_value=_MINIMAL_CONFIG),
        "setup_logger": patch("src.agents.orchestrator.setup_logger", return_value=MagicMock()),
        "AuditTrail": patch("src.agents.orchestrator.AuditTrail"),
        "load_checkpoint": patch(
            "src.agents.orchestrator.load_checkpoint",
            return_value={"completed_steps": [], "step_outputs": {}},
        ),
        "save_checkpoint": patch("src.agents.orchestrator.save_checkpoint"),
        "is_step_complete": patch(
            "src.agents.orchestrator.is_step_complete", return_value=is_complete
        ),
        "mark_step_complete": patch("src.agents.orchestrator.mark_step_complete"),
        "reset_from_step": patch("src.agents.orchestrator.reset_from_step"),
        "run_step": patch("src.agents.orchestrator.run_step", side_effect=step_results),
    }
    return patches


@pytest.mark.unit
def test_run_pipeline_all_success_returns_true(tmp_path):
    p = _make_pipeline_patches()
    with (
        p["load_yaml"],
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"],
        p["run_step"],
    ):
        from src.agents.orchestrator import run_pipeline

        result = run_pipeline(config_path="config/config.yaml")

    assert result is True


@pytest.mark.unit
def test_run_pipeline_step_failure_halt_returns_false(tmp_path):
    results = [(False, 0.1)] + [(True, 0.1)] * 10
    p = _make_pipeline_patches(step_results=results)
    with (
        p["load_yaml"],
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"],
        p["run_step"],
    ):
        from src.agents.orchestrator import run_pipeline

        result = run_pipeline(config_path="config/config.yaml")

    assert result is False


@pytest.mark.unit
def test_run_pipeline_validation_fail_warn_continues(tmp_path):
    warn_config = {
        **_MINIMAL_CONFIG,
        "failure": {"on_validation_fail": "warn", "on_agent_error": "warn"},
    }
    # validate_raw is step index 1 → fail it, rest succeed
    results = [(True, 0.1), (False, 0.1)] + [(True, 0.1)] * 9
    p = _make_pipeline_patches(step_results=results)
    with (
        patch("src.agents.orchestrator.load_yaml", return_value=warn_config),
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"],
        p["run_step"],
    ):
        from src.agents.orchestrator import run_pipeline

        result = run_pipeline(config_path="config/config.yaml")

    # Pipeline completes but returns False because a step failed
    assert result is False


@pytest.mark.unit
def test_run_pipeline_all_cached_skips_run_step(tmp_path):
    p = _make_pipeline_patches(is_complete=True)
    with (
        p["load_yaml"],
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"],
        p["run_step"] as mock_run_step,
    ):
        from src.agents.orchestrator import run_pipeline

        run_pipeline(config_path="config/config.yaml")

    mock_run_step.assert_not_called()


@pytest.mark.unit
def test_run_pipeline_force_reruns_cached_steps(tmp_path):
    p = _make_pipeline_patches(is_complete=True)
    with (
        p["load_yaml"],
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"],
        p["run_step"] as mock_run_step,
    ):
        from src.agents.orchestrator import run_pipeline

        run_pipeline(config_path="config/config.yaml", force=True)

    assert mock_run_step.call_count == 11


@pytest.mark.unit
def test_run_pipeline_from_step_resets_and_skips(tmp_path):
    p = _make_pipeline_patches()
    with (
        p["load_yaml"],
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"] as mock_reset,
        p["run_step"] as mock_run_step,
    ):
        from src.agents.orchestrator import run_pipeline

        run_pipeline(config_path="config/config.yaml", from_step="network_analysis")

    mock_reset.assert_called_once()
    # network_analysis is step index 8 → 11 - 8 = 3 steps should run
    assert mock_run_step.call_count == 3


@pytest.mark.unit
def test_run_pipeline_dry_run_calls_run_step_dry(tmp_path):
    p = _make_pipeline_patches()
    with (
        p["load_yaml"],
        p["setup_logger"],
        p["AuditTrail"],
        p["load_checkpoint"],
        p["save_checkpoint"],
        p["is_step_complete"],
        p["mark_step_complete"],
        p["reset_from_step"],
        p["run_step"] as mock_run_step,
    ):
        from src.agents.orchestrator import run_pipeline

        run_pipeline(config_path="config/config.yaml", dry_run=True)

    for call in mock_run_step.call_args_list:
        assert call.kwargs.get("dry_run") is True or call.args[5] is True


# ── main() (--list-steps) ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_main_list_steps_prints_and_exits(capsys):

    with patch("sys.argv", ["orchestrator.py", "--list-steps"]):
        from src.agents.orchestrator import main

        main()

    captured = capsys.readouterr()
    assert "data_collection" in captured.out
    assert "visualization" in captured.out
