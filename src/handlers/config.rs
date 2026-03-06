use crate::cli::config::*;
use crate::config::validation::validate_config;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: ConfigCommands, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    match cmd {
        ConfigCommands::Show(args) => handle_show(args, format),
        ConfigCommands::Set(args) => handle_set(args, format),
        ConfigCommands::Edit(_) => handle_edit(format),
        ConfigCommands::Validate(_) => handle_validate(format),
        ConfigCommands::Push(args) => handle_push(args, format),
        ConfigCommands::Diff(_) => handle_diff(format),
    }
}

fn handle_show(args: ConfigShowArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let config = crate::config::load_config()?;
    let json = serde_json::to_value(&config)?;

    if let Some(key) = args.key {
        let value = json.pointer(&format!("/{}", key.replace('.', "/")))
            .cloned()
            .ok_or_else(|| AppError::NotFound {
                message: format!("Config key '{key}' not found"),
                hint: Some("Use 'ndb config show' to see all config keys".to_string()),
            })?;
        let result = ConfigShowResult { command: "config show", data: serde_json::json!({ "key": key, "value": value }) };
        output::render(&result, format);
    } else {
        let result = ConfigShowResult { command: "config show", data: serde_json::json!({ "config": json }) };
        output::render(&result, format);
    }
    Ok(ExitCode::Success)
}

fn handle_set(args: ConfigSetArgs, format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let config_path = crate::common::platform::config_path();
    let content = std::fs::read_to_string(&config_path).map_err(|e| AppError::Config {
        message: format!("Failed to read config: {e}"),
        hint: Some("Run 'ndb init' first".to_string()),
    })?;

    let mut json: serde_json::Value = serde_json::from_str(&content)?;

    // Navigate to the key and set value
    let parts: Vec<&str> = args.key.split('.').collect();
    let mut current = &mut json;
    for (i, part) in parts.iter().enumerate() {
        if i == parts.len() - 1 {
            // Try to parse as JSON value, fallback to string
            let value = serde_json::from_str(&args.value)
                .unwrap_or_else(|_| serde_json::Value::String(args.value.clone()));
            current[part] = value;
        } else {
            if !current[part].is_object() {
                current[part] = serde_json::json!({});
            }
            current = &mut current[part];
        }
    }

    let output_str = serde_json::to_string_pretty(&json)?;
    std::fs::write(&config_path, output_str)?;

    let result = ConfigShowResult {
        command: "config set",
        data: serde_json::json!({ "key": args.key, "value": args.value }),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_edit(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let config_path = crate::common::platform::config_path();
    let editor = std::env::var("EDITOR").unwrap_or_else(|_| {
        if cfg!(target_os = "macos") { "open -t".to_string() }
        else { "vi".to_string() }
    });

    let parts: Vec<&str> = editor.split_whitespace().collect();
    let status = std::process::Command::new(parts[0])
        .args(&parts[1..])
        .arg(&config_path)
        .status()
        .map_err(|e| AppError::General {
            message: format!("Failed to open editor: {e}"),
            hint: Some(format!("Set EDITOR env var. Tried: {editor}")),
        })?;

    if !status.success() {
        return Err(AppError::General {
            message: "Editor exited with error".to_string(),
            hint: None,
        });
    }

    let result = ConfigShowResult {
        command: "config edit",
        data: serde_json::json!({ "path": config_path.to_string_lossy() }),
    };
    output::render(&result, format);
    Ok(ExitCode::Success)
}

fn handle_validate(format: ResolvedFormat) -> Result<ExitCode, AppError> {
    let config = crate::config::load_config()?;
    match validate_config(&config) {
        Ok(()) => {
            let result = ConfigShowResult {
                command: "config validate",
                data: serde_json::json!({ "valid": true, "errors": [] }),
            };
            output::render(&result, format);
            Ok(ExitCode::Success)
        }
        Err(AppError::Validation { details, .. }) => {
            let result = ConfigShowResult {
                command: "config validate",
                data: serde_json::json!({ "valid": false, "errors": details }),
            };
            output::render(&result, format);
            Ok(ExitCode::ValidationError)
        }
        Err(e) => Err(e),
    }
}

fn handle_push(_args: ConfigPushArgs, _format: ResolvedFormat) -> Result<ExitCode, AppError> {
    // This requires API access - delegates to sync
    Err(AppError::General {
        message: "Use 'ndb sync' to push configuration to NextDNS API".to_string(),
        hint: Some("ndb sync --dry-run to preview changes".to_string()),
    })
}

fn handle_diff(_format: ResolvedFormat) -> Result<ExitCode, AppError> {
    Err(AppError::General {
        message: "Config diff requires API access. Use 'ndb sync --dry-run' to see differences.".to_string(),
        hint: Some("ndb sync --dry-run".to_string()),
    })
}

struct ConfigShowResult {
    command: &'static str,
    data: serde_json::Value,
}

impl Renderable for ConfigShowResult {
    fn command_name(&self) -> &str { self.command }
    fn to_json(&self) -> serde_json::Value { serde_json::json!({ "data": self.data }) }
    fn to_human(&self) -> String {
        serde_json::to_string_pretty(&self.data).unwrap_or_else(|_| format!("{:?}", self.data)) + "\n"
    }
}
