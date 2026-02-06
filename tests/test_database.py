"""Tests for the SQLite database module."""

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from nextdns_blocker import database as db


class TestDatabaseConnection:
    """Tests for database connection management."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield test_db_path
            db.close_connection()

    def test_get_connection_returns_connection(self):
        """Should return a valid SQLite connection."""
        conn = db.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

    def test_connection_has_wal_mode(self):
        """Should use WAL journal mode for better concurrency."""
        conn = db.get_connection()
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

    def test_connection_has_foreign_keys(self):
        """Should have foreign keys enabled."""
        conn = db.get_connection()
        cursor = conn.execute("PRAGMA foreign_keys")
        enabled = cursor.fetchone()[0]
        assert enabled == 1

    def test_close_connection(self):
        """Should close the thread-local connection."""
        _ = db.get_connection()
        db.close_connection()
        assert not hasattr(db._local, "connection") or db._local.connection is None


class TestSchemaManagement:
    """Tests for schema initialization and versioning."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            yield test_db_path
            db.close_connection()

    def test_init_database_creates_tables(self, use_temp_database):
        """Should create all required tables."""
        db.init_database()
        conn = db.get_connection()

        # Check expected tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor}

        expected_tables = {
            "config",
            "blocked_domains",
            "allowed_domains",
            "categories",
            "category_domains",
            "nextdns_categories",
            "nextdns_services",
            "schedules",
            "pending_actions",
            "unlock_requests",
            "retry_queue",
            "audit_log",
            "daily_stats",
            "pin_protection",
        }

        assert expected_tables.issubset(tables)

    def test_init_database_is_idempotent(self, use_temp_database):
        """Calling init_database multiple times should be safe."""
        db.init_database()
        db.init_database()
        db.init_database()
        # Should not raise any errors


class TestConfigOperations:
    """Tests for config key-value storage."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_set_and_get_string_config(self):
        """Should store and retrieve string values."""
        db.set_config("api_key", "test-key-123")
        value = db.get_config("api_key")
        assert value == "test-key-123"

    def test_set_and_get_dict_config(self):
        """Should store and retrieve dict values as JSON."""
        config_dict = {"enabled": True, "timeout": 30}
        db.set_config("settings", config_dict)
        value = db.get_config("settings")
        assert value == config_dict

    def test_set_and_get_list_config(self):
        """Should store and retrieve list values as JSON."""
        config_list = ["a", "b", "c"]
        db.set_config("items", config_list)
        value = db.get_config("items")
        assert value == config_list

    def test_get_config_with_default(self):
        """Should return default when key doesn't exist."""
        value = db.get_config("nonexistent", default="fallback")
        assert value == "fallback"

    def test_get_config_returns_none_by_default(self):
        """Should return None when key doesn't exist and no default given."""
        value = db.get_config("nonexistent")
        assert value is None

    def test_get_all_config(self):
        """Should return all config as dictionary."""
        db.set_config("key1", "value1")
        db.set_config("key2", {"nested": True})

        all_config = db.get_all_config()
        assert all_config["key1"] == "value1"
        assert all_config["key2"] == {"nested": True}

    def test_delete_config(self):
        """Should delete a config key."""
        db.set_config("to_delete", "value")
        assert db.get_config("to_delete") == "value"

        result = db.delete_config("to_delete")
        assert result is True
        assert db.get_config("to_delete") is None

    def test_delete_nonexistent_config(self):
        """Should return False when deleting nonexistent key."""
        result = db.delete_config("nonexistent")
        assert result is False

    def test_update_config_value(self):
        """Should update existing config value."""
        db.set_config("key", "original")
        db.set_config("key", "updated")
        value = db.get_config("key")
        assert value == "updated"


