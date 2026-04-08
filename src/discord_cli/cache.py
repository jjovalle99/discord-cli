import hashlib
import io
import sys
import time
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path

_STRIPPED_FLAGS = {"--token", "--cache-ttl", "--no-cache"}

DEFAULT_CACHE_DIR = Path.home() / ".config" / "discord-cli" / "cache"


def make_cache_key(argv: list[str], token: str = "") -> str:
    filtered: list[str] = []
    skip_next = False
    for arg in argv:
        if skip_next:
            skip_next = False
            continue
        if arg in _STRIPPED_FLAGS:
            if arg != "--no-cache":
                skip_next = True
            continue
        filtered.append(arg)
    raw = "\0".join(filtered)
    if token:
        raw += "\0" + token
    return hashlib.sha256(raw.encode()).hexdigest()


def write_cache(key: str, data: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / key).write_text(data)


def read_cache(key: str, ttl: int, cache_dir: Path = DEFAULT_CACHE_DIR) -> str | None:
    path = cache_dir / key
    try:
        if (time.time() - path.stat().st_mtime) < ttl:
            return path.read_text()
    except (FileNotFoundError, OSError):
        pass
    return None


def run_with_cache(
    fn: Callable[[], object],
    *,
    argv: list[str],
    cache_ttl: int,
    no_cache: bool,
    token: str = "",
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> None:
    if cache_ttl <= 0:
        fn()
        return

    key = make_cache_key(argv, token)

    if not no_cache:
        cached = read_cache(key, cache_ttl, cache_dir)
        if cached is not None:
            print(cached, end="")
            return

    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    output = buf.getvalue()
    sys.stdout.write(output)
    if output and not no_cache:
        try:
            write_cache(key, output, cache_dir)
        except OSError:
            pass
