use crate::cli::watchdog::*;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub async fn handle(cmd: WatchdogCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    match cmd {
        WatchdogCommands::Install(args) => handle_install(args, format),
        WatchdogCommands::Uninstall(_) => handle_uninstall(format),
        WatchdogCommands::Status(_) => handle_status(format),
        WatchdogCommands::Run(_) => handle_run(format).await,
    }
}

fn handle_install(args: WatchdogInstallArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let duration = crate::common::time::parse_duration(&args.interval)?;
    let secs = duration.as_secs();

    let path = crate::watchdog::install(secs)?;

    let result = WdResult {
        command: "watchdog install",
        data: serde_json::json!({ "path": path, "interval_secs": secs, "scheduler": crate::watchdog::detect_scheduler() }),
        msg: format!("  Installed watchdog ({}) every {}s\n  Path: {path}\n", crate::watchdog::detect_scheduler(), secs),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_uninstall(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    crate::watchdog::uninstall()?;

    let result = WdResult {
        command: "watchdog uninstall",
        data: serde_json::json!({ "uninstalled": true }),
        msg: "  Watchdog uninstalled.\n".to_string(),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_status(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let status = crate::watchdog::status()?;

    let result = WdResult {
        command: "watchdog status",
        data: serde_json::to_value(&status)?,
        msg: format!("  Scheduler: {}\n  Installed: {}\n  Running: {}\n", status.scheduler, status.installed, status.running),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

async fn handle_run(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let env_config = crate::config::types::EnvConfig::from_env()?;
    let db_path = crate::common::platform::db_path();
    let db = crate::db::Database::open(&db_path)?;
    let app_config = crate::config::load_config()?;

    let client = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id)?;

    let tz: chrono_tz::Tz = app_config.settings.timezone.as_deref().unwrap_or("UTC").parse()
        .map_err(|_| AppError::Config { message: "Invalid timezone".to_string(), hint: None })?;
    let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);

    // Run sync
    let sync_result = crate::sync::execute_sync(&db, &client, &evaluator, false).await?;

    // Process pending actions
    let pending_result = crate::pending::process_pending(&db, &client).await?;

    // Process retry queue
    let retry_result = crate::retry::process_retries(&db, &client).await?;

    let result = WdResult {
        command: "watchdog run",
        data: serde_json::json!({
            "sync": sync_result.to_json(),
            "pending": pending_result,
            "retries": retry_result,
        }),
        msg: format!("  Watchdog cycle complete.\n  Pending: {} executed, {} failed\n  Retries: {} ok, {} failed\n",
            pending_result.executed, pending_result.failed, retry_result.succeeded, retry_result.failed),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct WdResult { command: &'static str, data: serde_json::Value, msg: String }
impl Renderable for WdResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
    fn to_human(&self) -> String { self.msg.clone() }
}
