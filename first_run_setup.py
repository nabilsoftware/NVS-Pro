"""
Nabil Video Studio Pro - First Run Setup
Installs all packages via pip in stages to avoid dependency conflicts
"""
import sys
import os
import subprocess
import time
import shutil
import winreg
import urllib.request
from pathlib import Path
from datetime import datetime

# Get script directory
SCRIPT_DIR = Path(__file__).parent.resolve()
EMBEDDED_PYTHON = SCRIPT_DIR / "python" / "python.exe"
SETUP_COMPLETE_FLAG = SCRIPT_DIR / "setup_complete.flag"
SITE_PACKAGES = SCRIPT_DIR / "python" / "Lib" / "site-packages"
LOG_FILE = SCRIPT_DIR / "logs" / "first_run_setup.log"

# Ensure logs directory exists
(SCRIPT_DIR / "logs").mkdir(exist_ok=True)

# ============================================================================
# LOGGING SYSTEM
# ============================================================================
def log(message, level="INFO"):
    """Log message to console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(message)  # Console (simpler)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")
    except:
        pass

def log_error(message):
    log(message, "ERROR")

def log_warning(message):
    log(message, "WARN")

# ============================================================================
# VISUAL C++ RUNTIME CHECK
# ============================================================================
def check_vc_runtime():
    """Check if Visual C++ Redistributable is installed"""
    log("Checking Visual C++ Runtime...")

    vc_keys = [
        # VC++ 2015-2022 x64
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        # Alternative locations
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
    ]

    for key_path in vc_keys:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            version, _ = winreg.QueryValueEx(key, "Version")
            winreg.CloseKey(key)
            log(f"  + Visual C++ Runtime found: {version}")
            return True
        except:
            continue

    return False

def install_vc_runtime():
    """Download and install Visual C++ Redistributable"""
    log("  ! Visual C++ Runtime not found - attempting to install...")

    # Microsoft's official download URL for VC++ 2015-2022 x64
    vc_url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    vc_installer = SCRIPT_DIR / "vc_redist.x64.exe"

    try:
        # Download
        log("  Downloading Visual C++ Redistributable...")
        urllib.request.urlretrieve(vc_url, vc_installer)

        # Install silently
        log("  Installing Visual C++ Redistributable...")
        result = subprocess.run(
            [str(vc_installer), "/install", "/quiet", "/norestart"],
            capture_output=True, timeout=300
        )

        # Clean up
        if vc_installer.exists():
            vc_installer.unlink()

        if result.returncode == 0:
            log("  + Visual C++ Runtime installed successfully!")
            return True
        else:
            log_warning("  ! VC++ install may require admin rights")
            return False

    except Exception as e:
        log_error(f"  ! Failed to install VC++ Runtime: {e}")
        log("  Please install manually from: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        return False

def ensure_vc_runtime():
    """Ensure Visual C++ Runtime is available"""
    if not check_vc_runtime():
        return install_vc_runtime()
    return True

# ============================================================================
# FFMPEG CHECK AND INSTALL
# ============================================================================
def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    log("Checking FFmpeg...")

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Extract version from output
            version_line = result.stdout.split('\n')[0] if result.stdout else "Unknown"
            log(f"  + FFmpeg found: {version_line[:50]}")
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        log_warning(f"  FFmpeg check error: {e}")

    return False

def install_ffmpeg():
    """Download and install FFmpeg"""
    log("  ! FFmpeg not found - downloading...")

    # FFmpeg download URL (essentials build from gyan.dev)
    ffmpeg_url = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"
    ffmpeg_zip = SCRIPT_DIR / "ffmpeg.zip"
    ffmpeg_dir = SCRIPT_DIR / "ffmpeg"

    try:
        # Download FFmpeg
        log("  Downloading FFmpeg (about 80 MB)...")
        print("      Downloading FFmpeg...")

        import ssl
        ssl_context = ssl.create_default_context()
        try:
            import certifi
            ssl_context.load_verify_locations(certifi.where())
        except Exception:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        req = urllib.request.urlopen(ffmpeg_url, context=ssl_context)
        with open(ffmpeg_zip, 'wb') as f:
            f.write(req.read())
        log("  Download complete, extracting...")
        print("      Extracting...")

        # Extract zip
        import zipfile
        with zipfile.ZipFile(ffmpeg_zip, 'r') as zip_ref:
            zip_ref.extractall(SCRIPT_DIR)

        # Find extracted folder (named like ffmpeg-7.1-essentials_build)
        extracted_folder = None
        for item in SCRIPT_DIR.iterdir():
            if item.is_dir() and item.name.startswith("ffmpeg-") and "essentials" in item.name:
                extracted_folder = item
                break

        if extracted_folder:
            # Move bin contents to ffmpeg folder
            ffmpeg_dir.mkdir(exist_ok=True)
            bin_folder = extracted_folder / "bin"

            if bin_folder.exists():
                for exe in bin_folder.glob("*.exe"):
                    dest = ffmpeg_dir / exe.name
                    if dest.exists():
                        dest.unlink()
                    shutil.move(str(exe), str(dest))
                log(f"  Moved FFmpeg executables to {ffmpeg_dir}")

            # Clean up extracted folder
            shutil.rmtree(extracted_folder, ignore_errors=True)

        # Clean up zip
        if ffmpeg_zip.exists():
            ffmpeg_zip.unlink()

        # Add to PATH for current session
        os.environ["PATH"] = str(ffmpeg_dir) + ";" + os.environ.get("PATH", "")

        # Verify installation
        ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
        if ffmpeg_exe.exists():
            log("  + FFmpeg installed successfully!")
            print("      FFmpeg installed!")
            return True
        else:
            log_error("  ! FFmpeg extraction failed")
            return False

    except Exception as e:
        log_error(f"  ! Failed to install FFmpeg: {e}")
        log("  Please install manually: winget install FFmpeg")
        print(f"      Failed: {e}")
        return False

def ensure_ffmpeg():
    """Ensure FFmpeg is available"""
    # First check if ffmpeg folder exists in app directory
    ffmpeg_dir = SCRIPT_DIR / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"

    if ffmpeg_exe.exists():
        # Add to PATH for current session
        os.environ["PATH"] = str(ffmpeg_dir) + ";" + os.environ.get("PATH", "")
        log(f"  + FFmpeg found in app folder")
        return True

    # Check bundled in assets/bin/
    assets_ffmpeg = SCRIPT_DIR / "assets" / "bin" / "ffmpeg.exe"
    if assets_ffmpeg.exists():
        os.environ["PATH"] = str(assets_ffmpeg.parent) + ";" + os.environ.get("PATH", "")
        log(f"  + FFmpeg found in assets/bin")
        return True

    # Check system PATH
    if check_ffmpeg():
        return True

    # Install FFmpeg
    return install_ffmpeg()

# Package groups - install in order to manage dependencies
PACKAGE_GROUPS = [
    # Stage 1: PyTorch with CUDA 12.8 (supports RTX 5080/5090 Blackwell sm_120)
    {
        "name": "PyTorch + CUDA",
        "packages": [
            "torch",
            "torchaudio",
            "torchvision",
        ],
        "pre": True,
        "index_url": "https://download.pytorch.org/whl/nightly/cu128"
    },
    # Stage 2: Core packages
    {
        "name": "Core Libraries",
        "packages": [
            "numpy==2.2.6",
            "scipy==1.16.3",
            "scikit-learn==1.7.2",
            "pandas==2.3.3",
        ]
    },
    # Stage 3: AI/ML packages
    {
        "name": "AI/ML Libraries",
        "packages": [
            "transformers==4.57.3",
            "huggingface-hub==0.36.0",
            "safetensors==0.7.0",
            "tokenizers==0.22.1",
            "sentencepiece==0.2.1",
            "pytorch-lightning==2.6.0",
        ]
    },
    # Stage 4: Pyannote (speaker diarization)
    {
        "name": "Pyannote (Speaker Diarization)",
        "packages": [
            "pyannote-audio>=4.0.0",
        ]
    },
    # Stage 5: Whisper (speech recognition)
    {
        "name": "Whisper (Speech Recognition)",
        "packages": [
            "faster-whisper==1.2.1",
            "ctranslate2==4.6.1",
            "openai-whisper",
        ]
    },
    # Stage 6: Demucs (audio separation)
    {
        "name": "Demucs (Audio Separation)",
        "packages": [
            "demucs",
        ]
    },
    # Stage 7: Video/Image processing
    {
        "name": "Video/Image Processing",
        "packages": [
            "opencv-python==4.12.0.88",
            "moviepy==2.2.1",
            "pillow==11.3.0",
            "imageio==2.37.2",
            "imageio-ffmpeg==0.6.0",
        ]
    },
    # Stage 8: Audio processing
    {
        "name": "Audio Processing",
        "packages": [
            "pydub==0.25.1",
            "soundfile==0.13.1",
            "av==16.0.1",
        ]
    },
    # Stage 9: AI Providers (Google + Anthropic)
    {
        "name": "AI Providers (Gemini + Claude)",
        "packages": [
            "google-generativeai==0.8.5",
            "anthropic",
        ]
    },
    # Stage 10: Web/Browser
    {
        "name": "Web/Browser Automation",
        "packages": [
            "selenium>=4.38.0",
            "playwright==1.56.0",
            "requests==2.32.5",
            "aiohttp==3.13.2",
        ]
    },
    # Stage 11: GUI
    {
        "name": "GUI (PyQt5)",
        "packages": [
            "PyQt5",
            "qtawesome==1.4.0",
        ]
    },
    # Stage 12: Utilities
    {
        "name": "Utilities",
        "packages": [
            "tqdm==4.67.1",
            "pyyaml==6.0.3",
            "python-dotenv==1.2.1",
            "coloredlogs==15.0.1",
            "rich==14.2.0",
            "yt-dlp",
            "numba==0.62.1",
            "matplotlib==3.10.7",
            "psutil",
        ]
    },
]

def get_python():
    """Get Python executable"""
    if EMBEDDED_PYTHON.exists():
        return str(EMBEDDED_PYTHON)
    return sys.executable

def fix_pip_user_install():
    """Fix pip trying to do --user installs with embedded Python.

    Embedded Python doesn't support --user installs (no USER_SITE).
    This can happen if there's a global pip.ini or pip config that sets user=true.
    We fix it by:
    1. Setting PIP_NO_USER=1 environment variable
    2. Creating a pip.ini in the embedded Python folder that explicitly disables user installs
    3. Ensuring the ._pth file includes site-packages
    """
    # Set environment variable globally for this process
    os.environ["PIP_NO_USER"] = "1"
    os.environ["PIP_USER"] = "0"

    # Create/update pip.ini to disable user installs
    pip_ini_dir = SCRIPT_DIR / "python"
    pip_ini = pip_ini_dir / "pip.ini"
    try:
        pip_ini.write_text("[install]\nuser = false\nno-user = true\n", encoding="utf-8")
        log(f"  Created {pip_ini} to disable --user installs")
    except Exception as e:
        log_warning(f"  Could not create pip.ini: {e}")

    # Also set PIP_CONFIG_FILE to point to our pip.ini
    os.environ["PIP_CONFIG_FILE"] = str(pip_ini)

    # Ensure ._pth file includes site-packages (critical for embedded Python)
    pth_files = list((SCRIPT_DIR / "python").glob("python*._pth"))
    for pth_file in pth_files:
        try:
            content = pth_file.read_text(encoding="utf-8")
            if "Lib\\site-packages" not in content and "Lib/site-packages" not in content:
                # Add site-packages path
                if not content.endswith("\n"):
                    content += "\n"
                content += "Lib\\site-packages\n"
                pth_file.write_text(content, encoding="utf-8")
                log(f"  Added site-packages to {pth_file.name}")
        except Exception as e:
            log_warning(f"  Could not update {pth_file.name}: {e}")

def print_header():
    """Print setup header"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 70)
    print("   Nabil Video Studio Pro - FIRST TIME SETUP")
    print("   Installing AI Components via pip (Stage-by-Stage)")
    print("=" * 70)
    print()
    print("   This will download approximately 3-4 GB of data.")
    print("   Please keep this window open and wait patiently.")
    print("   Estimated time: 20-45 minutes depending on internet speed.")
    print()
    print("=" * 70)
    print()

