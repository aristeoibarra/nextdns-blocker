use crate::cli::pending::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: PendingCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        PendingCommands::List(args) => handle_list(&db, args, format),
        PendingCommands::Show(args) => handle_show(&db, args, format),
        PendingCommands::Cancel(args) => handle_cancel(&db, args, format),
    }
}

fn handle_list(db: &Database, args: PendingListArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let actions = db.with_conn(|conn| crate::db::pending::list_pending(conn, args.status.as_deref()))?;

    let result = PendingListResult { actions };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct PendingListResult {
    actions: Vec<crate::types::PendingAction>,
}

impl Renderable for PendingListResult {
    fn command_name(&self) -> &str { "pending list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "actions": self.actions }, "summary": { "total": self.actions.len() } })
    }
    fn to_human(&self) -> String {
        if self.actions.is_empty() { return "  No pending actions.\n".to_string(); }
        let mut out = String::new();
        for a in &self.actions {
            let domain = a.domain.as_deref().unwrap_or("-");
            out.push_str(&format!("  {} {} {} [{}] (execute at: {})\n", a.id, a.action, domain, a.status, crate::common::time::format_timestamp(a.execute_at)));
        }
        out
    }
}

fn handle_show(db: &Database, args: PendingShowArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let action = db.with_conn(|conn| crate::db::pending::get_pending(conn, &args.id))?
        .ok_or_else(|| AppError::NotFound {
            message: format!("Pending action '{}' not found", args.id),
            hint: Some("Use 'ndb pending list' to see pending actions".to_string()),
        })?;

    let result = PendingShowResult { action };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct PendingShowResult {
    action: crate::types::PendingAction,
}

impl Renderable for PendingShowResult {
    fn command_name(&self) -> &str { "pending show" }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.action }) }
    fn to_human(&self) -> String {
        format!("  ID: {}\n  Action: {}\n  Domain: {}\n  Status: {}\n  Execute at: {}\n",
            self.action.id, self.action.action,
            self.action.domain.as_deref().unwrap_or("-"),
            self.action.status,
            crate::common::time::format_timestamp(self.action.execute_at))
    }
}

fn handle_cancel(db: &Database, args: PendingCancelArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let cancelled = db.with_conn(|conn| crate::db::pending::cancel_pending(conn, &args.id))?;
    if !cancelled {
        return Err(AppError::NotFound {
            message: format!("Pending action '{}' not found or already completed", args.id),
            hint: None,
        });
    }

    db.with_conn(|conn| crate::db::audit::log_action(conn, "cancel", "pending", &args.id, None))?;

    let result = SimpleMsg { command: "pending cancel", msg: format!("  Cancelled pending action '{}'\n", args.id), data: serde_json::json!({ "id": args.id }) };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct SimpleMsg { command: &'static str, msg: String, data: serde_json::Value }
impl Renderable for SimpleMsg {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
    fn to_human(&self) -> String { self.msg.clone() }
}
