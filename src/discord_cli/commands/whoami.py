from discord_cli.auth.errors import AuthError
from discord_cli.client import DiscordClient
from discord_cli.output import write_success
from discord_cli.validation import validate_token


async def whoami(client: DiscordClient, *, token_source: str) -> None:
    try:
        user_info = await validate_token(client)
    except AuthError:
        write_success({
            "token_source": token_source,
            "token_valid": False,
        })
        raise SystemExit(1)

    write_success({
        "id": user_info["id"],
        "username": user_info["username"],
        "global_name": user_info.get("global_name"),
        "token_source": token_source,
        "token_valid": True,
    })
