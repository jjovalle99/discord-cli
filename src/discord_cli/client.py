import asyncio
import sys
from typing import Any

import httpx

BASE_URL = "https://discord.com/api/v10"
_ALLOWED_HOSTS = ("cdn.discordapp.com", "media.discordapp.net")


class DiscordAPIError(Exception):
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Discord API error {status}: {body}")


class DiscordClient:
    def __init__(
        self,
        *,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        cdn_transport: httpx.AsyncBaseTransport | None = None,
        super_properties: str | None = None,
    ) -> None:
        headers: dict[str, str] = {"Authorization": token}
        if super_properties is not None:
            from discord_cli.super_properties import get_fingerprint

            headers["X-Super-Properties"] = super_properties
            headers["User-Agent"] = get_fingerprint().user_agent
        api_kwargs: dict[str, Any] = {
            "base_url": BASE_URL,
            "headers": headers,
        }
        cdn_kwargs: dict[str, Any] = {}
        if transport is not None:
            api_kwargs["transport"] = transport
        if cdn_transport is not None:
            cdn_kwargs["transport"] = cdn_transport
        self._http = httpx.AsyncClient(**api_kwargs)
        self._cdn = httpx.AsyncClient(**cdn_kwargs)

    async def _request(
        self, path: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        response = await self._http.get(path, params=params)

        if response.status_code == 429:
            retry_after = min(float(response.json().get("retry_after", 1)), 60)
            print(f"Rate limited. Waiting {retry_after}s...", file=sys.stderr)
            await asyncio.sleep(retry_after)
            response = await self._http.get(path, params=params)

        if response.status_code >= 400:
            raise DiscordAPIError(response.status_code, response.json())

        return response

    async def api_get(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        return (await self._request(path, params)).json()  # type: ignore[no-any-return]

    async def api_get_list(
        self, path: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        return (await self._request(path, params)).json()  # type: ignore[no-any-return]

    @staticmethod
    def _validate_url(url: str) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host not in _ALLOWED_HOSTS:
            msg = f"Refusing to fetch URL with host '{host}' — only Discord CDN allowed"
            raise ValueError(msg)

    async def fetch_url_bytes(self, url: str) -> bytes:
        self._validate_url(url)
        response = await self._cdn.get(url)
        response.raise_for_status()
        return response.content

    async def close(self) -> None:
        await self._http.aclose()
        await self._cdn.aclose()

    async def __aenter__(self) -> "DiscordClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
