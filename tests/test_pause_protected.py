"""Tests for pause functionality and protected domains."""

from datetime import datetime, timedelta
from unittest.mock import patch

from nextdns_blocker.cli import get_pause_remaining, is_paused
from nextdns_blocker.config import get_protected_domains


class TestPauseFunctionality:
    """Tests for pause/resume functionality."""

    def test_is_paused_no_file(self, tmp_path):
        """Should return False when no pause file exists."""
        pause_file = tmp_path / ".paused"
        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            assert is_paused() is False

    def test_is_paused_active(self, tmp_path):
        """Should return True when pause is active."""
        pause_file = tmp_path / ".paused"
        future_time = datetime.now() + timedelta(minutes=30)
        pause_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            assert is_paused() is True

    def test_is_paused_expired(self, tmp_path):
        """Should return False and clean up when pause has expired."""
        pause_file = tmp_path / ".paused"
        past_time = datetime.now() - timedelta(minutes=5)
        pause_file.write_text(past_time.isoformat())

        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            assert is_paused() is False
            assert not pause_file.exists()

    def test_is_paused_invalid_content(self, tmp_path):
        """Should return False when pause file has invalid content."""
        pause_file = tmp_path / ".paused"
        pause_file.write_text("invalid_datetime")

        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            assert is_paused() is False

    def test_get_pause_remaining_no_file(self, tmp_path):
        """Should return None when no pause file exists."""
        pause_file = tmp_path / ".paused"
        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            assert get_pause_remaining() is None

    def test_get_pause_remaining_active(self, tmp_path):
        """Should return remaining time string when pause is active."""
        pause_file = tmp_path / ".paused"
        future_time = datetime.now() + timedelta(minutes=45)
        pause_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            remaining = get_pause_remaining()
            assert remaining is not None
            assert "min" in remaining

    def test_get_pause_remaining_less_than_minute(self, tmp_path):
        """Should return '< 1 min' when less than a minute remains."""
        pause_file = tmp_path / ".paused"
        future_time = datetime.now() + timedelta(seconds=30)
        pause_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            remaining = get_pause_remaining()
            assert remaining == "< 1 min"

    def test_get_pause_remaining_expired(self, tmp_path):
        """Should return None and clean up when pause has expired."""
        pause_file = tmp_path / ".paused"
        past_time = datetime.now() - timedelta(minutes=5)
        pause_file.write_text(past_time.isoformat())

        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            remaining = get_pause_remaining()
            assert remaining is None
            assert not pause_file.exists()


class TestProtectedDomains:
    """Tests for protected domain extraction."""

    def test_get_protected_domains_empty_list(self):
        """Should return empty list for empty input."""
        assert get_protected_domains([]) == []

    def test_get_protected_domains_no_protected(self):
        """Should return empty list when no domains are protected."""
        domains = [
            {"domain": "example.com", "schedule": None},
            {"domain": "test.com", "protected": False},
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
        domains = [{"domain": "no-field.com"}, {"domain": "explicit-true.com", "protected": True}]
        result = get_protected_domains(domains)
        assert result == ["explicit-true.com"]

    def test_get_protected_domains_false_value(self):
        """Should not include domains with protected=False."""
        domains = [
            {"domain": "false-protected.com", "protected": False},
            {"domain": "true-protected.com", "protected": True},
        ]
        result = get_protected_domains(domains)
        assert result == ["true-protected.com"]

    def test_get_protected_domains_preserves_order(self):
        """Should preserve order of protected domains."""
        domains = [
            {"domain": "first.com", "protected": True},
            {"domain": "skip.com", "protected": False},
            {"domain": "second.com", "protected": True},
            {"domain": "third.com", "protected": True},
        ]
        result = get_protected_domains(domains)
        assert result == ["first.com", "second.com", "third.com"]
