use crate::cli::fix::FixArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(args: FixArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db_path = crate::common::platform::db_path();
    let config_path = crate::common::platform::config_path();

    let mut issues = Vec::new();
    let mut fixed = Vec::new();

    // Check config exists
    if !config_path.exists() {
        issues.push("Config file missing".to_string());
        if !args.check_only {
            // Auto-fix: create default config
            if let Some(parent) = config_path.parent() {
                std::fs::create_dir_all(parent)?;
            }
            let default = crate::config::types::AppConfig {
                version: "1.0".to_string(),
                settings: crate::config::types::Settings::default(),
                nextdns: crate::config::types::NextDnsConfig::default(),
                categories: vec![], blocklist: vec![], allowlist: vec![],
            };
            std::fs::write(&config_path, serde_json::to_string_pretty(&default)?)?;
            fixed.push("Created default config".to_string());
        }
    }

    // Check DB exists and is valid
    if !db_path.exists() {
        issues.push("Database file missing".to_string());
        if !args.check_only {
            let _db = crate::db::Database::open(&db_path)?;
            fixed.push("Created database".to_string());
        }
    } else {
        // Try to open and migrate
        match crate::db::Database::open(&db_path) {
            Ok(_) => {}
            Err(e) => {
                issues.push(format!("Database error: {e}"));
            }
        }
    }

    // Validate config if it exists
    if config_path.exists() {
        match crate::config::load_config() {
            Ok(config) => {
                if let Err(AppError::Validation { details, .. }) = crate::config::validation::validate_config(&config) {
                    for d in &details {
                        issues.push(format!("{}: {}", d.field, d.reason));
                    }
                }
            }
            Err(e) => issues.push(format!("Config load error: {e}")),
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
    output::render(&result, format);

    Ok(ExitCode::Success)
}

struct FixResult { issues: Vec<String>, fixed: Vec<String> }
impl Renderable for FixResult {
    fn command_name(&self) -> &str { "fix" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "issues": self.issues, "fixed": self.fixed }, "summary": { "found": self.issues.len(), "fixed": self.fixed.len() } })
    }
    fn to_human(&self) -> String {
        let mut out = String::new();
        if self.issues.is_empty() { out.push_str("  No issues found.\n"); }
        else {
            out.push_str("  Issues:\n");
            for i in &self.issues { out.push_str(&format!("    ! {i}\n")); }
        }
        if !self.fixed.is_empty() {
            out.push_str("  Fixed:\n");
            for f in &self.fixed { out.push_str(&format!("    + {f}\n")); }
        }
        out
    }
}
