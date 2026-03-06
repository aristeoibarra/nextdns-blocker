//! Spec-driven contract tests.
//!
//! Reads TOML spec files from `specs/` and auto-generates contract tests that
//! verify the binary's behavior matches the declared contracts.

#![allow(deprecated, dead_code)]

use assert_cmd::Command;
use serde::Deserialize;
use serde_json::Value;
use std::collections::HashSet;
use std::path::{Path, PathBuf};

// ---------------------------------------------------------------------------
// Spec types (mirrors the TOML structure)
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct CommandSpec {
    command: CommandMeta,
    #[serde(default)]
    args: Vec<ArgSpec>,
    #[serde(default)]
    flags: Vec<FlagSpec>,
    output: OutputSpec,
    exit_codes: Vec<ExitCodeRef>,
    #[serde(default)]
    side_effects: Vec<SideEffect>,
    #[serde(default)]
    examples: Vec<Example>,
}

#[derive(Debug, Deserialize)]
struct CommandMeta {
    name: String,
    binary_path: Vec<String>,
    description: String,
    requires_config: bool,
    requires_api: bool,
    requires_pin: bool,
}

#[derive(Debug, Deserialize)]
struct ArgSpec {
    name: String,
    #[serde(rename = "type")]
    arg_type: String,
    required: bool,
    #[serde(default)]
    validation: Option<String>,
}

#[derive(Debug, Deserialize)]
struct FlagSpec {
    name: String,
    #[serde(rename = "type")]
    flag_type: String,
    required: bool,
    #[serde(default)]
    short: Option<String>,
    #[serde(default)]
    description: Option<String>,
}

#[derive(Debug, Deserialize)]
struct OutputSpec {
    success: SchemaRef,
    #[serde(default)]
    error: Option<SchemaRef>,
}

#[derive(Debug, Deserialize)]
struct SchemaRef {
    schema: String,
}

#[derive(Debug, Deserialize)]
struct ExitCodeRef {
    code: u8,
    name: String,
}

#[derive(Debug, Deserialize)]
struct SideEffect {
    target: String,
    operation: String,
}

#[derive(Debug, Deserialize)]
struct Example {
    description: String,
    input: String,
    exit_code: u8,
}

// Global exit codes spec
#[derive(Debug, Deserialize)]
struct GlobalExitCodes {
    exit_codes: Vec<GlobalExitCode>,
}

#[derive(Debug, Deserialize)]
struct GlobalExitCode {
    code: u8,
    name: String,
    description: String,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn specs_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("specs")
}

fn load_command_specs() -> Vec<(PathBuf, CommandSpec)> {
    let commands_dir = specs_dir().join("commands");
    let mut specs = Vec::new();
    collect_spec_files(&commands_dir, &mut specs);
    specs
}

fn collect_spec_files(dir: &Path, specs: &mut Vec<(PathBuf, CommandSpec)>) {
    if !dir.exists() {
        return;
    }
    let mut entries: Vec<_> = std::fs::read_dir(dir)
        .expect("cannot read specs dir")
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.path());

    for entry in entries {
        let path = entry.path();
        if path.is_dir() {
            collect_spec_files(&path, specs);
        } else if path.extension().is_some_and(|ext| ext == "toml") {
            let content = std::fs::read_to_string(&path)
                .unwrap_or_else(|e| panic!("cannot read {}: {e}", path.display()));
            // Skip meta-schema files (specs/commands/schema/commands.toml has [schema] not [command])
            if content.contains("[command]") {
                match toml::from_str::<CommandSpec>(&content) {
                    Ok(spec) => specs.push((path, spec)),
                    Err(e) => panic!("invalid spec {}: {e}", path.display()),
                }
            }
        }
    }
}

fn load_global_exit_codes() -> Vec<GlobalExitCode> {
    let path = specs_dir().join("exit_codes.toml");
    let content = std::fs::read_to_string(&path).expect("cannot read exit_codes.toml");
    let codes: GlobalExitCodes = toml::from_str(&content).expect("invalid exit_codes.toml");
    codes.exit_codes
}

fn ndb() -> Command {
    assert_cmd::cargo::cargo_bin_cmd!("ndb")
}

fn extract_json_keys(schema_json: &str) -> HashSet<String> {
    // Parse the example schema JSON and extract top-level keys
    if let Ok(val) = serde_json::from_str::<Value>(schema_json) {
        if let Some(obj) = val.as_object() {
            return obj.keys().cloned().collect();
        }
    }
    HashSet::new()
}

