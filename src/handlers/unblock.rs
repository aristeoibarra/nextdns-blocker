use crate::cli::unblock::UnblockArgs;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(args: UnblockArgs) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    let is_domain = db.with_conn(|conn| crate::db::domains::is_blocked(conn, &args.target))?;
    let is_category = db.with_conn(|conn| crate::db::categories::get_category(conn, &args.target))?.is_some();

    if !is_domain && !is_category {
        return Err(AppError::NotFound {
            message: format!("'{}' not found in denylist or categories", args.target),
            hint: Some("Use 'ndb denylist list' or 'ndb category list' to check".to_string()),
        });
    }

    if is_domain {
        let locked = crate::protection::validate_no_locked_removal(&db, std::slice::from_ref(&args.target))?;
        if !locked.is_empty() {
            return Err(AppError::Permission {
                message: format!("'{}' is protected", args.target),
                hint: Some("Use 'ndb protection unlock-request' to request unblocking".to_string()),
            });
        }
    }
    if is_category && crate::protection::is_locked(&db, "category", &args.target)? {
        return Err(AppError::Permission {
            message: format!("Category '{}' is locked", args.target),
            hint: Some("Use 'ndb protection unlock-request' to request unblocking".to_string()),
        });
    }

    if let Some(ref dur_str) = args.duration {
        let duration = crate::common::time::parse_duration(dur_str)?;
        let execute_at = crate::common::time::now_unix() + duration.as_secs() as i64;
        let id = uuid::Uuid::new_v4().to_string();

        if is_domain {
            db.with_conn(|conn| crate::db::domains::deactivate_blocked(conn, &args.target))?;
            db.with_conn(|conn| crate::db::pending::create_pending(
                conn, &id, "add", Some(&args.target), "denylist", execute_at,
                Some(&format!("Auto re-block after {dur_str}")),
            ))?;
        }

        db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", if is_domain { "domain" } else { "category" }, &args.target, Some(dur_str)))?;

        let result = UnblockResult { target: args.target, duration: Some(dur_str.clone()), pending_id: Some(id) };
        output::render(&result);
    } else {
        if is_domain {
            db.with_conn(|conn| crate::db::domains::remove_blocked(conn, &args.target))?;
        }
        db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", if is_domain { "domain" } else { "category" }, &args.target, None))?;

        let result = UnblockResult { target: args.target, duration: None, pending_id: None };
        output::render(&result);
    }

    Ok(ExitCode::Success)
}

struct UnblockResult { target: String, duration: Option<String>, pending_id: Option<String> }
impl Renderable for UnblockResult {
    fn command_name(&self) -> &str { "unblock" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "target": self.target, "duration": self.duration, "pending_id": self.pending_id },
            "summary": { "unblocked": 1 }
        })
    }
}
