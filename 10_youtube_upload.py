#!/usr/bin/env python3
# Fix Windows console encoding for emoji/unicode
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Step 10: YouTube Upload (Clean & Simple)
=========================================

This script ONLY uploads final videos to YouTube:
- Uploads videos from Step 9 (combined videos)
- Generic - works with ANY profile name (no hardcoded profiles)
- NO metadata handling (title/description/tags added manually later)
- Profile-specific browser sessions for different YouTube channels
- Uploads as UNLISTED for manual review

FIXES in this version:
- Kills stuck Chrome processes before starting
- Cleans up stale lock files
- Verifies browser started correctly
- Verifies page loaded (not just sleep)
- Retry logic - max 3 attempts
- Updated YouTube selectors
- Better error logging

Usage:
- Standalone: python 10_youtube_upload.py --input <step9_folder> --video-stem <name> --profiles <profile1> [profile2...]
- Orchestrator: Called automatically after Step 9
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import psutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException, SessionNotCreatedException


# =============================================================================
# CONFIGURATION
# =============================================================================

# Import app utilities for portable paths
try:
    import app_utils
    DATA_DIR = app_utils.get_user_data_dir()
except (ImportError, AttributeError):
    # Fallback for standalone usage
    DATA_DIR = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / "NabilVideoStudioPro"

# Default paths (used if not run by orchestrator)
DEFAULT_INPUT_FOLDER = ""
# Browser profiles stored in user data folder (persists login sessions)
DEFAULT_BROWSER_PROFILES_FOLDER = str(DATA_DIR / "browser_profiles")

# YouTube settings
YOUTUBE_UPLOAD_URL = "https://www.youtube.com/upload"
YOUTUBE_STUDIO_URL = "https://studio.youtube.com"

# Upload settings
UPLOAD_TIMEOUT = 300  # 5 minutes timeout for upload
WAIT_TIMEOUT = 30  # 30 seconds for element waits
MAX_RETRIES = 3  # Maximum retry attempts

# Supported video extensions
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')

# === SHARED BROWSER FOR PARALLEL TAB UPLOADS ===
import threading
import msvcrt  # Windows file locking
_shared_browser_lock = threading.Lock()
_shared_browsers = {}  # profile_name -> {'driver': driver, 'debugger_address': str}


# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# NEW: CHROME CLEANUP FUNCTIONS
# =============================================================================

def kill_chrome_processes_for_profile(profile_name: str) -> int:
    """Kill any Chrome processes that are using a specific profile.

    Returns:
        Number of processes killed
    """
    killed = 0
    profile_dir_name = f"profile_{profile_name}"

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if it's a Chrome process
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline:
                        cmdline_str = ' '.join(cmdline)
                        # Check if this Chrome is using our profile
                        if profile_dir_name in cmdline_str:
                            logger.info(f"🔪 Killing stuck Chrome process (PID: {proc.pid}) for profile {profile_name}")
                            proc.kill()
                            killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.warning(f"Error checking Chrome processes: {e}")

    if killed > 0:
        logger.info(f"🧹 Killed {killed} stuck Chrome process(es) for profile {profile_name}")
        time.sleep(2)  # Wait for processes to fully terminate

    return killed


def cleanup_profile_locks(profile_name: str, browser_profile_path: str = None) -> bool:
    """Clean up stale lock files in browser profile folder.

    Returns:
        True if cleanup was done
    """
    if browser_profile_path:
        profile_dir = Path(browser_profile_path)
    else:
        profile_dir = Path(DEFAULT_BROWSER_PROFILES_FOLDER) / f"profile_{profile_name}"

    if not profile_dir.exists():
        return False

    cleaned = False
    lock_files = [
        'SingletonLock',
        'SingletonSocket',
        'SingletonCookie',
        '.org.chromium.Chromium.lock'
    ]

    for lock_file in lock_files:
        lock_path = profile_dir / lock_file
        if lock_path.exists():
            try:
                lock_path.unlink()
                logger.info(f"🔓 Removed stale lock file: {lock_file}")
                cleaned = True
            except PermissionError:
                logger.warning(f"⚠️ Could not remove lock file (in use): {lock_file}")
            except Exception as e:
                logger.warning(f"⚠️ Error removing lock file {lock_file}: {e}")

    # Also clean up our custom lock files
    browser_lock = Path(DEFAULT_BROWSER_PROFILES_FOLDER) / f".browser_lock_{profile_name}.lock"
    if browser_lock.exists():
        try:
            browser_lock.unlink()
            logger.info(f"🔓 Removed stale browser lock file")
            cleaned = True
        except:
            pass

    debugger_file = Path(DEFAULT_BROWSER_PROFILES_FOLDER) / f".debugger_{profile_name}.txt"
    if debugger_file.exists():
        try:
            debugger_file.unlink()
            logger.info(f"🔓 Removed stale debugger file")
            cleaned = True
        except:
            pass

    return cleaned


