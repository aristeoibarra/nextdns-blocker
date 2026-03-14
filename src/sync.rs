use std::collections::HashSet;

use crate::api::NextDnsClient;
use crate::db::Database;
use crate::error::AppError;
use crate::output::Renderable;
use crate::scheduler::ScheduleEvaluator;

const RETRY_MAX_ATTEMPTS: i32 = 5;

/// Update in_nextdns state and audit-log if the DB write fails.
fn update_in_nextdns(db: &Database, domain: &str, list: &str, value: bool) {
    let result = match list {
        "denylist" => db.with_conn(|conn| crate::db::domains::set_in_nextdns_blocked(conn, domain, value)),
        "allowlist" => db.with_conn(|conn| crate::db::domains::set_in_nextdns_allowed(conn, domain, value)),
        _ => return,
    };
    if let Err(e) = result {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(
                conn, "in_nextdns_update_failed", list, domain,
                Some(&format!("Failed to set in_nextdns={value}: {e}")),
                "sync",
            )
        });
    }
}

// === Result types ===

/// Result of a full drift-detection sync (GET + diff).
#[derive(Debug, serde::Serialize)]
pub struct SyncResult {
    pub denylist: SyncListResult,
    pub allowlist: SyncListResult,
    pub categories: SyncListResult,
}

#[derive(Debug, serde::Serialize)]
pub struct SyncListResult {
    pub added: Vec<String>,
    pub removed: Vec<String>,
    pub unchanged: usize,
    pub errors: Vec<SyncError>,
}

#[derive(Debug, serde::Serialize)]
pub struct SyncError {
    pub domain: String,
    pub error: String,
    /// True for 401/403 errors that indicate invalid credentials (not retryable).
    #[serde(skip_serializing_if = "std::ops::Not::not")]
    pub auth_error: bool,
}

/// Result of a lightweight schedule-based sync (no GETs).
#[derive(Debug, serde::Serialize)]
pub struct ScheduleSyncResult {
    pub added: Vec<String>,
    pub removed: Vec<String>,
    pub errors: Vec<SyncError>,
}

impl Renderable for SyncResult {
    fn command_name(&self) -> &str { "sync" }

    fn to_json(&self) -> serde_json::Value {
        let total_added = self.denylist.added.len()
            + self.allowlist.added.len()
            + self.categories.added.len();
        let total_removed = self.denylist.removed.len()
            + self.allowlist.removed.len()
            + self.categories.removed.len();

        serde_json::json!({
            "data": {
                "denylist": self.denylist,
                "allowlist": self.allowlist,
                "categories": self.categories,
            },
            "summary": { "added": total_added, "removed": total_removed }
        })
    }
}

// === Eager push helpers (called from command handlers) ===

/// Result of an eager push attempt.
#[derive(Debug, Default)]
pub struct EagerPushResult {
    pub pushed: usize,
    pub retrying: usize,
}

/// Immediately push denylist changes to NextDNS.
/// On success, updates `in_nextdns`. On failure, enqueues retry.
/// Returns counts so callers can report API failures to the user.
pub fn eager_push_denylist(db: &Database, client: &NextDnsClient, domains: &[String], add: bool) -> EagerPushResult {
    let mut result = EagerPushResult::default();
    let mut changed = false;
    for domain in domains {
        let api_call = || if add { client.add_to_denylist(domain) } else { client.remove_from_denylist(domain) };
        if api_call().is_ok() || api_call().is_ok() {
            changed = true;
            result.pushed += 1;
            update_in_nextdns(db, domain, "denylist", add);
        } else {
            enqueue_retry(db, if add { "add" } else { "remove" }, Some(domain), "denylist");
            result.retrying += 1;
        }
    }
    if changed {
        crate::common::platform::flush_dns_cache();
    }
    result
}

/// Immediately push allowlist changes to NextDNS.
/// On success, updates `in_nextdns`. On failure, enqueues retry.
/// Returns counts so callers can report API failures to the user.
pub fn eager_push_allowlist(db: &Database, client: &NextDnsClient, domains: &[String], add: bool) -> EagerPushResult {
    let mut result = EagerPushResult::default();
    let mut changed = false;
    for domain in domains {
        let api_call = || if add { client.add_to_allowlist(domain) } else { client.remove_from_allowlist(domain) };
        if api_call().is_ok() || api_call().is_ok() {
            changed = true;
            result.pushed += 1;
            update_in_nextdns(db, domain, "allowlist", add);
        } else {
            enqueue_retry(db, if add { "add" } else { "remove" }, Some(domain), "allowlist");
            result.retrying += 1;
        }
    }
    if changed {
        crate::common::platform::flush_dns_cache();
    }
    result
}

