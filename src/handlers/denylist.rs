use crate::cli::denylist::*;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode, ValidationDetail};
use crate::output::{self, Renderable};

pub fn handle(cmd: DenylistCommands) -> Result<ExitCode, AppError> {
    let db = open_db()?;
    match cmd {
        DenylistCommands::Add(args) => handle_add(&db, args),
        DenylistCommands::Remove(args) => handle_remove(&db, args),
        DenylistCommands::List(args) => handle_list(&db, args),
        DenylistCommands::Import(args) => handle_import(&db, args),
        DenylistCommands::Export(args) => handle_export(&db, args),
    }
}

fn open_db() -> Result<Database, AppError> {
    Database::open(&crate::common::platform::db_path())
}

fn handle_add(db: &Database, args: DenylistAddArgs) -> Result<ExitCode, AppError> {
    // Validate schedule upfront before any DB writes
    if let Some(ref sched_str) = args.schedule {
        let sched: crate::config::types::Schedule = serde_json::from_str(sched_str)
            .map_err(|e| AppError::Validation {
                message: format!("Invalid schedule JSON: {e}"),
                details: vec![],
                hint: Some("Schedule must be valid JSON with available_hours array".to_string()),
            })?;
        crate::scheduler::validate_config_schedule(&sched).map_err(|e| AppError::Validation {
            message: format!("Invalid schedule: {e}"),
            details: vec![],
            hint: Some("Times must be HH:MM, days must be mon/tue/wed/thu/fri/sat/sun".to_string()),
        })?;
    }

    let (valid, errors) = parse_domains(&args.domains);

    if valid.is_empty() && !errors.is_empty() {
        return Err(AppError::Validation {
            message: "No valid domains provided".to_string(),
            details: errors
                .iter()
                .map(|(d, r)| ValidationDetail { field: d.clone(), reason: r.clone() })
                .collect(),
            hint: Some("Domains must be valid RFC 1123 hostnames (e.g., example.com)".to_string()),
        });
    }

    let mut added = Vec::new();
    let mut skipped = Vec::new();

    db.with_transaction(|conn| {
        for domain in &valid {
            if crate::common::domain::is_protected(domain.as_str()) {
                skipped.push(domain.to_string());
                continue;
            }
            let existed = crate::db::domains::is_blocked(conn, domain.as_str())
                .map_err(AppError::from)?;
            crate::db::domains::add_blocked(
                conn, domain.as_str(), args.description.as_deref(),
                args.category.as_deref(), args.schedule.as_deref(),
            ).map_err(AppError::from)?;
            if existed { skipped.push(domain.to_string()); }
            else { added.push(domain.to_string()); }
            crate::db::audit::log_action(conn, "add", "denylist", domain.as_str(), None, "cli")
                .map_err(AppError::from)?;
        }
        Ok(())
    })?;

    if !added.is_empty() {
        if let Ok(env_config) = crate::config::types::EnvConfig::from_env() {
            if let Ok(client) = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id) {
                crate::sync::eager_push_denylist(db, &client, &added, true);
            }
        }
    }

    // Check congruency for added domains
    let mut warnings = Vec::new();
    for domain in &added {
        let issues = crate::congruency::check_denylist_add(db, domain, args.schedule.is_some());
        for issue in issues {
            warnings.push(serde_json::json!(issue));
        }
    }

    let result = DenylistAddResult {
        added, skipped, warnings,
        errors: errors.iter().map(|(d, r)| format!("{d}: {r}")).collect(),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct DenylistAddResult { added: Vec<String>, skipped: Vec<String>, errors: Vec<String>, warnings: Vec<serde_json::Value> }
impl Renderable for DenylistAddResult {
    fn command_name(&self) -> &str { "denylist add" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "added": self.added, "skipped": self.skipped, "errors": self.errors, "warnings": self.warnings },
            "summary": { "added": self.added.len(), "skipped": self.skipped.len(), "errors": self.errors.len(), "warnings": self.warnings.len() }
        })
    }
}

