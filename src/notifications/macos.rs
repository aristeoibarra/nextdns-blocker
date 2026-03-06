use super::NotificationAdapter;
use crate::error::AppError;

pub struct MacosAdapter;

impl MacosAdapter {
    pub fn new() -> Self {
        Self
    }
}

impl NotificationAdapter for MacosAdapter {
    fn name(&self) -> &str {
        "macos"
    }

    fn send(&self, title: &str, message: &str) -> Result<(), AppError> {
        let script = format!(
            "display notification \"{}\" with title \"{}\"",
            message.replace('\"', "\\\""),
            title.replace('\"', "\\\""),
        );

        std::process::Command::new("osascript")
            .args(["-e", &script])
            .output()
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
