use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::{AndroidMapping, RemoteAndroidBlocked};

// === Android Package Mappings ===

pub fn add_mapping(
    conn: &Connection,
    domain: &str,
    package_name: &str,
    display_name: &str,
    auto: bool,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO android_package_mappings (domain, package_name, display_name, auto, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5)
         ON CONFLICT(domain, package_name) DO UPDATE SET
           display_name = ?3,
           auto = ?4",
        params![domain, package_name, display_name, auto as i64, now],
    )?;
    Ok(())
}

pub fn get_mappings_for_domain(
    conn: &Connection,
    domain: &str,
) -> Result<Vec<AndroidMapping>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, package_name, display_name, auto, created_at
         FROM android_package_mappings WHERE domain = ?1",
    )?;
    let rows = stmt.query_map(params![domain], map_android_mapping)?;
    rows.collect()
}

pub fn list_mappings(conn: &Connection) -> Result<Vec<AndroidMapping>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT domain, package_name, display_name, auto, created_at
         FROM android_package_mappings ORDER BY domain, display_name",
    )?;
    let rows = stmt.query_map([], map_android_mapping)?;
    rows.collect()
}

fn map_android_mapping(row: &rusqlite::Row) -> Result<AndroidMapping, rusqlite::Error> {
    Ok(AndroidMapping {
        domain: row.get(0)?,
        package_name: row.get(1)?,
        display_name: row.get(2)?,
        auto: row.get::<_, i64>(3)? != 0,
        created_at: row.get(4)?,
    })
}

// === Remote Android Blocked ===

pub fn add_remote_blocked(
    conn: &Connection,
    package_name: &str,
    domain: &str,
    device_id: &str,
    unblock_at: Option<i64>,
) -> Result<(), rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO remote_android_blocked (package_name, domain, device_id, blocked_at, unblock_at, in_firebase)
         VALUES (?1, ?2, ?3, ?4, ?5, 0)
         ON CONFLICT(package_name) DO UPDATE SET
           domain = ?2,
           device_id = ?3,
           blocked_at = ?4,
           unblock_at = ?5,
           in_firebase = 0,
           push_error = NULL",
        params![package_name, domain, device_id, now, unblock_at],
    )?;
    Ok(())
}

pub fn remove_remote_blocked(
    conn: &Connection,
    package_name: &str,
) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "DELETE FROM remote_android_blocked WHERE package_name = ?1",
        params![package_name],
    )?;
    Ok(rows > 0)
}

pub fn list_remote_blocked(conn: &Connection) -> Result<Vec<RemoteAndroidBlocked>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT package_name, domain, device_id, blocked_at, unblock_at, in_firebase, push_error
         FROM remote_android_blocked ORDER BY domain",
    )?;
    let rows = stmt.query_map([], map_remote_blocked)?;
    rows.collect()
}

pub fn get_blocked_for_domain(
    conn: &Connection,
    domain: &str,
) -> Result<Vec<RemoteAndroidBlocked>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT package_name, domain, device_id, blocked_at, unblock_at, in_firebase, push_error
         FROM remote_android_blocked WHERE domain = ?1",
    )?;
    let rows = stmt.query_map(params![domain], map_remote_blocked)?;
    rows.collect()
}

pub fn get_pending_push(conn: &Connection) -> Result<Vec<RemoteAndroidBlocked>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT package_name, domain, device_id, blocked_at, unblock_at, in_firebase, push_error
         FROM remote_android_blocked WHERE in_firebase = 0",
    )?;
    let rows = stmt.query_map([], map_remote_blocked)?;
    rows.collect()
}

pub fn set_in_firebase(
    conn: &Connection,
    package_name: &str,
    success: bool,
    error: Option<&str>,
) -> Result<(), rusqlite::Error> {
    conn.execute(
        "UPDATE remote_android_blocked SET in_firebase = ?1, push_error = ?2 WHERE package_name = ?3",
        params![success as i64, error, package_name],
    )?;
    Ok(())
}

fn map_remote_blocked(row: &rusqlite::Row) -> Result<RemoteAndroidBlocked, rusqlite::Error> {
    Ok(RemoteAndroidBlocked {
        package_name: row.get(0)?,
        domain: row.get(1)?,
        device_id: row.get(2)?,
        blocked_at: row.get(3)?,
        unblock_at: row.get(4)?,
        in_firebase: row.get::<_, i64>(5)? != 0,
        push_error: row.get(6)?,
    })
}
