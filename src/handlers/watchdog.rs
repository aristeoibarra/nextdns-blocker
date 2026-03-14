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
    let notifier = crate::notifications::macos::MacosAdapter::new();

    let env_config = match crate::config::types::EnvConfig::from_env() {
        Ok(c) => c,
        Err(e) => {
            let notification = crate::notifications::Notification::new(
                "ndb watchdog",
                "Run: ndb config set-secret api-key <value>",
            )
                .subtitle("Missing API credentials")
                .sound("Basso");
            let _ = crate::notifications::NotificationAdapter::send(&notifier, &notification);
            return Err(e);
        }
    };

    let db_path = crate::common::platform::db_path();
    let db = crate::db::Database::open(&db_path)?;

    let client = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id)?;

    let tz_str = db.with_conn(crate::db::config::get_timezone)?;
    let tz: chrono_tz::Tz = tz_str.parse()
        .map_err(|_| AppError::Config {
            message: format!("Invalid timezone: {tz_str}"),
            hint: Some("Fix with 'ndb config set timezone America/Mexico_City'".to_string()),
        })?;
    let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);

    let sound = db.with_conn(crate::db::config::get_notification_sound)?;

    // Schedule sync — the primary job of the watchdog (time-based transitions)
    let schedule_result = crate::sync::execute_schedule_sync(&db, &client, &evaluator)?;

    // Sync Android state after schedule transitions
    if !schedule_result.added.is_empty() || !schedule_result.removed.is_empty() {
        let _ = crate::android_blocker::compute_and_sync(&db);
    }

    // Safety net: process pending/retries in case Claude Code hasn't run recently
    let pending_result = crate::pending::process_pending(&db, &client)?;
    let retry_result = crate::retry::process_retries(&db, &client)?;

    // Metrics
    let schedule_changes = schedule_result.added.len() + schedule_result.removed.len();
    let schedule_errors = schedule_result.errors.len();
    let pending_changes = pending_result.executed;
    let retry_changes = retry_result.succeeded;
    let total_failures = pending_result.failed + retry_result.failed + schedule_errors;
    let total_changes = schedule_changes + pending_changes + retry_changes;

    // Check if any errors are auth-related (invalid API key / profile ID)
    let has_auth_errors = schedule_result.errors.iter().any(|e| e.auth_error);

    if has_auth_errors {
        let notification = crate::notifications::Notification::new(
            "ndb watchdog",
            "Run: ndb config set-secret api-key <value>",
        )
            .subtitle("Invalid API credentials (401/403)")
            .sound("Basso");
        let _ = crate::notifications::NotificationAdapter::send(&notifier, &notification);
    } else if total_failures > 0 {
        let mut parts = Vec::new();
        if schedule_errors > 0 { parts.push(format!("{schedule_errors} schedule errors")); }
        if pending_result.failed > 0 { parts.push(format!("{} pending failed", pending_result.failed)); }
        if retry_result.failed > 0 { parts.push(format!("{} retries failed", retry_result.failed)); }

        let notification = crate::notifications::Notification::new("ndb watchdog", parts.join(", "))
            .subtitle("Errors detected")
            .sound("Basso");
        let _ = crate::notifications::NotificationAdapter::send(&notifier, &notification);
    }

    if total_changes > 0 {
        let mut parts = Vec::new();
        if schedule_changes > 0 { parts.push(format!("{schedule_changes} schedule")); }
        if pending_changes > 0 { parts.push(format!("{pending_changes} pending")); }
        if retry_changes > 0 { parts.push(format!("{retry_changes} retries")); }

        let notification = crate::notifications::Notification::new("ndb watchdog", parts.join(", "))
            .subtitle("Sync complete")
            .sound(sound);
        let _ = crate::notifications::NotificationAdapter::send(&notifier, &notification);
    }

    // Audit-log watchdog cycle summary
    let summary_details = serde_json::json!({
        "schedule_added": schedule_result.added,
        "schedule_removed": schedule_result.removed,
        "schedule_errors": schedule_errors,
        "pending_executed": pending_result.executed,
        "pending_failed": pending_result.failed,
        "retries_succeeded": retry_result.succeeded,
        "retries_failed": retry_result.failed,
        "retries_exhausted": retry_result.exhausted,
    }).to_string();
    let _ = db.with_conn(|conn| {
        crate::db::audit::log_action(
            conn, "watchdog_cycle", "watchdog", "run",
            Some(&summary_details), "watchdog",
        )
    });

    let result = WdResult {
        command: "watchdog run",
        data: serde_json::json!({
            "schedule_sync": schedule_result,
            "pending": pending_result,
            "retries": retry_result,
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
