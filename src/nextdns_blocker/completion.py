"""Shell completion functions for CLI commands."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

import click
from click.shell_completion import CompletionItem

logger = logging.getLogger(__name__)

# Completion marker to identify our completion line
COMPLETION_MARKER = "# nextdns-blocker shell completion"
COMPLETION_LINE_BASH = 'eval "$(_NEXTDNS_BLOCKER_COMPLETE=bash_source nextdns-blocker)"'
COMPLETION_LINE_ZSH = 'eval "$(_NEXTDNS_BLOCKER_COMPLETE=zsh_source nextdns-blocker)"'
COMPLETION_LINE_FISH = "_NEXTDNS_BLOCKER_COMPLETE=fish_source nextdns-blocker | source"


def complete_blocklist_domains(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """
    Return blocklist domains for shell completion.

    Used by the unblock command to suggest domains that can be unblocked.

    Args:
        ctx: Click context
        param: Click parameter
        incomplete: Partial input from user

    Returns:
        List of completion items matching the incomplete string
    """
    try:
        # Import locally to allow patching in tests
        from .config import get_config_dir, load_domains

        config_dir = get_config_dir()
        config_file = config_dir / "config.json"

        if not config_file.exists():
            return []

        # Get script_dir from .env if available
        env_file = config_dir / ".env"
        script_dir = str(config_dir)

        if env_file.exists():
            with open(env_file, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NEXTDNS_SCRIPT_DIR="):
                        script_dir = line.split("=", 1)[1].strip().strip("\"'")
                        break

        domains, _ = load_domains(script_dir)
        completions = []

        for domain_config in domains:
            domain = domain_config.get("domain", "")
            if domain and domain.lower().startswith(incomplete.lower()):
                # Include description as help text if available
                description = domain_config.get("description", "")
                completions.append(CompletionItem(domain, help=description))

        return completions

    except (FileNotFoundError, PermissionError) as e:
        # Specific file access errors - log at debug level (common during initial setup)
        logger.debug(f"Config file not accessible for completion: {e}")
        return []
    except json.JSONDecodeError as e:
        # JSON parsing error - more serious, log at warning
        logger.warning(f"Invalid JSON in config file for completion: {e}")
        return []
    except (KeyError, TypeError) as e:
        # Data structure errors - log at warning
        logger.warning(f"Invalid config structure for completion: {e}")
        return []
    except OSError as e:
        # Other I/O errors - log at warning
        logger.warning(f"I/O error loading domains for completion: {e}")
        return []


def complete_allowlist_domains(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """
    Return allowlist domains for shell completion.

    Used by the disallow command to suggest domains that can be removed from allowlist.

    Args:
        ctx: Click context
        param: Click parameter
        incomplete: Partial input from user

    Returns:
        List of completion items matching the incomplete string
    """
    try:
        # Import locally to allow patching in tests
        from .config import get_config_dir, load_domains

        config_dir = get_config_dir()
        config_file = config_dir / "config.json"

        if not config_file.exists():
            return []

        # Get script_dir from .env if available
        env_file = config_dir / ".env"
        script_dir = str(config_dir)

        if env_file.exists():
            with open(env_file, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NEXTDNS_SCRIPT_DIR="):
                        script_dir = line.split("=", 1)[1].strip().strip("\"'")
                        break

        _, allowlist = load_domains(script_dir)
        completions = []

        for allowlist_config in allowlist:
            domain = allowlist_config.get("domain", "")
            if domain and domain.lower().startswith(incomplete.lower()):
                description = allowlist_config.get("description", "")
                completions.append(CompletionItem(domain, help=description))

        return completions

    except (FileNotFoundError, PermissionError) as e:
        logger.debug(f"Config file not accessible for allowlist completion: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in config file for allowlist completion: {e}")
        return []
    except (KeyError, TypeError) as e:
        logger.warning(f"Invalid config structure for allowlist completion: {e}")
        return []
    except OSError as e:
        logger.warning(f"I/O error loading allowlist for completion: {e}")
        return []


def complete_pending_action_ids(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """
    Return pending action IDs for shell completion.

    Used by pending show/cancel commands to suggest action IDs.

    Args:
        ctx: Click context
        param: Click parameter
        incomplete: Partial input from user

    Returns:
        List of completion items matching the incomplete string
    """
    try:
        # Import locally to allow patching in tests
        from .pending import get_pending_actions

        actions = get_pending_actions(status="pending")
        completions = []

        for action in actions:
            action_id = action.get("id", "")
            # Allow matching full ID or just the suffix (last 6 chars - random part)
            if action_id:
                suffix = action_id[-6:] if len(action_id) > 6 else action_id
                domain = action.get("domain", "")

                # Match against full ID or suffix
                if action_id.lower().startswith(incomplete.lower()) or suffix.lower().startswith(
                    incomplete.lower()
                ):
                    help_text = f"Unblock {domain}" if domain else ""
                    completions.append(CompletionItem(action_id, help=help_text))

        return completions

    except (FileNotFoundError, PermissionError) as e:
        logger.debug(f"Pending file not accessible for completion: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in pending file for completion: {e}")
        return []
    except (KeyError, TypeError) as e:
        logger.warning(f"Invalid pending data structure for completion: {e}")
        return []
    except OSError as e:
        logger.warning(f"I/O error loading pending actions for completion: {e}")
        return []


def get_completion_script(shell: str) -> str:
    """
    Generate shell completion script for the specified shell.

    Args:
        shell: Shell type ('bash', 'zsh', 'fish')

    Returns:
        Shell completion script as string
    """
    prog_name = "nextdns-blocker"
    env_var = "_NEXTDNS_BLOCKER_COMPLETE"

    if shell == "bash":
        return f"""# Bash completion for {prog_name}
