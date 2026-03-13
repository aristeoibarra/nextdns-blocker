//! Pre-flight checks that run before every ndb command.
//! Handles enforcement and housekeeping so the watchdog doesn't have to.
//! All errors are silently ignored — preflight must never block a command.

use crate::cli::Commands;

/// Commands that skip preflight (no DB yet, or do their own processing).
pub fn should_run(command: &Commands) -> bool {
    !matches!(
        command,
        Commands::Init(_) | Commands::Watchdog(_) | Commands::Schema(_)
    )
}

/// Run all preflight checks. Best-effort: errors are silently swallowed.
pub fn run() {
    let _ = run_inner();
}

fn run_inner() -> Result<(), crate::error::AppError> {
    let db_path = crate::common::platform::db_path();
    if !db_path.exists() {
        return Ok(());
    }
    let db = crate::db::Database::open(&db_path)?;

    // Watchdog health: auto-repair if missing or binary path stale
    let _ = crate::watchdog::ensure_healthy();

    // Enforcement (DB-only, no API needed)
    // Audit-log failures so they're visible in `ndb audit list`
    if let Err(e) = crate::app_blocker::enforce_blocked_apps(&db) {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(
                conn, "enforce_failed", "app_blocker", "preflight",
                Some(&e.to_string()),
            )
        });
    }
    if let Err(e) = crate::hosts_blocker::enforce_hosts_entries(&db) {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(
                conn, "enforce_failed", "hosts_blocker", "preflight",
                Some(&e.to_string()),
            )
        });
    }

    // Check if there's pending/retry work before building API client
    let has_pending = db.with_conn(crate::db::pending::has_due_pending)?;
    let has_retries = db.with_conn(crate::db::retry::has_due_retries)?;

    if !has_pending && !has_retries {
        return Ok(());
    }

    // Build API client (may fail if not configured — that's fine)
    let env_config = crate::config::types::EnvConfig::from_env()?;
    let client = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id)?;

    if has_pending {
        if let Err(e) = crate::pending::process_pending(&db, &client) {
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(
                    conn, "process_failed", "pending", "preflight",
                    Some(&e.to_string()),
                )
            });
        }
    }
    if has_retries {
        if let Err(e) = crate::retry::process_retries(&db, &client) {
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(
                    conn, "process_failed", "retry", "preflight",
                    Some(&e.to_string()),
                )
            });
        }
    }

    Ok(())
}
