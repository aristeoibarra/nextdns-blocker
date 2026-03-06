# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

CLI tool (`ndb`) for managing NextDNS domain blocking with scheduling, protection, and notifications. Designed exclusively for Claude Code — all output is always JSON envelope, no human format.

## Build & Test Commands

```bash
cargo build                    # Build debug binary
cargo build --release          # Build optimized binary (LTO, stripped)
cargo test                     # Run all tests (52 total: 16 unit + 36 integration)
cargo test --lib               # Unit tests only
cargo test --test cli_test     # CLI integration tests only
cargo test --test db_test      # Database tests only
cargo test --test spec_contract_test  # Spec contract tests only
cargo test <test_name>         # Run a single test by name
```

Binary is `ndb` (not `nextdns-blocker`). Edition 2024, rust-version 1.85.

## Architecture

### Binary/Library Split

`src/lib.rs` exports all modules as a library crate. `src/main.rs` imports from `nextdns_blocker::*` — it does NOT redeclare modules with `mod`. This is critical: the binary uses the lib crate to avoid duplicate dead-code warnings.

### Command Flow

```
main.rs → Cli::parse() → run(command) → handlers::<cmd>::handle(args) → output::render()
```

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

`db::Database` wraps `rusqlite::Connection` in `Mutex`. Access via `db.with_conn(|conn| { ... })`. All tables use SQLite STRICT mode. Migrations in `src/db/schema.rs` via `include_str!()` from `migrations/`. WAL mode enabled.

### Config System

- SQLite `kv_config` table — all settings (timezone, safe_search, etc.)
- Environment variables — `NEXTDNS_API_KEY` and `NEXTDNS_PROFILE_ID` (secrets via `secrecy::SecretString`)
- Data path overridable with `NDB_DATA_DIR` env var

### API Client

`api::NextDnsClient` uses `ureq` (sync HTTP). Built-in resilience: circuit breaker (5 failures → open), sliding-window rate limiter (30 req/60s), TTL cache (300s). All API calls go through `pre_request_check()` first.

### Scheduler

`scheduler::ScheduleEvaluator` evaluates time-based blocking rules. Supports overnight ranges (22:00-02:00). Injectable `Clock` trait for testing. Used by `sync::execute_sync()` to determine what should be blocked right now.

### Protection

PIN-based protection using Argon2id hashing. Locked categories/domains can't be removed without unlock request. PIN sessions expire after 30 minutes, lockout after 3 failed attempts.

### Spec Contract Tests

`specs/` contains TOML files declaring each command's interface (args, flags, output schema, exit codes, examples). `tests/spec_contract_test.rs` auto-generates 12 tests that verify the binary matches these specs. When adding a new command, create its TOML spec in `specs/commands/`.

### Exit Codes

0=Success, 1=General, 2=Config, 3=Api, 4=Validation, 5=Permission, 6=Conflict, 7=NotFound, 130=Interrupted. Defined in `src/error.rs`. Each `AppError` variant maps to an exit code.

## Pinned Crate Versions

Do not upgrade: rusqlite 0.31.

## Key Patterns

- Handlers open DB via `Database::open(&common::platform::db_path())`
- Audit logging: `db::audit::log_action(conn, action, target_type, target_id, details)` in handlers
- Domain validation: `common::domain::parse_domains()` returns `(valid, errors)` tuples
- Error hints: every `AppError` variant includes an optional `hint` for recovery suggestions
- Notifications module exists but is not yet wired to handlers
