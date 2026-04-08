import os
from pathlib import Path

import pytest

from discord_cli.cache import make_cache_key, read_cache, run_with_cache, write_cache


def test_cache_write_read_and_expiry(tmp_path: Path) -> None:
    cache_dir = tmp_path
    key = "abc123"

    assert read_cache(key, ttl=300, cache_dir=cache_dir) is None

    write_cache(key, "hello world\n", cache_dir=cache_dir)
    assert read_cache(key, ttl=300, cache_dir=cache_dir) == "hello world\n"

    cache_file = cache_dir / key
    old_mtime = cache_file.stat().st_mtime - 301
    os.utime(cache_file, (old_mtime, old_mtime))
    assert read_cache(key, ttl=300, cache_dir=cache_dir) is None


def test_make_cache_key_deterministic_and_strips_flags() -> None:
    argv1 = ["discord-cli", "read", "channel", "123", "--limit", "50"]
    argv2 = ["discord-cli", "read", "channel", "123", "--limit", "50"]
    assert make_cache_key(argv1) == make_cache_key(argv2)

    argv3 = ["discord-cli", "read", "channel", "456", "--limit", "50"]
    assert make_cache_key(argv1) != make_cache_key(argv3)

    argv_with_token = [
        "discord-cli", "read", "channel", "123", "--limit", "50",
        "--token", "secret", "--cache-ttl", "300", "--no-cache",
    ]
    assert make_cache_key(argv_with_token) == make_cache_key(argv1)

    assert make_cache_key(argv1, token="tok_a") != make_cache_key(argv1, token="tok_b")
    assert make_cache_key(argv1, token="tok_a") == make_cache_key(argv1, token="tok_a")


def test_run_with_cache_caches_on_miss_and_replays_on_hit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path
    argv = ["discord-cli", "list", "servers"]
    call_count = 0

    def fn() -> None:
        nonlocal call_count
        call_count += 1
        print('["server1"]')

    run_with_cache(fn, argv=argv, cache_ttl=300, no_cache=False, token="t", cache_dir=cache_dir)
    first_out = capsys.readouterr().out
    assert first_out == '["server1"]\n'
    assert call_count == 1

    run_with_cache(fn, argv=argv, cache_ttl=300, no_cache=False, token="t", cache_dir=cache_dir)
    second_out = capsys.readouterr().out
    assert second_out == '["server1"]\n'
    assert call_count == 1


def test_run_with_cache_no_cache_bypasses_read_and_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path
    argv = ["discord-cli", "list", "servers"]
    call_count = 0

    def fn() -> None:
        nonlocal call_count
        call_count += 1
        print(f'["v{call_count}"]')

    run_with_cache(fn, argv=argv, cache_ttl=300, no_cache=True, token="t", cache_dir=cache_dir)
    out = capsys.readouterr().out
    assert out == '["v1"]\n'
    assert call_count == 1
    assert not list(cache_dir.iterdir())

    run_with_cache(fn, argv=argv, cache_ttl=300, no_cache=True, token="t", cache_dir=cache_dir)
    out = capsys.readouterr().out
    assert out == '["v2"]\n'
    assert call_count == 2


def test_run_with_cache_survives_cache_write_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "readonly"
    cache_dir.mkdir()
    cache_dir.chmod(0o444)

    def fn() -> None:
        print('["data"]')

    run_with_cache(
        fn, argv=["discord-cli", "list", "servers"],
        cache_ttl=300, no_cache=False, token="t", cache_dir=cache_dir,
    )
    out = capsys.readouterr().out
    assert out == '["data"]\n'

    cache_dir.chmod(0o755)
