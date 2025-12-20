# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.2.0] - 2025-12-20

### Added
- **Shell tab completion** (#134): Native tab completion for bash, zsh, and fish shells
  - `nextdns-blocker completion bash|zsh|fish` generates shell scripts
  - Completes commands, subcommands, domain names, and pending action IDs
  - Auto-installed during `init`, `fix`, and `update` commands
  - See README for installation instructions
- **Update notification in status command** (#133): Proactive update awareness
  - Status command now checks PyPI for available updates
  - 24-hour cache to minimize network requests
  - `--no-update-check` flag to skip the check
  - Graceful handling of network errors
- **Panic mode command** (#132): Emergency lockdown functionality
  - `nextdns-blocker panic <duration>` activates panic mode (minimum 15 minutes)
  - `nextdns-blocker panic status` shows remaining time
  - `nextdns-blocker panic extend <duration>` extends the lockdown
  - Immediately blocks all active domains on activation
  - Hides dangerous commands (unblock, pause, resume, disallow, allow)
  - Sync skips unblocks and allowlist operations during panic mode
  - Discord notifications for panic activation
- **Allowlist schedule support** (#131): Time-based allowlist entries
  - Add `schedule` field to allowlist entries for dynamic control
  - `null` or missing schedule: always in allowlist (24/7)
  - Defined schedule: only in allowlist during `available_hours`
  - Useful for domains blocked by NextDNS categories or services
  - New `should_allow()` and `should_allow_domain()` methods in scheduler
- **Spanish README translation** (#137): Full Spanish documentation
  - Complete translation in `README.es.md`
  - Language selector links added to both README files
  - Thanks to @Manasvisingh12

### Changed
- **Discord notifications**: Extended to allowlist operations (allow/disallow commands)
- **Rate limiting**: Discord webhook rate limit increased from 2s to 3s for bulk operations
- **Rate limiter**: Use `collections.deque` for O(1) operations instead of list
- **Backup timestamps**: Include microseconds to prevent collision on rapid saves
- **Cleanup strategy**: Replace random 1% cleanup with deterministic 24-hour interval

### Fixed
- **Security: Full API key redaction** in logs (was showing first/last 4 characters)
- **Security: Safe editors whitelist** to prevent command injection via EDITOR environment variable
- **Security: Editor command parsing** uses `shlex.split()` for proper escaping
- **Security: Atomic config writes** using temp file + rename pattern
- **Security: API key dynamic loading** via `_get_headers()` method instead of storing in headers
- **Security: Stricter Discord webhook validation** with extended token pattern (60-100 chars)
- **Security: Environment variable validation** with POSIX-compliant key checking and null byte rejection
- **Security: Leading zeros rejection** in port validation
- **Race condition: File locking in pending.py** for atomic operations on pending actions
- **Race condition: RateLimiter** by tracking actual wait time
- **Race condition: DomainCache sync** between `_data` and `_domains` on add/remove
- **Bug: Version parsing** now handles semver suffixes (e.g., `1.0.0rc1`)
- **Bug: WEEKDAY_TO_DAY** now uses tuple instead of dict key order for reliability
- **Bug: Datetime naive/aware inconsistencies** by stripping timezone info with `ensure_naive_datetime()`
- **Bug: File descriptor leaks** in `write_secure_file()` and init.py env file creation
- **Bug: Windows file locking** with proper errno handling (13, 33, 36)
- **Bug: Deprecated ssl.CertificateError** replaced with `ssl.SSLError`
- **Bug: Non-existent json.JSONEncodeError** replaced with `TypeError/ValueError`
- **Exception handling**: Replace broad `except Exception` with specific exception types throughout
- **Exception handling**: Add `subprocess.TimeoutExpired` handling with proper error messages
- **Exception handling**: Preserve tracebacks with `from e` in exception chaining
- **Subprocess safety**: Add timeout (30-60s) to all `subprocess.run()` calls
- **Subprocess safety**: Add `shlex.quote()` escaping for paths in cron job commands
- **Cache reliability**: Filter empty domain IDs to prevent false positives
- **Cache reliability**: `add_domain()` now prevents duplicate entries
- **Crontab handling**: Distinguish between no crontab and errors in `get_crontab()`
- **File locking**: Add timeout support (10s default) to prevent indefinite blocking
- **Disk writes**: Add `fsync()` to `write_secure_file()` for guaranteed persistence
- **Logging**: Add logging for previously silenced exceptions
- **Logging**: Elevate audit log failures to warning level
- **mypy**: Use click package instead of outdated types-click stubs

### Refactored
- Extract `_load_env_file()` for better code organization
- Extract `validate_schedule()` function in config.py for reuse
- Refactor `sync()` into smaller helper functions
- Refactor `load_config()` into separate validation functions
- Refactor client.py to use `requests.request()` instead of repetitive get/post/delete
- Remove duplicated code (`_escape_windows_path`, `_build_task_command`) from init.py
- Move inline imports to module level for better performance
- Remove unreachable defensive code blocks and dead code
- Encapsulate notification rate limiting in class

### Documentation
- Add comprehensive docstrings to exception classes
- Add descriptive docstrings to `DenylistCache`/`AllowlistCache`
- Document blocklist/allowlist interaction and panic mode behavior in README
- Document datetime handling conventions in pending.py
- Add rate limiting constants documentation
- Add comments explaining sync order and NextDNS priority rules

### Tests
- Add 23 tests for shell completion functions
- Add 18 tests for blocklist/allowlist consistency
- Add comprehensive tests for update notification logic
- Update tests to use specific exception types
- Fix Windows test compatibility for subprocess calls

## [6.1.1] - 2025-12-17

### Fixed
- **Homebrew executable detection in scheduler**: `get_executable_path()` and `get_executable_args()` now check Homebrew paths as fallback
  - Fixes launchd plist using `python -m nextdns_blocker` instead of `/opt/homebrew/bin/nextdns-blocker`
  - Checks: `/opt/homebrew/bin/nextdns-blocker` (macOS ARM), `/usr/local/bin/nextdns-blocker` (macOS Intel), `/home/linuxbrew/.linuxbrew/bin/nextdns-blocker` (Linuxbrew)
  - Users should run `nextdns-blocker watchdog uninstall && nextdns-blocker watchdog install` to regenerate plists

## [6.1.0] - 2025-12-17

### Added
- **Homebrew support for update command** (#115): Auto-detect Homebrew installations
  - Detects `/homebrew/` or `/cellar/` in executable path
  - Uses `brew upgrade nextdns-blocker` for Homebrew installations
  - Homebrew detection takes priority over pipx
  - Updated help text to reflect supported installation methods
- **Root-level uninstall command**: `nextdns-blocker uninstall`
  - Removes scheduler jobs (launchd/cron/Task Scheduler)
  - Cross-platform support (macOS, Linux, Windows)

### Fixed
- **Config detection logic** (#124): Require both `.env` AND config file for CWD detection
  - Prevents incorrect directory detection when only one file exists
  - More reliable configuration loading

### Changed
- Examples migrated to v6 config format
- Tests updated to match new config detection logic

## [6.0.0] - 2025-12-15

### Breaking Changes
- **Removed remote URL support**: `DOMAINS_URL` and `DOMAINS_HASH_URL` environment variables no longer supported
- **New configuration format**: `config.json` replaces `domains.json`
  - `domains` key renamed to `blocklist`
  - `protected` field replaced with `unblock_delay` (`"0"` = instant, `"never"` = protected)
  - Settings (timezone, editor) now in `settings` object
- **Timezone moved to config.json**: No longer in `.env`, stored in `config.json` under `settings.timezone`
- **init wizard simplified**: No longer prompts for timezone (auto-detected) or remote URL
- **Version via importlib.metadata**: `__version__` now uses `importlib.metadata` as single source of truth

### Added
- **Pending actions with cooldown delays** (#106): Protection against impulsive unblocking
  - New `unblock_delay` field: `"never"`, `"24h"`, `"4h"`, `"30m"`, `"0"`
  - Pending command group: `nextdns-blocker pending <subcommand>`
    - `pending list` - Show all pending unblock actions
    - `pending show <id>` - Show details of a pending action
    - `pending cancel <id>` - Cancel a pending unblock
  - Watchdog automatically executes pending actions when ready
  - Discord notifications for pending/cancel events
  - Audit logging for all pending action states
- **Config command group** (#104): `nextdns-blocker config <subcommand>`
  - `config show` - Display current configuration
  - `config edit` - Open config in editor (`$EDITOR`)
  - `config set <key> <value>` - Change settings (editor, timezone)
  - `config validate` - Validate configuration (JSON syntax, domain formats, schedules)
  - `config migrate` - Migrate from domains.json to config.json format
  - `config sync` - Sync with NextDNS (deprecates root `sync`)
- **Homebrew tap integration** (#105): Install via Homebrew
  - `brew tap aristeoibarra/tap && brew install nextdns-blocker`
  - Automated formula updates on new releases
  - All Python dependencies bundled
- **Automatic timezone detection**: System timezone saved to config.json during init
- **Migration support**: `config migrate` converts legacy domains.json to new config.json format
- **Validate command** (#102): Pre-deployment configuration verification
- **Colored CLI output** (#101): Rich terminal output with colors and formatting (thanks @Jacques-Murray)
- **PR template**: Standardized pull request template (thanks @niloymajumder)

### Changed
- `.env` now only contains API credentials (API_KEY, PROFILE_ID)
- `init` creates `config.json` instead of `domains.json`
- Root `sync` and `validate` commands show deprecation warnings
- CI: Updated GitHub Actions (upload-artifact v6, download-artifact v7)
- CI: Linting moved to pre-commit.ci for faster feedback
- Version is now dynamically read from package metadata (no manual sync needed)

### Removed
- Remote domains fetching via URL
- Domain caching for remote URLs
- `--url` flag from `init` command
- `--domains-url` flag from `sync` command
- `DOMAINS_URL` and `DOMAINS_HASH_URL` environment variables
- Hardcoded `__version__` string in `__init__.py`

### Contributors
- @Jacques-Murray - Colored CLI output (#101)
- @niloymajumder - PR template (#103)

## [5.4.0] - 2025-12-14

### Added
- **Auto-detect System Timezone**: `nextdns-blocker init` now automatically detects the system timezone
  - No manual timezone input required during setup
  - Falls back to interactive prompt if detection fails
- **Discord Notification Improvements**:
  - Emoji indicators for block/unblock events (visual feedback)
  - Webhook URL validation on startup
  - New `test-notifications` command to verify webhook configuration
- **Documentation**: Starlight documentation site setup in `docs/`
- **CODE_OF_CONDUCT.md**: Community guidelines added

### Changed
- Updated README with timezone auto-detection information
- Improved FAQ section in README

## [5.3.0] - 2025-12-12

### Added
- **Windows Platform Support**: Full native Windows support
  - PowerShell installer script (`install.ps1`) for automated setup
  - Windows Task Scheduler integration for sync and watchdog jobs
  - PowerShell log rotation script (`setup-logrotate.ps1`)
  - Windows-specific paths via `platformdirs` (`%APPDATA%`, `%LOCALAPPDATA%`)
  - Comprehensive Windows troubleshooting documentation in README
- **Study Mode Example**: New `examples/study-mode.json` configuration
  - Blocks distracting sites during study hours (weekdays 8am-12pm, 2pm-6pm)
  - Allows access during lunch breaks and evenings
  - Full access on weekends
- **E2E Test Suite**: Comprehensive end-to-end tests
  - Full workflow testing from init to sync
  - Platform-specific scheduler tests
  - Improved test isolation and mocking

### Changed
- **Test Coverage**: Improved from 85% to 94%
- **README**: Added status badges (PyPI version, downloads, Python versions, License, CI status)

### Fixed
- Windows file locking and permission handling tests
- Platform detection mocking in pipx fallback tests

## [5.2.0] - 2025-12-11

### Added
- **Fix Command**: `nextdns-blocker fix` for troubleshooting common issues
  - Verifies configuration exists and is valid
  - Detects installation type (pipx/system/module)
  - Reinstalls scheduler (unload + install)
  - Runs sync to verify everything works
- **Scheduler Status**: `nextdns-blocker status` now shows scheduler health
  - Displays sync and watchdog job status (ok/NOT RUNNING)
  - Shows helpful command when scheduler is not running
  - Supports both macOS (launchd) and Linux (cron)
- **Pipx Update Support**: `nextdns-blocker update` detects pipx installations
  - Uses `pipx upgrade` instead of `pip install --upgrade` when appropriate
  - Automatic detection via pipx venv directory

### Fixed
- **Full Pipx Compatibility**: Complete support for pipx installations
  - Added `~/.local/bin` to PATH in all launchd plists
  - Pipx fallback detection in `_install_launchd()`, `_install_cron()`, `run_initial_sync()`
  - Pipx fallback in watchdog's `get_executable_path()` and `get_executable_args()`
  - Fixed `generate_plist()` to include pipx PATH
- Scheduler auto-repair now works correctly with pipx installations

## [5.1.0] - 2025-12-09

### Added
- **Cross-platform Support**: Full macOS and Linux support
  - **launchd integration** for macOS (replaces cron on Darwin)
  - Automatic platform detection (`is_macos()`)
  - `generate_plist()`, `load_launchd_job()`, `unload_launchd_job()` functions
  - LaunchAgents installed to `~/Library/LaunchAgents/`
- **Discord Notifications**: Real-time alerts for block/unblock events
  - New `notifications.py` module with webhook support
  - Configure via `DISCORD_WEBHOOK_URL` and `DISCORD_NOTIFICATIONS_ENABLED`
  - Rich embeds with color coding (red=block, green=unblock)
- **Update Command**: `nextdns-blocker update` for quick version upgrades
  - Checks PyPI for latest version
  - Automatic upgrade via pip
  - `-y/--yes` flag to skip confirmation
- **Domains Migration Support**: Seamless config transitions
  - Detects existing local/remote domains configuration
  - Interactive wizard for migration choices
  - `detect_existing_config()`, `prompt_domains_migration()` functions
- **Unified Init Command**: `nextdns-blocker init` now includes:
  - Scheduling setup (launchd/cron) automatically
  - Initial sync after configuration
  - Platform-appropriate job installation
- **Example Configurations**: New `examples/` directory
  - `minimal.json` - Quick-start templates
  - `work-focus.json` - Productivity-focused rules
  - `gaming.json` - Gaming platforms scheduling
  - `social-media.json` - Social networks management
  - `parental-control.json` - Protected content blocking
  - Comprehensive README with schedule snippets

### Changed
- **Branch Strategy**: Simplified from 3-tier to 2-tier model
  - Removed `stage` branch (now: `feature/* → main → prod`)
  - Streamlined release process
- **Docker**: Python base image upgraded from 3.12-alpine to 3.14-alpine
- **CI**: Updated GitHub Actions (checkout v6, setup-python v6, artifacts v5/v6)
- **Tests**: Added mocked sleep in retry tests for faster execution
- Test count increased to 6,291 lines across all test files

### Fixed
- Scheduling setup wrapped in try-except for proper error handling
- Code formatting applied consistently across modules

## [5.0.2] - 2025-12-06

### Fixed
- Cron jobs now use full executable path instead of `cd` + command
  - Prevents issues when PATH is not set correctly in cron environment
- PyPI badge updated to shields.io for better reliability

## [5.0.1] - 2025-12-05

### Fixed
- `load_config()` now correctly uses `get_config_dir()` for XDG support
  - Config files in `~/.config/nextdns-blocker/` are now properly detected
  - Previously fell back to package directory instead of XDG paths

### Added
- Interactive wizard now prompts for optional `DOMAINS_URL`
  - Users can configure remote domains.json URL during `nextdns-blocker init`
  - No longer requires `--url` flag for interactive setup

## [5.0.0] - 2025-12-05

### Added
- **PyPI Distribution**: Package available via `pip install nextdns-blocker`
  - Modern `pyproject.toml` configuration with hatchling build backend
  - Support for Python 3.9, 3.10, 3.11, 3.12, and 3.13
  - Proper package metadata, classifiers, and entry points
- **Interactive Setup Wizard**: `nextdns-blocker init` command
  - Guided configuration for API key, profile ID, and timezone
  - Option to create sample domains.json
  - Validates credentials before saving
- **XDG Config Directory Support**: Configuration now follows XDG Base Directory Specification
  - Config files in `~/.config/nextdns-blocker/`
  - Data files in `~/.local/share/nextdns-blocker/`
  - Cache files in `~/.cache/nextdns-blocker/`
  - Automatic migration from legacy paths
- **Remote Domains Caching**: Smart caching for remote domains.json
  - 1-hour TTL cache with automatic refresh
  - Fallback to cached data when network fails
  - Cache status displayed in health check
  - `--no-cache` flag to force fresh fetch
- **CI/CD Pipeline**: Automated testing and publishing
  - GitHub Actions workflow for linting (ruff, black)
  - Type checking with mypy (strict mode)
  - Security scanning with bandit
  - Matrix testing across Python 3.9-3.13
  - Automatic PyPI publishing on tagged releases
  - TestPyPI publishing for pre-release validation
- **Code Quality Tooling**: Industry-standard development tools
  - ruff for fast linting
  - black for code formatting
  - mypy for type checking
  - bandit for security analysis
  - pytest-cov for coverage reporting

### Changed
- **BREAKING**: Project restructured to `src/` layout
  - Package now at `src/nextdns_blocker/`
  - All imports updated to use package structure
- **BREAKING**: CLI commands changed from `./blocker` to `nextdns-blocker`
  - `./blocker sync` → `nextdns-blocker sync`
  - `./watchdog` → `nextdns-blocker watchdog`
- **BREAKING**: Click-based CLI replaces argparse
  - Improved help messages and command structure
  - Better error handling and user feedback
- Test count increased from 329 to 379 (50 new tests)
- Code coverage maintained at 85%
- Removed legacy `cmd_*` functions in favor of Click commands
- Consolidated DenylistCache and AllowlistCache into base class

### Fixed
- Silent error suppression replaced with proper logging
- Security: Paths in cron job strings now escaped with `shlex.quote`
- Various type annotation improvements for strict mypy compliance

### Security
- All dependencies pinned with version ranges
- Bandit security scanning in CI pipeline
- Safety dependency vulnerability checking

### Removed
- Legacy `requirements.txt` and `requirements-dev.txt` (use `pip install -e ".[dev]"`)
- Old `install.sh` script (replaced by `pip install` + `nextdns-blocker init`)
- Direct script execution (now requires package installation)

## [4.0.0] - 2024-12-04

### Added
- **Allowlist Management**: Block parent domains while keeping subdomains accessible
  - New commands: `./blocker allow <domain>` and `./blocker disallow <domain>`
  - Allowlist configuration in domains.json with 24/7 availability
  - Validation to prevent overlap between denylist and allowlist
  - AllowlistCache with same TTL strategy as DenylistCache
  - 42 new tests for allowlist functionality
- **Docker Support**: Run NextDNS Blocker in containers
  - Dockerfile with Python 3.11 Alpine (~50MB image)
  - docker-compose.yml with watchdog as default command
  - .dockerignore for optimized builds
  - Health check endpoint for container orchestration
  - Volume mounts for domains.json and persistent logs
- **GitHub Actions CI**: Automated testing pipeline
  - Runs on push/PR to main and stage branches
  - Matrix testing: Python 3.9, 3.10, 3.11, 3.12
  - pip dependency caching for faster builds

### Changed
- `load_domains()` now returns tuple `(domains, allowlist)` for backwards compatibility
- `cmd_sync()` and `cmd_status()` signatures updated to include allowlist parameter
- README updated with Docker setup section and allowlist documentation
- Test count increased from 287 to 329 (42 new allowlist tests)

## [3.1.0] - 2024-11-27

### Changed
- **Removed Nuitka compilation**: Install now takes seconds instead of 10+ minutes
  - No longer requires gcc, patchelf, or compilation tools
  - Scripts run directly with Python interpreter
  - Commands changed from `./blocker.bin` to `./blocker`
  - Wrapper scripts created for clean CLI interface

### Fixed
- **install.sh**: Now supports DOMAINS_URL without requiring local domains.json
  - Installation no longer fails when using remote configuration
  - Displays "using remote: URL" or "using local: domains.json" during install
  - Provides clear error message when neither local file nor URL is configured

### Added
- Test suite for install.sh domain configuration logic (6 tests)

## [3.0.0] - 2024-11-27

### Added
- **Health Check Command**: `./blocker.bin health` - Comprehensive system health verification
  - API connectivity check
  - Configuration validation
  - Timezone verification
  - Pause state status
  - Log directory accessibility
  - Cache status
- **Statistics Command**: `./blocker.bin stats` - Usage statistics from audit log
  - Total blocks/unblocks count
  - Total pauses count
  - Last action timestamp
- **Dry-run Mode**: `./blocker.bin sync --dry-run` - Preview changes without applying
  - Shows what would be blocked/unblocked
  - Displays current vs expected state
  - Summary of changes
- **Verbose Mode**: `./blocker.bin sync --verbose` or `-v`
  - Detailed output of all sync actions
  - Per-domain status display
  - Summary at completion
- **Denylist Cache**: Smart caching to reduce API calls
  - 60-second TTL with automatic invalidation
  - Optimistic updates on block/unblock
  - `refresh_cache()` method for manual refresh
- **Rate Limiting**: Built-in protection against API rate limits
  - Sliding window algorithm (30 requests/minute)
  - Automatic waiting when limit reached
- **Exponential Backoff**: Automatic retries with increasing delays
  - Base delay: 1 second, max: 30 seconds
  - Retries on timeout, 429, and 5xx errors
- **is_blocked() Method**: Convenience method in NextDNSClient
- **Shared utilities module**: `common.py` with `ensure_log_dir()` for lazy initialization
- 287 tests with 92% code coverage

### Changed
- Default retries increased from 2 to 3
- URL validation regex is now stricter (requires valid TLD)
- Overnight range boundary handling improved (end time exclusive)
- `time` import renamed to `dt_time` to avoid conflicts
- Log directory creation is now lazy (no side effects on import)

### Fixed
- **Race condition in `is_paused()`**: Removed file existence check before acquiring lock
- **Double fd close bug**: Fixed file descriptor handling in `write_secure_file`
- **find_domain redundancy**: Simplified return value
- **Documentation**: Corrected test coverage percentage (92%)
- **API_RETRIES default**: Fixed inconsistency in .env.example (was 2, now 3)

### Security
- Race condition fix prevents potential timing attacks on pause state
- Rate limiting prevents accidental API abuse
- Input validation strengthened for URLs

## [2.1.0] - 2024-11-27

### Added
- Comprehensive test suite with 243 tests (91% coverage)
- Tests for watchdog.py (93% coverage)
- Time format validation in schedule configuration (HH:MM format)
- Early timezone validation at config load time
- Domain trailing dot validation (rejects FQDN notation)
- Named constants for domain validation (MAX_DOMAIN_LENGTH, MAX_LABEL_LENGTH)
- CHANGELOG.md for version tracking

### Fixed
- Race condition in `write_secure_file` - chmod now applied atomically
- File locking consistency in watchdog.py
- Improved error messages for invalid time formats

### Security
- Secure file creation with `os.open()` and proper permissions from start
- File locking on all sensitive file operations

## [2.0.0] - 2024-11-26

### Added
- Per-domain schedule configuration
- Support for loading domains.json from URL (DOMAINS_URL)
- Protected domains feature
- Pause/resume functionality with expiration
- Watchdog for cron job protection
- Audit logging for all blocking actions

### Changed
- Complete refactor for production quality
- Separated blocker and watchdog into independent scripts

## [1.0.0] - 2024-11-25

### Added
- Initial release
- Basic domain blocking via NextDNS API
- Simple time-based scheduling
- Cron-based automatic sync

[6.2.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v6.1.1...v6.2.0
[6.1.1]: https://github.com/aristeoibarra/nextdns-blocker/compare/v6.1.0...v6.1.1
[6.1.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v6.0.0...v6.1.0
[6.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.4.0...v6.0.0
[5.4.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.3.0...v5.4.0
[5.3.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.2.0...v5.3.0
[5.2.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.1.0...v5.2.0
[5.1.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.0.2...v5.1.0
[5.0.2]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.0.1...v5.0.2
[5.0.1]: https://github.com/aristeoibarra/nextdns-blocker/compare/v5.0.0...v5.0.1
[5.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v4.0.0...v5.0.0
[4.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v3.1.0...v4.0.0
[3.1.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v2.1.0...v3.0.0
[2.1.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/aristeoibarra/nextdns-blocker/releases/tag/v1.0.0