def clean_site_packages():
    """Delete existing site-packages to ensure clean install (only on first install)"""
    print("\n[2/6] Checking packages directory...")

    if SITE_PACKAGES.exists():
        # If torch is already installed, don't wipe packages - just ensure directory exists
        torch_dir = SITE_PACKAGES / "torch"
        if torch_dir.exists():
            print("  + Packages already present, skipping clean")
            return True

        keep_patterns = ['pip', 'pip-', 'setuptools', 'setuptools-', 'pkg_resources', '_distutils_hack', 'wheel']

        deleted_count = 0
        for item in SITE_PACKAGES.iterdir():
            should_keep = any(item.name.startswith(p) or item.name == p for p in keep_patterns)

            if not should_keep:
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink()
                    deleted_count += 1
                except:
                    pass

        print(f"  + Cleaned {deleted_count} old packages/files")
    else:
        SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
        print("  + Created site-packages directory")

    return True

def install_pip():
    """Ensure pip is installed and upgraded with build tools"""
    python = get_python()
    print("\n[3/6] Installing pip and build tools...")

    # Fix --user install issue BEFORE any pip commands
    fix_pip_user_install()

    get_pip = SCRIPT_DIR / "python" / "get-pip.py"
    if get_pip.exists():
        try:
            subprocess.run(
                [python, str(get_pip), "--no-warn-script-location", "--no-user"],
                capture_output=True, text=True, timeout=120
            )
        except:
            pass

    # Install/upgrade pip
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "--upgrade", "pip",
             "--no-warn-script-location", "--no-user"],
            capture_output=True, text=True, timeout=120
        )
        print("  + pip upgraded")
    except:
        pass

    # Install build tools - use --ignore-installed for setuptools (fixes broken embedded Python setuptools)
    # These are CRITICAL for building packages from source
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "--ignore-installed",
             "setuptools", "wheel", "build", "packaging", "Cython",
             "--no-warn-script-location", "--no-compile", "--no-user"],
            capture_output=True, text=True, timeout=180
        )
        print("  + Build tools installed (setuptools, wheel, build, Cython)")
    except:
        print("  ! Build tools may be incomplete")

    # Install numpy early - many packages need it during build
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "numpy",
             "--no-warn-script-location", "--no-compile", "--no-user"],
            capture_output=True, text=True, timeout=180
        )
        print("  + NumPy installed (required for building other packages)")
    except:
        print("  ! NumPy install failed (will retry later)")

    return True

