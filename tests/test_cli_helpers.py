"""Tests for CLI helper functions."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from nextdns_blocker.cli_helpers import (
    command_context,
    config_context,
    get_client,
    get_client_and_config,
    handle_error,
)
from nextdns_blocker.exceptions import (
    EXIT_API_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_VALIDATION_ERROR,
    ConfigurationError,
)


class TestHandleError:
    """Tests for handle_error function."""

    def test_timeout_error(self):
        """Test handling of request timeout."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(requests.exceptions.Timeout("Connection timed out"))
        assert exc_info.value.code == EXIT_API_ERROR

    def test_timeout_error_with_context(self):
        """Test timeout error with context prefix."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(requests.exceptions.Timeout(), "fetching denylist")
        assert exc_info.value.code == EXIT_API_ERROR

    def test_connection_error(self):
        """Test handling of connection error."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(requests.exceptions.ConnectionError("Failed to connect"))
        assert exc_info.value.code == EXIT_API_ERROR

    def test_http_error(self):
        """Test handling of HTTP error."""
        response = MagicMock()
        response.status_code = 401
        with pytest.raises(SystemExit) as exc_info:
            handle_error(requests.exceptions.HTTPError("401 Unauthorized", response=response))
        assert exc_info.value.code == EXIT_API_ERROR

    def test_configuration_error(self):
        """Test handling of ConfigurationError."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(ConfigurationError("Invalid API key"))
        assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_permission_error(self):
        """Test handling of PermissionError."""
        error = PermissionError("Access denied")
        error.filename = "/path/to/file"
        with pytest.raises(SystemExit) as exc_info:
            handle_error(error)
        assert exc_info.value.code == 1

    def test_permission_error_no_filename(self):
        """Test handling of PermissionError without filename."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(PermissionError("Access denied"))
        assert exc_info.value.code == 1

    def test_file_not_found_error(self):
        """Test handling of FileNotFoundError."""
        error = FileNotFoundError("File not found")
        error.filename = "/missing/file.json"
        with pytest.raises(SystemExit) as exc_info:
            handle_error(error)
        assert exc_info.value.code == 1

    def test_json_decode_error(self):
        """Test handling of JSONDecodeError."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(json.JSONDecodeError("Expecting value", "doc", 0))
        assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_value_error(self):
        """Test handling of ValueError."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(ValueError("Invalid value provided"))
        assert exc_info.value.code == EXIT_VALIDATION_ERROR

    def test_generic_exception(self):
        """Test handling of generic exception."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(Exception("Something went wrong"))
        assert exc_info.value.code == 1

    def test_generic_exception_with_context(self):
        """Test generic exception with context prefix."""
        with pytest.raises(SystemExit) as exc_info:
            handle_error(RuntimeError("Unexpected failure"), "processing data")
        assert exc_info.value.code == 1


class TestGetClient:
    """Tests for get_client function."""

    def test_get_client_success(self, temp_dir):
        """Test successful client creation."""
        # Create mock .env file
        env_file = temp_dir / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test_api_key_12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test_api_key_12345",
                "profile_id": "testprofile",
            }
            client = get_client(temp_dir)
            assert client is not None
            # API key is stored privately as _api_key
            assert client._api_key == "test_api_key_12345"
            assert client.profile_id == "testprofile"

    def test_get_client_config_error(self, temp_dir):
        """Test client creation with missing config."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = ConfigurationError("Missing API key")
            with pytest.raises(ConfigurationError):
                get_client(temp_dir)


class TestGetClientAndConfig:
    """Tests for get_client_and_config function."""

    def test_get_client_and_config_success(self, temp_dir):
        """Test successful client and config retrieval."""
        mock_config = {
            "api_key": "test_api_key_12345",
            "profile_id": "testprofile",
            "blocklist": [],
        }

        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.return_value = mock_config
            client, config = get_client_and_config(temp_dir)

            assert client is not None
            assert config == mock_config
            assert config["api_key"] == "test_api_key_12345"


