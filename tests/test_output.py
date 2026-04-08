import json

import pytest

from discord_cli.output import write_error, write_success


def test_write_success_prints_json_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_success({"id": "123", "name": "test"})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"id": "123", "name": "test"}
    assert captured.err == ""


def test_write_error_prints_json_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    write_error("not_found", "Channel not found")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": "not_found",
        "message": "Channel not found",
    }


def test_write_status_prints_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.output import set_quiet, write_status

    set_quiet(False)
    write_status("Connecting...")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Connecting...\n"


def test_write_status_suppressed_when_quiet(capsys: pytest.CaptureFixture[str]) -> None:
    from discord_cli.output import set_quiet, write_status

    set_quiet(True)
    write_status("Connecting...")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    set_quiet(False)
