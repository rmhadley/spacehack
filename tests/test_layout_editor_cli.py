"""Tests for the headless layout editor command."""

from __future__ import annotations

from pathlib import Path

from tools.layout_editor.__main__ import main


_DATA = Path(__file__).resolve().parent.parent / "src" / "spacehack" / "data"


def test_validate_command_accepts_one_shipped_asset(capsys):
    result = main([
        "--validate",
        str(_DATA / "landmarks" / "mars_signal_door.layout"),
    ])

    assert result == 0
    assert "OK" in capsys.readouterr().out


def test_validate_command_reports_missing_asset(capsys, tmp_path):
    missing = tmp_path / "missing.layout"

    result = main(["--validate", str(missing)])

    assert result == 1
    assert "ERROR" in capsys.readouterr().out


def test_validate_command_checks_all_shipped_assets(capsys):
    result = main(["--validate"])

    output = capsys.readouterr().out
    assert result == 0
    assert output.count("OK ") == 4
