pub mod launchd;

use crate::error::AppError;

/// Install the watchdog service via launchd.
pub fn install(interval_secs: u64) -> Result<String, AppError> {
    launchd::install(interval_secs)
}

/// Uninstall the watchdog service.
pub fn uninstall() -> Result<(), AppError> {
    launchd::uninstall()
}

/// Check if the watchdog service is installed and running.
pub fn status() -> Result<WatchdogStatus, AppError> {
    launchd::status()
}

/// Re-install watchdog if binary path is stale. Returns true if repaired.
pub fn ensure_healthy() -> Result<bool, AppError> {
    launchd::ensure_healthy()
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct WatchdogStatus {
    pub scheduler: String,
    pub installed: bool,
    pub running: bool,
    pub interval_secs: Option<u64>,
    pub binary_path: Option<String>,
    pub binary_valid: bool,
    pub healthy: bool,
}