class TestBlockedDomainsOperations:
    """Tests for blocked domains CRUD operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_blocked_domain(self):
        """Should add a domain to the blocklist."""
        row_id = db.add_blocked_domain("example.com", description="Test domain")
        assert row_id > 0

    def test_get_blocked_domain(self):
        """Should retrieve a blocked domain by name."""
        db.add_blocked_domain(
            "example.com",
            description="Test domain",
            locked=True,
            unblock_delay="24h",
        )

        domain = db.get_blocked_domain("example.com")
        assert domain is not None
        assert domain["domain"] == "example.com"
        assert domain["description"] == "Test domain"
        assert domain["locked"] == 1
        assert domain["unblock_delay"] == "24h"

    def test_get_blocked_domain_not_found(self):
        """Should return None for nonexistent domain."""
        domain = db.get_blocked_domain("nonexistent.com")
        assert domain is None

    def test_is_domain_blocked(self):
        """Should check if domain is blocked."""
        assert db.is_domain_blocked("example.com") is False
        db.add_blocked_domain("example.com")
        assert db.is_domain_blocked("example.com") is True

    def test_remove_blocked_domain(self):
        """Should remove a blocked domain."""
        db.add_blocked_domain("example.com")
        assert db.is_domain_blocked("example.com") is True

        result = db.remove_blocked_domain("example.com")
        assert result is True
        assert db.is_domain_blocked("example.com") is False

    def test_remove_nonexistent_domain(self):
        """Should return False when removing nonexistent domain."""
        result = db.remove_blocked_domain("nonexistent.com")
        assert result is False

    def test_get_all_blocked_domains(self):
        """Should return all blocked domains sorted by domain."""
        db.add_blocked_domain("zebra.com")
        db.add_blocked_domain("apple.com")
        db.add_blocked_domain("mango.com")

        domains = db.get_all_blocked_domains()
        assert len(domains) == 3
        assert domains[0]["domain"] == "apple.com"
        assert domains[1]["domain"] == "mango.com"
        assert domains[2]["domain"] == "zebra.com"

    def test_upsert_blocked_domain(self):
        """Should update existing domain on conflict."""
        db.add_blocked_domain("example.com", description="Original")
        db.add_blocked_domain("example.com", description="Updated", locked=True)

        domain = db.get_blocked_domain("example.com")
        assert domain["description"] == "Updated"
        assert domain["locked"] == 1


class TestAllowedDomainsOperations:
    """Tests for allowed domains CRUD operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_allowed_domain(self):
        """Should add a domain to the allowlist."""
        row_id = db.add_allowed_domain("example.com", description="Test domain")
        assert row_id > 0

    def test_get_allowed_domain(self):
        """Should retrieve an allowed domain by name."""
        db.add_allowed_domain(
            "example.com",
            description="Test domain",
            suppress_subdomain_warning=True,
        )

        domain = db.get_allowed_domain("example.com")
        assert domain is not None
        assert domain["domain"] == "example.com"
        assert domain["description"] == "Test domain"
        assert domain["suppress_subdomain_warning"] == 1

    def test_is_domain_allowed(self):
        """Should check if domain is allowed."""
        assert db.is_domain_allowed("example.com") is False
        db.add_allowed_domain("example.com")
        assert db.is_domain_allowed("example.com") is True

    def test_remove_allowed_domain(self):
        """Should remove an allowed domain."""
        db.add_allowed_domain("example.com")
        result = db.remove_allowed_domain("example.com")
        assert result is True
        assert db.is_domain_allowed("example.com") is False

    def test_get_all_allowed_domains(self):
        """Should return all allowed domains."""
        db.add_allowed_domain("a.com")
        db.add_allowed_domain("b.com")

        domains = db.get_all_allowed_domains()
        assert len(domains) == 2


