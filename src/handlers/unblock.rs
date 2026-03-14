use crate::cli::unblock::UnblockArgs;
use crate::config::constants::{NEXTDNS_CATEGORIES, NEXTDNS_SERVICES};
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

/// What kind of target the user wants to unblock.
enum UnblockTarget {
    Domain,
    LocalCategory,
    NextdnsCategory,
    NextdnsService,
}

pub fn handle(args: UnblockArgs) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    // Resolve what kind of target this is (order: domain > local category > nextdns category > nextdns service)
    let target_kind = if db.with_conn(|conn| crate::db::domains::is_blocked(conn, &args.target))? {
        UnblockTarget::Domain
    } else if db.with_conn(|conn| crate::db::categories::get_category(conn, &args.target))?.is_some() {
        UnblockTarget::LocalCategory
    } else if db.with_conn(|conn| crate::db::nextdns::is_active_nextdns_category(conn, &args.target))? {
        UnblockTarget::NextdnsCategory
    } else if db.with_conn(|conn| crate::db::nextdns::is_active_nextdns_service(conn, &args.target))? {
        UnblockTarget::NextdnsService
    } else {
        // Also check if it's a valid NextDNS ID that's not currently active
        let is_valid_cat = NEXTDNS_CATEGORIES.iter().any(|(id, _)| *id == args.target);
        let is_valid_svc = NEXTDNS_SERVICES.iter().any(|(id, _)| *id == args.target);
        let hint = if is_valid_cat || is_valid_svc {
            format!("'{}' is a valid NextDNS ID but is not currently active", args.target)
        } else {
            "Use 'ndb denylist list', 'ndb category list', or 'ndb nextdns list' to check".to_string()
        };
        return Err(AppError::NotFound {
            message: format!("'{}' not found in denylist, categories, or active NextDNS filters", args.target),
            hint: Some(hint),
        });
    };

    // Build structured details
    let detail_str = args.duration.as_ref().map(|d| {
        serde_json::json!({"duration": d, "temporary": true}).to_string()
    });

    // Unblock mapped apps (only for domains)
    let apps_unblocked = if matches!(target_kind, UnblockTarget::Domain) {
        crate::app_blocker::unblock_apps_for_domain(&db, &args.target)
            .unwrap_or_else(|e| {
                let _ = db.with_conn(|conn| {
                    crate::db::audit::log_action(conn, "unblock_app_failed", "app", &e.to_string(), None, "cli")
                });
                Vec::new()
            })
    } else {
        Vec::new()
    };
    for app in &apps_unblocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "unblock_app", "app", &app.bundle_id, Some(&app.app_name), "cli")
        });
    }

    // Unblock from /etc/hosts only if domain is currently in hosts
    // (hosts are only added via explicit --hosts flag, so only remove if present)
    let hosts_unblocked = if matches!(target_kind, UnblockTarget::Domain) {
        let in_hosts = db.with_conn(|conn| {
            let entries = crate::db::hosts::list_host_entries(conn)?;
            Ok::<bool, rusqlite::Error>(entries.iter().any(|e| e.domain == args.target || e.source_domain.as_deref() == Some(&args.target)))
        }).unwrap_or(false);
        if in_hosts {
            crate::hosts_blocker::unblock_hosts_for_domain(&db, &args.target)
                .unwrap_or_else(|e| {
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(conn, "unblock_hosts_failed", "hosts", &e.to_string(), None, "cli")
                    });
                    Vec::new()
                })
        } else {
            Vec::new()
        }
    } else {
        Vec::new()
    };
    for domain in &hosts_unblocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "unblock_hosts", "hosts", domain, None, "cli")
        });
    }

    // Unblock Android apps via Firebase RTDB + FCM push
    let android_unblocked = if matches!(target_kind, UnblockTarget::Domain) {
        crate::android_blocker::unblock_android_for_domain(&db, &args.target)
            .unwrap_or_else(|e| {
                let _ = db.with_conn(|conn| {
                    crate::db::audit::log_action(conn, "unblock_android_failed", "android", &e.to_string(), None, "cli")
                });
                Vec::new()
            })
    } else {
        Vec::new()
    };
    for ab in &android_unblocked {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "unblock_android", "android", &ab.package_name, Some(&ab.domain), "cli")
        });
    }

    // Build API client for eager push
    let api_client: Option<(crate::config::types::EnvConfig, crate::api::NextDnsClient)> =
        crate::config::types::EnvConfig::from_env().ok().and_then(|env| {
            crate::api::NextDnsClient::new(&env.api_key, env.profile_id.clone())
                .ok()
                .map(|c| (env, c))
        });

    let mut eager_push_failed = false;

    if let Some(ref dur_str) = args.duration {
        let duration = crate::common::time::parse_duration(dur_str)?;
        let execute_at = crate::common::time::now_unix() + duration.as_secs() as i64;
        let id = uuid::Uuid::new_v4().to_string();

        match target_kind {
            UnblockTarget::Domain => {
                db.with_transaction(|conn| {
                    crate::db::domains::deactivate_blocked(conn, &args.target)
                        .map_err(crate::error::AppError::from)?;
                    crate::db::pending::create_pending(
                        conn, &id, "add", Some(&args.target), "denylist", execute_at,
                        Some(&format!("Auto re-block after {dur_str}")),
                    ).map_err(crate::error::AppError::from)?;
                    crate::db::audit::log_action(conn, "unblock", "domain", &args.target, detail_str.as_deref(), "cli")
                        .map_err(crate::error::AppError::from)?;
                    Ok(())
                })?;
                if let Some((_, ref client)) = api_client {
                    let r = crate::sync::eager_push_denylist(&db, client, &[args.target.clone()], false);
                    if r.pushed == 0 { eager_push_failed = true; }
                }
            }
            UnblockTarget::LocalCategory => {
                db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", "category", &args.target, detail_str.as_deref(), "cli"))?;
            }
            UnblockTarget::NextdnsCategory => {
                db.with_transaction(|conn| {
                    crate::db::nextdns::deactivate_nextdns_category(conn, &args.target)
                        .map_err(crate::error::AppError::from)?;
                    crate::db::pending::create_pending(
                        conn, &id, "add", Some(&args.target), "category", execute_at,
                        Some(&format!("Auto re-enable category after {dur_str}")),
                    ).map_err(crate::error::AppError::from)?;
                    crate::db::audit::log_action(conn, "unblock", "nextdns_category", &args.target, detail_str.as_deref(), "cli")
                        .map_err(crate::error::AppError::from)?;
                    Ok(())
                })?;
                if let Some((_, ref client)) = api_client {
                    let r = crate::sync::eager_push_category(&db, client, &args.target, false);
                    if r.pushed == 0 { eager_push_failed = true; }
                }
            }
            UnblockTarget::NextdnsService => {
                db.with_transaction(|conn| {
                    crate::db::nextdns::deactivate_nextdns_service(conn, &args.target)
                        .map_err(crate::error::AppError::from)?;
                    crate::db::pending::create_pending(
                        conn, &id, "add", Some(&args.target), "service", execute_at,
                        Some(&format!("Auto re-enable service after {dur_str}")),
                    ).map_err(crate::error::AppError::from)?;
                    crate::db::audit::log_action(conn, "unblock", "nextdns_service", &args.target, detail_str.as_deref(), "cli")
                        .map_err(crate::error::AppError::from)?;
                    Ok(())
                })?;
                if let Some((_, ref client)) = api_client {
                    let r = crate::sync::eager_push_service(&db, client, &args.target, false);
                    if r.pushed == 0 { eager_push_failed = true; }
                }
            }
        }

        let mut watchdog_warning = None;
        if let Ok(status) = crate::watchdog::status() {
            if !status.healthy {
                watchdog_warning = Some("Watchdog unhealthy — pending action may not execute automatically. Run 'ndb fix' or 'ndb watchdog install --interval 5m'".to_string());
            }
        }

        let result = UnblockResult { target: args.target, duration: Some(dur_str.clone()), pending_id: Some(id), watchdog_warning, eager_push_failed, apps_unblocked, hosts_unblocked, android_unblocked };
        output::render(&result);
    } else {
        match target_kind {
            UnblockTarget::Domain => {
                db.with_transaction(|conn| {
                    crate::db::domains::remove_blocked(conn, &args.target)
                        .map_err(crate::error::AppError::from)?;
                    crate::db::audit::log_action(conn, "unblock", "domain", &args.target, None, "cli")
                        .map_err(crate::error::AppError::from)?;
                    Ok(())
                })?;
                if let Some((_, ref client)) = api_client {
                    let r = crate::sync::eager_push_denylist(&db, client, &[args.target.clone()], false);
                    if r.pushed == 0 { eager_push_failed = true; }
                }
            }
            UnblockTarget::LocalCategory => {
                db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", "category", &args.target, None, "cli"))?;
            }
            UnblockTarget::NextdnsCategory => {
                db.with_conn(|conn| crate::db::nextdns::remove_nextdns_category(conn, &args.target))?;
                db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", "nextdns_category", &args.target, None, "cli"))?;
                if let Some((_, ref client)) = api_client {
                    let r = crate::sync::eager_push_category(&db, client, &args.target, false);
                    if r.pushed == 0 { eager_push_failed = true; }
                }
            }
            UnblockTarget::NextdnsService => {
                db.with_conn(|conn| crate::db::nextdns::remove_nextdns_service(conn, &args.target))?;
                db.with_conn(|conn| crate::db::audit::log_action(conn, "unblock", "nextdns_service", &args.target, None, "cli"))?;
                if let Some((_, ref client)) = api_client {
                    let r = crate::sync::eager_push_service(&db, client, &args.target, false);
                    if r.pushed == 0 { eager_push_failed = true; }
                }
            }
        }

        let result = UnblockResult { target: args.target, duration: None, pending_id: None, watchdog_warning: None, eager_push_failed, apps_unblocked, hosts_unblocked, android_unblocked };
        output::render(&result);
    }

    Ok(ExitCode::Success)
}

struct UnblockResult {
    target: String,
    duration: Option<String>,
    pending_id: Option<String>,
    watchdog_warning: Option<String>,
    eager_push_failed: bool,
    apps_unblocked: Vec<crate::app_blocker::AppUnblockResult>,
    hosts_unblocked: Vec<String>,
    android_unblocked: Vec<crate::android_blocker::AndroidUnblockResult>,
}
impl Renderable for UnblockResult {
    fn command_name(&self) -> &str { "unblock" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": {
                "target": self.target, "duration": self.duration,
                "pending_id": self.pending_id, "watchdog_warning": self.watchdog_warning,
                "eager_push_failed": self.eager_push_failed,
                "apps_unblocked": self.apps_unblocked,
                "hosts_unblocked": self.hosts_unblocked,
                "android_unblocked": self.android_unblocked,
            },
            "summary": { "unblocked": 1, "apps_unblocked": self.apps_unblocked.len(), "hosts_unblocked": self.hosts_unblocked.len(), "android_unblocked": self.android_unblocked.len() }
        })
    }
}
