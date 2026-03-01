"""
app_utils.py - Central Utility Module for Nabil Video Studio Pro

This module provides portable path handling that works in both:
- Development mode (running .py files directly)
- Frozen mode (running from PyInstaller exe)

All scripts should import from this module instead of hardcoding paths.
"""

import os
import sys
import platform
from pathlib import Path


# =============================================================================
# CORE PATH DETECTION
# =============================================================================

def is_frozen():
    """Check if running as a frozen (PyInstaller) application."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_app_dir():
    """
    Get the application's root directory.

    - In development: The folder containing the scripts
    - In frozen mode: The folder containing the exe
    """
    if is_frozen():
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # But for our setup, we want the folder where the exe is located
        return Path(sys.executable).parent
    else:
        # Development mode - return the script directory
        return Path(__file__).parent.resolve()


def get_base_dir():
    """
    Get the base directory for the application.
    Same as get_app_dir() but named for clarity.
    """
    return get_app_dir()


# =============================================================================
# USER DATA DIRECTORIES (AppData)
# =============================================================================

def get_user_data_dir():
    """
    Get the user data directory for storing configs, API keys, etc.

    Windows: C:/Users/<user>/AppData/Local/NabilVideoStudioPro
    Linux/Mac: ~/.nvspro
    """
    if os.name == 'nt':  # Windows
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        user_dir = Path(appdata) / "NabilVideoStudioPro"
    else:  # Linux/Mac
        user_dir = Path.home() / ".nvspro"

    # Create directory if it doesn't exist
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_cache_dir():
    """
    Get the cache directory for temporary files, model downloads, etc.

    Windows: C:/Users/<user>/AppData/Local/NabilVideoStudioPro/cache
    """
    cache_dir = get_user_data_dir() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_models_dir():
    """
    Get the directory for AI models (Whisper, Pyannote, etc.)

    Windows: C:/Users/<user>/AppData/Local/NabilVideoStudioPro/models
    """
    models_dir = get_user_data_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_logs_dir():
    """
    Get the directory for log files.

    Windows: C:/Users/<user>/AppData/Local/NabilVideoStudioPro/logs
    """
    logs_dir = get_user_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


# =============================================================================
# CONFIGURATION FILES
# =============================================================================

def get_config_path():
    """
    Get the path to config.json.

    Priority:
    1. User data dir (AppData) - for user customizations
    2. App directory - for default config
    """
    user_config = get_user_data_dir() / "config.json"
    if user_config.exists():
        return user_config

    # Fallback to app directory
    app_config = get_app_dir() / "config.json"
    return app_config


def get_api_keys_path():
    """
    Get the path to api_keys.json.

    Priority:
    1. User data dir (AppData) - where UI saves it
    2. App directory - fallback
    """
    user_keys = get_user_data_dir() / "api_keys.json"
    if user_keys.exists():
        return user_keys

    # Fallback to app directory
    app_keys = get_app_dir() / "api_keys.json"
    return app_keys


def get_license_path():
    """Get the path to the license file."""
    return get_user_data_dir() / "license.key"


def get_default_config_path():
    """Get the path to the default config template in assets."""
    return get_asset_path("defaults/config.json")


# =============================================================================
# ASSET PATHS (bundled resources)
# =============================================================================

def get_assets_dir():
    """
    Get the assets directory containing bundled resources.

    Structure:
    assets/
      bin/          - ffmpeg.exe, ffprobe.exe
      sounds/       - notification sounds
      defaults/     - default config templates
      icons/        - application icons
    """
    return get_app_dir() / "assets"


def get_asset_path(relative_path):
    """
    Get the full path to a bundled asset.

    Args:
        relative_path: Path relative to assets/ folder
                      e.g., "bin/ffmpeg.exe" or "sounds/notification.mp3"

    Returns:
        Path object to the asset
    """
    assets_dir = get_assets_dir()
    asset_path = assets_dir / relative_path

    # If asset doesn't exist in assets folder, check app root (legacy support)
    if not asset_path.exists():
        legacy_path = get_app_dir() / relative_path
        if legacy_path.exists():
            return legacy_path

    return asset_path


# =============================================================================
# FFMPEG / FFPROBE PATHS
# =============================================================================

def get_ffmpeg_path():
    """
    Get the path to ffmpeg executable.

    Priority:
    1. App ffmpeg folder (downloaded by first_run_setup)
    2. Bundled in assets/bin/ffmpeg.exe
    3. System PATH (ffmpeg command)
    """
    # Check app ffmpeg folder (first_run_setup downloads here)
    app_ffmpeg = get_app_dir() / "ffmpeg" / "ffmpeg.exe"
    if app_ffmpeg.exists():
        return str(app_ffmpeg)

    # Check bundled location
    bundled = get_asset_path("bin/ffmpeg.exe")
    if bundled.exists():
        return str(bundled)

    # Check app root (legacy)
    app_root = get_app_dir() / "ffmpeg.exe"
    if app_root.exists():
        return str(app_root)

    # Fall back to system PATH
    return "ffmpeg"


def get_ffprobe_path():
    """
    Get the path to ffprobe executable.

    Priority:
    1. App ffmpeg folder (downloaded by first_run_setup)
    2. Bundled in assets/bin/ffprobe.exe
    3. System PATH (ffprobe command)
    """
    # Check app ffmpeg folder (first_run_setup downloads here)
    app_ffprobe = get_app_dir() / "ffmpeg" / "ffprobe.exe"
    if app_ffprobe.exists():
        return str(app_ffprobe)

    # Check bundled location
    bundled = get_asset_path("bin/ffprobe.exe")
    if bundled.exists():
        return str(bundled)

    # Check app root (legacy)
    app_root = get_app_dir() / "ffprobe.exe"
    if app_root.exists():
        return str(app_root)

    # Fall back to system PATH
    return "ffprobe"


def check_ffmpeg_installed():
    """
    Check if ffmpeg is available (bundled or system).

    Returns:
        tuple: (is_installed: bool, path: str, source: str)
    """
    import subprocess

    # Check app ffmpeg folder first
    app_ffmpeg = get_app_dir() / "ffmpeg" / "ffmpeg.exe"
    if app_ffmpeg.exists():
        return (True, str(app_ffmpeg), "app_folder")

    # Check bundled
    bundled = get_asset_path("bin/ffmpeg.exe")
    if bundled.exists():
        return (True, str(bundled), "bundled")

    # Check system PATH
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return (True, "ffmpeg", "system")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return (False, None, None)


# =============================================================================
# NOTIFICATION SOUNDS
# =============================================================================

def get_notification_sound_path(sound_name="notification.mp3"):
    """
    Get the path to a notification sound.

    Args:
        sound_name: Name of the sound file (e.g., "work_work_work.mp3")
    """
    # Check assets/sounds folder
    sound_path = get_asset_path(f"sounds/{sound_name}")
    if sound_path.exists():
        return str(sound_path)

    # Check Notification folder (legacy)
    legacy_path = get_app_dir() / "Notification" / sound_name
    if legacy_path.exists():
        return str(legacy_path)

    return None


# =============================================================================
# SCRIPT PATHS
# =============================================================================

def get_script_path(script_name):
    """
    Get the path to a pipeline script.

    Args:
        script_name: Name of the script (e.g., "1_diarize_cut_video.py")
    """
    return get_app_dir() / script_name


def get_python_executable():
    """
    Get the path to the Python executable.

    - In frozen mode: Uses bundled Python
    - In development: Uses current Python
    """
    if is_frozen():
        # Check for bundled Python
        bundled_python = get_app_dir() / "python" / "python.exe"
        if bundled_python.exists():
            return str(bundled_python)

    return sys.executable


# =============================================================================
# HUGGINGFACE CACHE
# =============================================================================

def get_huggingface_cache_dir():
    """
    Get the HuggingFace cache directory.

    Default: ~/.cache/huggingface/hub
    """
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    return hf_cache


def get_huggingface_token_path():
    """
    Get the path to HuggingFace token file.

    Default: ~/.cache/huggingface/token
    """
    return Path.home() / ".cache" / "huggingface" / "token"


def load_huggingface_token():
    """
    Load HuggingFace token from cache file.

    Returns:
        str or None: The token if found, None otherwise
    """
    token_path = get_huggingface_token_path()
    if token_path.exists():
        try:
            return token_path.read_text().strip()
        except Exception:
            pass
    return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ensure_dir(path):
    """Ensure a directory exists, create if not."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(path_str, base_dir=None):
    """
    Resolve a path string to an absolute path.

    - If absolute, return as-is
    - If relative, resolve relative to base_dir (or app_dir)
    """
    if base_dir is None:
        base_dir = get_app_dir()

    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def get_temp_dir(prefix="nvsp_"):
    """
    Get a temporary directory for processing.

    Creates a unique temp folder in the cache directory.
    """
    import tempfile
    temp_base = get_cache_dir() / "temp"
    temp_base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=temp_base))


