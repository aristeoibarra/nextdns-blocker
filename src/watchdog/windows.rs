use crate::error::AppError;

use super::WatchdogStatus;

const TASK_NAME: &str = "NDB-Watchdog";

fn ndb_binary() -> String {
    std::env::current_exe()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "ndb.exe".to_string())
}

pub fn install(interval_secs: u64) -> Result<String, AppError> {
    let minutes = (interval_secs / 60).max(1);

    let script = format!(
        r#"$action = New-ScheduledTaskAction -Execute '{}' -Argument 'watchdog run'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes {minutes})
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Force"#,
        ndb_binary()
    );

    std::process::Command::new("powershell")
        .args(["-Command", &script])
        .status()
        .map_err(|e| AppError::General {
            message: format!("Failed to create scheduled task: {e}"),
            hint: Some("Run as Administrator".to_string()),
        })?;

    Ok(TASK_NAME.to_string())
}

pub fn uninstall() -> Result<(), AppError> {
    std::process::Command::new("powershell")
        .args([
            "-Command",
            &format!("Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false"),
        ])
        .status()
        .map_err(|e| AppError::General {
            message: format!("Failed to remove scheduled task: {e}"),
            hint: None,
        })?;

    Ok(())
}

pub fn status() -> Result<WatchdogStatus, AppError> {
    let output = std::process::Command::new("powershell")
        .args([
            "-Command",
            &format!("Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty State"),
        ])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to check task status: {e}"),
            hint: None,
        })?;

    let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let installed = !state.is_empty();
    let running = state == "Ready" || state == "Running";

    Ok(WatchdogStatus {
        scheduler: "windows_task_scheduler".to_string(),
        installed,
        running,
        interval_secs: None,
    })
}
