use crate::cli::status::StatusArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(args: StatusArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let db_path = crate::common::platform::db_path();
    let db = crate::db::Database::open(&db_path)?;

    let blocked_count = db.with_conn(crate::db::domains::count_blocked)?;
    let allowed_count = db.with_conn(crate::db::domains::count_allowed)?;
    let pending_count = db.with_conn(|conn| {
        let actions = crate::db::pending::list_pending(conn, Some("pending"))?;
        Ok::<_, rusqlite::Error>(actions.len() as i64)
    })?;
    let retry_count = db.with_conn(crate::db::retry::count_retries)?;
    let has_pin = db.with_conn(crate::db::pin::has_pin)?;
    let categories = db.with_conn(crate::db::categories::list_categories)?;

    let result = StatusResult {
        blocked_count, allowed_count, category_count: categories.len() as i64,
        pending_count, retry_count, has_pin, _detailed: args.detailed,
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

struct StatusResult {
    blocked_count: i64, allowed_count: i64, category_count: i64,
    pending_count: i64, retry_count: i64, has_pin: bool, _detailed: bool,
}

impl Renderable for StatusResult {
    fn command_name(&self) -> &str { "status" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": {
            "blocked_domains": self.blocked_count, "allowed_domains": self.allowed_count,
            "categories": self.category_count, "pending_actions": self.pending_count,
            "retry_queue": self.retry_count, "pin_enabled": self.has_pin,
        }})
    }
    fn to_human(&self) -> String {
        format!("Status:\n  Blocked domains: {}\n  Allowed domains: {}\n  Categories: {}\n  Pending actions: {}\n  Retry queue: {}\n  PIN protection: {}\n",
            self.blocked_count, self.allowed_count, self.category_count,
            self.pending_count, self.retry_count, if self.has_pin { "enabled" } else { "disabled" })
    }
}
