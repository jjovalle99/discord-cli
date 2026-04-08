# Progress

## Step 1: Project scaffolding — DONE
- `pyproject.toml` with cyclopts, httpx, dev deps (pytest, ruff, ty)
- `src/discord_cli/config.py` — atomic temp-file + os.replace writes with `0o600`, inode rotation
- `src/discord_cli/output.py` — JSON stdout/stderr contract
- 5 tests

## Step 2: Token resolution — DONE
- Priority chain: `--token` flag > `DISCORD_TOKEN` env > config file
- SystemExit with actionable message when no token found
- 4 tests

## Step 3: HTTP client — DONE
- `DiscordClient` with `api_get` (dict) and `api_get_list` (list) for type safety
- Rate-limit retry on 429 (capped at 60s)
- Separate unauthenticated `_cdn` client for `fetch_url_bytes` — no token leak to CDN
- Exact hostname matching for `cdn.discordapp.com` and `media.discordapp.net`
- `X-Super-Properties` + matching `User-Agent` from coherent per-platform Fingerprint bundle
- 8 client tests

## Step 4: Token validation — DONE
- `GET /users/@me`, AuthError on 401
- 2 tests

## Steps 5-7: Token extraction/decryption/auth command — DONE
- LevelDB extraction via `ccl_chromium_reader`, copy-to-temp to avoid locks
- AES-128-CBC decryption (PBKDF2, macOS Keychain `"Discord Safe Storage"` / Linux `"peanuts"`)
- AES-256-GCM fallback when CBC output fails token-shape validation
- `is_encrypted()` predicate encapsulates prefix check — no leaky constant export
- Typed `AuthError` for all auth failure paths
- Unified `_run_with_error_handling` for JSON stderr error contract across all commands
- 12 auth tests

## Steps 8-20: All commands — DONE
- **list**: servers, channels (with type_name shaping), dms (with type_name shaping)
- **read**: channel (with auto-pagination), thread (alias), message, server-info, channel-info, user, member, file
- **search**: messages (with 202 retry), dms
- **CLI wiring**: all commands wired via cyclopts with `--token` flag
- **Response shaping**: list commands emit only documented fields, no raw Discord payloads
- 21 command tests

## X-Super-Properties — DONE
- Per-platform Fingerprint (Darwin/Linux/Windows) with coherent UA + super-properties
- Build number scraped from Discord app JS, on-disk JSON cache with 1h TTL
- Scrape runs after token resolution — bad tokens fail immediately without network
- Graceful degradation — header omitted if scrape fails
- 7 super-properties tests

## Issue #2: --compact flag — DONE
- `--compact` on `read channel`, `read thread`, `read message`
- Strips null-valued fields from message output
- Reduces author to {id, username, global_name}, includes bot/system only when truthy
- Preserves `referenced_message: null` (Discord uses null vs absent to distinguish "reply to deleted" from "not a reply")
- Does not synthesize fields absent from the API response
- 6 new tests (null stripping, author reduction, bot provenance, absent global_name, referenced_message sentinel, read_message)

## Issue #3: search index lag note + --fallback-read — DONE
- Search output now includes `"note"` field warning about Elasticsearch indexing lag
- `--fallback-read` flag on `search messages` and `search dms` falls back to reading channel history + client-side case-insensitive substring filter when search returns 0 results
- Requires `--channel-id` (guild search) or positional channel_id (DM search)
- Rejects unsupported filters (`--author-id`, `--has`, `--offset`) when fallback is active
- Fixed page size (100) with 500-message scan cap, independent of result limit
- 9 search tests total (6 new)
- Edge case: fallback only does substring match on `content` field — no support for author/attachment/embed filters in fallback mode

## Issue #4: --author filter on read channel/thread — DONE
- `--author <user_id>` flag on `read channel` and `read thread`
- Client-side filtering by `author.id` (Discord API has no server-side author filter for message history)
- Always fetches 100 messages per page when author is set for efficiency
- 500-message scan cap prevents unbounded channel crawls on sparse/absent authors
- 3 new tests (basic filtering, cross-page pagination, scan cap enforcement)
- Edge case: if target author has no messages in the scanned window, returns empty list silently

