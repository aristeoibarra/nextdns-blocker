use crate::cli::protection::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: ProtectionCommands) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        ProtectionCommands::Status(_) => handle_status(&db),
        ProtectionCommands::UnlockRequest(args) => handle_unlock_request(&db, args),
        ProtectionCommands::Cancel(args) => handle_cancel(&db, args),
        ProtectionCommands::List(args) => handle_list(&db, args),
        ProtectionCommands::PinSet(args) => handle_pin_set(&db, args),
        ProtectionCommands::PinRemove(args) => handle_pin_remove(&db, args),
        ProtectionCommands::PinStatus(_) => handle_pin_status(&db),
        ProtectionCommands::PinVerify(args) => handle_pin_verify(&db, args),
    }
}

fn handle_status(db: &Database) -> Result<ExitCode, AppError> {
    let has_pin = db.with_conn(crate::db::pin::has_pin)?;
    let locked_out = db.with_conn(crate::db::pin::is_locked_out)?;
    let pending = crate::protection::unlock::list_requests(db, Some("pending"))?;

    let result = ProtStatusResult { has_pin, locked_out, pending_unlocks: pending.len() };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct ProtStatusResult { has_pin: bool, locked_out: bool, pending_unlocks: usize }
impl Renderable for ProtStatusResult {
    fn command_name(&self) -> &str { "protection status" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "pin_enabled": self.has_pin, "locked_out": self.locked_out, "pending_unlocks": self.pending_unlocks } })
    }
}

fn handle_unlock_request(db: &Database, args: UnlockRequestArgs) -> Result<ExitCode, AppError> {
    let id = crate::protection::unlock::create_request(db, &args.target_type, &args.target_id, &args.reason)?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "unlock_request", &args.target_type, &args.target_id, Some(&args.reason)))?;

    let result = SimpleMsg { command: "protection unlock-request", data: serde_json::json!({ "id": id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_cancel(db: &Database, args: ProtectionCancelArgs) -> Result<ExitCode, AppError> {
    let resolved = db.with_conn(|conn| crate::db::unlock::resolve_unlock_request(conn, &args.id, "denied"))?;
    if !resolved {
        return Err(AppError::NotFound { message: format!("Unlock request '{}' not found", args.id), hint: None });
    }

    let result = SimpleMsg { command: "protection cancel", data: serde_json::json!({ "id": args.id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_list(db: &Database, args: ProtectionListArgs) -> Result<ExitCode, AppError> {
    let requests = crate::protection::unlock::list_requests(db, args.status.as_deref())?;
    let result = UnlockListResult { requests };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct UnlockListResult { requests: Vec<crate::types::UnlockRequest> }
impl Renderable for UnlockListResult {
    fn command_name(&self) -> &str { "protection list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "active_unlocks": [], "pending_requests": self.requests }, "summary": { "active": 0, "pending": self.requests.len() } })
    }
}

fn handle_pin_set(db: &Database, args: PinSetArgs) -> Result<ExitCode, AppError> {
    if args.pin.len() < 4 {
        return Err(AppError::Validation { message: "PIN must be at least 4 characters".to_string(), details: vec![], hint: None });
    }
    crate::protection::pin::set_pin(db, &args.pin, args.current.as_deref())?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "pin_set", "pin", "", None))?;

    let result = SimpleMsg { command: "protection pin-set", data: serde_json::json!({ "set": true }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_pin_remove(db: &Database, args: PinRemoveArgs) -> Result<ExitCode, AppError> {
    let _session = crate::protection::pin::verify_and_create_session(db, &args.pin)?;
    db.with_conn(crate::db::pin::remove_pin)?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "pin_remove", "pin", "", None))?;

    let result = SimpleMsg { command: "protection pin-remove", data: serde_json::json!({ "removed": true }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_pin_status(db: &Database) -> Result<ExitCode, AppError> {
    let has_pin = db.with_conn(crate::db::pin::has_pin)?;
    let locked_out = db.with_conn(crate::db::pin::is_locked_out)?;

    let result = SimpleMsg {
        command: "protection pin-status",
        data: serde_json::json!({ "pin_enabled": has_pin, "locked_out": locked_out }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_pin_verify(db: &Database, args: PinVerifyArgs) -> Result<ExitCode, AppError> {
    let session_id = crate::protection::pin::verify_and_create_session(db, &args.pin)?;

    let result = SimpleMsg {
        command: "protection pin-verify",
        data: serde_json::json!({ "valid": true, "session_id": session_id }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct SimpleMsg { command: &'static str, data: serde_json::Value }
impl Renderable for SimpleMsg {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
}
