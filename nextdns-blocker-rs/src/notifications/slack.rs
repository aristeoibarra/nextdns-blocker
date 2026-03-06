use async_trait::async_trait;

use super::NotificationAdapter;
use crate::error::AppError;

pub struct SlackAdapter {
    webhook_url: String,
    http: reqwest::Client,
}

impl SlackAdapter {
    pub fn new(webhook_url: String) -> Self {
        Self {
            webhook_url,
            http: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl NotificationAdapter for SlackAdapter {
    fn name(&self) -> &str {
        "slack"
    }

    async fn send(&self, title: &str, message: &str) -> Result<(), AppError> {
        let body = serde_json::json!({
            "blocks": [{
                "type": "header",
                "text": { "type": "plain_text", "text": title }
            }, {
                "type": "section",
                "text": { "type": "mrkdwn", "text": message }
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
