use rusqlite::{params, Connection};

use crate::common::time::now_unix;

pub fn get_value(conn: &Connection, key: &str) -> Result<Option<String>, rusqlite::Error> {
    let mut stmt = conn.prepare("SELECT value FROM kv_config WHERE key = ?1")?;
    let mut rows = stmt.query_map(params![key], |row| row.get(0))?;
    rows.next().transpose()
}

pub fn set_value(conn: &Connection, key: &str, value: &str) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO kv_config (key, value, updated_at) VALUES (?1, ?2, ?3)
         ON CONFLICT(key) DO UPDATE SET value = ?2, updated_at = ?3",
        params![key, value, now],
    )?;
    Ok(())
}

pub fn delete_value(conn: &Connection, key: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM kv_config WHERE key = ?1", params![key])?;
    Ok(rows > 0)
}

pub fn list_all(conn: &Connection) -> Result<Vec<(String, String)>, rusqlite::Error> {
    let mut stmt = conn.prepare("SELECT key, value FROM kv_config ORDER BY key")?;
    let rows = stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?;
    rows.collect()
}
