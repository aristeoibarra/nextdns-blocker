use rusqlite::{params, Connection};

use crate::types::DailyStats;

pub fn increment_stat(
    conn: &Connection,
    date: &str,
    field: &str,
) -> Result<(), rusqlite::Error> {
    // Ensure the row exists
    conn.execute(
        "INSERT OR IGNORE INTO daily_stats (date) VALUES (?1)",
        params![date],
    )?;

    // Increment the specific field
    let sql = match field {
        "domains_blocked" => {
            "UPDATE daily_stats SET domains_blocked = domains_blocked + 1 WHERE date = ?1"
        }
        "domains_allowed" => {
            "UPDATE daily_stats SET domains_allowed = domains_allowed + 1 WHERE date = ?1"
        }
        "sync_count" => {
            "UPDATE daily_stats SET sync_count = sync_count + 1 WHERE date = ?1"
        }
        "api_errors" => {
            "UPDATE daily_stats SET api_errors = api_errors + 1 WHERE date = ?1"
        }
        _ => return Ok(()),
    };

    conn.execute(sql, params![date])?;
    Ok(())
}

pub fn get_stats(conn: &Connection, date: &str) -> Result<Option<DailyStats>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT date, domains_blocked, domains_allowed, sync_count, api_errors
         FROM daily_stats WHERE date = ?1",
    )?;
    let mut rows = stmt.query_map(params![date], map_stats)?;
    rows.next().transpose()
}

pub fn get_stats_range(
    conn: &Connection,
    from: &str,
    to: &str,
) -> Result<Vec<DailyStats>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT date, domains_blocked, domains_allowed, sync_count, api_errors
         FROM daily_stats WHERE date >= ?1 AND date <= ?2 ORDER BY date",
    )?;
    let rows = stmt.query_map(params![from, to], map_stats)?;
    rows.collect()
}

fn map_stats(row: &rusqlite::Row) -> Result<DailyStats, rusqlite::Error> {
    Ok(DailyStats {
        date: row.get(0)?,
        domains_blocked: row.get(1)?,
        domains_allowed: row.get(2)?,
        sync_count: row.get(3)?,
        api_errors: row.get(4)?,
    })
}
