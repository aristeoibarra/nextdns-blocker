use serde_json::json;

use crate::android_blocker::firebase::FirebaseClient;
use crate::error::AppError;

/// Send a sync push to the Android device via FCM HTTP v1.
pub fn send_sync_push(client: &FirebaseClient) -> Result<(), AppError> {
    let fcm_token = client.get_fcm_token()?;
    let token = match fcm_token {
        Some(t) if !t.is_empty() => t,
        _ => return Ok(()), // No token registered yet — Android app not installed
    };

    let url = format!(
        "https://fcm.googleapis.com/v1/projects/{}/messages:send",
        client.project_id
    );

    let agent = ureq::Agent::new_with_config(
        ureq::config::Config::builder()
            .timeout_global(Some(std::time::Duration::from_secs(15)))
            .build(),
    );

    agent
        .post(&url)
        .header("Authorization", &format!("Bearer {}", client.access_token()))
        .send_json(&json!({
            "message": {
                "token": token,
                "android": {
                    "priority": "high"
                },
                "data": {
                    "action": "sync"
                }
            }
        }))
        .map_err(|e| AppError::Api {
            message: format!("FCM push failed: {e}"),
            status_code: extract_status(&e),
            hint: Some("FCM push failed — Android device will sync via WorkManager within 15 minutes".to_string()),
        })?;

    Ok(())
}

fn extract_status(e: &ureq::Error) -> Option<u16> {
    if let ureq::Error::StatusCode(code) = e {
        Some(*code)
    } else {
        None
    }
}
