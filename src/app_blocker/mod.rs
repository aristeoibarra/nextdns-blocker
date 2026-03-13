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
    /// Set when a reinstalled .app was found alongside .blocked during unblock.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conflict_path: Option<String>,
}

/// Find the installed path of an app by bundle ID using Spotlight.
pub fn find_app_path(bundle_id: &str) -> Option<String> {
    // Validate bundle_id to prevent mdfind query injection
    if !bundle_id.chars().all(|c| c.is_ascii_alphanumeric() || c == '.' || c == '-' || c == '_') {
        return None;
    }

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

/// Kill all running instances of an app by exact name.
pub fn kill_app(app_name: &str) {
    let _ = Command::new("killall").args(["-e", app_name]).output();
}

/// Compute the blocked path by stripping `.app` to prevent macOS from
/// recognizing the directory as an application bundle.
/// e.g. `/Applications/WhatsApp.app` → `/Applications/WhatsApp.blocked`
fn blocked_path_for(app_path: &str) -> String {
    if let Some(stem) = app_path.strip_suffix(".app") {
        format!("{stem}.blocked")
    } else {
        format!("{app_path}.blocked")
    }
}

/// Unregister an app path from macOS LaunchServices so it no longer appears
/// in Spotlight, Launchpad, or other app launchers.
fn unregister_app(path: &str) {
    let _ = Command::new("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister")
        .args(["-u", path])
        .output();
}

/// Remove execute permission from all binaries inside the bundle's MacOS directory.
/// This prevents macOS from launching the app even if the bundle structure is intact.
fn disable_binary(blocked_path: &str) {
    let macos_dir = format!("{blocked_path}/Contents/MacOS");
    if let Ok(entries) = std::fs::read_dir(&macos_dir) {
        for entry in entries.flatten() {
            let _ = Command::new("chmod").args(["-x", &entry.path().to_string_lossy().to_string()]).output();
        }
    }
}

/// Restore execute permission on all binaries inside the bundle's MacOS directory.
fn enable_binary(app_path: &str) {
    let macos_dir = format!("{app_path}/Contents/MacOS");
    if let Ok(entries) = std::fs::read_dir(&macos_dir) {
        for entry in entries.flatten() {
            let _ = Command::new("chmod").args(["+x", &entry.path().to_string_lossy().to_string()]).output();
        }
    }
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

    let blocked_path = blocked_path_for(&path);

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

    // 1. Rename .app -> .blocked (strip .app to prevent macOS recognizing it as app bundle)
    std::fs::rename(&path, &blocked_path).map_err(|e| AppError::General {
        message: format!("Failed to block app {app_name}: {e}"),
        hint: Some("Ensure ndb has Full Disk Access in System Settings > Privacy & Security".to_string()),
    })?;

    // 2. Remove execute permission from binaries to prevent launching
    disable_binary(&blocked_path);

    // 3. Unregister from LaunchServices so Launchpad/Spotlight stop showing it
    unregister_app(&path);
    unregister_app(&blocked_path);

    // 4. Kill running instances after rename succeeded
    kill_app(app_name);

    // 5. Record in DB — rollback rename if DB write fails
    if let Err(e) = db.with_conn(|conn| {
        crate::db::apps::add_blocked_app(
            conn, bundle_id, app_name, &path, &blocked_path, source_domain,
        )
    }) {
        // Rollback: restore .app from .app.blocked
        if let Err(rename_err) = std::fs::rename(&blocked_path, &path) {
            // Rollback failed — filesystem and DB are now inconsistent.
            // Log to audit so `ndb apps doctor` can detect and repair this orphan.
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(
                    conn, "block_rollback_failed", "app", bundle_id,
                    Some(&format!(
                        "DB write failed ({e}), rename rollback also failed ({rename_err}). \
                         Orphaned .app.blocked at {blocked_path}"
                    )),
                    "system",
                )
            });
        }
        return Err(e);
    }

    Ok(Some(AppBlockResult {
        bundle_id: bundle_id.to_string(),
        app_name: app_name.to_string(),
        path,
    }))
}

