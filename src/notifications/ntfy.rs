use async_trait::async_trait;

use super::NotificationAdapter;
use crate::error::AppError;

pub struct NtfyAdapter {
    url: String,
    topic: String,
    http: reqwest::Client,
}

impl NtfyAdapter {
    pub fn new(url: String, topic: String) -> Self {
        Self {
            url,
            topic,
            http: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl NotificationAdapter for NtfyAdapter {
    fn name(&self) -> &str {
        "ntfy"
    }

    async fn send(&self, title: &str, message: &str) -> Result<(), AppError> {
        let url = format!("{}/{}", self.url.trim_end_matches('/'), self.topic);

        self.http
            .post(&url)
            .header("Title", title)
            .body(message.to_string())
            .send()
            .await?;

        Ok(())
    }
}
