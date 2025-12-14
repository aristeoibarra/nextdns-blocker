"""Tests for init wizard functionality."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.cli import main
from nextdns_blocker.init import (
    NEXTDNS_API_URL,
    create_env_file,
    create_sample_domains,
    detect_existing_config,
    detect_system_timezone,
    handle_domains_migration,
    prompt_domains_migration,
    run_initial_sync,
    run_interactive_wizard,
    run_non_interactive,
    validate_api_credentials,
    validate_timezone,
)
from nextdns_blocker.platform_utils import is_linux, is_macos, is_windows

# Helper for skipping Unix-specific tests on Windows
is_windows_platform = sys.platform == "win32"
skip_on_windows = pytest.mark.skipif(
    is_windows_platform, reason="Unix permissions not applicable on Windows"
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


class TestDetectSystemTimezone:
    """Tests for detect_system_timezone function."""

    def test_returns_string(self):
        """Should return a string."""
        result = detect_system_timezone()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_valid_timezone(self):
        """Should return a valid IANA timezone."""
        from zoneinfo import ZoneInfo

        result = detect_system_timezone()
        # Should not raise KeyError
        ZoneInfo(result)

    @patch.dict(os.environ, {"TZ": "America/New_York"})
    def test_uses_tz_env_variable(self):
        """Should use TZ environment variable when set."""
        result = detect_system_timezone()
        assert result == "America/New_York"

    @patch.dict(os.environ, {"TZ": "Invalid/Timezone"})
    def test_ignores_invalid_tz_env(self):
        """Should ignore invalid TZ environment variable."""
        result = detect_system_timezone()
        # Should fall back to system detection or UTC, not the invalid value
        assert result != "Invalid/Timezone"

    @patch.dict(os.environ, {}, clear=True)
    @patch("nextdns_blocker.init.is_windows", return_value=False)
    @patch("nextdns_blocker.init.Path")
    def test_unix_symlink_detection(self, mock_path_class, mock_is_windows):
        """Should detect timezone from /etc/localtime symlink on Unix."""
        mock_path = MagicMock()
        mock_path.is_symlink.return_value = True
        mock_path.resolve.return_value = MagicMock(
            __str__=lambda self: "/usr/share/zoneinfo/Europe/London"
        )
        mock_path_class.return_value = mock_path

        result = detect_system_timezone()
        assert result == "Europe/London"

    @patch.dict(os.environ, {}, clear=True)
    @patch("nextdns_blocker.init.is_windows", return_value=False)
    @patch("nextdns_blocker.init.Path")
    def test_macos_zoneinfo_default_path(self, mock_path_class, mock_is_windows):
        """Should detect timezone from macOS zoneinfo.default path."""
        mock_path = MagicMock()
        mock_path.is_symlink.return_value = True
        mock_path.resolve.return_value = MagicMock(
            __str__=lambda self: "/usr/share/zoneinfo.default/America/Los_Angeles"
        )
        mock_path_class.return_value = mock_path

        result = detect_system_timezone()
        assert result == "America/Los_Angeles"

    @patch.dict(os.environ, {}, clear=True)
    @patch("nextdns_blocker.init.is_windows", return_value=True)
    @patch("nextdns_blocker.init.subprocess.run")
    def test_windows_tzutil_detection(self, mock_run, mock_is_windows):
        """Should detect timezone using tzutil on Windows."""
        mock_run.return_value = MagicMock(stdout="Pacific Standard Time\n")

        result = detect_system_timezone()
        assert result == "America/Los_Angeles"

    @patch.dict(os.environ, {}, clear=True)
    @patch("nextdns_blocker.init.is_windows", return_value=True)
    @patch("nextdns_blocker.init.subprocess.run")
    def test_windows_unknown_timezone_falls_back(self, mock_run, mock_is_windows):
        """Should fall back to UTC for unknown Windows timezone."""
        mock_run.return_value = MagicMock(stdout="Unknown Timezone Name\n")

        result = detect_system_timezone()
        assert result == "UTC"

    @patch.dict(os.environ, {}, clear=True)
    @patch("nextdns_blocker.init.is_windows", return_value=False)
    @patch("nextdns_blocker.init.Path")
    def test_falls_back_to_utc(self, mock_path_class, mock_is_windows):
        """Should fall back to UTC when detection fails."""
        mock_path = MagicMock()
        mock_path.is_symlink.return_value = False
        mock_path_class.return_value = mock_path

        result = detect_system_timezone()
        assert result == "UTC"


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

    @skip_on_windows
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
    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    def test_init_non_interactive_success(self, mock_sync, runner, tmp_path):
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
    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    def test_init_with_domains_url(self, mock_sync, runner, tmp_path):
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

    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_creates_files(self, mock_get, mock_sync, tmp_path):
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

    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_skips_domains_creation(self, mock_get, mock_sync, tmp_path):
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

    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_with_domains_url(self, mock_get, mock_sync, tmp_path):
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


class TestDetectExistingConfig:
    """Tests for detect_existing_config function."""

    def test_no_existing_config(self, tmp_path):
        """Should detect no existing configuration."""
        result = detect_existing_config(tmp_path)

        assert result["has_local"] is False
        assert result["has_url"] is False
        assert result["url"] is None
        assert result["local_path"] == tmp_path / "domains.json"

    def test_local_domains_only(self, tmp_path):
        """Should detect local domains.json only."""
        (tmp_path / "domains.json").write_text('{"domains": []}')

        result = detect_existing_config(tmp_path)

        assert result["has_local"] is True
        assert result["has_url"] is False

    def test_url_only(self, tmp_path):
        """Should detect DOMAINS_URL from .env."""
        env_content = """NEXTDNS_API_KEY=testkey