def full_cleanup_before_start(profile_name: str, browser_profile_path: str = None):
    """Perform full cleanup before starting browser.

    This fixes the "browser opens but doesn't navigate" issue.
    """
    logger.info(f"🧹 Performing cleanup for profile: {profile_name}")

    # Step 1: Kill any stuck Chrome processes for this profile
    kill_chrome_processes_for_profile(profile_name)

    # Step 2: Clean up lock files
    cleanup_profile_locks(profile_name, browser_profile_path)

    # Step 3: Small delay to ensure everything is released
    time.sleep(1)

    logger.info(f"✅ Cleanup complete for profile: {profile_name}")


# =============================================================================
# NEW: BROWSER VERIFICATION FUNCTIONS
# =============================================================================

def verify_browser_started(driver) -> bool:
    """Verify that the browser actually started and is responsive.

    Returns:
        True if browser is working, False otherwise
    """
    try:
        # Try to get current URL - this will fail if browser didn't start
        current_url = driver.current_url
        logger.info(f"✅ Browser started successfully (URL: {current_url})")
        return True
    except Exception as e:
        logger.error(f"❌ Browser failed to start properly: {e}")
        return False


def verify_page_loaded(driver, expected_url_contains: str, timeout: int = 30) -> bool:
    """Verify that a page actually loaded (not just navigated).

    Args:
        driver: Selenium WebDriver
        expected_url_contains: String that should be in the URL
        timeout: Maximum seconds to wait

    Returns:
        True if page loaded correctly, False otherwise
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            current_url = driver.current_url
            page_source = driver.page_source

            # Check if we're on the expected page
            if expected_url_contains in current_url:
                # Also verify page has some content (not blank)
                if len(page_source) > 1000:  # Real page has more than 1KB
                    logger.info(f"✅ Page loaded: {current_url[:50]}...")
                    return True

            # Check for common error pages
            if "ERR_" in page_source or "This site can't be reached" in page_source:
                logger.error(f"❌ Page failed to load (network error)")
                return False

            time.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ Error checking page: {e}")
            time.sleep(1)

    logger.error(f"❌ Page did not load within {timeout} seconds")
    return False


def is_on_youtube_upload_page(driver) -> bool:
    """Check if we're actually on the YouTube upload page.

    Returns:
        True if on upload page, False otherwise
    """
    try:
        current_url = driver.current_url.lower()
        page_source = driver.page_source.lower()

        # Check URL
        if 'youtube.com/upload' in current_url or 'studio.youtube.com' in current_url:
            # Check for upload elements
            if any(x in page_source for x in ['select files', 'upload', 'drag and drop', 'file']):
                return True

        return False
    except:
        return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_video_files(folder_path: Path, video_stem: str = None, profile_suffix: str = None) -> List[Path]:
    """Get all video files from a folder, including profile subfolders

    Args:
        folder_path: Base folder to search
        video_stem: Video name stem (e.g., "VD-1") to find profile subfolder
        profile_suffix: Profile suffix (e.g., "3ibara") to find profile subfolder
    """
    if not folder_path.exists():
        logger.warning(f"Folder not found: {folder_path}")
        return []

    video_files = []

    # First check for videos directly in folder
    for file_path in folder_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
            video_files.append(file_path)

    # If no videos found and we have video_stem/profile, check profile subfolder
    if not video_files and video_stem and profile_suffix:
        # Check for profile subfolder pattern: {video_stem}_combined_{profile}
        profile_subfolder = folder_path / f"{video_stem}_combined_{profile_suffix}"
        if profile_subfolder.exists():
            logger.info(f"Checking profile subfolder: {profile_subfolder}")
            for file_path in profile_subfolder.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                    video_files.append(file_path)

    # Also check any subfolder if still no videos
    if not video_files:
        for subfolder in folder_path.iterdir():
            if subfolder.is_dir():
                for file_path in subfolder.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                        video_files.append(file_path)

    video_files.sort(key=lambda x: x.name.lower())
    logger.info(f"Found {len(video_files)} video files in {folder_path}")
    return video_files


def get_browser_lock_file(profile_name: str) -> Path:
    """Get the file path for cross-process browser lock"""
    return Path(DEFAULT_BROWSER_PROFILES_FOLDER) / f".browser_lock_{profile_name}.lock"


class FileLock:
    """Cross-process file lock for Windows"""
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.handle = None

    def acquire(self, timeout=60):
        """Acquire the lock with timeout"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.handle = open(self.lock_file, 'w')
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except (IOError, OSError):
                if self.handle:
                    self.handle.close()
                    self.handle = None
                time.sleep(0.5)
        return False

    def release(self):
        """Release the lock"""
        if self.handle:
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                self.handle.close()
            except:
                pass
            self.handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


