"""Tests for configuration validation."""

import pytest

from nextdns_blocker import validate_domain_config


class TestValidateDomainConfig:
    """Tests for validate_domain_config function."""

    def test_valid_config(self, sample_domain_config):
        errors = validate_domain_config(sample_domain_config, 0)
        assert errors == []

    def test_valid_config_no_schedule(self):
        config = {"domain": "example.com"}
        errors = validate_domain_config(config, 0)
        assert errors == []

    def test_valid_config_null_schedule(self, always_blocked_config):
        errors = validate_domain_config(always_blocked_config, 0)
        assert errors == []

    def test_missing_domain(self):
        config = {"description": "No domain"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Missing domain" in errors[0]

    def test_empty_domain(self):
        config = {"domain": ""}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Empty domain" in errors[0]

    def test_whitespace_domain(self):
        config = {"domain": "   "}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Empty domain" in errors[0]

    def test_invalid_schedule_type(self):
        config = {"domain": "example.com", "schedule": "invalid"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "must be dict" in errors[0]

    def test_invalid_available_hours_type(self):
        config = {
            "domain": "example.com",
            "schedule": {"available_hours": "invalid"}
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "must be list" in errors[0]

    def test_invalid_day_name(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {"days": ["invalid_day"], "time_ranges": []}
                ]
            }
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "invalid day" in errors[0]

    def test_missing_time_range_start(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday"],
                        "time_ranges": [{"end": "17:00"}]
                    }
                ]
            }
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "missing 'start'" in errors[0]

    def test_missing_time_range_end(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday"],
                        "time_ranges": [{"start": "09:00"}]
                    }
                ]
            }
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "missing 'end'" in errors[0]

    def test_multiple_errors(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["invalid_day", "another_bad"],
                        "time_ranges": [{"start": "09:00"}]  # missing end
                    }
                ]
            }
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 3  # 2 invalid days + 1 missing end

    def test_case_insensitive_days(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["Monday", "TUESDAY"],
                        "time_ranges": [{"start": "09:00", "end": "17:00"}]
                    }
                ]
            }
        }
        errors = validate_domain_config(config, 0)
        assert errors == []

    def test_empty_schedule_dict(self):
        config = {"domain": "example.com", "schedule": {}}
        errors = validate_domain_config(config, 0)
        assert errors == []
