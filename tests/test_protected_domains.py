"""Tests for protected domains functionality."""

from nextdns_blocker.config import get_protected_domains


class TestProtectedDomains:
    """Tests for protected domain extraction."""

    def test_get_protected_domains_empty_list(self):
        """Should return empty list for empty input."""
        assert get_protected_domains([]) == []

    def test_get_protected_domains_no_protected(self):
        """Should return empty list when no domains are protected."""
        domains = [
            {"domain": "example.com", "schedule": None},
            {"domain": "test.com"},
        ]
        assert get_protected_domains(domains) == []

    def test_get_protected_domains_single(self, protected_domain_config):
        """Should extract single protected domain."""
        result = get_protected_domains([protected_domain_config])
        assert result == ["protected.example.com"]

    def test_get_protected_domains_mixed(self, mixed_domains_config):
        """Should extract only protected domains from mixed list."""
        result = get_protected_domains(mixed_domains_config)
        assert len(result) == 2
        assert "protected1.com" in result
        assert "protected2.com" in result
        assert "normal.com" not in result
        assert "another.com" not in result

    def test_get_protected_domains_missing_field(self):
        """Should not include domains without protected field."""
        domains = [
            {"domain": "no-field.com"},
            {"domain": "explicit-true.com", "unblock_delay": "never"},
        ]
        result = get_protected_domains(domains)
        assert result == ["explicit-true.com"]

    def test_get_protected_domains_false_value(self):
        """Should not include domains with protected=False."""
        domains = [
            {"domain": "false-protected.com"},
            {"domain": "true-protected.com", "unblock_delay": "never"},
        ]
        result = get_protected_domains(domains)
        assert result == ["true-protected.com"]

    def test_get_protected_domains_preserves_order(self):
        """Should preserve order of protected domains."""
        domains = [
            {"domain": "first.com", "unblock_delay": "never"},
            {"domain": "skip.com"},
            {"domain": "second.com", "unblock_delay": "never"},
            {"domain": "third.com", "unblock_delay": "never"},
        ]
        result = get_protected_domains(domains)
        assert result == ["first.com", "second.com", "third.com"]