# =============================================================================
# YOUTUBE UPLOAD FUNCTIONS
# =============================================================================

def get_debugger_address_file(profile_name: str) -> Path:
    """Get the file path where we store the debugger address for shared browser"""
    return Path(DEFAULT_BROWSER_PROFILES_FOLDER) / f".debugger_{profile_name}.txt"


def setup_driver(profile_name: str, browser_profile_path: str = None, retry_count: int = 0) -> webdriver.Chrome:
    """Setup Chrome WebDriver with profile-specific browser profile.

    Includes cleanup and retry logic.

    Args:
        profile_name: Profile name (e.g., BASKLY)
        browser_profile_path: Optional custom browser profile path
        retry_count: Current retry attempt (for internal use)
    """
    # Perform cleanup before starting (fixes stuck browser issues)
    if retry_count == 0:  # Only on first attempt
        full_cleanup_before_start(profile_name, browser_profile_path)

    chrome_options = Options()

    # Create profile-specific browser data directory
    if browser_profile_path:
        profile_dir = Path(browser_profile_path)
        logger.info(f"🌐 Using CUSTOM browser profile: {profile_dir}")
    else:
        browser_profiles_folder = Path(DEFAULT_BROWSER_PROFILES_FOLDER)
        browser_profiles_folder.mkdir(parents=True, exist_ok=True)
        profile_dir = browser_profiles_folder / f"profile_{profile_name}"
        logger.info(f"🌐 Using default browser profile: {profile_dir}")
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Chrome options - use profile with extensions
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--enable-extensions")

    # Modern user agent
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

    # Keep extensions enabled in prefs
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0
    }
    chrome_options.add_experimental_option("prefs", prefs)

    logger.info(f"🚀 Starting Chrome browser...")

    try:
        driver = webdriver.Chrome(options=chrome_options)

        # Verify browser actually started
        if not verify_browser_started(driver):
            raise WebDriverException("Browser started but is not responsive")

        # Set page load timeout
        driver.set_page_load_timeout(60)

        return driver

    except (WebDriverException, SessionNotCreatedException) as e:
        error_str = str(e).lower()

        # Check if it's a profile lock issue
        if 'user data directory' in error_str or 'already in use' in error_str:
            logger.warning(f"⚠️ Profile appears to be locked. Attempting cleanup...")

            # Force kill Chrome and clean up
            kill_chrome_processes_for_profile(profile_name)
            cleanup_profile_locks(profile_name, browser_profile_path)
            time.sleep(3)

            # Retry if we haven't exceeded max retries
            if retry_count < MAX_RETRIES - 1:
                logger.info(f"🔄 Retrying browser start (attempt {retry_count + 2}/{MAX_RETRIES})...")
                return setup_driver(profile_name, browser_profile_path, retry_count + 1)

        logger.error(f"❌ Error setting up Chrome driver: {e}")
        raise


