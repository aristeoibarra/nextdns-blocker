use crate::cli::config::*;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: ConfigCommands) -> Result<ExitCode, AppError> {
    match cmd {
        ConfigCommands::Show(args) => handle_show(args),
        ConfigCommands::Set(args) => handle_set(args),
        ConfigCommands::Validate(_) => handle_validate(),
        ConfigCommands::Push(_args) => handle_push(),
        ConfigCommands::Diff(_) => handle_diff(),
    }
}

fn handle_show(args: ConfigShowArgs) -> Result<ExitCode, AppError> {
    let db = crate::db::Database::open(&crate::common::platform::db_path())?;

    if let Some(key) = args.key {
        let value = db.with_conn(|conn| crate::db::config::get_value(conn, &key))?;
        match value {
            Some(v) => {
                let result = ConfigResult {
                    command: "config show",
                    data: serde_json::json!({ "key": key, "value": v }),
                };
                output::render(&result);
            }
            None => {
                return Err(AppError::NotFound {
                    message: format!("Config key '{key}' not found"),
                    hint: Some("Use 'ndb config show' to see all keys".to_string()),
                });
            }
        }
    } else {
        let entries = db.with_conn(crate::db::config::list_all)?;
        let map: serde_json::Map<String, serde_json::Value> = entries
            .into_iter()
            .map(|(k, v)| (k, serde_json::Value::String(v)))
            .collect();
        let result = ConfigResult {
            command: "config show",
            data: serde_json::json!({ "settings": map, "db_path": crate::common::platform::db_path().to_string_lossy() }),
        };
        output::render(&result);
    }
    Ok(ExitCode::Success)
}

fn handle_set(args: ConfigSetArgs) -> Result<ExitCode, AppError> {
    if !crate::db::config::is_known_key(&args.key) {
        let known: Vec<&str> = crate::db::config::KNOWN_KEYS.iter().map(|(k, _)| *k).collect();
        return Err(AppError::Validation {
            message: format!("Unknown config key: '{}'", args.key),
            details: vec![],
            hint: Some(format!("Known keys: {}", known.join(", "))),
        });
    }

    match args.key.as_str() {
        "timezone" => {
            args.value.parse::<chrono_tz::Tz>().map_err(|_| AppError::Validation {
                message: format!("Invalid timezone: '{}'", args.value),
                details: vec![],
                hint: Some("Use IANA timezone names like 'America/Mexico_City' or 'UTC'".to_string()),
            })?;
        }
        "safe_search" | "youtube_restricted_mode" | "block_bypass" => {
            if args.value != "true" && args.value != "false" {
                return Err(AppError::Validation {
                    message: format!("'{}' must be 'true' or 'false'", args.key),
                    details: vec![],
                    hint: None,
                });
            }
        }
        _ => {}
    }

    let db = crate::db::Database::open(&crate::common::platform::db_path())?;
    let previous = db.with_conn(|conn| crate::db::config::get_value(conn, &args.key))?;
    db.with_conn(|conn| crate::db::config::set_value(conn, &args.key, &args.value))?;

    let result = ConfigResult {
        command: "config set",
        data: serde_json::json!({ "key": args.key, "value": args.value, "previous": previous }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_validate() -> Result<ExitCode, AppError> {
    let db = crate::db::Database::open(&crate::common::platform::db_path())?;
    let mut errors: Vec<serde_json::Value> = Vec::new();

    let tz = db.with_conn(crate::db::config::get_timezone)?;
    if tz.parse::<chrono_tz::Tz>().is_err() {
        errors.push(serde_json::json!({ "key": "timezone", "reason": format!("Invalid timezone: {tz}") }));
    }

    if std::env::var("NEXTDNS_API_KEY").is_err() {
        errors.push(serde_json::json!({ "key": "NEXTDNS_API_KEY", "reason": "Environment variable not set" }));
    }
    if std::env::var("NEXTDNS_PROFILE_ID").is_err() {
        errors.push(serde_json::json!({ "key": "NEXTDNS_PROFILE_ID", "reason": "Environment variable not set" }));
    }

    let valid = errors.is_empty();
    let result = ConfigResult {
        command: "config validate",
        data: serde_json::json!({ "valid": valid, "errors": errors }),
    };
    output::render(&result);

    if valid { Ok(ExitCode::Success) } else { Ok(ExitCode::ValidationError) }
}

fn handle_push() -> Result<ExitCode, AppError> {
    Err(AppError::General {
        message: "Use 'ndb sync' to push configuration to NextDNS API".to_string(),
        hint: Some("ndb sync --dry-run to preview changes".to_string()),
    })
}

fn handle_diff() -> Result<ExitCode, AppError> {
    Err(AppError::General {
        message: "Config diff requires API access. Use 'ndb sync --dry-run' to see differences.".to_string(),
        hint: Some("ndb sync --dry-run".to_string()),
    })
}

struct ConfigResult { command: &'static str, data: serde_json::Value }
impl Renderable for ConfigResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
}
