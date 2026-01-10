---
title: completion
description: Generate shell completion scripts
sidebar:
  order: 3
---

The `completion` command generates shell completion scripts for bash, zsh, and fish shells.

## Usage

```bash
nextdns-blocker completion SHELL
```

Where `SHELL` is one of: `bash`, `zsh`, or `fish`.

## Shells Supported

| Shell | Command |
|-------|---------|
| Bash | `nextdns-blocker completion bash` |
| Zsh | `nextdns-blocker completion zsh` |
| Fish | `nextdns-blocker completion fish` |

## Installation

### Bash

Add to your `~/.bashrc`:

```bash
eval "$(nextdns-blocker completion bash)"
```

Then reload:

```bash
source ~/.bashrc
```

### Zsh

Add to your `~/.zshrc`:

```bash
eval "$(nextdns-blocker completion zsh)"
```

Then reload:

```bash
source ~/.zshrc
```

### Fish

Save to the completions directory:

```bash
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
```

The completions will be available in new Fish sessions.

## What Gets Completed

Shell completion works for:

- **Commands**: `nextdns-blocker <TAB>` shows all available commands
- **Subcommands**: `nextdns-blocker config <TAB>` shows config subcommands
- **Options**: `nextdns-blocker config sync --<TAB>` shows available flags
- **Domains**: `nextdns-blocker unblock <TAB>` shows domains from your blocklist
- **Allowlist**: `nextdns-blocker disallow <TAB>` shows domains from your allowlist

## Examples

### Command Completion

```bash
$ nextdns-blocker <TAB>
allow           completion      fix             nextdns         pending         status          update
category        config          health          panic           resume          sync            validate
completion      disallow        init            pause           stats           test-notifications  watchdog
```

### Subcommand Completion

```bash
$ nextdns-blocker config <TAB>
edit      set       show      sync      validate
```

### Option Completion

```bash
$ nextdns-blocker config sync --<TAB>
--config-dir  --dry-run     --help        --verbose
```

### Domain Completion

```bash
$ nextdns-blocker unblock <TAB>
facebook.com  instagram.com  reddit.com  twitter.com
```

## Automatic Installation

The `fix` command can automatically install completions:

```bash
nextdns-blocker fix
```

This will detect your shell and install completions if not already present.

## Troubleshooting

### Completions Not Working

1. Ensure the eval line is in your shell config file
2. Open a new terminal or source the config file
3. Verify the completion is loaded:
   ```bash
   type _nextdns-blocker  # For bash/zsh
   ```

### "Command not found" Error

Ensure `nextdns-blocker` is in your PATH:

```bash
which nextdns-blocker
```

If not found, you may need to add the installation directory to your PATH.

### Slow Completion

Domain completion queries your config file. If you have many domains, there may be a slight delay. This is normal.

## Related

- [Shell Completion Feature](/features/shell-completion/) - Detailed feature documentation
- [fix Command](/commands/fix/) - Auto-install completions
