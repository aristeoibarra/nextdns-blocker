pub mod mappings;

use std::path::Path;
use std::process::Command;

use crate::db::Database;
use crate::error::AppError;

/// Result of blocking a single app.
#[derive(Debug, serde::Serialize)]
pub struct AppBlockResult {
    pub bundle_id: String,
    pub app_name: String,
    pub path: String,
}

/// Result of unblocking a single app.
#[derive(Debug, serde::Serialize)]
pub struct AppUnblockResult {
    pub bundle_id: String,
    pub app_name: String,
    /// Set when a reinstalled .app was found alongside .app.blocked during unblock.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conflict_path: Option<String>,
}

/// Find the installed path of an app by bundle ID using Spotlight.
pub fn find_app_path(bundle_id: &str) -> Option<String> {
    let output = Command::new("mdfind")
        .arg(format!("kMDItemCFBundleIdentifier == '{bundle_id}'"))
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    // Take the first result that ends with .app
    stdout
        .lines()
        .find(|line| line.ends_with(".app"))
        .map(|s| s.to_string())
}

/// Kill all running instances of an app by name.
pub fn kill_app(app_name: &str) {
    let _ = Command::new("killall").arg(app_name).output();
}

/// Block an app: kill process + rename .app to .app.blocked.
/// Records the state in the database.
pub fn block_app(
    db: &Database,
    bundle_id: &str,
    app_name: &str,
    source_domain: Option<&str>,
) -> Result<Option<AppBlockResult>, AppError> {
    // Check if already blocked in DB
    let already = db.with_conn(|conn| crate::db::apps::get_blocked_app(conn, bundle_id))?;
    if already.is_some() {
        return Ok(None);
    }

    let path = match find_app_path(bundle_id) {
        Some(p) => p,
        None => return Ok(None),
    };

    let blocked_path = format!("{path}.blocked");

    // Skip if .app doesn't exist (might already be renamed externally)
    if !Path::new(&path).exists() {
        // Check if blocked_path exists — already blocked outside ndb
        if Path::new(&blocked_path).exists() {
            db.with_conn(|conn| {
                crate::db::apps::add_blocked_app(
                    conn, bundle_id, app_name, &path, &blocked_path, source_domain,
                )
            })?;
        }
        return Ok(None);
    }

    // 1. Kill the process
    kill_app(app_name);

    // 2. Rename .app -> .app.blocked
    std::fs::rename(&path, &blocked_path).map_err(|e| AppError::General {
        message: format!("Failed to block app {app_name}: {e}"),
        hint: Some("Ensure ndb has Full Disk Access in System Settings > Privacy & Security".to_string()),
    })?;

    // 3. Record in DB — rollback rename if DB write fails
    if let Err(e) = db.with_conn(|conn| {
        crate::db::apps::add_blocked_app(
            conn, bundle_id, app_name, &path, &blocked_path, source_domain,
        )
    }) {
        // Rollback: restore .app from .app.blocked
        let _ = std::fs::rename(&blocked_path, &path);
        return Err(e);
    }

    Ok(Some(AppBlockResult {
        bundle_id: bundle_id.to_string(),
        app_name: app_name.to_string(),
        path,
    }))
}

/// Unblock an app: restore .app.blocked to .app and remove from DB.
pub fn unblock_app(db: &Database, bundle_id: &str) -> Result<Option<AppUnblockResult>, AppError> {
    let record = match db.with_conn(|conn| crate::db::apps::get_blocked_app(conn, bundle_id))? {
        Some(r) => r,
        None => return Ok(None),
    };

    let blocked = Path::new(&record.blocked_path);
    let original = Path::new(&record.original_path);

    // Remove from DB first, then restore filesystem.
    // If rename fails, re-add to DB so state stays consistent.
    db.with_conn(|conn| crate::db::apps::remove_blocked_app(conn, bundle_id))?;

    let mut conflict_path = None;

    if blocked.exists() {
        if original.exists() {
            // App was reinstalled while blocked. Don't delete the new install.
            // Move the old blocked copy aside so nothing is lost.
            let conflict = format!("{}.conflict", record.original_path);
            let _ = std::fs::rename(blocked, &conflict);
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(
                    conn,
                    "unblock_conflict",
                    "app",
                    bundle_id,
                    Some(&format!(
                        "Reinstalled app at {}; blocked copy moved to {conflict}",
                        record.original_path
                    )),
                )
            });
            conflict_path = Some(conflict);
        } else if let Err(e) = std::fs::rename(blocked, original) {
            // Re-add to DB since we couldn't complete the unblock
            let _ = db.with_conn(|conn| {
                crate::db::apps::add_blocked_app(
                    conn,
                    bundle_id,
                    &record.app_name,
                    &record.original_path,
                    &record.blocked_path,
                    record.source_domain.as_deref(),
                )
            });
            return Err(AppError::General {
                message: format!("Failed to restore app {}: {e}", record.app_name),
                hint: Some(
                    "Ensure ndb has Full Disk Access in System Settings > Privacy & Security"
                        .to_string(),
                ),
            });
        }
    }

    Ok(Some(AppUnblockResult {
        bundle_id: bundle_id.to_string(),
        app_name: record.app_name,
        conflict_path,
    }))
}

/// Block all apps mapped to the given domains. Returns what was actually blocked.
pub fn block_apps_for_domains(
    db: &Database,
    domains: &[String],
) -> Result<Vec<AppBlockResult>, AppError> {
    let mut results = Vec::new();

    for domain in domains {
        let mappings =
            db.with_conn(|conn| crate::db::apps::get_mappings_for_domain(conn, domain))?;

        for mapping in mappings {
            if let Some(result) =
                block_app(db, &mapping.bundle_id, &mapping.app_name, Some(domain))?
            {
                results.push(result);
            }
        }
    }

    Ok(results)
}