/// Immediately push a parental control category change. Retries once on failure before enqueuing.
pub fn eager_push_category(db: &Database, client: &NextDnsClient, id: &str, add: bool) -> EagerPushResult {
    let mut result = EagerPushResult::default();
    let ok = client.set_parental_category(id, add).is_ok()
        || client.set_parental_category(id, add).is_ok();
    if ok {
        crate::common::platform::flush_dns_cache();
        result.pushed = 1;
    } else {
        enqueue_retry(db, if add { "add" } else { "remove" }, Some(id), "category");
        result.retrying = 1;
    }
    result
}

fn enqueue_retry(db: &Database, action: &str, target: Option<&str>, list_type: &str) {
    let retry_at = crate::common::time::now_unix() + 60;
    let id = uuid::Uuid::new_v4().to_string();
    let _ = db.with_conn(|conn| {
        crate::db::retry::enqueue_retry(
            conn, &id, action, target, list_type, None, RETRY_MAX_ATTEMPTS, retry_at,
        )
    });
}

// === Schedule sync (lightweight, no GETs) ===

/// Evaluate time-based schedule rules against `in_nextdns` state.
/// Only makes API calls when schedule state actually changes — zero GETs.
/// Run this every watchdog cycle.
pub fn execute_schedule_sync(
    db: &Database,
    client: &NextDnsClient,
    evaluator: &ScheduleEvaluator,
) -> Result<ScheduleSyncResult, AppError> {
    let domains = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;

    let mut added = Vec::new();
    let mut removed = Vec::new();
    let mut errors = Vec::new();
    let mut auth_failed = false;

    for domain in &domains {
        let schedule = domain.schedule.as_deref().and_then(|s| {
            match serde_json::from_str::<crate::config::types::Schedule>(s) {
                Ok(sched) => Some(sched),
                Err(e) => {
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(
                            conn, "schedule_parse_error", "domain", &domain.domain,
                            Some(&format!("Malformed schedule JSON: {e}")),
                            "schedule",
                        )
                    });
                    None
                }
            }
        });

        // If schedule JSON exists but failed to parse, preserve current state
        // to avoid accidentally unblocking domains with corrupted schedules.
        if domain.schedule.is_some() && schedule.is_none() {
            continue;
        }

        let parsed = schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);
        let should_be_in_nextdns = evaluator.should_block(parsed.as_ref());

        if should_be_in_nextdns && !domain.in_nextdns {
            if auth_failed {
                errors.push(SyncError { domain: domain.domain.clone(), error: "Skipped: auth credentials invalid".to_string(), auth_error: true });
                continue;
            }
            match client.add_to_denylist(&domain.domain) {
                Ok(()) => {
                    update_in_nextdns(db, &domain.domain, "denylist", true);
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(
                            conn, "schedule_block", "domain", &domain.domain,
                            Some("Schedule rule activated — added to NextDNS denylist"),
                            "schedule",
                        )
                    });
                    added.push(domain.domain.clone());
                }
                Err(e) => {
                    let is_auth = e.is_auth_error();
                    if !is_auth {
                        enqueue_retry(db, "add", Some(&domain.domain), "denylist");
                    } else {
                        auth_failed = true;
                    }
                    errors.push(SyncError { domain: domain.domain.clone(), error: e.to_string(), auth_error: is_auth });
                }
            }
        } else if !should_be_in_nextdns && domain.in_nextdns {
            if auth_failed {
                errors.push(SyncError { domain: domain.domain.clone(), error: "Skipped: auth credentials invalid".to_string(), auth_error: true });
                continue;
            }
            match client.remove_from_denylist(&domain.domain) {
                Ok(()) => {
                    update_in_nextdns(db, &domain.domain, "denylist", false);
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(
                            conn, "schedule_unblock", "domain", &domain.domain,
                            Some("Schedule rule deactivated — removed from NextDNS denylist"),
                            "schedule",
                        )
                    });
                    removed.push(domain.domain.clone());
                }
                Err(e) => {
                    let is_auth = e.is_auth_error();
                    if !is_auth {
                        enqueue_retry(db, "remove", Some(&domain.domain), "denylist");
                    } else {
                        auth_failed = true;
                    }
                    errors.push(SyncError { domain: domain.domain.clone(), error: e.to_string(), auth_error: is_auth });
                }
            }
        }
        // State is already correct — no API call needed
    }

    // === Allowlist schedule processing ===
    let allowed_domains = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;

    for domain in &allowed_domains {
        let Some(schedule_str) = &domain.schedule else { continue };

        let schedule = match serde_json::from_str::<crate::config::types::Schedule>(schedule_str) {
            Ok(sched) => Some(sched),
            Err(e) => {
                let _ = db.with_conn(|conn| {
                    crate::db::audit::log_action(
                        conn, "schedule_parse_error", "allowlist", &domain.domain,
                        Some(&format!("Malformed schedule JSON: {e}")),
                        "schedule",
                    )
                });
                None
            }
        };

        // If schedule JSON failed to parse, preserve current state
        if schedule.is_none() {
            continue;
        }

        let parsed = schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);

        // Inverted semantics: is_available = should be in NextDNS allowlist
        let should_be_in_nextdns = evaluator.is_available(parsed.as_ref());

        if should_be_in_nextdns && !domain.in_nextdns {
            if auth_failed {
                errors.push(SyncError { domain: domain.domain.clone(), error: "Skipped: auth credentials invalid".to_string(), auth_error: true });
                continue;
            }
            match client.add_to_allowlist(&domain.domain) {
                Ok(()) => {
                    update_in_nextdns(db, &domain.domain, "allowlist", true);
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(
                            conn, "schedule_allow", "allowlist", &domain.domain,
                            Some("Schedule rule activated — added to NextDNS allowlist"),
                            "schedule",
                        )
                    });
                    added.push(domain.domain.clone());
                }
                Err(e) => {
                    let is_auth = e.is_auth_error();
                    if !is_auth {
                        enqueue_retry(db, "add", Some(&domain.domain), "allowlist");
                    } else {
                        auth_failed = true;
                    }
                    errors.push(SyncError { domain: domain.domain.clone(), error: e.to_string(), auth_error: is_auth });
                }
            }
        } else if !should_be_in_nextdns && domain.in_nextdns {
            if auth_failed {
                errors.push(SyncError { domain: domain.domain.clone(), error: "Skipped: auth credentials invalid".to_string(), auth_error: true });
                continue;
            }
            match client.remove_from_allowlist(&domain.domain) {
                Ok(()) => {
                    update_in_nextdns(db, &domain.domain, "allowlist", false);
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(
                            conn, "schedule_disallow", "allowlist", &domain.domain,
                            Some("Schedule rule deactivated — removed from NextDNS allowlist"),
                            "schedule",
                        )
                    });
                    removed.push(domain.domain.clone());
                }
                Err(e) => {
                    let is_auth = e.is_auth_error();
                    if !is_auth {
                        enqueue_retry(db, "remove", Some(&domain.domain), "allowlist");
                    } else {
                        auth_failed = true;
                    }
                    errors.push(SyncError { domain: domain.domain.clone(), error: e.to_string(), auth_error: is_auth });
                }
            }
        }
    }

    // Block/unblock apps for schedule-driven denylist changes
    if !added.is_empty() {
        let deny_added: Vec<String> = added.iter()
            .filter(|d| domains.iter().any(|dd| dd.domain == **d))
            .cloned()
            .collect();
        if !deny_added.is_empty() {
            let _ = crate::app_blocker::block_apps_for_domains(db, &deny_added);
            let _ = crate::android_blocker::block_android_for_domains(db, &deny_added, None);
            crate::browser_blocker::close_tabs_for_domains(&deny_added);
        }
    }
    if !removed.is_empty() {
        let deny_removed: Vec<String> = removed.iter()
            .filter(|d| domains.iter().any(|dd| dd.domain == **d))
            .cloned()
            .collect();
        for domain in &deny_removed {
            let _ = crate::app_blocker::unblock_apps_for_domain(db, domain);
            let _ = crate::android_blocker::unblock_android_for_domain(db, domain);
        }
    }

    if !added.is_empty() || !removed.is_empty() {
        crate::common::platform::flush_dns_cache();
    }

    Ok(ScheduleSyncResult { added, removed, errors })
}