fn handle_remove(db: &Database, args: DenylistRemoveArgs) -> Result<ExitCode, AppError> {
    let mut removed = Vec::new();
    let mut not_found = Vec::new();

    db.with_transaction(|conn| {
        for domain in &args.domains {
            let domain_lower = domain.to_lowercase();
            if crate::db::domains::remove_blocked(conn, &domain_lower)
                .map_err(AppError::from)? {
                crate::db::audit::log_action(conn, "remove", "denylist", &domain_lower, None, "cli")
                    .map_err(AppError::from)?;
                removed.push(domain_lower);
            } else {
                not_found.push(domain_lower);
            }
        }
        Ok(())
    })?;

    if !removed.is_empty() {
        if let Ok(env_config) = crate::config::types::EnvConfig::from_env() {
            if let Ok(client) = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id) {
                crate::sync::eager_push_denylist(db, &client, &removed, false);
            }
        }
    }

    let result = DenylistRemoveResult { removed, not_found };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct DenylistRemoveResult { removed: Vec<String>, not_found: Vec<String> }
impl Renderable for DenylistRemoveResult {
    fn command_name(&self) -> &str { "denylist remove" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "removed": self.removed, "not_found": self.not_found },
            "summary": { "removed": self.removed.len(), "not_found": self.not_found.len() }
        })
    }
}

fn handle_list(db: &Database, args: DenylistListArgs) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| {
        let all = crate::db::domains::list_blocked(conn, !args.all)?;
        if let Some(ref cat) = args.category {
            Ok(all.into_iter().filter(|d| d.category.as_deref() == Some(cat.as_str())).collect::<Vec<_>>())
        } else {
            Ok(all)
        }
    })?;

    let active_count = domains.iter().filter(|d| d.active).count();
    let result = DenylistListResult { domains, active_count };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct DenylistListResult { domains: Vec<crate::types::BlockedDomain>, active_count: usize }
impl Renderable for DenylistListResult {
    fn command_name(&self) -> &str { "denylist list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "domains": self.domains },
            "summary": { "total": self.domains.len(), "active": self.active_count }
        })
    }
}

fn handle_import(db: &Database, args: DenylistImportArgs) -> Result<ExitCode, AppError> {
    let content = std::fs::read_to_string(&args.file).map_err(|e| AppError::General {
        message: format!("Failed to read file '{}': {e}", args.file),
        hint: Some("Ensure the file exists and is readable".to_string()),
    })?;

    let lines: Vec<String> = content.lines()
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .collect();

    let (valid, errors) = parse_domains(&lines);

    let mut imported = 0;
    let mut skipped = 0;

    db.with_transaction(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_blocked(conn, domain.as_str())
                .map_err(AppError::from)?;
            crate::db::domains::add_blocked(conn, domain.as_str(), args.description.as_deref(), None, None)
                .map_err(AppError::from)?;
            if existed {
                skipped += 1;
            } else {
                imported += 1;
                crate::db::audit::log_action(conn, "import", "denylist", domain.as_str(), None, "cli")
                    .map_err(AppError::from)?;
            }
        }
        Ok(())
    })?;

    let result = ImportResult { imported, skipped, errors: errors.len() };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct ImportResult { imported: usize, skipped: usize, errors: usize }
impl Renderable for ImportResult {
    fn command_name(&self) -> &str { "denylist import" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "imported": self.imported, "skipped": self.skipped, "errors": self.errors },
            "summary": { "imported": self.imported, "skipped": self.skipped }
        })
    }
}

fn handle_export(db: &Database, args: DenylistExportArgs) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;

    let output_str = if args.format == "json" {
        serde_json::to_string_pretty(&domains)?
    } else {
        domains.iter().map(|d| d.domain.as_str()).collect::<Vec<_>>().join("\n") + "\n"
    };

    let path = if let Some(ref path) = args.file {
        std::fs::write(path, &output_str)?;
        Some(path.clone())
    } else {
        None
    };

    let result = ExportResult { path, count: domains.len() };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct ExportResult { path: Option<String>, count: usize }
impl Renderable for ExportResult {
    fn command_name(&self) -> &str { "denylist export" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "path": self.path, "count": self.count },
            "summary": { "exported": self.count }
        })
    }
}
