use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::{AllowedDomain, BlockedDomain};

// === Blocked domains (denylist) ===

pub fn add_blocked(
    conn: &Connection,
    domain: &str,
    description: Option<&str>,
    category: Option<&str>,
    schedule: Option<&str>,
) -> Result<i64, rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO blocked_domains (domain, description, category, schedule, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?5)
         ON CONFLICT(domain) DO UPDATE SET
           active = 1,
           description = COALESCE(?2, description),
           category = COALESCE(?3, category),
           schedule = COALESCE(?4, schedule),
           updated_at = ?5",
        params![domain, description, category, schedule, now],
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn remove_blocked(conn: &Connection, domain: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM blocked_domains WHERE domain = ?1", params![domain])?;
    Ok(rows > 0)
}

pub fn deactivate_blocked(conn: &Connection, domain: &str) -> Result<bool, rusqlite::Error> {
    let now = now_unix();
    let rows = conn.execute(
        "UPDATE blocked_domains SET active = 0, in_nextdns = 0, updated_at = ?1 WHERE domain = ?2 AND active = 1",
        params![now, domain],
    )?;
    Ok(rows > 0)
}

pub fn set_in_nextdns_blocked(conn: &Connection, domain: &str, value: bool) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE blocked_domains SET in_nextdns = ?1 WHERE domain = ?2",
        params![value as i64, domain],
    )?;
    Ok(())
}

pub fn set_in_nextdns_allowed(conn: &Connection, domain: &str, value: bool) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE allowed_domains SET in_nextdns = ?1 WHERE domain = ?2",
        params![value as i64, domain],
    )?;
    Ok(())
}

pub fn get_blocked(conn: &Connection, domain: &str) -> Result<Option<BlockedDomain>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, domain, active, description, category, schedule, created_at, updated_at, in_nextdns
         FROM blocked_domains WHERE domain = ?1",
    )?;
    let mut rows = stmt.query_map(params![domain], map_blocked)?;
    rows.next().transpose()
}

pub fn list_blocked(conn: &Connection, active_only: bool) -> Result<Vec<BlockedDomain>, rusqlite::Error> {
    let sql = if active_only {
        "SELECT id, domain, active, description, category, schedule, created_at, updated_at, in_nextdns
         FROM blocked_domains WHERE active = 1 ORDER BY domain"
    } else {
        "SELECT id, domain, active, description, category, schedule, created_at, updated_at, in_nextdns
         FROM blocked_domains ORDER BY domain"
    };
    let mut stmt = conn.prepare(sql)?;
    let rows = stmt.query_map([], map_blocked)?;
    rows.collect()
}

pub fn count_blocked(conn: &Connection) -> Result<i64, rusqlite::Error> {
    conn.query_row(
        "SELECT COUNT(*) FROM blocked_domains WHERE active = 1",
        [],
        |row| row.get(0),
    )
}

pub fn is_blocked(conn: &Connection, domain: &str) -> Result<bool, rusqlite::Error> {
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM blocked_domains WHERE domain = ?1 AND active = 1)",
        params![domain],
        |row| row.get(0),
    )
}

fn map_blocked(row: &rusqlite::Row) -> Result<BlockedDomain, rusqlite::Error> {
    Ok(BlockedDomain {
        id: row.get(0)?,
        domain: row.get(1)?,
        active: row.get::<_, i64>(2)? != 0,
        description: row.get(3)?,
        category: row.get(4)?,
        schedule: row.get(5)?,
        created_at: row.get(6)?,
        updated_at: row.get(7)?,
        in_nextdns: row.get::<_, i64>(8)? != 0,
    })
}

// === Allowed domains (allowlist) ===

pub fn add_allowed(
    conn: &Connection,
    domain: &str,
    description: Option<&str>,
) -> Result<i64, rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO allowed_domains (domain, description, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?3)
         ON CONFLICT(domain) DO UPDATE SET
           active = 1,
           description = COALESCE(?2, description),
           updated_at = ?3",
        params![domain, description, now],
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn remove_allowed(conn: &Connection, domain: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM allowed_domains WHERE domain = ?1", params![domain])?;
    Ok(rows > 0)
}

pub fn get_allowed(conn: &Connection, domain: &str) -> Result<Option<AllowedDomain>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, domain, active, description, created_at, updated_at, in_nextdns
         FROM allowed_domains WHERE domain = ?1",
    )?;
    let mut rows = stmt.query_map(params![domain], map_allowed)?;
    rows.next().transpose()
}

pub fn list_allowed(conn: &Connection, active_only: bool) -> Result<Vec<AllowedDomain>, rusqlite::Error> {
    let sql = if active_only {
        "SELECT id, domain, active, description, created_at, updated_at, in_nextdns
         FROM allowed_domains WHERE active = 1 ORDER BY domain"
    } else {
        "SELECT id, domain, active, description, created_at, updated_at, in_nextdns
         FROM allowed_domains ORDER BY domain"
    };
    let mut stmt = conn.prepare(sql)?;
    let rows = stmt.query_map([], map_allowed)?;
    rows.collect()
}

pub fn count_allowed(conn: &Connection) -> Result<i64, rusqlite::Error> {
    conn.query_row(
        "SELECT COUNT(*) FROM allowed_domains WHERE active = 1",
        [],
        |row| row.get(0),
    )
}

pub fn is_allowed(conn: &Connection, domain: &str) -> Result<bool, rusqlite::Error> {
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM allowed_domains WHERE domain = ?1 AND active = 1)",
        params![domain],
        |row| row.get(0),
    )
}

fn map_allowed(row: &rusqlite::Row) -> Result<AllowedDomain, rusqlite::Error> {
    Ok(AllowedDomain {
        id: row.get(0)?,
        domain: row.get(1)?,
        active: row.get::<_, i64>(2)? != 0,
        description: row.get(3)?,
        created_at: row.get(4)?,
        updated_at: row.get(5)?,
        in_nextdns: row.get::<_, i64>(6)? != 0,
    })
}
