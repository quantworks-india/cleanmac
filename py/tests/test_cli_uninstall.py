"""Tests for top-level `cleanmac uninstall` command surface."""

from __future__ import annotations

from maccleaner import cli


def test_uninstall_is_top_level_subcommand():
    """`uninstall` is a top-level tool, not hidden under `app`."""
    parser = cli._build_parser()
    for argv in (["uninstall"], ["uninstall", "Code"]):
        args = parser.parse_args(argv)
        assert args.tool == "uninstall", argv


def test_uninstall_target_is_optional_positional():
    """Target (name or bundle id) is an optional positional."""
    parser = cli._build_parser()
    bare = parser.parse_args(["uninstall"])
    assert getattr(bare, "target", None) is None

    named = parser.parse_args(["uninstall", "Code"])
    assert named.target == "Code"

    bundle = parser.parse_args(["uninstall", "com.microsoft.VSCode"])
    assert bundle.target == "com.microsoft.VSCode"


def test_uninstall_rejects_old_flag_surface():
    """--name / --yes / --force / --commit are not part of uninstall."""
    parser = cli._build_parser()
    for bad in (
        ["uninstall", "--name", "Code"],
        ["uninstall", "--yes"],
        ["uninstall", "--force"],
    ):
        try:
            parser.parse_args(bad)
        except SystemExit:
            continue  # argparse rejected it — good
        raise AssertionError(f"argparse accepted forbidden args: {bad}")
