---
title: update
description: Check for updates and upgrade NextDNS Blocker
---

The `update` command checks for new versions and can automatically upgrade the installation.

## Usage

```bash
nextdns-blocker update [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |
| `--help` | Show help message |

## Examples

### Check for Updates

```bash
nextdns-blocker update
```

### Output (Update Available)

```
Checking for updates...

Current version: 6.2.0
Latest version: 6.3.0

Release notes:
  - Added categories support for domain grouping
  - Added NextDNS native categories and services support
  - Docker development experience improvements

Update to 6.3.0? [y/N]: y

Updating...
✓ Updated to version 6.3.0

Restart your terminal to use the new version.
```

### Output (Up to Date)

```
Checking for updates...

Current version: 6.3.0
Latest version: 6.3.0

✓ You're running the latest version
```

### Skip Confirmation

```bash
nextdns-blocker update -y
```

Automatically installs updates without prompting.

## Update Methods

### pip Installation

If installed via pip, update uses:

```bash
pip install --upgrade nextdns-blocker
```

### Homebrew Installation

For Homebrew users, the command suggests:

```
You installed via Homebrew. Update with:
  brew upgrade nextdns-blocker
```

### pipx Installation

For pipx users:

```
You installed via pipx. Update with:
  pipx upgrade nextdns-blocker
```

## Version Checking

### Check Current Version

```bash
nextdns-blocker --version
```

Output:
```
nextdns-blocker, version 6.3.0
```

### Version in Status

The status command also shows version:

```bash
nextdns-blocker status | head -5
```

## Automatic Update Checks

NextDNS Blocker can periodically check for updates in the background. This is not enabled by default.

### How It Works

1. During sync, checks PyPI for latest version
2. Compares with installed version
3. If newer version exists, shows notification
4. Does not auto-install

### Notification Example

During normal commands, you might see:

```
nextdns-blocker sync

Syncing domains...
  reddit.com: BLOCKED
Sync complete

💡 Update available: 6.3.0 (current: 6.2.0)
   Run 'nextdns-blocker update' to upgrade
```

## Release Channels

Currently, there's only one release channel (stable). All releases go through:

1. Development and testing
2. Version bump
3. PyPI release
4. Homebrew formula update

## Changelog

View the full changelog:

- [GitHub Releases](https://github.com/aristeoibarra/nextdns-blocker/releases)
- [CHANGELOG.md](https://github.com/aristeoibarra/nextdns-blocker/blob/main/CHANGELOG.md)

## Shell Completion

### Updating Completions

After updating, regenerate shell completions:

```bash
# Bash
eval "$(nextdns-blocker completion bash)"

# Zsh
eval "$(nextdns-blocker completion zsh)"

# Fish
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
```

Or reinstall from your shell config file.

## Troubleshooting

### Update fails with permission error

```bash
# Use --user flag
pip install --user --upgrade nextdns-blocker

# Or use sudo (not recommended)
sudo pip install --upgrade nextdns-blocker
```

### Command not found after update

The installation directory might have changed. Reinstall:

```bash
pip uninstall nextdns-blocker
pip install nextdns-blocker
```

### Homebrew version behind

Homebrew formulas may lag behind PyPI. Options:

1. Wait for formula update
2. Install from PyPI instead:
   ```bash
   brew uninstall nextdns-blocker
   pip install nextdns-blocker
   ```

### Verify installation after update

```bash
# Check version
nextdns-blocker --version

# Test functionality
nextdns-blocker status
nextdns-blocker sync --dry-run
```

## Rolling Back

If an update causes issues:

### pip

```bash
pip install nextdns-blocker==6.1.0  # Specific version
```

### Homebrew

```bash
# List available versions
brew info nextdns-blocker

# Reinstall specific version (if available)
brew install nextdns-blocker@6.1.0
```

### From Source

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
git checkout v6.1.0
pip install -e .
```
