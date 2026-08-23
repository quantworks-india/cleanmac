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


def test_window_centers_on_selection():
    """_visible_window returns a window around idx, capped by total."""
    w = au._visible_window(idx=5, total=20, height=7)
    assert w == (2, 9)  # 7 rows: idx at center-ish
    assert (w[1] - w[0]) == 7


def test_window_clamps_to_top():
    assert au._visible_window(idx=0, total=20, height=5) == (0, 5)


def test_window_clamps_to_bottom():
    assert au._visible_window(idx=19, total=20, height=5) == (15, 20)


def test_window_smaller_than_height():
    assert au._visible_window(idx=1, total=3, height=10) == (0, 3)


def test_render_block_never_clears_screen():
    """The picker must not emit full-screen wipe escapes (ESC[H ESC[J)."""
    apps = ["Alpha", "Beta", "Gamma"]
    block = au._render_rows(apps, idx=1, start=0, end=3)
    assert "\x1b[H" not in block
    assert "\x1b[J" not in block
    assert "▸ Beta" in block


def test_render_rows_uses_crlf_in_raw_mode():
    """Bare \\n in raw mode stairs the list; lines must end with CR+LF."""
    block = au._render_rows(["Alpha", "Beta"], idx=0, start=0, end=2)
    assert "\r\n" in block
    assert "\n" not in block.replace("\r\n", "")


def test_picker_paint_rewinds_previous_frame():
    """A redraw must move the cursor up, not append another copy."""
    text, n = au._picker_paint(["A", "B"], idx=0, start=0, end=2, prev_lines=3)
    assert "\x1b[3A" in text
    assert "\x1b[H" not in text
    assert "\x1b[2J" not in text
    assert n >= 2


def test_render_block_shows_window_only():
    """Only the visible window rows are in the block, highlighted marker."""
    apps = [f"App{i}" for i in range(20)]
    block = au._render_rows(apps, idx=5, start=2, end=9)
    assert "App2" in block and "App8" in block
    assert "App0" not in block and "App9" not in block
    assert "▸ App5" in block


def test_render_block_shows_query_filter():
    """When a filter is set, only matching apps are shown."""
    apps = ["Alpha", "Beta", "Alpaca", "Gamma"]
    filtered = [a for a in apps if "al" in a.lower()]
    block = au._render_rows(filtered, idx=0, start=0, end=len(filtered))
    assert "Alpha" in block and "Alpaca" in block
    assert "Beta" not in block and "Gamma" not in block