def install_package_group(group, group_num, total_groups):
    """Install a group of packages"""
    python = get_python()
    name = group["name"]
    packages = group["packages"]
    extra_index = group.get("extra_index", None)
    index_url = group.get("index_url", None)
    use_pre = group.get("pre", False)

    print(f"\n  [{group_num}/{total_groups}] Installing {name}...")

    # Build pip command
    cmd = [python, "-m", "pip", "install"]
    if use_pre:
        cmd.append("--pre")
    cmd.extend(packages)
    # --no-user: CRITICAL - prevents "Can not perform a '--user' install" error with embedded Python
    # --prefer-binary: Use pre-built wheels when available (faster, no build errors)
    cmd.extend(["--no-user", "--no-warn-script-location", "--disable-pip-version-check", "--prefer-binary", "--no-compile"])

    if index_url:
        cmd.extend(["--index-url", index_url])
    elif extra_index:
        cmd.extend(["--extra-index-url", extra_index])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min timeout per group
            encoding='utf-8',
            errors='replace',
        )

        if result.returncode == 0:
            print(f"      [OK] {name}")
            return True
        else:
            # If first attempt fails, retry with --target pointing to site-packages
            site_packages = SCRIPT_DIR / "python" / "Lib" / "site-packages"
            if site_packages.exists():
                cmd_retry = [python, "-m", "pip", "install"]
                if use_pre:
                    cmd_retry.append("--pre")
                cmd_retry.extend(packages)
                cmd_retry.extend([
                    "--target", str(site_packages),
                    "--no-user", "--no-warn-script-location", "--disable-pip-version-check",
                    "--prefer-binary", "--no-compile"
                ])
                if index_url:
                    cmd_retry.extend(["--index-url", index_url])
                elif extra_index:
                    cmd_retry.extend(["--extra-index-url", extra_index])

                result2 = subprocess.run(
                    cmd_retry,
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    encoding='utf-8',
                    errors='replace',
                )
                if result2.returncode == 0:
                    print(f"      [OK] {name} (installed with --target)")
                    return True

            # Show error but continue
            error_lines = result.stderr.strip().split('\n') if result.stderr else []
            if error_lines:
                print(f"      [!] {name} - Warning: {error_lines[-1][:60]}")
            else:
                print(f"      [!] {name} - Warning: Some packages may have issues")
            return False

    except subprocess.TimeoutExpired:
        print(f"      [!] {name} - Timeout (continuing...)")
        return False
    except Exception as e:
        print(f"      [!] {name} - Error: {str(e)[:50]}")
        return False

