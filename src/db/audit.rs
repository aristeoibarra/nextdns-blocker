use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::AuditEntry;

pub fn log_action(
    conn: &Connection,
    action: &str,
    target_type: &str,
    target_id: &str,
    details: Option<&str>,
    source: &str,
) -> Result<i64, rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO audit_log (action, target_type, target_id, details, timestamp, source)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![action, target_type, target_id, details, now, source],
    )?;
    Ok(conn.last_insert_rowid())
}

/// Filter criteria for audit queries.
pub struct AuditFilter {
    pub domain: Option<String>,
    pub action: Option<String>,
    pub source: Option<String>,
}

pub fn list_audit(
    conn: &Connection,
    limit: i64,
    offset: i64,
    filter: &AuditFilter,
) -> Result<Vec<AuditEntry>, rusqlite::Error> {
    let mut sql = String::from(
        "SELECT id, action, target_type, target_id, details, timestamp, source FROM audit_log"
    );
    let mut conditions = Vec::new();
    let mut param_values: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();

    if let Some(ref domain) = filter.domain {
        let idx = param_values.len() + 1;
        // Search target_id and details for the domain
        conditions.push(format!("(target_id = ?{idx} OR details LIKE ?{})", idx + 1));
        param_values.push(Box::new(domain.clone()));
        param_values.push(Box::new(format!("%{domain}%")));
    }
    if let Some(ref action) = filter.action {
        let idx = param_values.len() + 1;
        conditions.push(format!("action = ?{idx}"));
        param_values.push(Box::new(action.clone()));
    }
    if let Some(ref source) = filter.source {
        let idx = param_values.len() + 1;
        conditions.push(format!("source = ?{idx}"));
        param_values.push(Box::new(source.clone()));
    }

    if !conditions.is_empty() {
        sql.push_str(" WHERE ");
        sql.push_str(&conditions.join(" AND "));
    }

    let limit_idx = param_values.len() + 1;
    let offset_idx = param_values.len() + 2;
    sql.push_str(&format!(" ORDER BY timestamp DESC LIMIT ?{limit_idx} OFFSET ?{offset_idx}"));
    param_values.push(Box::new(limit));
    param_values.push(Box::new(offset));

    let params_ref: Vec<&dyn rusqlite::types::ToSql> = param_values.iter().map(|p| p.as_ref()).collect();

    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(params_ref.as_slice(), |row| {
        Ok(AuditEntry {
            id: row.get(0)?,
            action: row.get(1)?,
            target_type: row.get(2)?,
            target_id: row.get(3)?,
            details: row.get(4)?,
            timestamp: row.get(5)?,
            source: row.get(6)?,
        })
    })?;
    rows.collect()
}

pub fn count_audit(conn: &Connection, filter: &AuditFilter) -> Result<i64, rusqlite::Error> {
    let mut sql = String::from("SELECT COUNT(*) FROM audit_log");
    let mut conditions = Vec::new();
    let mut param_values: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();

    if let Some(ref domain) = filter.domain {
        let idx = param_values.len() + 1;
        conditions.push(format!("(target_id = ?{idx} OR details LIKE ?{})", idx + 1));
        param_values.push(Box::new(domain.clone()));
        param_values.push(Box::new(format!("%{domain}%")));
    }
    if let Some(ref action) = filter.action {
        let idx = param_values.len() + 1;
        conditions.push(format!("action = ?{idx}"));
        param_values.push(Box::new(action.clone()));
    }
    if let Some(ref source) = filter.source {
        let idx = param_values.len() + 1;
        conditions.push(format!("source = ?{idx}"));
        param_values.push(Box::new(source.clone()));
    }

    if !conditions.is_empty() {
        sql.push_str(" WHERE ");
        sql.push_str(&conditions.join(" AND "));
    }

    let params_ref: Vec<&dyn rusqlite::types::ToSql> = param_values.iter().map(|p| p.as_ref()).collect();
    conn.query_row(&sql, params_ref.as_slice(), |row| row.get(0))
}
