"""Platform detection utilities for NextDNS Blocker.

This module provides centralized platform detection functions for cross-platform
support including macOS, Linux, Windows, and WSL (Windows Subsystem for Linux).
"""

import platform
import shutil
import sys
from pathlib import Path
from typing import Literal, Optional

# Platform type for type hints
PlatformName = Literal["macos", "windows", "wsl", "linux", "unknown"]


def is_windows() -> bool:
    """Check if running on Windows.

    Returns:
        True if running on Windows, False otherwise.
    """
    return sys.platform == "win32"


def is_macos() -> bool:
    """Check if running on macOS.

    Returns:
        True if running on macOS, False otherwise.
    """
    return sys.platform == "darwin"


def is_linux() -> bool:
    """Check if running on Linux (including WSL).

    Returns:
        True if running on Linux or WSL, False otherwise.
    """
    return sys.platform.startswith("linux")


def is_wsl() -> bool:
    """Check if running on Windows Subsystem for Linux (WSL).

    WSL is detected by checking for 'microsoft' or 'WSL' in the kernel release.

    Returns:
        True if running on WSL, False otherwise.
    """
    if not is_linux():
        return False
    try:
        release = platform.release().lower()
        return "microsoft" in release or "wsl" in release
    except (OSError, AttributeError, RuntimeError, TypeError):
        # OSError: File system errors reading /proc
        # AttributeError: If release() returns unexpected type
        # RuntimeError/TypeError: Other platform-specific errors
        return False


def get_platform() -> PlatformName:
    """Get the current platform name.

    Returns:
        Platform name: "macos", "windows", "wsl", "linux", or "unknown".
    """
    if is_macos():
        return "macos"
    elif is_windows():
        return "windows"
    elif is_wsl():
        return "wsl"
    elif is_linux():
        return "linux"
    return "unknown"


def get_platform_display_name() -> str:
    """Get a human-readable platform name for display.

    Returns:
        Human-readable platform name (e.g., "macOS", "Windows", "Linux (WSL)").
    """
    plat = get_platform()
    display_names = {
        "macos": "macOS",
        "windows": "Windows",
        "wsl": "Linux (WSL)",
        "linux": "Linux",
        "unknown": "Unknown",
    }
    return display_names.get(plat, "Unknown")


def get_scheduler_type() -> Literal["launchd", "cron", "task_scheduler", "none"]:
    """Get the appropriate scheduler type for the current platform.

    Returns:
        Scheduler type: "launchd" (macOS), "cron" (Linux/WSL),
        "task_scheduler" (Windows), or "none" (unknown).
    """
    if is_macos():
        return "launchd"
    elif is_windows():
        return "task_scheduler"
    elif is_linux():
        # WSL uses cron since it's a full Linux environment
        return "cron"
    return "none"


def _find_executable() -> Optional[str]:
    """Find the nextdns-blocker executable path.

    Searches in order:
    1. System PATH (shutil.which)
    2. pipx default location (~/.local/bin)
    3. Windows Python Scripts folder
    4. Homebrew locations (macOS/Linux)

    Returns:
        Path to the executable, or None if not found.
    """
    # First, check system PATH
    exe_path = shutil.which("nextdns-blocker")
    if exe_path:
        return exe_path

    # Fallback: check pipx default location
    if is_windows():
        # Windows pipx location
        pipx_exe = Path.home() / ".local" / "bin" / "nextdns-blocker.exe"
        if pipx_exe.exists():
            return str(pipx_exe)
        # Also check Scripts folder for pip installs
        scripts_exe = (
            Path.home()
            / "AppData"
            / "Local"
            / "Programs"
            / "Python"
            / "Scripts"
            / "nextdns-blocker.exe"
        )
        if scripts_exe.exists():
            return str(scripts_exe)
    else:
        pipx_exe = Path.home() / ".local" / "bin" / "nextdns-blocker"
        if pipx_exe.exists():
            return str(pipx_exe)

    # Fallback: check Homebrew locations (macOS/Linux)
    if not is_windows():
        homebrew_paths = [
            Path("/opt/homebrew/bin/nextdns-blocker"),  # macOS ARM (Apple Silicon)
            Path("/usr/local/bin/nextdns-blocker"),  # macOS Intel / Homebrew on Linux
            Path("/home/linuxbrew/.linuxbrew/bin/nextdns-blocker"),  # Linuxbrew
        ]
        for brew_path in homebrew_paths:
            if brew_path.exists():
                return str(brew_path)

    return None


def get_executable_path() -> str:
    """Get the full path to the nextdns-blocker executable.

    Returns a string suitable for shell commands (cron, Task Scheduler).
    For launchd, use get_executable_args() instead.

    Returns:
        Path to the executable or fallback command string.
    """
    exe_path = _find_executable()
    if exe_path:
        return exe_path
    # Fallback to sys.executable module invocation
    return f"{sys.executable} -m nextdns_blocker"


def get_executable_args() -> list[str]:
    """Get the executable as a list of arguments for subprocess.

    Returns a list suitable for subprocess.run() and launchd ProgramArguments.

    Returns:
        List of command arguments.
    """
    exe_path = _find_executable()
    if exe_path:
        return [exe_path]
    # Fallback to sys.executable module invocation
    return [sys.executable, "-m", "nextdns_blocker"]


def get_config_base_dir() -> Path:
    """Get the base configuration directory for the current platform.

    This returns the platform-appropriate base directory:
    - Windows: %APPDATA%
    - macOS: ~/Library/Application Support
    - Linux: ~/.config (XDG_CONFIG_HOME)

    Note: This is a low-level function. Use config.get_config_dir() for
    the full configuration directory path.

    Returns:
        Base configuration directory path.
    """
    if is_windows():
        appdata = Path.home() / "AppData" / "Roaming"
        return appdata
    elif is_macos():
        return Path.home() / "Library" / "Application Support"
    else:
        # Linux/WSL: XDG convention
        xdg_config = Path.home() / ".config"
        return xdg_config


def get_data_base_dir() -> Path:
    """Get the base data directory for the current platform.

    This returns the platform-appropriate base directory:
    - Windows: %LOCALAPPDATA%
    - macOS: ~/Library/Application Support
    - Linux: ~/.local/share (XDG_DATA_HOME)

    Note: This is a low-level function. Use platformdirs for the full
    data directory path.

    Returns:
        Base data directory path.
    """
    if is_windows():
        return Path.home() / "AppData" / "Local"
    elif is_macos():
        return Path.home() / "Library" / "Application Support"
    else:
        # Linux/WSL: XDG convention
        return Path.home() / ".local" / "share"


def get_log_base_dir() -> Path:
    """Get the base log directory for the current platform.

    This returns the platform-appropriate base directory for logs:
    - Windows: %LOCALAPPDATA%
    - macOS/Linux: Same as data directory

    Returns:
        Base log directory path.
    """
    return get_data_base_dir()
