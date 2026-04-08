from unittest.mock import patch

from keyring.errors import KeyringError

from discord_cli.credential import load_token, store_token


def test_store_token_calls_keyring_set_password() -> None:
    with patch("discord_cli.credential.keyring") as mock_keyring:
        result = store_token("my-token")

    assert result is True
    mock_keyring.set_password.assert_called_once_with(
        "discord-cli", "discord-cli", "my-token"
    )


def test_load_token_calls_keyring_get_password() -> None:
    with patch("discord_cli.credential.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = "my-token"
        result = load_token()

    assert result == "my-token"
    mock_keyring.get_password.assert_called_once_with("discord-cli", "discord-cli")


def test_store_token_returns_false_on_keyring_error() -> None:
    with patch(
        "discord_cli.credential.keyring.set_password",
        side_effect=KeyringError("no backend"),
    ):
        assert store_token("my-token") is False


def test_load_token_returns_none_on_keyring_error() -> None:
    with patch(
        "discord_cli.credential.keyring.get_password",
        side_effect=KeyringError("no backend"),
    ):
        assert load_token() is None
