use async_trait::async_trait;

use super::NotificationAdapter;
use crate::error::AppError;

pub struct TelegramAdapter {
    bot_token: String,
    chat_id: String,
    http: reqwest::Client,
}

impl TelegramAdapter {
    pub fn new(bot_token: String, chat_id: String) -> Self {
        Self {
            bot_token,
            chat_id,
            http: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl NotificationAdapter for TelegramAdapter {
    fn name(&self) -> &str {
        "telegram"
    }

    async fn send(&self, title: &str, message: &str) -> Result<(), AppError> {
        let url = format!(
            "https://api.telegram.org/bot{}/sendMessage",
            self.bot_token
        );

        let body = serde_json::json!({
            "chat_id": self.chat_id,
            "text": format!("*{title}*\n{message}"),
            "parse_mode": "Markdown"
        });

        self.http.post(&url).json(&body).send().await?;

        Ok(())
    }
}
