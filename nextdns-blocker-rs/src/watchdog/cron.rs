use crate::error::AppError;

use super::WatchdogStatus;

const CRON_MARKER: &str = "# ndb-watchdog";

fn ndb_binary() -> String {
    std::env::current_exe()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "ndb".to_string())
}

pub fn install(interval_secs: u64) -> Result<String, AppError> {
    let minutes = (interval_secs / 60).max(1);
    let cron_expr = if minutes >= 60 {
        format!("0 */{} * * *", minutes / 60)
    } else {
        format!("*/{minutes} * * * *")
    };

    let entry = format!(
        "{cron_expr} {} watchdog run {CRON_MARKER}",
        ndb_binary()
    );

    // Read existing crontab
    let existing = std::process::Command::new("crontab")
        .arg("-l")
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).to_string())
        .unwrap_or_default();

    // Remove old ndb entries and add new one
    let mut lines: Vec<&str> = existing
        .lines()
        .filter(|l| !l.contains(CRON_MARKER))
        .collect();
    lines.push(&entry);
    let new_crontab = lines.join("\n") + "\n";

    let mut child = std::process::Command::new("crontab")
        .arg("-")
        .stdin(std::process::Stdio::piped())
        .spawn()?;

    use std::io::Write;
    if let Some(ref mut stdin) = child.stdin {
        stdin.write_all(new_crontab.as_bytes())?;
    }
    child.wait()?;

    Ok(entry)
}

pub fn uninstall() -> Result<(), AppError> {
    let existing = std::process::Command::new("crontab")
        .arg("-l")
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).to_string())
        .unwrap_or_default();

    let new_crontab: String = existing
        .lines()
        .filter(|l| !l.contains(CRON_MARKER))
        .collect::<Vec<_>>()
        .join("\n")
        + "\n";

    let mut child = std::process::Command::new("crontab")
        .arg("-")
        .stdin(std::process::Stdio::piped())
        .spawn()?;

    use std::io::Write;
    if let Some(ref mut stdin) = child.stdin {
        stdin.write_all(new_crontab.as_bytes())?;
    }
    child.wait()?;

    Ok(())
}

pub fn status() -> Result<WatchdogStatus, AppError> {
    let existing = std::process::Command::new("crontab")
        .arg("-l")
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).to_string())
        .unwrap_or_default();

    let installed = existing.contains(CRON_MARKER);

    Ok(WatchdogStatus {
        scheduler: "cron".to_string(),
        installed,
        running: installed,
        interval_secs: None,
    })
}
