use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;

use serde_json::json;

use crate::db::Database;
use crate::error::AppError;

/// Firebase client for RTDB and FCM operations.
pub struct FirebaseClient {
    agent: ureq::Agent,
    pub project_id: String,
    rtdb_url: String,
    pub device_id: String,
    access_token: String,
}

impl FirebaseClient {
    /// Try to create a Firebase client. Returns None if not configured.
    pub fn try_new(db: &Database) -> Option<Self> {
        let project_id = db.with_conn(|conn| crate::db::config::get_value(conn, "firebase_project_id")).ok()??;
        if project_id.is_empty() {
            return None;
        }
        let rtdb_url = db.with_conn(|conn| crate::db::config::get_value(conn, "firebase_rtdb_url")).ok()??;
        if rtdb_url.is_empty() {
            return None;
        }
        let device_id = db.with_conn(|conn| crate::db::config::get_value(conn, "android_device_id"))
            .ok()?
            .unwrap_or_else(|| "android_pixel".to_string());

        let sa_path = crate::common::keychain::get_secret("firebase-service-account").ok()??;

        let access_token = get_or_refresh_token(&sa_path).ok()?;

        let agent = ureq::Agent::new_with_config(
            ureq::config::Config::builder()
                .timeout_global(Some(std::time::Duration::from_secs(15)))
                .build(),
        );

        Some(Self { agent, project_id, rtdb_url, device_id, access_token })
    }

    /// Write a blocked package to Firebase RTDB.
    pub fn set_package_blocked(
        &self,
        package: &str,
        domain: &str,
        unblock_at: Option<i64>,
    ) -> Result<(), AppError> {
        let encoded_pkg = package.replace('.', "~");
        let url = format!(
            "{}/devices/{}/blocked_packages/{}.json?auth={}",
            self.rtdb_url, self.device_id, encoded_pkg, self.access_token
        );
        self.agent
            .put(&url)
            .send_json(&json!({
                "domain": domain,
                "blocked_at": crate::common::time::now_unix(),
                "unblock_at": unblock_at,
            }))
            .map_err(|e| AppError::Api {
                message: format!("Firebase RTDB PUT failed: {e}"),
                status_code: extract_status(&e),
                hint: Some("Check Firebase config and network connectivity".to_string()),
            })?;
        Ok(())
    }

    /// Remove a blocked package from Firebase RTDB.
    pub fn remove_package(&self, package: &str) -> Result<(), AppError> {
        let encoded_pkg = package.replace('.', "~");
        let url = format!(
            "{}/devices/{}/blocked_packages/{}.json?auth={}",
            self.rtdb_url, self.device_id, encoded_pkg, self.access_token
        );
        self.agent
            .delete(&url)
            .call()
            .map_err(|e| AppError::Api {
                message: format!("Firebase RTDB DELETE failed: {e}"),
                status_code: extract_status(&e),
                hint: Some("Check Firebase config and network connectivity".to_string()),
            })?;
        Ok(())
    }

    /// Replace the entire blocked_packages node with a computed set.
    /// This is an atomic PUT of the full list (not individual package pushes).
    pub fn set_all_blocked_packages(
        &self,
        packages: &std::collections::HashMap<String, serde_json::Value>,
    ) -> Result<(), AppError> {
        let url = format!(
            "{}/devices/{}/blocked_packages.json?auth={}",
            self.rtdb_url, self.device_id, self.access_token
        );
        self.agent
            .put(&url)
            .send_json(&json!(packages))
            .map_err(|e| AppError::Api {
                message: format!("Firebase RTDB PUT blocked_packages failed: {e}"),
                status_code: extract_status(&e),
                hint: Some("Check Firebase config and network connectivity".to_string()),
            })?;
        Ok(())
    }

    /// Get the access token for external use (e.g., FCM).
    pub fn access_token(&self) -> &str {
        &self.access_token
    }

    /// Read installed packages reported by the Android device from RTDB.
    /// Returns a map of package_name -> {label, version}.
    pub fn get_installed_packages(&self) -> Result<serde_json::Value, AppError> {
        let url = format!(
            "{}/devices/{}/installed_packages.json?auth={}",
            self.rtdb_url, self.device_id, self.access_token
        );
        let mut response = self.agent
            .get(&url)
            .call()
            .map_err(|e| AppError::Api {
                message: format!("Firebase RTDB GET failed: {e}"),
                status_code: extract_status(&e),
                hint: Some("Check Firebase config and network connectivity".to_string()),
            })?;
        let body: serde_json::Value = response.body_mut().read_json().map_err(|e| AppError::Api {
            message: format!("Failed to parse installed packages response: {e}"),
            status_code: None,
            hint: None,
        })?;
        Ok(body)
    }

    /// Read the FCM token for this device from RTDB.
    pub fn get_fcm_token(&self) -> Result<Option<String>, AppError> {
        let url = format!(
            "{}/devices/{}/fcm_token.json?auth={}",
            self.rtdb_url, self.device_id, self.access_token
        );
        let mut response = self.agent
            .get(&url)
            .call()
            .map_err(|e| AppError::Api {
                message: format!("Firebase RTDB GET failed: {e}"),
                status_code: extract_status(&e),
                hint: Some("Check Firebase config and network connectivity".to_string()),
            })?;
        let body: serde_json::Value = response.body_mut().read_json().map_err(|e| AppError::Api {
            message: format!("Failed to parse FCM token response: {e}"),
            status_code: None,
            hint: None,
        })?;
        Ok(body.as_str().map(|s| s.to_string()))
    }
}

