use crate::cli::sync::SyncArgs;
use crate::error::{AppError, ExitCode};
use crate::output;
use crate::types::ResolvedFormat;

pub async fn handle(args: SyncArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let env_config = crate::config::types::EnvConfig::from_env()?;
    let db_path = crate::common::platform::db_path();
    let db = crate::db::Database::open(&db_path)?;
    let app_config = crate::config::load_config()?;

    let client = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id)?;

    let tz: chrono_tz::Tz = app_config.settings.timezone.as_deref().unwrap_or("UTC").parse()
        .map_err(|_| AppError::Config {
            message: "Invalid timezone in config".to_string(),
            hint: Some("Set a valid timezone with 'ndb config set settings.timezone America/Mexico_City'".to_string()),
        })?;

    let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);

    let result = crate::sync::execute_sync(&db, &client, &evaluator, args.dry_run).await?;
    output::render(&result, format);

    Ok(ExitCode::Success)
}
