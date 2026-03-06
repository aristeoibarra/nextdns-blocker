use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::{AppMapping, BlockedApp};

// === App Mappings ===

pub fn add_mapping(
    conn: &Connection,
    domain: &str,
    bundle_id: &str,
    app_name: &str,
    auto: bool,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO app_mappings (domain, bundle_id, app_name, auto, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5)
         ON CONFLICT(domain, bundle_id) DO UPDATE SET
           app_name = ?3,
           auto = ?4",
        params![domain, bundle_id, app_name, auto as i64, now],
    )?;
    Ok(())
}

pub fn remove_mapping(
    conn: &Connection,
    domain: &str,
    bundle_id: &str,
) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "DELETE FROM app_mappings WHERE domain = ?1 AND bundle_id = ?2",
        params![domain, bundle_id],
    )?;
    Ok(rows > 0)
}

pub fn get_mappings_for_domain(
    conn: &Connection,
    domain: &str,
) -> Result<Vec<AppMapping>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, bundle_id, app_name, auto, created_at
         FROM app_mappings WHERE domain = ?1",
    )?;
    let rows = stmt.query_map(params![domain], map_app_mapping)?;
    rows.collect()
}

pub fn get_mappings_for_bundle(
    conn: &Connection,
    bundle_id: &str,
) -> Result<Vec<AppMapping>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, bundle_id, app_name, auto, created_at
         FROM app_mappings WHERE bundle_id = ?1",
    )?;
    let rows = stmt.query_map(params![bundle_id], map_app_mapping)?;
    rows.collect()
}

pub fn list_mappings(conn: &Connection) -> Result<Vec<AppMapping>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, bundle_id, app_name, auto, created_at
         FROM app_mappings ORDER BY domain, app_name",
    )?;
    let rows = stmt.query_map([], map_app_mapping)?;
    rows.collect()
}

fn map_app_mapping(row: &rusqlite::Row) -> Result<AppMapping, rusqlite::Error> {
    Ok(AppMapping {
        domain: row.get(0)?,
        bundle_id: row.get(1)?,
        app_name: row.get(2)?,
        auto: row.get::<_, i64>(3)? != 0,
        created_at: row.get(4)?,
    })
}

// === Blocked Apps ===

pub fn add_blocked_app(
    conn: &Connection,
    bundle_id: &str,
    app_name: &str,
    original_path: &str,
    blocked_path: &str,
    source_domain: Option<&str>,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO blocked_apps (bundle_id, app_name, original_path, blocked_path, source_domain, blocked_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)
         ON CONFLICT(bundle_id) DO UPDATE SET
           source_domain = COALESCE(?5, source_domain),
           blocked_at = ?6",
        params![bundle_id, app_name, original_path, blocked_path, source_domain, now],
    )?;
    Ok(())
}

pub fn remove_blocked_app(conn: &Connection, bundle_id: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "DELETE FROM blocked_apps WHERE bundle_id = ?1",
        params![bundle_id],
    )?;
    Ok(rows > 0)
}

pub fn get_blocked_app(
    conn: &Connection,
    bundle_id: &str,
) -> Result<Option<BlockedApp>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT bundle_id, app_name, original_path, blocked_path, source_domain, blocked_at
         FROM blocked_apps WHERE bundle_id = ?1",
    )?;
    let mut rows = stmt.query_map(params![bundle_id], map_blocked_app)?;
    rows.next().transpose()
}

pub fn list_blocked_apps(conn: &Connection) -> Result<Vec<BlockedApp>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT bundle_id, app_name, original_path, blocked_path, source_domain, blocked_at
         FROM blocked_apps ORDER BY app_name",
    )?;
    let rows = stmt.query_map([], map_blocked_app)?;
    rows.collect()
}

pub fn get_blocked_apps_for_domain(
    conn: &Connection,
    domain: &str,
) -> Result<Vec<BlockedApp>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT bundle_id, app_name, original_path, blocked_path, source_domain, blocked_at
         FROM blocked_apps WHERE source_domain = ?1",
    )?;
    let rows = stmt.query_map(params![domain], map_blocked_app)?;
    rows.collect()
}

fn map_blocked_app(row: &rusqlite::Row) -> Result<BlockedApp, rusqlite::Error> {
    Ok(BlockedApp {
        bundle_id: row.get(0)?,
        app_name: row.get(1)?,
        original_path: row.get(2)?,
        blocked_path: row.get(3)?,
        source_domain: row.get(4)?,
        blocked_at: row.get(5)?,
    })
}
