use std::process::Command;

/// Result of closing tabs in a single browser.
#[derive(Debug, serde::Serialize)]
pub struct BrowserCloseResult {
    pub browser: String,
    pub tabs_closed: u32,
}

/// Chromium-based browsers that support AppleScript tab control.
/// Firefox-based browsers (Zen) do not expose a scripting dictionary for tabs.
const CHROMIUM_BROWSERS: &[&str] = &["Google Chrome", "Brave Browser"];

/// Close browser tabs matching any of the given domains across all supported browsers.
/// Only Chromium-based browsers (Chrome, Brave) support tab-level AppleScript control.
/// Firefox-based browsers (Zen) rely on DNS/hosts blocking instead.
pub fn close_tabs_for_domains(domains: &[String]) -> Vec<BrowserCloseResult> {
    if domains.is_empty() {
        return Vec::new();
    }

    let mut results = Vec::new();

    for &browser in CHROMIUM_BROWSERS {
        if let Some(result) = close_chromium_tabs(browser, domains) {
            if result.tabs_closed > 0 {
                results.push(result);
            }
        }
    }

    results
}

/// Close tabs in a Chromium-based browser via AppleScript.
/// Checks if the browser is running first to avoid launching it.
/// Iterates tabs in reverse to avoid index shifting when closing.
fn close_chromium_tabs(app_name: &str, domains: &[String]) -> Option<BrowserCloseResult> {
    let conditions = domain_match_conditions(domains);
    let app = escape(app_name);

    let script = format!(
        r#"if application "{app}" is running then
    tell application "{app}"
        set closedCount to 0
        repeat with w in windows
            set tabCount to count of tabs of w
            repeat with i from tabCount to 1 by -1
                set theURL to URL of tab i of w
                if ({conditions}) then
                    close tab i of w
                    set closedCount to closedCount + 1
                end if
            end repeat
        end repeat
        return closedCount
    end tell
else
    return 0
end if"#
    );

    let output = Command::new("osascript")
        .args(["-e", &script])
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let tabs_closed = String::from_utf8_lossy(&output.stdout)
        .trim()
        .parse::<u32>()
        .unwrap_or(0);

    Some(BrowserCloseResult {
        browser: app_name.to_string(),
        tabs_closed,
    })
}

/// Build AppleScript conditions that match URLs containing any of the given domains.
/// Matches both exact domain (`://domain`) and subdomains (`.domain`).
fn domain_match_conditions(domains: &[String]) -> String {
    domains
        .iter()
        .flat_map(|d| {
            let e = escape(d);
            [
                format!("theURL contains \"://{e}\""),
                format!("theURL contains \".{e}\""),
            ]
        })
        .collect::<Vec<_>>()
        .join(" or ")
}

/// Escape a string for safe inclusion in AppleScript double-quoted strings.
fn escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            c if c.is_control() => {}
            _ => out.push(c),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_domain_match_conditions_single() {
        let conditions = domain_match_conditions(&["youtube.com".to_string()]);
        assert!(conditions.contains("://youtube.com"));
        assert!(conditions.contains(".youtube.com"));
    }

    #[test]
    fn test_domain_match_conditions_multiple() {
        let domains = vec!["youtube.com".to_string(), "twitter.com".to_string()];
        let conditions = domain_match_conditions(&domains);
        assert!(conditions.contains("://youtube.com"));
        assert!(conditions.contains(".youtube.com"));
        assert!(conditions.contains("://twitter.com"));
        assert!(conditions.contains(".twitter.com"));
        assert!(conditions.contains(" or "));
    }

    #[test]
    fn test_escape_safe_strings() {
        assert_eq!(escape("Google Chrome"), "Google Chrome");
        assert_eq!(escape("youtube.com"), "youtube.com");
    }

    #[test]
    fn test_escape_special_chars() {
        assert_eq!(escape(r#"te"st"#), r#"te\"st"#);
        assert_eq!(escape(r"te\st"), r"te\\st");
    }

    #[test]
    fn test_escape_strips_control_chars() {
        assert_eq!(escape("ab\x00cd"), "abcd");
        assert_eq!(escape("ab\ncd"), "abcd");
    }

    #[test]
    fn test_empty_domains() {
        let result = close_tabs_for_domains(&[]);
        assert!(result.is_empty());
    }
}
