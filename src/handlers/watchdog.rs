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

    let sync_result = crate::sync::execute_sync(&db, &client, &evaluator, false)?;
    let pending_result = crate::pending::process_pending(&db, &client)?;
    let retry_result = crate::retry::process_retries(&db, &client)?;

    let result = WdResult {
        command: "watchdog run",
        data: serde_json::json!({
            "sync": sync_result.to_json(),
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