fn extract_data_keys(schema_json: &str) -> HashSet<String> {
    if let Ok(val) = serde_json::from_str::<Value>(schema_json) {
        if let Some(data) = val.get("data").and_then(|d| d.as_object()) {
            return data.keys().cloned().collect();
        }
    }
    HashSet::new()
}

// ---------------------------------------------------------------------------
// Contract test 1: All spec files parse correctly
// ---------------------------------------------------------------------------
#[test]
fn all_specs_parse_successfully() {
    let specs = load_command_specs();
    assert!(
        specs.len() >= 35,
        "Expected at least 35 command specs, found {}",
        specs.len()
    );
    for (path, spec) in &specs {
        assert!(
            !spec.command.name.is_empty(),
            "Spec {} has empty command name",
            path.display()
        );
        assert!(
            !spec.command.binary_path.is_empty(),
            "Spec {} has empty binary_path",
            path.display()
        );
        assert!(
            !spec.command.description.is_empty(),
            "Spec {} has empty description",
            path.display()
        );
        assert!(
            !spec.exit_codes.is_empty(),
            "Spec {} has no exit_codes",
            path.display()
        );
    }
}

// ---------------------------------------------------------------------------
// Contract test 2: Every spec has valid exit codes (subset of global)
// ---------------------------------------------------------------------------
#[test]
fn spec_exit_codes_match_global() {
    let global = load_global_exit_codes();
    let valid_codes: HashSet<u8> = global.iter().map(|c| c.code).collect();
    let valid_names: HashSet<&str> = global.iter().map(|c| c.name.as_str()).collect();

    for (path, spec) in load_command_specs() {
        for ec in &spec.exit_codes {
            assert!(
                valid_codes.contains(&ec.code),
                "Spec {} declares exit code {} which is not in global exit_codes.toml",
                path.display(),
                ec.code
            );
            assert!(
                valid_names.contains(ec.name.as_str()),
                "Spec {} declares exit code name '{}' which is not in global exit_codes.toml",
                path.display(),
                ec.name
            );
        }
    }
}

// ---------------------------------------------------------------------------
// Contract test 3: All commands appear in `ndb schema commands`
// ---------------------------------------------------------------------------
#[test]
fn schema_commands_lists_all_specs() {
    let output = ndb()
        .args(["schema", "commands"])
        .output()
        .expect("failed to run ndb schema commands");

    let json: Value =
        serde_json::from_slice(&output.stdout).expect("schema commands output is not valid JSON");

    let commands = json["data"]["commands"]
        .as_array()
        .expect("data.commands should be an array");

    let listed: HashSet<String> = commands
        .iter()
        .filter_map(|v| v.as_str().map(String::from))
        .collect();

    for (path, spec) in load_command_specs() {
        assert!(
            listed.contains(&spec.command.name),
            "Command '{}' (from {}) is not listed in `ndb schema commands`",
            spec.command.name,
            path.display()
        );
    }
}

// ---------------------------------------------------------------------------
// Contract test 4: All commands accept --help
// ---------------------------------------------------------------------------
#[test]
fn all_spec_commands_accept_help() {
    for (_path, spec) in load_command_specs() {
        let mut cmd = ndb();
        for seg in &spec.command.binary_path {
            cmd.arg(seg);
        }
        cmd.arg("--help");
        cmd.assert().success();
    }
}

