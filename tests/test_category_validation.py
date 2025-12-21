"""Tests for category validation functions."""

import pytest

from nextdns_blocker.common import validate_category_id
from nextdns_blocker.config import (
    parse_duration,
    validate_category_config,
    validate_no_duplicate_domains,
    validate_unblock_delay,
    validate_unique_category_ids,
)


class TestValidateCategoryId:
    """Tests for validate_category_id function."""

    def test_valid_simple_id(self):
        """Test valid simple category ID."""
        assert validate_category_id("social") is True

    def test_valid_id_with_numbers(self):
        """Test valid ID with numbers."""
        assert validate_category_id("social2") is True

    def test_valid_id_with_hyphens(self):
        """Test valid ID with hyphens."""
        assert validate_category_id("social-media") is True

    def test_valid_id_complex(self):
        """Test valid complex ID."""
        assert validate_category_id("my-category-123") is True

    def test_invalid_id_empty(self):
        """Test empty ID is rejected."""
        assert validate_category_id("") is False

    def test_invalid_id_none(self):
        """Test None ID is rejected."""
        assert validate_category_id(None) is False  # type: ignore

    def test_invalid_id_uppercase(self):
        """Test uppercase ID is rejected."""
        assert validate_category_id("Social") is False
        assert validate_category_id("SOCIAL") is False

    def test_invalid_id_starts_with_number(self):
        """Test ID starting with number is rejected."""
        assert validate_category_id("123social") is False

    def test_invalid_id_starts_with_hyphen(self):
        """Test ID starting with hyphen is rejected."""
        assert validate_category_id("-social") is False

    def test_invalid_id_special_chars(self):
        """Test ID with special characters is rejected."""
        assert validate_category_id("social@media") is False
        assert validate_category_id("social_media") is False
        assert validate_category_id("social.media") is False

    def test_invalid_id_spaces(self):
        """Test ID with spaces is rejected."""
        assert validate_category_id("social media") is False

    def test_valid_id_max_length(self):
        """Test ID at max length (50 chars)."""
        assert validate_category_id("a" * 50) is True

    def test_invalid_id_too_long(self):
        """Test ID over max length is rejected."""
        assert validate_category_id("a" * 51) is False


