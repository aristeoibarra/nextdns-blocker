use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::PendingAction;

pub fn create_pending(
    conn: &Connection,
    id: &str,
    action: &str,
    domain: Option<&str>,
    list_type: &str,
    execute_at: i64,
    description: Option<&str>,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO pending_actions (id, action, domain, list_type, scheduled_at, execute_at, status, description, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'pending', ?7, ?5)",
        params![id, action, domain, list_type, now, execute_at, description],
    )?;
    Ok(())
}

pub fn get_pending(conn: &Connection, id: &str) -> Result<Option<PendingAction>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, action, domain, list_type, scheduled_at, execute_at, status, description, created_at
         FROM pending_actions WHERE id = ?1",
    )?;
    let mut rows = stmt.query_map(params![id], map_pending)?;
    rows.next().transpose()
}

pub fn list_pending(conn: &Connection, status: Option<&str>) -> Result<Vec<PendingAction>, rusqlite::Error> {
    if let Some(status) = status {
        let mut stmt = conn.prepare(
            "SELECT id, action, domain, list_type, scheduled_at, execute_at, status, description, created_at
             FROM pending_actions WHERE status = ?1 ORDER BY execute_at",
        )?;
        let rows = stmt.query_map(params![status], map_pending)?;
        rows.collect()
    } else {
        let mut stmt = conn.prepare(
            "SELECT id, action, domain, list_type, scheduled_at, execute_at, status, description, created_at
             FROM pending_actions ORDER BY execute_at",
        )?;
        let rows = stmt.query_map([], map_pending)?;
        rows.collect()
    }
}

/// Get pending actions that are due: status='pending' and execute_at <= now,
/// OR stuck in 'executing' for more than 5 minutes (process likely died).
/// Uses `created_at` for stuck detection so future-scheduled actions that crashed
/// mid-execution are recovered promptly, not after their execute_at passes.
pub fn get_due_pending(conn: &Connection) -> Result<Vec<PendingAction>, rusqlite::Error> {
    let now = now_unix();
    let stuck_threshold = now - 300; // 5 minutes ago
    let mut stmt = conn.prepare(
        "SELECT id, action, domain, list_type, scheduled_at, execute_at, status, description, created_at
         FROM pending_actions
         WHERE (status = 'pending' AND execute_at <= ?1)
            OR (status = 'executing' AND created_at <= ?2)
         ORDER BY execute_at",
    )?;
    let rows = stmt.query_map(params![now, stuck_threshold], map_pending)?;
    rows.collect()
}

pub fn has_due_pending(conn: &Connection) -> Result<bool, rusqlite::Error> {
    let now = now_unix();
    let stuck_threshold = now - 300;
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM pending_actions
         WHERE (status = 'pending' AND execute_at <= ?1)
            OR (status = 'executing' AND created_at <= ?2))",
        params![now, stuck_threshold],
        |row| row.get(0),
    )
}

pub fn update_pending_status(
    conn: &Connection,
    id: &str,
    status: &str,
) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "UPDATE pending_actions SET status = ?1 WHERE id = ?2",
        params![status, id],
    )?;
    Ok(rows > 0)
}

pub fn cancel_pending(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    update_pending_status(conn, id, "cancelled")
}

fn map_pending(row: &rusqlite::Row) -> Result<PendingAction, rusqlite::Error> {
    Ok(PendingAction {
        id: row.get(0)?,
        action: row.get(1)?,
        domain: row.get(2)?,
        list_type: row.get(3)?,
        scheduled_at: row.get(4)?,
        execute_at: row.get(5)?,
        status: row.get(6)?,
        description: row.get(7)?,
        created_at: row.get(8)?,
    })
}
