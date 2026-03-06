use assert_cmd::Command;
use predicates::prelude::*;
use serde_json::Value;

fn ndb() -> Command {
    Command::cargo_bin("ndb").expect("binary 'ndb' not found")
}

// ---------------------------------------------------------------------------
// 1. version_flag
// ---------------------------------------------------------------------------
#[test]
fn version_flag() {
    ndb()
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::contains("ndb"));
}

// ---------------------------------------------------------------------------
// 2. help_flag
// ---------------------------------------------------------------------------
#[test]
fn help_flag() {
    ndb()
        .arg("--help")
        .assert()
        .success()
        .stdout(predicate::str::contains("NextDNS"))
        .stdout(predicate::str::contains("init"))
        .stdout(predicate::str::contains("sync"))
        .stdout(predicate::str::contains("schema"));
}

// ---------------------------------------------------------------------------
// 3. schema_exit_codes_json
// ---------------------------------------------------------------------------
#[test]
fn schema_exit_codes_json() {
    let output = ndb()
        .args(["schema", "exit-codes"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let json: Value = serde_json::from_slice(&output).expect("stdout is not valid JSON");

    assert_eq!(json["ok"], Value::Bool(true));

    let exit_codes = json["data"]["exit_codes"]
        .as_array()
        .expect("data.exit_codes should be an array");

    assert_eq!(exit_codes.len(), 9, "expected 9 exit codes");
}

// ---------------------------------------------------------------------------
// 4. schema_commands_json
// ---------------------------------------------------------------------------
#[test]
fn schema_commands_json() {
    let output = ndb()
        .args(["schema", "commands"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let json: Value = serde_json::from_slice(&output).expect("stdout is not valid JSON");

    json["data"]["commands"]
        .as_array()
        .expect("data.commands should be an array");
}

// ---------------------------------------------------------------------------
// 5. schema_envelope_json
// ---------------------------------------------------------------------------
#[test]
fn schema_envelope_json() {
    let output = ndb()
        .args(["schema", "envelope"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let json: Value = serde_json::from_slice(&output).expect("stdout is not valid JSON");

    assert!(
        json["data"]["success"].is_object(),
        "data.success should be an object"
    );
    assert!(
        json["data"]["error"].is_object(),
        "data.error should be an object"
    );
}

// ---------------------------------------------------------------------------
// 6. schema_output_json
// ---------------------------------------------------------------------------
#[test]
fn schema_output_json() {
    ndb()
        .args(["schema", "output", "sync"])
        .assert()
        .success();
}

// ---------------------------------------------------------------------------
// 7. init_creates_db
// ---------------------------------------------------------------------------
#[test]
fn init_creates_db() {
    let data_dir = tempfile::tempdir().expect("failed to create temp data dir");

    let output = ndb()
        .args(["init"])
        .env("NDB_DATA_DIR", data_dir.path())
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let json: Value = serde_json::from_slice(&output).expect("stdout is not valid JSON");
    assert_eq!(json["ok"], Value::Bool(true), "init should return ok: true");
    assert!(json["data"]["db_path"].is_string(), "should return db_path");
}

// ---------------------------------------------------------------------------
// 8. invalid_command
// ---------------------------------------------------------------------------
#[test]
fn invalid_command() {
    ndb()
        .arg("nonexistent")
        .assert()
        .failure();
}

// ---------------------------------------------------------------------------
// 9. denylist_help
// ---------------------------------------------------------------------------
#[test]
fn denylist_help() {
    ndb()
        .args(["denylist", "--help"])
        .assert()
        .success();
}

// ---------------------------------------------------------------------------
// 10. all_subcommands_have_help
// ---------------------------------------------------------------------------
#[test]
fn all_subcommands_have_help() {
    let subcommands = [
        "init",
        "status",
        "sync",
        "unblock",
        "fix",
        "denylist",
        "allowlist",
        "category",
        "nextdns",
        "config",
        "pending",
        "protection",
        "watchdog",
        "schema",
    ];

    for cmd in subcommands {
        ndb()
            .args([cmd, "--help"])
            .assert()
            .success()
            .stdout(predicate::str::is_empty().not());
    }
}

// ---------------------------------------------------------------------------
// 11. json_envelope_has_required_fields
// ---------------------------------------------------------------------------
#[test]
fn json_envelope_has_required_fields() {
    let output = ndb()
        .args(["schema", "exit-codes"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let json: Value = serde_json::from_slice(&output).expect("stdout is not valid JSON");
    let obj = json.as_object().expect("top-level should be an object");

    assert!(obj.contains_key("ok"), "envelope must contain 'ok'");
    assert!(obj.contains_key("command"), "envelope must contain 'command'");
    assert!(obj.contains_key("data"), "envelope must contain 'data'");
    assert!(
        obj.contains_key("timestamp"),
        "envelope must contain 'timestamp'"
    );
}

// ---------------------------------------------------------------------------
// 12. json_always_output (replaces human_output_format)
// ---------------------------------------------------------------------------
#[test]
fn json_always_output() {
    let output = ndb()
        .args(["schema", "exit-codes"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let json: Value = serde_json::from_slice(&output).expect("stdout should always be valid JSON");
    assert_eq!(json["ok"], Value::Bool(true));
}
