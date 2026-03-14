use rusqlite::{params, Connection};

use crate::common::time::now_unix;
use crate::types::Category;

pub fn create_category(
    conn: &Connection,
    name: &str,
    description: Option<&str>,
    schedule: Option<&str>,
) -> Result<i64, rusqlite::Error> {
    let now = now_unix();
    conn.execute(
        "INSERT INTO categories (name, description, schedule, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?4)",
        params![name, description, schedule, now],
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn delete_category(conn: &Connection, name: &str) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute("DELETE FROM categories WHERE name = ?1", params![name])?;
    Ok(rows > 0)
}

pub fn get_category(conn: &Connection, name: &str) -> Result<Option<Category>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, name, description, schedule, created_at, updated_at
         FROM categories WHERE name = ?1",
    )?;
    let mut rows = stmt.query_map(params![name], map_category)?;
    rows.next().transpose()
}

pub fn list_categories(conn: &Connection) -> Result<Vec<Category>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT id, name, description, schedule, created_at, updated_at
         FROM categories ORDER BY name",
    )?;
    let rows = stmt.query_map([], map_category)?;
    rows.collect()
}

pub fn add_domain_to_category(
    conn: &Connection,
    category_name: &str,
    domain: &str,
) -> Result<bool, rusqlite::Error> {
    let cat_id: Option<i64> = conn
        .query_row(
            "SELECT id FROM categories WHERE name = ?1",
            params![category_name],
            |row| row.get(0),
        )
        .ok();

    let Some(cat_id) = cat_id else {
        return Ok(false);
    };

    let now = now_unix();
    conn.execute(
        "INSERT OR IGNORE INTO category_domains (category_id, domain, created_at)
         VALUES (?1, ?2, ?3)",
        params![cat_id, domain, now],
    )?;
    Ok(true)
}

pub fn remove_domain_from_category(
    conn: &Connection,
    category_name: &str,
    domain: &str,
) -> Result<bool, rusqlite::Error> {
    let rows = conn.execute(
        "DELETE FROM category_domains WHERE domain = ?1
         AND category_id = (SELECT id FROM categories WHERE name = ?2)",
        params![domain, category_name],
    )?;
    Ok(rows > 0)
}

pub fn list_category_domains(
    conn: &Connection,
    category_name: &str,
) -> Result<Vec<String>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT cd.domain FROM category_domains cd
         JOIN categories c ON cd.category_id = c.id
         WHERE c.name = ?1 ORDER BY cd.domain",
    )?;
    let rows = stmt.query_map(params![category_name], |row| row.get(0))?;
    rows.collect()
}

/// List category domains with their descriptions from blocked_domains (LEFT JOIN).
pub fn list_category_domains_with_desc(
    conn: &Connection,
    category_name: &str,
) -> Result<Vec<(String, Option<String>)>, rusqlite::Error> {
    let mut stmt = conn.prepare(
        "SELECT cd.domain, bd.description
         FROM category_domains cd
         JOIN categories c ON cd.category_id = c.id
         LEFT JOIN blocked_domains bd ON cd.domain = bd.domain
         WHERE c.name = ?1 ORDER BY cd.domain",
    )?;
    let rows = stmt.query_map(params![category_name], |row| {
        Ok((row.get(0)?, row.get(1)?))
    })?;
    rows.collect()
}

fn map_category(row: &rusqlite::Row) -> Result<Category, rusqlite::Error> {
    Ok(Category {
        id: row.get(0)?,
        name: row.get(1)?,
        description: row.get(2)?,
        schedule: row.get(3)?,
        created_at: row.get(4)?,
        updated_at: row.get(5)?,
    })
}
