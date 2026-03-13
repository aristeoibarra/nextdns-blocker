use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::{NextDnsCategory, NextDnsService};

// === NextDNS Categories ===

pub fn add_nextdns_category(conn: &Connection, id: &str) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO nextdns_categories (id, active, created_at)
         VALUES (?1, 1, ?2)
         ON CONFLICT(id) DO UPDATE SET active = 1",
        params![id, now],
    )?;
    Ok(())
}

pub fn remove_nextdns_category(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM nextdns_categories WHERE id = ?1", params![id])?;
    Ok(rows > 0)
}

pub fn list_nextdns_categories(conn: &Connection) -> Result<Vec<NextDnsCategory>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, active, created_at FROM nextdns_categories ORDER BY id",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(NextDnsCategory {
            id: row.get(0)?,
            active: row.get::<_, i64>(1)? != 0,
            created_at: row.get(2)?,
        })
    })?;
    rows.collect()
}

pub fn is_active_nextdns_category(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM nextdns_categories WHERE id = ?1 AND active = 1",
        params![id],
        |row| row.get(0),
    )?;
    Ok(count > 0)
}

pub fn deactivate_nextdns_category(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "UPDATE nextdns_categories SET active = 0 WHERE id = ?1 AND active = 1",
        params![id],
    )?;
    Ok(rows > 0)
}

pub fn activate_nextdns_category(conn: &Connection, id: &str) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE nextdns_categories SET active = 1 WHERE id = ?1",
        params![id],
    )?;
    Ok(())
}

// === NextDNS Services ===

pub fn add_nextdns_service(conn: &Connection, id: &str) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO nextdns_services (id, active, created_at)
         VALUES (?1, 1, ?2)
         ON CONFLICT(id) DO UPDATE SET active = 1",
        params![id, now],
    )?;
    Ok(())
}

pub fn remove_nextdns_service(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM nextdns_services WHERE id = ?1", params![id])?;
    Ok(rows > 0)
}

pub fn is_active_nextdns_service(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM nextdns_services WHERE id = ?1 AND active = 1",
        params![id],
        |row| row.get(0),
    )?;
    Ok(count > 0)
}

pub fn deactivate_nextdns_service(conn: &Connection, id: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "UPDATE nextdns_services SET active = 0 WHERE id = ?1 AND active = 1",
        params![id],
    )?;
    Ok(rows > 0)
}

pub fn activate_nextdns_service(conn: &Connection, id: &str) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE nextdns_services SET active = 1 WHERE id = ?1",
        params![id],
    )?;
    Ok(())
}

pub fn list_nextdns_services(conn: &Connection) -> Result<Vec<NextDnsService>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, active, created_at FROM nextdns_services ORDER BY id",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(NextDnsService {
            id: row.get(0)?,
            active: row.get::<_, i64>(1)? != 0,
            created_at: row.get(2)?,
        })
    })?;
    rows.collect()
}