// ---------------------------------------------------------------------------
// Contract test 5: Commands that don't require config/api/pin produce valid
// JSON envelope (always JSON output)
// ---------------------------------------------------------------------------
#[test]
fn standalone_commands_produce_valid_envelope() {
    // Commands that can run without config, API, or PIN and don't need args
    let specs = load_command_specs();
    let standalone: Vec<_> = specs
        .iter()
        .filter(|(_, s)| {
            !s.command.requires_config
                && !s.command.requires_api
                && !s.command.requires_pin
                && s.args.iter().all(|a| !a.required)
        })
        .collect();

    assert!(
        !standalone.is_empty(),
        "Should have at least some standalone commands"
    );

    // Set up isolated dirs so commands don't interfere with real config
    let data_dir = tempfile::tempdir().expect("tempdir");

    // First init so status/fix etc. have a DB
    ndb()
        .args(["init"])
        .env("NDB_DATA_DIR", data_dir.path())
        .output()
        .ok();

    for (_path, spec) in &standalone {
        let mut cmd = ndb();
        cmd.env("NDB_DATA_DIR", data_dir.path());

        for seg in &spec.command.binary_path {
            cmd.arg(seg);
        }
        // JSON is always the output format

        let output = cmd.output().expect("failed to run command");

        // We only check stdout for JSON if the command succeeded
        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let json: Value = serde_json::from_str(&stdout).unwrap_or_else(|e| {
                panic!(
                    "Command '{}' produced invalid JSON: {e}\nstdout: {stdout}",
                    spec.command.name
                )
            });

            // Verify envelope fields
            assert_eq!(
                json["ok"],
                Value::Bool(true),
                "Command '{}' should have ok: true",
                spec.command.name
            );
            assert!(
                json["timestamp"].is_string(),
                "Command '{}' should have timestamp",
                spec.command.name
            );
            assert_eq!(
                json["command"].as_str().unwrap_or(""),
                spec.command.name,
                "Command '{}' should report correct command name",
                spec.command.name
            );
        }
    }
}

// ---------------------------------------------------------------------------
// Contract test 6: Success output schema has expected data keys
// ---------------------------------------------------------------------------
#[test]
fn success_schema_declares_data_keys() {
    for (path, spec) in load_command_specs() {
        let keys = extract_json_keys(&spec.output.success.schema);
        // The success schema should at minimum have "ok", "command", "data"
        if !keys.is_empty() {
            assert!(
                keys.contains("ok"),
                "Spec {} success schema missing 'ok' field",
                path.display()
            );
            assert!(
                keys.contains("command"),
                "Spec {} success schema missing 'command' field",
                path.display()
            );
            assert!(
                keys.contains("data"),
                "Spec {} success schema missing 'data' field",
                path.display()
            );
        }
    }
}

