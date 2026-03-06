use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::RetryEntry;

pub fn enqueue_retry(
    conn: &Connection,
    id: &str,
    action: &str,
    domain: Option<&str>,
    list_type: &str,
    payload: Option<&str>,
    max_attempts: i32,
    next_retry_at: i64,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO retry_queue (id, action, domain, list_type, payload, attempts, max_attempts, next_retry_at, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, 0, ?6, ?7, ?8)",
        params![id, action, domain, list_type, payload, max_attempts, next_retry_at, now],
    )?;
    Ok(())
}

pub fn get_due_retries(conn: &Connection) -> Result<Vec<RetryEntry>, rusqlite::Error> {
    let now = now_unix();
    let mut stmt = conn.prepare(
        "SELECT id, action, domain, list_type, payload, attempts, max_attempts, last_error, next_retry_at, created_at
         FROM retry_queue WHERE next_retry_at <= ?1 AND attempts < max_attempts
         ORDER BY next_retry_at",
    )?;
    let rows = stmt.query_map(params![now], map_retry)?;
    rows.collect()
}

pub fn increment_retry(
    conn: &Connection,
    id: &str,
    error: &str,
    next_retry_at: i64,
) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE retry_queue SET attempts = attempts + 1, last_error = ?1, next_retry_at = ?2
         WHERE id = ?3",
        params![error, next_retry_at, id],
    )?;
    Ok(())
}

pub fn remove_retry(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM retry_queue WHERE id = ?1", params![id])?;
    Ok(rows > 0)
}

pub fn list_retries(conn: &Connection) -> Result<Vec<RetryEntry>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, action, domain, list_type, payload, attempts, max_attempts, last_error, next_retry_at, created_at
         FROM retry_queue ORDER BY next_retry_at",
    )?;
    let rows = stmt.query_map([], map_retry)?;
    rows.collect()
}

pub fn count_retries(conn: &Connection) -> Result<i64, rusqlite::Error> {
    conn.query_row("SELECT COUNT(*) FROM retry_queue", [], |row| row.get(0))
}

pub fn clear_completed_retries(conn: &Connection) -> Result<usize, rusqlite::Error> {
    let rows = conn.execute(
        "DELETE FROM retry_queue WHERE attempts >= max_attempts",
        [],
    )?;
    Ok(rows)
}

fn map_retry(row: &rusqlite::Row) -> Result<RetryEntry, rusqlite::Error> {
    Ok(RetryEntry {
        id: row.get(0)?,
        action: row.get(1)?,
        domain: row.get(2)?,
        list_type: row.get(3)?,
        payload: row.get(4)?,
        attempts: row.get(5)?,
        max_attempts: row.get(6)?,
        last_error: row.get(7)?,
        next_retry_at: row.get(8)?,
        created_at: row.get(9)?,
    })
}
