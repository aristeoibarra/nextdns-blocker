# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

CLI tool (`ndb`) for managing NextDNS domain blocking with scheduling, notifications, and audit logging. macOS-only, designed exclusively for Claude Code — all output is always JSON envelope, no human format.

## Build & Test Commands

```bash
cargo build                    # Build debug binary
cargo build --release          # Build optimized binary (LTO, stripped)
cargo test                     # Run all tests (63 total: 16 unit + 47 integration)
cargo test --lib               # Unit tests only
cargo test --test cli_test     # CLI integration tests only (12)
cargo test --test db_test      # Database tests only (13)
cargo test --test integration_test  # Integration tests (10)
cargo test --test spec_contract_test  # Spec contract tests only (12)
cargo test <test_name>         # Run a single test by name
```

Binary is `ndb` (not `nextdns-blocker`). Edition 2024, rust-version 1.85.

## Architecture

### Binary/Library Split

`src/lib.rs` exports all modules as a library crate. `src/main.rs` imports from `nextdns_blocker::*` — it does NOT redeclare modules with `mod`. This is critical: the binary uses the lib crate to avoid duplicate dead-code warnings.

### Command Flow

```
main.rs → Cli::parse() → preflight::run() → run(command) → handlers::<cmd>::handle(args) → output::render()
```

### Pre-flight

`preflight` module runs before every command (except init, watchdog, schema). Best-effort, never blocks. Handles:
- App enforcement (batch `ps` check + killall)
- Hosts enforcement (re-apply /etc/hosts if drifted)
- Process due pending actions (if API client available)
- Process due retries (if API client available)

This makes the watchdog lighter — enforcement happens at command-time instead of polling.

17 top-level commands: init, status, sync, block, unblock, fix, apps, denylist, allowlist, category, nextdns, config, pending, audit, watchdog, hosts, schema.

Everything is sync — no async/await anywhere. Every handler returns `Result<ExitCode, AppError>`. On success, it constructs a struct implementing `Renderable` and calls `output::render()`. On error, `main.rs` catches it and calls `output::render_error()`.

### Output System (JSON-only)

All output is always JSON envelope to stdout:
```json
{ "ok": true, "command": "...", "data": {...}, "timestamp": "..." }
```

Errors go to stderr as JSON:
```json
{ "ok": false, "command": "...", "error": { "code": "...", "message": "...", "hint": "..." }, "exit_code": N, "timestamp": "..." }
```

The `Renderable` trait has only two methods: `command_name()` and `to_json()`. No human/TTY format exists.

### Database Layer

`db::Database` wraps `rusqlite::Connection` in `Mutex`. Access via `db.with_conn(|conn| { ... })` or `db.with_transaction(|conn| { ... })` for atomic multi-write operations. All tables use SQLite STRICT mode. Migrations in `src/db/schema.rs` via `include_str!()` from `migrations/` (6 migration files). WAL mode enabled.

### Config System

- SQLite `kv_config` table — all settings (timezone, safe_search, notification_sound, etc.)
- Secrets: macOS Keychain (preferred) or env vars `NEXTDNS_API_KEY`/`NEXTDNS_PROFILE_ID` (fallback). Managed via `ndb config set-secret`/`remove-secret`
- Data path overridable with `NDB_DATA_DIR` env var

### API Client

`api::NextDnsClient` uses `ureq` (sync HTTP). Built-in resilience: circuit breaker (5 failures → open), sliding-window rate limiter (30 req/60s), TTL cache (300s). All API calls go through `pre_request_check()` first.

### Scheduler

`scheduler::ScheduleEvaluator` evaluates time-based blocking rules. Supports overnight ranges (22:00-02:00). Injectable `Clock` trait for testing. Used by `sync::execute_sync()` to determine what should be blocked right now.

### App Blocker

`app_blocker` module handles local macOS app blocking alongside DNS blocking. When `ndb block whatsapp.com` runs, it also blocks the WhatsApp.app locally (rename `.app` to `.app.blocked` + `killall`). Uses `mdfind` (Spotlight) for app discovery. Known domain-to-bundle-ID mappings in `app_blocker::mappings::KNOWN_MAPPINGS`. DB tables: `app_mappings` (domain↔bundle_id), `blocked_apps` (rename state). `ndb apps scan` auto-populates mappings. `enforce_blocked_apps()` uses batch `ps -Ac` (1 subprocess) instead of N `pgrep` calls. Runs in pre-flight on every command.

### Hosts Blocker

`hosts_blocker` module is the 3rd blocking layer (DNS + apps + hosts). Writes domains to `/etc/hosts` as `0.0.0.0 domain.com` inside `# ndb-start` / `# ndb-end` markers. Uses `sudo -n cp` for atomic writes and auto-flushes DNS cache (`dscacheutil` + `mDNSResponder`). Requires `ndb hosts setup` first for passwordless sudo. DB table: `hosts_entries`. `enforce_hosts_entries()` runs in pre-flight on every command. `api.nextdns.io` is a protected domain that is never blocked in hosts.

### Notifications

`notifications::MacosAdapter` sends macOS native notifications via `osascript` (`display notification`). Supports title, message, subtitle, and sound. Watchdog sends two types: success notifications (configurable sound, default "Blow") and error notifications (sound "Basso"). Sound configurable via `ndb config set notification_sound <name>`.

### Watchdog

`watchdog` module manages a `launchd` plist for periodic execution. `watchdog run` only handles schedule transitions (time-based blocking rules) + safety-net pending/retries processing. Enforcement (apps, hosts) and housekeeping (pending, retries) moved to pre-flight. Drift sync (`ndb sync`) is on-demand only.

### Spec Contract Tests

`specs/` contains TOML files declaring each command's interface (args, flags, output schema, exit codes, examples). `tests/spec_contract_test.rs` auto-generates 12 tests that verify the binary matches these specs. When adding a new command, create its TOML spec in `specs/commands/`.

### Exit Codes

0=Success, 1=General, 2=Config, 3=Api, 4=Validation, 6=Conflict, 7=NotFound, 130=Interrupted. Defined in `src/error.rs`. Each `AppError` variant maps to an exit code.

## Pinned Crate Versions

Do not upgrade: rusqlite 0.31.

## Key Patterns

- Handlers open DB via `Database::open(&common::platform::db_path())`
- Audit logging: `db::audit::log_action(conn, action, target_type, target_id, details)` in handlers
- Domain validation: `common::domain::parse_domains()` returns `(valid, errors)` tuples
- Error hints: every `AppError` variant includes an optional `hint` for recovery suggestions
- Use `db.with_transaction()` for multi-write handlers (block, denylist import)
- Sync failures auto-enqueue to retry_queue for automatic recovery
- Pending action failures also escalate to retry_queue
- Exhausted retries are audit-logged before removal (never silently dropped)
- `block` = quick multi-domain action; `denylist add` = CRUD management
- Secrets via macOS `security` CLI (zero deps) in `common::keychain`
