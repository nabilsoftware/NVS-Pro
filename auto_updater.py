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

    Args:
        download_url: URL of the installer asset.
        progress_callback: Optional callable(percent: int) for progress updates.

    Returns:
        Path to the downloaded file, or None on failure.
    """
    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "NVS-Pro-Updater"},
        )
        resp = urllib.request.urlopen(req, timeout=30)

        total = int(resp.headers.get("Content-Length", 0))
        filename = download_url.rsplit("/", 1)[-1]
        dest = os.path.join(tempfile.gettempdir(), filename)

        downloaded = 0
        chunk_size = 65536

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
        return dest

    except Exception:
        return None


def install_update(installer_path, cleanup_callback=None):
    """
    Launch the downloaded installer and exit the app.

    Args:
        installer_path: Path to the downloaded installer exe.
        cleanup_callback: Optional callable to cleanup/close windows before exit.
    """
    try:
        # Call cleanup callback if provided (e.g., close all windows)
        if cleanup_callback:
            try:
                cleanup_callback()
            except Exception:
                pass

        # Determine the app install directory for relaunch after update
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        app_exe = os.path.join(app_dir, "NVS_Pro.exe")

        # Create a batch script that:
        # 1. Waits for NVS_Pro.exe and pythonw.exe to fully exit
        # 2. Runs the installer silently
        # 3. Relaunches the app after install
        batch_content = f'''@echo off
:: Wait for NVS_Pro.exe to fully exit (up to 30 seconds)
set WAIT=0
:waitloop
tasklist /FI "IMAGENAME eq NVS_Pro.exe" 2>nul | find /I "NVS_Pro.exe" >nul
if errorlevel 1 goto :done_waiting
timeout /t 2 /nobreak >nul
set /a WAIT+=2
if %WAIT% GEQ 30 goto :force_kill
goto :waitloop

:force_kill
taskkill /F /IM NVS_Pro.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:done_waiting
:: Extra wait for DLLs to release
timeout /t 3 /nobreak >nul

:: Run the installer silently
"{installer_path}" /VERYSILENT /CLOSEAPPLICATIONS /SP-

:: Wait for installer to finish
:wait_installer
tasklist /FI "IMAGENAME eq NVS_Pro_v*" 2>nul | find /I "Setup" >nul
if not errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto :wait_installer
)
timeout /t 2 /nobreak >nul

:: Relaunch the app
if exist "{app_exe}" start "" "{app_exe}"

:: Clean up this batch file
del "%~f0"
'''
        batch_path = os.path.join(tempfile.gettempdir(), "nvs_update_launcher.bat")
        with open(batch_path, "w") as f:
            f.write(batch_content)

        # Launch the batch script (hidden window)
        subprocess.Popen(
            ["cmd", "/c", batch_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            shell=False,
        )

        # Force exit the app immediately
        os._exit(0)
    except Exception:
        # Fallback: try direct launch without batch script
        try:
            time.sleep(0.5)
            subprocess.Popen(
                [installer_path, "/VERYSILENT", "/CLOSEAPPLICATIONS", "/SP-"],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            os._exit(0)
        except Exception:
            pass
