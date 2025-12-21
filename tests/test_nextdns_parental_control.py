"""Tests for NextDNS Parental Control functionality."""

from unittest.mock import MagicMock, patch

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.client import API_URL, NextDNSClient
from nextdns_blocker.common import NEXTDNS_CATEGORIES, NEXTDNS_SERVICES
from nextdns_blocker.config import (
    validate_nextdns_category,
    validate_nextdns_config,
    validate_nextdns_parental_control,
    validate_nextdns_service,
)

# =============================================================================
# CONSTANTS TESTS
# =============================================================================


class TestNextDNSConstants:
    """Tests for NEXTDNS_CATEGORIES and NEXTDNS_SERVICES constants."""

    def test_categories_is_frozenset(self):
        """Verify NEXTDNS_CATEGORIES is an immutable frozenset."""
        assert isinstance(NEXTDNS_CATEGORIES, frozenset)

    def test_categories_contains_expected_values(self):
        """Verify all 7 expected categories are present."""
        expected = {
            "porn",
            "gambling",
            "dating",
            "piracy",
            "social-networks",
            "gaming",
            "video-streaming",
        }
        assert expected == NEXTDNS_CATEGORIES

    def test_categories_count(self):
        """Verify exactly 7 categories."""
        assert len(NEXTDNS_CATEGORIES) == 7

    def test_services_is_frozenset(self):
        """Verify NEXTDNS_SERVICES is an immutable frozenset."""
        assert isinstance(NEXTDNS_SERVICES, frozenset)

    def test_services_count(self):
        """Verify exactly 43 services."""
        assert len(NEXTDNS_SERVICES) == 43

    def test_services_contains_expected_values(self):
        """Verify some key services are present."""
        expected_services = {
            "tiktok",
            "netflix",
            "youtube",
            "instagram",
            "discord",
            "fortnite",
            "spotify",
            "chatgpt",
        }
        for service in expected_services:
            assert service in NEXTDNS_SERVICES


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestValidateNextDNSCategory:
    """Tests for validate_nextdns_category function."""

    def test_valid_category(self):
        """Valid category should return no errors."""
        config = {"id": "gambling", "description": "Betting sites"}
        errors = validate_nextdns_category(config, 0)
        assert errors == []

    def test_valid_category_with_schedule(self):
        """Valid category with schedule should return no errors."""
        config = {
            "id": "piracy",
            "description": "Piracy sites",
            "unblock_delay": "4h",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["saturday", "sunday"],
                        "time_ranges": [{"start": "10:00", "end": "23:00"}],
                    }
                ]
            },
        }
        errors = validate_nextdns_category(config, 0)
        assert errors == []

    def test_missing_id(self):
        """Missing id field should return error."""
        config = {"description": "No ID"}
        errors = validate_nextdns_category(config, 0)
        assert len(errors) == 1
        assert "Missing 'id' field" in errors[0]

    def test_empty_id(self):
        """Empty id should return error."""
        config = {"id": ""}
        errors = validate_nextdns_category(config, 0)
        assert len(errors) == 1
        assert "Empty or invalid id" in errors[0]

    def test_invalid_category_id(self):
        """Invalid category ID should return error."""
        config = {"id": "invalid-category"}
        errors = validate_nextdns_category(config, 0)
        assert len(errors) == 1
        assert "Invalid category id" in errors[0]
        assert "Valid IDs:" in errors[0]

    def test_invalid_unblock_delay(self):
        """Invalid unblock_delay should return error."""
        config = {"id": "gambling", "unblock_delay": "invalid"}
        errors = validate_nextdns_category(config, 0)
        assert len(errors) == 1
        assert "invalid unblock_delay" in errors[0]

    def test_invalid_description_type(self):
        """Non-string description should return error."""
        config = {"id": "gambling", "description": 123}
        errors = validate_nextdns_category(config, 0)
        assert len(errors) == 1
        assert "'description' must be a string" in errors[0]


