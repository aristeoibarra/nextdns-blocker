use crate::cli::fix::FixArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(args: FixArgs) -> Result<ExitCode, AppError> {
    let db_path = crate::common::platform::db_path();

    let mut issues = Vec::new();
    let mut fixed = Vec::new();

    // Check DB exists and is valid
    if !db_path.exists() {
        issues.push("Database file missing".to_string());
        if !args.check_only {
            let _db = crate::db::Database::open(&db_path)?;
            fixed.push("Created database with defaults".to_string());
        }
    } else {
        match crate::db::Database::open(&db_path) {
            Ok(db) => {
                // Verify kv_config has required keys
                for (key, default) in crate::db::config::KNOWN_KEYS {
                    let val = db.with_conn(|conn| crate::db::config::get_value(conn, key))?;
                    if val.is_none() {
                        issues.push(format!("Missing config key: {key}"));
                        if !args.check_only {
                            db.with_conn(|conn| crate::db::config::set_value(conn, key, default))?;
                            fixed.push(format!("Set default for {key}"));
                        }
                    }
                }
            }
            Err(e) => {
                issues.push(format!("Database error: {e}"));
            }
        }
    }

    // Check env vars
    if std::env::var("NEXTDNS_API_KEY").is_err() {
        issues.push("NEXTDNS_API_KEY not set".to_string());
    }
    if std::env::var("NEXTDNS_PROFILE_ID").is_err() {
        issues.push("NEXTDNS_PROFILE_ID not set".to_string());
    }

    let result = FixResult { issues, fixed };
    output::render(&result);

    Ok(ExitCode::Success)
}

struct FixResult { issues: Vec<String>, fixed: Vec<String> }
impl Renderable for FixResult {
    fn command_name(&self) -> &str { "fix" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "issues": self.issues, "fixed": self.fixed }, "summary": { "found": self.issues.len(), "fixed": self.fixed.len() } })
    }
}
