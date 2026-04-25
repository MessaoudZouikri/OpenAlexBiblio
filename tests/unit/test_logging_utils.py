"""
Unit tests for src/utils/logging_utils.py

Covers: setup_logger, AuditTrail.__init__, record, _flush (atomic write),
finalize.
"""

import json
import logging
from pathlib import Path

import pytest

from src.utils.logging_utils import AuditTrail, setup_logger


# ── setup_logger ───────────────────────────────────────────────────────────────


class TestSetupLogger:
    @pytest.mark.unit
    def test_returns_logger_instance(self, tmp_path):
        logger = setup_logger("test_agent", log_dir=str(tmp_path))
        assert isinstance(logger, logging.Logger)

    @pytest.mark.unit
    def test_logger_name_preserved(self, tmp_path):
        logger = setup_logger("my_agent", log_dir=str(tmp_path))
        assert logger.name == "my_agent"

    @pytest.mark.unit
    def test_log_file_created(self, tmp_path):
        setup_logger("data_collector", log_dir=str(tmp_path))
        assert (tmp_path / "data_collector.log").exists()

    @pytest.mark.unit
    def test_log_dir_created_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b" / "logs"
        setup_logger("agent", log_dir=str(nested))
        assert nested.is_dir()

    @pytest.mark.unit
    def test_debug_level_accepted(self, tmp_path):
        logger = setup_logger("dbg_agent", log_dir=str(tmp_path), level="DEBUG")
        assert logger.level == logging.DEBUG

    @pytest.mark.unit
    def test_warning_level_accepted(self, tmp_path):
        logger = setup_logger("warn_agent", log_dir=str(tmp_path), level="WARNING")
        assert logger.level == logging.WARNING

    @pytest.mark.unit
    def test_invalid_level_defaults_to_info(self, tmp_path):
        logger = setup_logger("agent", log_dir=str(tmp_path), level="NONSENSE")
        assert logger.level == logging.INFO

    @pytest.mark.unit
    def test_console_false_no_stream_handler(self, tmp_path):
        logger = setup_logger("quiet_agent", log_dir=str(tmp_path), console=False)
        stream_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 0

    @pytest.mark.unit
    def test_console_true_has_stream_handler(self, tmp_path):
        logger = setup_logger("verbose_agent", log_dir=str(tmp_path), console=True)
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    @pytest.mark.unit
    def test_reinitialisation_does_not_duplicate_handlers(self, tmp_path):
        setup_logger("dup_agent", log_dir=str(tmp_path))
        logger = setup_logger("dup_agent", log_dir=str(tmp_path))
        # After second call, handlers should be cleared and reset — not doubled
        assert len(logger.handlers) <= 2  # at most: 1 file + 1 console

    @pytest.mark.unit
    def test_writes_to_log_file(self, tmp_path):
        logger = setup_logger("write_agent", log_dir=str(tmp_path), console=False)
        logger.info("Hello from test")
        for h in logger.handlers:
            h.flush()
        content = (tmp_path / "write_agent.log").read_text()
        assert "Hello from test" in content


# ── AuditTrail ────────────────────────────────────────────────────────────────


class TestAuditTrail:
    @pytest.mark.unit
    def test_init_creates_log_dir(self, tmp_path):
        log_dir = str(tmp_path / "audit_logs")
        AuditTrail("run001", log_dir=log_dir)
        assert Path(log_dir).is_dir()

    @pytest.mark.unit
    def test_trail_path_uses_run_id(self, tmp_path):
        trail = AuditTrail("abc123", log_dir=str(tmp_path))
        assert "abc123" in str(trail.trail_path)

    @pytest.mark.unit
    def test_entries_empty_on_init(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        assert trail.entries == []

    @pytest.mark.unit
    def test_record_appends_entry(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        assert len(trail.entries) == 1

    @pytest.mark.unit
    def test_record_stores_step_and_status(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("data_collection", "success")
        entry = trail.entries[0]
        assert entry["step"] == "data_collection"
        assert entry["status"] == "success"

    @pytest.mark.unit
    def test_record_stores_optional_fields(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record(
            "clean",
            "success",
            inputs={"file": "raw.parquet"},
            outputs={"file": "clean.parquet"},
            metrics={"rows": 100},
            duration_s=2.5,
        )
        entry = trail.entries[0]
        assert entry["inputs"] == {"file": "raw.parquet"}
        assert entry["outputs"] == {"file": "clean.parquet"}
        assert entry["metrics"] == {"rows": 100}
        assert entry["duration_s"] == 2.5

    @pytest.mark.unit
    def test_record_stores_error_field(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("fail_step", "failure", error="Something went wrong")
        assert trail.entries[0]["error"] == "Something went wrong"

    @pytest.mark.unit
    def test_record_flushes_to_disk(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        assert trail.trail_path.exists()

    @pytest.mark.unit
    def test_flush_writes_valid_json(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        content = json.loads(trail.trail_path.read_text())
        assert content["run_id"] == "r1"
        assert isinstance(content["entries"], list)

    @pytest.mark.unit
    def test_flush_marks_status_as_running(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        content = json.loads(trail.trail_path.read_text())
        assert content["overall_status"] == "running"

    @pytest.mark.unit
    def test_flush_atomic_no_tmp_leftover(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        tmp_file = Path(str(trail.trail_path) + ".tmp")
        assert not tmp_file.exists()

    @pytest.mark.unit
    def test_multiple_records_accumulate(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        trail.record("step2", "failure", error="oops")
        trail.record("step3", "warning")
        assert len(trail.entries) == 3
        content = json.loads(trail.trail_path.read_text())
        assert len(content["entries"]) == 3

    @pytest.mark.unit
    def test_finalize_writes_overall_status(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        trail.finalize("completed")
        content = json.loads(trail.trail_path.read_text())
        assert content["overall_status"] == "completed"

    @pytest.mark.unit
    def test_finalize_adds_finished_at(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        trail.finalize("completed")
        content = json.loads(trail.trail_path.read_text())
        assert "finished_at" in content

    @pytest.mark.unit
    def test_finalize_preserves_all_entries(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        trail.record("step2", "success")
        trail.finalize("completed")
        content = json.loads(trail.trail_path.read_text())
        assert len(content["entries"]) == 2

    @pytest.mark.unit
    def test_entry_has_timestamp(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        assert "timestamp" in trail.entries[0]

    @pytest.mark.unit
    def test_empty_inputs_outputs_default_to_empty_dicts(self, tmp_path):
        trail = AuditTrail("r1", log_dir=str(tmp_path))
        trail.record("step1", "success")
        entry = trail.entries[0]
        assert entry["inputs"] == {}
        assert entry["outputs"] == {}
        assert entry["metrics"] == {}
