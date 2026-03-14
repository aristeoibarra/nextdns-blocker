pub mod fcm;
pub mod firebase;
pub mod mappings;

use crate::db::Database;
use crate::error::AppError;

#[derive(Debug, serde::Serialize)]
pub struct AndroidBlockResult {
    pub package_name: String,
    pub display_name: String,
    pub domain: String,
}

#[derive(Debug, serde::Serialize)]
pub struct AndroidUnblockResult {
    pub package_name: String,
    pub display_name: String,
    pub domain: String,
}

/// Block Android packages for the given domains via Firebase RTDB + FCM push.
/// Returns Ok(vec![]) if Firebase is not configured (silent skip).
pub fn block_android_for_domains(
    db: &Database,
    domains: &[String],
    duration: Option<&std::time::Duration>,
) -> Result<Vec<AndroidBlockResult>, AppError> {
    let client = match firebase::FirebaseClient::try_new(db) {
        Some(c) => c,
        None => return Ok(Vec::new()),
    };

    let unblock_at = duration.map(|d| crate::common::time::now_unix() + d.as_secs() as i64);
    let mut results = Vec::new();

    for domain in domains {
        // Check DB mappings first, then fall back to built-in mappings
        let packages = get_packages_for_domain(db, domain);

        for (package_name, display_name) in &packages {
            // Record in local DB
            db.with_conn(|conn| {
                crate::db::android::add_remote_blocked(conn, package_name, domain, &client.device_id, unblock_at)
            })?;

            // Push to Firebase RTDB
            match client.set_package_blocked(package_name, domain, unblock_at) {
                Ok(()) => {
                    db.with_conn(|conn| {
                        crate::db::android::set_in_firebase(conn, package_name, true, None)
                    })?;
                    results.push(AndroidBlockResult {
                        package_name: package_name.to_string(),
                        display_name: display_name.to_string(),
                        domain: domain.clone(),
                    });
                }
                Err(e) => {
                    let _ = db.with_conn(|conn| {
                        crate::db::android::set_in_firebase(conn, package_name, false, Some(&e.to_string()))
                    });
                }
            }
        }
    }

    // Send a single FCM push for all changes
    if !results.is_empty() {
        let _ = fcm::send_sync_push(&client);
    }

    Ok(results)
}

/// Unblock Android packages for a domain via Firebase RTDB + FCM push.
/// Returns Ok(vec![]) if Firebase is not configured (silent skip).
pub fn unblock_android_for_domain(
    db: &Database,
    domain: &str,
) -> Result<Vec<AndroidUnblockResult>, AppError> {
    let client = match firebase::FirebaseClient::try_new(db) {
        Some(c) => c,
        None => return Ok(Vec::new()),
    };

    let blocked = db.with_conn(|conn| crate::db::android::get_blocked_for_domain(conn, domain))?;
    let mut results = Vec::new();

    for entry in &blocked {
        // Remove from Firebase RTDB
        let _ = client.remove_package(&entry.package_name);

        // Remove from local DB
        db.with_conn(|conn| crate::db::android::remove_remote_blocked(conn, &entry.package_name))?;

        // Look up display name
        let display_name = get_display_name(db, &entry.package_name, domain);
        results.push(AndroidUnblockResult {
            package_name: entry.package_name.clone(),
            display_name,
            domain: domain.to_string(),
        });
    }

    // Send FCM push
    if !results.is_empty() {
        let _ = fcm::send_sync_push(&client);
    }

    Ok(results)
}

/// Retry pushing packages that failed to sync to Firebase.
pub fn retry_pending_pushes(db: &Database) -> Result<(), AppError> {
    let client = match firebase::FirebaseClient::try_new(db) {
        Some(c) => c,
        None => return Ok(()),
    };

    let pending = db.with_conn(crate::db::android::get_pending_push)?;
    if pending.is_empty() {
        return Ok(());
    }

    let mut any_success = false;
    for entry in &pending {
        match client.set_package_blocked(&entry.package_name, &entry.domain, entry.unblock_at) {
            Ok(()) => {
                db.with_conn(|conn| {
                    crate::db::android::set_in_firebase(conn, &entry.package_name, true, None)
                })?;
                any_success = true;
            }
            Err(e) => {
                let _ = db.with_conn(|conn| {
                    crate::db::android::set_in_firebase(conn, &entry.package_name, false, Some(&e.to_string()))
                });
            }
        }
    }

    if any_success {
        let _ = fcm::send_sync_push(&client);
    }

    Ok(())
}

/// Compute which Android packages should be blocked based on:
/// 1. Active NextDNS categories → packages (block these)
/// 2. Allowlist domains → packages (don't block, respecting schedules)
/// 3. Denylist domains → packages (also block these)
/// Then atomically replace the blocked_packages node in Firebase RTDB.
#[derive(Debug, serde::Serialize)]
pub struct AndroidSyncResult {
    pub blocked: Vec<AndroidSyncEntry>,
    pub allowed: Vec<AndroidSyncEntry>,
    pub total_blocked: usize,
}

#[derive(Debug, serde::Serialize)]
pub struct AndroidSyncEntry {
    pub package_name: String,
    pub display_name: String,
    pub reason: String,
}