/// Get a valid OAuth2 access token, using cache if available.
fn get_or_refresh_token(sa_path: &str) -> Result<String, AppError> {
    let cache_path = token_cache_path();

    // Check cached token
    if let Ok(content) = std::fs::read_to_string(&cache_path) {
        if let Ok(cached) = serde_json::from_str::<serde_json::Value>(&content) {
            let expires_at = cached["expires_at"].as_i64().unwrap_or(0);
            if expires_at > crate::common::time::now_unix() + 300 {
                if let Some(token) = cached["access_token"].as_str() {
                    return Ok(token.to_string());
                }
            }
        }
    }

    // Read service account JSON
    let sa_content = std::fs::read_to_string(sa_path).map_err(|e| AppError::Config {
        message: format!("Cannot read service account file: {e}"),
        hint: Some(format!("Path: {sa_path}. Download from Firebase Console > Project Settings > Service Accounts")),
    })?;
    let sa: serde_json::Value = serde_json::from_str(&sa_content).map_err(|e| AppError::Config {
        message: format!("Invalid service account JSON: {e}"),
        hint: Some("Ensure the file is a valid Firebase service account JSON".to_string()),
    })?;

    let client_email = sa["client_email"].as_str().ok_or_else(|| AppError::Config {
        message: "Service account missing client_email".to_string(),
        hint: None,
    })?;
    let private_key = sa["private_key"].as_str().ok_or_else(|| AppError::Config {
        message: "Service account missing private_key".to_string(),
        hint: None,
    })?;
    let token_uri = sa["token_uri"].as_str().unwrap_or("https://oauth2.googleapis.com/token");

    // Create and sign JWT
    let now = crate::common::time::now_unix();
    let claims = json!({
        "iss": client_email,
        "scope": "https://www.googleapis.com/auth/firebase.database https://www.googleapis.com/auth/firebase.messaging",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    });

    let encoding_key = jsonwebtoken::EncodingKey::from_rsa_pem(private_key.as_bytes())
        .map_err(|e| AppError::Config {
            message: format!("Invalid private key in service account: {e}"),
            hint: Some("Re-download the service account JSON from Firebase Console".to_string()),
        })?;

    let header = jsonwebtoken::Header::new(jsonwebtoken::Algorithm::RS256);
    let jwt = jsonwebtoken::encode(&header, &claims, &encoding_key).map_err(|e| AppError::Config {
        message: format!("Failed to create JWT: {e}"),
        hint: None,
    })?;

    // Exchange JWT for access token
    let agent = ureq::Agent::new_with_config(
        ureq::config::Config::builder()
            .timeout_global(Some(std::time::Duration::from_secs(15)))
            .build(),
    );
    let form_body = format!(
        "grant_type={}&assertion={}",
        urlencoded("urn:ietf:params:oauth:grant-type:jwt-bearer"),
        urlencoded(&jwt),
    );
    let mut response = agent
        .post(token_uri)
        .header("Content-Type", "application/x-www-form-urlencoded")
        .send(form_body.as_bytes())
        .map_err(|e| AppError::Api {
            message: format!("OAuth2 token exchange failed: {e}"),
            status_code: extract_status(&e),
            hint: Some("Check service account credentials and network connectivity".to_string()),
        })?;

    let token_response: serde_json::Value = response.body_mut().read_json().map_err(|e| AppError::Api {
        message: format!("Failed to parse token response: {e}"),
        status_code: None,
        hint: None,
    })?;

    let access_token = token_response["access_token"]
        .as_str()
        .ok_or_else(|| AppError::Api {
            message: "Token response missing access_token".to_string(),
            status_code: None,
            hint: None,
        })?
        .to_string();

    let expires_in = token_response["expires_in"].as_i64().unwrap_or(3600);
    let expires_at = now + expires_in;

    // Cache token
    let cache_content = json!({
        "access_token": access_token,
        "expires_at": expires_at,
    });
    if let Some(parent) = cache_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(bytes) = serde_json::to_string(&cache_content) {
        if std::fs::write(&cache_path, bytes.as_bytes()).is_ok() {
            let _ = std::fs::set_permissions(&cache_path, std::fs::Permissions::from_mode(0o600));
        }
    }

    Ok(access_token)
}

fn token_cache_path() -> PathBuf {
    crate::common::platform::data_dir().join(".firebase_token")
}

/// Minimal URL encoding for form values.
fn urlencoded(s: &str) -> String {
    s.replace('%', "%25")
        .replace(' ', "%20")
        .replace(':', "%3A")
        .replace('/', "%2F")
        .replace('=', "%3D")
        .replace('&', "%26")
        .replace('+', "%2B")
}

fn extract_status(e: &ureq::Error) -> Option<u16> {
    if let ureq::Error::StatusCode(code) = e {
        Some(*code)
    } else {
        None
    }
}
