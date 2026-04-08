import json
import os
import tempfile
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "discord-cli" / "config.json"


def save_config(
    *,
    username: str,
    token: str | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str] = {"username": username}
    if token:
        data["token"] = token
    fd = tempfile.mkstemp(dir=config_path.parent, prefix=".config-", suffix=".tmp")
    tmp_path = Path(fd[1])
    try:
        with os.fdopen(fd[0], "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.chmod(0o600)
        os.replace(tmp_path, config_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    try:
        return json.loads(config_path.read_text())  # type: ignore[no-any-return]
    except FileNotFoundError:
        return {}
