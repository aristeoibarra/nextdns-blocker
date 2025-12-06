"""Tests for init wizard functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.cli import main
from nextdns_blocker.init import (
    NEXTDNS_API_URL,
    create_env_file,
    create_sample_domains,
    run_interactive_wizard,
    run_non_interactive,
    validate_api_credentials,
    validate_timezone,
)


class TestValidateApiCredentials:
    """Tests for validate_api_credentials function."""

    @patch("nextdns_blocker.init.requests.get")
    def test_valid_credentials(self, mock_get):
        """Should return True for valid credentials."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        valid, msg = validate_api_credentials("validkey123", "testprofile")

        assert valid is True
        assert "valid" in msg.lower()

    @patch("nextdns_blocker.init.requests.get")
    def test_invalid_api_key(self, mock_get):
        """Should return False for invalid API key."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        valid, msg = validate_api_credentials("invalidkey", "testprofile")

        assert valid is False
        assert "Invalid API key" in msg

    @patch("nextdns_blocker.init.requests.get")
    def test_invalid_profile_id(self, mock_get):
        """Should return False for invalid profile ID."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        valid, msg = validate_api_credentials("validkey123", "badprofile")

        assert valid is False
        assert "not found" in msg.lower()

    @patch("nextdns_blocker.init.requests.get")
    def test_connection_timeout(self, mock_get):
        """Should handle connection timeout."""
        import requests as req

        mock_get.side_effect = req.exceptions.Timeout("timeout")

        valid, msg = validate_api_credentials("testkey12345", "testprofile")

        assert valid is False
        assert "timeout" in msg.lower()


class TestValidateTimezone:
    """Tests for validate_timezone function."""

    def test_valid_timezone_utc(self):
        """Should accept UTC timezone."""
        valid, msg = validate_timezone("UTC")
        assert valid is True

    def test_valid_timezone_america(self):
        """Should accept America/Mexico_City timezone."""
        valid, msg = validate_timezone("America/Mexico_City")
        assert valid is True

    def test_valid_timezone_europe(self):
        """Should accept Europe/London timezone."""
        valid, msg = validate_timezone("Europe/London")
        assert valid is True

    def test_invalid_timezone(self):
        """Should reject invalid timezone."""
        valid, msg = validate_timezone("Invalid/Timezone")
        assert valid is False
        assert "Invalid timezone" in msg


class TestCreateEnvFile:
    """Tests for create_env_file function."""

    def test_creates_env_file(self, tmp_path):
        """Should create .env file with correct content."""
        env_file = create_env_file(tmp_path, "test_api_key", "test_profile_id", "America/New_York")

        assert env_file.exists()
        content = env_file.read_text()
        assert "NEXTDNS_API_KEY=test_api_key" in content
        assert "NEXTDNS_PROFILE_ID=test_profile_id" in content
        assert "TIMEZONE=America/New_York" in content

    def test_creates_env_file_with_domains_url(self, tmp_path):
        """Should include DOMAINS_URL when provided."""
        env_file = create_env_file(
            tmp_path,
            "test_key",
            "test_profile",
            "UTC",
            domains_url="https://example.com/domains.json",
        )

        content = env_file.read_text()
        assert "DOMAINS_URL=https://example.com/domains.json" in content

    def test_creates_parent_directory(self, tmp_path):
        """Should create parent directories if needed."""
        nested_dir = tmp_path / "nested" / "config"
        env_file = create_env_file(nested_dir, "key", "profile", "UTC")

        assert env_file.exists()
        assert nested_dir.exists()

    def test_secure_permissions(self, tmp_path):
        """Should create file with secure permissions (0o600)."""
        env_file = create_env_file(tmp_path, "key", "profile", "UTC")

        mode = env_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestCreateSampleDomains:
    """Tests for create_sample_domains function."""

    def test_creates_domains_file(self, tmp_path):
        """Should create domains.json file."""
        domains_file = create_sample_domains(tmp_path)

        assert domains_file.exists()
        assert domains_file.name == "domains.json"

    def test_valid_json_content(self, tmp_path):
        """Should create valid JSON content."""
        import json

        domains_file = create_sample_domains(tmp_path)
        content = json.loads(domains_file.read_text())

        assert "domains" in content
        assert isinstance(content["domains"], list)
        assert len(content["domains"]) > 0
        assert "domain" in content["domains"][0]

    def test_contains_schedule(self, tmp_path):
        """Should contain schedule configuration."""
        import json

        domains_file = create_sample_domains(tmp_path)
        content = json.loads(domains_file.read_text())

        domain_config = content["domains"][0]
        assert "schedule" in domain_config
        assert "available_hours" in domain_config["schedule"]


