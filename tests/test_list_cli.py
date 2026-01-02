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
        assert "Added 1 domain" in result.output

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
        assert "Added 2 domain" in result.output

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
        assert "Removed 1 domain" in result.output

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
        assert "Removed 2 domain" in result.output


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
        assert "Added 1 domain" in result.output

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
        assert "Added 2 domain" in result.output


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
        assert "Removed 1 domain" in result.output
