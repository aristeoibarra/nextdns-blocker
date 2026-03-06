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

/// Get the database file path.
pub fn db_path() -> std::path::PathBuf {
    data_dir().join("ndb.db")
}

/// Flush the macOS DNS cache so blocking changes take effect immediately.
/// Runs `dscacheutil -flushcache` (works without sudo on modern macOS).
pub fn flush_dns_cache() {
    let _ = std::process::Command::new("dscacheutil")
        .arg("-flushcache")
        .output();
}
