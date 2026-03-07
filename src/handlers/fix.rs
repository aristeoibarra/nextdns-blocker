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

    // Check credentials (env vars or Keychain) and validate against API
    match crate::config::types::EnvConfig::from_env() {
        Err(_) => {
            let has_api_key = std::env::var("NEXTDNS_API_KEY").is_ok()
                || crate::common::keychain::get_secret("api-key").ok().flatten().is_some();
            if !has_api_key {
                issues.push("NEXTDNS_API_KEY not set (env var or Keychain)".to_string());
            }
            let has_profile = std::env::var("NEXTDNS_PROFILE_ID").is_ok()
                || crate::common::keychain::get_secret("profile-id").ok().flatten().is_some();
            if !has_profile {
                issues.push("NEXTDNS_PROFILE_ID not set (env var or Keychain)".to_string());
            }
        }
        Ok(env_config) => {
            // Credentials exist — validate them against the API
            match crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id) {
                Ok(client) => {
                    if let Err(e) = client.get_denylist() {
                        if e.is_auth_error() {
                            issues.push("API credentials rejected (401/403) — update with: ndb config set-secret api-key <value>".to_string());
                        } else {
                            issues.push(format!("API connectivity issue: {e}"));
                        }
                    }
                }
                Err(e) => issues.push(format!("Failed to create API client: {e}")),
            }
        }
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
