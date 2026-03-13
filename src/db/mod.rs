pub mod apps;
pub mod audit;
pub mod categories;
pub mod config;
pub mod domains;
pub mod hosts;
pub mod nextdns;
pub mod pending;

pub mod retry;
pub mod schema;



use std::path::Path;
use std::sync::Mutex;

use rusqlite::Connection;

use crate::error::AppError;

/// Thread-safe database wrapper.
pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    /// Open (or create) a database at the given path and run migrations.
    pub fn open(path: &Path) -> Result<Self, AppError> {
        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(path)?;
        let db = Self {
            conn: Mutex::new(conn),
        };
        db.configure()?;
        db.migrate()?;
        Ok(db)
    }

    /// Open an in-memory database (for testing).
    pub fn open_memory() -> Result<Self, AppError> {
        let conn = Connection::open_in_memory()?;
        let db = Self {
            conn: Mutex::new(conn),
        };
        db.configure()?;
        db.migrate()?;
        Ok(db)
    }

    /// Acquire the database connection lock, converting poison errors.
    fn lock_conn(&self) -> Result<std::sync::MutexGuard<'_, Connection>, AppError> {
        self.conn.lock().map_err(|_| AppError::General {
            message: "Database mutex poisoned — a previous operation panicked".to_string(),
            hint: Some("Restart the application".to_string()),
        })
    }

    /// Configure SQLite pragmas.
    fn configure(&self) -> Result<(), AppError> {
        let conn = self.lock_conn()?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA foreign_keys = ON;
             PRAGMA busy_timeout = 5000;",
        )?;
        Ok(())
    }

    /// Run pending migrations.
    fn migrate(&self) -> Result<(), AppError> {
        let conn = self.lock_conn()?;

        // Bootstrap: create schema_migrations if it doesn't exist (can't be STRICT for bootstrap)
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                applied_at INTEGER NOT NULL
            );",
        )?;

        let current_version: i64 = conn
            .query_row(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations",
                [],
                |row| row.get(0),
            )?;

        let migrations = schema::get_migrations();

        for (version, name, sql) in &migrations {
            if *version > current_version {
                conn.execute_batch(sql)?;
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?1, ?2, ?3)",
                    rusqlite::params![version, name, crate::common::time::now_unix()],
                )?;
            }
        }

        Ok(())
    }

    /// Execute a closure with the database connection.
    pub fn with_conn<F, T>(&self, f: F) -> Result<T, AppError>
    where
        F: FnOnce(&Connection) -> Result<T, rusqlite::Error>,
    {
        let conn = self.lock_conn()?;
        f(&conn).map_err(AppError::from)
    }

    /// Execute a closure inside an explicit SQLite transaction.
    /// Commits on Ok, rolls back on Err.
    pub fn with_transaction<F, T>(&self, f: F) -> Result<T, AppError>
    where
        F: FnOnce(&Connection) -> Result<T, AppError>,
    {
        let conn = self.lock_conn()?;
        conn.execute_batch("BEGIN")?;
        match f(&conn) {
            Ok(val) => {
                conn.execute_batch("COMMIT")?;
                Ok(val)
            }
            Err(e) => {
                if let Err(rollback_err) = conn.execute_batch("ROLLBACK") {
                    // Surface rollback failure alongside the original error
                    return Err(AppError::General {
                        message: format!(
                            "Transaction failed: {e}. Additionally, ROLLBACK failed: {rollback_err}"
                        ),
                        hint: Some("Database may be in an inconsistent state. Restart the application.".to_string()),
                    });
                }
                Err(e)
            }
        }
    }
}
