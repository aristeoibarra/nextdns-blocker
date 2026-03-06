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

    // 3. Record in DB
    db.with_conn(|conn| {
        crate::db::apps::add_blocked_app(
            conn, bundle_id, app_name, &path, &blocked_path, source_domain,
        )
    })?;

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

    if blocked.exists() {
        // Remove original if somehow recreated
        if original.exists() {
            std::fs::remove_dir_all(original).map_err(|e| AppError::General {
                message: format!("Failed to clean up {}: {e}", record.original_path),
                hint: None,
            })?;
        }

        std::fs::rename(blocked, original).map_err(|e| AppError::General {
            message: format!("Failed to restore app {}: {e}", record.app_name),
            hint: Some(
                "Ensure ndb has Full Disk Access in System Settings > Privacy & Security"
                    .to_string(),
            ),
        })?;
    }

    db.with_conn(|conn| crate::db::apps::remove_blocked_app(conn, bundle_id))?;

    Ok(Some(AppUnblockResult {
        bundle_id: bundle_id.to_string(),
        app_name: record.app_name,
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

/// Enforce blocked apps: kill any that are somehow running.
/// Returns names of apps that were killed.
pub fn enforce_blocked_apps(db: &Database) -> Result<Vec<String>, AppError> {
    let blocked = db.with_conn(crate::db::apps::list_blocked_apps)?;
    let mut killed = Vec::new();

    for app in blocked {
        let output = Command::new("pgrep")
            .arg("-xi")
            .arg(&app.app_name)
            .output();

        if let Ok(out) = output {
            if out.status.success() {
                kill_app(&app.app_name);
                killed.push(app.app_name);
            }
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
