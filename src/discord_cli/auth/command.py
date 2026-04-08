import platform
from pathlib import Path

import httpx

from discord_cli.auth.decrypt import decrypt_token, is_encrypted
from discord_cli.auth.errors import AuthError
from discord_cli.auth.extract import extract_token_from_leveldb
from discord_cli.auth.keychain import get_macos_password
from discord_cli.client import DiscordClient
from discord_cli.config import DEFAULT_CONFIG_PATH, save_config
from discord_cli.credential import store_token
from discord_cli.output import set_quiet, write_status, write_success
from discord_cli.validation import validate_token

DISCORD_LEVELDB_PATHS = {
    "Darwin": Path.home()
    / "Library"
    / "Application Support"
    / "discord"
    / "Local Storage"
    / "leveldb",
    "Linux": Path.home() / ".config" / "discord" / "Local Storage" / "leveldb",
}

MACOS_KEYCHAIN_SERVICE = "discord Safe Storage"
MACOS_KEYCHAIN_ACCOUNT = "discord Key"
MACOS_ITERATIONS = 1003
LINUX_PASSWORD = "peanuts"
LINUX_ITERATIONS = 1


async def run_auth(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    is_macos: bool | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    quiet: bool = False,
) -> None:
    set_quiet(quiet)
    os_name = platform.system()
    if is_macos is None:
        is_macos = os_name == "Darwin"

    leveldb_path = DISCORD_LEVELDB_PATHS.get(os_name)
    if not leveldb_path:
        raise AuthError(
            f"Unsupported platform: {os_name}. Only macOS and Linux are supported."
        )

    if not leveldb_path.exists():
        raise AuthError(
            f"Discord LevelDB not found at {leveldb_path}. Is the Discord desktop app installed?"
        )

    raw_token = extract_token_from_leveldb(leveldb_path)
    if not raw_token:
        raise AuthError("No token found in Discord local storage.")

    if is_encrypted(raw_token):
        if is_macos:
            write_status(
                "Accessing macOS Keychain for Discord token decryption "
                "(system password prompt incoming)"
            )
            password = get_macos_password(
                MACOS_KEYCHAIN_SERVICE, MACOS_KEYCHAIN_ACCOUNT
            )
            iterations = MACOS_ITERATIONS
        else:
            password = LINUX_PASSWORD
            iterations = LINUX_ITERATIONS

        token = decrypt_token(
            raw_token, password=password, iterations=iterations
        )
    else:
        token = raw_token

    async with DiscordClient(token=token, transport=transport) as client:
        user_info = await validate_token(client)

    username = user_info.get("username", "unknown")

    if store_token(token):
        save_config(username=username, config_path=config_path)
        credential_storage = "keyring"
    else:
        write_status(
            "Warning: no system keyring available, storing token in plaintext config file"
        )
        save_config(token=token, username=username, config_path=config_path)
        credential_storage = "plaintext_config"

    write_status(f"Authenticated as {username}")
    write_success({
        "id": user_info.get("id"),
        "username": username,
        "credential_storage": credential_storage,
    })
