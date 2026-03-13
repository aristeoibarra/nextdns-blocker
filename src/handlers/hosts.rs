use crate::cli::hosts::*;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: HostsCommands) -> Result<ExitCode, AppError> {
    match cmd {
        HostsCommands::List(_) => handle_list(),
        HostsCommands::Setup(_) => handle_setup(),
        HostsCommands::Restore(_) => handle_restore(),
    }
}

fn handle_list() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    let entries = db.with_conn(crate::db::hosts::list_host_entries)?;

    let items: Vec<serde_json::Value> = entries
        .iter()
        .map(|e| {
            serde_json::json!({
                "domain": e.domain,
                "ip": e.ip,
                "source_domain": e.source_domain,
                "added_at": e.added_at,
            })
        })
        .collect();

    let result = HostsResult {
        command: "hosts list",
        data: serde_json::json!({
            "entries": items,
            "count": items.len(),
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_setup() -> Result<ExitCode, AppError> {
    let data_dir = crate::common::platform::data_dir();
    let data_dir_str = data_dir.to_string_lossy();
    let sudoers_content = format!(
        "%admin ALL=(root) NOPASSWD: /bin/cp {data_dir_str}/hosts_tmp_* /etc/hosts\n\
         %admin ALL=(root) NOPASSWD: /usr/bin/dscacheutil -flushcache\n\
         %admin ALL=(root) NOPASSWD: /usr/bin/killall -HUP mDNSResponder\n"
    );
    let sudoers_path = "/etc/sudoers.d/ndb-hosts";

    // Write via sudo tee (interactive — will prompt for password once)
    let mut child = std::process::Command::new("sudo")
        .args(["tee", sudoers_path])
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::null())
        .spawn()
        .map_err(|e| AppError::General {
            message: format!("Failed to run sudo tee: {e}"),
            hint: Some("Ensure you have admin privileges".to_string()),
        })?;

    if let Some(ref mut stdin) = child.stdin {
        use std::io::Write;
        stdin.write_all(sudoers_content.as_bytes()).map_err(|e| AppError::General {
            message: format!("Failed to write sudoers: {e}"),
            hint: None,
        })?;
    }

    let status = child.wait().map_err(|e| AppError::General {
        message: format!("sudo tee failed: {e}"),
        hint: None,
    })?;

    if !status.success() {
        return Err(AppError::General {
            message: "Failed to write sudoers file".to_string(),
            hint: Some("Ensure you entered the correct password".to_string()),
        });
    }

    // Set correct permissions
    let chmod = std::process::Command::new("sudo")
        .args(["chmod", "0440", sudoers_path])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to chmod: {e}"),
            hint: None,
        })?;

    if !chmod.status.success() {
        return Err(AppError::General {
            message: "Failed to set sudoers permissions".to_string(),
            hint: None,
        });
    }

    let result = HostsResult {
        command: "hosts setup",
        data: serde_json::json!({
            "sudoers_path": sudoers_path,
            "configured": true,
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_restore() -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    let removed = crate::hosts_blocker::restore_all(&db)?;

    for domain in &removed {
        let _ = db.with_conn(|conn| {
            crate::db::audit::log_action(conn, "hosts_restore", "hosts", domain, None)
        });
    }

    let result = HostsResult {
        command: "hosts restore",
        data: serde_json::json!({
            "removed": removed,
            "count": removed.len(),
        }),
    };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct HostsResult {
    command: &'static str,
    data: serde_json::Value,
}
impl Renderable for HostsResult {
    fn command_name(&self) -> &str {
        self.command
    }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": self.data })
    }
}
