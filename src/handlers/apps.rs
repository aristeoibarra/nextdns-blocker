use crate::app_blocker;
use crate::cli::apps::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: AppsCommands) -> Result<ExitCode, AppError> {
    match cmd {
        AppsCommands::List(_) => handle_list(),
        AppsCommands::Scan(_) => handle_scan(),
        AppsCommands::Map(args) => handle_map(args),
        AppsCommands::Unmap(args) => handle_unmap(args),
        AppsCommands::Restore(_) => handle_restore(),
    }
}

fn handle_list() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    let mappings = db.with_conn(crate::db::apps::list_mappings)?;
    let blocked = db.with_conn(crate::db::apps::list_blocked_apps)?;

    let entries: Vec<serde_json::Value> = mappings
        .iter()
        .map(|m| {
            let is_blocked = blocked.iter().any(|b| b.bundle_id == m.bundle_id);
            let installed = app_blocker::find_app_path(&m.bundle_id).is_some() || is_blocked;
            serde_json::json!({
                "domain": m.domain,
                "bundle_id": m.bundle_id,
                "app_name": m.app_name,
                "auto": m.auto,
                "installed": installed,
                "blocked": is_blocked,
            })
        })
        .collect();

    let result = AppsResult {
        command: "apps list",
        data: serde_json::json!({ "mappings": entries }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_scan() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    let installed = app_blocker::scan_installed_apps()?;
    let existing_mappings = db.with_conn(crate::db::apps::list_mappings)?;

    let mut matches = Vec::new();
    let mut auto_added = 0usize;

    for (bundle_id, name, path) in &installed {
        let known = app_blocker::mappings::lookup_bundle(bundle_id);
        if known.is_empty() {
            continue;
        }

        for (domain, _) in &known {
            let already = existing_mappings
                .iter()
                .any(|m| m.domain == *domain && m.bundle_id == *bundle_id);

            if !already {
                db.with_conn(|conn| {
                    crate::db::apps::add_mapping(conn, domain, bundle_id, name, true)
                })?;
                auto_added += 1;
            }

            matches.push(serde_json::json!({
                "domain": domain,
                "bundle_id": bundle_id,
                "app_name": name,
                "path": path,
                "already_mapped": already,
            }));
        }
    }

    let result = AppsResult {
        command: "apps scan",
        data: serde_json::json!({
            "installed_apps": installed.len(),
            "known_matches": matches,
            "auto_added": auto_added,
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_map(args: AppsMapArgs) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    let app_name = args.name.unwrap_or_else(|| {
        app_blocker::find_app_path(&args.bundle_id)
            .and_then(|p| {
                std::path::Path::new(&p)
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .map(|s| s.to_string())
            })
            .unwrap_or_else(|| args.bundle_id.clone())
    });

    db.with_conn(|conn| {
        crate::db::apps::add_mapping(conn, &args.domain, &args.bundle_id, &app_name, false)
    })?;
    db.with_conn(|conn| {
        crate::db::audit::log_action(conn, "map_app", "app", &args.bundle_id, Some(&args.domain))
    })?;

    let result = AppsResult {
        command: "apps map",
        data: serde_json::json!({
            "domain": args.domain,
            "bundle_id": args.bundle_id,
            "app_name": app_name,
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_unmap(args: AppsUnmapArgs) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;

    let removed =
        db.with_conn(|conn| crate::db::apps::remove_mapping(conn, &args.domain, &args.bundle_id))?;

    if !removed {
        return Err(AppError::NotFound {
            message: format!(
                "No mapping found for {} -> {}",
                args.domain, args.bundle_id
            ),
            hint: Some("Use 'ndb apps list' to see current mappings".to_string()),
        });
    }

    db.with_conn(|conn| {
        crate::db::audit::log_action(
            conn,
            "unmap_app",
            "app",
            &args.bundle_id,
            Some(&args.domain),
        )
    })?;

    let result = AppsResult {
        command: "apps unmap",
        data: serde_json::json!({
            "domain": args.domain,
            "bundle_id": args.bundle_id,
            "removed": true,
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_restore() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    let restored = app_blocker::restore_all(&db)?;

    let entries: Vec<serde_json::Value> = restored
        .iter()
        .map(|r| {
            serde_json::json!({
                "bundle_id": r.bundle_id,
                "app_name": r.app_name,
            })
        })
        .collect();

    let result = AppsResult {
        command: "apps restore",
        data: serde_json::json!({ "restored": entries }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct AppsResult {
    command: &'static str,
    data: serde_json::Value,
}
impl Renderable for AppsResult {
    fn command_name(&self) -> &str {
        self.command
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": self.data })
    }
}