DOMAINS_URL=https://example.com/domains.json
"""
        (tmp_path / ".env").write_text(env_content)

        result = detect_existing_config(tmp_path)

        assert result["has_local"] is False
        assert result["has_url"] is True
        assert result["url"] == "https://example.com/domains.json"

    def test_url_with_double_quotes(self, tmp_path):
        """Should handle DOMAINS_URL with double quotes."""
        env_content = 'DOMAINS_URL="https://example.com/domains.json"\n'
        (tmp_path / ".env").write_text(env_content)

        result = detect_existing_config(tmp_path)

        assert result["has_url"] is True
        assert result["url"] == "https://example.com/domains.json"

    def test_url_with_single_quotes(self, tmp_path):
        """Should handle DOMAINS_URL with single quotes."""
        env_content = "DOMAINS_URL='https://example.com/domains.json'\n"
        (tmp_path / ".env").write_text(env_content)

        result = detect_existing_config(tmp_path)

        assert result["has_url"] is True
        assert result["url"] == "https://example.com/domains.json"

    def test_both_local_and_url(self, tmp_path):
        """Should detect both local and URL config."""
        (tmp_path / "domains.json").write_text('{"domains": []}')
        env_content = "DOMAINS_URL=https://example.com/domains.json\n"
        (tmp_path / ".env").write_text(env_content)

        result = detect_existing_config(tmp_path)

        assert result["has_local"] is True
        assert result["has_url"] is True

    def test_empty_url_value(self, tmp_path):
        """Should handle empty DOMAINS_URL."""
        env_content = "DOMAINS_URL=\n"
        (tmp_path / ".env").write_text(env_content)

        result = detect_existing_config(tmp_path)

        assert result["has_url"] is False
        assert result["url"] is None

    def test_commented_url(self, tmp_path):
        """Should ignore commented DOMAINS_URL."""
        env_content = "#DOMAINS_URL=https://example.com/domains.json\n"
        (tmp_path / ".env").write_text(env_content)

        result = detect_existing_config(tmp_path)

        assert result["has_url"] is False


class TestHandleDomainsMigration:
    """Tests for handle_domains_migration function."""

    def test_url_choice_deletes_local(self, tmp_path):
        """Should delete local file when switching to URL."""
        (tmp_path / "domains.json").write_text('{"domains": []}')

        url, should_create = handle_domains_migration(
            tmp_path, "url", "https://example.com/domains.json"
        )

        assert url == "https://example.com/domains.json"
        assert should_create is False
        assert not (tmp_path / "domains.json").exists()

    def test_local_choice(self, tmp_path):
        """Should keep local file and no URL."""
        url, should_create = handle_domains_migration(tmp_path, "local", None)

        assert url is None
        assert should_create is True  # Should create if doesn't exist

    def test_local_choice_exists(self, tmp_path):
        """Should not create local if already exists."""
        (tmp_path / "domains.json").write_text('{"domains": []}')

        url, should_create = handle_domains_migration(tmp_path, "local", None)

        assert should_create is False

    def test_keep_url_choice(self, tmp_path):
        """Should keep existing URL."""
        url, should_create = handle_domains_migration(
            tmp_path, "keep_url", "https://example.com/domains.json"
        )

        assert url == "https://example.com/domains.json"
        assert should_create is False

    def test_both_choice(self, tmp_path):
        """Should keep both URL and local."""
        url, should_create = handle_domains_migration(
            tmp_path, "both", "https://example.com/domains.json"
        )

        assert url == "https://example.com/domains.json"
        assert should_create is False

    def test_none_choice(self, tmp_path):
        """Should return None for no existing config."""
        url, should_create = handle_domains_migration(tmp_path, "none", None)

        assert url is None
        assert should_create is False


class TestPromptDomainsMigration:
    """Tests for prompt_domains_migration function."""

    def test_both_local_and_url_keep(self, tmp_path):
        """Should return keep_url when user selects option 1."""
        existing = {
            "has_local": True,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt", return_value="1"):
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "keep_url"
        assert url == "https://example.com/domains.json"

    def test_both_local_and_url_switch_to_local(self, tmp_path):
        """Should return local when user selects option 2."""
        existing = {
            "has_local": True,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt", return_value="2"):
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "local"
        assert url is None

    def test_both_local_and_url_change_url(self, tmp_path):
        """Should return new URL when user selects option 3."""
        existing = {
            "has_local": True,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["3", "https://new.example.com/domains.json"]
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "url"
        assert url == "https://new.example.com/domains.json"

    def test_both_keep_both(self, tmp_path):
        """Should return both when user selects option 4."""
        existing = {
            "has_local": True,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt", return_value="4"):
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "both"
        assert url == "https://example.com/domains.json"

    def test_local_only_keep(self, tmp_path):
        """Should return local when user keeps local file."""
        existing = {
            "has_local": True,
            "has_url": False,
            "url": None,
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt", return_value="1"):
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "local"
        assert url is None

    def test_local_only_switch_to_url(self, tmp_path):
        """Should return url when user switches from local."""
        existing = {
            "has_local": True,
            "has_url": False,
            "url": None,
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["2", "https://example.com/domains.json"]
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "url"
        assert url == "https://example.com/domains.json"

    def test_url_only_keep(self, tmp_path):
        """Should return keep_url when user keeps URL."""
        existing = {
            "has_local": False,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt", return_value="1"):
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "keep_url"
        assert url == "https://example.com/domains.json"

    def test_url_only_switch_to_local(self, tmp_path):
        """Should return local when user switches from URL."""
        existing = {
            "has_local": False,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt", return_value="2"):
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "local"
        assert url is None

    def test_url_only_change_url(self, tmp_path):
        """Should return new URL when user changes URL."""
        existing = {
            "has_local": False,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["3", "https://new.example.com/domains.json"]
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "url"
        assert url == "https://new.example.com/domains.json"

    def test_no_existing_config(self, tmp_path):
        """Should return none when no existing config."""
        existing = {
            "has_local": False,
            "has_url": False,
            "url": None,
            "local_path": tmp_path / "domains.json",
        }

        choice, url = prompt_domains_migration(existing)

        assert choice == "none"
        assert url is None

    def test_invalid_url_fallback(self, tmp_path):
        """Should keep current URL when new URL is invalid."""
        existing = {
            "has_local": True,
            "has_url": True,
            "url": "https://example.com/domains.json",
            "local_path": tmp_path / "domains.json",
        }

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["3", "not-a-valid-url"]
            with patch("nextdns_blocker.init.click.echo"):
                choice, url = prompt_domains_migration(existing)

        assert choice == "keep_url"
        assert url == "https://example.com/domains.json"


class TestPlatformDetection:
    """Tests for platform detection functions (moved to platform_utils)."""

    def test_is_macos_darwin(self):
        """Should return True on Darwin platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_macos() is True

    def test_is_macos_linux(self):
        """Should return False on Linux platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            assert is_macos() is False

    def test_is_windows_win32(self):
        """Should return True on Windows platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert is_windows() is True

    def test_is_windows_darwin(self):
        """Should return False on macOS platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_windows() is False

    def test_is_linux_linux(self):
        """Should return True on Linux platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            assert is_linux() is True

    def test_is_linux_darwin(self):
        """Should return False on macOS platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_linux() is False


class TestRunInitialSync:
    """Tests for run_initial_sync function."""

    def test_sync_success_with_exe(self):
        """Should return True when sync succeeds."""
        with patch("shutil.which", return_value="/usr/bin/nextdns-blocker"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = run_initial_sync()

        assert result is True

    def test_sync_success_with_module(self, tmp_path):
        """Should use python module when exe not found anywhere."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    result = run_initial_sync()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "-m" in call_args
        assert "nextdns_blocker" in call_args

    def test_sync_success_with_pipx_fallback(self, tmp_path):
        """Should use pipx exe when shutil.which fails but pipx exe exists."""
        # Create pipx executable location
        pipx_bin = tmp_path / ".local" / "bin"
        pipx_bin.mkdir(parents=True)
        pipx_exe = pipx_bin / "nextdns-blocker"
        pipx_exe.touch()

        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
                with patch("nextdns_blocker.platform_utils.is_windows", return_value=False):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0)
                        result = run_initial_sync()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert str(pipx_exe) in call_args

    def test_sync_failure(self, tmp_path):
        """Should return False when sync fails."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=1)
                    result = run_initial_sync()

        assert result is False

    def test_sync_exception(self, tmp_path):
        """Should return False on exception."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
                with patch("subprocess.run", side_effect=Exception("error")):
                    result = run_initial_sync()

        assert result is False


