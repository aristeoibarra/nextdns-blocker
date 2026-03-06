use crate::cli::init::InitArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(args: InitArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db_path = crate::common::platform::db_path();

    if db_path.exists() && !args.force {
        return Err(AppError::Conflict {
            message: "Database already exists".to_string(),
            hint: Some("Use --force to re-initialize defaults".to_string()),
        });
    }

    // Open (or create) DB — migrations insert default kv_config values
    let db = crate::db::Database::open(&db_path)?;

    // If --force on existing DB, reset kv_config defaults
    if args.force {
        for (key, default) in crate::db::config::KNOWN_KEYS {
            db.with_conn(|conn| crate::db::config::set_value(conn, key, default))?;
        }
    }

    let result = InitResult {
        db_path: db_path.to_string_lossy().to_string(),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct InitResult { db_path: String }

impl Renderable for InitResult {
    fn command_name(&self) -> &str { "init" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "db_path": self.db_path }, "summary": { "initialized": true } })
    }
    fn to_human(&self) -> String {
        format!("Initialized ndb:\n  Database: {}\n\nNext steps:\n  1. Set NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID environment variables\n  2. Configure: ndb config set timezone America/Mexico_City\n  3. Sync: ndb sync\n", self.db_path)
    }
}