class TestCommandContext:
    """Tests for command_context context manager."""

    def test_command_context_success(self, temp_dir):
        """Test successful command context."""
        mock_config = {
            "api_key": "test_api_key_12345",
            "profile_id": "testprofile",
        }

        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.return_value = mock_config
            with command_context(temp_dir) as (client, config):
                assert client is not None
                assert config == mock_config

    def test_command_context_config_error(self, temp_dir):
        """Test command context with configuration error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = ConfigurationError("Invalid configuration")
            with pytest.raises(SystemExit) as exc_info:
                with command_context(temp_dir, "loading config"):
                    pass
            assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_command_context_request_error(self, temp_dir):
        """Test command context with request exception."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = requests.exceptions.Timeout("Timeout")
            with pytest.raises(SystemExit) as exc_info:
                with command_context(temp_dir):
                    pass
            assert exc_info.value.code == EXIT_API_ERROR

    def test_command_context_permission_error(self, temp_dir):
        """Test command context with permission error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = PermissionError("Access denied")
            with pytest.raises(SystemExit):
                with command_context(temp_dir):
                    pass

    def test_command_context_file_not_found(self, temp_dir):
        """Test command context with file not found."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = FileNotFoundError("Config file not found")
            with pytest.raises(SystemExit):
                with command_context(temp_dir):
                    pass

    def test_command_context_json_error(self, temp_dir):
        """Test command context with JSON decode error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            with pytest.raises(SystemExit) as exc_info:
                with command_context(temp_dir):
                    pass
            assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_command_context_value_error(self, temp_dir):
        """Test command context with value error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = ValueError("Invalid value")
            with pytest.raises(SystemExit) as exc_info:
                with command_context(temp_dir):
                    pass
            assert exc_info.value.code == EXIT_VALIDATION_ERROR

    def test_command_context_unexpected_error(self, temp_dir):
        """Test command context with unexpected error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = RuntimeError("Unexpected error")
            with pytest.raises(SystemExit) as exc_info:
                with command_context(temp_dir, "testing"):
                    pass
            assert exc_info.value.code == 1


class TestConfigContext:
    """Tests for config_context context manager."""

    def test_config_context_success(self, temp_dir):
        """Test successful config context."""
        mock_config = {
            "api_key": "test_api_key_12345",
            "profile_id": "testprofile",
            "blocklist": [],
        }

        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.return_value = mock_config
            with config_context(temp_dir) as config:
                assert config == mock_config

    def test_config_context_config_error(self, temp_dir):
        """Test config context with configuration error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = ConfigurationError("Invalid configuration")
            with pytest.raises(SystemExit) as exc_info:
                with config_context(temp_dir, "loading"):
                    pass
            assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_config_context_permission_error(self, temp_dir):
        """Test config context with permission error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = PermissionError("Access denied")
            with pytest.raises(SystemExit):
                with config_context(temp_dir):
                    pass

    def test_config_context_file_not_found(self, temp_dir):
        """Test config context with file not found."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = FileNotFoundError("Config not found")
            with pytest.raises(SystemExit):
                with config_context(temp_dir):
                    pass

    def test_config_context_json_error(self, temp_dir):
        """Test config context with JSON decode error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = json.JSONDecodeError("Parse error", "", 0)
            with pytest.raises(SystemExit) as exc_info:
                with config_context(temp_dir):
                    pass
            assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_config_context_value_error(self, temp_dir):
        """Test config context with value error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = ValueError("Bad value")
            with pytest.raises(SystemExit) as exc_info:
                with config_context(temp_dir):
                    pass
            assert exc_info.value.code == EXIT_VALIDATION_ERROR

    def test_config_context_unexpected_error(self, temp_dir):
        """Test config context with unexpected error."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = RuntimeError("Unexpected")
            with pytest.raises(SystemExit) as exc_info:
                with config_context(temp_dir, "test context"):
                    pass
            assert exc_info.value.code == 1

    def test_config_context_no_error_context(self, temp_dir):
        """Test config context unexpected error without context string."""
        with patch("nextdns_blocker.cli_helpers.load_config") as mock_load:
            mock_load.side_effect = RuntimeError("Unexpected")
            with pytest.raises(SystemExit) as exc_info:
                with config_context(temp_dir):
                    pass
            assert exc_info.value.code == 1