class TestValidateNextDNSService:
    """Tests for validate_nextdns_service function."""

    def test_valid_service(self):
        """Valid service should return no errors."""
        config = {"id": "tiktok", "description": "TikTok app"}
        errors = validate_nextdns_service(config, 0)
        assert errors == []

    def test_valid_service_with_schedule(self):
        """Valid service with schedule should return no errors."""
        config = {
            "id": "netflix",
            "description": "Netflix streaming",
            "unblock_delay": "0",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["friday", "saturday", "sunday"],
                        "time_ranges": [{"start": "19:00", "end": "23:00"}],
                    }
                ]
            },
        }
        errors = validate_nextdns_service(config, 0)
        assert errors == []

    def test_missing_id(self):
        """Missing id field should return error."""
        config = {"description": "No ID"}
        errors = validate_nextdns_service(config, 0)
        assert len(errors) == 1
        assert "Missing 'id' field" in errors[0]

    def test_invalid_service_id(self):
        """Invalid service ID should return error."""
        config = {"id": "invalid-service"}
        errors = validate_nextdns_service(config, 0)
        assert len(errors) == 1
        assert "Invalid service id" in errors[0]


class TestValidateNextDNSParentalControl:
    """Tests for validate_nextdns_parental_control function."""

    def test_valid_parental_control(self):
        """Valid parental control settings should return no errors."""
        config = {
            "safe_search": True,
            "youtube_restricted_mode": False,
            "block_bypass": True,
        }
        errors = validate_nextdns_parental_control(config)
        assert errors == []

    def test_empty_config(self):
        """Empty config should return no errors."""
        errors = validate_nextdns_parental_control({})
        assert errors == []

    def test_invalid_key(self):
        """Unknown key should return error."""
        config = {"safe_search": True, "unknown_key": True}
        errors = validate_nextdns_parental_control(config)
        assert len(errors) == 1
        assert "unknown key" in errors[0]

    def test_non_boolean_value(self):
        """Non-boolean value should return error."""
        config = {"safe_search": "yes"}
        errors = validate_nextdns_parental_control(config)
        assert len(errors) == 1
        assert "must be a boolean" in errors[0]

    def test_non_dict_config(self):
        """Non-dict config should return error."""
        errors = validate_nextdns_parental_control("not a dict")
        assert len(errors) == 1
        assert "must be an object" in errors[0]


class TestValidateNextDNSConfig:
    """Tests for validate_nextdns_config function."""

    def test_valid_complete_config(self):
        """Complete valid config should return no errors."""
        config = {
            "parental_control": {
                "safe_search": True,
                "youtube_restricted_mode": False,
                "block_bypass": False,
            },
            "categories": [
                {"id": "gambling", "description": "Betting sites", "unblock_delay": "never"},
                {"id": "porn", "description": "Adult content"},
            ],
            "services": [
                {"id": "tiktok", "description": "TikTok", "unblock_delay": "4h"},
                {"id": "netflix", "description": "Netflix"},
            ],
        }
        errors = validate_nextdns_config(config)
        assert errors == []

    def test_empty_config(self):
        """Empty config should return no errors."""
        errors = validate_nextdns_config({})
        assert errors == []

    def test_non_dict_config(self):
        """Non-dict config should return error."""
        errors = validate_nextdns_config("not a dict")
        assert len(errors) == 1
        assert "'nextdns' must be an object" in errors[0]

    def test_duplicate_category_ids(self):
        """Duplicate category IDs should return error."""
        config = {
            "categories": [
                {"id": "gambling"},
                {"id": "gambling"},
            ]
        }
        errors = validate_nextdns_config(config)
        assert any("duplicate category id" in e.lower() for e in errors)

    def test_duplicate_service_ids(self):
        """Duplicate service IDs should return error."""
        config = {
            "services": [
                {"id": "tiktok"},
                {"id": "tiktok"},
            ]
        }
        errors = validate_nextdns_config(config)
        assert any("duplicate service id" in e.lower() for e in errors)

    def test_categories_not_array(self):
        """Non-array categories should return error."""
        config = {"categories": "not an array"}
        errors = validate_nextdns_config(config)
        assert any("must be an array" in e for e in errors)

    def test_services_not_array(self):
        """Non-array services should return error."""
        config = {"services": "not an array"}
        errors = validate_nextdns_config(config)
        assert any("must be an array" in e for e in errors)