## Issue #5: --skip-system flag — DONE
- `--skip-system` on `read channel` and `read thread`
- Filters out system message types (join, pin, boost, etc.) using a denylist of Discord system types
- Keeps all user-authored types: 0 (default), 19 (reply), 20 (slash command), 23 (context menu command), and any future non-system types
- No scan cap when only `--skip-system` is set (paginate until limit satisfied or channel exhausted)
- Scan cap still applies when combined with `--author`
- 4 new tests (basic filtering with type 23 survival, pagination fill, author combo, scan cap decoupling)
- Edge case: channels with only system messages return empty list when `--skip-system` is set

## Issue #6: --resolve-channels flag — DONE
- `--resolve-channels` on `read channel` and `read thread`
- Fetches channel info + guild channels to build an id→name map
- Adds `channel_name` field to each message in the output
- Replaces `<#id>` references in message content with `#channel-name`; unknown IDs left unchanged
- Best-effort: API errors during resolution degrade gracefully (messages returned without enrichment)
- Channel map seeded from channel info before guild listing (handles threads/channels not in guild list)
- DM channels (no guild_id) skip resolution gracefully
- 5 new tests (channel_name addition, content replacement with unknown IDs, DM skip, thread seeding, API error degradation)
- Edge case: DM channels produce empty channel map since they have no `name` field

## Issue #7: --max-bytes flag for context-aware output — DONE
- `--max-bytes` on `read channel` and `read thread`
- When output exceeds byte limit, truncates older messages and wraps in metadata envelope: `{truncated, messages_returned, messages_available, messages}`
- When output fits within limit, returns plain list (no envelope overhead)
- Byte counting includes trailing newline from `print()` for exact stdout accuracy
- Errors with `max_bytes_too_small` when even an empty envelope can't fit
- Works with `--compact` (compact runs first, then truncation — more messages fit)
- 4 new tests (truncation with envelope, no-envelope when fits, compact combo, too-small error)
- Edge case: very small `max_bytes` values (< ~95 bytes) trigger structured error instead of silently violating the cap

## Issue #9: --before and --after pagination cursors — DONE
- `--before <message_id>` and `--after <message_id>` on `read channel` and `read thread`
- Maps directly to Discord's `GET /channels/{id}/messages?before=...&after=...` query parameters
- Enables forward/backward pagination through message history beyond the default newest-N
- `--after` cursor uses `max(batch, key=id)` for order-independent pagination (robust to response ordering)
- Mutually exclusive: `--before` + `--after` together → `incompatible_flags` error
- Incompatible with `--pinned` (pins endpoint has no cursor support)
- 5 new tests (before cursor, after pagination, mutual exclusivity, pinned rejection, newest-first regression)
- Edge case: `--after` returns messages in ascending order (oldest first) per Discord API spec

## Issue #10: --resolve-mentions flag — DONE
- `--resolve-mentions` on `read channel` and `read thread`
- Replaces `<@id>` and `<@!id>` (nick-prefix) patterns in message content with `@username`
- Uses the `mentions` array already present in the message — no extra API calls
- Code-span aware: mentions inside backtick-delimited code (inline and fenced) are preserved
- Unknown mention IDs (not in `mentions` array) left unchanged
- 3 new tests (basic resolution + unknown ID preservation, nick-prefix format, code-span preservation)
- Edge case: pre-existing `--resolve-channels` does not protect code spans — separate concern, not addressed here

## Issue #11: --chronological flag for oldest-first message order — DONE
- `--chronological` on `read channel` and `read thread`
- Reverses output from newest-first (Discord default) to oldest-first for natural conversation reading
- Uses O(n) `reverse()` for the default pagination path (messages already descending)
- `--after` pagination path sorts before slicing for contiguous message selection
- `--max-bytes` truncation operates before display reordering (retains newest messages, then reorders for display)
- Extracted `_message_sort_key` helper to deduplicate ID-based sort key across 4 call sites
- 3 new tests (basic reversal, after-path contiguity, max-bytes retention semantics)
- Edge case: `--after` responses may arrive in any order; sort ensures contiguous selection regardless

