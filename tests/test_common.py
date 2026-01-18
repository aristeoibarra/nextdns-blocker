"""Tests for common utility functions."""

from nextdns_blocker.common import is_subdomain, validate_domain


class TestIsSubdomain:
    """Tests for is_subdomain function."""

    def test_valid_subdomain(self):
        """Test that direct subdomain is detected."""
        assert is_subdomain("aws.amazon.com", "amazon.com") is True

    def test_deep_subdomain(self):
        """Test that deep subdomains are detected."""
        assert is_subdomain("a.b.c.example.com", "example.com") is True

    def test_same_domain_not_subdomain(self):
        """Test that same domain is not considered a subdomain."""
        assert is_subdomain("amazon.com", "amazon.com") is False

    def test_unrelated_domains(self):
        """Test that unrelated domains return False."""
        assert is_subdomain("google.com", "amazon.com") is False

    def test_partial_match_not_subdomain(self):
        """Test that partial suffix match is not considered subdomain."""
        # 'notamazon.com' ends with 'amazon.com' but is not a subdomain
        assert is_subdomain("notamazon.com", "amazon.com") is False

    def test_case_insensitive(self):
        """Test that comparison is case insensitive."""
        assert is_subdomain("AWS.Amazon.COM", "amazon.com") is True
        assert is_subdomain("aws.amazon.com", "AMAZON.COM") is True

    def test_whitespace_handling(self):
        """Test that whitespace is stripped."""
        assert is_subdomain("  aws.amazon.com  ", "amazon.com") is True
        assert is_subdomain("aws.amazon.com", "  amazon.com  ") is True

    def test_empty_child(self):
        """Test that empty child returns False."""
        assert is_subdomain("", "amazon.com") is False

    def test_empty_parent(self):
        """Test that empty parent returns False."""
        assert is_subdomain("aws.amazon.com", "") is False

    def test_both_empty(self):
        """Test that both empty returns False."""
        assert is_subdomain("", "") is False

    def test_www_subdomain(self):
        """Test www subdomain detection."""
        assert is_subdomain("www.example.com", "example.com") is True

    def test_mail_subdomain(self):
        """Test mail subdomain detection."""
        assert is_subdomain("mail.google.com", "google.com") is True

    def test_nested_subdomain(self):
        """Test deeply nested subdomain."""
        assert is_subdomain("very.deep.nested.subdomain.example.org", "example.org") is True

    def test_tld_difference(self):
        """Test that different TLDs don't match."""
        assert is_subdomain("example.org", "example.com") is False
        assert is_subdomain("sub.example.org", "example.com") is False


class TestValidateDomain:
    """Tests for validate_domain function (existing tests may exist elsewhere)."""

    def test_valid_domain(self):
        """Test valid domain."""
        assert validate_domain("example.com") is True

    def test_valid_subdomain(self):
        """Test valid subdomain."""
        assert validate_domain("www.example.com") is True

    def test_invalid_domain_with_spaces(self):
        """Test invalid domain with spaces."""
        assert validate_domain("example .com") is False

    def test_empty_domain(self):
        """Test empty domain."""
        assert validate_domain("") is False

    def test_numeric_tld_rejected(self):
        """Test that numeric TLD is rejected (RFC 1123)."""
        assert validate_domain("example.123") is False

    def test_label_too_long(self):
        """Test that labels longer than 63 characters are rejected."""
        long_label = "a" * 64  # 64 characters, exceeds max of 63
        assert validate_domain(f"{long_label}.com") is False

    def test_label_at_max_length(self):
        """Test that labels at exactly 63 characters are valid."""
        max_label = "a" * 63  # Exactly 63 characters
        assert validate_domain(f"{max_label}.com") is True

    def test_wildcard_rejected_by_default(self):
        """Test that wildcard domains are rejected by default."""
        assert validate_domain("*.example.com") is False

    def test_wildcard_allowed_when_flag_set(self):
        """Test that wildcard domains are accepted when allow_wildcards=True."""
        assert validate_domain("*.example.com", allow_wildcards=True) is True

    def test_wildcard_needs_valid_domain(self):
        """Test that wildcard still validates the rest of the domain."""
        # Invalid because only one label after wildcard
        assert validate_domain("*.com", allow_wildcards=True) is False
        # Invalid because of spaces
        assert validate_domain("*.exa mple.com", allow_wildcards=True) is False

    def test_single_label_rejected(self):
        """Test that single-label domains are rejected (need at least domain.tld)."""
        assert validate_domain("localhost") is False

    def test_empty_label_rejected(self):
        """Test that empty labels (double dots) are rejected."""
        assert validate_domain("example..com") is False

    def test_leading_hyphen_rejected(self):
        """Test that labels starting with hyphen are rejected."""
        assert validate_domain("-example.com") is False

    def test_trailing_hyphen_rejected(self):
        """Test that labels ending with hyphen are rejected."""
        assert validate_domain("example-.com") is False