# =============================================================================
# CLIENT TESTS
# =============================================================================


@pytest.fixture
def client():
    """Create a NextDNSClient instance for testing."""
    return NextDNSClient("testapikey12345", "testprofile")


@pytest.fixture
def mock_parental_control():
    """Sample parental control response."""
    return {
        "safeSearch": True,
        "youtubeRestrictedMode": False,
        "blockBypass": True,
        "categories": [
            {"id": "gambling", "active": True},
            {"id": "porn", "active": False},
        ],
        "services": [
            {"id": "tiktok", "active": True},
            {"id": "netflix", "active": False},
        ],
    }


class TestGetParentalControl:
    """Tests for get_parental_control method."""

    @responses.activate
    def test_get_parental_control_success(self, client, mock_parental_control):
        """Successfully fetch parental control config."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json=mock_parental_control,
            status=200,
        )
        result = client.get_parental_control()
        assert result == mock_parental_control

    @responses.activate
    def test_get_parental_control_failure(self, client):
        """Handle API failure gracefully."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            status=500,
        )
        result = client.get_parental_control()
        assert result is None


class TestUpdateParentalControl:
    """Tests for update_parental_control method."""

    @responses.activate
    def test_update_parental_control_success(self, client):
        """Successfully update parental control settings."""
        responses.add(
            responses.PATCH,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"success": True},
            status=200,
        )
        result = client.update_parental_control(safe_search=True)
        assert result is True

    @responses.activate
    def test_update_parental_control_no_changes(self, client):
        """No changes should return success without API call."""
        result = client.update_parental_control()
        assert result is True
        assert len(responses.calls) == 0

    @responses.activate
    def test_update_parental_control_failure(self, client):
        """Handle update failure."""
        responses.add(
            responses.PATCH,
            f"{API_URL}/profiles/testprofile/parentalControl",
            status=500,
        )
        result = client.update_parental_control(safe_search=True)
        assert result is False


class TestCategoryActive:
    """Tests for is_category_active method."""

    @responses.activate
    def test_category_is_active(self, client, mock_parental_control):
        """Check active category returns True."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json=mock_parental_control,
            status=200,
        )
        result = client.is_category_active("gambling")
        assert result is True

    @responses.activate
    def test_category_is_not_active(self, client, mock_parental_control):
        """Check inactive category returns False."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json=mock_parental_control,
            status=200,
        )
        result = client.is_category_active("porn")
        assert result is False

    @responses.activate
    def test_category_not_found(self, client, mock_parental_control):
        """Check non-existent category returns False."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json=mock_parental_control,
            status=200,
        )
        result = client.is_category_active("piracy")
        assert result is False


class TestServiceActive:
    """Tests for is_service_active method."""

    @responses.activate
    def test_service_is_active(self, client, mock_parental_control):
        """Check active service returns True."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json=mock_parental_control,
            status=200,
        )
        result = client.is_service_active("tiktok")
        assert result is True

    @responses.activate
    def test_service_is_not_active(self, client, mock_parental_control):
        """Check inactive service returns False."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json=mock_parental_control,
            status=200,
        )
        result = client.is_service_active("netflix")
        assert result is False


class TestAddCategory:
    """Tests for add_category and activate_category methods."""

    @responses.activate
    def test_add_category_success(self, client):
        """Successfully add a category."""
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/categories",
            json={"success": True},
            status=200,
        )
        result = client.add_category("gambling", active=True)
        assert result is True

    @responses.activate
    def test_activate_category_success(self, client):
        """Successfully activate a category."""
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/categories",
            json={"success": True},
            status=200,
        )
        result = client.activate_category("gambling")
        assert result is True


class TestRemoveCategory:
    """Tests for remove_category and deactivate_category methods."""

    @responses.activate
    def test_remove_category_success(self, client):
        """Successfully remove a category."""
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/categories/gambling",
            json={"success": True},
            status=200,
        )
        result = client.remove_category("gambling")
        assert result is True

    @responses.activate
    def test_deactivate_category_success(self, client):
        """Successfully deactivate a category."""
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/categories/gambling",
            json={"success": True},
            status=200,
        )
        result = client.deactivate_category("gambling")
        assert result is True


class TestAddService:
    """Tests for add_service and activate_service methods."""

    @responses.activate
    def test_add_service_success(self, client):
        """Successfully add a service."""
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/services",
            json={"success": True},
            status=200,
        )
        result = client.add_service("tiktok", active=True)
        assert result is True

    @responses.activate
    def test_activate_service_success(self, client):
        """Successfully activate a service."""
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/services",
            json={"success": True},
            status=200,
        )
        result = client.activate_service("tiktok")
        assert result is True


class TestRemoveService:
    """Tests for remove_service and deactivate_service methods."""

    @responses.activate
    def test_remove_service_success(self, client):
        """Successfully remove a service."""
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/services/tiktok",
            json={"success": True},
            status=200,
        )
        result = client.remove_service("tiktok")
        assert result is True

    @responses.activate
    def test_deactivate_service_success(self, client):
        """Successfully deactivate a service."""
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/services/tiktok",
            json={"success": True},
            status=200,
        )
        result = client.deactivate_service("tiktok")
        assert result is True


# =============================================================================
# CLI COMMAND TESTS
# =============================================================================


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing commands."""
    return CliRunner()


