use crate::cli::allowlist::*;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode, ValidationDetail};
use crate::output::{self, Renderable};

pub fn handle(cmd: AllowlistCommands) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        AllowlistCommands::Add(args) => handle_add(&db, args),
        AllowlistCommands::Remove(args) => handle_remove(&db, args),
        AllowlistCommands::List(args) => handle_list(&db, args),
        AllowlistCommands::Import(args) => handle_import(&db, args),
        AllowlistCommands::Export(args) => handle_export(&db, args),
    }
}

fn handle_add(db: &Database, args: AllowlistAddArgs) -> Result<ExitCode, AppError> {
    let (valid, errors) = parse_domains(&args.domains);
    if valid.is_empty() && !errors.is_empty() {
        return Err(AppError::Validation {
            message: "No valid domains provided".to_string(),
            details: errors.iter().map(|(d, r)| ValidationDetail { field: d.clone(), reason: r.clone() }).collect(),
            hint: Some("Domains must be valid RFC 1123 hostnames".to_string()),
        });
    }

    let mut added = Vec::new();
    let mut skipped = Vec::new();

    db.with_transaction(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_allowed(conn, domain.as_str())
                .map_err(AppError::from)?;
            crate::db::domains::add_allowed(conn, domain.as_str(), args.description.as_deref(), args.schedule.as_deref())
                .map_err(AppError::from)?;
            if existed { skipped.push(domain.to_string()); }
            else { added.push(domain.to_string()); }
            crate::db::audit::log_action(conn, "add", "allowlist", domain.as_str(), None)
                .map_err(AppError::from)?;
        }
        Ok(())
    })?;

    if !added.is_empty() {
        if let Ok(env_config) = crate::config::types::EnvConfig::from_env() {
            if let Ok(client) = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id) {
                let domains_to_push = if args.schedule.is_some() {
                    let tz_str = db.with_conn(crate::db::config::get_timezone).unwrap_or_else(|_| "UTC".to_string());
                    if let Ok(tz) = tz_str.parse::<chrono_tz::Tz>() {
                        let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);
                        let schedule = args.schedule.as_deref().and_then(|s| {
                            serde_json::from_str::<crate::config::types::Schedule>(s).ok()
                        });
                        let parsed = schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);
                        if evaluator.is_available(parsed.as_ref()) { added.clone() } else { vec![] }
                    } else { added.clone() }
                } else { added.clone() };

                if !domains_to_push.is_empty() {
                    crate::sync::eager_push_allowlist(db, &client, &domains_to_push, true);
                }
            }
        }
    }

    let result = ListModResult { command: "allowlist add", added, skipped, errors: errors.iter().map(|(d,r)| format!("{d}: {r}")).collect() };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_remove(db: &Database, args: AllowlistRemoveArgs) -> Result<ExitCode, AppError> {
    let mut removed = Vec::new();
    let mut not_found = Vec::new();

    db.with_transaction(|conn| {
        for domain in &args.domains {
            let d = domain.to_lowercase();
            if crate::db::domains::remove_allowed(conn, &d)
                .map_err(AppError::from)? {
                crate::db::audit::log_action(conn, "remove", "allowlist", &d, None)
                    .map_err(AppError::from)?;
                removed.push(d);
            } else {
                not_found.push(domain.clone());
            }
        }
        Ok(())
    })?;

    if !removed.is_empty() {
        if let Ok(env_config) = crate::config::types::EnvConfig::from_env() {
            if let Ok(client) = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id) {
                crate::sync::eager_push_allowlist(db, &client, &removed, false);
            }
        }
    }

    let result = RemoveResult { command: "allowlist remove", removed, not_found };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_list(db: &Database, args: AllowlistListArgs) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_allowed(conn, !args.all))?;
    let active_count = domains.iter().filter(|d| d.active).count();

    let result = AllowlistListResult { domains, active_count };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_import(db: &Database, args: AllowlistImportArgs) -> Result<ExitCode, AppError> {
    let content = std::fs::read_to_string(&args.file).map_err(|e| AppError::General { message: format!("Failed to read file: {e}"), hint: None })?;
    let lines: Vec<String> = content.lines().map(|l| l.trim().to_string()).filter(|l| !l.is_empty() && !l.starts_with('#')).collect();
    let (valid, _errors) = parse_domains(&lines);

    let mut imported = 0;
    let mut skipped = 0;
    db.with_transaction(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_allowed(conn, domain.as_str())
                .map_err(AppError::from)?;
            crate::db::domains::add_allowed(conn, domain.as_str(), args.description.as_deref(), None)
                .map_err(AppError::from)?;
            if existed { skipped += 1; } else { imported += 1; }
        }
        Ok(())
    })?;

    let result = ImportExportResult { command: "allowlist import", count: imported, path: None };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_export(db: &Database, args: AllowlistExportArgs) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;
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

    let result = ImportExportResult { command: "allowlist export", count: domains.len(), path };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct ListModResult { command: &'static str, added: Vec<String>, skipped: Vec<String>, errors: Vec<String> }
impl Renderable for ListModResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "added": self.added, "skipped": self.skipped, "errors": self.errors },
            "summary": { "added": self.added.len(), "skipped": self.skipped.len() }
        })
    }
}

struct RemoveResult { command: &'static str, removed: Vec<String>, not_found: Vec<String> }
impl Renderable for RemoveResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "removed": self.removed, "not_found": self.not_found },
            "summary": { "removed": self.removed.len() }
        })
    }
}

struct AllowlistListResult { domains: Vec<crate::types::AllowedDomain>, active_count: usize }
impl Renderable for AllowlistListResult {
    fn command_name(&self) -> &str { "allowlist list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "domains": self.domains },
            "summary": { "total": self.domains.len(), "active": self.active_count }
        })
    }
}

struct ImportExportResult { command: &'static str, count: usize, path: Option<String> }
impl Renderable for ImportExportResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "count": self.count, "path": self.path }, "summary": { "exported": self.count } })
    }
}