class TestParseDuration:
    """Tests for parse_duration function (flexible duration parser)."""

    def test_never(self):
        """Test 'never' returns None."""
        assert parse_duration("never") is None

    def test_zero(self):
        """Test '0' returns 0."""
        assert parse_duration("0") == 0

    def test_minutes(self):
        """Test minute durations."""
        assert parse_duration("30m") == 1800
        assert parse_duration("45m") == 2700
        assert parse_duration("90m") == 5400

    def test_hours(self):
        """Test hour durations."""
        assert parse_duration("1h") == 3600
        assert parse_duration("2h") == 7200
        assert parse_duration("4h") == 14400
        assert parse_duration("24h") == 86400

    def test_days(self):
        """Test day durations."""
        assert parse_duration("1d") == 86400
        assert parse_duration("7d") == 604800

    def test_case_insensitive(self):
        """Test duration parsing is case-insensitive."""
        assert parse_duration("NEVER") is None
        assert parse_duration("30M") == 1800
        assert parse_duration("2H") == 7200

    def test_whitespace_handling(self):
        """Test whitespace is stripped."""
        assert parse_duration("  30m  ") == 1800
        assert parse_duration(" never ") is None

    def test_zero_with_unit(self):
        """Test 0 with unit returns 0."""
        assert parse_duration("0m") == 0
        assert parse_duration("0h") == 0
        assert parse_duration("0d") == 0

    def test_invalid_format(self):
        """Test invalid formats raise ValueError."""
        with pytest.raises(ValueError):
            parse_duration("invalid")
        with pytest.raises(ValueError):
            parse_duration("30")
        with pytest.raises(ValueError):
            parse_duration("30x")
        with pytest.raises(ValueError):
            parse_duration("m30")

    def test_invalid_empty(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration("")

    def test_invalid_none(self):
        """Test None raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration(None)  # type: ignore


class TestValidateUnblockDelay:
    """Tests for validate_unblock_delay with flexible duration."""

    def test_valid_never(self):
        """Test 'never' is valid."""
        assert validate_unblock_delay("never") is True

    def test_valid_zero(self):
        """Test '0' is valid."""
        assert validate_unblock_delay("0") is True

    def test_valid_legacy_values(self):
        """Test legacy values still work."""
        assert validate_unblock_delay("24h") is True
        assert validate_unblock_delay("4h") is True
        assert validate_unblock_delay("30m") is True

    def test_valid_new_values(self):
        """Test new flexible values work."""
        assert validate_unblock_delay("1h") is True
        assert validate_unblock_delay("2h") is True
        assert validate_unblock_delay("45m") is True
        assert validate_unblock_delay("1d") is True

    def test_invalid_format(self):
        """Test invalid formats return False."""
        assert validate_unblock_delay("invalid") is False
        assert validate_unblock_delay("30") is False
        assert validate_unblock_delay("30x") is False

    def test_invalid_empty(self):
        """Test empty string is invalid."""
        assert validate_unblock_delay("") is False

    def test_invalid_none(self):
        """Test None is invalid."""
        assert validate_unblock_delay(None) is False  # type: ignore


class TestValidateCategoryConfig:
    """Tests for validate_category_config function."""

    def test_valid_minimal_category(self):
        """Test valid minimal category config."""
        config = {
            "id": "social",
            "domains": ["facebook.com"],
        }
        errors = validate_category_config(config, 0)
        assert errors == []

    def test_valid_full_category(self):
        """Test valid category with all fields."""
        config = {
            "id": "social-media",
            "description": "Social networks",
            "unblock_delay": "4h",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday", "friday"],
                        "time_ranges": [{"start": "18:00", "end": "22:00"}],
                    }
                ]
            },
            "domains": ["facebook.com", "twitter.com"],
        }
        errors = validate_category_config(config, 0)
        assert errors == []

    def test_missing_id(self):
        """Test missing id field."""
        config = {"domains": ["facebook.com"]}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "Missing 'id'" in errors[0]

    def test_empty_id(self):
        """Test empty id."""
        config = {"id": "", "domains": ["facebook.com"]}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "Empty or invalid id" in errors[0]

    def test_invalid_id_format(self):
        """Test invalid id format."""
        config = {"id": "Social-Media", "domains": ["facebook.com"]}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "Invalid id format" in errors[0]

    def test_missing_domains(self):
        """Test missing domains field."""
        config = {"id": "social"}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "Missing 'domains'" in errors[0]

    def test_empty_domains(self):
        """Test empty domains array."""
        config = {"id": "social", "domains": []}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]

    def test_invalid_domains_type(self):
        """Test domains not an array."""
        config = {"id": "social", "domains": "facebook.com"}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "must be an array" in errors[0]

    def test_invalid_domain_in_list(self):
        """Test invalid domain format in list."""
        config = {"id": "social", "domains": ["facebook.com", "invalid domain!"]}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "invalid domain format" in errors[0]

    def test_non_string_domain(self):
        """Test non-string domain in list."""
        config = {"id": "social", "domains": ["facebook.com", 123]}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "must be a string" in errors[0]

    def test_invalid_description_type(self):
        """Test non-string description."""
        config = {"id": "social", "domains": ["facebook.com"], "description": 123}
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "'description' must be a string" in errors[0]

    def test_invalid_unblock_delay(self):
        """Test invalid unblock_delay value."""
        config = {
            "id": "social",
            "domains": ["facebook.com"],
            "unblock_delay": "invalid",
        }
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "invalid unblock_delay" in errors[0]

    def test_flexible_unblock_delay(self):
        """Test flexible unblock_delay values are accepted."""
        for delay in ["1h", "45m", "2d", "never", "0"]:
            config = {
                "id": "social",
                "domains": ["facebook.com"],
                "unblock_delay": delay,
            }
            errors = validate_category_config(config, 0)
            assert errors == [], f"Failed for delay: {delay}"

    def test_invalid_schedule(self):
        """Test invalid schedule structure."""
        config = {
            "id": "social",
            "domains": ["facebook.com"],
            "schedule": "not a dict",
        }
        errors = validate_category_config(config, 0)
        assert len(errors) == 1
        assert "schedule must be a dictionary" in errors[0]

    def test_null_schedule_allowed(self):
        """Test null schedule is allowed (means always blocked)."""
        config = {
            "id": "social",
            "domains": ["facebook.com"],
            "schedule": None,
        }
        errors = validate_category_config(config, 0)
        # schedule=None means no schedule validation, so it's treated as "always blocked"
        # The validation should not error on None schedule
        # Looking at the code, schedule is only validated if it's not None
        assert errors == []


class TestValidateNoDuplicateDomains:
    """Tests for validate_no_duplicate_domains function."""

    def test_no_duplicates(self):
        """Test no duplicates returns empty list."""
        categories = [
            {"id": "social", "domains": ["facebook.com", "twitter.com"]},
            {"id": "streaming", "domains": ["netflix.com", "youtube.com"]},
        ]
        blocklist = [{"domain": "example.com"}]
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert errors == []

    def test_duplicate_in_categories(self):
        """Test duplicate across categories is detected."""
        categories = [
            {"id": "social", "domains": ["facebook.com", "twitter.com"]},
            {"id": "other", "domains": ["facebook.com", "instagram.com"]},
        ]
        blocklist = []
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert len(errors) == 1
        assert "facebook.com" in errors[0]
        assert "multiple locations" in errors[0]

    def test_duplicate_category_and_blocklist(self):
        """Test duplicate in category and blocklist is detected."""
        categories = [
            {"id": "social", "domains": ["facebook.com"]},
        ]
        blocklist = [{"domain": "facebook.com"}]
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert len(errors) == 1
        assert "facebook.com" in errors[0]

    def test_case_insensitive(self):
        """Test duplicate detection is case-insensitive."""
        categories = [
            {"id": "social", "domains": ["Facebook.com"]},
            {"id": "other", "domains": ["FACEBOOK.COM"]},
        ]
        blocklist = []
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert len(errors) == 1

    def test_empty_categories(self):
        """Test empty categories returns no errors."""
        errors = validate_no_duplicate_domains([], [])
        assert errors == []


class TestValidateUniqueCategoryIds:
    """Tests for validate_unique_category_ids function."""

    def test_unique_ids(self):
        """Test unique IDs returns empty list."""
        categories = [
            {"id": "social"},
            {"id": "streaming"},
            {"id": "gambling"},
        ]
        errors = validate_unique_category_ids(categories)
        assert errors == []

    def test_duplicate_ids(self):
        """Test duplicate IDs are detected."""
        categories = [
            {"id": "social"},
            {"id": "streaming"},
            {"id": "social"},
        ]
        errors = validate_unique_category_ids(categories)
        assert len(errors) == 1
        assert "Duplicate id 'social'" in errors[0]

    def test_case_insensitive(self):
        """Test duplicate detection is case-insensitive."""
        categories = [
            {"id": "social"},
            {"id": "SOCIAL"},
        ]
        errors = validate_unique_category_ids(categories)
        assert len(errors) == 1

    def test_empty_categories(self):
        """Test empty categories returns no errors."""
        errors = validate_unique_category_ids([])
        assert errors == []

    def test_missing_id_field(self):
        """Test categories without id field are skipped."""
        categories = [
            {"id": "social"},
            {"name": "no-id"},
            {"id": "streaming"},
        ]
        errors = validate_unique_category_ids(categories)
        assert errors == []


class TestCategorySubdomainWarnings:
    """Tests for check_category_subdomain_relationships function."""

    def test_no_subdomain_relationship(self, caplog):
        """Test no warning when no subdomain relationship exists."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        categories = [{"id": "social", "domains": ["facebook.com", "twitter.com"]}]
        allowlist = [{"domain": "google.com"}]

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships(categories, allowlist)

        assert "Subdomain relationship" not in caplog.text

    def test_subdomain_warning_logged(self, caplog):
        """Test warning is logged for subdomain relationship."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        categories = [{"id": "shopping", "domains": ["amazon.com"]}]
        allowlist = [{"domain": "aws.amazon.com"}]

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships(categories, allowlist)

        assert "Subdomain relationship" in caplog.text
        assert "aws.amazon.com" in caplog.text
        assert "amazon.com" in caplog.text
        assert "shopping" in caplog.text

    def test_multiple_subdomain_warnings(self, caplog):
        """Test multiple warnings for multiple subdomain relationships."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        categories = [
            {"id": "shopping", "domains": ["amazon.com", "ebay.com"]},
        ]
        allowlist = [
            {"domain": "aws.amazon.com"},
            {"domain": "developer.ebay.com"},
        ]

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships(categories, allowlist)

        assert caplog.text.count("Subdomain relationship") == 2

    def test_subdomain_across_categories(self, caplog):
        """Test subdomain warning works across multiple categories."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        categories = [
            {"id": "shopping", "domains": ["amazon.com"]},
            {"id": "social", "domains": ["facebook.com"]},
        ]
        allowlist = [{"domain": "developer.facebook.com"}]

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships(categories, allowlist)

        assert "Subdomain relationship" in caplog.text
        assert "developer.facebook.com" in caplog.text
        assert "category: social" in caplog.text

    def test_empty_categories_no_warning(self, caplog):
        """Test no warning with empty categories."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships([], [{"domain": "test.com"}])

        assert "Subdomain relationship" not in caplog.text

    def test_empty_allowlist_no_warning(self, caplog):
        """Test no warning with empty allowlist."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        categories = [{"id": "social", "domains": ["facebook.com"]}]

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships(categories, [])

        assert "Subdomain relationship" not in caplog.text

    def test_invalid_domain_entries_skipped(self, caplog):
        """Test invalid domain entries are skipped without error."""
        from nextdns_blocker.config import check_category_subdomain_relationships

        categories = [{"id": "social", "domains": ["facebook.com", None, 123]}]
        allowlist = [{"domain": "test.facebook.com"}, {"domain": None}, {}]

        with caplog.at_level("WARNING"):
            check_category_subdomain_relationships(categories, allowlist)

        # Only valid subdomain relationship should be logged
        assert caplog.text.count("Subdomain relationship") == 1
        assert "test.facebook.com" in caplog.text