class TestPendingActionsOperations:
    """Tests for pending actions queue operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_and_get_pending_action(self):
        """Should add and retrieve a pending action."""
        now = datetime.now().isoformat()
        later = "2099-12-31T23:59:59"

        db.add_pending_action(
            action_id="pnd_test_123",
            action="unblock",
            domain="example.com",
            created_at=now,
            execute_at=later,
            delay="4h",
        )

        action = db.get_pending_action("pnd_test_123")
        assert action is not None
        assert action["id"] == "pnd_test_123"
        assert action["action"] == "unblock"
        assert action["domain"] == "example.com"
        assert action["status"] == "pending"

    def test_get_pending_actions_by_status(self):
        """Should filter actions by status."""
        now = datetime.now().isoformat()

        db.add_pending_action("pnd_1", "unblock", "a.com", now, "2099-12-31", "4h")
        db.add_pending_action("pnd_2", "unblock", "b.com", now, "2099-12-31", "4h")

        db.update_pending_action_status("pnd_2", "executed")

        pending = db.get_pending_actions("pending")
        assert len(pending) == 1
        assert pending[0]["id"] == "pnd_1"

    def test_get_executable_pending_actions(self):
        """Should return actions ready to execute."""
        now = datetime.now().isoformat()
        past = "2000-01-01T00:00:00"
        future = "2099-12-31T23:59:59"

        db.add_pending_action("pnd_past", "unblock", "past.com", now, past, "4h")
        db.add_pending_action("pnd_future", "unblock", "future.com", now, future, "4h")

        executable = db.get_executable_pending_actions()
        assert len(executable) == 1
        assert executable[0]["id"] == "pnd_past"

    def test_cancel_pending_action(self):
        """Should mark action as cancelled."""
        now = datetime.now().isoformat()
        db.add_pending_action("pnd_cancel", "unblock", "example.com", now, "2099-12-31", "4h")

        result = db.cancel_pending_action("pnd_cancel")
        assert result is True

        action = db.get_pending_action("pnd_cancel")
        assert action["status"] == "cancelled"
        assert action["cancelled_at"] is not None


class TestUnlockRequestsOperations:
    """Tests for unlock requests operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_and_get_unlock_request(self):
        """Should add and retrieve an unlock request."""
        now = datetime.now().isoformat()
        later = "2099-12-31T23:59:59"

        db.add_unlock_request(
            request_id="unlock_test_123",
            item_type="category",
            item_id="gambling",
            created_at=now,
            execute_at=later,
            delay_hours=48,
            reason="Test reason",
        )

        request = db.get_unlock_request("unlock_test_123")
        assert request is not None
        assert request["id"] == "unlock_test_123"
        assert request["item_type"] == "category"
        assert request["item_id"] == "gambling"
        assert request["delay_hours"] == 48
        assert request["reason"] == "Test reason"
        assert request["status"] == "pending"

    def test_get_executable_unlock_requests(self):
        """Should return requests ready to execute."""
        now = datetime.now().isoformat()
        past = "2000-01-01T00:00:00"
        future = "2099-12-31T23:59:59"

        db.add_unlock_request("unlock_past", "category", "porn", now, past, 48)
        db.add_unlock_request("unlock_future", "category", "gambling", now, future, 48)

        executable = db.get_executable_unlock_requests()
        assert len(executable) == 1
        assert executable[0]["id"] == "unlock_past"


class TestRetryQueueOperations:
    """Tests for retry queue operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_and_get_retry_entry(self):
        """Should add and retrieve a retry entry."""
        now = datetime.now().isoformat()

        db.add_retry_entry(
            entry_id="retry_123",
            domain="example.com",
            action="block",
            error_type="rate_limit",
            error_msg="Too many requests",
            created_at=now,
            next_retry_at=now,
            attempt_count=1,
            backoff_seconds=60,
        )

        entry = db.get_retry_entry("retry_123")
        assert entry is not None
        assert entry["domain"] == "example.com"
        assert entry["action"] == "block"
        assert entry["error_type"] == "rate_limit"
        assert entry["attempt_count"] == 1

    def test_get_retryable_entries(self):
        """Should return entries ready to retry."""
        now = datetime.now().isoformat()
        past = "2000-01-01T00:00:00"
        future = "2099-12-31T23:59:59"

        db.add_retry_entry("retry_past", "past.com", "block", "error", "msg", now, past)
        db.add_retry_entry("retry_future", "future.com", "block", "error", "msg", now, future)

        retryable = db.get_retryable_entries()
        assert len(retryable) == 1
        assert retryable[0]["id"] == "retry_past"

    def test_remove_retry_entry(self):
        """Should remove a retry entry."""
        now = datetime.now().isoformat()
        db.add_retry_entry("retry_del", "example.com", "block", "error", "msg", now, now)

        result = db.remove_retry_entry("retry_del")
        assert result is True
        assert db.get_retry_entry("retry_del") is None

    def test_clear_retry_queue(self):
        """Should clear all retry entries."""
        now = datetime.now().isoformat()
        db.add_retry_entry("retry_1", "a.com", "block", "error", "msg", now, now)
        db.add_retry_entry("retry_2", "b.com", "block", "error", "msg", now, now)

        count = db.clear_retry_queue()
        assert count == 2

        retryable = db.get_retryable_entries()
        assert len(retryable) == 0


class TestAuditLogOperations:
    """Tests for audit log operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_audit_log(self):
        """Should add an audit log entry."""
        row_id = db.add_audit_log(
            event_type="BLOCK",
            domain="example.com",
            metadata={"source": "cli"},
        )
        assert row_id > 0

    def test_get_audit_logs(self):
        """Should retrieve audit logs."""
        db.add_audit_log("BLOCK", "a.com")
        db.add_audit_log("UNBLOCK", "b.com")

        logs = db.get_audit_logs()
        assert len(logs) == 2

    def test_get_audit_logs_by_event_type(self):
        """Should filter logs by event type."""
        db.add_audit_log("BLOCK", "a.com")
        db.add_audit_log("UNBLOCK", "b.com")
        db.add_audit_log("BLOCK", "c.com")

        blocks = db.get_audit_logs(event_type="BLOCK")
        assert len(blocks) == 2

    def test_count_audit_logs(self):
        """Should count audit logs."""
        db.add_audit_log("BLOCK", "a.com")
        db.add_audit_log("BLOCK", "b.com")
        db.add_audit_log("UNBLOCK", "c.com")

        total = db.count_audit_logs()
        assert total == 3

        blocks = db.count_audit_logs(event_type="BLOCK")
        assert blocks == 2


