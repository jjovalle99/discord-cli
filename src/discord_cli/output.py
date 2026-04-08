import json
import sys
from typing import Any


def write_success(data: Any) -> None:  # noqa: ANN401
    print(json.dumps(data, indent=2))


def write_error(error: str, message: str) -> None:
    print(json.dumps({"error": error, "message": message}), file=sys.stderr)


_quiet = False


def set_quiet(value: bool) -> None:
    global _quiet  # noqa: PLW0603
    _quiet = value


def write_status(message: str) -> None:
    if not _quiet:
        print(message, file=sys.stderr)
