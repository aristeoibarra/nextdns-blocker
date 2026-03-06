/// Check if running on macOS.
pub fn is_macos() -> bool {
    cfg!(target_os = "macos")
}

/// Check if running on Linux.
pub fn is_linux() -> bool {
    cfg!(target_os = "linux")
}

/// Check if running on Windows.
pub fn is_windows() -> bool {
    cfg!(target_os = "windows")
}

/// Check if systemd is available (Linux only).
pub fn has_systemd() -> bool {
    if !is_linux() {
        return false;
    }
    std::path::Path::new("/run/systemd/system").exists()
}

/// Get the platform-specific data directory for ndb.
/// Respects `NDB_DATA_DIR` env var override.
pub fn data_dir() -> std::path::PathBuf {
    if let Ok(dir) = std::env::var("NDB_DATA_DIR") {
        return std::path::PathBuf::from(dir);
    }
    dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("ndb")
}

/// Get the platform-specific config directory for ndb.
/// Respects `NDB_CONFIG_DIR` env var override.
pub fn config_dir() -> std::path::PathBuf {
    if let Ok(dir) = std::env::var("NDB_CONFIG_DIR") {
        return std::path::PathBuf::from(dir);
    }
    dirs::config_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("ndb")
}

/// Get the database file path.
pub fn db_path() -> std::path::PathBuf {
    data_dir().join("ndb.db")
}

/// Get the config file path.
pub fn config_path() -> std::path::PathBuf {
    config_dir().join("config.json")
}