class TestNextDNSCLICategories:
    """Tests for nextdns categories command."""

    def test_categories_shows_all_ids(self, cli_runner):
        """categories command shows all 5 category IDs."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        result = cli_runner.invoke(nextdns_cli, ["categories"])
        assert result.exit_code == 0
        assert "gambling" in result.output
        assert "porn" in result.output
        assert "dating" in result.output
        assert "piracy" in result.output
        assert "social-networks" in result.output


class TestNextDNSCLIServices:
    """Tests for nextdns services command."""

    def test_services_shows_grouped_services(self, cli_runner):
        """services command shows services grouped by category."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        result = cli_runner.invoke(nextdns_cli, ["services"])
        assert result.exit_code == 0
        assert "Social & Messaging" in result.output
        assert "Streaming" in result.output
        assert "Gaming" in result.output
        assert "tiktok" in result.output
        assert "netflix" in result.output
        assert "fortnite" in result.output

    def test_services_shows_43_total(self, cli_runner):
        """services command shows correct count."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        result = cli_runner.invoke(nextdns_cli, ["services"])
        assert result.exit_code == 0
        assert "43 total" in result.output


class TestNextDNSCLIAddCategory:
    """Tests for nextdns add-category command."""

    def test_add_category_validates_id(self, cli_runner, tmp_path):
        """add-category rejects invalid category IDs."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": [{"domain": "example.com"}]}')

        result = cli_runner.invoke(
            nextdns_cli, ["add-category", "invalid-cat", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "Invalid category ID" in result.output
        assert "Valid IDs:" in result.output


class TestNextDNSCLIRemoveCategory:
    """Tests for nextdns remove-category command."""

    def test_remove_category_validates_id(self, cli_runner, tmp_path):
        """remove-category rejects invalid category IDs."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": [{"domain": "example.com"}]}')

        result = cli_runner.invoke(
            nextdns_cli, ["remove-category", "invalid-cat", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "Invalid category ID" in result.output
        assert "Valid IDs:" in result.output


class TestNextDNSCLIAddService:
    """Tests for nextdns add-service command."""

    def test_add_service_validates_id(self, cli_runner, tmp_path):
        """add-service rejects invalid service IDs."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": [{"domain": "example.com"}]}')

        result = cli_runner.invoke(
            nextdns_cli, ["add-service", "invalid-svc", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "Invalid service ID" in result.output


class TestNextDNSCLIRemoveService:
    """Tests for nextdns remove-service command."""

    def test_remove_service_validates_id(self, cli_runner, tmp_path):
        """remove-service rejects invalid service IDs."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": [{"domain": "example.com"}]}')

        result = cli_runner.invoke(
            nextdns_cli, ["remove-service", "invalid-svc", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "Invalid service ID" in result.output


class TestNextDNSCLIStatus:
    """Tests for nextdns status command."""

    @responses.activate
    def test_status_shows_parental_control_info(self, cli_runner, tmp_path):
        """status command shows parental control settings from API."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={
                "safeSearch": True,
                "youtubeRestrictedMode": False,
                "blockBypass": True,
                "categories": [{"id": "gambling", "active": True}],
                "services": [{"id": "tiktok", "active": True}],
            },
            status=200,
        )

        result = cli_runner.invoke(nextdns_cli, ["status", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Parental Control Status" in result.output
        assert "gambling" in result.output
        assert "tiktok" in result.output

    @responses.activate
    def test_status_handles_api_failure(self, cli_runner, tmp_path):
        """status command handles API failure gracefully."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API failure
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"error": "Unauthorized"},
            status=401,
        )

        result = cli_runner.invoke(nextdns_cli, ["status", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Error" in result.output or "Failed" in result.output

    @responses.activate
    def test_status_shows_empty_state(self, cli_runner, tmp_path):
        """status command shows empty state correctly."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response with no active items
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={
                "safeSearch": False,
                "youtubeRestrictedMode": False,
                "blockBypass": False,
                "categories": [],
                "services": [],
            },
            status=200,
        )

        result = cli_runner.invoke(nextdns_cli, ["status", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "None" in result.output


class TestNextDNSCLIList:
    """Tests for nextdns list command."""

    def test_list_shows_no_config_message(self, cli_runner, tmp_path):
        """list command shows message when no nextdns config."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config without nextdns section
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        result = cli_runner.invoke(nextdns_cli, ["list", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "No NextDNS section" in result.output

    def test_list_shows_configured_items(self, cli_runner, tmp_path):
        """list command shows configured categories and services."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create config with nextdns section
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text(
            """{
            "blocklist": [],
            "nextdns": {
                "parental_control": {"safe_search": true},
                "categories": [{"id": "gambling", "description": "Betting sites"}],
                "services": [{"id": "tiktok", "description": "Short videos"}]
            }
        }"""
        )

        result = cli_runner.invoke(nextdns_cli, ["list", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "gambling" in result.output
        assert "tiktok" in result.output

    @responses.activate
    def test_list_remote_shows_api_data(self, cli_runner, tmp_path):
        """list --remote shows data from API."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={
                "safeSearch": True,
                "youtubeRestrictedMode": False,
                "blockBypass": False,
                "categories": [{"id": "porn", "active": True}],
                "services": [{"id": "netflix", "active": True}],
            },
            status=200,
        )

        result = cli_runner.invoke(nextdns_cli, ["list", "--remote", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "from API" in result.output
        assert "porn" in result.output
        assert "netflix" in result.output

    @responses.activate
    def test_list_remote_no_active_items(self, cli_runner, tmp_path):
        """list --remote shows message when no active items."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response with no active items
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={
                "safeSearch": False,
                "youtubeRestrictedMode": False,
                "blockBypass": False,
                "categories": [],
                "services": [],
            },
            status=200,
        )

        result = cli_runner.invoke(nextdns_cli, ["list", "--remote", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "No categories active" in result.output
        assert "No services active" in result.output


class TestNextDNSCLIAddCategorySuccess:
    """Tests for nextdns add-category command success paths."""

    @responses.activate
    def test_add_category_succeeds(self, cli_runner, tmp_path):
        """add-category succeeds with valid category."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/categories",
            json={"success": True},
            status=200,
        )

        result = cli_runner.invoke(
            nextdns_cli, ["add-category", "gambling", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Activated" in result.output
        assert "gambling" in result.output

    @responses.activate
    def test_add_category_api_failure(self, cli_runner, tmp_path):
        """add-category handles API failure."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API failure
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/categories",
            json={"error": "Failed"},
            status=500,
        )

        result = cli_runner.invoke(
            nextdns_cli, ["add-category", "gambling", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "Failed" in result.output or "Error" in result.output

    def test_add_category_blocked_during_panic(self, cli_runner, tmp_path):
        """add-category is blocked during panic mode."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        with patch("nextdns_blocker.panic.is_panic_mode", return_value=True):
            result = cli_runner.invoke(
                nextdns_cli, ["add-category", "gambling", "--config-dir", str(tmp_path)]
            )
            assert result.exit_code == 1
            assert "panic mode" in result.output


class TestNextDNSCLIRemoveCategorySuccess:
    """Tests for nextdns remove-category command success paths."""

    @responses.activate
    def test_remove_category_succeeds(self, cli_runner, tmp_path):
        """remove-category succeeds with valid category."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/categories/gambling",
            json={"success": True},
            status=200,
        )

        result = cli_runner.invoke(
            nextdns_cli, ["remove-category", "gambling", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Deactivated" in result.output
        assert "gambling" in result.output

    def test_remove_category_blocked_during_panic(self, cli_runner, tmp_path):
        """remove-category is blocked during panic mode."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        with patch("nextdns_blocker.panic.is_panic_mode", return_value=True):
            result = cli_runner.invoke(
                nextdns_cli, ["remove-category", "gambling", "--config-dir", str(tmp_path)]
            )
            assert result.exit_code == 1
            assert "panic mode" in result.output


class TestNextDNSCLIAddServiceSuccess:
    """Tests for nextdns add-service command success paths."""

    @responses.activate
    def test_add_service_succeeds(self, cli_runner, tmp_path):
        """add-service succeeds with valid service."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/services",
            json={"success": True},
            status=200,
        )

        result = cli_runner.invoke(
            nextdns_cli, ["add-service", "tiktok", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Activated" in result.output
        assert "tiktok" in result.output

    def test_add_service_blocked_during_panic(self, cli_runner, tmp_path):
        """add-service is blocked during panic mode."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        with patch("nextdns_blocker.panic.is_panic_mode", return_value=True):
            result = cli_runner.invoke(
                nextdns_cli, ["add-service", "tiktok", "--config-dir", str(tmp_path)]
            )
            assert result.exit_code == 1
            assert "panic mode" in result.output


class TestNextDNSCLIRemoveServiceSuccess:
    """Tests for nextdns remove-service command success paths."""

    @responses.activate
    def test_remove_service_succeeds(self, cli_runner, tmp_path):
        """remove-service succeeds with valid service."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        # Mock API response
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/services/tiktok",
            json={"success": True},
            status=200,
        )

        result = cli_runner.invoke(
            nextdns_cli, ["remove-service", "tiktok", "--config-dir", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Deactivated" in result.output
        assert "tiktok" in result.output

    def test_remove_service_blocked_during_panic(self, cli_runner, tmp_path):
        """remove-service is blocked during panic mode."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Create minimal config
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testapikey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')

        with patch("nextdns_blocker.panic.is_panic_mode", return_value=True):
            result = cli_runner.invoke(
                nextdns_cli, ["remove-service", "tiktok", "--config-dir", str(tmp_path)]
            )
            assert result.exit_code == 1
            assert "panic mode" in result.output


class TestNextDNSCLIConfigurationErrors:
    """Tests for configuration error handling in nextdns commands."""

    def test_status_handles_config_error(self, cli_runner, tmp_path):
        """status command handles missing config gracefully."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Don't create any config files
        result = cli_runner.invoke(nextdns_cli, ["status", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_list_handles_config_error(self, cli_runner, tmp_path):
        """list command handles missing config gracefully."""
        from nextdns_blocker.nextdns_cli import nextdns_cli

        # Don't create any config files
        result = cli_runner.invoke(nextdns_cli, ["list", "--config-dir", str(tmp_path)])
        # Should not crash, may show error or empty state
        # With no config file, load_nextdns_config returns None
        assert result.exit_code == 0 or "Error" in result.output


# =============================================================================
# SYNC FUNCTION TESTS
# =============================================================================


class TestSyncNextDNSCategories:
    """Tests for _sync_nextdns_categories function."""

    @responses.activate
    def test_sync_activates_category_when_should_block(self):
        """Sync activates category when schedule says should block."""
        from nextdns_blocker.cli import _sync_nextdns_categories
        from nextdns_blocker.scheduler import ScheduleEvaluator

        client = NextDNSClient("testapikey12345", "testprofile")
        evaluator = MagicMock(spec=ScheduleEvaluator)
        evaluator.should_block.return_value = True

        # Mock: category is not active
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"categories": [{"id": "gambling", "active": False}], "services": []},
            status=200,
        )
        # Mock: activate succeeds
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/categories",
            json={"success": True},
            status=200,
        )

        categories = [{"id": "gambling", "schedule": None}]
        config = {}

        with (
            patch("nextdns_blocker.cli.audit_log"),
            patch("nextdns_blocker.cli.send_discord_notification"),
        ):
            activated, deactivated = _sync_nextdns_categories(
                categories,
                client,
                evaluator,
                config,
                dry_run=False,
                verbose=False,
                panic_active=False,
            )

        assert activated == 1
        assert deactivated == 0

    @responses.activate
    def test_sync_deactivates_category_when_should_not_block(self):
        """Sync deactivates category when schedule says should not block."""
        from nextdns_blocker.cli import _sync_nextdns_categories
        from nextdns_blocker.scheduler import ScheduleEvaluator

        client = NextDNSClient("testapikey12345", "testprofile")
        evaluator = MagicMock(spec=ScheduleEvaluator)
        evaluator.should_block.return_value = False

        # Mock: category is active
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"categories": [{"id": "gambling", "active": True}], "services": []},
            status=200,
        )
        # Mock: deactivate succeeds
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/categories/gambling",
            json={"success": True},
            status=200,
        )

        categories = [{"id": "gambling", "schedule": {"available_hours": []}}]
        config = {}

        with (
            patch("nextdns_blocker.cli.audit_log"),
            patch("nextdns_blocker.cli.send_discord_notification"),
        ):
            activated, deactivated = _sync_nextdns_categories(
                categories,
                client,
                evaluator,
                config,
                dry_run=False,
                verbose=False,
                panic_active=False,
            )

        assert activated == 0
        assert deactivated == 1

    @responses.activate
    def test_sync_skips_deactivation_during_panic_mode(self):
        """Sync skips deactivation during panic mode."""
        from nextdns_blocker.cli import _sync_nextdns_categories
        from nextdns_blocker.scheduler import ScheduleEvaluator

        client = NextDNSClient("testapikey12345", "testprofile")
        evaluator = MagicMock(spec=ScheduleEvaluator)
        evaluator.should_block.return_value = False

        # Mock: category is active
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"categories": [{"id": "gambling", "active": True}], "services": []},
            status=200,
        )

        categories = [{"id": "gambling", "schedule": {"available_hours": []}}]
        config = {}

        activated, deactivated = _sync_nextdns_categories(
            categories, client, evaluator, config, dry_run=False, verbose=False, panic_active=True
        )

        # Should not deactivate during panic mode
        assert activated == 0
        assert deactivated == 0


class TestSyncNextDNSServices:
    """Tests for _sync_nextdns_services function."""

    @responses.activate
    def test_sync_activates_service_when_should_block(self):
        """Sync activates service when schedule says should block."""
        from nextdns_blocker.cli import _sync_nextdns_services
        from nextdns_blocker.scheduler import ScheduleEvaluator

        client = NextDNSClient("testapikey12345", "testprofile")
        evaluator = MagicMock(spec=ScheduleEvaluator)
        evaluator.should_block.return_value = True

        # Mock: service is not active
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"categories": [], "services": [{"id": "tiktok", "active": False}]},
            status=200,
        )
        # Mock: activate succeeds
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/parentalControl/services",
            json={"success": True},
            status=200,
        )

        services = [{"id": "tiktok", "schedule": None}]
        config = {}

        with (
            patch("nextdns_blocker.cli.audit_log"),
            patch("nextdns_blocker.cli.send_discord_notification"),
        ):
            activated, deactivated = _sync_nextdns_services(
                services,
                client,
                evaluator,
                config,
                dry_run=False,
                verbose=False,
                panic_active=False,
            )

        assert activated == 1
        assert deactivated == 0

    @responses.activate
    def test_sync_deactivates_service_when_should_not_block(self):
        """Sync deactivates service when schedule says should not block."""
        from nextdns_blocker.cli import _sync_nextdns_services
        from nextdns_blocker.scheduler import ScheduleEvaluator

        client = NextDNSClient("testapikey12345", "testprofile")
        evaluator = MagicMock(spec=ScheduleEvaluator)
        evaluator.should_block.return_value = False

        # Mock: service is active
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"categories": [], "services": [{"id": "tiktok", "active": True}]},
            status=200,
        )
        # Mock: deactivate succeeds
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/parentalControl/services/tiktok",
            json={"success": True},
            status=200,
        )

        services = [{"id": "tiktok", "schedule": {"available_hours": []}}]
        config = {}

        with (
            patch("nextdns_blocker.cli.audit_log"),
            patch("nextdns_blocker.cli.send_discord_notification"),
        ):
            activated, deactivated = _sync_nextdns_services(
                services,
                client,
                evaluator,
                config,
                dry_run=False,
                verbose=False,
                panic_active=False,
            )

        assert activated == 0
        assert deactivated == 1

    @responses.activate
    def test_sync_skips_service_deactivation_during_panic_mode(self):
        """Sync skips service deactivation during panic mode."""
        from nextdns_blocker.cli import _sync_nextdns_services
        from nextdns_blocker.scheduler import ScheduleEvaluator

        client = NextDNSClient("testapikey12345", "testprofile")
        evaluator = MagicMock(spec=ScheduleEvaluator)
        evaluator.should_block.return_value = False

        # Mock: service is active
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"categories": [], "services": [{"id": "tiktok", "active": True}]},
            status=200,
        )

        services = [{"id": "tiktok", "schedule": {"available_hours": []}}]
        config = {}

        activated, deactivated = _sync_nextdns_services(
            services, client, evaluator, config, dry_run=False, verbose=False, panic_active=True
        )

        # Should not deactivate during panic mode
        assert activated == 0
        assert deactivated == 0