// ---------------------------------------------------------------------------
// Contract test 7: Error output schema has expected error keys
// ---------------------------------------------------------------------------
#[test]
fn error_schema_declares_error_keys() {
    for (path, spec) in load_command_specs() {
        if let Some(error_schema) = &spec.output.error {
            let keys = extract_json_keys(&error_schema.schema);
            if !keys.is_empty() {
                assert!(
                    keys.contains("ok"),
                    "Spec {} error schema missing 'ok' field",
                    path.display()
                );
                assert!(
                    keys.contains("error"),
                    "Spec {} error schema missing 'error' field",
                    path.display()
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Contract test 8: Standalone command data keys match spec schema
// ---------------------------------------------------------------------------
#[test]
fn standalone_command_data_keys_match_spec() {
    let specs = load_command_specs();
    let standalone: Vec<_> = specs
        .iter()
        .filter(|(_, s)| {
            !s.command.requires_config
                && !s.command.requires_api
                && !s.command.requires_pin
                && s.args.iter().all(|a| !a.required)
        })
        .collect();

    let data_dir = tempfile::tempdir().expect("tempdir");

    ndb()
        .args(["init"])
        .env("NDB_DATA_DIR", data_dir.path())
        .output()
        .ok();

    for (_path, spec) in &standalone {
        let expected_keys = extract_data_keys(&spec.output.success.schema);
        if expected_keys.is_empty() {
            continue;
        }

        let mut cmd = ndb();
        cmd.env("NDB_DATA_DIR", data_dir.path());

        for seg in &spec.command.binary_path {
            cmd.arg(seg);
        }
        // JSON is always the output format

        let output = cmd.output().expect("failed to run");
        if !output.status.success() {
            continue;
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        let json: Value = match serde_json::from_str(&stdout) {
            Ok(v) => v,
            Err(_) => continue,
        };

        if let Some(data) = json.get("data").and_then(|d| d.as_object()) {
            let actual_keys: HashSet<String> = data.keys().cloned().collect();
            for key in &expected_keys {
                assert!(
                    actual_keys.contains(key),
                    "Command '{}' data missing key '{}' declared in spec. Actual keys: {:?}",
                    spec.command.name,
                    key,
                    actual_keys
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Contract test 9: All exit code 0 examples work for standalone commands
// ---------------------------------------------------------------------------
#[test]
fn spec_examples_exit_code_zero_work() {
    let specs = load_command_specs();
    let standalone: Vec<_> = specs
        .iter()
        .filter(|(_, s)| {
            !s.command.requires_config
                && !s.command.requires_api
                && !s.command.requires_pin
        })
        .collect();

    let data_dir = tempfile::tempdir().expect("tempdir");

    ndb()
        .args(["init"])
        .env("NDB_DATA_DIR", data_dir.path())
        .output()
        .ok();

    for (_, spec) in &standalone {
        for example in &spec.examples {
            if example.exit_code != 0 {
                continue;
            }

            // Parse the example input: "ndb category list" -> ["category", "list"]
            let parts: Vec<&str> = example.input.split_whitespace().collect();
            if parts.is_empty() || parts[0] != "ndb" {
                continue;
            }
            let args = &parts[1..];

            // Skip examples that have quoted args or complex flags
            // (we can't reliably parse shell quoting here)
            if example.input.contains('\'') || example.input.contains('"') {
                continue;
            }

            // Skip examples that need file paths or specific data
            if args.iter().any(|a| a.contains('/') || a.contains('.')) {
                // Might be a domain arg — skip if command requires input we can't provide
                if spec.args.iter().any(|a| a.required) {
                    continue;
                }
            }

            let mut cmd = ndb();
            cmd.env("NDB_DATA_DIR", data_dir.path());

            for arg in args {
                cmd.arg(arg);
            }
            // JSON is always the output format

            let output = cmd.output().expect("failed to run example");
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                // If it produced output, it should be valid JSON
                if !stdout.trim().is_empty() {
                    assert!(
                        serde_json::from_str::<Value>(&stdout).is_ok(),
                        "Example '{}' for command '{}' produced invalid JSON: {}",
                        example.description,
                        spec.command.name,
                        stdout
                    );
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Contract test 10: Spec coverage — every command in ndb schema commands
//                   has a TOML spec file
// ---------------------------------------------------------------------------
#[test]
fn every_listed_command_has_spec() {
    let output = ndb()
        .args(["schema", "commands"])
        .output()
        .expect("failed to run ndb schema commands");

    let json: Value =
        serde_json::from_slice(&output.stdout).expect("schema commands is not valid JSON");

    let commands = json["data"]["commands"]
        .as_array()
        .expect("data.commands should be an array");

    let spec_names: HashSet<String> = load_command_specs()
        .iter()
        .map(|(_, s)| s.command.name.clone())
        .collect();

    for cmd_val in commands {
        let cmd_name = cmd_val.as_str().unwrap_or("");
        assert!(
            spec_names.contains(cmd_name),
            "Command '{}' is listed in `ndb schema commands` but has no TOML spec file",
            cmd_name
        );
    }
}

// ---------------------------------------------------------------------------
// Contract test 11: Validate global exit codes spec matches binary output
// ---------------------------------------------------------------------------
#[test]
fn global_exit_codes_match_binary() {
    let output = ndb()
        .args(["schema", "exit-codes"])
        .output()
        .expect("failed to run ndb schema exit-codes");

    let json: Value = serde_json::from_slice(&output.stdout).expect("not valid JSON");

    let binary_codes: HashSet<u8> = json["data"]["exit_codes"]
        .as_array()
        .expect("exit_codes array")
        .iter()
        .filter_map(|v| v["code"].as_u64().map(|c| c as u8))
        .collect();

    let spec_codes = load_global_exit_codes();
    let spec_code_set: HashSet<u8> = spec_codes.iter().map(|c| c.code).collect();

    assert_eq!(
        binary_codes, spec_code_set,
        "Exit codes from binary don't match exit_codes.toml spec.\nBinary: {:?}\nSpec: {:?}",
        binary_codes, spec_code_set
    );
}

// ---------------------------------------------------------------------------
// Contract test 12: Flag names in specs correspond to actual CLI flags
// ---------------------------------------------------------------------------
#[test]
fn spec_flags_accepted_by_binary() {
    let specs = load_command_specs();

    for (path, spec) in &specs {
        // Run --help and check that each flag appears in the help output
        let mut cmd = ndb();
        for seg in &spec.command.binary_path {
            cmd.arg(seg);
        }
        cmd.arg("--help");

        let output = cmd.output().expect("--help failed");
        let help_text = String::from_utf8_lossy(&output.stdout);

        for flag in &spec.flags {
            // Extract the long flag name: "--force" -> "force"
            let flag_name = flag.name.trim_start_matches('-');
            assert!(
                help_text.contains(flag_name),
                "Spec {} declares flag '{}' but it doesn't appear in --help output:\n{}",
                path.display(),
                flag.name,
                help_text
            );
        }
    }
}