/// Unblock all apps mapped to the given domain. Returns what was actually unblocked.
pub fn unblock_apps_for_domain(
    db: &Database,
    domain: &str,
) -> Result<Vec<AppUnblockResult>, AppError> {
    let blocked =
        db.with_conn(|conn| crate::db::apps::get_blocked_apps_for_domain(conn, domain))?;

    let mut results = Vec::new();
    for app in blocked {
        if let Some(result) = unblock_app(db, &app.bundle_id)? {
            results.push(result);
        }
    }

    Ok(results)
}

/// Enforce blocked apps: re-rename any manually restored .app bundles and kill
/// running processes. Uses a single `ps` call instead of N `pgrep` calls.
/// Returns names of apps that were killed or re-blocked.
pub fn enforce_blocked_apps(db: &Database) -> Result<Vec<String>, AppError> {
    let blocked = db.with_conn(crate::db::apps::list_blocked_apps)?;
    if blocked.is_empty() {
        return Ok(Vec::new());
    }

    // Re-rename: if someone manually restored .app from .app.blocked, put it back.
    for app in &blocked {
        if Path::new(&app.original_path).exists() {
            kill_app(&app.app_name);
            let _ = std::fs::rename(&app.original_path, &app.blocked_path);
        }
    }

    // Single ps call to get all running process names (= suppresses header)
    let output = Command::new("ps")
        .args(["-Ac", "-o", "comm="])
        .output();

    let running_procs: std::collections::HashSet<String> = match output {
        Ok(out) if out.status.success() => String::from_utf8_lossy(&out.stdout)
            .lines()
            .map(|l| l.trim().to_lowercase())
            .collect(),
        _ => return Ok(Vec::new()),
    };

    let mut killed = Vec::new();
    for app in &blocked {
        if running_procs.contains(&app.app_name.to_lowercase()) {
            kill_app(&app.app_name);
            killed.push(app.app_name.clone());
        }
    }

    Ok(killed)
}

/// Restore ALL blocked apps (emergency/cleanup). Returns count restored.
pub fn restore_all(db: &Database) -> Result<Vec<AppUnblockResult>, AppError> {
    let blocked = db.with_conn(crate::db::apps::list_blocked_apps)?;
    let mut results = Vec::new();

    for app in blocked {
        if let Some(result) = unblock_app(db, &app.bundle_id)? {
            results.push(result);
        }
    }

    Ok(results)
}

/// Result of the doctor reconciliation check.
#[derive(Debug, serde::Serialize)]
pub struct DoctorReport {
    /// `.app.blocked` files on disk not tracked in the database.
    pub orphans: Vec<String>,
    /// DB records whose `.app.blocked` AND `.app` no longer exist on disk.
    pub phantoms: Vec<PhantomApp>,
}

#[derive(Debug, serde::Serialize)]
pub struct PhantomApp {
    pub bundle_id: String,
    pub app_name: String,
    pub blocked_path: String,
}

/// Reconcile blocked apps between filesystem and database.
/// Scans `/Applications` and `~/Applications` for `.app.blocked` files and
/// compares against the `blocked_apps` table.
pub fn doctor(db: &Database) -> Result<DoctorReport, AppError> {
    let blocked = db.with_conn(crate::db::apps::list_blocked_apps)?;
    let blocked_paths: std::collections::HashSet<&str> =
        blocked.iter().map(|b| b.blocked_path.as_str()).collect();

    // Scan filesystem for .app.blocked entries
    let home = std::env::var("HOME").unwrap_or_default();
    let dirs = ["/Applications", &format!("{home}/Applications")];

    let mut on_disk = Vec::new();
    for dir in &dirs {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                if let Some(name) = entry.file_name().to_str() {
                    if name.ends_with(".app.blocked") {
                        if let Some(path) = entry.path().to_str() {
                            on_disk.push(path.to_string());
                        }
                    }
                }
            }
        }
    }

    let orphans: Vec<String> = on_disk
        .into_iter()
        .filter(|p| !blocked_paths.contains(p.as_str()))
        .collect();

    let phantoms: Vec<PhantomApp> = blocked
        .into_iter()
        .filter(|b| !Path::new(&b.blocked_path).exists() && !Path::new(&b.original_path).exists())
        .map(|b| PhantomApp {
            bundle_id: b.bundle_id,
            app_name: b.app_name,
            blocked_path: b.blocked_path,
        })
        .collect();

    Ok(DoctorReport { orphans, phantoms })
}

/// Scan installed apps and return (bundle_id, app_name, path) for all .app bundles.
pub fn scan_installed_apps() -> Result<Vec<(String, String, String)>, AppError> {
    let output = Command::new("system_profiler")
        .args(["SPApplicationsDataType", "-json"])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to run system_profiler: {e}"),
            hint: None,
        })?;

    if !output.status.success() {
        return Err(AppError::General {
            message: "system_profiler failed".to_string(),
            hint: None,
        });
    }

    let json: serde_json::Value =
        serde_json::from_slice(&output.stdout).map_err(|e| AppError::General {
            message: format!("Failed to parse system_profiler output: {e}"),
            hint: None,
        })?;

    let mut apps = Vec::new();

    if let Some(items) = json
        .get("SPApplicationsDataType")
        .and_then(|v| v.as_array())
    {
        for item in items {
            let bundle_id = item.get("bundleIdentifier").and_then(|v| v.as_str());
            let name = item.get("_name").and_then(|v| v.as_str());
            let path = item.get("path").and_then(|v| v.as_str());

            if let (Some(bid), Some(n), Some(p)) = (bundle_id, name, path) {
                apps.push((bid.to_string(), n.to_string(), p.to_string()));
            }
        }
    }

    Ok(apps)
}
