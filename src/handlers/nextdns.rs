use crate::cli::nextdns::*;
use crate::config::constants::{NEXTDNS_CATEGORIES, NEXTDNS_SERVICES};
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: NextdnsCommands) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        NextdnsCommands::List(_) => handle_list(&db),
        NextdnsCommands::AddCategory(args) => handle_add_category(&db, args),
        NextdnsCommands::RemoveCategory(args) => handle_remove_category(&db, args),
        NextdnsCommands::AddService(args) => handle_add_service(&db, args),
        NextdnsCommands::RemoveService(args) => handle_remove_service(&db, args),
        NextdnsCommands::Categories(_) => handle_available_categories(),
        NextdnsCommands::Services(_) => handle_available_services(),
    }
}

fn handle_list(db: &Database) -> Result<ExitCode, AppError> {
    let categories = db.with_conn(crate::db::nextdns::list_nextdns_categories)?;
    let services = db.with_conn(crate::db::nextdns::list_nextdns_services)?;

    let result = NextdnsListResult { categories, services };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct NextdnsListResult { categories: Vec<crate::types::NextDnsCategory>, services: Vec<crate::types::NextDnsService> }
impl Renderable for NextdnsListResult {
    fn command_name(&self) -> &str { "nextdns list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "categories": self.categories, "services": self.services },
            "summary": { "categories": self.categories.len(), "services": self.services.len() }
        })
    }
}

fn handle_add_category(db: &Database, args: NextdnsAddCategoryArgs) -> Result<ExitCode, AppError> {
    validate_category_id(&args.id)?;
    db.with_conn(|conn| crate::db::nextdns::add_nextdns_category(conn, &args.id))?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "add", "nextdns_category", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns add-category", data: serde_json::json!({ "id": args.id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_remove_category(db: &Database, args: NextdnsRemoveCategoryArgs) -> Result<ExitCode, AppError> {
    let removed = db.with_conn(|conn| crate::db::nextdns::remove_nextdns_category(conn, &args.id))?;
    if !removed {
        return Err(AppError::NotFound { message: format!("NextDNS category '{}' not found", args.id), hint: None });
    }
    db.with_conn(|conn| crate::db::audit::log_action(conn, "remove", "nextdns_category", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns remove-category", data: serde_json::json!({ "id": args.id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_add_service(db: &Database, args: NextdnsAddServiceArgs) -> Result<ExitCode, AppError> {
    validate_service_id(&args.id)?;
    db.with_conn(|conn| crate::db::nextdns::add_nextdns_service(conn, &args.id))?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "add", "nextdns_service", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns add-service", data: serde_json::json!({ "id": args.id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_remove_service(db: &Database, args: NextdnsRemoveServiceArgs) -> Result<ExitCode, AppError> {
    let removed = db.with_conn(|conn| crate::db::nextdns::remove_nextdns_service(conn, &args.id))?;
    if !removed {
        return Err(AppError::NotFound { message: format!("NextDNS service '{}' not found", args.id), hint: None });
    }
    db.with_conn(|conn| crate::db::audit::log_action(conn, "remove", "nextdns_service", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns remove-service", data: serde_json::json!({ "id": args.id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_available_categories() -> Result<ExitCode, AppError> {
    let cats: Vec<serde_json::Value> = NEXTDNS_CATEGORIES.iter()
        .map(|(id, name)| serde_json::json!({ "id": id, "name": name }))
        .collect();
    let result = SimpleMsg { command: "nextdns categories", data: serde_json::json!({ "categories": cats }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_available_services() -> Result<ExitCode, AppError> {
    let svcs: Vec<serde_json::Value> = NEXTDNS_SERVICES.iter()
        .map(|(id, name)| serde_json::json!({ "id": id, "name": name }))
        .collect();
    let result = SimpleMsg { command: "nextdns services", data: serde_json::json!({ "services": svcs }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn validate_category_id(id: &str) -> Result<(), AppError> {
    if NEXTDNS_CATEGORIES.iter().any(|(cid, _)| *cid == id) { return Ok(()); }
    let valid: Vec<&str> = NEXTDNS_CATEGORIES.iter().map(|(id, _)| *id).collect();
    Err(AppError::Validation {
        message: format!("Unknown NextDNS category: {id}"),
        details: vec![],
        hint: Some(format!("Valid categories: {}", valid.join(", "))),
    })
}

fn validate_service_id(id: &str) -> Result<(), AppError> {
    if NEXTDNS_SERVICES.iter().any(|(sid, _)| *sid == id) { return Ok(()); }
    Err(AppError::Validation {
        message: format!("Unknown NextDNS service: {id}"),
        details: vec![],
        hint: Some("Use 'ndb nextdns services' to see available services".to_string()),
    })
}

struct SimpleMsg { command: &'static str, data: serde_json::Value }
impl Renderable for SimpleMsg {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
}
