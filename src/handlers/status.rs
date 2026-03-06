use crate::cli::status::StatusArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(_args: StatusArgs) -> Result<ExitCode, AppError> {
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
        pending_count, retry_count, has_pin,
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct StatusResult {
    blocked_count: i64, allowed_count: i64, category_count: i64,
    pending_count: i64, retry_count: i64, has_pin: bool,
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
}
