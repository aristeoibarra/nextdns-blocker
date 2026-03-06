use crate::cli::category::*;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: CategoryCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        CategoryCommands::Create(args) => handle_create(&db, args, format),
        CategoryCommands::Delete(args) => handle_delete(&db, args, format),
        CategoryCommands::List(_) => handle_list(&db, format),
        CategoryCommands::Show(args) => handle_show(&db, args, format),
        CategoryCommands::AddDomain(args) => handle_add_domain(&db, args, format),
        CategoryCommands::RemoveDomain(args) => handle_remove_domain(&db, args, format),
    }
}

fn handle_create(db: &Database, args: CategoryCreateArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    // Check if exists
    let exists = db.with_conn(|conn| crate::db::categories::get_category(conn, &args.name))?;
    if exists.is_some() {
        return Err(AppError::Conflict {
            message: format!("Category '{}' already exists", args.name),
            hint: Some("Use a different name or delete the existing category first".to_string()),
        });
    }

    let id = db.with_conn(|conn| {
        crate::db::categories::create_category(conn, &args.name, args.description.as_deref(), args.schedule.as_deref())
    })?;

    db.with_conn(|conn| crate::db::audit::log_action(conn, "create", "category", &args.name, None))?;

    let result = SimpleResult { command: "category create", data: serde_json::json!({ "id": id, "name": args.name }), summary: serde_json::json!({ "created": 1 }), human: format!("  Created category '{}'\n", args.name) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_delete(db: &Database, args: CategoryDeleteArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    // Check if locked
    if crate::protection::is_locked(db, "category", &args.name)? {
        return Err(AppError::Permission {
            message: format!("Category '{}' is locked", args.name),
            hint: Some("Use 'ndb protection unlock-request' to request removal".to_string()),
        });
    }

    let deleted = db.with_conn(|conn| crate::db::categories::delete_category(conn, &args.name))?;
    if !deleted {
        return Err(AppError::NotFound {
            message: format!("Category '{}' not found", args.name),
            hint: Some("Use 'ndb category list' to see available categories".to_string()),
        });
    }

    db.with_conn(|conn| crate::db::audit::log_action(conn, "delete", "category", &args.name, None))?;

    let result = SimpleResult { command: "category delete", data: serde_json::json!({ "name": args.name }), summary: serde_json::json!({ "deleted": 1 }), human: format!("  Deleted category '{}'\n", args.name) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_list(db: &Database, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let categories = db.with_conn(|conn| crate::db::categories::list_categories(conn))?;

    let result = CategoryListResult { categories };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct CategoryListResult {
    categories: Vec<crate::types::Category>,
}

impl Renderable for CategoryListResult {
    fn command_name(&self) -> &str { "category list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "categories": self.categories },
            "summary": { "total": self.categories.len() }
        })
    }
    fn to_human(&self) -> String {
        if self.categories.is_empty() { return "  No categories.\n".to_string(); }
        let mut out = String::new();
        for c in &self.categories {
            let lock = if c.is_locked { " [locked]" } else { "" };
            let desc = c.description.as_deref().map(|s| format!(" - {s}")).unwrap_or_default();
            out.push_str(&format!("  {}{desc}{lock}\n", c.name));
        }
        out
    }
}

fn handle_show(db: &Database, args: CategoryShowArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let cat = db.with_conn(|conn| crate::db::categories::get_category(conn, &args.name))?
        .ok_or_else(|| AppError::NotFound {
            message: format!("Category '{}' not found", args.name),
            hint: Some("Use 'ndb category list' to see available categories".to_string()),
        })?;

    let domains = db.with_conn(|conn| crate::db::categories::list_category_domains(conn, &args.name))?;

    let result = CategoryShowResult { category: cat, domains };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct CategoryShowResult {
    category: crate::types::Category,
    domains: Vec<String>,
}

impl Renderable for CategoryShowResult {
    fn command_name(&self) -> &str { "category show" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": {
                "name": self.category.name,
                "description": self.category.description,
                "is_locked": self.category.is_locked,
                "schedule": self.category.schedule,
                "domains": self.domains,
            },
            "summary": { "domain_count": self.domains.len() }
        })
    }
    fn to_human(&self) -> String {
        let mut out = format!("  Category: {}\n", self.category.name);
        if let Some(ref d) = self.category.description { out.push_str(&format!("  Description: {d}\n")); }
        out.push_str(&format!("  Locked: {}\n", self.category.is_locked));
        out.push_str(&format!("  Domains ({}):\n", self.domains.len()));
        for d in &self.domains { out.push_str(&format!("    {d}\n")); }
        out
    }
}

fn handle_add_domain(db: &Database, args: CategoryAddDomainArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let (valid, _errors) = parse_domains(&args.domains);
    let mut added = Vec::new();
    let mut skipped = Vec::new();

    for domain in &valid {
        let ok = db.with_conn(|conn| crate::db::categories::add_domain_to_category(conn, &args.category, domain.as_str()))?;
        if ok { added.push(domain.to_string()); } else { skipped.push(domain.to_string()); }
    }

    if added.is_empty() && !valid.is_empty() {
        return Err(AppError::NotFound {
            message: format!("Category '{}' not found", args.category),
            hint: Some("Create the category first with 'ndb category create'".to_string()),
        });
    }

    let result = SimpleResult {
        command: "category add-domain",
        data: serde_json::json!({ "added": added, "skipped": skipped }),
        summary: serde_json::json!({ "added": added.len() }),
        human: format!("  Added {} domain(s) to '{}'\n", added.len(), args.category),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_remove_domain(db: &Database, args: CategoryRemoveDomainArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let mut removed = Vec::new();
    for domain in &args.domains {
        let d = domain.to_lowercase();
        let ok = db.with_conn(|conn| crate::db::categories::remove_domain_from_category(conn, &args.category, &d))?;
        if ok { removed.push(d); }
    }

    let result = SimpleResult {
        command: "category remove-domain",
        data: serde_json::json!({ "removed": removed }),
        summary: serde_json::json!({ "removed": removed.len() }),
        human: format!("  Removed {} domain(s) from '{}'\n", removed.len(), args.category),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

// Generic result type for simple commands
struct SimpleResult {
    command: &'static str,
    data: serde_json::Value,
    summary: serde_json::Value,
    human: String,
}

impl Renderable for SimpleResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": self.data, "summary": self.summary })
    }
    fn to_human(&self) -> String { self.human.clone() }
}
