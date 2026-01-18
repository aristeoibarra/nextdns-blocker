"""Tests for denylist and allowlist CLI commands."""

import json
from pathlib import Path

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.__main__ import main

API_URL = "https://api.nextdns.io"


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path: Path):
    """Create a temporary config directory with .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("NEXTDNS_API_KEY=test_key_12345\nNEXTDNS_PROFILE_ID=testprofile\n")
    config_file = tmp_path / "config.json"
    config_file.write_text('{"blocklist": []}')
    return tmp_path


class TestDenylistList:
    """Tests for denylist list command."""

    @responses.activate
    def test_list_shows_domains(self, runner, temp_config_dir):
        """Test listing denylist domains."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(main, ["denylist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 0
        assert "example.com" in result.output

    @responses.activate
    def test_list_empty(self, runner, temp_config_dir):
        """Test listing empty denylist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        result = runner.invoke(main, ["denylist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()


class TestDenylistExport:
    """Tests for denylist export command."""

    @responses.activate
    def test_export_json(self, runner, temp_config_dir):
        """Test exporting denylist to JSON."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={
                "data": [
                    {"id": "example.com", "active": True},
                    {"id": "test.org", "active": False},
                ]
            },
            status=200,
        )

        result = runner.invoke(
            main,
            ["denylist", "export", "--format", "json", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["domain"] == "example.com"

    @responses.activate
    def test_export_csv(self, runner, temp_config_dir):
        """Test exporting denylist to CSV."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(
            main,
            ["denylist", "export", "--format", "csv", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "domain,active" in result.output
        assert "example.com" in result.output

    @responses.activate
    def test_export_to_file(self, runner, temp_config_dir, tmp_path):
        """Test exporting denylist to a file."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )

        output_file = tmp_path / "export.json"
        result = runner.invoke(
            main,
            [
                "denylist",
                "export",
                "-o",
                str(output_file),
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data[0]["domain"] == "example.com"


class TestDenylistImport:
    """Tests for denylist import command."""

    @responses.activate
    def test_import_json(self, runner, temp_config_dir, tmp_path):
        """Test importing domains from JSON file."""
        # Mock get denylist for checking existing
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # Mock get denylist for block() check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # Mock add domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )

        import_file = tmp_path / "import.json"
        import_file.write_text('[{"domain": "example.com", "active": true}]')

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Added: 1" in result.output

    @responses.activate
    def test_import_csv(self, runner, temp_config_dir, tmp_path):
        """Test importing domains from CSV file."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )

        import_file = tmp_path / "import.csv"
        import_file.write_text("domain,active\nexample.com,true\n")

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Added: 1" in result.output

    @responses.activate
    def test_import_plain_text(self, runner, temp_config_dir, tmp_path):
        """Test importing domains from plain text file."""
        # First GET for existing check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # GET for first block() call
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # POST for first domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )
        # GET for second block() call
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        # POST for second domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )

        import_file = tmp_path / "import.txt"
        import_file.write_text("# Comment\nexample.com\ntest.org\n")

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Added: 2" in result.output

    def test_import_dry_run(self, runner, temp_config_dir, tmp_path):
        """Test dry-run import (no API calls needed)."""
        import_file = tmp_path / "import.json"
        import_file.write_text('["example.com", "test.org"]')

        result = runner.invoke(
            main,
            [
                "denylist",
                "import",
                str(import_file),
                "--dry-run",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Would import" in result.output
        assert "example.com" in result.output

    @responses.activate
    def test_import_skips_existing(self, runner, temp_config_dir, tmp_path):
        """Test that import skips existing domains."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )

        import_file = tmp_path / "import.json"
        import_file.write_text('["example.com"]')

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Skipped (existing): 1" in result.output


class TestDenylistAdd:
    """Tests for denylist add command."""

    @responses.activate
    def test_add_single_domain(self, runner, temp_config_dir):
        """Test adding a single domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main, ["denylist", "add", "example.com", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 0
        assert "Added 1" in result.output

    @responses.activate
    def test_add_multiple_domains(self, runner, temp_config_dir):
        """Test adding multiple domains."""
        # GET for first block()
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # POST for first domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )
        # GET for second block()
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        # POST for second domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main,
            ["denylist", "add", "example.com", "test.org", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Added 2" in result.output

    def test_add_invalid_domain(self, runner, temp_config_dir):
        """Test adding invalid domain fails."""
        result = runner.invoke(
            main, ["denylist", "add", "http://invalid", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 1
        assert "invalid" in result.output.lower()


class TestDenylistRemove:
    """Tests for denylist remove command."""

    @responses.activate
    def test_remove_single_domain(self, runner, temp_config_dir):
        """Test removing a single domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/denylist/example.com",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main,
            ["denylist", "remove", "example.com", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Removed 1" in result.output

    @responses.activate
    def test_remove_multiple_domains(self, runner, temp_config_dir):
        """Test removing multiple domains."""
        # First GET
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={
                "data": [
                    {"id": "example.com", "active": True},
                    {"id": "test.org", "active": True},
                ]
            },
            status=200,
        )
        # DELETE first domain
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/denylist/example.com",
            json={"success": True},
            status=200,
        )
        # Second GET (cache refreshed)
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "test.org", "active": True}]},
            status=200,
        )
        # DELETE second domain
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/denylist/test.org",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main,
            [
                "denylist",
                "remove",
                "example.com",
                "test.org",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Removed 2" in result.output


class TestAllowlistList:
    """Tests for allowlist list command."""

    @responses.activate
    def test_list_shows_domains(self, runner, temp_config_dir):
        """Test listing allowlist domains."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(main, ["allowlist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 0
        assert "trusted.com" in result.output


class TestAllowlistExport:
    """Tests for allowlist export command."""

    @responses.activate
    def test_export_json(self, runner, temp_config_dir):
        """Test exporting allowlist to JSON."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(
            main,
            ["allowlist", "export", "--format", "json", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["domain"] == "trusted.com"


class TestAllowlistImport:
    """Tests for allowlist import command."""

    @responses.activate
    def test_import_json(self, runner, temp_config_dir, tmp_path):
        """Test importing domains to allowlist from JSON."""
        # GET for existing check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        # GET for allow() check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        # POST
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"success": True},
            status=200,
        )

        import_file = tmp_path / "import.json"
        import_file.write_text('["trusted.com"]')

        result = runner.invoke(
            main,
            ["allowlist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Added: 1" in result.output


class TestAllowlistAdd:
    """Tests for allowlist add command."""

    @responses.activate
    def test_add_single_domain(self, runner, temp_config_dir):
        """Test adding a single domain to allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main, ["allowlist", "add", "trusted.com", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 0
        assert "Added 1" in result.output

    @responses.activate
    def test_add_multiple_domains(self, runner, temp_config_dir):
        """Test adding multiple domains to allowlist."""
        # GET for first allow()
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        # POST for first domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"success": True},
            status=200,
        )
        # GET for second allow()
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )
        # POST for second domain
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main,
            ["allowlist", "add", "trusted.com", "safe.org", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Added 2" in result.output


class TestAllowlistRemove:
    """Tests for allowlist remove command."""

    @responses.activate
    def test_remove_single_domain(self, runner, temp_config_dir):
        """Test removing a single domain from allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/allowlist/trusted.com",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main,
            ["allowlist", "remove", "trusted.com", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Removed 1" in result.output


class TestHandleApiError:
    """Tests for _handle_api_error function."""

    def test_handles_timeout_error(self, runner, temp_config_dir):
        """Test handling of timeout error."""
        import responses as resp
        from requests.exceptions import Timeout

        with resp.RequestsMock() as rsps:
            rsps.add(
                resp.GET,
                f"{API_URL}/profiles/testprofile/denylist",
                body=Timeout("Connection timed out"),
            )

            result = runner.invoke(main, ["denylist", "list", "--config-dir", str(temp_config_dir)])

            assert result.exit_code == 1
            # Error is wrapped as "Failed to fetch denylist"
            assert "failed" in result.output.lower()

    def test_handles_connection_error(self, runner, temp_config_dir):
        """Test handling of connection error."""
        import responses as resp
        from requests.exceptions import ConnectionError

        with resp.RequestsMock() as rsps:
            rsps.add(
                resp.GET,
                f"{API_URL}/profiles/testprofile/denylist",
                body=ConnectionError("Connection refused"),
            )

            result = runner.invoke(main, ["denylist", "list", "--config-dir", str(temp_config_dir)])

            assert result.exit_code == 1
            # Error is wrapped as "Failed to fetch denylist"
            assert "failed" in result.output.lower()

    @responses.activate
    def test_handles_http_error(self, runner, temp_config_dir):
        """Test handling of HTTP error."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"error": "Unauthorized"},
            status=401,
        )

        result = runner.invoke(main, ["denylist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 1

    def test_handles_permission_error(self, runner, tmp_path):
        """Test handling of permission error when reading config."""
        # Create config dir without .env file to trigger FileNotFoundError
        result = runner.invoke(main, ["denylist", "list", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1

    def test_handles_value_error(self, runner, tmp_path):
        """Test handling of value error."""
        # Create invalid config file
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=\nNEXTDNS_PROFILE_ID=\n")

        result = runner.invoke(main, ["denylist", "list", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1


class TestHandleFileError:
    """Tests for _handle_file_error function."""

    def test_handles_unicode_decode_error(self, runner, temp_config_dir, tmp_path):
        """Test handling of unicode decode error."""
        import_file = tmp_path / "import.txt"
        # Write binary data that will cause decode error
        import_file.write_bytes(b"\x80\x81\x82")

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        # The file reading happens before API calls, so this may fail with encoding error
        assert result.exit_code == 1 or "encoding" in result.output.lower()


class TestParseImportFileEdgeCases:
    """Tests for edge cases in _parse_import_file."""

    def test_import_json_with_domains_key(self, runner, temp_config_dir, tmp_path):
        """Test importing JSON file with 'domains' key format."""
        import_file = tmp_path / "import.json"
        import_file.write_text('{"domains": ["example.com", "test.org"]}')

        result = runner.invoke(
            main,
            [
                "denylist",
                "import",
                str(import_file),
                "--dry-run",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Would import 2 domains" in result.output

    def test_import_inactive_domains_filtered(self, runner, temp_config_dir, tmp_path):
        """Test that inactive domains are filtered out."""
        import_file = tmp_path / "import.json"
        import_file.write_text(
            '[{"domain": "active.com", "active": true}, {"domain": "inactive.com", "active": false}]'
        )

        result = runner.invoke(
            main,
            [
                "denylist",
                "import",
                str(import_file),
                "--dry-run",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Would import 1 domain" in result.output
        assert "active.com" in result.output
        assert "inactive.com" not in result.output

    def test_import_empty_file(self, runner, temp_config_dir, tmp_path):
        """Test importing an empty file."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("")

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "No domains found" in result.output

    def test_import_with_invalid_domains(self, runner, temp_config_dir, tmp_path):
        """Test importing file with mix of valid and invalid domains."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("valid.com\nhttp://invalid\ntest.org\n")

        result = runner.invoke(
            main,
            [
                "denylist",
                "import",
                str(import_file),
                "--dry-run",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Invalid domains (skipped)" in result.output
        assert "Would import 2 domains" in result.output

    def test_import_only_invalid_domains(self, runner, temp_config_dir, tmp_path):
        """Test importing file with only invalid domains."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("http://invalid\nftp://also_invalid\n")

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 1
        assert "No valid domains" in result.output

    def test_import_csv_inactive_filtered(self, runner, temp_config_dir, tmp_path):
        """Test that inactive CSV domains are filtered."""
        import_file = tmp_path / "import.csv"
        import_file.write_text("domain,active\nactive.com,true\ninactive.com,false\n")

        result = runner.invoke(
            main,
            [
                "denylist",
                "import",
                str(import_file),
                "--dry-run",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Would import 1 domain" in result.output


class TestDenylistApiFailures:
    """Tests for API failure scenarios in denylist commands."""

    @responses.activate
    def test_list_api_server_error(self, runner, temp_config_dir):
        """Test denylist list when API returns server error."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"error": "Internal server error"},
            status=500,
        )

        result = runner.invoke(main, ["denylist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 1

    @responses.activate
    def test_export_api_server_error(self, runner, temp_config_dir):
        """Test denylist export when API returns server error."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"error": "Internal server error"},
            status=500,
        )

        result = runner.invoke(main, ["denylist", "export", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 1

    @responses.activate
    def test_add_domain_already_exists(self, runner, temp_config_dir):
        """Test adding domain that already exists."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(
            main, ["denylist", "add", "example.com", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 0
        assert "already exists" in result.output or "skipped" in result.output.lower()

    @responses.activate
    def test_add_domain_api_failure(self, runner, temp_config_dir):
        """Test adding domain when API fails."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"error": "Server error"},
            status=500,
        )

        result = runner.invoke(
            main, ["denylist", "add", "example.com", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 1
        assert "failed" in result.output.lower()

    @responses.activate
    def test_remove_domain_not_found(self, runner, temp_config_dir):
        """Test removing domain that doesn't exist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        result = runner.invoke(
            main,
            ["denylist", "remove", "example.com", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestAllowlistApiFailures:
    """Tests for API failure scenarios in allowlist commands."""

    @responses.activate
    def test_list_api_server_error(self, runner, temp_config_dir):
        """Test allowlist list when API returns server error."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"error": "Internal server error"},
            status=500,
        )

        result = runner.invoke(main, ["allowlist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 1

    @responses.activate
    def test_list_empty(self, runner, temp_config_dir):
        """Test listing empty allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        result = runner.invoke(main, ["allowlist", "list", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    @responses.activate
    def test_export_api_server_error(self, runner, temp_config_dir):
        """Test allowlist export when API returns server error."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"error": "Internal server error"},
            status=500,
        )

        result = runner.invoke(main, ["allowlist", "export", "--config-dir", str(temp_config_dir)])

        assert result.exit_code == 1

    @responses.activate
    def test_export_csv_format(self, runner, temp_config_dir):
        """Test exporting allowlist to CSV."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(
            main,
            ["allowlist", "export", "--format", "csv", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "domain,active" in result.output
        assert "trusted.com" in result.output

    @responses.activate
    def test_export_to_file(self, runner, temp_config_dir, tmp_path):
        """Test exporting allowlist to a file."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )

        output_file = tmp_path / "export.json"
        result = runner.invoke(
            main,
            [
                "allowlist",
                "export",
                "-o",
                str(output_file),
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

    def test_import_dry_run(self, runner, temp_config_dir, tmp_path):
        """Test allowlist dry-run import."""
        import_file = tmp_path / "import.json"
        import_file.write_text('["trusted.com", "safe.org"]')

        result = runner.invoke(
            main,
            [
                "allowlist",
                "import",
                str(import_file),
                "--dry-run",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Would import" in result.output

    def test_import_empty_file(self, runner, temp_config_dir, tmp_path):
        """Test allowlist import with empty file."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("")

        result = runner.invoke(
            main,
            ["allowlist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "No domains found" in result.output

    def test_import_invalid_domains(self, runner, temp_config_dir, tmp_path):
        """Test allowlist import with invalid domains."""
        import_file = tmp_path / "import.txt"
        import_file.write_text("http://invalid\n")

        result = runner.invoke(
            main,
            ["allowlist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 1
        assert "No valid domains" in result.output

    @responses.activate
    def test_import_skips_existing(self, runner, temp_config_dir, tmp_path):
        """Test that allowlist import skips existing domains."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )

        import_file = tmp_path / "import.json"
        import_file.write_text('["trusted.com"]')

        result = runner.invoke(
            main,
            ["allowlist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Skipped (existing): 1" in result.output

    @responses.activate
    def test_add_domain_already_exists(self, runner, temp_config_dir):
        """Test adding domain that already exists to allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "trusted.com", "active": True}]},
            status=200,
        )

        result = runner.invoke(
            main, ["allowlist", "add", "trusted.com", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 0
        assert "already exists" in result.output or "skipped" in result.output.lower()

    @responses.activate
    def test_add_domain_api_failure(self, runner, temp_config_dir):
        """Test adding domain when API fails."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"error": "Server error"},
            status=500,
        )

        result = runner.invoke(
            main, ["allowlist", "add", "trusted.com", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 1
        assert "failed" in result.output.lower()

    def test_add_invalid_domain(self, runner, temp_config_dir):
        """Test adding invalid domain to allowlist."""
        result = runner.invoke(
            main, ["allowlist", "add", "http://invalid", "--config-dir", str(temp_config_dir)]
        )

        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    @responses.activate
    def test_remove_domain_not_found(self, runner, temp_config_dir):
        """Test removing domain that doesn't exist from allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        result = runner.invoke(
            main,
            ["allowlist", "remove", "trusted.com", "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    @responses.activate
    def test_remove_multiple_domains(self, runner, temp_config_dir):
        """Test removing multiple domains from allowlist."""
        # First GET
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={
                "data": [
                    {"id": "trusted.com", "active": True},
                    {"id": "safe.org", "active": True},
                ]
            },
            status=200,
        )
        # DELETE first domain
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/allowlist/trusted.com",
            json={"success": True},
            status=200,
        )
        # Second GET (cache refreshed)
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "safe.org", "active": True}]},
            status=200,
        )
        # DELETE second domain
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/allowlist/safe.org",
            json={"success": True},
            status=200,
        )

        result = runner.invoke(
            main,
            [
                "allowlist",
                "remove",
                "trusted.com",
                "safe.org",
                "--config-dir",
                str(temp_config_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Removed 2" in result.output


class TestDenylistImportApiFailures:
    """Tests for API failures during denylist import."""

    @responses.activate
    def test_import_api_failure_during_add(self, runner, temp_config_dir, tmp_path):
        """Test import when API fails during domain addition."""
        # GET for existing check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # GET for block() check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # POST fails
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"error": "Server error"},
            status=500,
        )

        import_file = tmp_path / "import.json"
        import_file.write_text('["example.com"]')

        result = runner.invoke(
            main,
            ["denylist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Failed: 1" in result.output


class TestAllowlistImportApiFailures:
    """Tests for API failures during allowlist import."""

    @responses.activate
    def test_import_api_failure_during_add(self, runner, temp_config_dir, tmp_path):
        """Test import when API fails during domain addition."""
        # GET for existing check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        # GET for allow() check
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        # POST fails
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"error": "Server error"},
            status=500,
        )

        import_file = tmp_path / "import.json"
        import_file.write_text('["trusted.com"]')

        result = runner.invoke(
            main,
            ["allowlist", "import", str(import_file), "--config-dir", str(temp_config_dir)],
        )

        assert result.exit_code == 0
        assert "Failed: 1" in result.output
