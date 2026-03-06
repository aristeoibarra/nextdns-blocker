use std::collections::HashSet;

use crate::api::NextDnsClient;
use crate::db::Database;
use crate::error::AppError;
use crate::output::Renderable;
use crate::scheduler::ScheduleEvaluator;

const RETRY_MAX_ATTEMPTS: i32 = 5;

/// Result of a sync operation.
#[derive(Debug, serde::Serialize)]
pub struct SyncResult {
    pub denylist: SyncListResult,
    pub allowlist: SyncListResult,
    pub categories: SyncListResult,
    pub services: SyncListResult,
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
}

impl Renderable for SyncResult {
    fn command_name(&self) -> &str { "sync" }

    fn to_json(&self) -> serde_json::Value {
        let total_added = self.denylist.added.len()
            + self.allowlist.added.len()
            + self.categories.added.len()
            + self.services.added.len();
        let total_removed = self.denylist.removed.len()
            + self.allowlist.removed.len()
            + self.categories.removed.len()
            + self.services.removed.len();

        serde_json::json!({
            "data": {
                "denylist": self.denylist,
                "allowlist": self.allowlist,
                "categories": self.categories,
                "services": self.services,
            },
            "summary": { "added": total_added, "removed": total_removed }
        })
    }
}

/// Execute a full sync between local DB and NextDNS API.
pub fn execute_sync(
    db: &Database,
    client: &NextDnsClient,
    evaluator: &ScheduleEvaluator,
    dry_run: bool,
) -> Result<SyncResult, AppError> {
    let local_blocked = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;
    let local_allowed = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;

    let remote_denylist = client.get_denylist()?;
    let remote_allowlist = client.get_allowlist()?;

    let remote_blocked_set: HashSet<String> = remote_denylist.iter().map(|e| e.id.clone()).collect();
    let remote_allowed_set: HashSet<String> = remote_allowlist.iter().map(|e| e.id.clone()).collect();

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

    let should_allow: HashSet<String> = local_allowed.iter().map(|d| d.domain.clone()).collect();

    let to_add_blocked: Vec<String> = should_block.difference(&remote_blocked_set).cloned().collect();
    let to_remove_blocked: Vec<String> = remote_blocked_set.difference(&should_block).cloned().collect();
    let to_add_allowed: Vec<String> = should_allow.difference(&remote_allowed_set).cloned().collect();
    let to_remove_allowed: Vec<String> = remote_allowed_set.difference(&should_allow).cloned().collect();

    // === NextDNS categories and services ===
    let local_categories = db.with_conn(crate::db::nextdns::list_nextdns_categories)?;
    let local_services = db.with_conn(crate::db::nextdns::list_nextdns_services)?;

    let remote_categories = client.get_parental_categories()?;
    let remote_services = client.get_parental_services()?;

    let local_cat_set: HashSet<String> = local_categories.iter().map(|c| c.id.clone()).collect();
    let remote_cat_set: HashSet<String> = remote_categories.iter().filter(|c| c.active).map(|c| c.id.clone()).collect();
    let local_svc_set: HashSet<String> = local_services.iter().map(|s| s.id.clone()).collect();
    let remote_svc_set: HashSet<String> = remote_services.iter().filter(|s| s.active).map(|s| s.id.clone()).collect();

    let to_add_cats: Vec<String> = local_cat_set.difference(&remote_cat_set).cloned().collect();
    let to_remove_cats: Vec<String> = remote_cat_set.difference(&local_cat_set).cloned().collect();
    let to_add_svcs: Vec<String> = local_svc_set.difference(&remote_svc_set).cloned().collect();
    let to_remove_svcs: Vec<String> = remote_svc_set.difference(&local_svc_set).cloned().collect();

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
            services: SyncListResult {
                added: to_add_svcs, removed: to_remove_svcs,
                unchanged: local_svc_set.intersection(&remote_svc_set).count(), errors: vec![],
            },
        });
    }

    // === Execute denylist sync ===
    let mut denylist_errors = Vec::new();
    let mut denylist_added = Vec::new();
    for domain in &to_add_blocked {
        match client.add_to_denylist(domain) {
            Ok(()) => denylist_added.push(domain.clone()),
            Err(e) => denylist_errors.push(SyncError { domain: domain.clone(), error: e.to_string() }),
        }
    }
    let mut denylist_removed = Vec::new();
    for domain in &to_remove_blocked {
        match client.remove_from_denylist(domain) {
            Ok(()) => denylist_removed.push(domain.clone()),
            Err(e) => denylist_errors.push(SyncError { domain: domain.clone(), error: e.to_string() }),
        }
    }

    // === Execute allowlist sync ===
    let mut allowlist_errors = Vec::new();
    let mut allowlist_added = Vec::new();
    for domain in &to_add_allowed {
        match client.add_to_allowlist(domain) {
            Ok(()) => allowlist_added.push(domain.clone()),
            Err(e) => allowlist_errors.push(SyncError { domain: domain.clone(), error: e.to_string() }),
        }
    }
    let mut allowlist_removed = Vec::new();
    for domain in &to_remove_allowed {
        match client.remove_from_allowlist(domain) {
            Ok(()) => allowlist_removed.push(domain.clone()),
            Err(e) => allowlist_errors.push(SyncError { domain: domain.clone(), error: e.to_string() }),
        }
    }

    // === Execute categories sync ===
    let mut cat_errors = Vec::new();
    let mut cat_added = Vec::new();
    for id in &to_add_cats {
        match client.set_parental_category(id, true) {
            Ok(()) => cat_added.push(id.clone()),
            Err(e) => cat_errors.push(SyncError { domain: id.clone(), error: e.to_string() }),
        }
    }
    let mut cat_removed = Vec::new();
    for id in &to_remove_cats {
        match client.set_parental_category(id, false) {
            Ok(()) => cat_removed.push(id.clone()),
            Err(e) => cat_errors.push(SyncError { domain: id.clone(), error: e.to_string() }),
        }
    }

    // === Execute services sync ===
    let mut svc_errors = Vec::new();
    let mut svc_added = Vec::new();
    for id in &to_add_svcs {
        match client.set_parental_service(id, true) {
            Ok(()) => svc_added.push(id.clone()),
            Err(e) => svc_errors.push(SyncError { domain: id.clone(), error: e.to_string() }),
        }
    }
    let mut svc_removed = Vec::new();
    for id in &to_remove_svcs {
        match client.set_parental_service(id, false) {
            Ok(()) => svc_removed.push(id.clone()),
            Err(e) => svc_errors.push(SyncError { domain: id.clone(), error: e.to_string() }),
        }
    }

    // Enqueue retries for all failed operations
    let all_errors: Vec<(&str, &str, &SyncError)> = denylist_errors.iter().map(|e| ("add", "denylist", e))
        .chain(allowlist_errors.iter().map(|e| ("add", "allowlist", e)))
        .chain(cat_errors.iter().map(|e| ("add", "category", e)))
        .chain(svc_errors.iter().map(|e| ("add", "service", e)))
        .collect();

    if !all_errors.is_empty() {
        let retry_at = crate::common::time::now_unix() + 60;
        for (action, list_type, err) in &all_errors {
            let id = uuid::Uuid::new_v4().to_string();
            let _ = db.with_conn(|conn| {
                crate::db::retry::enqueue_retry(
                    conn, &id, action, Some(&err.domain), list_type,
                    None, RETRY_MAX_ATTEMPTS, retry_at,
                )
            });
        }
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
        services: SyncListResult {
            added: svc_added, removed: svc_removed,
            unchanged: local_svc_set.intersection(&remote_svc_set).count(), errors: svc_errors,
        },
    })
}