def install_packages_staged():
    """Install all packages in stages with retry for failed groups"""
    print("\n[3/6] Installing packages in stages...")
    log("Starting package installation...")
    print("      This will take 20-45 minutes. Please wait...\n")
    print("-" * 70)

    total_groups = len(PACKAGE_GROUPS)
    successful = 0
    failed_groups = []

    # First pass - install all groups
    for i, group in enumerate(PACKAGE_GROUPS, 1):
        if install_package_group(group, i, total_groups):
            successful += 1
            log(f"  [OK] {group['name']}")
        else:
            failed_groups.append((i, group))
            log_error(f"  [FAIL] {group['name']}")

    # Retry failed groups
    if failed_groups:
        print("\n" + "-" * 70)
        print(f"  ⚠ Retrying {len(failed_groups)} failed package group(s)...")
        log(f"Retrying {len(failed_groups)} failed groups...")
        print("-" * 70)

        still_failed = []
        for i, group in failed_groups:
            print(f"\n  [RETRY] {group['name']}...")
            time.sleep(2)  # Small delay before retry
            if install_package_group(group, i, total_groups):
                successful += 1
                log(f"  [RETRY OK] {group['name']}")
            else:
                still_failed.append(group['name'])
                log_error(f"  [RETRY FAIL] {group['name']}")

        if still_failed:
            print(f"\n  ❌ These packages still failed after retry:")
            for name in still_failed:
                print(f"      - {name}")
            log_error(f"Failed packages: {', '.join(still_failed)}")

    print("-" * 70)
    print(f"  Stages completed: {successful}/{total_groups} successful")
    log(f"Package installation complete: {successful}/{total_groups}")

    return len(failed_groups) - (len(failed_groups) - successful) < 3  # Allow up to 2 final failures

