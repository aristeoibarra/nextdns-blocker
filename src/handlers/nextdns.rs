use crate::cli::nextdns::*;
use crate::config::constants::{NEXTDNS_CATEGORIES, NEXTDNS_SERVICES};
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: NextdnsCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        NextdnsCommands::List(_) => handle_list(&db, format),
        NextdnsCommands::AddCategory(args) => handle_add_category(&db, args, format),
        NextdnsCommands::RemoveCategory(args) => handle_remove_category(&db, args, format),
        NextdnsCommands::AddService(args) => handle_add_service(&db, args, format),
        NextdnsCommands::RemoveService(args) => handle_remove_service(&db, args, format),
        NextdnsCommands::Categories(_) => handle_available_categories(format),
        NextdnsCommands::Services(_) => handle_available_services(format),
    }
}

fn handle_list(db: &Database, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let categories = db.with_conn(crate::db::nextdns::list_nextdns_categories)?;
    let services = db.with_conn(crate::db::nextdns::list_nextdns_services)?;

    let result = NextdnsListResult { categories, services };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct NextdnsListResult {
    categories: Vec<crate::types::NextDnsCategory>,
    services: Vec<crate::types::NextDnsService>,
}

impl Renderable for NextdnsListResult {
    fn command_name(&self) -> &str { "nextdns list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "categories": self.categories, "services": self.services },
            "summary": { "categories": self.categories.len(), "services": self.services.len() }
        })
    }
    fn to_human(&self) -> String {
        let mut out = String::from("  Categories:\n");
        for c in &self.categories { out.push_str(&format!("    {} (active: {})\n", c.id, c.active)); }
        out.push_str("  Services:\n");
        for s in &self.services { out.push_str(&format!("    {} (active: {})\n", s.id, s.active)); }
        out
    }
}

fn handle_add_category(db: &Database, args: NextdnsAddCategoryArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    validate_category_id(&args.id)?;
    db.with_conn(|conn| crate::db::nextdns::add_nextdns_category(conn, &args.id))?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "add", "nextdns_category", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns add-category", data: serde_json::json!({ "id": args.id }), msg: format!("  Added NextDNS category '{}'\n", args.id) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_remove_category(db: &Database, args: NextdnsRemoveCategoryArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let removed = db.with_conn(|conn| crate::db::nextdns::remove_nextdns_category(conn, &args.id))?;
    if !removed {
        return Err(AppError::NotFound { message: format!("NextDNS category '{}' not found", args.id), hint: None });
    }
    db.with_conn(|conn| crate::db::audit::log_action(conn, "remove", "nextdns_category", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns remove-category", data: serde_json::json!({ "id": args.id }), msg: format!("  Removed NextDNS category '{}'\n", args.id) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_add_service(db: &Database, args: NextdnsAddServiceArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    validate_service_id(&args.id)?;
    db.with_conn(|conn| crate::db::nextdns::add_nextdns_service(conn, &args.id))?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "add", "nextdns_service", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns add-service", data: serde_json::json!({ "id": args.id }), msg: format!("  Added NextDNS service '{}'\n", args.id) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_remove_service(db: &Database, args: NextdnsRemoveServiceArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let removed = db.with_conn(|conn| crate::db::nextdns::remove_nextdns_service(conn, &args.id))?;
    if !removed {
        return Err(AppError::NotFound { message: format!("NextDNS service '{}' not found", args.id), hint: None });
    }
    db.with_conn(|conn| crate::db::audit::log_action(conn, "remove", "nextdns_service", &args.id, None))?;

    let result = SimpleMsg { command: "nextdns remove-service", data: serde_json::json!({ "id": args.id }), msg: format!("  Removed NextDNS service '{}'\n", args.id) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_available_categories(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let cats: Vec<serde_json::Value> = NEXTDNS_CATEGORIES.iter()
        .map(|(id, name)| serde_json::json!({ "id": id, "name": name }))
        .collect();
    let result = SimpleMsg { command: "nextdns categories", data: serde_json::json!({ "categories": cats }), msg: {
        let mut s = String::from("  Available NextDNS categories:\n");
        for (id, name) in NEXTDNS_CATEGORIES { s.push_str(&format!("    {id:<20} {name}\n")); }
        s
    }};
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_available_services(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let svcs: Vec<serde_json::Value> = NEXTDNS_SERVICES.iter()
        .map(|(id, name)| serde_json::json!({ "id": id, "name": name }))
        .collect();
    let result = SimpleMsg { command: "nextdns services", data: serde_json::json!({ "services": svcs }), msg: {
        let mut s = String::from("  Available NextDNS services:\n");
        for (id, name) in NEXTDNS_SERVICES { s.push_str(&format!("    {id:<30} {name}\n")); }
        s
    }};
    output::render(&result, format);
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

struct SimpleMsg {
    command: &'static str,
    data: serde_json::Value,
    msg: String,
}

impl Renderable for SimpleMsg {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
    fn to_human(&self) -> String { self.msg.clone() }
}
