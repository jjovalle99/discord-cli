import asyncio
from typing import Any

import httpx

from discord_cli.output import write_status

BASE_URL = "https://discord.com/api/v10"
_ALLOWED_HOSTS = ("cdn.discordapp.com", "media.discordapp.net")
_MAX_RETRIES = 5
_MAX_RETRY_DELAY = 60


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
        self._total_retries = 0
        self._min_remaining: int | None = None
        self._max_reset_after: float | None = None

    async def _request(
        self, path: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        response = await self._http.get(path, params=params)

        retries = 0
        while response.status_code == 429 and retries < _MAX_RETRIES:
            retry_after = min(float(response.json().get("retry_after", 1)), _MAX_RETRY_DELAY)
            write_status(f"[rate-limit] 429 on GET {path} — retrying in {retry_after}s")
            await asyncio.sleep(retry_after)
            retries += 1
            response = await self._http.get(path, params=params)

        self._total_retries += retries
        self._update_rate_limit_headers(response)

        if response.status_code >= 400:
            raise DiscordAPIError(response.status_code, response.json())

        return response

    def _update_rate_limit_headers(self, response: httpx.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            val = int(remaining)
            if self._min_remaining is None or val < self._min_remaining:
                self._min_remaining = val
        reset_after = response.headers.get("X-RateLimit-Reset-After")
        if reset_after is not None:
            val_f = float(reset_after)
            if self._max_reset_after is None or val_f > self._max_reset_after:
                self._max_reset_after = val_f

    @property
    def rate_limit_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {"retries": self._total_retries}
        if self._min_remaining is not None:
            stats["remaining"] = self._min_remaining
        if self._max_reset_after is not None:
            stats["reset_after"] = self._max_reset_after
        return stats

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
