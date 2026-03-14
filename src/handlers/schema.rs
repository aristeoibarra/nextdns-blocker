use crate::cli::schema::*;
use crate::error::ExitCode;
use crate::output::{self, Renderable};

pub fn handle(cmd: SchemaCommands) -> Result<ExitCode, crate::error::AppError> {
    match cmd {
        SchemaCommands::ExitCodes(_) => { output::render(&ExitCodesOut); }
        SchemaCommands::Envelope(_) => { output::render(&EnvelopeOut); }
        SchemaCommands::Commands(_) => { output::render(&CommandsOut); }
        SchemaCommands::Output(args) => { output::render(&OutputOut(args.command.join(" "))); }
    }
    Ok(ExitCode::Success)
}

struct ExitCodesOut;
impl Renderable for ExitCodesOut {
    fn command_name(&self) -> &str { "schema exit-codes" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "exit_codes": [
            {"code": 0, "name": "success", "description": "Parse stdout JSON"},
            {"code": 1, "name": "general_error", "description": "Read error.hint, retry or fix"},
            {"code": 2, "name": "config_error", "description": "Run `ndb init` or `ndb config validate`"},
            {"code": 3, "name": "api_error", "description": "Retry after delay, check `ndb status`"},
            {"code": 4, "name": "validation_error", "description": "Fix input, don't retry same"},

            {"code": 6, "name": "conflict_error", "description": "Duplicate or protected item"},
            {"code": 7, "name": "not_found", "description": "Item doesn't exist"},
            {"code": 130, "name": "interrupted", "description": "SIGINT, state may be partial"},
        ]}})
    }
}

struct EnvelopeOut;
impl Renderable for EnvelopeOut {
    fn command_name(&self) -> &str { "schema envelope" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": {
            "success": { "ok": true, "command": "<cmd>", "data": {}, "summary": {}, "timestamp": "ISO8601" },
            "error": { "ok": false, "command": "<cmd>", "error": { "code": "", "message": "", "hint": "", "details": [] }, "exit_code": 0, "timestamp": "ISO8601" }
        }})
    }
}

struct CommandsOut;
impl Renderable for CommandsOut {
    fn command_name(&self) -> &str { "schema commands" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "commands": [
            "init", "status", "sync", "block", "unblock", "fix",
            "denylist add", "denylist remove", "denylist list", "denylist import", "denylist export",
            "allowlist add", "allowlist remove", "allowlist list", "allowlist import", "allowlist export",
            "category create", "category delete", "category list", "category show", "category add-domain", "category remove-domain",
            "nextdns list", "nextdns add-category", "nextdns remove-category", "nextdns categories",
            "config show", "config set", "config set-secret", "config remove-secret", "config validate",
            "apps list", "apps scan", "apps map", "apps unmap", "apps restore", "apps doctor",
            "audit list",
            "pending list", "pending show", "pending cancel",
            "watchdog install", "watchdog uninstall", "watchdog status", "watchdog run",
            "schema commands", "schema output", "schema exit-codes", "schema envelope",
        ]}})
    }
}

struct OutputOut(String);
impl Renderable for OutputOut {
    fn command_name(&self) -> &str { "schema output" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "command": self.0, "note": "All output is JSON envelope" } })
    }
}