class TestRunNonInteractive:
    """Tests for run_non_interactive function."""

    @responses.activate
    def test_success_with_env_vars(self, tmp_path):
        """Should succeed when env vars are set."""
        responses.add(
            responses.GET,
            f"{NEXTDNS_API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        env = {
            "NEXTDNS_API_KEY": "testkey12345",
            "NEXTDNS_PROFILE_ID": "testprofile",
            "TIMEZONE": "UTC",
        }

        with patch.dict(os.environ, env, clear=True):
            result = run_non_interactive(tmp_path)

        assert result is True
        assert (tmp_path / ".env").exists()

    def test_fails_without_api_key(self, tmp_path):
        """Should fail when API key is not set."""
        env = {"NEXTDNS_PROFILE_ID": "testprofile"}

        with patch.dict(os.environ, env, clear=True):
            result = run_non_interactive(tmp_path)

        assert result is False

    def test_fails_without_profile_id(self, tmp_path):
        """Should fail when profile ID is not set."""
        env = {"NEXTDNS_API_KEY": "testkey12345"}

        with patch.dict(os.environ, env, clear=True):
            result = run_non_interactive(tmp_path)

        assert result is False

    def test_fails_with_invalid_timezone(self, tmp_path):
        """Should fail with invalid timezone."""
        env = {
            "NEXTDNS_API_KEY": "testkey12345",
            "NEXTDNS_PROFILE_ID": "testprofile",
            "TIMEZONE": "Invalid/Timezone",
        }

        with patch.dict(os.environ, env, clear=True):
            result = run_non_interactive(tmp_path)

        assert result is False

    @responses.activate
    def test_fails_with_invalid_credentials(self, tmp_path):
        """Should fail when credentials are invalid."""
        responses.add(
            responses.GET,
            f"{NEXTDNS_API_URL}/profiles/testprofile/denylist",
            json={"error": "unauthorized"},
            status=401,
        )

        env = {"NEXTDNS_API_KEY": "badkey12345", "NEXTDNS_PROFILE_ID": "testprofile"}

        with patch.dict(os.environ, env, clear=True):
            result = run_non_interactive(tmp_path)

        assert result is False


class TestInitCommand:
    """Tests for init CLI command."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        return CliRunner()

    def test_init_help(self, runner):
        """Should show help for init command."""
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize" in result.output
        assert "--non-interactive" in result.output

    @responses.activate
    def test_init_non_interactive_success(self, runner, tmp_path):
        """Should succeed with non-interactive mode."""
        responses.add(
            responses.GET,
            f"{NEXTDNS_API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        env = {"NEXTDNS_API_KEY": "testkey12345", "NEXTDNS_PROFILE_ID": "testprofile"}

        with patch.dict(os.environ, env, clear=False):
            result = runner.invoke(
                main, ["init", "--non-interactive", "--config-dir", str(tmp_path)]
            )

        assert result.exit_code == 0
        assert (tmp_path / ".env").exists()

    def test_init_non_interactive_missing_env(self, runner, tmp_path):
        """Should fail non-interactive mode without env vars."""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(
                main, ["init", "--non-interactive", "--config-dir", str(tmp_path)]
            )

        assert result.exit_code == 1

    @responses.activate
    def test_init_with_domains_url(self, runner, tmp_path):
        """Should accept domains URL option."""
        responses.add(
            responses.GET,
            f"{NEXTDNS_API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        env = {"NEXTDNS_API_KEY": "testkey12345", "NEXTDNS_PROFILE_ID": "testprofile"}

        with patch.dict(os.environ, env, clear=False):
            result = runner.invoke(
                main,
                [
                    "init",
                    "--non-interactive",
                    "--config-dir",
                    str(tmp_path),
                    "--url",
                    "https://example.com/domains.json",
                ],
            )

        assert result.exit_code == 0
        content = (tmp_path / ".env").read_text()
        assert "DOMAINS_URL=https://example.com/domains.json" in content


class TestInteractiveWizard:
    """Tests for interactive wizard flow."""

    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_creates_files(self, mock_get, tmp_path):
        """Should create .env and optionally domains.json."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Mock click prompts
        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            with patch("nextdns_blocker.init.click.confirm", return_value=True):
                # Set up prompt responses
                mock_prompt.side_effect = [
                    "testapikey123",  # API key (must be at least 8 chars)
                    "testprofile",  # Profile ID
                    "UTC",  # Timezone
                    "",  # Domains URL (skip)
                ]

                result = run_interactive_wizard(tmp_path)

        assert result is True
        assert (tmp_path / ".env").exists()
        assert (tmp_path / "domains.json").exists()

    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_invalid_credentials(self, mock_get, tmp_path):
        """Should fail with invalid credentials."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["badkey12345", "badprofile", "UTC", ""]

            result = run_interactive_wizard(tmp_path)

        assert result is False

    def test_wizard_invalid_timezone(self, tmp_path):
        """Should fail with invalid timezone."""
        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["testkey12345", "testprofile", "Invalid/Timezone"]

            result = run_interactive_wizard(tmp_path)

        assert result is False

    def test_wizard_empty_api_key(self, tmp_path):
        """Should fail with empty API key."""
        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["", "testprofile", "UTC"]  # Empty API key

            result = run_interactive_wizard(tmp_path)

        assert result is False

    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_skips_domains_creation(self, mock_get, tmp_path):
        """Should skip domains.json when user declines."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            with patch("nextdns_blocker.init.click.confirm", return_value=False):
                mock_prompt.side_effect = ["testapikey123", "testprofile", "UTC", ""]

                result = run_interactive_wizard(tmp_path)

        assert result is True
        assert (tmp_path / ".env").exists()
        assert not (tmp_path / "domains.json").exists()

    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_with_domains_url(self, mock_get, tmp_path):
        """Should save DOMAINS_URL when provided interactively."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            with patch("nextdns_blocker.init.click.confirm", return_value=False):
                mock_prompt.side_effect = [
                    "testapikey123",
                    "testprofile",
                    "UTC",
                    "https://example.com/domains.json",  # Valid URL
                ]

                result = run_interactive_wizard(tmp_path)

        assert result is True
        env_content = (tmp_path / ".env").read_text()
        assert "DOMAINS_URL=https://example.com/domains.json" in env_content

    def test_wizard_invalid_url(self, tmp_path):
        """Should fail with invalid URL format."""
        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = [
                "testapikey123",
                "testprofile",
                "UTC",
                "not-a-valid-url",  # Invalid URL
            ]

            result = run_interactive_wizard(tmp_path)

        assert result is False
