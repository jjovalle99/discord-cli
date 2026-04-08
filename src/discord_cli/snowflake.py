from datetime import datetime, timezone

_DISCORD_EPOCH_MS = 1420070400000


def date_to_snowflake(iso_date: str) -> str:
    dt = datetime.fromisoformat(iso_date)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    unix_ms = int(dt.timestamp() * 1000)
    return str((unix_ms - _DISCORD_EPOCH_MS) << 22)
