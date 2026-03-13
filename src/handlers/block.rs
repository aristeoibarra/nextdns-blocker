use crate::cli::block::BlockArgs;
use crate::common::domain::parse_domains;
use crate::db::Database;
use crate::error::{AppError, ExitCode, ValidationDetail};
use crate::output::{self, Renderable};

pub fn handle(args: BlockArgs) -> Result<ExitCode, AppError> {
    // Validate duration upfront before any DB writes
    let parsed_duration = if let Some(ref dur_str) = args.duration {
        Some(crate::common::time::parse_duration(dur_str)?)
    } else {
        None
    };

    let db = Database::open(&crate::common::platform::db_path())?;

    let (valid, errors) = parse_domains(&args.domains);

    if valid.is_empty() && !errors.is_empty() {
        return Err(AppError::Validation {
            message: "No valid domains provided".to_string(),
            details: errors
                .iter()
                .map(|(d, r)| ValidationDetail { field: d.clone(), reason: r.clone() })
                .collect(),
            hint: Some("Domains must be valid RFC 1123 hostnames (e.g., example.com)".to_string()),
        });
    }

    let mut added = Vec::new();
    let mut skipped = Vec::new();
    let mut pending_id = None;

    db.with_transaction(|conn| {
        for domain in &valid {
            let existed = crate::db::domains::is_blocked(conn, domain.as_str())?;
            crate::db::domains::add_blocked(
                conn, domain.as_str(), args.description.as_deref(),
                args.category.as_deref(), None,
            )?;
            if existed { skipped.push(domain.to_string()); }
            else { added.push(domain.to_string()); }
            crate::db::audit::log_action(conn, "block", "domain", domain.as_str(), None)?;
        }
        Ok(())
    })?;

    let mut watchdog_warning = None;
    if let Some(ref dur_str) = args.duration {
        let duration = parsed_duration.expect("validated above");
        let execute_at = crate::common::time::now_unix() + duration.as_secs() as i64;
        let id = uuid::Uuid::new_v4().to_string();

        db.with_transaction(|conn| {
            for domain in &added {
                crate::db::pending::create_pending(
                    conn, &id, "remove", Some(domain), "denylist", execute_at,
                    Some(&format!("Auto unblock after {dur_str}")),
                ).map_err(crate::error::AppError::from)?;
            }
            Ok(())
        })?;
        pending_id = Some(id);

        if let Ok(status) = crate::watchdog::status() {
            if !status.healthy {
                watchdog_warning = Some("Watchdog unhealthy — pending action may not execute automatically. Run 'ndb fix' or 'ndb watchdog install --interval 5m'".to_string());
            }
        }
    }

    // Eager push newly added domains to NextDNS API immediately
    let mut api_retrying = 0usize;
    if !added.is_empty() {
        if let Ok(env_config) = crate::config::types::EnvConfig::from_env() {
            if let Ok(client) = crate::api::NextDnsClient::new(&env_config.api_key, env_config.profile_id) {
                let push = crate::sync::eager_push_denylist(&db, &client, &added, true);
                api_retrying = push.retrying;
            }
        }
    }

    // Block mapped apps for newly added domains
    let apps_blocked = crate::app_blocker::block_apps_for_domains(&db, &added)
        .unwrap_or_else(|e| {
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(conn, "block_app_failed", "app", &e.to_string(), None)
            });
            Vec::new()
        });
    for app in &apps_blocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "block_app", "app", &app.bundle_id, Some(&app.app_name))
        });
    }

    // Block domains in /etc/hosts
    let hosts_blocked = crate::hosts_blocker::block_hosts_for_domains(&db, &added)
        .unwrap_or_else(|e| {
            let _ = db.with_conn(|conn| {
                crate::db::audit::log_action(conn, "block_hosts_failed", "hosts", &e.to_string(), None)
            });
            Vec::new()
        });
    for domain in &hosts_blocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "block_hosts", "hosts", domain, None)
        });
    }

    // Surface API retry warning so caller knows push is deferred
    if api_retrying > 0 && watchdog_warning.is_none() {
        watchdog_warning = Some(format!(
            "{api_retrying} domain(s) failed to push to NextDNS API — queued for automatic retry"
        ));
    }

    let result = BlockResult {
        added, skipped,
        errors: errors.iter().map(|(d, r)| format!("{d}: {r}")).collect(),
        duration: args.duration,
        pending_id, watchdog_warning,
        apps_blocked, hosts_blocked,
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct BlockResult {
    added: Vec<String>,
    skipped: Vec<String>,
    errors: Vec<String>,
    duration: Option<String>,
    pending_id: Option<String>,
    watchdog_warning: Option<String>,
    apps_blocked: Vec<crate::app_blocker::AppBlockResult>,
    hosts_blocked: Vec<String>,
}

impl Renderable for BlockResult {
    fn command_name(&self) -> &str { "block" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": {
                "added": self.added, "skipped": self.skipped, "errors": self.errors,
                "duration": self.duration, "pending_id": self.pending_id,
                "watchdog_warning": self.watchdog_warning,
                "apps_blocked": self.apps_blocked,
                "hosts_blocked": self.hosts_blocked,
            },
            "summary": {
                "added": self.added.len(), "skipped": self.skipped.len(),
                "errors": self.errors.len(), "apps_blocked": self.apps_blocked.len(),
                "hosts_blocked": self.hosts_blocked.len(),
            }
        })
    }
}
