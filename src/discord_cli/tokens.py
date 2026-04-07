import os
from pathlib import Path

from discord_cli.config import DEFAULT_CONFIG_PATH, load_config


def resolve_token(
    *, flag_token: str | None = None, config_path: Path = DEFAULT_CONFIG_PATH
) -> str:
    if flag_token:
        return flag_token

    env_token = os.environ.get("DISCORD_TOKEN")
    if env_token:
        return env_token

    config = load_config(config_path)
    token = config.get("token")
    if token:
        return token

    msg = "No token found. Run 'discord-cli auth', set DISCORD_TOKEN, or pass --token."
    raise SystemExit(msg)
