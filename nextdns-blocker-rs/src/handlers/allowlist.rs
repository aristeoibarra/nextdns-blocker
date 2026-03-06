use crate::cli::allowlist::*;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode, ValidationDetail};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: AllowlistCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        AllowlistCommands::Add(args) => handle_add(&db, args, format),
        AllowlistCommands::Remove(args) => handle_remove(&db, args, format),
        AllowlistCommands::List(args) => handle_list(&db, args, format),
        AllowlistCommands::Import(args) => handle_import(&db, args, format),
        AllowlistCommands::Export(args) => handle_export(&db, args, format),
    }
}

fn handle_add(db: &Database, args: AllowlistAddArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
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

    db.with_conn(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_allowed(conn, domain.as_str())?;
            crate::db::domains::add_allowed(conn, domain.as_str(), args.description.as_deref())?;
            if existed { skipped.push(domain.to_string()); }
            else { added.push(domain.to_string()); }
            crate::db::audit::log_action(conn, "add", "allowlist", domain.as_str(), None)?;
        }
        Ok(())
    })?;

    let result = ListModResult { command: "allowlist add", added, skipped, errors: errors.iter().map(|(d,r)| format!("{d}: {r}")).collect() };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_remove(db: &Database, args: AllowlistRemoveArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let mut removed = Vec::new();
    let mut not_found = Vec::new();

    db.with_conn(|conn| {
        for domain in &args.domains {
            let d = domain.to_lowercase();
            if crate::db::domains::remove_allowed(conn, &d)? {
                crate::db::audit::log_action(conn, "remove", "allowlist", &d, None)?;
                removed.push(d);
            } else {
                not_found.push(domain.clone());
            }
        }
        Ok(())
    })?;

    let result = RemoveResult { command: "allowlist remove", removed, not_found };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_list(db: &Database, args: AllowlistListArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_allowed(conn, !args.all))?;
    let active_count = domains.iter().filter(|d| d.active).count();

    let result = AllowlistListResult { domains, active_count };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_import(db: &Database, args: AllowlistImportArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let content = std::fs::read_to_string(&args.file).map_err(|e| AppError::General { message: format!("Failed to read file: {e}"), hint: None })?;
    let lines: Vec<String> = content.lines().map(|l| l.trim().to_string()).filter(|l| !l.is_empty() && !l.starts_with('#')).collect();
    let (valid, _errors) = parse_domains(&lines);

    let mut imported = 0;
    let mut skipped = 0;
    db.with_conn(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_allowed(conn, domain.as_str())?;
            crate::db::domains::add_allowed(conn, domain.as_str(), args.description.as_deref())?;
            if existed { skipped += 1; } else { imported += 1; }
        }
        Ok(())
    })?;

    let result = ImportExportResult { command: "allowlist import", count: imported, path: None };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_export(db: &Database, args: AllowlistExportArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;
    let output_str = if args.format == "json" {
        serde_json::to_string_pretty(&domains)?
    } else {
        domains.iter().map(|d| d.domain.as_str()).collect::<Vec<_>>().join("\n") + "\n"
    };

    if let Some(ref path) = args.file {
        std::fs::write(path, &output_str)?;
        let result = ImportExportResult { command: "allowlist export", count: domains.len(), path: Some(path.clone()) };
        output::render(&result, format);
    } else {
        let result = ImportExportResult { command: "allowlist export", count: domains.len(), path: None };
        output::render(&result, format);
    }
    Ok(ExitCode::Success)
}

// Shared result types

struct ListModResult {
    command: &'static str,
    added: Vec<String>,
    skipped: Vec<String>,
    errors: Vec<String>,
}

impl Renderable for ListModResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "added": self.added, "skipped": self.skipped, "errors": self.errors },
            "summary": { "added": self.added.len(), "skipped": self.skipped.len() }
        })
    }
    fn to_human(&self) -> String {
        let mut out = String::new();
        for d in &self.added { out.push_str(&format!("  + {d}\n")); }
        for d in &self.skipped { out.push_str(&format!("  ~ {d} (exists)\n")); }
        for e in &self.errors { out.push_str(&format!("  ! {e}\n")); }
        out
    }
}

struct RemoveResult {
    command: &'static str,
    removed: Vec<String>,
    not_found: Vec<String>,
}

impl Renderable for RemoveResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "removed": self.removed, "not_found": self.not_found },
            "summary": { "removed": self.removed.len() }
        })
    }
    fn to_human(&self) -> String {
        let mut out = String::new();
        for d in &self.removed { out.push_str(&format!("  - {d}\n")); }
        for d in &self.not_found { out.push_str(&format!("  ? {d} (not found)\n")); }
        out
    }
}

struct AllowlistListResult {
    domains: Vec<crate::types::AllowedDomain>,
    active_count: usize,
}

impl Renderable for AllowlistListResult {
    fn command_name(&self) -> &str { "allowlist list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "domains": self.domains },
            "summary": { "total": self.domains.len(), "active": self.active_count }
        })
    }
    fn to_human(&self) -> String {
        if self.domains.is_empty() { return "  No domains in allowlist.\n".to_string(); }
        let mut out = String::new();
        for d in &self.domains {
            let status = if d.active { "+" } else { "-" };
            let desc = d.description.as_deref().map(|s| format!(" ({s})")).unwrap_or_default();
            out.push_str(&format!("  {status} {}{desc}\n", d.domain));
        }
        out.push_str(&format!("\n  Total: {} ({} active)\n", self.domains.len(), self.active_count));
        out
    }
}

struct ImportExportResult {
    command: &'static str,
    count: usize,
    path: Option<String>,
}

impl Renderable for ImportExportResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "count": self.count, "path": self.path }, "summary": { "exported": self.count } })
    }
    fn to_human(&self) -> String {
        match &self.path {
            Some(p) => format!("  {}: {} domains to {}\n", self.command, self.count, p),
            None => format!("  {}: {} domains to stdout\n", self.command, self.count),
        }
    }
}
