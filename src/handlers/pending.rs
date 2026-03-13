use crate::cli::pending::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: PendingCommands) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        PendingCommands::List(args) => handle_list(&db, args),
        PendingCommands::Show(args) => handle_show(&db, args),
        PendingCommands::Cancel(args) => handle_cancel(&db, args),
    }
}

fn handle_list(db: &Database, args: PendingListArgs) -> Result<ExitCode, AppError> {
    let actions = db.with_conn(|conn| crate::db::pending::list_pending(conn, args.status.as_deref()))?;
    let result = PendingListResult { actions };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct PendingListResult { actions: Vec<crate::types::PendingAction> }
impl Renderable for PendingListResult {
    fn command_name(&self) -> &str { "pending list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "actions": self.actions }, "summary": { "total": self.actions.len() } })
    }
}

fn handle_show(db: &Database, args: PendingShowArgs) -> Result<ExitCode, AppError> {
    let action = db.with_conn(|conn| crate::db::pending::get_pending(conn, &args.id))?
        .ok_or_else(|| AppError::NotFound {
            message: format!("Pending action '{}' not found", args.id),
            hint: Some("Use 'ndb pending list' to see pending actions".to_string()),
        })?;

    let result = PendingShowResult { action };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct PendingShowResult { action: crate::types::PendingAction }
impl Renderable for PendingShowResult {
    fn command_name(&self) -> &str { "pending show" }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.action }) }
}

fn handle_cancel(db: &Database, args: PendingCancelArgs) -> Result<ExitCode, AppError> {
    let cancelled = db.with_conn(|conn| crate::db::pending::cancel_pending(conn, &args.id))?;
    if !cancelled {
        return Err(AppError::NotFound {
            message: format!("Pending action '{}' not found or already completed", args.id),
            hint: None,
        });
    }

    db.with_conn(|conn| crate::db::audit::log_action(conn, "cancel", "pending", &args.id, None, "cli"))?;

    let result = SimpleMsg { command: "pending cancel", data: serde_json::json!({ "id": args.id }) };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct SimpleMsg { command: &'static str, data: serde_json::Value }
impl Renderable for SimpleMsg {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
}
