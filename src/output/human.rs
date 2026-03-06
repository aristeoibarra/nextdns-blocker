use crate::error::AppError;

/// Print an error in human-readable format to stderr.
pub fn print_error(err: &AppError) {
    eprintln!("error: {err}");
    if let Some(hint) = err.hint() {
        eprintln!("hint: {hint}");
    }
}