## Issue #12: --since timestamp filter for incremental reads — DONE
- `--since <ISO8601>` on `read channel` and `read thread`
- Converts ISO 8601 timestamp to Discord snowflake and passes as `after` query parameter
- Naive timestamps (no timezone) treated as UTC; timezone-aware timestamps converted correctly
- Incompatible with `--after` (both set the same cursor); inherits existing `--before`/`--pinned` incompatibilities via `after`
- Invalid timestamps produce `invalid_since` error (prevents misleading "Token decryption failed" from generic `ValueError` handler)
- 5 new tests (snowflake conversion, mutual exclusivity, invalid timestamp, timezone-aware, incremental-read slice semantics)
- Edge case: when more messages exist after the timestamp than `--limit`, returns the oldest slice (nearest to cutoff) — correct for incremental polling workflows

## Issue #13: list members command — DONE
- `list members <guild_id>` with `--role <name>` filter and `--limit N`
- Fetches guild roles and first members page concurrently via `asyncio.gather`
- Cursor-based pagination via Discord's `after` parameter for guilds > 1000 members
- Resolves role IDs to human-readable names in output
- `--role` filter scans across pages until `limit` matches found or guild exhausted
- Filters on raw role IDs before shaping (avoids unnecessary name resolution for discarded members)
- 4 new tests (role resolution, role filter, pagination with cursor, cross-page role scanning)
- Edge case: `GET /guilds/{id}/members` returns 403 for user accounts on most servers (Discord API limitation for non-bot tokens). Surfaced as structured error via existing `DiscordAPIError` handler.

## Issue #14: --format text|jsonl output modes — DONE
- `--format text` on `read channel`, `read thread`, `read message`
- Outputs one line per message: `[YYYY-MM-DD HH:MM] username: content`
- Newlines and carriage returns in content escaped as `\n`/`\r` to preserve one-line-per-message invariant
- `--format jsonl` on the same commands — one JSON object per line, no indentation
- `--format json` (default) — existing behavior unchanged
- `--max-bytes` works correctly with all formats: text/jsonl use incremental size subtraction (O(N)), JSON uses envelope-based truncation
- `Format` type alias (`Literal["json", "jsonl", "text"]`) for compile-time validation
- 6 new tests (text formatting, text output, jsonl output, single message text, newline escaping, text+max_bytes truncation)
- Edge case: multiline Discord messages (code blocks, etc.) collapse to single output line in text mode — content preserved via escaping

## Issue #15: auto-refresh expired attachment URLs — DONE
- `--channel <id> --message <id> --filename <name>` flags on `read file` as alternative to `--url`
- Fetches message via API, finds attachment by filename, downloads fresh signed URL
- Clean JSON error (`url_expired`) on 403 for attachment URLs, suggesting `--channel --message --filename`
- Clean JSON error (`download_failed`) for non-attachment CDN 403s and other HTTP errors
- Clean JSON error (`attachment_not_found`) when filename doesn't match any attachment in the message
- Clean JSON error (`missing_flags`) when neither `--url` nor the full `--channel/--message/--filename` trio provided
- URL-decoded filenames from CDN paths (handles spaces, Unicode in attachment names)
- Reuses `_ALLOWED_HOSTS` from `client.py` (no duplicate host set)
- 7 new tests (URL parsing, percent-encoding, expired URL, message reference, attachment not found, non-attachment 403)
- Edge case: Discord CDN attachment URLs contain `attachment_id` not `message_id` — auto-refresh from URL alone is impossible, hence the `--channel --message --filename` approach
- Edge case: `GET /channels/{id}/messages/{id}` returns 403 on some servers for user tokens (Discord API limitation, pre-existing)

## Summary
- 117 tests total, all gates pass (pytest, ruff, ty)
- All SPEC.md steps implemented
- Edge case: active threads not listable by user accounts (Discord API limitation)
