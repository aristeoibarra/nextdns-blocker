use std::collections::HashSet;

use crate::api::NextDnsClient;
use crate::db::Database;
use crate::error::AppError;
use crate::output::Renderable;
use crate::scheduler::ScheduleEvaluator;

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
    fn command_name(&self) -> &str {
        "sync"
    }

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
            "summary": {
                "added": total_added,
                "removed": total_removed,
            }
        })
    }

    fn to_human(&self) -> String {
        let mut out = String::new();
        out.push_str(&format_list_result("Denylist", &self.denylist));
        out.push_str(&format_list_result("Allowlist", &self.allowlist));
        out.push_str(&format_list_result("Categories", &self.categories));
        out.push_str(&format_list_result("Services", &self.services));
        out
    }
}

fn format_list_result(name: &str, result: &SyncListResult) -> String {
    let mut out = format!("{name}: ");
    if result.added.is_empty() && result.removed.is_empty() {
        out.push_str("no changes\n");
    } else {
        if !result.added.is_empty() {
            out.push_str(&format!("+{} ", result.added.len()));
        }
        if !result.removed.is_empty() {
            out.push_str(&format!("-{} ", result.removed.len()));
        }
        out.push('\n');
    }
    out
}

/// Execute a full sync between local DB and NextDNS API.
pub async fn execute_sync(
    db: &Database,
    client: &NextDnsClient,
    evaluator: &ScheduleEvaluator,
    dry_run: bool,
) -> Result<SyncResult, AppError> {
    // Get local state
    let local_blocked = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;
    let local_allowed = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;

    // Get remote state
    let remote_denylist = client.get_denylist().await?;
    let remote_allowlist = client.get_allowlist().await?;

    let remote_blocked_set: HashSet<String> =
        remote_denylist.iter().map(|e| e.id.clone()).collect();
    let remote_allowed_set: HashSet<String> =
        remote_allowlist.iter().map(|e| e.id.clone()).collect();

    // Determine what should be blocked based on schedule
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

    // Calculate diffs
    let to_add_blocked: Vec<String> = should_block.difference(&remote_blocked_set).cloned().collect();
    let to_remove_blocked: Vec<String> = remote_blocked_set.difference(&should_block).cloned().collect();
    let to_add_allowed: Vec<String> = should_allow.difference(&remote_allowed_set).cloned().collect();
    let to_remove_allowed: Vec<String> = remote_allowed_set.difference(&should_allow).cloned().collect();

    if dry_run {
        return Ok(SyncResult {
            denylist: SyncListResult {
                added: to_add_blocked,
                removed: to_remove_blocked,
                unchanged: should_block.intersection(&remote_blocked_set).count(),
                errors: vec![],
            },
            allowlist: SyncListResult {
                added: to_add_allowed,
                removed: to_remove_allowed,
                unchanged: should_allow.intersection(&remote_allowed_set).count(),
                errors: vec![],
            },
            categories: SyncListResult {
                added: vec![],
                removed: vec![],
                unchanged: 0,
                errors: vec![],
            },
            services: SyncListResult {
                added: vec![],
                removed: vec![],
                unchanged: 0,
                errors: vec![],
            },
        });
    }

    // Execute denylist changes
    let mut denylist_errors = Vec::new();
    let mut denylist_added = Vec::new();
    for domain in &to_add_blocked {
        match client.add_to_denylist(domain).await {
            Ok(()) => denylist_added.push(domain.clone()),
            Err(e) => denylist_errors.push(SyncError {
                domain: domain.clone(),
                error: e.to_string(),
            }),
        }
    }
    let mut denylist_removed = Vec::new();
    for domain in &to_remove_blocked {
        match client.remove_from_denylist(domain).await {
            Ok(()) => denylist_removed.push(domain.clone()),
            Err(e) => denylist_errors.push(SyncError {
                domain: domain.clone(),
                error: e.to_string(),
            }),
        }
    }

    // Execute allowlist changes
    let mut allowlist_errors = Vec::new();
    let mut allowlist_added = Vec::new();
    for domain in &to_add_allowed {
        match client.add_to_allowlist(domain).await {
            Ok(()) => allowlist_added.push(domain.clone()),
            Err(e) => allowlist_errors.push(SyncError {
                domain: domain.clone(),
                error: e.to_string(),
            }),
        }
    }
    let mut allowlist_removed = Vec::new();
    for domain in &to_remove_allowed {
        match client.remove_from_allowlist(domain).await {
            Ok(()) => allowlist_removed.push(domain.clone()),
            Err(e) => allowlist_errors.push(SyncError {
                domain: domain.clone(),
                error: e.to_string(),
            }),
        }
    }

    Ok(SyncResult {
        denylist: SyncListResult {
            added: denylist_added,
            removed: denylist_removed,
            unchanged: should_block.intersection(&remote_blocked_set).count(),
            errors: denylist_errors,
        },
        allowlist: SyncListResult {
            added: allowlist_added,
            removed: allowlist_removed,
            unchanged: should_allow.intersection(&remote_allowed_set).count(),
            errors: allowlist_errors,
        },
        categories: SyncListResult {
            added: vec![],
            removed: vec![],
            unchanged: 0,
            errors: vec![],
        },
        services: SyncListResult {
            added: vec![],
            removed: vec![],
            unchanged: 0,
            errors: vec![],
        },
    })
}
