use crate::db::Database;
use crate::error::AppError;

/// Create a new unlock request.
pub fn create_request(
    db: &Database,
    target_type: &str,
    target_id: &str,
    reason: &str,
) -> Result<String, AppError> {
    let id = uuid::Uuid::new_v4().to_string();
    db.with_conn(|conn| {
        crate::db::unlock::create_unlock_request(conn, &id, target_type, target_id, reason)
    })?;
    Ok(id)
}

/// List unlock requests with optional status filter.
pub fn list_requests(
    db: &Database,
    status: Option<&str>,
) -> Result<Vec<crate::types::UnlockRequest>, AppError> {
    db.with_conn(|conn| crate::db::unlock::list_unlock_requests(conn, status))
}