class TestDailyStatsOperations:
    """Tests for daily statistics operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_increment_daily_stat(self):
        """Should increment a daily statistic."""
        db.increment_daily_stat("2024-01-15", "blocks", 5)

        stats = db.get_daily_stats("2024-01-15")
        assert stats is not None
        assert stats["blocks"] == 5

    def test_increment_daily_stat_multiple_times(self):
        """Should accumulate increments."""
        db.increment_daily_stat("2024-01-15", "blocks", 2)
        db.increment_daily_stat("2024-01-15", "blocks", 3)

        stats = db.get_daily_stats("2024-01-15")
        assert stats["blocks"] == 5

    def test_increment_invalid_stat_raises(self):
        """Should raise error for invalid stat name."""
        with pytest.raises(ValueError, match="Invalid stat name"):
            db.increment_daily_stat("2024-01-15", "invalid_stat")

    def test_get_stats_range(self):
        """Should return stats for date range."""
        db.increment_daily_stat("2024-01-14", "blocks", 1)
        db.increment_daily_stat("2024-01-15", "blocks", 2)
        db.increment_daily_stat("2024-01-16", "blocks", 3)

        stats = db.get_stats_range("2024-01-14", "2024-01-16")
        assert len(stats) == 3


class TestCategoryOperations:
    """Tests for category CRUD operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_category_with_domains(self):
        """Should add a category with associated domains."""
        db.add_category(
            category_id="social",
            description="Social media sites",
            domains=["facebook.com", "twitter.com", "instagram.com"],
        )

        category = db.get_category("social")
        assert category is not None
        assert category["id"] == "social"
        assert category["description"] == "Social media sites"
        assert len(category["domains"]) == 3
        assert "facebook.com" in category["domains"]

    def test_get_all_categories(self):
        """Should return all categories with domains."""
        db.add_category("cat1", domains=["a.com"])
        db.add_category("cat2", domains=["b.com", "c.com"])

        categories = db.get_all_categories()
        assert len(categories) == 2

    def test_add_domain_to_category(self):
        """Should add a domain to existing category."""
        db.add_category("social", domains=["facebook.com"])

        result = db.add_domain_to_category("social", "twitter.com")
        assert result is True

        category = db.get_category("social")
        assert "twitter.com" in category["domains"]

    def test_remove_domain_from_category(self):
        """Should remove a domain from category."""
        db.add_category("social", domains=["facebook.com", "twitter.com"])

        result = db.remove_domain_from_category("social", "twitter.com")
        assert result is True

        category = db.get_category("social")
        assert "twitter.com" not in category["domains"]

    def test_remove_category(self):
        """Should remove a category."""
        db.add_category("to_delete", domains=["example.com"])

        result = db.remove_category("to_delete")
        assert result is True
        assert db.get_category("to_delete") is None


