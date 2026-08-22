"""Tests for cli — argument parsing and subcommand dispatch."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from maccleaner import cli


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Redirect state dir for Auditor; sandbox home for safety."""
    from maccleaner import core

    monkeypatch.setattr(core, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(core, "AUDIT_DIR", tmp_path / "state" / "audit")
    monkeypatch.setattr(core, "LOG_DIR", tmp_path / "state" / "logs")
    monkeypatch.setenv("CLEANMAC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CLEANMAC_HOME", str(tmp_path))
    return tmp_path


def test_main_help_exits_0(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_main_dispatches_to_app(capsys):
    with patch("maccleaner.app_uninstaller.run", return_value=0) as mock_run:
        rc = cli.main(["--dry-run", "app", "list"])
    assert rc == 0
    mock_run.assert_called_once()


def test_main_dispatches_to_dup():
    with patch("maccleaner.duplicates.run", return_value=0) as mock_run:
        rc = cli.main(["--dry-run", "dup", "scan", "/tmp"])
    assert rc == 0
    mock_run.assert_called_once()


def test_main_dispatches_to_disk():
    with patch("maccleaner.disk_analyzer.run", return_value=0) as mock_run:
        rc = cli.main(["--dry-run", "disk", "top"])
    assert rc == 0
    mock_run.assert_called_once()


def test_main_dispatches_to_mem():
    with patch("maccleaner.memory.run", return_value=0) as mock_run:
        rc = cli.main(["--dry-run", "mem", "heavy"])
    assert rc == 0
    mock_run.assert_called_once()


def test_main_dispatches_to_hidden():
    with patch("maccleaner.hidden_files.run", return_value=0) as mock_run:
        rc = cli.main(["--dry-run", "hidden", "show"])
    assert rc == 0
    mock_run.assert_called_once()


def test_main_commit_mode_creates_live_auditor(monkeypatch):
    captured_mode: list[str] = []

    class CaptureAuditor:
        def __init__(self, run_id, mode="dry-run"):
            captured_mode.append(mode)

        def close(self):
            pass

    monkeypatch.setattr(cli, "Auditor", CaptureAuditor)
    with patch("maccleaner.hidden_files.run", return_value=0):
        cli.main(["--commit", "hidden", "show"])
    assert captured_mode == ["live"]


def test_main_unknown_tool_returns_2():
    # argparse with required subparsers rejects unknown tools at parse time
    with pytest.raises(SystemExit) as exc:
        cli.main(["--dry-run", "nonexistent"])
    assert exc.value.code == 2


def test_main_propagates_module_return_code():
    with patch("maccleaner.hidden_files.run", return_value=7):
        rc = cli.main(["--dry-run", "hidden", "show"])
    assert rc == 7
