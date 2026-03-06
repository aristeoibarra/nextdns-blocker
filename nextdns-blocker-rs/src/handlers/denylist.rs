use crate::cli::denylist::*;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode, ValidationDetail};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: DenylistCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db = open_db()?;
    match cmd {
        DenylistCommands::Add(args) => handle_add(&db, args, format),
        DenylistCommands::Remove(args) => handle_remove(&db, args, format),
        DenylistCommands::List(args) => handle_list(&db, args, format),
        DenylistCommands::Import(args) => handle_import(&db, args, format),
        DenylistCommands::Export(args) => handle_export(&db, args, format),
    }
}

fn open_db() -> Result<Database, AppError> {
    Database::open(&crate::common::platform::db_path())
}

fn handle_add(
    db: &Database,
    args: DenylistAddArgs,
    format: ResolvedFormat,
) -> Result<ExitCode, AppError> {
    let (valid, errors) = parse_domains(&args.domains);

    if valid.is_empty() && !errors.is_empty() {
        return Err(AppError::Validation {
            message: "No valid domains provided".to_string(),
            details: errors
                .iter()
                .map(|(d, r)| ValidationDetail {
                    field: d.clone(),
                    reason: r.clone(),
                })
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
                conn,
                domain.as_str(),
                args.description.as_deref(),
                args.category.as_deref(),
                args.schedule.as_deref(),
            )?;
            if existed {
                skipped.push(domain.to_string());
            } else {
                added.push(domain.to_string());
            }
            // Audit log
            crate::db::audit::log_action(conn, "add", "denylist", domain.as_str(), None)?;
        }
        Ok(())
    })?;

    let result = DenylistAddResult {
        added,
        skipped,
        errors: errors.iter().map(|(d, r)| format!("{d}: {r}")).collect(),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct DenylistAddResult {
    added: Vec<String>,
    skipped: Vec<String>,
    errors: Vec<String>,
}

impl Renderable for DenylistAddResult {
    fn command_name(&self) -> &str {
        "denylist add"
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "added": self.added, "skipped": self.skipped, "errors": self.errors },
            "summary": { "added": self.added.len(), "skipped": self.skipped.len(), "errors": self.errors.len() }
        })
    }
    fn to_human(&self) -> String {
        let mut out = String::new();
        for d in &self.added {
            out.push_str(&format!("  + {d}\n"));
        }
        for d in &self.skipped {
            out.push_str(&format!("  ~ {d} (already blocked)\n"));
        }
        for e in &self.errors {
            out.push_str(&format!("  ! {e}\n"));
        }
        if self.added.is_empty() && self.skipped.is_empty() {
            out.push_str("  No domains added.\n");
        }
        out
    }
}

fn handle_remove(
    db: &Database,
    args: DenylistRemoveArgs,
    format: ResolvedFormat,
) -> Result<ExitCode, AppError> {
    // Check protection
    let locked = crate::protection::validate_no_locked_removal(db, &args.domains)?;
    if !locked.is_empty() {
        return Err(AppError::Permission {
            message: format!("Protected domains cannot be removed: {}", locked.join(", ")),
            hint: Some("Use 'ndb protection unlock-request' to request removal".to_string()),
        });
    }

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

    let result = DenylistRemoveResult {
        removed,
        not_found,
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct DenylistRemoveResult {
    removed: Vec<String>,
    not_found: Vec<String>,
}

impl Renderable for DenylistRemoveResult {
    fn command_name(&self) -> &str {
        "denylist remove"
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "removed": self.removed, "not_found": self.not_found },
            "summary": { "removed": self.removed.len(), "not_found": self.not_found.len() }
        })
    }
    fn to_human(&self) -> String {
        let mut out = String::new();
        for d in &self.removed {
            out.push_str(&format!("  - {d}\n"));
        }
        for d in &self.not_found {
            out.push_str(&format!("  ? {d} (not found)\n"));
        }
        out
    }
}

