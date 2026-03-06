use crate::cli::unblock::UnblockArgs;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(args: UnblockArgs) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    let is_domain = db.with_conn(|conn| crate::db::domains::is_blocked(conn, &args.target))?;
    let is_category = db.with_conn(|conn| crate::db::categories::get_category(conn, &args.target))?.is_some();

    if !is_domain && !is_category {
        return Err(AppError::NotFound {
            message: format!("'{}' not found in denylist or categories", args.target),
            hint: Some("Use 'ndb denylist list' or 'ndb category list' to check".to_string()),
        });
    }

    // Unblock mapped apps for this domain
    let apps_unblocked = if is_domain {
        crate::app_blocker::unblock_apps_for_domain(&db, &args.target).unwrap_or_default()
    } else {
        Vec::new()
    };
    for app in &apps_unblocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "unblock_app", "app", &app.bundle_id, Some(&app.app_name))
        });
    }

    // Unblock from /etc/hosts
    let hosts_unblocked = if is_domain {
        crate::hosts_blocker::unblock_hosts_for_domain(&db, &args.target).unwrap_or_default()
    } else {
        Vec::new()
    };
    for domain in &hosts_unblocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "unblock_hosts", "hosts", domain, None)
        });
    }

    // Eager push removal to NextDNS API immediately
    let api_client: Option<(crate::config::types::EnvConfig, crate::api::NextDnsClient)> =
        crate::config::types::EnvConfig::from_env().ok().and_then(|env| {
            crate::api::NextDnsClient::new(&env.api_key, env.profile_id.clone())
                .ok()
                .map(|c| (env, c))
        });

    if let Some(ref dur_str) = args.duration {
        let duration = crate::common::time::parse_duration(dur_str)?;
        let execute_at = crate::common::time::now_unix() + duration.as_secs() as i64;
        let id = uuid::Uuid::new_v4().to_string();

        if is_domain {
            db.with_conn(|conn| crate::db::domains::deactivate_blocked(conn, &args.target))?;
            db.with_conn(|conn| crate::db::pending::create_pending(
                conn, &id, "add", Some(&args.target), "denylist", execute_at,
                Some(&format!("Auto re-block after {dur_str}")),
            ))?;
            if let Some((_, ref client)) = api_client {
                crate::sync::eager_push_denylist(&db, client, &[args.target.clone()], false);
            }
        }

        db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", if is_domain { "domain" } else { "category" }, &args.target, Some(dur_str)))?;

        let mut watchdog_warning = None;
        if let Ok(status) = crate::watchdog::status() {
            if !status.installed {
                watchdog_warning = Some("Watchdog not installed — pending action will not execute automatically. Run 'ndb watchdog install --interval 5m'".to_string());
            }
        }

        let result = UnblockResult { target: args.target, duration: Some(dur_str.clone()), pending_id: Some(id), watchdog_warning, apps_unblocked, hosts_unblocked };
        output::render(&result);
    } else {
        if is_domain {
            db.with_conn(|conn| crate::db::domains::remove_blocked(conn, &args.target))?;
            if let Some((_, ref client)) = api_client {
                crate::sync::eager_push_denylist(&db, client, &[args.target.clone()], false);
            }
        }
        db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", if is_domain { "domain" } else { "category" }, &args.target, None))?;

        let result = UnblockResult { target: args.target, duration: None, pending_id: None, watchdog_warning: None, apps_unblocked, hosts_unblocked };
        output::render(&result);
    }

    Ok(ExitCode::Success)
}

struct UnblockResult {
    target: String,
    duration: Option<String>,
    pending_id: Option<String>,
    watchdog_warning: Option<String>,
    apps_unblocked: Vec<crate::app_blocker::AppUnblockResult>,
    hosts_unblocked: Vec<String>,
}
impl Renderable for UnblockResult {
    fn command_name(&self) -> &str { "unblock" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": {
                "target": self.target, "duration": self.duration,
                "pending_id": self.pending_id, "watchdog_warning": self.watchdog_warning,
                "apps_unblocked": self.apps_unblocked,
                "hosts_unblocked": self.hosts_unblocked,
            },
            "summary": { "unblocked": 1, "apps_unblocked": self.apps_unblocked.len(), "hosts_unblocked": self.hosts_unblocked.len() }
        })
    }
}
