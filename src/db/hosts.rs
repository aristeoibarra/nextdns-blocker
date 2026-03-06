use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::HostEntry;

pub fn add_host_entry(
    conn: &Connection,
    domain: &str,
    ip: &str,
    source_domain: Option<&str>,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO hosts_entries (domain, ip, source_domain, added_at)
         VALUES (?1, ?2, ?3, ?4)
         ON CONFLICT(domain) DO UPDATE SET
           ip = ?2,
           source_domain = COALESCE(?3, source_domain)",
        params![domain, ip, source_domain, now],
    )?;
    Ok(())
}

pub fn remove_host_entry(conn: &Connection, domain: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "DELETE FROM hosts_entries WHERE domain = ?1",
        params![domain],
    )?;
    Ok(rows > 0)
}

pub fn list_host_entries(conn: &Connection) -> Result<Vec<HostEntry>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, ip, source_domain, added_at
         FROM hosts_entries ORDER BY domain",
    )?;
    let rows = stmt.query_map([], map_host_entry)?;
    rows.collect()
}

pub fn get_entries_for_source(
    conn: &Connection,
    source_domain: &str,
) -> Result<Vec<HostEntry>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, ip, source_domain, added_at
         FROM hosts_entries WHERE source_domain = ?1",
    )?;
    let rows = stmt.query_map(params![source_domain], map_host_entry)?;
    rows.collect()
}

fn map_host_entry(row: &rusqlite::Row) -> Result<HostEntry, rusqlite::Error> {
    Ok(HostEntry {
        domain: row.get(0)?,
        ip: row.get(1)?,
        source_domain: row.get(2)?,
        added_at: row.get(3)?,
    })
}
