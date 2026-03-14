use crate::cli::doctor::DoctorArgs;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(_args: DoctorArgs) -> Result<ExitCode, AppError> {
    let db = crate::db::Database::open(&crate::common::platform::db_path())?;
    let issues = crate::congruency::audit(&db)?;

    let entries: Vec<serde_json::Value> = issues
        .iter()
        .map(|i| serde_json::json!(i))
        .collect();

    let errors = issues.iter().filter(|i| i.severity == "error").count();
    let warnings = issues.iter().filter(|i| i.severity == "warning").count();

    let result = DoctorResult {
        data: serde_json::json!({
            "issues": entries,
            "errors": errors,
            "warnings": warnings,
            "clean": issues.is_empty(),
        }),
    };
    output::render(&result);

    if errors > 0 {
        Ok(ExitCode::ValidationError)
    } else {
        Ok(ExitCode::Success)
    }
}

struct DoctorResult {
    data: serde_json::Value,
}
impl Renderable for DoctorResult {
    fn command_name(&self) -> &str {
        "doctor"
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": self.data })
    }
}
