use super::{Notification, NotificationAdapter};
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

    fn send(&self, notification: &Notification) -> Result<(), AppError> {
        let msg = escape(&notification.message);
        let title = escape(&notification.title);

        let mut script = format!("display notification \"{msg}\" with title \"{title}\"");

        if let Some(ref subtitle) = notification.subtitle {
            script.push_str(&format!(" subtitle \"{}\"", escape(subtitle)));
        }

        if let Some(ref sound) = notification.sound {
            script.push_str(&format!(" sound name \"{}\"", escape(sound)));
        }

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

/// Escape a string for safe inclusion in AppleScript double-quoted strings.
fn escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            // Strip control chars to prevent AppleScript injection
            c if c.is_control() => {}
            _ => out.push(c),
        }
    }
    out
}
