use console::style;

use crate::error::AppError;

/// Print an error in human-readable format to stderr.
pub fn print_error(err: &AppError) {
    eprintln!("{} {}", style("error:").red().bold(), err);
    if let Some(hint) = err.hint() {
        eprintln!("{} {}", style("hint:").yellow(), hint);
    }
}

/// Print a success message.
pub fn print_success(message: &str) {
    println!("{} {}", style("ok:").green().bold(), message);
}

/// Print a warning message.
pub fn print_warning(message: &str) {
    eprintln!("{} {}", style("warning:").yellow().bold(), message);
}

/// Print an info message.
pub fn print_info(message: &str) {
    println!("{} {}", style("info:").cyan(), message);
}
