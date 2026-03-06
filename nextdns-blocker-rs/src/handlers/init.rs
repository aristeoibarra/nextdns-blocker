use crate::cli::init::InitArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub async fn handle(args: InitArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let config_path = crate::common::platform::config_path();
    let db_path = crate::common::platform::db_path();

    if config_path.exists() && !args.force {
        return Err(AppError::Conflict {
            message: "Configuration already exists".to_string(),
            hint: Some("Use --force to overwrite existing configuration".to_string()),
        });
    }

    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let default_config = crate::config::types::AppConfig {
        version: "1.0".to_string(),
        settings: crate::config::types::Settings::default(),
        nextdns: crate::config::types::NextDnsConfig::default(),
        categories: vec![],
        blocklist: vec![],
        allowlist: vec![],
    };

    let json = serde_json::to_string_pretty(&default_config)?;
    std::fs::write(&config_path, json)?;

    let _db = crate::db::Database::open(&db_path)?;

    let result = InitResult {
        config_path: config_path.to_string_lossy().to_string(),
        db_path: db_path.to_string_lossy().to_string(),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct InitResult { config_path: String, db_path: String }

impl Renderable for InitResult {
    fn command_name(&self) -> &str { "init" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "config_path": self.config_path, "db_path": self.db_path }, "summary": { "initialized": true } })
    }
    fn to_human(&self) -> String {
        format!("Initialized ndb:\n  Config: {}\n  Database: {}\n\nNext steps:\n  1. Set NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID environment variables\n  2. Edit config: ndb config edit\n  3. Sync: ndb sync\n", self.config_path, self.db_path)
    }
}
