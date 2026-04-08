import keyring
from keyring.errors import KeyringError

SERVICE = "discord-cli"
ACCOUNT = "discord-cli"


def store_token(token: str) -> bool:
    try:
        keyring.set_password(SERVICE, ACCOUNT, token)
        return True
    except KeyringError:
        return False


def load_token() -> str | None:
    try:
        return keyring.get_password(SERVICE, ACCOUNT)
    except KeyringError:
        return None
