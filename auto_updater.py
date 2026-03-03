"""
Auto-Update System for Nabil Video Studio Pro
===============================================
Checks GitHub Releases for new versions, downloads and runs the installer.
"""

import json
import os
import sys
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from version import VERSION, VERSION_TUPLE


GITHUB_API_URL = "https://api.github.com/repos/nabilsoftware/NVS-Pro/releases/latest"
REQUEST_TIMEOUT = 10  # seconds
_SKIP_FILE = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "NabilVideoStudioPro", "skip_update.txt")


def is_update_skipped(version):
    """Check if the user chose to skip this version."""
    try:
        if os.path.exists(_SKIP_FILE):
            with open(_SKIP_FILE, "r") as f:
                return f.read().strip() == version
    except Exception:
        pass
    return False


def skip_update(version):
    """Save the version the user wants to skip."""
    try:
        os.makedirs(os.path.dirname(_SKIP_FILE), exist_ok=True)
        with open(_SKIP_FILE, "w") as f:
            f.write(version)
    except Exception:
        pass


def _parse_version(tag: str) -> tuple:
    """Parse version tag like 'v1.3.0' or '1.3.0' into a comparable tuple."""
    try:
        tag = tag.lstrip("vV")
        # Strip suffixes like -beta, -rc.1
        if "-" in tag:
            tag = tag.split("-")[0]
        parts = tag.split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_for_update():
    """
    Check GitHub for a newer release.

    Returns:
        (has_update, latest_version, download_url, release_notes)
        On error, returns (False, None, None, None).
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "NVS-Pro-Updater"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")
        latest_tuple = _parse_version(tag)
        local_tuple = VERSION_TUPLE[:3]

        if latest_tuple <= local_tuple:
            return (False, None, None, None)

        # Find the .exe asset
        download_url = None
        for asset in data.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            return (False, None, None, None)

        latest_version = tag.lstrip("vV")
        release_notes = data.get("body", "") or ""

        return (True, latest_version, download_url, release_notes)

    except Exception:
        return (False, None, None, None)


def download_update(download_url, progress_callback=None):
    """
    Download the installer .exe to a temp folder.

    Uses a unique filename to avoid conflicts with previous download attempts.

    Returns:
        Path to the downloaded file, or None on failure.
    """
    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "NVS-Pro-Updater"},
        )
        resp = urllib.request.urlopen(req, timeout=60)

        total = int(resp.headers.get("Content-Length", 0))

        # Use unique temp file to avoid conflicts with previous failed downloads
        dest_dir = os.path.join(tempfile.gettempdir(), "nvs_updates")
        os.makedirs(dest_dir, exist_ok=True)

        # Clean up old downloads first
        try:
            for f in os.listdir(dest_dir):
                try:
                    os.remove(os.path.join(dest_dir, f))
                except OSError:
                    pass  # File may be locked
        except Exception:
            pass

        filename = download_url.rsplit("/", 1)[-1]
        dest = os.path.join(dest_dir, filename)

        downloaded = 0
        chunk_size = 131072  # 128KB chunks for faster download

        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(int(downloaded * 100 / total))

        resp.close()

        # Verify the file was fully downloaded
        if total > 0 and downloaded < total:
            return None

        return dest

    except Exception:
        return None


def install_update(installer_path, cleanup_callback=None):
    """
    Launch the downloaded installer and exit the app.

    Just opens the installer .exe normally — user clicks Next/Next/Install like
    a regular install. Inno Setup handles closing the app (CloseApplications=force).
    """
    try:
        # Call cleanup callback if provided (e.g., close all windows)
        if cleanup_callback:
            try:
                cleanup_callback()
            except Exception:
                pass

        # Launch the installer normally — user sees the wizard and clicks through it
        subprocess.Popen(
            [installer_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        # Give the installer a moment to start
        time.sleep(1)

        # Exit the app — Inno Setup will handle closing any remaining processes
        os._exit(0)
    except Exception:
        pass
