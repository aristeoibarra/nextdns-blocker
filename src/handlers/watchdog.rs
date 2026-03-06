use crate::cli::watchdog::*;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: WatchdogCommands) -> Result<ExitCode, AppError> {
    match cmd {
        WatchdogCommands::Install(args) => handle_install(args),
        WatchdogCommands::Uninstall(_) => handle_uninstall(),
        WatchdogCommands::Status(_) => handle_status(),
        WatchdogCommands::Run(_) => handle_run(),
    }
}

fn handle_install(args: WatchdogInstallArgs) -> Result<ExitCode, AppError> {
    let duration = crate::common::time::parse_duration(&args.interval)?;
    let secs = duration.as_secs();

    let path = crate::watchdog::install(secs)?;

    let result = WdResult {
        command: "watchdog install",
        data: serde_json::json!({ "path": path, "interval_secs": secs, "scheduler": "launchd" }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_uninstall() -> Result<ExitCode, AppError> {
    crate::watchdog::uninstall()?;

    let result = WdResult {
        command: "watchdog uninstall",
        data: serde_json::json!({ "uninstalled": true }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_status() -> Result<ExitCode, AppError> {
    let status = crate::watchdog::status()?;

    let result = WdResult {
        command: "watchdog status",
        data: serde_json::to_value(&status)?,
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_run() -> Result<ExitCode, AppError> {
    let env_config = crate::config::types::EnvConfig::from_env()?;
    let db_path = crate::common::platform::db_path();
    let db = crate::db::Database::open(&db_path)?;

    let client = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id)?;

    let tz_str = db.with_conn(crate::db::config::get_timezone)?;
    let tz: chrono_tz::Tz = tz_str.parse()
        .map_err(|_| AppError::Config { message: format!("Invalid timezone: {tz_str}"), hint: None })?;
    let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);

    let sound = db.with_conn(crate::db::config::get_notification_sound)?;

    let sync_result = crate::sync::execute_sync(&db, &client, &evaluator, false)?;
    let pending_result = crate::pending::process_pending(&db, &client)?;
    let retry_result = crate::retry::process_retries(&db, &client)?;

    // Enforce blocked apps: kill any that are somehow running
    let apps_killed = crate::app_blocker::enforce_blocked_apps(&db).unwrap_or_default();

    // Collect success metrics
    let sync_changes = sync_result.denylist.added.len() + sync_result.denylist.removed.len()
        + sync_result.allowlist.added.len() + sync_result.allowlist.removed.len()
        + sync_result.categories.added.len() + sync_result.categories.removed.len()
        + sync_result.services.added.len() + sync_result.services.removed.len();
    let pending_changes = pending_result.executed;
    let retry_changes = retry_result.succeeded;
    let apps_enforced = apps_killed.len();

    // Collect failure metrics
    let pending_failures = pending_result.failed;
    let retry_failures = retry_result.failed;

    let notifier = crate::notifications::macos::MacosAdapter::new();

    // Notify failures with error sound
    if pending_failures + retry_failures > 0 {
        let mut parts = Vec::new();
        if pending_failures > 0 { parts.push(format!("{pending_failures} pending failed")); }
        if retry_failures > 0 { parts.push(format!("{retry_failures} retries failed")); }

        let notification = crate::notifications::Notification::new("ndb watchdog", parts.join(", "))
            .subtitle("Errors detected")
            .sound("Basso");
        let _ = crate::notifications::NotificationAdapter::send(&notifier, &notification);
    }

    // Notify successes with configured sound
    if sync_changes + pending_changes + retry_changes + apps_enforced > 0 {
        let mut parts = Vec::new();
        if sync_changes > 0 { parts.push(format!("{sync_changes} sync")); }
        if pending_changes > 0 { parts.push(format!("{pending_changes} pending")); }
        if retry_changes > 0 { parts.push(format!("{retry_changes} retries")); }
        if apps_enforced > 0 { parts.push(format!("{apps_enforced} apps killed")); }

        let notification = crate::notifications::Notification::new("ndb watchdog", parts.join(", "))
            .subtitle("Sync complete")
            .sound(sound);
        let _ = crate::notifications::NotificationAdapter::send(&notifier, &notification);
    }

    let result = WdResult {
        command: "watchdog run",
        data: serde_json::json!({
            "sync": sync_result.to_json(),
            "pending": pending_result,
            "retries": retry_result,
            "apps_killed": apps_killed,
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct WdResult { command: &'static str, data: serde_json::Value }
impl Renderable for WdResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
}
