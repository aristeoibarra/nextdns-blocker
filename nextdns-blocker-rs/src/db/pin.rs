use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::config::constants::{PIN_LOCKOUT_DURATION_SECS, PIN_MAX_ATTEMPTS, PIN_SESSION_DURATION_SECS};

/// Check if a PIN is configured.
pub fn has_pin(conn: &Connection) -> Result<bool, rusqlite::Error> {
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM pin_config WHERE id = 1)",
        [],
        |row| row.get(0),
    )
}

/// Get the stored PIN hash.
pub fn get_pin_hash(conn: &Connection) -> Result<Option<String>, rusqlite::Error> {
    let mut stmt = conn.prepare("SELECT pin_hash FROM pin_config WHERE id = 1")?;
    let mut rows = stmt.query_map([], |row| row.get(0))?;
    rows.next().transpose()
}

/// Set or update the PIN hash.
pub fn set_pin_hash(conn: &Connection, hash: &str) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO pin_config (id, pin_hash, created_at, updated_at) VALUES (1, ?1, ?2, ?2)
         ON CONFLICT(id) DO UPDATE SET pin_hash = ?1, updated_at = ?2",
        params![hash, now],
    )?;
    Ok(())
}

/// Remove the PIN.
pub fn remove_pin(conn: &Connection) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM pin_config WHERE id = 1", [])?;
    // Also clear sessions and lockout
    conn.execute("DELETE FROM pin_sessions", [])?;
    conn.execute("DELETE FROM pin_lockout WHERE id = 1", [])?;
    Ok(rows > 0)
}

/// Create a new PIN session.
pub fn create_session(conn: &Connection, session_id: &str) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    let expires = now + PIN_SESSION_DURATION_SECS;
    conn.execute(
        "INSERT INTO pin_sessions (id, created_at, expires_at) VALUES (?1, ?2, ?3)",
        params![session_id, now, expires],
    )?;
    Ok(())
}

/// Check if a session is valid (not expired).
pub fn is_session_valid(conn: &Connection, session_id: &str) -> Result<bool, rusqlite::Error> {
    let now = now_unix();
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM pin_sessions WHERE id = ?1 AND expires_at > ?2)",
        params![session_id, now],
        |row| row.get(0),
    )
}

/// Clean up expired sessions.
pub fn cleanup_sessions(conn: &Connection) -> Result<usize, rusqlite::Error> {
    let now = now_unix();
    let rows = conn.execute("DELETE FROM pin_sessions WHERE expires_at <= ?1", params![now])?;
    Ok(rows)
}

/// Check if PIN is locked out due to too many failed attempts.
pub fn is_locked_out(conn: &Connection) -> Result<bool, rusqlite::Error> {
    let now = now_unix();
    let result: Option<i64> = conn
        .query_row(
            "SELECT locked_until FROM pin_lockout WHERE id = 1 AND locked_until > ?1",
            params![now],
            |row| row.get(0),
        )
        .ok();
    Ok(result.is_some())
}

/// Record a failed PIN attempt. Returns true if now locked out.
pub fn record_failed_attempt(conn: &Connection) -> Result<bool, rusqlite::Error> {
    let now = now_unix();

    // Ensure lockout row exists
    conn.execute(
        "INSERT OR IGNORE INTO pin_lockout (id, failed_attempts, last_attempt_at)
         VALUES (1, 0, ?1)",
        params![now],
    )?;

    conn.execute(
        "UPDATE pin_lockout SET failed_attempts = failed_attempts + 1, last_attempt_at = ?1
         WHERE id = 1",
        params![now],
    )?;

    let attempts: i32 = conn.query_row(
        "SELECT failed_attempts FROM pin_lockout WHERE id = 1",
        [],
        |row| row.get(0),
    )?;

    if attempts >= PIN_MAX_ATTEMPTS {
        let locked_until = now + PIN_LOCKOUT_DURATION_SECS;
        conn.execute(
            "UPDATE pin_lockout SET locked_until = ?1 WHERE id = 1",
            params![locked_until],
        )?;
        return Ok(true);
    }

    Ok(false)
}

/// Reset failed attempts (after successful verification).
pub fn reset_failed_attempts(conn: &Connection) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE pin_lockout SET failed_attempts = 0, locked_until = NULL WHERE id = 1",
        [],
    )?;
    Ok(())
}
