pub mod macos;

use crate::error::AppError;

/// Trait for notification adapters.
pub trait NotificationAdapter: Send + Sync {
    fn name(&self) -> &str;
    fn send(&self, title: &str, message: &str) -> Result<(), AppError>;
}

/// Notification manager that dispatches to all configured adapters.
pub struct NotificationManager {
    adapters: Vec<Box<dyn NotificationAdapter>>,
}

impl NotificationManager {
    pub fn new() -> Self {
        Self {
            adapters: Vec::new(),
        }
    }

    pub fn add_adapter(&mut self, adapter: Box<dyn NotificationAdapter>) {
        self.adapters.push(adapter);
    }

    /// Send a notification to all adapters.
    pub fn notify(&self, title: &str, message: &str) -> Vec<Result<(), AppError>> {
        self.adapters
            .iter()
            .map(|a| a.send(title, message))
            .collect()
    }

    pub fn adapter_count(&self) -> usize {
        self.adapters.len()
    }
}

impl Default for NotificationManager {
    fn default() -> Self {
        Self::new()
    }
}
