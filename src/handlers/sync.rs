use crate::cli::sync::SyncArgs;
use crate::error::{AppError, ExitCode};
use crate::output;

pub fn handle(args: SyncArgs) -> Result<ExitCode, AppError> {
    let env_config = crate::config::types::EnvConfig::from_env()?;
    let db_path = crate::common::platform::db_path();
    let db = crate::db::Database::open(&db_path)?;

    let client = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id)?;

    let tz_str = db.with_conn(crate::db::config::get_timezone)?;
    let tz: chrono_tz::Tz = tz_str.parse()
        .map_err(|_| AppError::Config {
            message: format!("Invalid timezone in DB: {tz_str}"),
            hint: Some("Fix with 'ndb config set timezone America/Mexico_City'".to_string()),
        })?;

    let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);

    let result = crate::sync::execute_sync(&db, &client, &evaluator, args.dry_run)?;
    output::render(&result);

    Ok(ExitCode::Success)
}
