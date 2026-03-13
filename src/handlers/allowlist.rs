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

    // Validate duration upfront before any DB writes
    let parsed_duration = if let Some(ref dur_str) = args.duration {
        Some(crate::common::time::parse_duration(dur_str)?)
    } else {
        None
    };

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

    // Create pending removal actions for --duration
    let mut pending_ids = Vec::new();
    let mut watchdog_warning = None;
    if let Some(ref dur_str) = args.duration {
        let duration = parsed_duration.expect("validated above");
        let execute_at = crate::common::time::now_unix() + duration.as_secs() as i64;

        db.with_transaction(|conn| {
            for domain in &added {
                let id = uuid::Uuid::new_v4().to_string();
                crate::db::pending::create_pending(
                    conn, &id, "remove", Some(domain), "allowlist", execute_at,
                    Some(&format!("Auto remove from allowlist after {dur_str}")),
                ).map_err(AppError::from)?;
                pending_ids.push(id);
            }
            Ok(())
        })?;

        if let Ok(status) = crate::watchdog::status() {
            if !status.healthy {
                watchdog_warning = Some("Watchdog unhealthy — temp allow may not expire automatically. Run 'ndb fix' or 'ndb watchdog install --interval 5m'".to_string());
            }
        }
    }

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

    let result = AllowlistAddResult {
        added, skipped,
        errors: errors.iter().map(|(d,r)| format!("{d}: {r}")).collect(),
        duration: args.duration, pending_ids, watchdog_warning,
    };
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
                not_found.push(d);
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
    let content = std::fs::read_to_string(&args.file).map_err(|e| AppError::General { message: format!("Failed to read file '{}': {e}", args.file), hint: Some("Ensure the file exists and is readable".to_string()) })?;
    let lines: Vec<String> = content.lines().map(|l| l.trim().to_string()).filter(|l| !l.is_empty() && !l.starts_with('#')).collect();
    let (valid, errors) = parse_domains(&lines);

    let mut imported = 0;
    let mut skipped = 0;
    db.with_transaction(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_allowed(conn, domain.as_str())
                .map_err(AppError::from)?;
            crate::db::domains::add_allowed(conn, domain.as_str(), args.description.as_deref(), None)
                .map_err(AppError::from)?;
            if existed {
                skipped += 1;
            } else {
                imported += 1;
                crate::db::audit::log_action(conn, "import", "allowlist", domain.as_str(), None)
                    .map_err(AppError::from)?;
            }
        }
        Ok(())
    })?;

    let result = AllowlistImportResult { imported, skipped, errors: errors.len() };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct AllowlistImportResult { imported: usize, skipped: usize, errors: usize }
impl Renderable for AllowlistImportResult {
    fn command_name(&self) -> &str { "allowlist import" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "imported": self.imported, "skipped": self.skipped, "errors": self.errors },
            "summary": { "imported": self.imported, "skipped": self.skipped }
        })
    }
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

struct AllowlistAddResult {
    added: Vec<String>,
    skipped: Vec<String>,
    errors: Vec<String>,
    duration: Option<String>,
    pending_ids: Vec<String>,
    watchdog_warning: Option<String>,
}
impl Renderable for AllowlistAddResult {
    fn command_name(&self) -> &str { "allowlist add" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": {
                "added": self.added, "skipped": self.skipped, "errors": self.errors,
                "duration": self.duration, "pending_ids": self.pending_ids,
                "watchdog_warning": self.watchdog_warning,
            },
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
