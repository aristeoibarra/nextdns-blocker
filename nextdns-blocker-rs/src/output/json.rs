use super::Renderable;

/// Wrap a successful Renderable output in the standard JSON envelope.
pub fn wrap_success(output: &dyn Renderable) -> serde_json::Value {
    let data = output.to_json();
    let mut envelope = serde_json::json!({
        "ok": true,
        "command": output.command_name(),
    });

    // Merge data fields into envelope
    if let serde_json::Value::Object(map) = data {
        let obj = envelope.as_object_mut().expect("envelope is object");
        for (k, v) in map {
            obj.insert(k, v);
        }
    } else {
        envelope["data"] = data;
    }

    envelope["timestamp"] =
        serde_json::Value::String(chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true));

    envelope
}

/// Write a progress message to stderr as NDJSON.
pub fn write_progress(command: &str, message: &str, progress: Option<f64>) {
    let mut val = serde_json::json!({
        "type": "progress",
        "command": command,
        "message": message,
    });
    if let Some(pct) = progress {
        val["progress"] = serde_json::json!(pct);
    }
    // Progress goes to stderr so stdout stays clean for the result
    eprintln!("{}", serde_json::to_string(&val).expect("JSON serialization failed"));
}