// === Drift sync (full GET + diff, run every 30 min) ===

/// Full GET-based sync against NextDNS API. Detects drift from web UI changes.
/// Updates `in_nextdns` for all domains to reflect confirmed remote state.
/// Run this infrequently (every 30 min). For manual `ndb sync`, always runs.
pub fn execute_drift_sync(
    db: &Database,
    client: &NextDnsClient,
    evaluator: &ScheduleEvaluator,
    dry_run: bool,
) -> Result<SyncResult, AppError> {
    let local_blocked = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;
    let local_allowed = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;

    let remote_denylist = client.get_denylist()?;
    let remote_allowlist = client.get_allowlist()?;

    let remote_blocked_set: HashSet<String> = remote_denylist.iter().filter(|e| e.active).map(|e| e.id.clone()).collect();
    let remote_allowed_set: HashSet<String> = remote_allowlist.iter().filter(|e| e.active).map(|e| e.id.clone()).collect();

    let should_block: HashSet<String> = local_blocked
        .iter()
        .filter(|d| {
            let schedule = d.schedule.as_deref().and_then(|s| {
                serde_json::from_str::<crate::config::types::Schedule>(s).ok()
            });
            let parsed = schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);
            evaluator.should_block(parsed.as_ref())
        })
        .map(|d| d.domain.clone())
        .collect();

    let should_allow: HashSet<String> = local_allowed
        .iter()
        .filter(|d| {
            match &d.schedule {
                Some(s) => {
                    let schedule = serde_json::from_str::<crate::config::types::Schedule>(s).ok();
                    let parsed = schedule.as_ref().and_then(crate::scheduler::parse_config_schedule);
                    evaluator.is_available(parsed.as_ref())
                }
                None => true,
            }
        })
        .map(|d| d.domain.clone())
        .collect();

    let to_add_blocked: Vec<String> = should_block.difference(&remote_blocked_set).cloned().collect();
    let to_remove_blocked: Vec<String> = remote_blocked_set.difference(&should_block).cloned().collect();
    let to_add_allowed: Vec<String> = should_allow.difference(&remote_allowed_set).cloned().collect();
    let to_remove_allowed: Vec<String> = remote_allowed_set.difference(&should_allow).cloned().collect();

    // === NextDNS categories and services ===
    let local_categories = db.with_conn(crate::db::nextdns::list_nextdns_categories)?;
    let remote_categories = client.get_parental_categories()?;

    let local_cat_set: HashSet<String> = local_categories.iter().filter(|c| c.active).map(|c| c.id.clone()).collect();
    let remote_cat_set: HashSet<String> = remote_categories.iter().filter(|c| c.active).map(|c| c.id.clone()).collect();
    let to_add_cats: Vec<String> = local_cat_set.difference(&remote_cat_set).cloned().collect();
    let to_remove_cats: Vec<String> = remote_cat_set.difference(&local_cat_set).cloned().collect();

    // Confirm unchanged domains are marked as in_nextdns (local-only, safe for dry-run)
    for domain in should_block.intersection(&remote_blocked_set) {
        update_in_nextdns(db, domain, "denylist", true);
    }
    for domain in should_allow.intersection(&remote_allowed_set) {
        update_in_nextdns(db, domain, "allowlist", true);
    }

    if dry_run {
        return Ok(SyncResult {
            denylist: SyncListResult {
                added: to_add_blocked, removed: to_remove_blocked,
                unchanged: should_block.intersection(&remote_blocked_set).count(), errors: vec![],
            },
            allowlist: SyncListResult {
                added: to_add_allowed, removed: to_remove_allowed,
                unchanged: should_allow.intersection(&remote_allowed_set).count(), errors: vec![],
            },
            categories: SyncListResult {
                added: to_add_cats, removed: to_remove_cats,
                unchanged: local_cat_set.intersection(&remote_cat_set).count(), errors: vec![],
            },
        });
    }

    // === Execute denylist sync ===
    let mut denylist_errors = Vec::new();
    let mut denylist_added = Vec::new();
    for domain in &to_add_blocked {
        match client.add_to_denylist(domain) {
            Ok(()) => {
                update_in_nextdns(db, domain, "denylist", true);
                denylist_added.push(domain.clone());
            }
            Err(e) => {
                let se = SyncError { domain: domain.clone(), error: e.to_string(), auth_error: e.is_auth_error() };
                denylist_errors.push(se);
            }
        }
    }
    let mut denylist_removed = Vec::new();
    for domain in &to_remove_blocked {
        match client.remove_from_denylist(domain) {
            Ok(()) => {
                update_in_nextdns(db, domain, "denylist", false);
                denylist_removed.push(domain.clone());
            }
            Err(e) => {
                let se = SyncError { domain: domain.clone(), error: e.to_string(), auth_error: e.is_auth_error() };
                denylist_errors.push(se);
            }
        }
    }

    // === Execute allowlist sync ===
    let mut allowlist_errors = Vec::new();
    let mut allowlist_added = Vec::new();
    for domain in &to_add_allowed {
        match client.add_to_allowlist(domain) {
            Ok(()) => {
                update_in_nextdns(db, domain, "allowlist", true);
                allowlist_added.push(domain.clone());
            }
            Err(e) => {
                let se = SyncError { domain: domain.clone(), error: e.to_string(), auth_error: e.is_auth_error() };
                allowlist_errors.push(se);
            }
        }
    }
    let mut allowlist_removed = Vec::new();
    for domain in &to_remove_allowed {
        match client.remove_from_allowlist(domain) {
            Ok(()) => {
                update_in_nextdns(db, domain, "allowlist", false);
                allowlist_removed.push(domain.clone());
            }
            Err(e) => {
                let se = SyncError { domain: domain.clone(), error: e.to_string(), auth_error: e.is_auth_error() };
                allowlist_errors.push(se);
            }
        }
    }

    // === Execute categories sync ===
    let mut cat_errors = Vec::new();
    let mut cat_added = Vec::new();
    for id in &to_add_cats {
        match client.set_parental_category(id, true) {
            Ok(()) => cat_added.push(id.clone()),
            Err(e) => {
                let se = SyncError { domain: id.clone(), error: e.to_string(), auth_error: e.is_auth_error() };
                cat_errors.push(se);
            }
        }
    }
    let mut cat_removed = Vec::new();
    for id in &to_remove_cats {
        match client.set_parental_category(id, false) {
            Ok(()) => cat_removed.push(id.clone()),
            Err(e) => {
                let se = SyncError { domain: id.clone(), error: e.to_string(), auth_error: e.is_auth_error() };
                cat_errors.push(se);
            }
        }
    }

    // Enqueue retries only for non-auth errors (auth errors are permanent, not retryable)
    let all_errors: Vec<(&str, &str, &SyncError)> = denylist_errors.iter().map(|e| ("add", "denylist", e))
        .chain(allowlist_errors.iter().map(|e| ("add", "allowlist", e)))
        .chain(cat_errors.iter().map(|e| ("add", "category", e)))
        .collect();

    if !all_errors.is_empty() {
        let retry_at = crate::common::time::now_unix() + 60;
        for (action, list_type, err) in &all_errors {
            if err.auth_error { continue; }
            let id = uuid::Uuid::new_v4().to_string();
            let _ = db.with_conn(|conn| {
                crate::db::retry::enqueue_retry(
                    conn, &id, action, Some(&err.domain), list_type,
                    None, RETRY_MAX_ATTEMPTS, retry_at,
                )
            });
        }
    }

    let had_changes = !denylist_added.is_empty() || !denylist_removed.is_empty()
        || !allowlist_added.is_empty() || !allowlist_removed.is_empty()
        || !cat_added.is_empty() || !cat_removed.is_empty();

    if had_changes {
        crate::common::platform::flush_dns_cache();
    }

    Ok(SyncResult {
        denylist: SyncListResult {
            added: denylist_added, removed: denylist_removed,
            unchanged: should_block.intersection(&remote_blocked_set).count(), errors: denylist_errors,
        },
        allowlist: SyncListResult {
            added: allowlist_added, removed: allowlist_removed,
            unchanged: should_allow.intersection(&remote_allowed_set).count(), errors: allowlist_errors,
        },
        categories: SyncListResult {
            added: cat_added, removed: cat_removed,
            unchanged: local_cat_set.intersection(&remote_cat_set).count(), errors: cat_errors,
        },
    })
}

/// Record the current time as the last drift check timestamp.
pub fn record_drift_check(db: &Database) {
    let now = crate::common::time::now_unix().to_string();
    let _ = db.with_conn(|conn| crate::db::config::set_value(conn, "last_drift_check", &now));
}
