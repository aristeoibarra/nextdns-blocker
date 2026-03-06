use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::AuditEntry;

pub fn log_action(
    conn: &Connection,
    action: &str,
    target_type: &str,
    target_id: &str,
    details: Option<&str>,
) -> Result<i64, rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO audit_log (action, target_type, target_id, details, timestamp)
         VALUES (?1, ?2, ?3, ?4, ?5)",
        params![action, target_type, target_id, details, now],
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn list_audit(
    conn: &Connection,
    limit: i64,
    offset: i64,
) -> Result<Vec<AuditEntry>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, action, target_type, target_id, details, timestamp
         FROM audit_log ORDER BY timestamp DESC LIMIT ?1 OFFSET ?2",
    )?;
    let rows = stmt.query_map(params![limit, offset], |row| {
        Ok(AuditEntry {
            id: row.get(0)?,
            action: row.get(1)?,
            target_type: row.get(2)?,
            target_id: row.get(3)?,
            details: row.get(4)?,
            timestamp: row.get(5)?,
        })
    })?;
    rows.collect()
}

pub fn count_audit(conn: &Connection) -> Result<i64, rusqlite::Error> {
    conn.query_row("SELECT COUNT(*) FROM audit_log", [], |row| row.get(0))
}
