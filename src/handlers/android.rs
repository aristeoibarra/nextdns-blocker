use crate::android_blocker::firebase::FirebaseClient;
use crate::cli::android::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: AndroidCommands) -> Result<ExitCode, AppError> {
    match cmd {
        AndroidCommands::Sync(_) => handle_sync(),
        AndroidCommands::Scan(_) => handle_scan(),
        AndroidCommands::List(_) => handle_list(),
    }
}

fn handle_sync() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    let sync_result = crate::android_blocker::compute_and_sync(&db)?;

    let blocked: Vec<serde_json::Value> = sync_result.blocked.iter().map(|e| {
        serde_json::json!({
            "package": e.package_name,
            "name": e.display_name,
            "reason": e.reason,
        })
    }).collect();

    let allowed: Vec<serde_json::Value> = sync_result.allowed.iter().map(|e| {
        serde_json::json!({
            "package": e.package_name,
            "name": e.display_name,
            "reason": e.reason,
        })
    }).collect();

    // Individual push tracking (pending retries from ndb block)
    let pending_pushes = db.with_conn(crate::db::android::list_remote_blocked).unwrap_or_default();
    let pending_entries: Vec<serde_json::Value> = pending_pushes.iter()
        .filter(|b| !b.in_firebase)
        .map(|b| serde_json::json!({
            "package_name": b.package_name,
            "domain": b.domain,
            "push_error": b.push_error,
        }))
        .collect();

    let out = AndroidResult {
        command: "android sync",
        data: serde_json::json!({
            "blocked": blocked,
            "allowed": allowed,
            "total_blocked": sync_result.total_blocked,
            "total_allowed": allowed.len(),
            "pending_pushes": pending_entries,
        }),
    };
    output::render(&out);
    Ok(ExitCode::Success)
}

fn handle_scan() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    let client = FirebaseClient::try_new(&db).ok_or_else(|| AppError::Config {
        message: "Firebase not configured".to_string(),
        hint: Some(
            "Set firebase_project_id, firebase_rtdb_url, android_device_id via 'ndb config set' \
             and firebase-service-account via 'ndb config set-secret'"
                .to_string(),
        ),
    })?;

    let installed = client.get_installed_packages()?;

    let packages = match installed.as_object() {
        Some(obj) => obj,
        None => {
            let result = AndroidResult {
                command: "android scan",
                data: serde_json::json!({
                    "device_id": client.device_id,
                    "installed_packages": 0,
                    "new_mappings": 0,
                    "packages": [],
                }),
            };
            output::render(&result);
            return Ok(ExitCode::Success);
        }
    };

    let existing = db.with_conn(crate::db::android::list_mappings)?;
    let mut new_count = 0usize;
    let mut package_list = Vec::new();

    // Collect new mappings from known built-in associations
    let mut to_add: Vec<(String, String, String)> = Vec::new();

    for (encoded_key, info) in packages {
        // Android encodes '.' as '~' in Firebase keys; decode, or use "package" field
        let pkg_name = info
            .get("package")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| encoded_key.replace('~', "."));
        let pkg = &pkg_name;
        let label = info
            .get("label")
            .and_then(|v| v.as_str())
            .unwrap_or(pkg)
            .to_string();
        let version = info
            .get("version")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();

        // Check if this package has a known domain mapping
        let known_domains: Vec<&str> = crate::android_blocker::mappings::ANDROID_PACKAGES
            .iter()
            .filter(|(_, p, _)| *p == pkg.as_str())
            .map(|(d, _, _)| *d)
            .collect();

        let already_mapped = existing.iter().any(|m| m.package_name == *pkg);

        for domain in &known_domains {
            let already = existing
                .iter()
                .any(|m| m.package_name == *pkg && m.domain == *domain);
            if !already {
                to_add.push((domain.to_string(), pkg.clone(), label.clone()));
            }
        }

        package_list.push(serde_json::json!({
            "package": pkg,
            "label": label,
            "version": version,
            "known_domains": known_domains,
            "already_mapped": already_mapped,
        }));
    }

    if !to_add.is_empty() {
        db.with_transaction(|conn| {
            for (domain, pkg, label) in &to_add {
                crate::db::android::add_mapping(conn, domain, pkg, label, true)
                    .map_err(AppError::from)?;
            }
            Ok(())
        })?;
        new_count = to_add.len();
    }

    let result = AndroidResult {
        command: "android scan",
        data: serde_json::json!({
            "device_id": client.device_id,
            "installed_packages": packages.len(),
            "new_mappings": new_count,
            "packages": package_list,
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_list() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    let mappings = db.with_conn(crate::db::android::list_mappings)?;

    let entries: Vec<serde_json::Value> = mappings
        .iter()
        .map(|m| {
            serde_json::json!({
                "domain": m.domain,
                "package_name": m.package_name,
                "display_name": m.display_name,
                "auto": m.auto,
            })
        })
        .collect();

    let result = AndroidResult {
        command: "android list",
        data: serde_json::json!({ "mappings": entries }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct AndroidResult {
    command: &'static str,
    data: serde_json::Value,
}
impl Renderable for AndroidResult {
    fn command_name(&self) -> &str {
        self.command
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": self.data })
    }
}
