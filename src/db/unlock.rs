use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::UnlockRequest;

pub fn create_unlock_request(
    conn: &Connection,
    id: &str,
    target_type: &str,
    target_id: &str,
    reason: &str,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO unlock_requests (id, target_type, target_id, reason, status, requested_at)
         VALUES (?1, ?2, ?3, ?4, 'pending', ?5)",
        params![id, target_type, target_id, reason, now],
    )?;
    Ok(())
}

pub fn get_unlock_request(
    conn: &Connection,
    id: &str,
) -> Result<Option<UnlockRequest>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, target_type, target_id, reason, status, requested_at, resolved_at
         FROM unlock_requests WHERE id = ?1",
    )?;
    let mut rows = stmt.query_map(params![id], map_unlock)?;
    rows.next().transpose()
}

pub fn list_unlock_requests(
    conn: &Connection,
    status: Option<&str>,
) -> Result<Vec<UnlockRequest>, rusqlite::Error> {
    if let Some(status) = status {
        let mut stmt = conn.prepare(
            "SELECT id, target_type, target_id, reason, status, requested_at, resolved_at
             FROM unlock_requests WHERE status = ?1 ORDER BY requested_at DESC",
        )?;
        let rows = stmt.query_map(params![status], map_unlock)?;
        rows.collect()
    } else {
        let mut stmt = conn.prepare(
            "SELECT id, target_type, target_id, reason, status, requested_at, resolved_at
             FROM unlock_requests ORDER BY requested_at DESC",
        )?;
        let rows = stmt.query_map([], map_unlock)?;
        rows.collect()
    }
}

pub fn resolve_unlock_request(
    conn: &Connection,
    id: &str,
    status: &str,
) -> Result<bool, rusqlite::Error> {
    let now = now_unix();
    let rows = conn.execute(
        "UPDATE unlock_requests SET status = ?1, resolved_at = ?2 WHERE id = ?3 AND status = 'pending'",
        params![status, now, id],
    )?;
    Ok(rows > 0)
}

fn map_unlock(row: &rusqlite::Row) -> Result<UnlockRequest, rusqlite::Error> {
    Ok(UnlockRequest {
        id: row.get(0)?,
        target_type: row.get(1)?,
        target_id: row.get(2)?,
        reason: row.get(3)?,
        status: row.get(4)?,
        requested_at: row.get(5)?,
        resolved_at: row.get(6)?,
    })
}