def patch_installed_packages():
    """Patch installed packages for compatibility with PyTorch nightly + pyannote-audio 4.0+

    Two patches are needed:
    1. pyannote/audio/core/io.py - torchcodec may fail to load FFmpeg DLLs on Windows.
       Add ffmpeg/ffprobe subprocess fallback so audio decoding works without torchcodec.
    2. speechbrain/utils/torch_audio_backend.py - torchaudio 2.11+ removed list_audio_backends().
       Add hasattr guards so speechbrain doesn't crash on import.
    """
    print("\n[4b/6] Patching packages for compatibility...")
    log("Applying post-install patches...")

    patched = 0

    # ---- Patch 0: Uninstall torchcodec ----
    # torchcodec requires FFmpeg shared DLLs which aren't available on Windows.
    # It gets imported by demucs/torchaudio and crashes the whole pipeline.
    # pyannote's io.py is patched below to use ffmpeg subprocess instead.
    python = get_python()
    tc_dir = SITE_PACKAGES / "torchcodec"
    if tc_dir.exists():
        try:
            result = subprocess.run(
                [python, "-m", "pip", "uninstall", "torchcodec", "-y",
                 "--no-warn-script-location"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                print("      [OK] Uninstalled torchcodec (incompatible with Windows)")
                log("  Uninstalled torchcodec")
                patched += 1
            else:
                print("      [!] Failed to uninstall torchcodec")
        except Exception as e:
            print(f"      [!] Error uninstalling torchcodec: {e}")
    else:
        print("      [OK] torchcodec not present (good)")

    # ---- Patch 1: pyannote/audio/core/io.py ----
    io_py = SITE_PACKAGES / "pyannote" / "audio" / "core" / "io.py"
    if io_py.exists():
        try:
            content = io_py.read_text(encoding="utf-8")
            # Only patch if not already patched (check for our marker)
            if "TORCHCODEC_AVAILABLE" not in content and "torchcodec" in content:
                # Replace the torchcodec import block with our fallback version
                # The original typically has:
                #   from torchcodec.decoders import AudioDecoder, AudioStreamMetadata
                # We wrap it in a try/except with ffmpeg fallback

                old_import = None
                # Find the torchcodec import block - could be bare imports or wrapped in try/except
                import re as _re_patch
                lines = content.split("\n")
                start_idx = None
                end_idx = None

                # First, check if torchcodec imports are inside a try/except block (pyannote 4.0+)
                try_except_match = _re_patch.search(
                    r'^(try:\s*\n(?:.*torchcodec.*\n)+(?:.*\n)*?except\s+\w+[^\n]*:\s*\n(?:(?:    .*|[ \t]*)\n)*)',
                    content, _re_patch.MULTILINE
                )

                if try_except_match:
                    # Found try/except block - find its line range
                    block_start = content[:try_except_match.start()].count("\n")
                    block_text = try_except_match.group(0)
                    block_lines = block_text.rstrip("\n").split("\n")
                    start_idx = block_start
                    end_idx = block_start + len(block_lines) - 1
                else:
                    # Fallback: find bare torchcodec import lines
                    for i, line in enumerate(lines):
                        if "from torchcodec" in line or "import torchcodec" in line:
                            if start_idx is None:
                                start_idx = i
                            end_idx = i

                    if start_idx is not None:
                        # Collect all consecutive torchcodec import lines
                        import_lines = []
                        for i in range(start_idx, len(lines)):
                            if "torchcodec" in lines[i] or (lines[i].strip().startswith("from torchcodec") or lines[i].strip().startswith("import torchcodec")):
                                import_lines.append(i)
                                end_idx = i
                            elif lines[i].strip() == "" or lines[i].strip().startswith("#"):
                                continue
                            elif import_lines:
                                break

                if start_idx is not None:
                    # Build the replacement block (always at top-level indent)
                    indent = ""

                    replacement = f'''{indent}TORCHCODEC_AVAILABLE = False
{indent}try:
{indent}    import torchcodec
{indent}    from torchcodec import AudioSamples
{indent}    from torchcodec.decoders import AudioDecoder, AudioStreamMetadata
{indent}    TORCHCODEC_AVAILABLE = True
{indent}except Exception as _torchcodec_err:
{indent}    import warnings as _w
{indent}    _w.warn(
{indent}        "\\ntorchcodec is not available. Falling back to ffmpeg for audio decoding.\\n"
{indent}        f"Error: {{_torchcodec_err}}"
{indent}    )
{indent}
{indent}    import torch as _torch_fb
{indent}    import subprocess as _sp_fb
{indent}    import json as _json_fb
{indent}    import numpy as _np_fb
{indent}    import shutil as _shutil_fb
{indent}
{indent}    def _find_ffprobe():
{indent}        p = _shutil_fb.which("ffprobe")
{indent}        if p:
{indent}            return p
{indent}        for candidate in [
{indent}            Path(__file__).parent.parent.parent.parent / "assets" / "bin" / "ffprobe.exe",
{indent}            Path(__file__).parent.parent.parent.parent / "ffmpeg" / "ffprobe.exe",
{indent}        ]:
{indent}            if candidate.exists():
{indent}                return str(candidate)
{indent}        return "ffprobe"
{indent}
{indent}    _FFPROBE = _find_ffprobe()
{indent}
{indent}    class _FallbackMetadata:
{indent}        def __init__(self, audio_path):
{indent}            audio_path = str(audio_path)
{indent}            result = _sp_fb.run(
{indent}                [_FFPROBE, "-v", "error", "-select_streams", "a:0",
{indent}                 "-show_entries", "stream=sample_rate,channels,duration",
{indent}                 "-show_entries", "format=duration",
{indent}                 "-of", "json", audio_path],
{indent}                capture_output=True, text=True, timeout=30
{indent}            )
{indent}            data = _json_fb.loads(result.stdout)
{indent}            stream = {{}}
{indent}            for s in data.get("streams", []):
{indent}                stream = s
{indent}                break
{indent}            fmt = data.get("format", {{}})
{indent}            self.sample_rate = int(stream.get("sample_rate", 16000))
{indent}            self.num_channels = int(stream.get("channels", 1))
{indent}            dur = stream.get("duration") or fmt.get("duration")
{indent}            self.duration_seconds_from_header = float(dur) if dur else 0.0
{indent}
{indent}    def _load_audio_ffmpeg(audio_path, offset=None, duration=None):
{indent}        audio_path = str(audio_path)
{indent}        meta = _FallbackMetadata(audio_path)
{indent}        sr = meta.sample_rate
{indent}        cmd = ["ffmpeg", "-v", "error", "-i", audio_path]
{indent}        if offset is not None:
{indent}            cmd.extend(["-ss", str(offset)])
{indent}        if duration is not None:
{indent}            cmd.extend(["-t", str(duration)])
{indent}        cmd.extend(["-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(sr), "-ac", "1", "pipe:1"])
{indent}        result = _sp_fb.run(cmd, capture_output=True, timeout=300)
{indent}        audio_data = _np_fb.frombuffer(result.stdout, dtype=_np_fb.int16).astype(_np_fb.float32) / 32768.0
{indent}        waveform = _torch_fb.from_numpy(audio_data).unsqueeze(0)
{indent}        return waveform, sr
{indent}
{indent}    class AudioDecoder:
{indent}        def __init__(self, audio_path):
{indent}            self.audio_path = str(audio_path)
{indent}            self.metadata = _FallbackMetadata(audio_path)
{indent}        def get_all_samples(self):
{indent}            waveform, sample_rate = _load_audio_ffmpeg(self.audio_path)
{indent}            return _FallbackSamples(waveform, sample_rate)
{indent}        def get_samples_played_in_range(self, start, end):
{indent}            waveform, sample_rate = _load_audio_ffmpeg(
{indent}                self.audio_path, offset=start, duration=end - start
{indent}            )
{indent}            return _FallbackSamples(waveform, sample_rate)
{indent}
{indent}    class _FallbackSamples:
{indent}        def __init__(self, data, sample_rate):
{indent}            self.data = data
{indent}            self.sample_rate = sample_rate
{indent}
{indent}    class AudioStreamMetadata:
{indent}        pass'''

                    # Replace the original import lines
                    new_lines = lines[:start_idx]
                    new_lines.append(replacement)
                    new_lines.extend(lines[end_idx + 1:])

                    io_py.write_text("\n".join(new_lines), encoding="utf-8")
                    print("      [OK] Patched pyannote/audio/core/io.py (torchcodec fallback)")
                    log("  Patched pyannote/audio/core/io.py")
                    patched += 1
                else:
                    print("      [!] Could not find torchcodec imports in io.py")
            elif "TORCHCODEC_AVAILABLE" in content:
                print("      [OK] pyannote/audio/core/io.py already patched")
            else:
                print("      [-] pyannote/audio/core/io.py - no torchcodec imports found")
        except Exception as e:
            log_error(f"  Failed to patch io.py: {e}")
            print(f"      [!] Failed to patch pyannote io.py: {e}")
    else:
        print("      [-] pyannote/audio/core/io.py not found (pyannote not installed yet?)")

    # ---- Patch 2: speechbrain/utils/torch_audio_backend.py ----
    sb_py = SITE_PACKAGES / "speechbrain" / "utils" / "torch_audio_backend.py"
    if sb_py.exists():
        try:
            content = sb_py.read_text(encoding="utf-8")
            if "hasattr(torchaudio" not in content and "list_audio_backends" in content:
                # Replace all bare calls to torchaudio.list_audio_backends()
                # with hasattr-guarded versions
                content = content.replace(
                    "torchaudio.list_audio_backends()",
                    '(torchaudio.list_audio_backends() if hasattr(torchaudio, "list_audio_backends") else [])'
                )
                sb_py.write_text(content, encoding="utf-8")
                print("      [OK] Patched speechbrain/utils/torch_audio_backend.py")
                log("  Patched speechbrain/utils/torch_audio_backend.py")
                patched += 1
            elif "hasattr(torchaudio" in content:
                print("      [OK] speechbrain/torch_audio_backend.py already patched")
            else:
                print("      [-] speechbrain/torch_audio_backend.py - no list_audio_backends found")
        except Exception as e:
            log_error(f"  Failed to patch speechbrain: {e}")
            print(f"      [!] Failed to patch speechbrain: {e}")
    else:
        print("      [-] speechbrain/utils/torch_audio_backend.py not found")

    # ---- Patch 3: torchaudio/__init__.py - soundfile fallback for load/save ----
    # torchaudio 2.11+ delegates load() and save() entirely to torchcodec which
    # doesn't work on Windows (needs FFmpeg shared DLLs).
    # Replace the torchcodec import with a guarded version that checks if the
    # actual torchcodec package is available, and add soundfile fallbacks.
    ta_init = SITE_PACKAGES / "torchaudio" / "__init__.py"
    if ta_init.exists():
        try:
            content = ta_init.read_text(encoding="utf-8")
            if "_TORCHCODEC_AVAILABLE" not in content and "save_with_torchcodec" in content:
                # Replace the direct torchcodec import with a guarded version
                old_import = "from ._torchcodec import load_with_torchcodec, save_with_torchcodec"
                new_import = """# torchcodec may not be available on Windows - check if the actual package works
_TORCHCODEC_AVAILABLE = False
try:
    from ._torchcodec import load_with_torchcodec, save_with_torchcodec
    # Verify the actual torchcodec package is importable (not just the torchaudio wrapper)
    import torchcodec  # noqa: F401
    _TORCHCODEC_AVAILABLE = True
except (ImportError, OSError, RuntimeError):
    pass"""
                if old_import in content:
                    content = content.replace(old_import, new_import)

                # Patch load() - add soundfile fallback after the torchcodec call
                old_load = """    return load_with_torchcodec(
        uri,
        frame_offset=frame_offset,
        num_frames=num_frames,
        normalize=normalize,
        channels_first=channels_first,
        format=format,
        buffer_size=buffer_size,
        backend=backend,
    )"""
                new_load = """    if _TORCHCODEC_AVAILABLE:
        return load_with_torchcodec(
            uri,
            frame_offset=frame_offset,
            num_frames=num_frames,
            normalize=normalize,
            channels_first=channels_first,
            format=format,
            buffer_size=buffer_size,
            backend=backend,
        )
    # Fallback: use soundfile for loading audio
    import soundfile as sf
    import numpy as np
    data, sr = sf.read(str(uri), dtype='float32')
    if data.ndim == 1:
        data = data[np.newaxis, :]  # (1, time)
    else:
        data = data.T  # (channels, time)
    if frame_offset > 0:
        data = data[:, frame_offset:]
    if num_frames > 0:
        data = data[:, :num_frames]
    waveform = torch.from_numpy(data)
    if not channels_first:
        waveform = waveform.T
    return waveform, sr"""
                if old_load in content:
                    content = content.replace(old_load, new_load)

                # Patch save() - add soundfile fallback after the torchcodec call
                old_save = """    return save_with_torchcodec(
        uri,
        src,
        sample_rate,
        channels_first=channels_first,
        format=format,
        encoding=encoding,
        bits_per_sample=bits_per_sample,
        buffer_size=buffer_size,
        backend=backend,
        compression=compression,
    )"""
                new_save = """    if _TORCHCODEC_AVAILABLE:
        return save_with_torchcodec(
            uri,
            src,
            sample_rate,
            channels_first=channels_first,
            format=format,
            encoding=encoding,
            bits_per_sample=bits_per_sample,
            buffer_size=buffer_size,
            backend=backend,
            compression=compression,
        )
    # Fallback: save using soundfile when torchcodec is not available
    import soundfile as sf
    if src.ndim == 1:
        src = src.unsqueeze(0)
    if channels_first:
        audio_np = src.T.cpu().numpy()
    else:
        audio_np = src.cpu().numpy()
    sf.write(str(uri), audio_np, sample_rate)"""
                if old_save in content:
                    content = content.replace(old_save, new_save)

                ta_init.write_text(content, encoding="utf-8")
                print("      [OK] Patched torchaudio/__init__.py (soundfile fallback for load/save)")
                log("  Patched torchaudio/__init__.py")
                patched += 1
            elif "_TORCHCODEC_AVAILABLE" in content:
                print("      [OK] torchaudio/__init__.py already patched")
            else:
                print("      [-] torchaudio/__init__.py - no save_with_torchcodec found")
        except Exception as e:
            log_error(f"  Failed to patch torchaudio: {e}")
            print(f"      [!] Failed to patch torchaudio: {e}")
    else:
        print("      [-] torchaudio/__init__.py not found")

    print(f"      Applied {patched} patch(es)")
    log(f"Post-install patches applied: {patched}")
    return True

def install_playwright_browsers():
    """Install Playwright browsers"""
    print("\n[5/6] Installing Playwright browsers...")

    python = get_python()
    try:
        result = subprocess.run(
            [python, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print("  + Playwright Chromium installed!")
        else:
            print("  - Playwright install skipped (optional)")
        return True
    except:
        print("  - Playwright install skipped (optional)")
        return True

def verify():
    """Quick verification of critical packages"""
    print("\n[6/6] Verifying installation...")
    print("-" * 70)

    python = get_python()

    # Build environment with DLL paths for torch, etc.
    env = os.environ.copy()
    site_packages = SCRIPT_DIR / "python" / "Lib" / "site-packages"
    dll_paths = [
        str(site_packages / "torch" / "lib"),
        str(site_packages / "torch" / "bin"),
        str(SCRIPT_DIR / "python"),
        str(SCRIPT_DIR / "python" / "Scripts"),
    ]
    env["PATH"] = ";".join(dll_paths) + ";" + env.get("PATH", "")

    checks = [
        ("import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}')", "PyTorch"),
        ("import numpy; print(f'NumPy {numpy.__version__}')", "NumPy"),
        ("import pyannote.audio; print('OK')", "Pyannote"),
        ("import whisper; print('OK')", "Whisper"),
        ("import faster_whisper; print('OK')", "Faster Whisper"),
        ("import demucs; print('OK')", "Demucs"),
        ("import cv2; print(f'OpenCV {cv2.__version__}')", "OpenCV"),
        ("from PyQt5.QtWidgets import QApplication; print('OK')", "PyQt5"),
        ("import google.generativeai; print('OK')", "Gemini AI"),
        ("import anthropic; print('OK')", "Anthropic Claude"),
        ("import transformers; print('OK')", "Transformers"),
        ("import selenium; print('OK')", "Selenium"),
    ]

    all_ok = True
    passed = 0
    failed = 0

    for code, name in checks:
        try:
            result = subprocess.run(
                [python, "-B", "-c", code],
                capture_output=True, text=True, timeout=60,
                encoding='utf-8', errors='replace',
                env=env
            )
            if result.returncode == 0:
                output = result.stdout.strip()[:50] if result.stdout else "OK"
                print(f"  [OK] {name}: {output}")
                passed += 1
            else:
                err = result.stderr.strip().split('\n')[-1][:40] if result.stderr else "Failed"
                print(f"  [X]  {name}: {err}")
                failed += 1
                all_ok = False
        except Exception as e:
            print(f"  [X]  {name}: {str(e)[:30]}")
            failed += 1
            all_ok = False

    print("-" * 70)
    print(f"  Results: {passed} passed, {failed} failed")

    return all_ok

def create_flag(success):
    """Create setup complete flag"""
    try:
        with open(SETUP_COMPLETE_FLAG, 'w') as f:
            f.write(f"Setup completed: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Method: pip install staged\n")
            f.write(f"Success: {success}\n")
    except Exception as e:
        log_error(f"Failed to create setup flag: {e}")

def quick_check_already_installed():
    """Check if critical packages are already installed - skip setup if so"""
    python = get_python()

    # Build environment with DLL paths for torch
    env = os.environ.copy()
    site_packages = SCRIPT_DIR / "python" / "Lib" / "site-packages"
    dll_paths = [
        str(site_packages / "torch" / "lib"),
        str(site_packages / "torch" / "bin"),
        str(SCRIPT_DIR / "python"),
        str(SCRIPT_DIR / "python" / "Scripts"),
    ]
    env["PATH"] = ";".join(dll_paths) + ";" + env.get("PATH", "")

    # Quick checks - only test a few critical packages
    critical_checks = [
        "import torch",
        "import numpy",
        "import whisper",
        "from PyQt5.QtWidgets import QApplication",
        "import google.generativeai",
        "import cv2",
    ]

    for check in critical_checks:
        try:
            result = subprocess.run(
                [python, "-B", "-c", check],
                capture_output=True, text=True, timeout=30,
                encoding='utf-8', errors='replace',
                env=env
            )
            if result.returncode != 0:
                return False
        except:
            return False

    return True

def main():
    """Main setup function"""

    # Quick check: if packages are already installed, just ensure FFmpeg and patches, then skip
    if quick_check_already_installed():
        log("=" * 60)
        log("Nabil Video Studio Pro - FIRST RUN SETUP")
        log("=" * 60)
        log("All critical packages already installed")

        # Still check/install FFmpeg even if packages are installed
        print("=" * 70)
        print("   Checking FFmpeg...")
        ensure_ffmpeg()

        # Always run patches (torchcodec can sneak back in via dependency updates)
        patch_installed_packages()

        print("=" * 70)
        print("   All components already installed!")
        print("   Skipping first-time setup.")
        print("=" * 70)
        create_flag(True)
        return

    print_header()

    # Initialize log file
    log("=" * 60)
    log("Nabil Video Studio Pro - FIRST RUN SETUP")
    log("=" * 60)

    start_time = time.time()

    # Step 1: Check Visual C++ Runtime and FFmpeg
    print("\n[1/6] Checking system requirements...")
    ensure_vc_runtime()
    ensure_ffmpeg()

    # Step 2: Clean old packages
    clean_site_packages()

    # Step 3: Install/upgrade pip and build tools
    install_pip()

    # Step 4: Install packages in stages (with retry)
    install_ok = install_packages_staged()

    # Step 4b: Patch installed packages for compatibility
    patch_installed_packages()

    # Step 5: Install Playwright browsers
    install_playwright_browsers()

    # Step 6: Verify
    verify_ok = verify()

    # Calculate time
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Summary
    print("\n" + "=" * 70)
    if verify_ok:
        print("   SETUP COMPLETE!")
        print("=" * 70)
        print(f"   Time: {minutes}m {seconds}s")
        print("   All components installed successfully!")
        print("\n   You can now use Nabil Video Studio Pro.")
        log("SETUP COMPLETED SUCCESSFULLY")
        create_flag(True)
    else:
        print("   SETUP COMPLETE - WITH WARNINGS")
        print("=" * 70)
        print(f"   Time: {minutes}m {seconds}s")
        print("   Some components may have issues.")
        print("   Try running System Check in the app to fix problems.")
        log_warning("SETUP COMPLETED WITH WARNINGS")
        create_flag(False)

    print(f"\n   Log file: {LOG_FILE}")
    print("\n   Press Enter to close...")
    try:
        input()
    except (EOFError, OSError):
        pass

if __name__ == "__main__":
    main()
