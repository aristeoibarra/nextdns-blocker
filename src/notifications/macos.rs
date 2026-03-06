use async_trait::async_trait;

use super::NotificationAdapter;
use crate::error::AppError;

pub struct MacosAdapter;

impl MacosAdapter {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl NotificationAdapter for MacosAdapter {
    fn name(&self) -> &str {
        "macos"
    }

    async fn send(&self, title: &str, message: &str) -> Result<(), AppError> {
        if !cfg!(target_os = "macos") {
            return Ok(());
        }

        let script = format!(
            "display notification \"{}\" with title \"{}\"",
            message.replace('\"', "\\\""),
            title.replace('\"', "\\\""),
        );

        tokio::process::Command::new("osascript")
            .args(["-e", &script])
            .output()
            .await
            .map_err(|e| AppError::General {
                message: format!("Failed to send macOS notification: {e}"),
                hint: None,
            })?;

        Ok(())
    }
}

impl Default for MacosAdapter {
    fn default() -> Self {
        Self::new()
    }
}
