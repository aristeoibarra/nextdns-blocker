pub mod macos;

use crate::error::AppError;

/// A notification to send.
pub struct Notification {
    pub title: String,
    pub message: String,
    pub subtitle: Option<String>,
    pub sound: Option<String>,
}

impl Notification {
    pub fn new(title: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            message: message.into(),
            subtitle: None,
            sound: None,
        }
    }

    pub fn subtitle(mut self, subtitle: impl Into<String>) -> Self {
        self.subtitle = Some(subtitle.into());
        self
    }

    pub fn sound(mut self, sound: impl Into<String>) -> Self {
        self.sound = Some(sound.into());
        self
    }
}

/// Trait for notification adapters.
pub trait NotificationAdapter: Send + Sync {
    fn name(&self) -> &str;
    fn send(&self, notification: &Notification) -> Result<(), AppError>;
}
