pub mod human;
pub mod json;

use crate::error::AppError;
use crate::types::ResolvedFormat;

/// Trait for types that can be rendered as command output.
pub trait Renderable {
    /// The command name for the JSON envelope.
    fn command_name(&self) -> &str;

    /// Render as JSON envelope (success case).
    fn to_json(&self) -> serde_json::Value;

    /// Render as human-readable terminal output.
    fn to_human(&self) -> String;
}

/// Dispatch output to the correct format and print.
pub fn render(output: &dyn Renderable, format: ResolvedFormat) {
    match format {
        ResolvedFormat::Json => {
            let envelope = json::wrap_success(output);
            println!(
                "{}",
                serde_json::to_string_pretty(&envelope).expect("JSON serialization failed")
            );
        }
        ResolvedFormat::Human => {
            print!("{}", output.to_human());
        }
    }
}

/// Render an error to the correct format and print to stderr.
pub fn render_error(err: &AppError, command: &str, format: ResolvedFormat) {
    match format {
        ResolvedFormat::Json => {
            let envelope = err.to_json(command);
            eprintln!(
                "{}",
                serde_json::to_string_pretty(&envelope).expect("JSON serialization failed")
            );
        }
        ResolvedFormat::Human => {
            human::print_error(err);
        }
    }
}