pub fn compute_and_sync(db: &Database) -> Result<AndroidSyncResult, AppError> {
    let client = match firebase::FirebaseClient::try_new(db) {
        Some(c) => c,
        None => return Err(AppError::Config {
            message: "Firebase not configured".to_string(),
            hint: Some("Set firebase_project_id, firebase_rtdb_url, android_device_id via 'ndb config set'".to_string()),
        }),
    };

    // 1. Collect packages to block from active NextDNS categories
    let all_categories = db.with_conn(crate::db::nextdns::list_nextdns_categories)?;
    let active_categories: Vec<_> = all_categories.into_iter().filter(|c| c.active).collect();
    let mut blocked_packages: std::collections::HashMap<String, (String, String)> = std::collections::HashMap::new(); // pkg -> (display_name, reason)

    for cat in &active_categories {
        for (pkg, name) in mappings::packages_for_category(&cat.id) {
            blocked_packages.entry(pkg.to_string())
                .or_insert_with(|| (name.to_string(), format!("category:{}", cat.id)));
        }
    }

    // 2. Collect packages to block from denylist (explicit domain blocks)
    let denylist = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;
    let tz: chrono_tz::Tz = db.with_conn(crate::db::config::get_timezone)?
        .parse()
        .unwrap_or(chrono_tz::UTC);
    let evaluator = crate::scheduler::ScheduleEvaluator::new(tz);

    for entry in &denylist {
        if !entry.active {
            continue;
        }
        // Evaluate schedule: if domain has a schedule and it's not blocking time, skip
        let config_schedule = entry.schedule.as_deref().and_then(|s| {
            serde_json::from_str::<crate::config::types::Schedule>(s).ok()
        });
        let parsed = config_schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);
        if !evaluator.should_block(parsed.as_ref()) {
            continue;
        }
        let packages = get_packages_for_domain(db, &entry.domain);
        for (pkg, name) in packages {
            blocked_packages.entry(pkg)
                .or_insert_with(|| (name, format!("denylist:{}", entry.domain)));
        }
    }

    // 3. Remove packages whose domains are in the allowlist (and currently available)
    let allowlist = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;
    let mut allowed_entries = Vec::new();

    for entry in &allowlist {
        if !entry.active {
            continue;
        }
        let config_schedule = entry.schedule.as_deref().and_then(|s| {
            serde_json::from_str::<crate::config::types::Schedule>(s).ok()
        });
        let parsed = config_schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);
        // For allowlist: is_available = true means the domain is allowed right now
        // No schedule = always allowed
        let is_allowed = parsed.is_none() || evaluator.is_available(parsed.as_ref());
        if !is_allowed {
            continue;
        }
        // Find packages for this allowed domain and remove from blocked set
        let packages = get_packages_for_domain(db, &entry.domain);
        for (pkg, name) in packages {
            if blocked_packages.remove(&pkg).is_some() {
                allowed_entries.push(AndroidSyncEntry {
                    package_name: pkg,
                    display_name: name,
                    reason: format!("allowlist:{}", entry.domain),
                });
            }
        }
    }

    // 4. Build Firebase payload and push atomically
    let now = crate::common::time::now_unix();
    let mut firebase_data: std::collections::HashMap<String, serde_json::Value> = std::collections::HashMap::new();

    let blocked_list: Vec<AndroidSyncEntry> = blocked_packages.iter()
        .map(|(pkg, (name, reason))| {
            let encoded = pkg.replace('.', "~");
            firebase_data.insert(encoded, serde_json::json!({
                "domain": reason.split(':').nth(1).unwrap_or(""),
                "blocked_at": now,
                "unblock_at": null,
            }));
            AndroidSyncEntry {
                package_name: pkg.clone(),
                display_name: name.clone(),
                reason: reason.clone(),
            }
        })
        .collect();

    let total = blocked_list.len();
    client.set_all_blocked_packages(&firebase_data)?;

    // Send FCM push to wake the Android app
    if !firebase_data.is_empty() {
        let _ = fcm::send_sync_push(&client);
    }

    Ok(AndroidSyncResult {
        blocked: blocked_list,
        allowed: allowed_entries,
        total_blocked: total,
    })
}

/// Get Android packages for a domain: DB mappings first, then built-in.
fn get_packages_for_domain(db: &Database, domain: &str) -> Vec<(String, String)> {
    // Try DB mappings first
    if let Ok(db_mappings) = db.with_conn(|conn| crate::db::android::get_mappings_for_domain(conn, domain)) {
        if !db_mappings.is_empty() {
            return db_mappings.into_iter().map(|m| (m.package_name, m.display_name)).collect();
        }
    }

    // Fall back to built-in mappings
    mappings::lookup_domain(domain)
        .into_iter()
        .map(|(pkg, name)| (pkg.to_string(), name.to_string()))
        .collect()
}

/// Get display name for a package from DB or built-in mappings.
fn get_display_name(db: &Database, package_name: &str, domain: &str) -> String {
    // Try built-in mappings first (cheapest)
    for (d, pkg, name) in mappings::ANDROID_PACKAGES {
        if *pkg == package_name && *d == domain {
            return name.to_string();
        }
    }

    // Try DB
    if let Ok(mappings) = db.with_conn(|conn| crate::db::android::get_mappings_for_domain(conn, domain)) {
        for m in &mappings {
            if m.package_name == package_name {
                return m.display_name.clone();
            }
        }
    }

    package_name.to_string()
}
