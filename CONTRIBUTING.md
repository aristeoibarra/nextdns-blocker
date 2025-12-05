# Contributing to NextDNS Blocker

Thank you for your interest in contributing! This guide will help you get started.

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in [Issues](https://github.com/aristeoibarra/nextdns-blocker/issues)
2. If not, create a new issue with:
   - Clear title describing the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version)

### Suggesting Features

1. Open an issue with the `enhancement` label
2. Describe the feature and its use case
3. Explain why it would be useful

## Branch Strategy

This project uses a three-tier branching model:

```
  feature/*          main              stage              prod
      |                |                 |                  |
      +--- PR -------->|                 |                  |
                       +---- PR -------->|                  |
                                         +---- PR + tag --->|
                                                            |
                                                       [PyPI Release]
```

### Branch Overview

| Branch | Purpose | Target for PRs |
|--------|---------|----------------|
| `prod` | Production releases (PyPI) | From `stage` only |
| `stage` | Pre-release QA | From `main` |
| `main` | Daily development | Feature branches, forks |
| `feature/*` | New features | PR to `main` |
| `hotfix/*` | Critical fixes | PR to `prod` |

### For Contributors

**All PRs should target `main`**, not `prod` or `stage`. The maintainers will promote changes through `stage` → `prod` when ready for release.

### Code Contributions

#### Setup Development Environment

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/nextdns-blocker.git
cd nextdns-blocker

# Install in development mode with dev dependencies
pip3 install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check .
black --check .
```

#### Making Changes

1. **Fork** the repository
2. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the code style
4. **Add tests** for new functionality
5. **Run tests** to ensure everything passes:
   ```bash
   pytest tests/ -v
   ```
6. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add your feature description"
   ```
7. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Open a Pull Request**

#### Commit Message Format

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation changes
- `test:` adding or updating tests
- `refactor:` code refactoring

#### Code Style

- Follow PEP 8 guidelines (enforced by `ruff` and `black`)
- Use type hints for all function signatures
- Keep functions small and focused
- Add docstrings for public functions
- Run `ruff check . && black .` before committing

### Documentation

Improvements to documentation are always welcome:
- Fix typos or unclear explanations
- Add examples
- Translate to other languages

## Project Structure

```
nextdns-blocker/
├── src/
│   └── nextdns_blocker/      # Main package
│       ├── __init__.py       # Package initialization and version
│       ├── __main__.py       # Entry point for python -m
│       ├── cli.py            # Click CLI commands
│       ├── client.py         # NextDNS API client
│       ├── common.py         # Shared utilities (logging, file ops)
│       ├── config.py         # Configuration loading
│       ├── exceptions.py     # Custom exception classes
│       ├── init.py           # Interactive setup wizard
│       ├── scheduler.py      # Schedule evaluation logic
│       └── watchdog.py       # Cron protection
├── tests/                    # Test suite (379 tests)
│   ├── conftest.py           # Shared pytest fixtures
│   ├── test_allowlist.py     # Allowlist feature tests
│   ├── test_cli_commands.py  # CLI command tests
│   ├── test_client.py        # API client tests
│   ├── test_config_loading.py # Config loading tests
│   ├── test_init.py          # Init wizard tests
│   ├── test_pause_protected.py # Pause/protected domain tests
│   ├── test_remote_domains.py # Remote domains tests
│   ├── test_schedule.py      # Schedule logic tests
│   ├── test_validation.py    # Input validation tests
│   └── test_watchdog.py      # Watchdog tests
├── pyproject.toml            # Package configuration
├── domains.json.example      # Example domain configuration
├── .env.example              # Example environment configuration
├── Dockerfile                # Container image
└── docker-compose.yml        # Docker Compose configuration
```

## Getting Help

- Open an issue for questions
- Check existing issues and discussions

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback

Thank you for contributing!
