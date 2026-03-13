use std::collections::HashMap;
use std::path::PathBuf;

use crate::error::AppError;

/// Path to the .env file in the data directory.
fn env_file_path() -> PathBuf {
    super::platform::data_dir().join(".env")
}

/// Store a secret in the .env file.
pub fn set_secret(name: &str, value: &str) -> Result<(), AppError> {
    let path = env_file_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let mut entries = read_env_file(&path);
    let key = secret_name_to_env_key(name);
    entries.insert(key, value.to_string());
    write_env_file(&path, &entries)
}

/// Retrieve a secret from the .env file.
pub fn get_secret(name: &str) -> Result<Option<String>, AppError> {
    let path = env_file_path();
    if !path.exists() {
        return Ok(None);
    }
    let entries = read_env_file(&path);
    let key = secret_name_to_env_key(name);
    Ok(entries.get(&key).cloned())
}

/// Remove a secret from the .env file.
pub fn remove_secret(name: &str) -> Result<bool, AppError> {
    let path = env_file_path();
    if !path.exists() {
        return Ok(false);
    }
    let mut entries = read_env_file(&path);
    let key = secret_name_to_env_key(name);
    let removed = entries.remove(&key).is_some();
    if removed {
        write_env_file(&path, &entries)?;
    }
    Ok(removed)
}

/// Map secret names to env var keys.
fn secret_name_to_env_key(name: &str) -> String {
    match name {
        "api-key" => "NEXTDNS_API_KEY".to_string(),
        "profile-id" => "NEXTDNS_PROFILE_ID".to_string(),
        other => other.to_uppercase().replace('-', "_"),
    }
}

/// Read the .env file into a key-value map.
fn read_env_file(path: &std::path::Path) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return map,
    };
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((key, value)) = line.split_once('=') {
            let key = key.trim().to_string();
            let value = value.trim().trim_matches('"').trim_matches('\'').to_string();
            map.insert(key, value);
        }
    }
    map
}

/// Write the key-value map back to the .env file with owner-only permissions.
fn write_env_file(path: &std::path::Path, entries: &HashMap<String, String>) -> Result<(), AppError> {
    use std::os::unix::fs::OpenOptionsExt;

    let mut lines: Vec<String> = entries
        .iter()
        .map(|(k, v)| {
            // Quote values to handle special chars (=, spaces, etc.)
            let escaped = v.replace('\\', "\\\\").replace('"', "\\\"");
            format!("{k}=\"{escaped}\"")
        })
        .collect();
    lines.sort();
    let content = lines.join("\n") + "\n";

    std::fs::OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .mode(0o600)
        .open(path)
        .and_then(|mut f| {
            use std::io::Write;
            f.write_all(content.as_bytes())
        })
        .map_err(|e| AppError::General {
            message: format!("Failed to write .env file: {e}"),
            hint: Some(format!("Path: {}", path.display())),
        })
}
