"""Tests for the terminal app-picker key handling (stdlib termios)."""

from __future__ import annotations


from maccleaner import app_uninstaller as au


def test_cursor_down_moves_forward():
    assert au._move_cursor(0, "down", 5) == 1
    assert au._move_cursor(4, "down", 5) == 4  # clamps at last


def test_cursor_up_moves_back():
    assert au._move_cursor(3, "up", 5) == 2
    assert au._move_cursor(0, "up", 5) == 0  # clamps at first


def test_cursor_stays_put_on_other_keys():
    assert au._move_cursor(2, "j", 5) == 2


def test_key_from_escape_sequences():
    # Up arrow: ESC [ A
    assert au._parse_key(b"\x1b[A") == "up"
    # Down arrow: ESC [ B
    assert au._parse_key(b"\x1b[B") == "down"
    # Enter
    assert au._parse_key(b"\r") == "enter"
    assert au._parse_key(b"\n") == "enter"
    # q / ctrl-c cancel
    assert au._parse_key(b"q") == "cancel"
    assert au._parse_key(b"\x03") == "cancel"
    # Plain letter -> itself
    assert au._parse_key(b"j") == "j"


def test_resolve_pick_pure():
    """Arrow-key navigation picks the highlighted entry."""
    apps = ["Alpha", "Beta", "Gamma"]
    idx = 0
    idx = au._move_cursor(idx, au._parse_key(b"\x1b[B"), 3)  # down -> 1
    idx = au._move_cursor(idx, au._parse_key(b"\x1b[B"), 3)  # down -> 2
    assert apps[idx] == "Gamma"
    idx = au._move_cursor(idx, au._parse_key(b"\x1b[A"), 3)  # up -> 1
    assert apps[idx] == "Beta"
