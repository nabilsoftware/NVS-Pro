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

    Architecture:
    - NVS_Pro.exe (launcher) runs pythonw.exe ui_modern.py via subprocess.call (waits)
    - os._exit(0) kills pythonw.exe → NVS_Pro.exe also exits shortly after
    - We need to wait for BOTH processes to fully die before running the installer
    - If files are still locked, Inno Setup queues replacements for reboot (bad!)
    - Solution: PowerShell script force-kills both, verifies files are unlocked, then installs
    """
    try:
        # Call cleanup callback if provided (e.g., close all windows)
        if cleanup_callback:
            try:
                cleanup_callback()
            except Exception:
                pass

        # Determine the app exe path for relaunch after update
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        app_exe = os.path.join(app_dir, "NVS_Pro.exe")

        # Escape backslashes for PowerShell string embedding
        installer_ps = installer_path.replace("'", "''")
        app_exe_ps = app_exe.replace("'", "''")
        app_dir_ps = app_dir.replace("'", "''")

        # PowerShell script that handles the entire update process
        ps_path = os.path.join(tempfile.gettempdir(), "nvs_update.ps1")
        ps_content = f'''# NVS Pro Auto-Update Script
$ErrorActionPreference = "SilentlyContinue"

# Log file for debugging
$logFile = Join-Path $env:TEMP "nvs_update_log.txt"
"[$(Get-Date)] Update script started" | Out-File $logFile

# Step 1: Force-kill ALL app processes immediately
"[$(Get-Date)] Killing app processes..." | Out-File $logFile -Append
Stop-Process -Name "NVS_Pro" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "pythonw" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Step 2: Wait until NVS_Pro.exe and pythonw.exe are completely gone (up to 30 sec)
$waited = 0
while ($waited -lt 30) {{
    $nvs = Get-Process -Name "NVS_Pro" -ErrorAction SilentlyContinue
    $pyw = Get-Process -Name "pythonw" -ErrorAction SilentlyContinue
    if ((-not $nvs) -and (-not $pyw)) {{ break }}

    # Keep trying to kill them
    if ($nvs) {{ Stop-Process -Name "NVS_Pro" -Force -ErrorAction SilentlyContinue }}
    if ($pyw) {{ Stop-Process -Name "pythonw" -Force -ErrorAction SilentlyContinue }}

    Start-Sleep -Seconds 2
    $waited += 2
}}
"[$(Get-Date)] Processes gone after $waited sec" | Out-File $logFile -Append

# Step 3: Wait for file locks to release — test by opening a key file
$appDir = '{app_dir_ps}'
$testFile = Join-Path $appDir "ui_modern.py"
$unlocked = $false
for ($i = 0; $i -lt 15; $i++) {{
    try {{
        if (Test-Path $testFile) {{
            $stream = [System.IO.File]::Open($testFile, 'Open', 'ReadWrite', 'None')
            $stream.Close()
            $stream.Dispose()
            $unlocked = $true
            break
        }} else {{
            $unlocked = $true
            break
        }}
    }} catch {{
        Start-Sleep -Seconds 1
    }}
}}
"[$(Get-Date)] File unlock check: unlocked=$unlocked" | Out-File $logFile -Append

# Step 4: Run the installer silently and wait for it to finish
$installerPath = '{installer_ps}'
"[$(Get-Date)] Running installer: $installerPath" | Out-File $logFile -Append

$proc = Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /SP- /NORESTARTAPPLICATIONS" -Wait -PassThru -WindowStyle Hidden
"[$(Get-Date)] Installer exit code: $($proc.ExitCode)" | Out-File $logFile -Append

# Step 5: Verify the update was applied by checking if version.py was modified recently
Start-Sleep -Seconds 2
$versionFile = Join-Path $appDir "version.py"
if (Test-Path $versionFile) {{
    $lastWrite = (Get-Item $versionFile).LastWriteTime
    $age = (Get-Date) - $lastWrite
    "[$(Get-Date)] version.py last modified: $lastWrite (age: $($age.TotalSeconds) sec)" | Out-File $logFile -Append
    if ($age.TotalSeconds -gt 60) {{
        "[$(Get-Date)] WARNING: version.py was NOT updated — installer may have failed to replace files!" | Out-File $logFile -Append
    }}
}}

# Step 6: Relaunch the app
$appExe = '{app_exe_ps}'
if (Test-Path $appExe) {{
    "[$(Get-Date)] Relaunching: $appExe" | Out-File $logFile -Append
    Start-Process -FilePath $appExe
}} else {{
    "[$(Get-Date)] ERROR: App exe not found: $appExe" | Out-File $logFile -Append
}}

"[$(Get-Date)] Update script finished" | Out-File $logFile -Append
'''
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(ps_content)

        # Use a tiny VBScript to launch PowerShell completely hidden (no window at all)
        vbs_path = os.path.join(tempfile.gettempdir(), "nvs_update_launcher.vbs")
        # VBScript does NOT need escaped backslashes — just double-quotes via ""
        vbs_content = (
            'Set shell = CreateObject("WScript.Shell")\n'
            f'shell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{ps_path}""", 0, False\n'
        )
        with open(vbs_path, "w") as f:
            f.write(vbs_content)

        # Launch the VBScript (completely invisible, fully detached from our process)
        subprocess.Popen(
            ["wscript.exe", vbs_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        # Force exit the app immediately — this kills pythonw.exe
        # NVS_Pro.exe (parent, subprocess.call) will also exit shortly after
        os._exit(0)
    except Exception:
        # Fallback: just run the installer directly and exit
        try:
            subprocess.Popen(
                [installer_path, "/VERYSILENT", "/CLOSEAPPLICATIONS", "/SP-"],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            os._exit(0)
        except Exception:
            pass
