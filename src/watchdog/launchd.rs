use std::path::PathBuf;

use crate::error::AppError;

use super::WatchdogStatus;

const LABEL: &str = "com.ndb.watchdog";
const DEFAULT_INTERVAL: u64 = 300;

fn plist_path() -> Result<PathBuf, AppError> {
    let home = dirs::home_dir().ok_or_else(|| AppError::General {
        message: "Could not determine home directory".to_string(),
        hint: Some("Ensure $HOME is set".to_string()),
    })?;
    Ok(home.join("Library/LaunchAgents").join(format!("{LABEL}.plist")))
}

fn log_dir() -> Result<PathBuf, AppError> {
    let home = dirs::home_dir().ok_or_else(|| AppError::General {
        message: "Could not determine home directory".to_string(),
        hint: Some("Ensure $HOME is set".to_string()),
    })?;
    let dir = home.join("Library/Logs/ndb");
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn ndb_binary() -> String {
    std::env::current_exe()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "ndb".to_string())
}

/// Extract the binary path from the plist XML.
fn binary_path_from_plist(path: &std::path::Path) -> Option<String> {
    let content = std::fs::read_to_string(path).ok()?;
    // ProgramArguments array: first <string> after <key>ProgramArguments</key> <array>
    let marker = "<key>ProgramArguments</key>";
    let after = content.find(marker)?;
    let rest = &content[after..];
    // Find the first <string>...</string> inside the <array>
    let open = rest.find("<array>")?;
    let inner = &rest[open..];
    let s_start = inner.find("<string>")? + "<string>".len();
    let s_end = inner[s_start..].find("</string>")?;
    Some(inner[s_start..s_start + s_end].to_string())
}

/// Extract the interval from the plist XML.
fn interval_from_plist(path: &std::path::Path) -> Option<u64> {
    let content = std::fs::read_to_string(path).ok()?;
    let marker = "<key>StartInterval</key>";
    let after = content.find(marker)?;
    let rest = &content[after..];
    let s_start = rest.find("<integer>")? + "<integer>".len();
    let s_end = rest[s_start..].find("</integer>")?;
    rest[s_start..s_start + s_end].trim().parse().ok()
}

pub fn install(interval_secs: u64) -> Result<String, AppError> {
    let log_dir = log_dir()?;
    let log_out = log_dir.join("watchdog.log");
    let log_err = log_dir.join("watchdog.err");

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
    <string>{}</string>
    <key>StandardErrorPath</key>
    <string>{}</string>
</dict>
</plist>"#,
        ndb_binary(),
        log_out.display(),
        log_err.display(),
    );

    let path = plist_path()?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    // Unload existing job before overwriting
    if path.exists() {
        let _ = std::process::Command::new("launchctl")
            .args(["unload", &path.to_string_lossy()])
            .status();
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
    let path = plist_path()?;

    if path.exists() {
        // Best-effort unload — may fail if already unloaded
        let _ = std::process::Command::new("launchctl")
            .args(["unload", &path.to_string_lossy()])
            .status();
        std::fs::remove_file(&path)?;
    }

    Ok(())
}

pub fn status() -> Result<WatchdogStatus, AppError> {
    let path = plist_path()?;
    let installed = path.exists();

    let (running, binary_path, binary_valid, interval_secs) = if installed {
        let running = std::process::Command::new("launchctl")
            .args(["list", LABEL])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false);

        let plist_binary = binary_path_from_plist(&path);
        let current = ndb_binary();
        let valid = plist_binary.as_ref().is_some_and(|p| {
            std::path::Path::new(p).exists() && *p == current
        });
        let interval = interval_from_plist(&path);

        (running, plist_binary, valid, interval)
    } else {
        (false, None, false, None)
    };

    let healthy = installed && running && binary_valid;

    Ok(WatchdogStatus {
        scheduler: "launchd".to_string(),
        installed,
        running,
        interval_secs,
        binary_path,
        binary_valid,
        healthy,
    })
}

/// Re-install watchdog if plist is missing or binary path is stale.
/// Returns true if a repair was performed.
pub fn ensure_healthy() -> Result<bool, AppError> {
    let path = plist_path()?;

    if !path.exists() {
        // Not installed at all — install with default interval
        install(DEFAULT_INTERVAL)?;
        return Ok(true);
    }

    let plist_binary = binary_path_from_plist(&path);
    let current = ndb_binary();

    let needs_repair = match &plist_binary {
        Some(p) => !std::path::Path::new(p).exists() || *p != current,
        None => true, // can't parse plist — reinstall
    };

    if needs_repair {
        let interval = interval_from_plist(&path).unwrap_or(DEFAULT_INTERVAL);
        install(interval)?;
        return Ok(true);
    }

    // Plist exists and binary matches — check if loaded in launchctl
    let loaded = std::process::Command::new("launchctl")
        .args(["list", LABEL])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);

    if !loaded {
        std::process::Command::new("launchctl")
            .args(["load", &path.to_string_lossy()])
            .status()
            .map_err(|e| AppError::General {
                message: format!("Failed to load launchd plist: {e}"),
                hint: None,
            })?;
        return Ok(true);
    }

    Ok(false)
}
