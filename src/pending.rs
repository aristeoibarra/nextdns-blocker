use crate::api::NextDnsClient;
use crate::db::Database;
use crate::error::AppError;

/// Process all due pending actions.
pub fn process_pending(db: &Database, client: &NextDnsClient) -> Result<PendingResult, AppError> {
    let actions = db.with_conn(crate::db::pending::get_due_pending)?;

    let mut executed = 0;
    let mut failed = 0;

    for action in actions {
        db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "executing"))?;

        let result = match (action.action.as_str(), action.list_type.as_str()) {
            ("add", "denylist") => {
                action.domain.as_ref().map_or(Ok(()), |d| client.add_to_denylist(d))
            }
            ("remove", "denylist") => {
                action.domain.as_ref().map_or(Ok(()), |d| client.remove_from_denylist(d))
            }
            ("add", "allowlist") => {
                action.domain.as_ref().map_or(Ok(()), |d| client.add_to_allowlist(d))
            }
            ("remove", "allowlist") => {
                action.domain.as_ref().map_or(Ok(()), |d| client.remove_from_allowlist(d))
            }
            _ => Ok(()),
        };

        match result {
            Ok(()) => {
                db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "completed"))?;
                executed += 1;
            }
            Err(_) => {
                db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "failed"))?;
                failed += 1;
            }
        }
    }

    Ok(PendingResult { executed, failed })
}

#[derive(Debug, serde::Serialize)]
pub struct PendingResult {
    pub executed: usize,
    pub failed: usize,
}
