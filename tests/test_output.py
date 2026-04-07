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
