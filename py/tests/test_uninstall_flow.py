"""Tests for the top-level `cleanmac uninstall` flow (single y/N gate)."""

from __future__ import annotations


import pytest

from maccleaner import app_uninstaller as au
from maccleaner import uninstall as uninstall_mod
from maccleaner.core import Auditor, Deleter, Reporter


@pytest.fixture
def leftover_only(tmp_path, monkeypatch):
    """Sandbox home with a leftover dir but NO live .app."""
    home = tmp_path / "home"
    (home / "Library" / "Application Support").mkdir(parents=True)
    (home / "Library" / "Application Support" / "MyApp").mkdir(parents=True)
    (home / "Library" / "Application Support" / "MyApp" / "data.bin").write_bytes(
        b"x" * 16
    )
    monkeypatch.setenv("CLEANMAC_HOME", str(home))
    monkeypatch.setattr(au, "_candidate_dirs", lambda: [])
    return home


def _run_with_confirm(target, confirm_resp, capsys):
    """Drive uninstall.run() with a stubbed yes/no answer."""
    args = type("A", (), {"target": target})()
    aud = Auditor("uninstall-flow", mode="live")
    d = Deleter(aud, commit=False, confirm_fn=lambda _p: True)
    reporter = Reporter()
    import maccleaner.uninstall as u

    real_confirm = u.confirm
    u.confirm = lambda _prompt: confirm_resp
    try:
        rc = u.run(args, d, None, reporter)
    finally:
        u.confirm = real_confirm
        aud.close()
    return rc


def test_confirm_no_deletes_nothing(leftover_only, monkeypatch, capsys):
    """Answering n leaves every leftover file untouched."""
    monkeypatch.setattr(uninstall_mod, "resolve", lambda q: au.UninstallTarget(
        name="MyApp", bundle_id="com.example.myapp", path="", app_installed=False, query=q,
    ))
    rc = _run_with_confirm("MyApp", False, capsys)
    assert rc == 0
    assert (leftover_only / "Library" / "Application Support" / "MyApp").exists()


def test_confirm_yes_deletes_leftovers(leftover_only, monkeypatch, capsys):
    """Answering y deletes the leftover dir (single gate, no --commit flag)."""
    monkeypatch.setattr(uninstall_mod, "resolve", lambda q: au.UninstallTarget(
        name="MyApp", bundle_id="com.example.myapp", path="", app_installed=False, query=q,
    ))
    rc = _run_with_confirm("MyApp", True, capsys)
    assert rc == 0
    assert not (leftover_only / "Library" / "Application Support" / "MyApp").exists()


def test_run_rejects_missing_target():
    """No target and not a TTY -> clear usage error, exit 2, nothing crashes."""
    args = type("A", (), {"target": None})()
    aud = Auditor("uninstall-missing", mode="dry-run")
    d = Deleter(aud, commit=False)
    reporter = Reporter()
    import maccleaner.uninstall as u

    rc = u.run(args, d, None, reporter)
    assert rc == 2
    aud.close()


def test_quarantine_system_plist_uses_sudo(tmp_path, monkeypatch):
    """A LaunchDaemon must be moved via sudo, not shutil as the user."""
    src = tmp_path / "Library" / "LaunchDaemons" / "us.zoom.ZoomDaemon.plist"
    src.parent.mkdir(parents=True)
    src.write_text("plist")
    home = tmp_path / "home"
    monkeypatch.setenv("CLEANMAC_HOME", str(home))
    cmds: list[list[str]] = []

    class FakeSudo:
        def run(self, args):
            cmds.append(list(args))
            dest = home / "Library" / "LaunchAgents-disabled" / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if args and args[0] == "mv":
                src.rename(dest)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    au._quarantine_launch(
        "us.zoom.ZoomDaemon",
        str(src),
        type("D", (), {"commit": True})(),
        FakeSudo(),
        Reporter(),
    )
    assert any(c[:1] == ["mv"] for c in cmds)
    assert not src.exists()


def test_quarantine_system_plist_does_not_crash_without_sudo(tmp_path, monkeypatch):
    """Permission denied on a system plist must not traceback."""
    src = tmp_path / "Library" / "LaunchDaemons" / "com.example.d.plist"
    src.parent.mkdir(parents=True)
    src.write_text("plist")
    monkeypatch.setenv("CLEANMAC_HOME", str(tmp_path / "home"))

    class BoomSudo:
        def run(self, args):
            raise PermissionError("denied")

    au._quarantine_launch(
        "com.example.d",
        str(src),
        type("D", (), {"commit": True})(),
        BoomSudo(),
        Reporter(),
    )
    assert src.exists()
