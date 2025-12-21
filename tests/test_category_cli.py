"""Tests for category CLI commands."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nextdns_blocker.category_cli import category_cli


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def config_with_categories(tmp_path):
    """Create a config.json with categories."""
    config = {
        "version": "1.0",
        "categories": [
            {
                "id": "social-media",
                "description": "Social networks",
                "unblock_delay": "4h",
                "domains": ["facebook.com", "twitter.com", "instagram.com"],
            },
            {
                "id": "streaming",
                "description": "Video streaming",
                "domains": ["netflix.com", "youtube.com"],
            },
        ],
        "blocklist": [],
        "allowlist": [],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config, indent=2))
    return tmp_path


@pytest.fixture
def config_empty_categories(tmp_path):
    """Create a config.json with empty categories."""
    config = {
        "version": "1.0",
        "categories": [],
        "blocklist": [{"domain": "example.com"}],
        "allowlist": [],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config, indent=2))
    return tmp_path


@pytest.fixture
def config_no_categories(tmp_path):
    """Create a config.json without categories key."""
    config = {
        "version": "1.0",
        "blocklist": [{"domain": "example.com"}],
        "allowlist": [],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config, indent=2))
    return tmp_path


class TestCategoryList:
    """Tests for category list command."""

    def test_list_categories(self, runner, config_with_categories):
        """Test listing categories."""
        result = runner.invoke(category_cli, ["list", "--config-dir", str(config_with_categories)])
        assert result.exit_code == 0
        assert "social-media" in result.output
        assert "streaming" in result.output
        assert "Social networks" in result.output

    def test_list_empty_categories(self, runner, config_empty_categories):
        """Test listing when no categories exist."""
        result = runner.invoke(category_cli, ["list", "--config-dir", str(config_empty_categories)])
        assert result.exit_code == 0
        assert "No categories configured" in result.output

    def test_list_no_categories_key(self, runner, config_no_categories):
        """Test listing when categories key doesn't exist."""
        result = runner.invoke(category_cli, ["list", "--config-dir", str(config_no_categories)])
        assert result.exit_code == 0
        assert "No categories configured" in result.output

    def test_list_config_not_found(self, runner, tmp_path):
        """Test listing when config file doesn't exist."""
        result = runner.invoke(category_cli, ["list", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Config file not found" in result.output


class TestCategoryShow:
    """Tests for category show command."""

    def test_show_category(self, runner, config_with_categories):
        """Test showing category details."""
        result = runner.invoke(
            category_cli,
            ["show", "social-media", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0
        assert "social-media" in result.output
        assert "Social networks" in result.output
        assert "facebook.com" in result.output
        assert "4h" in result.output

    def test_show_category_not_found(self, runner, config_with_categories):
        """Test showing non-existent category."""
        result = runner.invoke(
            category_cli,
            ["show", "nonexistent", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_show_case_insensitive(self, runner, config_with_categories):
        """Test show is case-insensitive."""
        result = runner.invoke(
            category_cli,
            ["show", "SOCIAL-MEDIA", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0
        assert "social-media" in result.output


class TestCategoryAdd:
    """Tests for category add command."""

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_add_domain(self, mock_panic, runner, config_with_categories):
        """Test adding domain to category."""
        result = runner.invoke(
            category_cli,
            ["add", "social-media", "tiktok.com", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0
        assert "Added" in result.output
        assert "tiktok.com" in result.output

        # Verify domain was added
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        social_cat = next(c for c in config["categories"] if c["id"] == "social-media")
        assert "tiktok.com" in social_cat["domains"]

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_add_domain_already_exists(self, mock_panic, runner, config_with_categories):
        """Test adding domain that already exists."""
        result = runner.invoke(
            category_cli,
            ["add", "social-media", "facebook.com", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0
        assert "already exists" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_add_domain_invalid_format(self, mock_panic, runner, config_with_categories):
        """Test adding invalid domain format."""
        result = runner.invoke(
            category_cli,
            ["add", "social-media", "invalid domain!", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "Invalid domain format" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_add_domain_category_not_found(self, mock_panic, runner, config_with_categories):
        """Test adding domain to non-existent category."""
        result = runner.invoke(
            category_cli,
            ["add", "nonexistent", "test.com", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=True)
    def test_add_domain_panic_mode(self, mock_panic, runner, config_with_categories):
        """Test adding domain is blocked during panic mode."""
        result = runner.invoke(
            category_cli,
            ["add", "social-media", "tiktok.com", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "panic mode" in result.output


class TestCategoryRemove:
    """Tests for category remove command."""

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_remove_domain(self, mock_panic, runner, config_with_categories):
        """Test removing domain from category."""
        result = runner.invoke(
            category_cli,
            [
                "remove",
                "social-media",
                "facebook.com",
                "-y",
                "--config-dir",
                str(config_with_categories),
            ],
        )
        assert result.exit_code == 0
        assert "Removed" in result.output

        # Verify domain was removed
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        social_cat = next(c for c in config["categories"] if c["id"] == "social-media")
        assert "facebook.com" not in social_cat["domains"]

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_remove_domain_not_found(self, mock_panic, runner, config_with_categories):
        """Test removing domain that doesn't exist."""
        result = runner.invoke(
            category_cli,
            [
                "remove",
                "social-media",
                "notexist.com",
                "-y",
                "--config-dir",
                str(config_with_categories),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_remove_domain_confirmation(self, mock_panic, runner, config_with_categories):
        """Test remove requires confirmation."""
        result = runner.invoke(
            category_cli,
            ["remove", "social-media", "facebook.com", "--config-dir", str(config_with_categories)],
            input="n\n",
        )
        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # Verify domain was NOT removed
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        social_cat = next(c for c in config["categories"] if c["id"] == "social-media")
        assert "facebook.com" in social_cat["domains"]


class TestCategoryCreate:
    """Tests for category create command."""

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_create_category(self, mock_panic, runner, config_with_categories):
        """Test creating new category."""
        result = runner.invoke(
            category_cli,
            ["create", "gaming", "-d", "Gaming sites", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0
        assert "Created category 'gaming'" in result.output

        # Verify category was created
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        gaming_cat = next((c for c in config["categories"] if c["id"] == "gaming"), None)
        assert gaming_cat is not None
        assert gaming_cat["description"] == "Gaming sites"

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_create_category_with_delay(self, mock_panic, runner, config_with_categories):
        """Test creating category with delay."""
        result = runner.invoke(
            category_cli,
            ["create", "gambling", "--delay", "never", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0

        # Verify delay was set
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        gambling_cat = next((c for c in config["categories"] if c["id"] == "gambling"), None)
        assert gambling_cat["unblock_delay"] == "never"

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_create_category_invalid_id(self, mock_panic, runner, config_with_categories):
        """Test creating category with invalid ID."""
        result = runner.invoke(
            category_cli,
            ["create", "Invalid-ID", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "Invalid category ID" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_create_category_already_exists(self, mock_panic, runner, config_with_categories):
        """Test creating category that already exists."""
        result = runner.invoke(
            category_cli,
            ["create", "social-media", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_create_category_invalid_delay(self, mock_panic, runner, config_with_categories):
        """Test creating category with invalid delay."""
        result = runner.invoke(
            category_cli,
            ["create", "gaming", "--delay", "invalid", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "Invalid delay format" in result.output


class TestCategoryDelete:
    """Tests for category delete command."""

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_delete_category(self, mock_panic, runner, config_with_categories):
        """Test deleting category."""
        result = runner.invoke(
            category_cli,
            ["delete", "streaming", "-y", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 0
        assert "Deleted category 'streaming'" in result.output

        # Verify category was deleted
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        streaming_cat = next((c for c in config["categories"] if c["id"] == "streaming"), None)
        assert streaming_cat is None

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_delete_category_not_found(self, mock_panic, runner, config_with_categories):
        """Test deleting non-existent category."""
        result = runner.invoke(
            category_cli,
            ["delete", "nonexistent", "-y", "--config-dir", str(config_with_categories)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    def test_delete_category_confirmation(self, mock_panic, runner, config_with_categories):
        """Test delete requires confirmation."""
        result = runner.invoke(
            category_cli,
            ["delete", "streaming", "--config-dir", str(config_with_categories)],
            input="n\n",
        )
        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # Verify category was NOT deleted
        config_file = config_with_categories / "config.json"
        config = json.loads(config_file.read_text())
        streaming_cat = next((c for c in config["categories"] if c["id"] == "streaming"), None)
        assert streaming_cat is not None
