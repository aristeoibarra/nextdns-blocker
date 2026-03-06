pub mod constants;
pub mod types;
pub mod validation;

use std::path::Path;

use crate::common::platform;
use crate::error::AppError;

pub use types::AppConfig;

/// Load configuration from the default config file path.
pub fn load_config() -> Result<AppConfig, AppError> {
    let path = platform::config_path();
    load_config_from(&path)
}

/// Load configuration from a specific path.
pub fn load_config_from(path: &Path) -> Result<AppConfig, AppError> {
    if !path.exists() {
        return Err(AppError::Config {
            message: format!("Config file not found: {}", path.display()),
            hint: Some("Run 'ndb init' to create initial configuration".to_string()),
        });
    }

    let content = std::fs::read_to_string(path).map_err(|e| AppError::Config {
        message: format!("Failed to read config: {e}"),
        hint: None,
    })?;

    let config: AppConfig = serde_json::from_str(&content).map_err(|e| AppError::Config {
        message: format!("Invalid config JSON: {e}"),
        hint: Some("Run 'ndb config validate' to check configuration".to_string()),
    })?;

    Ok(config)
}
