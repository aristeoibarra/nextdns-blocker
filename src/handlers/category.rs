use crate::cli::category::*;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: CategoryCommands) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        CategoryCommands::Create(args) => handle_create(&db, args),
        CategoryCommands::Delete(args) => handle_delete(&db, args),
        CategoryCommands::List(_) => handle_list(&db),
        CategoryCommands::Show(args) => handle_show(&db, args),
        CategoryCommands::AddDomain(args) => handle_add_domain(&db, args),
        CategoryCommands::RemoveDomain(args) => handle_remove_domain(&db, args),
    }
}

fn handle_create(db: &Database, args: CategoryCreateArgs) -> Result<ExitCode, AppError> {
    let exists = db.with_conn(|conn| crate::db::categories::get_category(conn, &args.name))?;
    if exists.is_some() {
        return Err(AppError::Conflict {
            message: format!("Category '{}' already exists", args.name),
            hint: Some("Use a different name or delete the existing category first".to_string()),
        });
    }

    let id = db.with_transaction(|conn| {
        let id = crate::db::categories::create_category(conn, &args.name, args.description.as_deref(), args.schedule.as_deref())
            .map_err(AppError::from)?;
        crate::db::audit::log_action(conn, "create", "category", &args.name, None)
            .map_err(AppError::from)?;
        Ok(id)
    })?;

    let result = SimpleResult { command: "category create", data: serde_json::json!({ "id": id, "name": args.name }), summary: serde_json::json!({ "created": 1 }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_delete(db: &Database, args: CategoryDeleteArgs) -> Result<ExitCode, AppError> {
    let deleted = db.with_conn(|conn| crate::db::categories::delete_category(conn, &args.name))?;
    if !deleted {
        return Err(AppError::NotFound {
            message: format!("Category '{}' not found", args.name),
            hint: Some("Use 'ndb category list' to see available categories".to_string()),
        });
    }

    db.with_conn(|conn| crate::db::audit::log_action(conn, "delete", "category", &args.name, None))?;

    let result = SimpleResult { command: "category delete", data: serde_json::json!({ "name": args.name }), summary: serde_json::json!({ "deleted": 1 }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_list(db: &Database) -> Result<ExitCode, AppError> {
    let categories = db.with_conn(crate::db::categories::list_categories)?;
    let result = CategoryListResult { categories };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct CategoryListResult { categories: Vec<crate::types::Category> }
impl Renderable for CategoryListResult {
    fn command_name(&self) -> &str { "category list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "categories": self.categories },
            "summary": { "total": self.categories.len() }
        })
    }
}

fn handle_show(db: &Database, args: CategoryShowArgs) -> Result<ExitCode, AppError> {
    let cat = db.with_conn(|conn| crate::db::categories::get_category(conn, &args.name))?
        .ok_or_else(|| AppError::NotFound {
            message: format!("Category '{}' not found", args.name),
            hint: Some("Use 'ndb category list' to see available categories".to_string()),
        })?;

    let domains = db.with_conn(|conn| crate::db::categories::list_category_domains(conn, &args.name))?;

    let result = CategoryShowResult { category: cat, domains };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct CategoryShowResult { category: crate::types::Category, domains: Vec<String> }
impl Renderable for CategoryShowResult {
    fn command_name(&self) -> &str { "category show" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": {
                "name": self.category.name, "description": self.category.description,
                "schedule": self.category.schedule,
                "domains": self.domains,
            },
            "summary": { "domain_count": self.domains.len() }
        })
    }
}

fn handle_add_domain(db: &Database, args: CategoryAddDomainArgs) -> Result<ExitCode, AppError> {
    let (valid, errors) = parse_domains(&args.domains);

    if valid.is_empty() && !errors.is_empty() {
        return Err(AppError::Validation {
            message: "No valid domains provided".to_string(),
            details: errors
                .iter()
                .map(|(d, r)| crate::error::ValidationDetail { field: d.clone(), reason: r.clone() })
                .collect(),
            hint: Some("Domains must be valid RFC 1123 hostnames (e.g., example.com)".to_string()),
        });
    }

    let mut added = Vec::new();
    let mut skipped = Vec::new();

    db.with_transaction(|conn| {
        for domain in &valid {
            let ok = crate::db::categories::add_domain_to_category(conn, &args.category, domain.as_str())
                .map_err(AppError::from)?;
            if ok { added.push(domain.to_string()); } else { skipped.push(domain.to_string()); }
        }
        Ok(())
    })?;

    if added.is_empty() && !valid.is_empty() {
        return Err(AppError::NotFound {
            message: format!("Category '{}' not found", args.category),
            hint: Some("Create the category first with 'ndb category create'".to_string()),
        });
    }

    let validation_errors: Vec<String> = errors.iter().map(|(d, r)| format!("{d}: {r}")).collect();
    let result = SimpleResult {
        command: "category add-domain",
        data: serde_json::json!({ "added": added, "skipped": skipped, "errors": validation_errors }),
        summary: serde_json::json!({ "added": added.len(), "errors": validation_errors.len() }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_remove_domain(db: &Database, args: CategoryRemoveDomainArgs) -> Result<ExitCode, AppError> {
    let mut removed = Vec::new();
    db.with_transaction(|conn| {
        for domain in &args.domains {
            let d = domain.to_lowercase();
            let ok = crate::db::categories::remove_domain_from_category(conn, &args.category, &d)
                .map_err(AppError::from)?;
            if ok { removed.push(d); }
        }
        Ok(())
    })?;

    let result = SimpleResult {
        command: "category remove-domain",
        data: serde_json::json!({ "removed": removed }),
        summary: serde_json::json!({ "removed": removed.len() }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct SimpleResult { command: &'static str, data: serde_json::Value, summary: serde_json::Value }
impl Renderable for SimpleResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": self.data, "summary": self.summary })
    }
}
