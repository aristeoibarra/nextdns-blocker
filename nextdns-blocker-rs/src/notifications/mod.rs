pub mod discord;
pub mod macos;
pub mod ntfy;
pub mod slack;
pub mod telegram;

use async_trait::async_trait;

use crate::error::AppError;

/// Trait for notification adapters.
#[async_trait]
pub trait NotificationAdapter: Send + Sync {
    fn name(&self) -> &str;
    async fn send(&self, title: &str, message: &str) -> Result<(), AppError>;
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

    /// Send a notification to all adapters concurrently.
    pub async fn notify(&self, title: &str, message: &str) -> Vec<Result<(), AppError>> {
        let futures: Vec<_> = self
            .adapters
            .iter()
            .map(|a| a.send(title, message))
            .collect();

        futures::future::join_all(futures).await
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