# Add to ~/.bashrc or ~/.bash_profile:
# eval "$({env_var}=bash_source {prog_name})"

eval "$({env_var}=bash_source {prog_name})"
"""
    elif shell == "zsh":
        return f"""# Zsh completion for {prog_name}
# Add to ~/.zshrc:
# eval "$({env_var}=zsh_source {prog_name})"

eval "$({env_var}=zsh_source {prog_name})"
"""
    elif shell == "fish":
        return f"""# Fish completion for {prog_name}
# Save to ~/.config/fish/completions/{prog_name}.fish
# Or run: {env_var}=fish_source {prog_name} | source

{env_var}=fish_source {prog_name} | source
"""
    else:
        raise ValueError(f"Unsupported shell: {shell}")


def detect_shell() -> Optional[str]:
    """
    Detect the user's current shell.

    Returns:
        Shell name ('bash', 'zsh', 'fish') or None if unsupported
    """
    shell = os.environ.get("SHELL", "")
    shell_name = Path(shell).name if shell else ""

    if shell_name in ("bash", "zsh", "fish"):
        return shell_name

    # Try to detect from parent process on macOS/Linux
    try:
        result = subprocess.run(
            ["ps", "-p", str(os.getppid()), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        parent_name = result.stdout.strip()
        if parent_name in ("bash", "zsh", "fish", "-bash", "-zsh", "-fish"):
            return parent_name.lstrip("-")
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logger.debug(f"Could not detect shell from parent process: {e}")

    return None


def get_shell_rc_file(shell: str) -> Optional[Path]:
    """
    Get the RC file path for the given shell.

    Args:
        shell: Shell name ('bash', 'zsh', 'fish')

    Returns:
        Path to RC file or None if not found
    """
    home = Path.home()

    if shell == "bash":
        # Prefer .bashrc, fallback to .bash_profile
        bashrc = home / ".bashrc"
        bash_profile = home / ".bash_profile"
        if bashrc.exists():
            return bashrc
        elif bash_profile.exists():
            return bash_profile
        else:
            # Create .bashrc if neither exists
            return bashrc
    elif shell == "zsh":
        return home / ".zshrc"
    elif shell == "fish":
        # Fish uses a completions directory
        return home / ".config" / "fish" / "completions" / "nextdns-blocker.fish"

    return None


def is_completion_installed(shell: str) -> bool:
    """
    Check if shell completion is already installed.

    Args:
        shell: Shell name ('bash', 'zsh', 'fish')

    Returns:
        True if completion is installed
    """
    rc_file = get_shell_rc_file(shell)
    if not rc_file or not rc_file.exists():
        return False

    try:
        content = rc_file.read_text(encoding="utf-8")
        # Check for our marker or the completion line
        if COMPLETION_MARKER in content:
            return True
        if shell == "bash" and COMPLETION_LINE_BASH in content:
            return True
        if shell == "zsh" and COMPLETION_LINE_ZSH in content:
            return True
        if shell == "fish" and COMPLETION_LINE_FISH in content:
            return True
    except (OSError, UnicodeDecodeError) as e:
        logger.debug(f"Could not check completion status for {shell}: {e}")

    return False


def install_completion(shell: str) -> tuple[bool, str]:
    """
    Install shell completion for the given shell.

    Args:
        shell: Shell name ('bash', 'zsh', 'fish')

    Returns:
        Tuple of (success, message)
    """
    if is_completion_installed(shell):
        rc_file = get_shell_rc_file(shell)
        return True, f"Already installed in {rc_file}"

    rc_file = get_shell_rc_file(shell)
    if not rc_file:
        return False, f"Could not determine RC file for {shell}"

    try:
        # Ensure parent directory exists (for fish)
        rc_file.parent.mkdir(parents=True, exist_ok=True)

        if shell == "fish":
            # Fish uses a separate completion file
            completion_content = f"""{COMPLETION_MARKER}
{COMPLETION_LINE_FISH}
"""
            rc_file.write_text(completion_content, encoding="utf-8")
        else:
            # Bash/Zsh: append to RC file
            completion_line = COMPLETION_LINE_BASH if shell == "bash" else COMPLETION_LINE_ZSH
            append_content = f"\n{COMPLETION_MARKER}\n{completion_line}\n"

            with open(rc_file, "a", encoding="utf-8") as f:
                f.write(append_content)

        return True, f"Installed in {rc_file}"

    except PermissionError:
        return False, f"Permission denied: {rc_file}"
    except OSError as e:
        return False, f"Failed to install: {e}"
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        return False, f"Encoding error during install: {e}"


def uninstall_completion(shell: str) -> tuple[bool, str]:
    """
    Remove shell completion for the given shell.

    Args:
        shell: Shell name ('bash', 'zsh', 'fish')

    Returns:
        Tuple of (success, message)
    """
    rc_file = get_shell_rc_file(shell)
    if not rc_file or not rc_file.exists():
        return True, "Nothing to remove"

    try:
        if shell == "fish":
            # Just delete the fish completion file
            rc_file.unlink()
            return True, f"Removed {rc_file}"

        # Bash/Zsh: remove our lines from RC file
        content = rc_file.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        new_lines = []
        skip_next = False

        for line in lines:
            if COMPLETION_MARKER in line:
                skip_next = True
                continue
            if skip_next:
                # Skip the completion line after our marker
                if "_NEXTDNS_BLOCKER_COMPLETE" in line:
                    skip_next = False
                    continue
                skip_next = False
            new_lines.append(line)

        rc_file.write_text("".join(new_lines), encoding="utf-8")
        return True, f"Removed from {rc_file}"

    except PermissionError:
        return False, f"Permission denied: {rc_file}"
    except OSError as e:
        return False, f"Failed to remove: {e}"
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        return False, f"Encoding error during removal: {e}"
