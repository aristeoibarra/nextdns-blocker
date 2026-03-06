use std::path::PathBuf;

use crate::error::AppError;

use super::WatchdogStatus;

const LABEL: &str = "com.ndb.watchdog";

fn plist_path() -> PathBuf {
    dirs::home_dir()
        .expect("home directory")
        .join("Library/LaunchAgents")
        .join(format!("{LABEL}.plist"))
}

fn ndb_binary() -> String {
    std::env::current_exe()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "ndb".to_string())
}

pub fn install(interval_secs: u64) -> Result<String, AppError> {
    let plist_content = format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{}</string>
        <string>watchdog</string>
        <string>run</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_secs}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ndb-watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ndb-watchdog.err</string>
</dict>
</plist>"#,
        ndb_binary()
    );

    let path = plist_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, plist_content)?;

    std::process::Command::new("launchctl")
        .args(["load", &path.to_string_lossy()])
        .status()
        .map_err(|e| AppError::General {
            message: format!("Failed to load launchd plist: {e}"),
            hint: None,
        })?;

    Ok(path.to_string_lossy().to_string())
}

pub fn uninstall() -> Result<(), AppError> {
    let path = plist_path();

    if path.exists() {
        let _ = std::process::Command::new("launchctl")
            .args(["unload", &path.to_string_lossy()])
            .status();
        std::fs::remove_file(&path)?;
    }

    Ok(())
}

pub fn status() -> Result<WatchdogStatus, AppError> {
    let path = plist_path();
    let installed = path.exists();

    let running = if installed {
        std::process::Command::new("launchctl")
            .args(["list", LABEL])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    } else {
        false
    };

    Ok(WatchdogStatus {
        scheduler: "launchd".to_string(),
        installed,
        running,
        interval_secs: None,
    })
}
