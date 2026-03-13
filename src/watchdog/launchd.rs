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
/// Parses line-by-line to tolerate whitespace/formatting differences.
fn binary_path_from_plist(path: &std::path::Path) -> Option<String> {
    let content = std::fs::read_to_string(path).ok()?;
    let lines: Vec<&str> = content.lines().map(|l| l.trim()).collect();

    // Find the ProgramArguments key, then the <array>, then the first <string>
    let mut found_key = false;
    let mut in_array = false;

    for line in &lines {
        if !found_key {
            if line.contains("<key>ProgramArguments</key>") {
                found_key = true;
            }
            continue;
        }
        if !in_array {
            if line.contains("<array>") {
                in_array = true;
            }
            continue;
        }
        // We're inside ProgramArguments array — extract first <string>
        if line.contains("</array>") {
            return None; // Empty array
        }
        if let (Some(start), Some(end)) = (line.find("<string>"), line.find("</string>")) {
            let value_start = start + "<string>".len();
            if value_start <= end {
                return Some(line[value_start..end].to_string());
            }
        }
    }

    None
}

/// Extract the interval from the plist XML.
/// Parses line-by-line to tolerate whitespace/formatting differences.
fn interval_from_plist(path: &std::path::Path) -> Option<u64> {
    let content = std::fs::read_to_string(path).ok()?;
    let lines: Vec<&str> = content.lines().map(|l| l.trim()).collect();

    let mut found_key = false;

    for line in &lines {
        if !found_key {
            if line.contains("<key>StartInterval</key>") {
                found_key = true;
                // Check if integer is on the same line (compact plist)
                if let (Some(start), Some(end)) = (line.find("<integer>"), line.find("</integer>")) {
                    let value_start = start + "<integer>".len();
                    return line[value_start..end].trim().parse().ok();
                }
            }
            continue;
        }
        // Next line after the key should have the integer value
        if let (Some(start), Some(end)) = (line.find("<integer>"), line.find("</integer>")) {
            let value_start = start + "<integer>".len();
            return line[value_start..end].trim().parse().ok();
        }
        // If we hit another key without finding integer, give up
        if line.contains("<key>") {
            return None;
        }
    }

    None
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
