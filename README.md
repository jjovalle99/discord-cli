# discord-cli

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![ty](https://img.shields.io/badge/type%20checked-ty-blue)](https://github.com/astral-sh/ty) [![coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)]()

Read-only Discord CLI for coding agents. All output is JSON to stdout.

Errors go to stderr as JSON. Every command accepts a `--token` flag to override credentials.

## Install

```
uv tool install .
```

> [!WARNING]
> This tool authenticates with unofficial user session tokens pulled from the Discord desktop app, not through OAuth or the Bot API. This means no app registration and no admin approval, but it also means your token has your full user permissions, Discord can revoke it at any time, and using it this way violates Discord's Terms of Service. Discord actively detects and bans "self-bot" usage. Read-only use is lower risk but not zero risk. Treat your token like a password. Don't share it.

## Credentials

This tool uses session tokens extracted from the Discord desktop app instead of official Bot API tokens. This means no bot creation, no OAuth flow, and no server admin approval. It piggybacks on your existing desktop session. The tradeoff: these are unofficial, undocumented tokens. They can expire (on logout, password change, or session revocation) or break if Discord changes their internal format, and they carry whatever permissions the logged-in user has with no scoping.

## Auth

```
discord-cli auth
```

Extracts the user token from the Discord desktop app (must be logged in). On macOS, triggers a system password prompt for Keychain access. Token is saved to `~/.config/discord-cli/config.json`. Token priority: `--token` flag > `DISCORD_TOKEN` env var > config file.

Supports both plaintext and encrypted tokens (AES-128-CBC and AES-256-GCM via Electron's safeStorage).

## Features

| I want to...                          | Command                                                                 |
|---------------------------------------|-------------------------------------------------------------------------|
| List all my servers                   | `discord-cli list servers`                                              |
| List channels in a server             | `discord-cli list channels <guild_id>`                                  |
| List open DM conversations            | `discord-cli list dms`                                                  |
| Read a channel's message history      | `discord-cli read channel <channel_id> [--limit N]`                     |
| Read all messages in a thread         | `discord-cli read thread <thread_id> [--limit N]`                       |
| Read a single message                 | `discord-cli read message <channel_id> <message_id>`                    |
| Get server metadata                   | `discord-cli read server-info <guild_id>`                               |
| Get channel metadata                  | `discord-cli read channel-info <channel_id>`                            |
| Look up a user's profile              | `discord-cli read user <user_id>`                                       |
| Look up a member's server profile     | `discord-cli read member <guild_id> <user_id>`                          |
| Download a file (image, doc, etc.)    | `discord-cli read file --url <url> [--output path]`                     |
| Search messages in a server           | `discord-cli search messages <guild_id> <query> [--limit N]`            |
| Search messages in a DM               | `discord-cli search dms <channel_id> <query> [--limit N]`               |

## Data Flow

Search commands return IDs that feed into read commands:

```bash
# 1. Search returns messages with channel_id and message id fields
discord-cli search messages 123456789 "deployment issue"

# 2. Use those values to read the full channel or a specific message
discord-cli read channel 987654321 --limit 50
discord-cli read message 987654321 111111111
```

Same pattern: `list servers` returns objects with an `id` field, which is the `guild_id` argument for `list channels`, `read server-info`, and `search messages`.

## Anti-Abuse Headers

Every API request includes `X-Super-Properties` and a matching `User-Agent` header derived from a coherent per-platform fingerprint (macOS/Linux/Windows). The `client_build_number` is scraped from Discord's web app and cached on disk (`~/.config/discord-cli/build_number.json`, 1h TTL) to avoid re-scraping on every command. If scraping fails, the header is silently omitted.

## Limitations

- Read-only. No posting, reacting, or modifying.
- Threads are channels in Discord. Thread IDs must be discovered from message `thread` fields or archived thread endpoints. `GET /guilds/{id}/threads/active` is not usable by user accounts.
- Attachment URLs are signed and expire after a few hours. Re-fetch the parent message for a fresh URL.
- `list dms` only returns currently open/visible DM conversations.
- Search is Elasticsearch-powered. Very recent messages may not appear. Max 10,000 navigable results.
- `read user` returns a partial profile. Some fields require a shared server with the target user.
- `auth` only works on macOS and Linux. Windows users must provide `--token` flag or `DISCORD_TOKEN` env var manually.
- Ban risk. Discord actively detects and bans self-bots. Read-only usage is lower risk but not zero risk.
