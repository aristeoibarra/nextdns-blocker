# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[5.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v4.0.0...v5.0.0
[4.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v3.1.0...v4.0.0
[3.1.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v2.1.0...v3.0.0
[2.1.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/aristeoibarra/nextdns-blocker/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/aristeoibarra/nextdns-blocker/releases/tag/v1.0.0
