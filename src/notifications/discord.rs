use async_trait::async_trait;

use super::NotificationAdapter;
use crate::error::AppError;

pub struct DiscordAdapter {
    webhook_url: String,
    http: reqwest::Client,
}

impl DiscordAdapter {
    pub fn new(webhook_url: String) -> Self {
        Self {
            webhook_url,
            http: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl NotificationAdapter for DiscordAdapter {
    fn name(&self) -> &str {
        "discord"
    }

    async fn send(&self, title: &str, message: &str) -> Result<(), AppError> {
        let body = serde_json::json!({
            "embeds": [{
                "title": title,
                "description": message,
                "color": 3447003
            }]
        });

        self.http
            .post(&self.webhook_url)
            .json(&body)
            .send()
            .await?;

        Ok(())
    }
}
