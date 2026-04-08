# discord-cli

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![ty](https://img.shields.io/badge/type%20checked-ty-blue)](https://github.com/astral-sh/ty) [![coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)]()

Read-only Discord CLI for coding agents. All output is JSON to stdout.

![demo](demo.gif)

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

## Commands

| I want to...                          | Command                                                                 |
|---------------------------------------|-------------------------------------------------------------------------|
| Extract and save my token             | `discord-cli auth`                                                      |
| See who I'm authenticated as          | `discord-cli whoami`                                                    |
| List all my servers                   | `discord-cli list servers [--limit N]`                                  |
| List channels in a server             | `discord-cli list channels <guild_id>`                                  |
| List open DM conversations            | `discord-cli list dms`                                                  |
| List members in a server              | `discord-cli list members <guild_id> [--role NAME] [--limit N]`         |
| List threads in a channel             | `discord-cli list threads <channel_id>`                                 |
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
| Stream real-time channel events       | `discord-cli stream channel <channel_id> [--event TYPE]`                |
| Stream real-time server events        | `discord-cli stream server <guild_id> [--event TYPE]`                   |

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

## Flags

### Global flags

Every command accepts these flags:

| Flag | Description |
|------|-------------|
| `--token` | Override token (skips config file / env var) |
| `--quiet`, `-q` | Suppress stderr status messages |

### Read flags

Flags for `read channel` and `read thread`:

| Flag | Description |
|------|-------------|
| `--limit N` | Max messages to fetch (default 50) |
| `--compact` | Strip null fields and reduce author objects to id/username |
| `--author ID` | Filter messages by author user ID |
| `--skip-system` | Exclude join/pin/boost notifications |
| `--resolve-channels` | Replace `<#id>` mentions with `#channel-name` |
| `--resolve-mentions` | Replace `<@id>` mentions with `@username` |
| `--flatten-embeds` | Extract embed content into a plaintext `embed_text` field |
| `--max-bytes N` | Truncate output to fit within N bytes (context-aware) |
| `--pinned` | Fetch only pinned messages |
| `--before ID` | Pagination cursor: messages before this message ID |
| `--after ID` | Pagination cursor: messages after this message ID |
| `--since TIMESTAMP` | Fetch messages after an ISO 8601 timestamp |
| `--chronological` | Output oldest messages first (default is newest first) |
| `--format json\|jsonl\|text` | Output format (default `json`) |

Flags for `read message`:

| Flag | Description |
|------|-------------|
| `--compact` | Strip null fields and reduce author object |
| `--flatten-embeds` | Extract embed content into plaintext |
| `--format json\|jsonl\|text` | Output format |

Flags for `read file`:

| Flag | Description |
|------|-------------|
| `--url URL` | Direct CDN/attachment URL |
| `--channel ID` `--message ID` `--filename NAME` | Fetch by message reference (re-fetches fresh URL) |
| `--output PATH` | Write to file instead of stdout |

### Search flags

Flags for `search messages`:

| Flag | Description |
|------|-------------|
| `--limit N` | Max results (default 25, Discord caps at 25 per page) |
| `--channel ID` | Restrict search to a specific channel |
| `--from ID` | Filter by author ID |
| `--has TYPE` | Filter by attachment type (e.g. `file`, `image`, `link`) |
| `--before DATE` | Messages before this ISO 8601 date |
| `--after DATE` | Messages after this ISO 8601 date |
| `--sort-by FIELD` | Sort field (default `timestamp`) |
| `--sort-order asc\|desc` | Sort direction (default `desc`) |
| `--offset N` | Skip first N results |
| `--fallback-read` | If search returns 0 results, scan channel history instead (requires `--channel`) |

Flags for `search dms`:

| Flag | Description |
|------|-------------|
| `--limit N` | Max results (default 25) |
| `--fallback-read` | Scan channel history if search returns 0 results |

### List flags

| Flag | Description |
|------|-------------|
| `list servers --limit N` | Max servers (default 200) |
| `list members --role NAME` | Filter members by role name |
| `list members --limit N` | Max members (default 1000) |

### Stream flags

| Flag | Description |
|------|-------------|
| `--event TYPE` | Filter to a specific event type (e.g. `MESSAGE_CREATE`) |

### Performance flags

Available on most commands:

| Flag | Description |
|------|-------------|
| `--cache-ttl N` | Cache response for N seconds (default 0 = no cache) |
| `--no-cache` | Bypass cached response |
| `--rate-limit-info` | Include rate limit stats in output |

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