class TestValidateApiCredentialsEdgeCases:
    """Additional tests for validate_api_credentials edge cases."""

    @patch("nextdns_blocker.init.requests.get")
    def test_connection_error(self, mock_get):
        """Should handle connection error."""
        import requests as req

        mock_get.side_effect = req.exceptions.ConnectionError("connection failed")

        valid, msg = validate_api_credentials("testkey12345", "testprofile")

        assert valid is False
        assert "Connection failed" in msg

    @patch("nextdns_blocker.init.requests.get")
    def test_request_exception(self, mock_get):
        """Should handle generic request exception."""
        import requests as req

        mock_get.side_effect = req.exceptions.RequestException("generic error")

        valid, msg = validate_api_credentials("testkey12345", "testprofile")

        assert valid is False
        assert "Request error" in msg

    @patch("nextdns_blocker.init.requests.get")
    def test_other_status_code(self, mock_get):
        """Should handle other HTTP status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        valid, msg = validate_api_credentials("testkey12345", "testprofile")

        assert valid is False
        assert "API error: 500" in msg


class TestInstallLaunchd:
    """Tests for _install_launchd function."""

    def test_install_launchd_success(self, tmp_path):
        """Should successfully install launchd jobs on macOS."""
        from nextdns_blocker.init import _install_launchd

        launch_agents = tmp_path / "Library" / "LaunchAgents"
        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
            with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
                with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                        success, result = _install_launchd()

        assert success is True
        assert result == "launchd"
        assert launch_agents.exists()

    def test_install_launchd_uses_python_module(self, tmp_path):
        """Should use python module when exe not found."""
        from nextdns_blocker.init import _install_launchd

        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
            with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
                with patch("shutil.which", return_value=None):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                        success, result = _install_launchd()

        assert success is True

    def test_install_launchd_load_failure(self, tmp_path):
        """Should return failure when launchctl load fails."""
        from nextdns_blocker.init import _install_launchd

        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
            with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
                with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                    with patch("subprocess.run") as mock_run:
                        # First two calls (unload) succeed, third (load sync) fails
                        mock_run.side_effect = [
                            MagicMock(returncode=0),  # unload sync
                            MagicMock(returncode=0),  # unload watchdog
                            MagicMock(returncode=1, stdout="", stderr="error"),  # load sync
                            MagicMock(returncode=0),  # load watchdog
                        ]
                        success, result = _install_launchd()

        assert success is False
        assert "Failed" in result

    def test_install_launchd_exception(self, tmp_path):
        """Should handle exceptions during launchd installation."""
        from nextdns_blocker.init import _install_launchd

        with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
            with patch("nextdns_blocker.init.get_log_dir", side_effect=Exception("test error")):
                success, result = _install_launchd()

        assert success is False
        assert "launchd error" in result

    def test_install_launchd_uses_pipx_fallback(self, tmp_path):
        """Should use pipx executable when shutil.which fails but pipx exe exists."""
        import plistlib

        from nextdns_blocker.init import _install_launchd

        launch_agents = tmp_path / "Library" / "LaunchAgents"
        log_dir = tmp_path / "logs"

        # Create pipx executable location
        pipx_bin = tmp_path / ".local" / "bin"
        pipx_bin.mkdir(parents=True)
        pipx_exe = pipx_bin / "nextdns-blocker"
        pipx_exe.touch()

        with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
            with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
                with patch("shutil.which", return_value=None):  # Simulate exe not in PATH
                    with patch("nextdns_blocker.platform_utils.is_windows", return_value=False):
                        with patch("subprocess.run") as mock_run:
                            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                            success, result = _install_launchd()

        assert success is True
        assert result == "launchd"

        # Verify plist uses pipx executable path
        sync_plist_path = launch_agents / "com.nextdns-blocker.sync.plist"
        assert sync_plist_path.exists()
        plist_content = plistlib.loads(sync_plist_path.read_bytes())
        assert plist_content["ProgramArguments"][0] == str(pipx_exe)

    def test_install_launchd_includes_local_bin_in_path(self, tmp_path):
        """Should include ~/.local/bin in PATH environment variable."""
        import plistlib

        from nextdns_blocker.init import _install_launchd

        launch_agents = tmp_path / "Library" / "LaunchAgents"
        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.Path.home", return_value=tmp_path):
            with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
                with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                        success, result = _install_launchd()

        assert success is True

        # Verify PATH includes ~/.local/bin
        sync_plist_path = launch_agents / "com.nextdns-blocker.sync.plist"
        plist_content = plistlib.loads(sync_plist_path.read_bytes())
        path_env = plist_content["EnvironmentVariables"]["PATH"]
        assert "/.local/bin" in path_env

        # Verify watchdog plist too
        watchdog_plist_path = launch_agents / "com.nextdns-blocker.watchdog.plist"
        watchdog_content = plistlib.loads(watchdog_plist_path.read_bytes())
        watchdog_path = watchdog_content["EnvironmentVariables"]["PATH"]
        assert "/.local/bin" in watchdog_path


class TestInstallCron:
    """Tests for _install_cron function."""

    def test_install_cron_success(self, tmp_path):
        """Should successfully install cron jobs."""
        from nextdns_blocker.init import _install_cron

        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
            with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = [
                        MagicMock(returncode=0, stdout=""),  # crontab -l
                        MagicMock(returncode=0),  # crontab -
                    ]
                    success, result = _install_cron()

        assert success is True
        assert result == "cron"

    def test_install_cron_no_existing_crontab(self, tmp_path):
        """Should handle empty crontab."""
        from nextdns_blocker.init import _install_cron

        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
            with patch("shutil.which", return_value=None):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = [
                        MagicMock(returncode=1, stdout=""),  # no crontab
                        MagicMock(returncode=0),  # set crontab
                    ]
                    success, result = _install_cron()

        assert success is True

    def test_install_cron_replaces_existing(self, tmp_path):
        """Should replace existing nextdns-blocker cron entries."""
        from nextdns_blocker.init import _install_cron

        log_dir = tmp_path / "logs"
        existing_crontab = "*/5 * * * * nextdns-blocker sync\n0 * * * * other-task"

        with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
            with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = [
                        MagicMock(returncode=0, stdout=existing_crontab),
                        MagicMock(returncode=0),
                    ]
                    success, result = _install_cron()

        assert success is True
        # Verify the new crontab was set
        set_call = mock_run.call_args_list[1]
        new_crontab = set_call[1]["input"]
        assert "nextdns-blocker sync" in new_crontab
        assert "nextdns-blocker watchdog" in new_crontab

    def test_install_cron_failure(self, tmp_path):
        """Should return failure when crontab fails."""
        from nextdns_blocker.init import _install_cron

        log_dir = tmp_path / "logs"

        with patch("nextdns_blocker.init.get_log_dir", return_value=log_dir):
            with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = [
                        MagicMock(returncode=0, stdout=""),
                        MagicMock(returncode=1),  # crontab set fails
                    ]
                    success, result = _install_cron()

        assert success is False
        assert "Failed" in result

    def test_install_cron_exception(self, tmp_path):
        """Should handle exceptions during cron installation."""
        from nextdns_blocker.init import _install_cron

        with patch("nextdns_blocker.init.get_log_dir", side_effect=Exception("test error")):
            success, result = _install_cron()

        assert success is False
        assert "cron error" in result


class TestInstallScheduling:
    """Tests for install_scheduling function."""

    def test_install_scheduling_macos(self):
        """Should use launchd on macOS."""
        from nextdns_blocker.init import install_scheduling

        with patch("nextdns_blocker.init.is_macos", return_value=True):
            with patch("nextdns_blocker.init._install_launchd") as mock_launchd:
                mock_launchd.return_value = (True, "launchd")
                success, result = install_scheduling()

        assert success is True
        assert result == "launchd"
        mock_launchd.assert_called_once()

    def test_install_scheduling_linux(self):
        """Should use cron on Linux."""
        from nextdns_blocker.init import install_scheduling

        with patch("nextdns_blocker.init.is_macos", return_value=False):
            with patch("nextdns_blocker.init.is_windows", return_value=False):
                with patch("nextdns_blocker.init._install_cron") as mock_cron:
                    mock_cron.return_value = (True, "cron")
                    success, result = install_scheduling()

        assert success is True
        assert result == "cron"
        mock_cron.assert_called_once()


class TestCreateEnvFileEdgeCases:
    """Additional tests for create_env_file edge cases."""

    def test_create_env_file_oserror(self, tmp_path):
        """Should raise OSError when file creation fails."""
        with patch("os.open", side_effect=OSError("Permission denied")):
            with pytest.raises(OSError):
                create_env_file(tmp_path, "key", "profile", "UTC")


class TestInteractiveWizardEdgeCases:
    """Additional tests for interactive wizard edge cases."""

    def test_wizard_empty_profile_id(self, tmp_path):
        """Should fail with empty profile ID."""
        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            mock_prompt.side_effect = ["testapikey123", ""]  # Empty profile ID

            result = run_interactive_wizard(tmp_path)

        assert result is False

    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_with_url_flag_deletes_local(self, mock_get, mock_sync, tmp_path):
        """Should delete local file when URL provided via flag."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Create existing local file
        (tmp_path / "domains.json").write_text('{"domains": []}')

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            with patch("nextdns_blocker.init.click.confirm", return_value=True):
                mock_prompt.side_effect = ["testapikey123", "testprofile", "UTC"]

                result = run_interactive_wizard(
                    tmp_path, domains_url="https://example.com/domains.json"
                )

        assert result is True
        # Local file should be deleted
        assert not (tmp_path / "domains.json").exists()

    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_with_url_flag_keep_local(self, mock_get, mock_sync, tmp_path):
        """Should keep local file when user declines deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Create existing local file
        (tmp_path / "domains.json").write_text('{"domains": []}')

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            with patch("nextdns_blocker.init.click.confirm", return_value=False):
                mock_prompt.side_effect = ["testapikey123", "testprofile", "UTC"]

                result = run_interactive_wizard(
                    tmp_path, domains_url="https://example.com/domains.json"
                )

        assert result is True
        # Local file should still exist
        assert (tmp_path / "domains.json").exists()

    @patch("nextdns_blocker.init.run_initial_sync", return_value=True)
    @patch("nextdns_blocker.init.requests.get")
    def test_wizard_existing_config_migration(self, mock_get, mock_sync, tmp_path):
        """Should handle existing config migration."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Create existing URL config
        (tmp_path / ".env").write_text("DOMAINS_URL=https://old.example.com/domains.json\n")

        with patch("nextdns_blocker.init.click.prompt") as mock_prompt:
            with patch("nextdns_blocker.init.click.confirm", return_value=False):
                # Prompts: api_key, profile, timezone, then migration choice "1" (keep url)
                mock_prompt.side_effect = ["testapikey123", "testprofile", "UTC", "1"]

                result = run_interactive_wizard(tmp_path)

        assert result is True


class TestNonInteractiveEdgeCases:
    """Additional tests for non-interactive mode edge cases."""

    @responses.activate
    def test_non_interactive_scheduling_warning(self, tmp_path):
        """Should show warning when scheduling fails."""
        responses.add(
            responses.GET,
            f"{NEXTDNS_API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        env = {
            "NEXTDNS_API_KEY": "testkey12345",
            "NEXTDNS_PROFILE_ID": "testprofile",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("nextdns_blocker.init.install_scheduling", return_value=(False, "error")):
                result = run_non_interactive(tmp_path)

        # Should still succeed even if scheduling fails
        assert result is True

    @responses.activate
    def test_non_interactive_sync_warning(self, tmp_path):
        """Should show warning when initial sync fails."""
        responses.add(
            responses.GET,
            f"{NEXTDNS_API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        env = {
            "NEXTDNS_API_KEY": "testkey12345",
            "NEXTDNS_PROFILE_ID": "testprofile",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("nextdns_blocker.init.run_initial_sync", return_value=False):
                result = run_non_interactive(tmp_path)

        # Should still succeed even if sync fails
        assert result is True