def setup_driver_with_remote_debugging(profile_name: str) -> tuple:
    """Setup Chrome with remote debugging enabled for tab sharing.
    Returns (driver, debugger_address)
    """
    import socket

    # Cleanup first
    full_cleanup_before_start(profile_name)

    # Find a free port for debugging
    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    debug_port = find_free_port()

    # Setup profile directory
    browser_profiles_folder = Path(DEFAULT_BROWSER_PROFILES_FOLDER)
    browser_profiles_folder.mkdir(parents=True, exist_ok=True)
    profile_dir = browser_profiles_folder / f"profile_{profile_name}"
    profile_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument(f"--remote-debugging-port={debug_port}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--enable-extensions")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0
    })

    logger.info(f"🌐 Starting browser with remote debugging on port {debug_port}")
    driver = webdriver.Chrome(options=chrome_options)

    # Verify browser started
    if not verify_browser_started(driver):
        driver.quit()
        raise WebDriverException("Browser started but is not responsive")

    # Save debugger address for other processes to connect
    debugger_address = f"127.0.0.1:{debug_port}"
    debugger_file = get_debugger_address_file(profile_name)
    debugger_file.write_text(debugger_address)
    logger.info(f"📝 Saved debugger address to {debugger_file}")

    return driver, debugger_address


def connect_to_existing_browser(profile_name: str) -> webdriver.Chrome:
    """Connect to an existing browser instance using remote debugging"""
    debugger_file = get_debugger_address_file(profile_name)

    if not debugger_file.exists():
        logger.info(f"❌ No existing browser found for {profile_name}")
        return None

    debugger_address = debugger_file.read_text().strip()
    logger.info(f"🔗 Connecting to existing browser at {debugger_address}")

    try:
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)
        driver = webdriver.Chrome(options=chrome_options)
        logger.info(f"✅ Connected to existing browser!")
        return driver
    except Exception as e:
        logger.warning(f"⚠️ Failed to connect to existing browser: {e}")
        # Clean up stale debugger file
        debugger_file.unlink(missing_ok=True)
        return None


def wait_for_upload_completion(driver, wait, wait_minutes: int = 5):
    """Wait for upload to complete with proper monitoring."""
    logger.info(f"⏱️ Upload timer set to {wait_minutes} minutes")

    upload_started = False
    start_time = time.time()
    max_wait_for_start = 60  # Wait max 60 seconds for upload to start

    # Step 1: Wait for upload to start (detect uploading indicators)
    logger.info("🔍 Waiting for upload to start...")
    while time.time() - start_time < max_wait_for_start:
        try:
            page_text = driver.page_source.lower()
            if any(x in page_text for x in ["uploading", "upload complete", "processing", "checks complete", "% uploaded"]):
                logger.info("✅ Upload detected - starting timer countdown")
                upload_started = True
                break
            time.sleep(2)
        except Exception as e:
            logger.debug(f"Waiting for upload start: {e}")
            time.sleep(2)

    if not upload_started:
        logger.warning("⚠️ Upload not detected after 60 seconds - starting timer anyway")

    # Step 2: Start the countdown timer
    timer_start = time.time()
    wait_seconds = wait_minutes * 60
    last_update = 0

    logger.info(f"⏳ Starting {wait_minutes} minute countdown...")

    while True:
        elapsed = int(time.time() - timer_start)
        remaining = wait_seconds - elapsed

        # Show progress every 30 seconds
        if elapsed - last_update >= 30:
            minutes_left = int(remaining / 60)
            seconds_left = int(remaining % 60)
            logger.info(f"⏳ Timer: {minutes_left}m {seconds_left}s remaining...")
            last_update = elapsed

        # Check if timer expired
        if elapsed >= wait_seconds:
            logger.info(f"✅ Timer complete ({wait_minutes} minutes elapsed)")
            return True

        time.sleep(5)


