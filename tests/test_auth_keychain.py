from unittest.mock import patch

from discord_cli.auth.keychain import get_macos_password


def test_get_macos_password_calls_security_cli() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "my-secret\n"
        result = get_macos_password("Discord Safe Storage", "Discord")

    assert result == "my-secret"
    mock_run.assert_called_once_with(
        [
            "security",
            "find-generic-password",
            "-s",
            "Discord Safe Storage",
            "-a",
            "Discord",
            "-w",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