fn handle_list(
    db: &Database,
    args: DenylistListArgs,
    format: ResolvedFormat,
) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| {
        let all = crate::db::domains::list_blocked(conn, !args.all)?;
        if let Some(ref cat) = args.category {
            Ok(all
                .into_iter()
                .filter(|d| d.category.as_deref() == Some(cat.as_str()))
                .collect::<Vec<_>>())
        } else {
            Ok(all)
        }
    })?;

    let active_count = domains.iter().filter(|d| d.active).count();
    let result = DenylistListResult {
        domains,
        active_count,
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct DenylistListResult {
    domains: Vec<crate::types::BlockedDomain>,
    active_count: usize,
}

impl Renderable for DenylistListResult {
    fn command_name(&self) -> &str {
        "denylist list"
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "domains": self.domains },
            "summary": { "total": self.domains.len(), "active": self.active_count }
        })
    }
    fn to_human(&self) -> String {
        if self.domains.is_empty() {
            return "  No domains in denylist.\n".to_string();
        }
        let mut out = String::new();
        for d in &self.domains {
            let status = if d.active { "+" } else { "-" };
            let desc = d
                .description
                .as_deref()
                .map(|s| format!(" ({s})"))
                .unwrap_or_default();
            let cat = d
                .category
                .as_deref()
                .map(|s| format!(" [{s}]"))
                .unwrap_or_default();
            out.push_str(&format!("  {status} {}{desc}{cat}\n", d.domain));
        }
        out.push_str(&format!(
            "\n  Total: {} ({} active)\n",
            self.domains.len(),
            self.active_count
        ));
        out
    }
}

fn handle_import(
    db: &Database,
    args: DenylistImportArgs,
    format: ResolvedFormat,
) -> Result<ExitCode, AppError> {
    let content = std::fs::read_to_string(&args.file).map_err(|e| AppError::General {
        message: format!("Failed to read file '{}': {e}", args.file),
        hint: None,
    })?;

    let lines: Vec<String> = content
        .lines()
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .collect();

    let (valid, errors) = parse_domains(&lines);

    let mut imported = 0;
    let mut skipped = 0;

    db.with_conn(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_blocked(conn, domain.as_str())?;
            crate::db::domains::add_blocked(
                conn,
                domain.as_str(),
                args.description.as_deref(),
                None,
                None,
            )?;
            if existed {
                skipped += 1;
            } else {
                imported += 1;
            }
        }
        Ok(())
    })?;

    let result = ImportResult {
        imported,
        skipped,
        errors: errors.len(),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct ImportResult {
    imported: usize,
    skipped: usize,
    errors: usize,
}

impl Renderable for ImportResult {
    fn command_name(&self) -> &str {
        "denylist import"
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "imported": self.imported, "skipped": self.skipped, "errors": self.errors },
            "summary": { "imported": self.imported, "skipped": self.skipped }
        })
    }
    fn to_human(&self) -> String {
        format!(
            "  Imported: {}, Skipped: {}, Errors: {}\n",
            self.imported, self.skipped, self.errors
        )
    }
}

fn handle_export(
    db: &Database,
    args: DenylistExportArgs,
    format: ResolvedFormat,
) -> Result<ExitCode, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;

    let output_str = if args.format == "json" {
        serde_json::to_string_pretty(&domains)?
    } else {
        domains
            .iter()
            .map(|d| d.domain.as_str())
            .collect::<Vec<_>>()
            .join("\n")
            + "\n"
    };

    if let Some(ref path) = args.file {
        std::fs::write(path, &output_str)?;
        let result = ExportResult {
            path: Some(path.clone()),
            count: domains.len(),
        };
        output::render(&result, format);
    } else {
        let result = ExportResult {
            path: None,
            count: domains.len(),
        };
        output::render(&result, format);
    }

    Ok(ExitCode::Success)
}

struct ExportResult {
    path: Option<String>,
    count: usize,
}

impl Renderable for ExportResult {
    fn command_name(&self) -> &str {
        "denylist export"
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "path": self.path, "count": self.count },
            "summary": { "exported": self.count }
        })
    }
    fn to_human(&self) -> String {
        match &self.path {
            Some(p) => format!("  Exported {} domains to {}\n", self.count, p),
            None => format!("  Exported {} domains to stdout\n", self.count),
        }
    }
}
