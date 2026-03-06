pub mod pin;
pub mod unlock;

use crate::db::Database;
use crate::error::AppError;

/// Check if a domain or category is locked (protected from removal/weakening).
pub fn is_locked(db: &Database, target_type: &str, target_id: &str) -> Result<bool, AppError> {
    match target_type {
        "category" => db.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT is_locked FROM categories WHERE name = ?1",
            )?;
            let result: Option<bool> = stmt
                .query_map(rusqlite::params![target_id], |row| {
                    Ok(row.get::<_, i64>(0)? != 0)
                })?
                .next()
                .transpose()?;
            Ok(result.unwrap_or(false))
        }),
        _ => Ok(false),
    }
}

/// Validate that a removal operation doesn't affect locked items.
pub fn validate_no_locked_removal(
    db: &Database,
    domains: &[String],
) -> Result<Vec<String>, AppError> {
    let mut locked = Vec::new();
    db.with_conn(|conn| {
        for domain in domains {
            // Check if domain belongs to a locked category
            let is_in_locked: bool = conn.query_row(
                "SELECT EXISTS(
                    SELECT 1 FROM category_domains cd
                    JOIN categories c ON cd.category_id = c.id
                    WHERE cd.domain = ?1 AND c.is_locked = 1
                )",
                rusqlite::params![domain],
                |row| row.get(0),
            )?;
            if is_in_locked {
                locked.push(domain.clone());
            }
        }
        Ok(())
    })?;
    Ok(locked)
}
