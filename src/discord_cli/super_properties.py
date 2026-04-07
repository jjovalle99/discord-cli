import base64
import json
import platform
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

DISCORD_APP_URL = "https://discord.com/app"
_BUILD_NUMBER_RE = re.compile(r"Build Number:\s*(\d+)")
_ASSET_RE = re.compile(r'src="/assets/(\w+)\.js"')
_CACHE_TTL_SECONDS = 3600
_DEFAULT_CACHE_PATH = Path.home() / ".config" / "discord-cli" / "build_number.json"


@dataclass(frozen=True)
class Fingerprint:
    os: str
    os_version: str
    user_agent: str
    browser_version: str


_ELECTRON_VERSION = "33.3.1"

_FINGERPRINTS = {
    "Darwin": Fingerprint(
        os="Mac OS X",
        os_version="10.15.7",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "discord/0.0.332 Chrome/130.0.6723.191 Electron/33.3.1 Safari/537.36"
        ),
        browser_version=_ELECTRON_VERSION,
    ),
    "Linux": Fingerprint(
        os="Linux",
        os_version="6.5.0",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "discord/0.0.332 Chrome/130.0.6723.191 Electron/33.3.1 Safari/537.36"
        ),
        browser_version=_ELECTRON_VERSION,
    ),
    "Windows": Fingerprint(
        os="Windows",
        os_version="10.0.19045",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "discord/1.0.9188 Chrome/130.0.6723.191 Electron/33.3.1 Safari/537.36"
        ),
        browser_version=_ELECTRON_VERSION,
    ),
}

_DEFAULT_FINGERPRINT = _FINGERPRINTS["Linux"]


def get_fingerprint() -> Fingerprint:
    return _FINGERPRINTS.get(platform.system(), _DEFAULT_FINGERPRINT)


def build_super_properties(build_number: int) -> str:
    fp = get_fingerprint()
    payload = {
        "os": fp.os,
        "browser": "Discord Client",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": fp.user_agent,
        "browser_version": fp.browser_version,
        "os_version": fp.os_version,
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": build_number,
        "client_event_source": None,
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def fetch_build_number() -> int:
    app_html = httpx.get(DISCORD_APP_URL, follow_redirects=True).text
    asset_ids = _ASSET_RE.findall(app_html)

    for asset_id in reversed(asset_ids):
        js_url = f"https://discord.com/assets/{asset_id}.js"
        js_text = httpx.get(js_url).text
        match = _BUILD_NUMBER_RE.search(js_text)
        if match:
            return int(match.group(1))

    msg = "Could not find client_build_number in Discord assets"
    raise ValueError(msg)


def get_cached_build_number(
    cache_path: Path = _DEFAULT_CACHE_PATH,
) -> int | None:
    try:
        data = json.loads(cache_path.read_text())
        cached_at = data.get("cached_at", 0)
        if (time.time() - cached_at) < _CACHE_TTL_SECONDS:
            return data.get("build_number")  # type: ignore[no-any-return]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    try:
        build_number = fetch_build_number()
    except Exception:  # noqa: BLE001
        return None

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"build_number": build_number, "cached_at": time.time()})
        )
    except OSError:
        pass

    return build_number
