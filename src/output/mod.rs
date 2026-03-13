pub mod json;

use crate::error::AppError;

/// Trait for types that can be rendered as command output.
pub trait Renderable {
    /// The command name for the JSON envelope.
    fn command_name(&self) -> &str;

    /// Render as JSON data for the envelope.
    fn to_json(&self) -> serde_json::Value;
}

/// Render output as JSON envelope to stdout.
pub fn render(output: &dyn Renderable) {
    let envelope = json::wrap_success(output);
    match serde_json::to_string_pretty(&envelope) {
        Ok(json) => println!("{json}"),
        Err(e) => eprintln!("{{\"ok\":false,\"error\":\"JSON serialization failed: {e}\"}}"),
    }
}

/// Render an error as JSON envelope to stderr.
pub fn render_error(err: &AppError, command: &str) {
    let envelope = err.to_json(command);
    match serde_json::to_string_pretty(&envelope) {
        Ok(json) => eprintln!("{json}"),
        Err(e) => eprintln!("{{\"ok\":false,\"error\":\"JSON serialization failed: {e}\"}}"),
    }
}