class TestSyncNextDNSParentalControl:
    """Tests for _sync_nextdns_parental_control function."""

    @responses.activate
    def test_sync_updates_parental_control_settings(self):
        """Sync updates parental control global settings."""
        from nextdns_blocker.cli import _sync_nextdns_parental_control

        client = NextDNSClient("testapikey12345", "testprofile")

        # Mock: update succeeds
        responses.add(
            responses.PATCH,
            f"{API_URL}/profiles/testprofile/parentalControl",
            json={"success": True},
            status=200,
        )

        nextdns_config = {
            "parental_control": {
                "safe_search": True,
                "youtube_restricted_mode": False,
                "block_bypass": True,
            }
        }
        config = {}

        result = _sync_nextdns_parental_control(
            nextdns_config, client, config, dry_run=False, verbose=False
        )

        assert result is True

    def test_sync_skips_when_no_parental_control(self):
        """Sync returns True when no parental_control settings."""
        from nextdns_blocker.cli import _sync_nextdns_parental_control

        client = NextDNSClient("testapikey12345", "testprofile")

        nextdns_config = {}  # No parental_control
        config = {}

        result = _sync_nextdns_parental_control(
            nextdns_config, client, config, dry_run=False, verbose=False
        )

        assert result is True

    def test_sync_dry_run_does_not_call_api(self):
        """Sync in dry-run mode does not call API."""
        from nextdns_blocker.cli import _sync_nextdns_parental_control

        client = NextDNSClient("testapikey12345", "testprofile")

        nextdns_config = {
            "parental_control": {
                "safe_search": True,
            }
        }
        config = {}

        result = _sync_nextdns_parental_control(
            nextdns_config, client, config, dry_run=True, verbose=False
        )

        assert result is True
        # No API calls should be made in dry-run mode