# =============================================================================
# SYSTEM INFO
# =============================================================================

def get_system_info():
    """Get system information for debugging."""
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": sys.version,
        "is_frozen": is_frozen(),
        "app_dir": str(get_app_dir()),
        "user_data_dir": str(get_user_data_dir()),
        "executable": sys.executable,
    }


def print_paths_info():
    """Print all path information for debugging."""
    print("=" * 60)
    print("Nabil Video Studio Pro - PATH INFORMATION")
    print("=" * 60)
    print(f"Running Mode:     {'FROZEN (EXE)' if is_frozen() else 'DEVELOPMENT (PY)'}")
    print(f"App Directory:    {get_app_dir()}")
    print(f"User Data Dir:    {get_user_data_dir()}")
    print(f"Assets Dir:       {get_assets_dir()}")
    print(f"Config Path:      {get_config_path()}")
    print(f"API Keys Path:    {get_api_keys_path()}")
    print(f"FFmpeg Path:      {get_ffmpeg_path()}")
    print(f"FFprobe Path:     {get_ffprobe_path()}")
    print(f"Python Exe:       {get_python_executable()}")
    print(f"Cache Dir:        {get_cache_dir()}")
    print(f"Models Dir:       {get_models_dir()}")
    print(f"Logs Dir:         {get_logs_dir()}")
    print("=" * 60)


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    print_paths_info()

    print("\nFFmpeg Check:")
    installed, path, source = check_ffmpeg_installed()
    if installed:
        print(f"  FFmpeg is available ({source}): {path}")
    else:
        print("  FFmpeg is NOT installed!")

    print("\nHuggingFace Token:")
    token = load_huggingface_token()
    if token:
        print(f"  Token found: {token[:10]}...{token[-4:]}")
    else:
        print("  No token found")
