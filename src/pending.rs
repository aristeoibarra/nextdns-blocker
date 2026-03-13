use crate::api::NextDnsClient;
use crate::db::Database;
use crate::error::AppError;

/// Process all due pending actions.
pub fn process_pending(db: &Database, client: &NextDnsClient) -> Result<PendingResult, AppError> {
    let actions = db.with_conn(crate::db::pending::get_due_pending)?;

    let mut executed = 0;
    let mut failed = 0;

    for action in actions {
        // Skip actions with missing domain — mark completed and audit-log the anomaly
        let domain = match &action.domain {
            Some(d) => d.clone(),
            None => {
                let _ = db.with_conn(|conn| {
                    crate::db::audit::log_action(
                        conn, "pending_no_domain", &action.list_type, &action.id,
                        Some(&format!("Pending action '{}' has no domain, marking completed", action.action)),
                    )
                });
                db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "completed"))?;
                continue;
            }
        };

        db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "executing"))?;

        let result = match (action.action.as_str(), action.list_type.as_str()) {
            ("add", "denylist") => client.add_to_denylist(&domain),
            ("remove", "denylist") => client.remove_from_denylist(&domain),
            ("add", "allowlist") => client.add_to_allowlist(&domain),
            ("remove", "allowlist") => client.remove_from_allowlist(&domain),
            (act, lt) => {
                // Unknown combo — mark completed and audit-log so it doesn't loop
                let _ = db.with_conn(|conn| {
                    crate::db::audit::log_action(
                        conn, "pending_unknown_combo", lt, &action.id,
                        Some(&format!("Unknown action/list_type: {act}/{lt} for domain {domain}")),
                    )
                });
                db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "completed"))?;
                continue;
            }
        };

        match result {
            Ok(()) => {
                db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "completed"))?;
                executed += 1;
            }
            Err(_) => {
                db.with_conn(|conn| crate::db::pending::update_pending_status(conn, &action.id, "failed"))?;
                // Escalate to retry queue for automatic recovery
                let retry_id = uuid::Uuid::new_v4().to_string();
                let retry_at = crate::common::time::now_unix() + 60;
                let _ = db.with_conn(|conn| {
                    crate::db::retry::enqueue_retry(
                        conn, &retry_id, &action.action, action.domain.as_deref(),
                        &action.list_type, None, 5, retry_at,
                    )
                });
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
