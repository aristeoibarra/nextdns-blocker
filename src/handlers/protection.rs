use crate::cli::protection::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: ProtectionCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        ProtectionCommands::Status(_) => handle_status(&db, format),
        ProtectionCommands::UnlockRequest(args) => handle_unlock_request(&db, args, format),
        ProtectionCommands::Cancel(args) => handle_cancel(&db, args, format),
        ProtectionCommands::List(args) => handle_list(&db, args, format),
        ProtectionCommands::PinSet(args) => handle_pin_set(&db, args, format),
        ProtectionCommands::PinRemove(args) => handle_pin_remove(&db, args, format),
        ProtectionCommands::PinStatus(_) => handle_pin_status(&db, format),
        ProtectionCommands::PinVerify(args) => handle_pin_verify(&db, args, format),
    }
}

fn handle_status(db: &Database, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let has_pin = db.with_conn(|conn| crate::db::pin::has_pin(conn))?;
    let locked_out = db.with_conn(|conn| crate::db::pin::is_locked_out(conn))?;
    let pending = crate::protection::unlock::list_requests(db, Some("pending"))?;

    let result = ProtStatusResult { has_pin, locked_out, pending_unlocks: pending.len() };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct ProtStatusResult { has_pin: bool, locked_out: bool, pending_unlocks: usize }
impl Renderable for ProtStatusResult {
    fn command_name(&self) -> &str { "protection status" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "pin_enabled": self.has_pin, "locked_out": self.locked_out, "pending_unlocks": self.pending_unlocks } })
    }
    fn to_human(&self) -> String {
        format!("  PIN: {}\n  Locked out: {}\n  Pending unlocks: {}\n",
            if self.has_pin { "enabled" } else { "disabled" }, self.locked_out, self.pending_unlocks)
    }
}

fn handle_unlock_request(db: &Database, args: UnlockRequestArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let id = crate::protection::unlock::create_request(db, &args.target_type, &args.target_id, &args.reason)?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "unlock_request", &args.target_type, &args.target_id, Some(&args.reason)))?;

    let result = SimpleMsg { command: "protection unlock-request", data: serde_json::json!({ "id": id }), msg: format!("  Created unlock request '{id}'\n") };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_cancel(db: &Database, args: ProtectionCancelArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let resolved = db.with_conn(|conn| crate::db::unlock::resolve_unlock_request(conn, &args.id, "denied"))?;
    if !resolved {
        return Err(AppError::NotFound { message: format!("Unlock request '{}' not found", args.id), hint: None });
    }

    let result = SimpleMsg { command: "protection cancel", data: serde_json::json!({ "id": args.id }), msg: format!("  Cancelled unlock request '{}'\n", args.id) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_list(db: &Database, args: ProtectionListArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let requests = crate::protection::unlock::list_requests(db, args.status.as_deref())?;

    let result = UnlockListResult { requests };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct UnlockListResult { requests: Vec<crate::types::UnlockRequest> }
impl Renderable for UnlockListResult {
    fn command_name(&self) -> &str { "protection list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "active_unlocks": [], "pending_requests": self.requests }, "summary": { "active": 0, "pending": self.requests.len() } })
    }
    fn to_human(&self) -> String {
        if self.requests.is_empty() { return "  No unlock requests.\n".to_string(); }
        let mut out = String::new();
        for r in &self.requests {
            out.push_str(&format!("  {} {} {} [{}] - {}\n", r.id, r.target_type, r.target_id, r.status, r.reason));
        }
        out
    }
}

fn handle_pin_set(db: &Database, args: PinSetArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    if args.pin.len() < 4 {
        return Err(AppError::Validation { message: "PIN must be at least 4 characters".to_string(), details: vec![], hint: None });
    }
    crate::protection::pin::set_pin(db, &args.pin, args.current.as_deref())?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "pin_set", "pin", "", None))?;

    let result = SimpleMsg { command: "protection pin-set", data: serde_json::json!({ "set": true }), msg: "  PIN set successfully.\n".to_string() };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_pin_remove(db: &Database, args: PinRemoveArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    // Verify current PIN first
    let _session = crate::protection::pin::verify_and_create_session(db, &args.pin)?;
    db.with_conn(|conn| crate::db::pin::remove_pin(conn))?;
    db.with_conn(|conn| crate::db::audit::log_action(conn, "pin_remove", "pin", "", None))?;

    let result = SimpleMsg { command: "protection pin-remove", data: serde_json::json!({ "removed": true }), msg: "  PIN removed.\n".to_string() };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_pin_status(db: &Database, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let has_pin = db.with_conn(|conn| crate::db::pin::has_pin(conn))?;
    let locked_out = db.with_conn(|conn| crate::db::pin::is_locked_out(conn))?;

    let result = SimpleMsg {
        command: "protection pin-status",
        data: serde_json::json!({ "pin_enabled": has_pin, "locked_out": locked_out }),
        msg: format!("  PIN enabled: {}\n  Locked out: {}\n", has_pin, locked_out),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_pin_verify(db: &Database, args: PinVerifyArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let session_id = crate::protection::pin::verify_and_create_session(db, &args.pin)?;

    let result = SimpleMsg {
        command: "protection pin-verify",
        data: serde_json::json!({ "valid": true, "session_id": session_id }),
        msg: format!("  PIN verified. Session: {session_id}\n"),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct SimpleMsg { command: &'static str, data: serde_json::Value, msg: String }
impl Renderable for SimpleMsg {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
    fn to_human(&self) -> String { self.msg.clone() }
}
