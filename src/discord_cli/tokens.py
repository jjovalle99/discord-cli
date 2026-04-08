import os
from pathlib import Path
from typing import Literal, NamedTuple

from discord_cli.config import DEFAULT_CONFIG_PATH, load_config
from discord_cli.credential import load_token

TokenSource = Literal["flag", "environment_variable", "config_file", "keyring"]


class ResolvedToken(NamedTuple):
    value: str
    source: TokenSource


def resolve_token(
    *, flag_token: str | None = None, config_path: Path = DEFAULT_CONFIG_PATH
) -> ResolvedToken:
    if flag_token:
        return ResolvedToken(flag_token, "flag")

    env_token = os.environ.get("DISCORD_TOKEN")
    if env_token:
        return ResolvedToken(env_token, "environment_variable")

    config = load_config(config_path)
    token = config.get("token")
    if token:
        return ResolvedToken(token, "config_file")

    keyring_token = load_token()
    if keyring_token:
        return ResolvedToken(keyring_token, "keyring")

    msg = "No token found. Run 'discord-cli auth', set DISCORD_TOKEN, or pass --token."
    raise SystemExit(msg)