/// Unblock an app: restore .app.blocked to .app and remove from DB.
/// Filesystem operations happen BEFORE DB changes to prevent inconsistency:
/// if rename fails, DB still reflects the blocked state accurately.
pub fn unblock_app(db: &Database, bundle_id: &str) -> Result<Option<AppUnblockResult>, AppError> {
    let record = match db.with_conn(|conn| crate::db::apps::get_blocked_app(conn, bundle_id))? {
        Some(r) => r,
        None => return Ok(None),
    };

    let blocked = Path::new(&record.blocked_path);
    let original = Path::new(&record.original_path);
    let mut conflict_path = None;

    // 1. Restore filesystem FIRST (before DB change)
    if blocked.exists() {
        if original.exists() {
            // App was reinstalled while blocked. Don't delete the new install.
            // Move the old blocked copy aside so nothing is lost.
            let conflict = format!("{}.conflict", record.original_path);
            std::fs::rename(blocked, &conflict).map_err(|e| AppError::General {
                message: format!("Failed to move blocked app aside {}: {e}", record.app_name),
                hint: Some(
                    "Ensure ndb has Full Disk Access in System Settings > Privacy & Security"
                        .to_string(),
                ),
            })?;
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
                    "system",
                )
            });
            conflict_path = Some(conflict);
        } else {
            // Restore execute permission before renaming back
            enable_binary(&record.blocked_path);
            std::fs::rename(blocked, original).map_err(|e| AppError::General {
                message: format!("Failed to restore app {}: {e}", record.app_name),
                hint: Some(
                    "Ensure ndb has Full Disk Access in System Settings > Privacy & Security"
                        .to_string(),
                ),
            })?;
        }
    }

    // 2. Remove from DB AFTER filesystem is restored.
    // If DB write fails, rollback the filesystem change.
    if let Err(e) = db.with_conn(|conn| crate::db::apps::remove_blocked_app(conn, bundle_id)) {
        if let Some(ref conflict) = conflict_path {
            // Conflict case: can't rollback — filesystem moved to .conflict but DB still thinks blocked.
            // Audit-log so `ndb apps doctor` can detect and repair.
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(
                    conn, "unblock_rollback_failed", "app", bundle_id,
                    Some(&format!(
                        "DB write failed ({e}), blocked copy at {conflict}. \
                         DB/filesystem inconsistent — run 'ndb apps doctor --repair'"
                    )),
                    "system",
                )
            });
        } else if original.exists() && !blocked.exists() {
            let _ = std::fs::rename(original, blocked);
        }
        return Err(e);
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

    // Migrate old .app.blocked convention → .blocked (removes .app so macOS won't recognize it)
    for app in &blocked {
        if app.blocked_path.ends_with(".app.blocked") {
            let new_blocked = blocked_path_for(&app.original_path);
            let old_exists = Path::new(&app.blocked_path).exists();
            let new_exists = Path::new(&new_blocked).exists();

            if old_exists && !new_exists {
                if std::fs::rename(&app.blocked_path, &new_blocked).is_ok() {
                    disable_binary(&new_blocked);
                    unregister_app(&app.blocked_path);
                    unregister_app(&new_blocked);
                    kill_app(&app.app_name);
                    let _ = db.with_conn(|conn| {
                        crate::db::apps::update_blocked_path(conn, &app.bundle_id, &new_blocked)
                    });
                }
            }
        }
    }

    // Reload after potential migration
    let blocked = db.with_conn(crate::db::apps::list_blocked_apps)?;

    // Re-rename: if someone manually restored .app, put it back.
    for app in &blocked {
        if Path::new(&app.original_path).exists() {
            kill_app(&app.app_name);
            if let Err(e) = std::fs::rename(&app.original_path, &app.blocked_path) {
                let _ = db.with_conn(|conn| {
                    crate::db::audit::log_action(
                        conn, "enforce_rename_failed", "app", &app.bundle_id,
                        Some(&format!("Failed to re-block {}: {e}", app.app_name)),
                        "preflight",
                    )
                });
            } else {
                disable_binary(&app.blocked_path);
                unregister_app(&app.original_path);
                unregister_app(&app.blocked_path);
            }
        }
    }

    // Ensure execute permission is removed on all blocked app binaries
    for app in &blocked {
        if Path::new(&app.blocked_path).exists() {
            disable_binary(&app.blocked_path);
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
    /// `.blocked` files on disk not tracked in the database.
    pub orphans: Vec<String>,
    /// DB records whose `.blocked` AND `.app` no longer exist on disk.
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

    // Scan filesystem for .blocked entries (and legacy .app.blocked)
    let home = std::env::var("HOME").unwrap_or_default();
    let dirs = ["/Applications", &format!("{home}/Applications")];

    let mut on_disk = Vec::new();
    for dir in &dirs {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                if let Some(name) = entry.file_name().to_str() {
                    if name.ends_with(".blocked") {
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
            hint: Some("Ensure system_profiler is available at /usr/sbin/system_profiler".to_string()),
        })?;

    if !output.status.success() {
        return Err(AppError::General {
            message: "system_profiler failed".to_string(),
            hint: Some("Try running 'system_profiler SPApplicationsDataType' manually".to_string()),
        });
    }

    let json: serde_json::Value =
        serde_json::from_slice(&output.stdout).map_err(|e| AppError::General {
            message: format!("Failed to parse system_profiler output: {e}"),
            hint: Some("system_profiler returned unexpected format".to_string()),
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