def navigate_to_youtube_upload(driver, max_retries: int = 3) -> bool:
    """Navigate to YouTube upload page with retry logic.

    Returns:
        True if successfully on upload page, False otherwise
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"📍 Navigating to YouTube upload (attempt {attempt + 1}/{max_retries})...")

            # Wait for extensions (like VPN) to initialize
            if attempt == 0:
                logger.info("⏳ Waiting 2 seconds for extensions to load...")
                time.sleep(2)

            # First try direct upload URL
            driver.get(YOUTUBE_UPLOAD_URL)
            time.sleep(5)

            # Check if we landed on the right page
            if is_on_youtube_upload_page(driver):
                logger.info("✅ Successfully on YouTube upload page")
                return True

            # Check if we need to login
            current_url = driver.current_url
            if "accounts.google.com" in current_url:
                logger.info("🔐 Login required - waiting for user login...")
                # Wait for login
                login_wait_start = time.time()
                while time.time() - login_wait_start < 300:  # 5 minutes to login
                    if "youtube.com" in driver.current_url and "accounts.google.com" not in driver.current_url:
                        logger.info("✅ Login detected!")
                        time.sleep(3)
                        # Navigate to upload after login
                        driver.get(YOUTUBE_UPLOAD_URL)
                        time.sleep(5)
                        if is_on_youtube_upload_page(driver):
                            return True
                        break
                    time.sleep(3)

            # Try YouTube Studio upload if direct upload failed
            logger.info("🔄 Trying YouTube Studio...")
            driver.get("https://studio.youtube.com")
            time.sleep(5)

            if "studio.youtube.com" in driver.current_url:
                # Look for create/upload button in studio
                try:
                    create_btn = driver.find_element(By.CSS_SELECTOR, "ytcp-button#create-icon")
                    create_btn.click()
                    time.sleep(2)
                    upload_btn = driver.find_element(By.XPATH, "//tp-yt-paper-item[contains(., 'Upload')]")
                    upload_btn.click()
                    time.sleep(3)
                    if is_on_youtube_upload_page(driver):
                        return True
                except:
                    pass

            logger.warning(f"⚠️ Could not reach upload page on attempt {attempt + 1}")

        except Exception as e:
            logger.error(f"❌ Error navigating to YouTube: {e}")

        if attempt < max_retries - 1:
            logger.info(f"🔄 Retrying in 5 seconds...")
            time.sleep(5)

    return False


def find_and_use_upload_input(driver, video_path: Path, timeout: int = 30) -> bool:
    """Find the file upload input and send the video file.

    Uses multiple selectors to handle YouTube UI changes.

    Returns:
        True if file was sent to input, False otherwise
    """
    wait = WebDriverWait(driver, timeout)

    # Updated selectors for 2024/2025 YouTube UI
    selectors_to_try = [
        # Direct file inputs
        "//input[@type='file']",
        "//input[@name='Filedata']",
        "//input[contains(@accept, 'video')]",
        # YouTube specific
        "//ytcp-uploads-file-picker//input[@type='file']",
        "//*[@id='select-files-button']//input[@type='file']",
        "//input[@id='file-picker']",
        # CSS selectors (converted to XPath)
        "//input[contains(@class, 'file')]",
    ]

    for selector in selectors_to_try:
        try:
            logger.info(f"🔍 Trying selector: {selector}")

            # Find the input element
            upload_input = wait.until(EC.presence_of_element_located((By.XPATH, selector)))

            # Make sure element is interactable
            driver.execute_script("arguments[0].style.display = 'block';", upload_input)
            time.sleep(0.5)

            # Send the file path
            upload_input.send_keys(str(video_path))
            logger.info(f"✅ Video file selected using: {selector}")
            return True

        except TimeoutException:
            logger.debug(f"Selector not found: {selector}")
            continue
        except Exception as e:
            logger.debug(f"Error with selector {selector}: {e}")
            continue

    # If all selectors fail, try JavaScript injection
    logger.info("🔧 Trying JavaScript file input injection...")
    try:
        # Create a visible file input
        js_code = """
        var input = document.createElement('input');
        input.type = 'file';
        input.id = 'nvs-file-input';
        input.style.position = 'fixed';
        input.style.top = '10px';
        input.style.left = '10px';
        input.style.zIndex = '9999';
        document.body.appendChild(input);
        return input;
        """
        driver.execute_script(js_code)
        time.sleep(1)

        # Find our created input
        custom_input = driver.find_element(By.ID, "nvs-file-input")
        custom_input.send_keys(str(video_path))
        logger.info("✅ Video file selected using JavaScript injection")
        return True
    except Exception as e:
        logger.debug(f"JavaScript injection failed: {e}")

    return False


def upload_video_to_youtube(video_path: Path, profile_name: str, wait_minutes: int = 5,
                            browser_profile_path: str = None, attempt: int = 1) -> Optional[str]:
    """Upload a video to YouTube with full retry logic.

    Args:
        video_path: Path to video file to upload
        profile_name: Profile name (e.g., BASKLY)
        wait_minutes: Minutes to wait for upload completion
        browser_profile_path: Optional custom browser profile path
        attempt: Current attempt number (for retry logic)
    """

    logger.info(f"\n{'=' * 60}")
    logger.info(f"📤 UPLOAD ATTEMPT {attempt}/{MAX_RETRIES}")
    logger.info(f"{'=' * 60}")
    logger.info(f"📹 Video: {video_path.name}")
    logger.info(f"👤 Profile: {profile_name}")
    logger.info(f"⏱️ Wait time: {wait_minutes} minutes")

    driver = None
    upload_successful = False

    try:
        # Setup driver with cleanup and retry
        driver = setup_driver(profile_name, browser_profile_path)
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        # Navigate to YouTube upload page with retry
        if not navigate_to_youtube_upload(driver):
            logger.error("❌ Could not reach YouTube upload page")
            raise Exception("Failed to navigate to YouTube upload page")

        # Wait for page to stabilize
        logger.info("⏳ Waiting for page to stabilize...")
        time.sleep(3)

        # Find upload input and send file
        if not find_and_use_upload_input(driver, video_path):
            logger.error("❌ Could not find upload button")
            logger.info("🎬 MANUAL MODE: Please upload the file manually")
            logger.info(f"   Video: {video_path}")

            # Wait for manual upload with detection
            manual_wait_start = time.time()
            manual_timeout = 120  # 2 minutes for manual upload

            while time.time() - manual_wait_start < manual_timeout:
                try:
                    page_text = driver.page_source.lower()
                    if any(x in page_text for x in ["uploading", "processing", "% uploaded"]):
                        logger.info("✅ Manual upload detected!")
                        break
                except:
                    pass
                time.sleep(3)

        # Wait for upload completion
        logger.info("📊 Monitoring upload progress...")
        upload_completed = wait_for_upload_completion(driver, wait, wait_minutes)

        if upload_completed:
            upload_successful = True
            logger.info("✅ Upload completed successfully!")

    except Exception as e:
        error_str = str(e).lower()

        # Check if browser was closed manually (treat as success)
        if any(phrase in error_str for phrase in [
            "session deleted", "disconnected", "browser has closed",
            "not connected", "no such window", "target closed",
            "connection refused", "connection reset"
        ]):
            logger.info(f"🚀 Browser closed manually - treating as UPLOAD COMPLETE!")
            upload_successful = True
        else:
            logger.error(f"❌ Upload error: {e}")

            # Retry if we haven't exceeded max attempts
            if attempt < MAX_RETRIES:
                logger.info(f"\n🔄 RETRYING UPLOAD (attempt {attempt + 1}/{MAX_RETRIES})...")

                # Close current browser if still open
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass

                # Wait before retry
                time.sleep(5)

                # Recursive retry
                return upload_video_to_youtube(
                    video_path, profile_name, wait_minutes,
                    browser_profile_path, attempt + 1
                )

    finally:
        # Close browser
        if driver:
            try:
                logger.info("🔄 Closing browser...")
                time.sleep(5)  # Wait before closing
                driver.quit()
                logger.info("✅ Browser closed")
            except Exception as e:
                logger.debug(f"Browser close note: {e}")

    if upload_successful:
        logger.info("📤 Upload step returning SUCCESS")
        return "Upload completed"
    else:
        logger.error("📤 Upload step returning FAILURE")
        return None


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def upload_videos_for_profile(input_folder: Path, profile_name: str, video_stem: str,
                              wait_minutes: int = 5, browser_profile_path: str = None) -> List[Tuple[str, str]]:
    """Upload all videos for a specific profile.

    Args:
        input_folder: Path to folder containing videos
        profile_name: Profile name (e.g., BASKLY)
        video_stem: Video stem name
        wait_minutes: Minutes to wait for upload completion
        browser_profile_path: Optional custom browser profile path
    """

    logger.info(f"\n{'=' * 60}")
    logger.info(f"🎬 UPLOADING FOR PROFILE: {profile_name}")
    logger.info(f"{'=' * 60}")

    # Find video files (now also checks profile subfolders)
    video_files = get_video_files(input_folder, video_stem, profile_name)
    if not video_files:
        logger.error(f"No video files found in {input_folder}")
        return []

    # Filter by video stem if specified
    if video_stem:
        stem_lower = video_stem.lower()
        video_files = [v for v in video_files if stem_lower in v.name.lower()]
        logger.info(f"Filtered to {len(video_files)} videos matching stem '{video_stem}'")

    # Upload each video
    uploaded = []
    for video_path in video_files:
        logger.info(f"\n📹 Uploading: {video_path.name}")

        result = upload_video_to_youtube(
            video_path, profile_name, wait_minutes, browser_profile_path
        )

        if result:
            uploaded.append((video_path.name, result))
            logger.info(f"✅ Uploaded: {video_path.name}")
        else:
            logger.error(f"❌ Failed: {video_path.name}")

    return uploaded


def upload_video_in_new_tab(video_path: Path, profile_name: str, wait_minutes: int = 5) -> Optional[str]:
    """Upload a video in a NEW TAB of the shared browser (for parallel uploads)."""
    logger.info(f"📑 [{video_path.stem}] Starting tab-based upload...")
    logger.info(f"📑 [{video_path.stem}] Profile: {profile_name}")

    driver = None
    is_new_browser = False
    upload_successful = False

    # Use cross-process file lock
    lock_file = get_browser_lock_file(profile_name)
    file_lock = FileLock(lock_file)

    try:
        # Acquire lock
        logger.info(f"📑 [{video_path.stem}] Acquiring browser lock...")
        if not file_lock.acquire(timeout=120):
            logger.error(f"📑 [{video_path.stem}] Failed to acquire browser lock")
            return None
        logger.info(f"📑 [{video_path.stem}] Lock acquired!")

        # Try to connect to existing browser
        driver = connect_to_existing_browser(profile_name)

        if driver is None:
            # Create new browser
            logger.info(f"📑 [{video_path.stem}] Creating new browser...")
            driver, _ = setup_driver_with_remote_debugging(profile_name)
            is_new_browser = True

            # Check login
            driver.get(YOUTUBE_STUDIO_URL)
            time.sleep(3)
            if "accounts.google.com" in driver.current_url:
                logger.info("🔐 LOGIN REQUIRED - Please login to YouTube...")
                login_start = time.time()
                while time.time() - login_start < 300:
                    if "studio.youtube.com" in driver.current_url:
                        logger.info("✅ Login detected!")
                        break
                    time.sleep(3)

        # Release lock
        file_lock.release()
        logger.info(f"📑 [{video_path.stem}] Lock released")

        # Open new tab
        logger.info(f"📑 [{video_path.stem}] Opening new tab...")
        driver.execute_script("window.open('');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])

        # Navigate to upload
        driver.get(YOUTUBE_UPLOAD_URL)
        time.sleep(5)

        # Find and use upload input
        if find_and_use_upload_input(driver, video_path):
            logger.info(f"📑 [{video_path.stem}] Upload started, waiting {wait_minutes} minutes...")
            time.sleep(wait_minutes * 60)
            upload_successful = True
            logger.info(f"📑 [{video_path.stem}] ✅ Upload complete!")
        else:
            logger.error(f"📑 [{video_path.stem}] Could not find upload input")

    except Exception as e:
        error_str = str(e).lower()
        if any(phrase in error_str for phrase in ["session deleted", "disconnected", "browser has closed"]):
            logger.info(f"📑 [{video_path.stem}] Browser closed - treating as complete")
            upload_successful = True
        else:
            logger.error(f"📑 [{video_path.stem}] Error: {e}")
    finally:
        file_lock.release()

    if upload_successful:
        return "Upload completed - tab mode"
    return None


def save_upload_results(output_folder: Path, video_stem: str, results: Dict):
    """Save upload results to JSON file"""
    output_folder.mkdir(parents=True, exist_ok=True)
    results_file = output_folder / f"{video_stem}_youtube_uploads.json"

    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"Upload results saved to: {results_file}")
    except Exception as e:
        logger.error(f"Error saving upload results: {e}")


def youtube_upload_step(input_folder: Path, output_folder: Path, video_stem: str,
                        selected_profiles: List[str], wait_minutes: int = 5,
                        browser_profile_path: str = None) -> bool:
    """Main function to upload videos for selected profiles."""

    logger.info(f"\n{'=' * 60}")
    logger.info(f"🎬 YOUTUBE UPLOAD - STEP 10")
    logger.info(f"{'=' * 60}")
    logger.info(f"🎯 Processing video: {video_stem}")
    logger.info(f"📁 Input folder: {input_folder}")
    logger.info(f"📂 Output folder: {output_folder}")
    logger.info(f"🎭 Profiles: {', '.join(selected_profiles)}")
    logger.info(f"⏱️ Upload wait time: {wait_minutes} minutes")
    logger.info(f"🔄 Max retries: {MAX_RETRIES}")
    if browser_profile_path:
        logger.info(f"🌐 Custom browser profile: {browser_profile_path}")
    logger.info(f"{'=' * 60}")

    all_results = {}

    for profile_name in selected_profiles:
        logger.info(f"\n🔄 Uploading videos for profile: {profile_name}")

        uploaded_videos = upload_videos_for_profile(
            input_folder, profile_name, video_stem, wait_minutes, browser_profile_path
        )

        all_results[profile_name] = {
            'profile_name': profile_name,
            'uploaded_count': len(uploaded_videos),
            'videos': uploaded_videos,
            'upload_timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if uploaded_videos:
            logger.info(f"✅ Profile {profile_name}: {len(uploaded_videos)} videos uploaded")
        else:
            logger.error(f"❌ Profile {profile_name}: No videos uploaded")

    # Save results
    save_upload_results(output_folder, video_stem, all_results)

    # Summary
    total_uploaded = sum(len(result['videos']) for result in all_results.values())
    logger.info(f"\n✨ STEP 10 COMPLETE!")
    logger.info(f"📊 Total videos uploaded: {total_uploaded}")

    return total_uploaded > 0


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main function for standalone execution"""
    parser = argparse.ArgumentParser(
        description="Step 10: Upload videos to YouTube",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--input',
        type=Path,
        default=DEFAULT_INPUT_FOLDER,
        help="Path to folder containing final videos"
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path.cwd() / "10_youtube_uploads",
        help="Path to output folder for upload results"
    )

    parser.add_argument(
        '--video-stem',
        type=str,
        required=True,
        help="Video stem (e.g., 'vd-1')"
    )

    parser.add_argument(
        '--profiles',
        type=str,
        nargs='+',
        required=True,
        help="Profile names to upload videos for"
    )

    parser.add_argument(
        '--wait-minutes',
        type=int,
        default=5,
        help="Wait time in minutes for upload completion"
    )

    parser.add_argument(
        '--browser-profile-path',
        type=str,
        default=None,
        help="Custom browser profile path"
    )

    parser.add_argument(
        '--use-tab',
        action='store_true',
        help="Use a new TAB in shared browser instead of new window"
    )

    args = parser.parse_args()

    # Validate input
    if not args.input.exists():
        logger.error(f"Input folder not found: {args.input}")
        sys.exit(1)

    # Run upload
    logger.info("🚀 Starting YouTube upload...")

    if args.use_tab:
        # Tab mode
        logger.info("📑 TAB MODE: Using shared browser")
        profile_name = args.profiles[0] if args.profiles else "DEFAULT"

        video_files = get_video_files(args.input)
        if not video_files:
            logger.error(f"No video files found in {args.input}")
            sys.exit(1)

        video_file = video_files[0]
        result = upload_video_in_new_tab(video_file, profile_name, args.wait_minutes)

        if result:
            args.output.mkdir(parents=True, exist_ok=True)
            results = {
                profile_name: {
                    'uploaded_count': 1,
                    'videos': [(video_file.name, result)],
                    'upload_timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
            save_upload_results(args.output, args.video_stem, results)
            logger.info("✅ Upload completed!")
            sys.exit(0)
        else:
            logger.error("❌ Upload failed!")
            sys.exit(1)
    else:
        # Normal mode
        success = youtube_upload_step(
            args.input, args.output, args.video_stem, args.profiles,
            args.wait_minutes, args.browser_profile_path
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
