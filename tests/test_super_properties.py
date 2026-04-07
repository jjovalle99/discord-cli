import base64
import json
from pathlib import Path

from discord_cli.super_properties import build_super_properties


def test_build_super_properties_returns_valid_base64_json() -> None:
    result = build_super_properties(build_number=300000)
    decoded = json.loads(base64.b64decode(result))

    assert decoded["client_build_number"] == 300000
    assert decoded["os"] in ("Mac OS X", "Linux", "Windows")
    assert decoded["release_channel"] == "stable"
    assert decoded["browser"] == "Discord Client"
    assert decoded["client_event_source"] is None
    assert "browser_user_agent" in decoded
    assert "browser_version" in decoded
    assert "Mozilla/5.0" in decoded["browser_user_agent"]


def test_fingerprint_is_coherent_across_headers() -> None:
    from discord_cli.super_properties import get_fingerprint

    fp = get_fingerprint()
    sp = build_super_properties(build_number=300000)
    decoded = json.loads(base64.b64decode(sp))

    assert decoded["browser_user_agent"] == fp.user_agent
    assert decoded["os"] == fp.os
    assert decoded["os_version"] == fp.os_version
    assert decoded["browser_version"] == fp.browser_version

    if "Macintosh" in fp.user_agent:
        assert decoded["os"] == "Mac OS X"
    elif "Linux" in fp.user_agent:
        assert decoded["os"] == "Linux"
    elif "Windows" in fp.user_agent:
        assert decoded["os"] == "Windows"


def test_fetch_build_number_parses_js_asset() -> None:
    from unittest.mock import patch, MagicMock

    from discord_cli.super_properties import fetch_build_number

    app_html = '<script src="/assets/abc123.js"></script><script src="/assets/def456.js"></script>'
    js_with_build = "some code Build Number: 350000, Version Hash: abc123"

    mock_responses = {
        "https://discord.com/app": MagicMock(text=app_html),
        "https://discord.com/assets/def456.js": MagicMock(text=js_with_build),
    }

    def mock_get(url: str, **_kwargs: object) -> MagicMock:
        return mock_responses[url]

    with patch("discord_cli.super_properties.httpx.get", side_effect=mock_get):
        result = fetch_build_number()

    assert result == 350000


def test_get_cached_build_number_persists_to_disk(tmp_path: Path) -> None:
    from unittest.mock import MagicMock, patch

    from discord_cli.super_properties import get_cached_build_number

    app_html = '<script src="/assets/abc123.js"></script>'
    js_with_build = "Build Number: 400000, Version Hash: xyz"

    call_count = 0

    def mock_get(url: str, **_kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        return MagicMock(text=app_html if "app" in url else js_with_build)

    cache_path = tmp_path / "build_number.json"

    with patch("discord_cli.super_properties.httpx.get", side_effect=mock_get):
        result1 = get_cached_build_number(cache_path=cache_path)

    assert result1 == 400000
    assert cache_path.exists()

    result2 = get_cached_build_number(cache_path=cache_path)
    assert result2 == 400000
    assert call_count == 2


def test_get_cached_build_number_returns_none_on_failure(tmp_path: Path) -> None:
    from unittest.mock import patch

    from discord_cli.super_properties import get_cached_build_number

    with patch(
        "discord_cli.super_properties.httpx.get", side_effect=Exception("network")
    ):
        result = get_cached_build_number(cache_path=tmp_path / "nope.json")

    assert result is None


def test_fetch_build_number_raises_on_missing() -> None:
    from unittest.mock import patch, MagicMock

    import pytest

    from discord_cli.super_properties import fetch_build_number

    app_html = '<script src="/assets/abc123.js"></script>'
    js_no_build = "some code without build info"

    def mock_get(url: str, **_kwargs: object) -> MagicMock:
        return MagicMock(text=app_html if "app" in url else js_no_build)

    with patch("discord_cli.super_properties.httpx.get", side_effect=mock_get):
        with pytest.raises(ValueError, match="client_build_number"):
            fetch_build_number()
