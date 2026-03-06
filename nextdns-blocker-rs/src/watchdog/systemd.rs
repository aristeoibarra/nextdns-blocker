use std::path::PathBuf;

use crate::error::AppError;

use super::WatchdogStatus;

fn user_systemd_dir() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("~/.config"))
        .join("systemd/user")
}

fn ndb_binary() -> String {
    std::env::current_exe()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "ndb".to_string())
}

pub fn install(interval_secs: u64) -> Result<String, AppError> {
    let dir = user_systemd_dir();
    std::fs::create_dir_all(&dir)?;

    let service = format!(
        "[Unit]\nDescription=NDB Watchdog\n\n[Service]\nType=oneshot\nExecStart={} watchdog run\n",
        ndb_binary()
    );

    let timer = format!(
        "[Unit]\nDescription=NDB Watchdog Timer\n\n[Timer]\nOnBootSec=60\nOnUnitActiveSec={interval_secs}s\n\n[Install]\nWantedBy=timers.target\n"
    );

    let service_path = dir.join("ndb-watchdog.service");
    let timer_path = dir.join("ndb-watchdog.timer");

    std::fs::write(&service_path, service)?;
    std::fs::write(&timer_path, timer)?;

    std::process::Command::new("systemctl")
        .args(["--user", "daemon-reload"])
        .status()?;

    std::process::Command::new("systemctl")
        .args(["--user", "enable", "--now", "ndb-watchdog.timer"])
        .status()?;

    Ok(timer_path.to_string_lossy().to_string())
}

pub fn uninstall() -> Result<(), AppError> {
    let _ = std::process::Command::new("systemctl")
        .args(["--user", "disable", "--now", "ndb-watchdog.timer"])
        .status();

    let dir = user_systemd_dir();
    let _ = std::fs::remove_file(dir.join("ndb-watchdog.service"));
    let _ = std::fs::remove_file(dir.join("ndb-watchdog.timer"));

    let _ = std::process::Command::new("systemctl")
        .args(["--user", "daemon-reload"])
        .status();

    Ok(())
}

pub fn status() -> Result<WatchdogStatus, AppError> {
    let timer_exists = user_systemd_dir().join("ndb-watchdog.timer").exists();

    let running = std::process::Command::new("systemctl")
        .args(["--user", "is-active", "ndb-watchdog.timer"])
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim() == "active")
        .unwrap_or(false);

    Ok(WatchdogStatus {
        scheduler: "systemd".to_string(),
        installed: timer_exists,
        running,
        interval_secs: None,
    })
}
