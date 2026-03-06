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

    db.with_conn(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_blocked(conn, domain.as_str())?;
            crate::db::domains::add_blocked(
                conn, domain.as_str(), args.description.as_deref(),
                args.category.as_deref(), args.schedule.as_deref(),
            )?;
            if existed { skipped.push(domain.to_string()); }
            else { added.push(domain.to_string()); }
            crate::db::audit::log_action(conn, "add", "denylist", domain.as_str(), None)?;
        }
        Ok(())
    })?;

    let result = DenylistAddResult {
        added, skipped,
        errors: errors.iter().map(|(d, r)| format!("{d}: {r}")).collect(),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct DenylistAddResult { added: Vec<String>, skipped: Vec<String>, errors: Vec<String> }
impl Renderable for DenylistAddResult {
    fn command_name(&self) -> &str { "denylist add" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "added": self.added, "skipped": self.skipped, "errors": self.errors },
            "summary": { "added": self.added.len(), "skipped": self.skipped.len(), "errors": self.errors.len() }
        })
    }
}

fn handle_remove(db: &Database, args: DenylistRemoveArgs) -> Result<ExitCode, AppError> {
    let mut removed = Vec::new();
    let mut not_found = Vec::new();

    db.with_conn(|conn| {
        for domain in &args.domains {
            let domain_lower = domain.to_lowercase();
            if crate::db::domains::remove_blocked(conn, &domain_lower)? {
                crate::db::audit::log_action(conn, "remove", "denylist", &domain_lower, None)?;
                removed.push(domain_lower);
            } else {
                not_found.push(domain.clone());
            }
        }
        Ok(())
    })?;

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
        message: format!("Failed to read file '{}': {e}", args.file), hint: None,
    })?;

    let lines: Vec<String> = content.lines()
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .collect();

    let (valid, errors) = parse_domains(&lines);

    let mut imported = 0;
    let mut skipped = 0;

    db.with_conn(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_blocked(conn, domain.as_str())?;
            crate::db::domains::add_blocked(conn, domain.as_str(), args.description.as_deref(), None, None)?;
            if existed { skipped += 1; } else { imported += 1; }
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
