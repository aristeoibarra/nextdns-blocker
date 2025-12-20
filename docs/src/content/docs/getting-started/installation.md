---
title: Installation
description: Install NextDNS Blocker on macOS, Linux, Windows, or Docker
---

Choose the installation method that best fits your environment.

## Homebrew (macOS/Linux)

The recommended method for macOS and Linux users:

```bash
# Add the tap
brew tap aristeoibarra/tap

# Install
brew install nextdns-blocker

# Verify installation
nextdns-blocker --version
```

### Updating via Homebrew

```bash
brew upgrade nextdns-blocker
```

## PyPI (pip)

Works on any platform with Python 3.9+:

```bash
# Install from PyPI
pip install nextdns-blocker

# Or with pipx for isolated installation
pipx install nextdns-blocker

# Verify installation
nextdns-blocker --version
```

### Updating via pip

```bash
pip install --upgrade nextdns-blocker

# Or check for updates within the tool
nextdns-blocker update
```

## From Source

For development or the latest unreleased features:

```bash
# Clone the repository
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker

# Install in editable mode
pip install -e .

# Verify installation
nextdns-blocker --version
```

### Development Installation

For contributing or running tests:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Windows PowerShell

Automated installation script for Windows:

```powershell
# Download and run the installer
irm https://raw.githubusercontent.com/aristeoibarra/nextdns-blocker/main/install.ps1 | iex

# Or run locally after cloning
.\install.ps1
```

The installer will:
1. Check for Python installation
2. Install the package via pip
3. Run the interactive setup wizard
4. Configure Windows Task Scheduler for automatic sync

## Docker

Run NextDNS Blocker in a container:

```bash
# Clone the repository
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker

# Copy configuration templates
cp .env.example .env
cp config.json.example config.json

# Edit your configuration
nano .env        # Add API key and profile ID
nano config.json # Configure domains

# Start the container
docker compose up -d
```

See [Docker Setup](/platforms/docker/) for detailed configuration.

## Verifying Installation

After installation, verify everything works:

```bash
# Check version
nextdns-blocker --version

# View available commands
nextdns-blocker --help

# Run the setup wizard
nextdns-blocker init
```

## System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| Python | 3.9 | 3.11+ |
| RAM | 50 MB | 100 MB |
| Disk | 20 MB | 50 MB |
| Network | Required | - |

### Platform-Specific Requirements

- **macOS**: No additional requirements
- **Linux**: `cron` for scheduled sync
- **Windows**: Task Scheduler service running

## Troubleshooting Installation

### Python not found

```bash
# Check Python version
python3 --version

# On Windows, try:
python --version
```

If Python isn't installed, download from [python.org](https://www.python.org/downloads/).

### Permission denied

```bash
# Use --user flag
pip install --user nextdns-blocker

# Or use pipx
pipx install nextdns-blocker
```

### Command not found after installation

The installation directory might not be in your PATH:

```bash
# Find where pip installed it
pip show nextdns-blocker

# Add to PATH (example for ~/.local/bin)
export PATH="$HOME/.local/bin:$PATH"
```

Add this export to your shell's rc file (`.bashrc`, `.zshrc`, etc.).

## Next Steps

After installation, run the [Quick Setup](/getting-started/quick-setup/) wizard to configure your credentials.