class TestScheduleOperations:
    """Tests for schedule template operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_add_and_get_schedule(self):
        """Should add and retrieve a schedule."""
        schedule_data = {
            "available_hours": ["12:00-14:00", "18:00-22:00"],
            "blocked_days": ["Saturday", "Sunday"],
        }

        db.add_schedule("work_hours", schedule_data)

        schedule = db.get_schedule("work_hours")
        assert schedule is not None
        assert schedule["schedule_data"] == schedule_data

    def test_get_all_schedules(self):
        """Should return all schedules as dict keyed by name."""
        db.add_schedule("schedule_1", {"hours": ["09:00-17:00"]})
        db.add_schedule("schedule_2", {"hours": ["18:00-22:00"]})

        schedules = db.get_all_schedules()
        assert "schedule_1" in schedules
        assert "schedule_2" in schedules

    def test_remove_schedule(self):
        """Should remove a schedule."""
        db.add_schedule("to_delete", {"hours": []})

        result = db.remove_schedule("to_delete")
        assert result is True
        assert db.get_schedule("to_delete") is None


class TestNextDNSOperations:
    """Tests for NextDNS categories and services operations."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_set_and_get_nextdns_category(self):
        """Should set and retrieve NextDNS category config."""
        db.set_nextdns_category(
            category_id="porn",
            description="Adult content",
            unblock_delay="never",
            locked=True,
        )

        category = db.get_nextdns_category("porn")
        assert category is not None
        assert category["id"] == "porn"
        assert category["unblock_delay"] == "never"
        assert category["locked"] == 1

    def test_get_all_nextdns_categories(self):
        """Should return all NextDNS categories."""
        db.set_nextdns_category("porn")
        db.set_nextdns_category("gambling")

        categories = db.get_all_nextdns_categories()
        assert len(categories) == 2

    def test_set_and_get_nextdns_service(self):
        """Should set and retrieve NextDNS service config."""
        db.set_nextdns_service(
            service_id="facebook",
            description="Facebook and Instagram",
            unblock_delay="4h",
        )

        service = db.get_nextdns_service("facebook")
        assert service is not None
        assert service["id"] == "facebook"
        assert service["unblock_delay"] == "4h"

    def test_get_all_nextdns_services(self):
        """Should return all NextDNS services."""
        db.set_nextdns_service("facebook")
        db.set_nextdns_service("twitter")

        services = db.get_all_nextdns_services()
        assert len(services) == 2


class TestUtilityFunctions:
    """Tests for database utility functions."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"
        self.db_path = test_db_path

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_database_exists(self):
        """Should detect if database exists."""
        assert db.database_exists() is True

    def test_get_database_size(self):
        """Should return database file size."""
        size = db.get_database_size()
        assert size > 0

    def test_execute_query(self):
        """Should execute raw queries."""
        db.add_blocked_domain("test.com")

        results = db.execute_query(
            "SELECT domain FROM blocked_domains WHERE domain = ?",
            ("test.com",),
        )
        assert len(results) == 1
        assert results[0]["domain"] == "test.com"

    def test_export_to_json(self):
        """Should export database to JSON-compatible dict."""
        db.add_blocked_domain("blocked.com")
        db.add_allowed_domain("allowed.com")
        db.add_category("social", domains=["facebook.com"])

        export = db.export_to_json()

        assert "blocked_domains" in export
        assert "allowed_domains" in export
        assert "categories" in export
        assert len(export["blocked_domains"]) == 1
        assert len(export["allowed_domains"]) == 1
        assert len(export["categories"]) == 1


class TestTransaction:
    """Tests for transaction context manager."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
        """Use a temporary database for each test."""
        test_db_path = tmp_path / "test.db"

        with patch.object(db, "get_db_path", return_value=test_db_path):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            yield
            db.close_connection()

    def test_transaction_commits_on_success(self):
        """Should commit changes on successful transaction."""
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO blocked_domains (domain) VALUES (?)",
                ("success.com",),
            )

        assert db.is_domain_blocked("success.com") is True

    def test_transaction_rolls_back_on_error(self):
        """Should rollback changes on exception."""
        try:
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO blocked_domains (domain) VALUES (?)",
                    ("rollback.com",),
                )
                raise ValueError("Intentional error")
        except ValueError:
            pass

        assert db.is_domain_blocked("rollback.com") is False
