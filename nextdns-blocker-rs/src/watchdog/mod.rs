pub mod cron;
pub mod launchd;
pub mod systemd;
pub mod windows;

use crate::common::platform;
use crate::error::AppError;

/// Detect the best scheduler for the current platform.
pub fn detect_scheduler() -> &'static str {
    if platform::is_macos() {
        "launchd"
    } else if platform::is_linux() && platform::has_systemd() {
        "systemd"
    } else if platform::is_linux() {
        "cron"
    } else if platform::is_windows() {
        "windows_task_scheduler"
    } else {
        "cron"
    }
}

/// Install the watchdog service for the current platform.
pub fn install(interval_secs: u64) -> Result<String, AppError> {
    let scheduler = detect_scheduler();
    match scheduler {
        "launchd" => launchd::install(interval_secs),
        "systemd" => systemd::install(interval_secs),
        "cron" => cron::install(interval_secs),
        "windows_task_scheduler" => windows::install(interval_secs),
        _ => Err(AppError::General {
            message: format!("Unsupported scheduler: {scheduler}"),
            hint: None,
        }),
    }
}

/// Uninstall the watchdog service for the current platform.
pub fn uninstall() -> Result<(), AppError> {
    let scheduler = detect_scheduler();
    match scheduler {
        "launchd" => launchd::uninstall(),
        "systemd" => systemd::uninstall(),
        "cron" => cron::uninstall(),
        "windows_task_scheduler" => windows::uninstall(),
        _ => Err(AppError::General {
            message: format!("Unsupported scheduler: {scheduler}"),
            hint: None,
        }),
    }
}

/// Check if the watchdog service is installed and running.
pub fn status() -> Result<WatchdogStatus, AppError> {
    let scheduler = detect_scheduler();
    match scheduler {
        "launchd" => launchd::status(),
        "systemd" => systemd::status(),
        "cron" => cron::status(),
        "windows_task_scheduler" => windows::status(),
        _ => Err(AppError::General {
            message: format!("Unsupported scheduler: {scheduler}"),
            hint: None,
        }),
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct WatchdogStatus {
    pub scheduler: String,
    pub installed: bool,
    pub running: bool,
    pub interval_secs: Option<u64>,
}
