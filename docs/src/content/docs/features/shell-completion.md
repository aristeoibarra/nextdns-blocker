---
title: Shell Completion
description: Enable tab completion for commands and domain names
---

Shell completion provides tab-completion for commands, subcommands, options, and even domain names from your configuration.

:::tip
See the [`completion` command reference](/commands/completion/) for quick setup instructions.
:::

## Supported Shells

- **Bash** - Most common on Linux
- **Zsh** - Default on macOS
- **Fish** - Modern shell with great defaults

## Quick Setup

### Bash

Add to `~/.bashrc`:

```bash
eval "$(nextdns-blocker completion bash)"
```

Then reload:
```bash
source ~/.bashrc
```

### Zsh

Add to `~/.zshrc`:

```bash
eval "$(nextdns-blocker completion zsh)"
```

Then reload:
```bash
source ~/.zshrc
```

### Fish

Save to completions directory:

```bash
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
```

Fish loads completions automatically.

## What Completes

### Commands

```bash
nextdns-blocker <TAB>
# Shows: sync, status, pause, resume, unblock, config, watchdog, panic, pending, allow, disallow, update, completion
```

### Subcommands

```bash
nextdns-blocker config <TAB>
# Shows: show, edit, validate, set, sync

nextdns-blocker watchdog <TAB>
# Shows: status, install, uninstall, enable, disable

nextdns-blocker pending <TAB>
# Shows: list, show, cancel
```

### Options

```bash
nextdns-blocker sync --<TAB>
# Shows: --dry-run, --verbose, --help

nextdns-blocker --<TAB>
# Shows: --help, --version, --no-color
```

### Domain Names

```bash
nextdns-blocker unblock <TAB>
# Shows domains from your blocklist:
# reddit.com, twitter.com, youtube.com...

nextdns-blocker disallow <TAB>
# Shows domains from your allowlist:
# aws.amazon.com, github.com...
```

### Pending Action IDs

```bash
nextdns-blocker pending cancel <TAB>
# Shows pending action IDs:
# pnd_20240115_143000_a1b2c3, pnd_20240115_150000_d4e5f6...

nextdns-blocker pending show <TAB>
# Same - shows pending action IDs
```

## Advanced Setup

### Bash (Alternative)

If `eval` is slow, save to a file:

```bash
# Generate once
nextdns-blocker completion bash > ~/.local/share/bash-completion/completions/nextdns-blocker

# Or system-wide (requires sudo)
nextdns-blocker completion bash | sudo tee /etc/bash_completion.d/nextdns-blocker
```

### Zsh (Alternative)

For Oh-My-Zsh users:

```bash
# Save to Oh-My-Zsh completions
nextdns-blocker completion zsh > ~/.oh-my-zsh/completions/_nextdns-blocker

# Rebuild cache
rm ~/.zcompdump*
compinit
```

### Zsh (fpath method)

```bash
# Create completions directory
mkdir -p ~/.zfunc

# Generate completion
nextdns-blocker completion zsh > ~/.zfunc/_nextdns-blocker

# Add to .zshrc (before compinit)
fpath=(~/.zfunc $fpath)
autoload -Uz compinit && compinit
```

## Verifying Setup

### Test Completion

After setup, test in a new terminal:

```bash
nextdns-blocker <TAB><TAB>
```

Should show available commands.

### Check Script Generated

```bash
nextdns-blocker completion bash | head -20
```

Should output shell completion script.

## Dynamic Completions

Domain names and pending IDs are read dynamically from your configuration:

1. Completion script runs
2. Reads `config.json` for domains
3. Reads `pending.json` for action IDs
4. Returns matches to shell

This means:
- Add a domain to config → immediately available for completion
- Create pending action → ID immediately completable

## Updating Completions

After updating NextDNS Blocker, regenerate completions:

```bash
# Bash
eval "$(nextdns-blocker completion bash)"

# Zsh
eval "$(nextdns-blocker completion zsh)"

# Fish
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
```

Or restart your terminal.

## Troubleshooting

### Completion not working

1. **Check shell type**:
   ```bash
   echo $SHELL
   ```

2. **Verify completion installed**:
   ```bash
   # Bash
   complete -p nextdns-blocker

   # Zsh
   which _nextdns-blocker
   ```

3. **Regenerate**:
   ```bash
   eval "$(nextdns-blocker completion bash)"  # or zsh
   ```

### Domain names not completing

1. **Check config exists**:
   ```bash
   nextdns-blocker config show
   ```

2. **Verify domains in blocklist**:
   ```bash
   cat ~/.config/nextdns-blocker/config.json | grep domain
   ```

### Slow completion

If completion is slow:

1. **Check config file size** - Very large configs might be slow
2. **Use file-based completion** instead of `eval`
3. **Check disk speed** - Config is read on each completion

### Pending IDs not completing

1. **Check pending actions exist**:
   ```bash
   nextdns-blocker pending list
   ```

2. **Verify pending.json readable**:
   ```bash
   cat ~/.local/share/nextdns-blocker/pending.json
   ```

## Shell-Specific Notes

### Bash

- Requires `bash-completion` package on some systems
- Minimum Bash 4.0 recommended

### Zsh

- Works with Oh-My-Zsh, Prezto, etc.
- May need `compinit` call after adding completions

### Fish

- Most straightforward setup
- Completions auto-load from `~/.config/fish/completions/`
- No shell restart needed

## Uninstalling Completions

### Bash

Remove from `~/.bashrc`:
```bash
# Remove this line:
eval "$(nextdns-blocker completion bash)"
```

Or delete file:
```bash
rm ~/.local/share/bash-completion/completions/nextdns-blocker
```

### Zsh

Remove from `~/.zshrc`:
```bash
# Remove this line:
eval "$(nextdns-blocker completion zsh)"
```

### Fish

Delete completion file:
```bash
rm ~/.config/fish/completions/nextdns-blocker.fish
```
