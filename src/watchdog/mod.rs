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

#[derive(Debug, Clone, serde::Serialize)]
pub struct WatchdogStatus {
    pub scheduler: String,
    pub installed: bool,
    pub running: bool,
    pub interval_secs: Option<u64>,
}
