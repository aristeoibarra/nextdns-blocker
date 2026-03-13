use crate::types::Domain;

/// Domains that must never be blocked (ndb needs API access to function).
pub const PROTECTED_DOMAINS: &[&str] = &["api.nextdns.io"];

/// Check whether a domain is protected from blocking.
pub fn is_protected(domain: &str) -> bool {
    PROTECTED_DOMAINS.contains(&domain)
}

/// Validate and parse a list of domain strings, returning valid domains and errors.
pub fn parse_domains(inputs: &[String]) -> (Vec<Domain>, Vec<(String, String)>) {
    let mut valid = Vec::new();
    let mut errors = Vec::new();

    for input in inputs {
        match Domain::new(input) {
            Ok(domain) => valid.push(domain),
            Err(e) => errors.push((input.clone(), e.to_string())),
        }
    }

    (valid, errors)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_domains() {
        let cases = [
            "example.com",
            "sub.example.com",
            "deep.sub.example.com",
            "UPPER.COM",
            "a-b.example.com",
            "123.example.com",
        ];
        for case in cases {
            assert!(Domain::new(case).is_ok(), "should be valid: {case}");
        }
    }

    #[test]
    fn invalid_domains() {
        let cases = [
            "",
            "localhost",
            ".example.com",
            "example.com.",
            "-bad.com",
            "bad-.com",
            "ex ample.com",
            "ex@mple.com",
        ];
        for case in cases {
            assert!(Domain::new(case).is_err(), "should be invalid: {case}");
        }
    }

    #[test]
    fn domain_normalized_to_lowercase() {
        let d = Domain::new("EXAMPLE.COM").unwrap();
        assert_eq!(d.as_str(), "example.com");
    }

    #[test]
    fn parse_domains_mixed() {
        let inputs = vec![
            "good.com".to_string(),
            "bad".to_string(),
            "also-good.org".to_string(),
        ];
        let (valid, errors) = parse_domains(&inputs);
        assert_eq!(valid.len(), 2);
        assert_eq!(errors.len(), 1);
        assert_eq!(errors[0].0, "bad");
    }
}
