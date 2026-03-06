use crate::cli::schema::*;
use crate::error::ExitCode;
use crate::output::{self, Renderable};
use crate::types::ResolvedFormat;

pub fn handle(cmd: SchemaCommands, format: ResolvedFormat) -> Result<ExitCode, crate::error::AppError> {
    match cmd {
        SchemaCommands::ExitCodes(_) => { output::render(&ExitCodesOut, format); }
        SchemaCommands::Envelope(_) => { output::render(&EnvelopeOut, format); }
        SchemaCommands::Commands(_) => { output::render(&CommandsOut, format); }
        SchemaCommands::Output(args) => { output::render(&OutputOut(args.command.join(" ")), format); }
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
            {"code": 5, "name": "permission_error", "description": "PIN required or file perms"},
            {"code": 6, "name": "conflict_error", "description": "Duplicate or protected item"},
            {"code": 7, "name": "not_found", "description": "Item doesn't exist"},
            {"code": 130, "name": "interrupted", "description": "SIGINT, state may be partial"},
        ]}})
    }
    fn to_human(&self) -> String { "Exit codes:\n  0  success\n  1  general_error\n  2  config_error\n  3  api_error\n  4  validation_error\n  5  permission_error\n  6  conflict_error\n  7  not_found\n  130 interrupted\n".to_string() }
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
    fn to_human(&self) -> String { "JSON envelope:\n  Success: { ok, command, data, summary, timestamp }\n  Error:   { ok, command, error: { code, message, hint, details }, exit_code, timestamp }\n".to_string() }
}

struct CommandsOut;
impl Renderable for CommandsOut {
    fn command_name(&self) -> &str { "schema commands" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "commands": [
            "init", "status", "sync", "unblock", "fix",
            "denylist add", "denylist remove", "denylist list", "denylist import", "denylist export",
            "allowlist add", "allowlist remove", "allowlist list", "allowlist import", "allowlist export",
            "category create", "category delete", "category list", "category show", "category add-domain", "category remove-domain",
            "nextdns list", "nextdns add-category", "nextdns remove-category", "nextdns add-service", "nextdns remove-service", "nextdns categories", "nextdns services",
            "config show", "config set", "config edit", "config validate", "config push", "config diff",
            "pending list", "pending show", "pending cancel",
            "protection status", "protection unlock-request", "protection cancel", "protection list",
            "protection pin-set", "protection pin-remove", "protection pin-status", "protection pin-verify",
            "watchdog install", "watchdog uninstall", "watchdog status", "watchdog run",
            "schema commands", "schema output", "schema exit-codes", "schema envelope",
            "completions",
        ]}})
    }
    fn to_human(&self) -> String { "Use 'ndb <command> --help' for details on any command.\n".to_string() }
}

struct OutputOut(String);
impl Renderable for OutputOut {
    fn command_name(&self) -> &str { "schema output" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({ "data": { "command": self.0, "note": "Use --output json on any command to see its schema" } })
    }
    fn to_human(&self) -> String { format!("Output schema for '{}': use --output json to see structured output\n", self.0) }
}
