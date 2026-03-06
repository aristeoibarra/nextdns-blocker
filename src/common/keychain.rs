use crate::error::AppError;

const SERVICE: &str = "ndb-nextdns-blocker";

/// Store a secret in the macOS Keychain.
pub fn set_secret(account: &str, value: &str) -> Result<(), AppError> {
    // Delete existing entry first (ignore errors if it doesn't exist)
    let _ = std::process::Command::new("security")
        .args(["delete-generic-password", "-a", account, "-s", SERVICE])
        .output();

    let output = std::process::Command::new("security")
        .args([
            "add-generic-password",
            "-a", account,
            "-s", SERVICE,
            "-w", value,
            "-U", // update if exists
        ])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to access macOS Keychain: {e}"),
            hint: Some("Ensure you have Keychain access permissions".to_string()),
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(AppError::General {
            message: format!("Keychain set failed: {stderr}"),
            hint: None,
        });
    }

    Ok(())
}

/// Retrieve a secret from the macOS Keychain.
pub fn get_secret(account: &str) -> Result<Option<String>, AppError> {
    let output = std::process::Command::new("security")
        .args([
            "find-generic-password",
            "-a", account,
            "-s", SERVICE,
            "-w", // output password only
        ])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to access macOS Keychain: {e}"),
            hint: None,
        })?;

    if !output.status.success() {
        return Ok(None);
    }

    let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if value.is_empty() {
        Ok(None)
    } else {
        Ok(Some(value))
    }
}

/// Remove a secret from the macOS Keychain.
pub fn remove_secret(account: &str) -> Result<bool, AppError> {
    let output = std::process::Command::new("security")
        .args(["delete-generic-password", "-a", account, "-s", SERVICE])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to access macOS Keychain: {e}"),
            hint: None,
        })?;

    Ok(output.status.success())
}
