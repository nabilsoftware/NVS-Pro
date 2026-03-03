# Fix Windows console encoding for emoji/unicode
import sys
import io
if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import time
import logging
from playwright.sync_api import sync_playwright

# ===== PARAGRAPH SPLITTING SETTINGS =====
MAX_PARAGRAPH_LENGTH = 6500  # Maximum characters per paragraph before splitting
# Adjust this value based on your needs:
# - 5000: Shorter chunks for faster processing
# - 8000: Default, good balance
# - 12000: Longer chunks for fewer files
# - 999999: Effectively disable splitting

# ===== VOICEOVER SETTINGS =====
# Default VOICEOVER_URL - This gets overridden by orchestrator for each profile
VOICEOVER_URL = "https://fish.audio/app/text-to-speech/?modelId=e4a2d14e7f5c4b2d80a6c56538051612&version=speech-1.6"  # Generic URL, model ID set by orchestrator
#VOICEOVER_URL = "https://fish.audio/text-to-speech/?modelId=c48162cbf1aa4732a961eb5fad38674c&version=speech-1.6"
DEFAULT_OUTPUT_FOLDER = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NabilVideoStudioPro', 'voiceovers')
BROWSER_PROFILE_PATH = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NabilVideoStudioPro', 'browser_profile')


def copy_cookies_from_master(target_profile_path, master_profile_path=None):
    """Copy cookies/session from master profile to target profile for parallel processing.

    This allows multiple browser instances to share the same Fish Audio login.
    Called right before launching browser to ensure fresh cookies.
    """
    import shutil

    if master_profile_path is None:
        master_profile_path = BROWSER_PROFILE_PATH

    if not os.path.exists(master_profile_path):
        logger.warning(f"Master profile not found: {master_profile_path}")
        return False

    # Create target directory
    os.makedirs(target_profile_path, exist_ok=True)

    # Essential files for login/cookies
    essential_files = ['Cookies', 'Cookies-journal', 'Local State', 'Preferences']

    # Copy essential files
    for file_name in essential_files:
        src = os.path.join(master_profile_path, file_name)
        if os.path.exists(src):
            try:
                shutil.copy2(src, os.path.join(target_profile_path, file_name))
            except Exception as e:
                logger.debug(f"Could not copy {file_name}: {e}")

    # Copy Default directory (contains cookies and session)
    src_default = os.path.join(master_profile_path, 'Default')
    dst_default = os.path.join(target_profile_path, 'Default')
    if os.path.exists(src_default):
        try:
            if os.path.exists(dst_default):
                shutil.rmtree(dst_default, ignore_errors=True)
            shutil.copytree(src_default, dst_default,
                           ignore=shutil.ignore_patterns('Cache', 'Code Cache', 'GPUCache',
                                                         'Service Worker', 'CacheStorage'))
        except Exception as e:
            logger.debug(f"Could not copy Default dir: {e}")

    logger.info(f"📋 Copied cookies from master profile to: {target_profile_path}")
    return True


def cleanup_browser_locks():
    """Remove browser lock files from crashed sessions (keeps cookies intact)"""
    cleanup_browser_locks_for_path(BROWSER_PROFILE_PATH)


def cleanup_browser_locks_for_path(profile_path):
    """Remove browser lock files from a specific profile path"""
    lock_files = [
        'SingletonLock',
        'SingletonCookie',
        'SingletonSocket',
        'lockfile'
    ]
    for lock_file in lock_files:
        lock_path = os.path.join(profile_path, lock_file)
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass  # Ignore errors, file might be in use


def wait_for_browser_profile_available(profile_path, max_wait=300, check_interval=5):
    """
    Wait until the browser profile is available (not locked by another browser).
    This ensures cookies are shared properly between browser sessions.

    Args:
        profile_path: Path to the browser profile
        max_wait: Maximum seconds to wait (default 5 minutes)
        check_interval: Seconds between checks

    Returns:
        True if profile is available, False if timeout
    """
    lock_file = os.path.join(profile_path, 'SingletonLock')
    start_time = time.time()

    while os.path.exists(lock_file):
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            logger.warning(f"⏰ Timeout waiting for browser profile to be available")
            return False

        # Try to remove the lock (works if browser crashed)
        try:
            os.remove(lock_file)
            logger.info(f"🔓 Removed stale browser lock file")
            return True
        except PermissionError:
            # Lock is held by active browser - wait
            remaining = max_wait - elapsed
            logger.info(f"⏳ Browser profile in use, waiting... ({remaining:.0f}s remaining)")
            time.sleep(check_interval)
        except Exception:
            pass

    return True


# Global mutex for voiceover access - ensures only ONE folder runs voiceover at a time
VOICEOVER_MUTEX_FILE = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NabilVideoStudioPro', 'voiceover_mutex.lock')
_voiceover_lock_handle = None


def acquire_voiceover_lock(profile_name, max_wait=600, check_interval=3):
    """
    Acquire exclusive lock for voiceover processing.
    This prevents multiple folders from trying to launch browsers simultaneously.

    Uses file locking to ensure atomic access across processes.

    Args:
        profile_name: Name for logging
        max_wait: Maximum seconds to wait for lock (default 10 minutes)
        check_interval: Seconds between lock attempts

    Returns:
        Lock file handle if acquired, None if timeout
    """
    global _voiceover_lock_handle
    import msvcrt  # Windows file locking

    # Ensure directory exists
    os.makedirs(os.path.dirname(VOICEOVER_MUTEX_FILE), exist_ok=True)

    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            logger.warning(f"⏰ {profile_name}: Timeout waiting for voiceover lock after {max_wait}s")
            return None

        try:
            # Open/create the lock file
            lock_handle = open(VOICEOVER_MUTEX_FILE, 'w')

            # Try to acquire exclusive lock (non-blocking)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)

            # Write who has the lock for debugging
            lock_handle.write(f"{profile_name} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            lock_handle.flush()

            _voiceover_lock_handle = lock_handle
            logger.info(f"🔒 {profile_name}: Acquired voiceover lock!")
            return lock_handle

        except (IOError, OSError) as e:
            # Lock is held by another process
            try:
                lock_handle.close()
            except:
                pass

            remaining = max_wait - elapsed
            logger.info(f"⏳ {profile_name}: Voiceover in progress by another folder, waiting... ({remaining:.0f}s remaining)")
            time.sleep(check_interval)
        except Exception as e:
            logger.warning(f"⚠️ {profile_name}: Lock error: {e}")
            time.sleep(check_interval)


def release_voiceover_lock(profile_name):
    """
    Release the voiceover lock so other folders can proceed.

    Args:
        profile_name: Name for logging
    """
    global _voiceover_lock_handle
    import msvcrt

    if _voiceover_lock_handle:
        try:
            # Unlock the file
            msvcrt.locking(_voiceover_lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            _voiceover_lock_handle.close()
            _voiceover_lock_handle = None
            logger.info(f"🔓 {profile_name}: Released voiceover lock")
        except Exception as e:
            logger.warning(f"⚠️ {profile_name}: Error releasing lock: {e}")
            try:
                _voiceover_lock_handle.close()
            except:
                pass
            _voiceover_lock_handle = None


def create_profile_with_cookies(profile_name):
    """
    Create a new browser profile folder and copy cookies from the main profile.
    This allows multiple browsers to run in parallel with the same login session.

    Args:
        profile_name: Unique name for this profile (e.g., "profile_1", "video_abc")

    Returns:
        Path to the new profile folder with cookies copied
    """
    import shutil

    # Create unique profile path
    profiles_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NabilVideoStudioPro', 'browser_profiles')
    new_profile_path = os.path.join(profiles_dir, profile_name)

    # Create directory
    os.makedirs(new_profile_path, exist_ok=True)

    # Files that contain login cookies and session data
    cookie_files = [
        'Cookies',
        'Cookies-journal',
        'Login Data',
        'Login Data-journal',
        'Web Data',
        'Web Data-journal',
        'Preferences',
        'Secure Preferences',
        'Local State',
    ]

    # Also copy the Default folder if it exists (Chrome stores cookies there)
    default_source = os.path.join(BROWSER_PROFILE_PATH, 'Default')
    default_dest = os.path.join(new_profile_path, 'Default')

    if os.path.exists(default_source):
        os.makedirs(default_dest, exist_ok=True)
        for cookie_file in cookie_files:
            src = os.path.join(default_source, cookie_file)
            dst = os.path.join(default_dest, cookie_file)
            try:
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                    logger.info(f"📋 Copied {cookie_file} to {profile_name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not copy {cookie_file}: {e}")

    # Also copy root level cookie files
    for cookie_file in cookie_files:
        src = os.path.join(BROWSER_PROFILE_PATH, cookie_file)
        dst = os.path.join(new_profile_path, cookie_file)
        try:
            if os.path.exists(src):
                shutil.copy2(src, dst)
        except Exception:
            pass

    # Copy Local State file (contains encryption keys for cookies)
    local_state_src = os.path.join(BROWSER_PROFILE_PATH, 'Local State')
    local_state_dst = os.path.join(new_profile_path, 'Local State')
    try:
        if os.path.exists(local_state_src):
            shutil.copy2(local_state_src, local_state_dst)
            logger.info(f"📋 Copied Local State to {profile_name}")
    except Exception as e:
        logger.warning(f"⚠️ Could not copy Local State: {e}")

    logger.info(f"✅ Created browser profile with cookies: {new_profile_path}")
    return new_profile_path


def cleanup_temp_profiles():
    """Clean up temporary browser profiles created for parallel processing"""
    import shutil

    profiles_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NabilVideoStudioPro', 'browser_profiles')

    if os.path.exists(profiles_dir):
        try:
            shutil.rmtree(profiles_dir)
            logger.info(f"🧹 Cleaned up temporary browser profiles")
        except Exception as e:
            logger.warning(f"⚠️ Could not clean up profiles: {e}")


# ===== SMART TIMING SETTINGS =====
BASE_WAIT_TIME = 10  # Minimum wait time in seconds
SECONDS_PER_100_CHARS = 4  # Additional seconds per 100 characters
MAX_WAIT_TIME = 300  # Maximum wait time (5 minutes)

# ===== TAB MANAGEMENT SETTINGS =====
TAB_TIMEOUT = 120  # Timeout for tab operations
PAGE_LOAD_TIMEOUT = 60000  # Page load timeout in milliseconds
TAB_REFRESH_INTERVAL = 300  # Refresh tabs every 5 minutes to prevent freezing

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('voiceover_automation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def calculate_wait_time(text_length):
    """Calculate expected wait time based on text length"""
    estimated_time = BASE_WAIT_TIME + (text_length // 100) * SECONDS_PER_100_CHARS
    estimated_time = min(estimated_time, MAX_WAIT_TIME)
    return estimated_time


class SmartTabProcessor:
    def __init__(self, page, tab_id, browser):
        self.page = page
        self.tab_id = tab_id
        self.browser = browser
        self.is_busy = False
        self.current_task_start = None
        self.current_text_length = 0
        self.last_activity = time.time()
        self.creation_time = time.time()
        self.error_count = 0
        self.max_errors = 3

    def is_tab_healthy(self):
        """Check if tab is still responsive"""
        try:
            # Try a simple operation to test responsiveness
            self.page.evaluate("document.title")
            return True
        except Exception as e:
            logger.warning(f"Tab {self.tab_id}: Health check failed: {e}")
            self.error_count += 1
            return self.error_count < self.max_errors

    def refresh_tab(self):
        """Refresh the tab if it becomes unresponsive"""
        try:
            logger.info(f"Tab {self.tab_id}: Refreshing due to unresponsiveness...")
            self.page.reload(timeout=PAGE_LOAD_TIMEOUT)
            time.sleep(5)  # Wait for page to fully load
            self.error_count = 0
            self.last_activity = time.time()
            self.is_busy = False
            self.current_task_start = None
            return True
        except Exception as e:
            logger.error(f"Tab {self.tab_id}: Failed to refresh: {e}")
            return False

    def recreate_tab(self):
        """Recreate the tab if refresh fails"""
        try:
            logger.info(f"Tab {self.tab_id}: Recreating tab...")
            self.page.close()
            self.page = self.browser.new_page()

            # Set longer timeouts for the new page
            self.page.set_default_timeout(TAB_TIMEOUT * 1000)
            self.page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)

            self.page.goto(VOICEOVER_URL, timeout=PAGE_LOAD_TIMEOUT)
            time.sleep(5)

            self.error_count = 0
            self.last_activity = time.time()
            self.creation_time = time.time()
            self.is_busy = False
            self.current_task_start = None

            logger.info(f"Tab {self.tab_id}: Successfully recreated")
            return True
        except Exception as e:
            logger.error(f"Tab {self.tab_id}: Failed to recreate: {e}")
            return False

    def find_elements(self):
        """Find text area and generate button with better error handling"""
        try:
            # Ensure tab is responsive first
            if not self.is_tab_healthy():
                if not self.refresh_tab():
                    return None, None

            # Wait for elements to be available
            self.page.wait_for_selector("[contenteditable='true'], textarea", timeout=10000)

            text_area = self.page.locator("[contenteditable='true']").first
            if not text_area.is_visible():
                text_area = self.page.locator("textarea").first

            # Wait for generate button using JavaScript (Playwright's wait_for_selector
            # picks wrong button when comma-separated selectors match multiple elements)
            self.page.wait_for_function("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.trim();
                        if ((text === 'Generate speech' || text === 'Generate' || text === 'Synthesize')
                            && !btn.getAttribute('aria-haspopup')
                            && btn.offsetParent !== null) {
                            return true;
                        }
                    }
                    return false;
                }
            """, timeout=10000)

            # Find the actual generate button by exact text match, skipping dropdown triggers
            generate_btn = None
            for text in ["Generate speech", "Generate", "Synthesize"]:
                btn = self.page.locator(f"button:has-text('{text}'):not([aria-haspopup])").last
                try:
                    if btn.is_visible():
                        generate_btn = btn
                        break
                except Exception:
                    continue
            if not generate_btn:
                generate_btn = self.page.locator("button:has-text('Generate')").last

            self.last_activity = time.time()
            return text_area, generate_btn

        except Exception as e:
            logger.error(f"Tab {self.tab_id}: Error finding elements: {e}")
            self.error_count += 1
            return None, None

    def is_ready_for_new_task(self):
        """Check if tab is ready for a new task"""
        if self.is_busy:
            return False

        try:
            # Check if tab needs to be refreshed due to inactivity
            if time.time() - self.last_activity > TAB_REFRESH_INTERVAL:
                logger.info(f"Tab {self.tab_id}: Refreshing due to inactivity...")
                if not self.refresh_tab():
                    return False

            # Check if tab is healthy
            if not self.is_tab_healthy():
                return False

            # Check if download button is visible (previous task done)
            download_btn = self.page.locator("button:has-text('Download')").first
            if download_btn.is_visible():
                return True

            # Check if generate button is available (fish.audio button = "Generate speech")
            for selector in ["button:has-text('Generate speech')", "button:has-text('Generate'):not([aria-haspopup])", "button:has-text('Synthesize')"]:
                try:
                    btn = self.page.locator(selector).last
                    if btn.is_visible() and btn.is_enabled():
                        self.last_activity = time.time()
                        return True
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.warning(f"Tab {self.tab_id}: Error checking readiness: {e}")
            self.error_count += 1
            return False

    def start_generation(self, paragraph_text, task_idx):
        """Start generation with smart timing awareness"""
        try:
            # Check tab health before starting
            if not self.is_tab_healthy():
                if not self.refresh_tab():
                    return False

            text_area, generate_btn = self.find_elements()
            if not text_area or not generate_btn:
                logger.error(f"Tab {self.tab_id}: Could not find required elements for task {task_idx}")
                return False

            # Store text length for smart waiting
            self.current_text_length = len(paragraph_text)

            logger.info(f"Tab {self.tab_id}: Starting task {task_idx} ({self.current_text_length} chars)")

            # Clear and set text with better error handling
            text_area.click()
            time.sleep(0.5)

            # Clear the text area using multiple methods
            try:
                # Method 1: JavaScript clear
                self.page.evaluate('''
                    const textArea = document.querySelector("[contenteditable='true']") || document.querySelector("textarea");
                    if (textArea) {
                        textArea.focus();
                        if (textArea.contentEditable === "true") {
                            textArea.innerHTML = "";
                        } else {
                            textArea.value = "";
                        }
                    }
                ''')

                time.sleep(0.5)

                # Method 2: Keyboard shortcuts as backup
                text_area.press("Control+a")
                time.sleep(0.2)
                text_area.press("Delete")
                time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Tab {self.tab_id}: Error clearing text area: {e}")

            # Set new text with better escaping
            try:
                # Use fill method as primary approach
                text_area.fill(paragraph_text)
                time.sleep(0.5)

                # Trigger input event
                text_area.dispatch_event("input")
                time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Tab {self.tab_id}: Fill method failed, trying JavaScript: {e}")

                # Fallback to JavaScript method
                escaped_text = paragraph_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace(
                    '\r', '')
                self.page.evaluate(f'''
                    const textArea = document.querySelector("[contenteditable='true']") || document.querySelector("textarea");
                    if (textArea) {{
                        if (textArea.contentEditable === "true") {{
                            textArea.innerText = "{escaped_text}";
                        }} else {{
                            textArea.value = "{escaped_text}";
                        }}
                        textArea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                ''')
                time.sleep(0.5)

            # Wait for the interface to update
            time.sleep(1)

            # Check if generate button is still enabled after setting text
            if not generate_btn.is_enabled():
                logger.error(f"Tab {self.tab_id}: Generate button disabled after setting text for task {task_idx}")
                return False

            # Click generate with retry logic
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    generate_btn.click()
                    self.is_busy = True
                    self.current_task_start = time.time()
                    self.last_activity = time.time()

                    logger.info(f"Tab {self.tab_id}: ✅ Generation started for task {task_idx}")
                    return True

                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Tab {self.tab_id}: Click attempt {retry_count} failed: {e}")
                    time.sleep(1)

            logger.error(f"Tab {self.tab_id}: Failed to click generate button after {max_retries} attempts")
            return False

        except Exception as e:
            logger.error(f"Tab {self.tab_id}: Error starting generation for task {task_idx}: {e}")
            self.error_count += 1
            return False

    def check_download_ready(self):
        """Check if download is ready without waiting (non-blocking)"""
        if not self.is_busy:
            return False

        try:
            # Check tab health
            if not self.is_tab_healthy():
                return False

            # Quick check if download button is ready
            download_btn = self.page.locator("button:has-text('Download')").first
            if download_btn.is_visible() and download_btn.is_enabled():
                self.last_activity = time.time()
                return True

            # Check if enough time has passed for this text length
            if self.current_task_start:
                elapsed = time.time() - self.current_task_start
                estimated_time = calculate_wait_time(self.current_text_length)

                # If we've waited long enough, check more thoroughly
                if elapsed >= estimated_time:
                    result = download_btn.is_visible()
                    if result:
                        self.last_activity = time.time()
                    return result

            return False

        except Exception as e:
            logger.warning(f"Tab {self.tab_id}: Error checking download status: {e}")
            self.error_count += 1
            return False

    def download_file(self, output_path, task_idx):
        """Download the file if ready"""
        try:
            download_btn = self.page.locator("button:has-text('Download')").first

            # Set up download expectation with longer timeout
            with self.page.expect_download(timeout=60000) as download_info:
                download_btn.click()

            download = download_info.value
            download.save_as(output_path)

            self.is_busy = False
            self.current_task_start = None
            self.last_activity = time.time()

            # Verify file
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                size_kb = os.path.getsize(output_path) // 1024
                logger.info(f"Tab {self.tab_id}: ✅ Downloaded task {task_idx} ({size_kb}KB)")
                return True
            else:
                logger.error(f"Tab {self.tab_id}: ❌ File verification failed for task {task_idx}")
                return False

        except Exception as e:
            logger.error(f"Tab {self.tab_id}: Download error for task {task_idx}: {e}")
            self.is_busy = False
            self.current_task_start = None
            self.error_count += 1
            return False


def split_long_paragraph(paragraph, max_length=MAX_PARAGRAPH_LENGTH):
    """Split long paragraph into smaller chunks at natural break points"""
    if len(paragraph) <= max_length:
        return [paragraph]
    
    splits = []
    remaining_text = paragraph
    
    while len(remaining_text) > max_length:
        # Find the best split point within max_length
        best_split = 0
        
        # Priority 1: Look for sentence endings (. ! ?) with space after
        for i in range(max_length - 1, max_length // 2, -1):
            if remaining_text[i] in '.!?' and i + 1 < len(remaining_text) and remaining_text[i + 1] == ' ':
                best_split = i + 1
                break
        
        # Priority 2: Look for dialogue endings (" followed by space)
        if best_split == 0:
            for i in range(max_length - 1, max_length // 2, -1):
                if remaining_text[i] == '"' and i + 1 < len(remaining_text) and remaining_text[i + 1] == ' ':
                    best_split = i + 1
                    break
        
        # Priority 3: Look for paragraph breaks (\n\n)
        if best_split == 0:
            for i in range(max_length - 2, max_length // 2, -1):
                if remaining_text[i:i+2] == '\n\n':
                    best_split = i + 2
                    break
        
        # Priority 4: Look for commas with space after (for lists)
        if best_split == 0:
            for i in range(max_length - 1, max_length // 2, -1):
                if remaining_text[i] == ',' and i + 1 < len(remaining_text) and remaining_text[i + 1] == ' ':
                    best_split = i + 1
                    break
        
        # Priority 5: Look for any space (word boundary)
        if best_split == 0:
            for i in range(max_length - 1, max_length // 2, -1):
                if remaining_text[i] == ' ':
                    best_split = i + 1
                    break
        
        # Fallback: Hard cut (should rarely happen)
        if best_split == 0:
            best_split = max_length
        
        # Extract the split part and add to results
        split_part = remaining_text[:best_split].strip()
        if split_part:
            splits.append(split_part)
        
        # Continue with remaining text
        remaining_text = remaining_text[best_split:].strip()
    
    # Add the final remaining part
    if remaining_text:
        splits.append(remaining_text)
    
    return splits


def load_text_file(file_path):
    """Load and parse text file with length analysis and smart splitting"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        raw_paragraphs = [p.strip() for p in content.split("\n\n\n") if p.strip()]

        # Smart paragraph splitting for long paragraphs
        paragraphs = []
        splits_info = []
        
        for i, paragraph in enumerate(raw_paragraphs, 1):
            if len(paragraph) > MAX_PARAGRAPH_LENGTH:
                split_parts = split_long_paragraph(paragraph)
                logger.info(f"📄 Paragraph {i}: {len(paragraph)} chars → Split into {len(split_parts)} parts")
                
                for j, part in enumerate(split_parts):
                    paragraphs.append(part)
                    splits_info.append(f"{i}{'abcdefghijklmnopqrstuvwxyz'[j]}")
            else:
                paragraphs.append(paragraph)
                splits_info.append(str(i))

        # Analyze text lengths
        total_chars = sum(len(p) for p in paragraphs)
        avg_length = total_chars // len(paragraphs) if paragraphs else 0
        max_length = max(len(p) for p in paragraphs) if paragraphs else 0
        min_length = min(len(p) for p in paragraphs) if paragraphs else 0
        long_paragraphs = sum(1 for p in raw_paragraphs if len(p) > MAX_PARAGRAPH_LENGTH)

        logger.info(f"📊 Text Analysis:")
        logger.info(f"  - Original paragraphs: {len(raw_paragraphs)}")
        logger.info(f"  - After smart splitting: {len(paragraphs)}")
        logger.info(f"  - Long paragraphs split: {long_paragraphs}")
        logger.info(f"  - Average length: {avg_length} chars")
        logger.info(f"  - Shortest: {min_length} chars")
        logger.info(f"  - Longest: {max_length} chars")
        logger.info(f"  - Total characters: {total_chars}")

        # Estimate total time
        total_estimated_time = sum(calculate_wait_time(len(p)) for p in paragraphs)
        logger.info(f"  - Estimated total generation time: {total_estimated_time / 60:.1f} minutes")

        # Store splits info for file naming
        return list(zip(paragraphs, splits_info))
    except Exception as e:
        logger.error(f"Error reading text file: {e}")
        return []


def calculate_optimal_tabs(paragraphs, min_tabs=2, max_tabs=25):
    """
    🎯 AUTO-TAB CALCULATOR: Dynamically determine optimal number of tabs based on script content
    
    Args:
        paragraphs: List of paragraph strings
        min_tabs: Minimum tabs to open (default: 2)
        max_tabs: Maximum tabs to open (default: 25)
    
    Returns:
        Optimal number of tabs
    """
    if not paragraphs:
        logger.warning("⚠️ No paragraphs found, using minimum tabs")
        return min_tabs
    
    paragraph_count = len(paragraphs)
    
    # SMART LOGIC: Base calculation on paragraph count
    if paragraph_count <= 3:
        # Very short scripts: Use minimal tabs
        optimal_tabs = max(paragraph_count, min_tabs)
    elif paragraph_count <= 10:
        # Short to medium scripts: Use paragraph count
        optimal_tabs = paragraph_count
    elif paragraph_count <= 20:
        # Medium scripts: Use 1:1 ratio for good PCs (maximum speed)
        optimal_tabs = paragraph_count
    else:
        # Long scripts: Cap at reasonable maximum for system performance
        optimal_tabs = min(max_tabs, max(15, paragraph_count // 2))
    
    # Ensure we stay within bounds
    optimal_tabs = max(min_tabs, min(optimal_tabs, max_tabs))
    
    # Log the smart decision
    logger.info(f"🧠 SMART TAB CALCULATION:")
    logger.info(f"   📄 Script has {paragraph_count} paragraphs")
    logger.info(f"   🎯 Optimal tabs: {optimal_tabs}")
    logger.info(f"   💡 Efficiency: {optimal_tabs/paragraph_count:.2f} tabs per paragraph" if paragraph_count > 0 else "")
    
    return optimal_tabs


def run_smart_parallel(text_file_path, output_folder, num_tabs=2):
    """Smart parallel processing with adaptive timing and better tab management"""

    paragraphs_data = load_text_file(text_file_path)
    if not paragraphs_data:
        return

    # Extract paragraphs for tab calculation
    paragraphs = [item[0] for item in paragraphs_data]

    # 🎯 AUTO-TAB FEATURE: Use smart calculation if num_tabs is "auto" or negative
    if num_tabs == "auto" or (isinstance(num_tabs, int) and num_tabs <= 0):
        num_tabs = calculate_optimal_tabs(paragraphs)
        logger.info(f"🤖 AUTO-TAB MODE: Calculated {num_tabs} optimal tabs")
    elif isinstance(num_tabs, int) and num_tabs > 0:
        logger.info(f"👤 MANUAL MODE: Using {num_tabs} tabs as specified")

    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(BROWSER_PROFILE_PATH, exist_ok=True)

    # Create task queue with smart naming
    pending_tasks = []
    for idx, (paragraph_text, split_id) in enumerate(paragraphs_data, 1):
        output_filename = f"paragraph_{split_id.zfill(3)}.mp3"
        output_path = os.path.join(output_folder, output_filename)

        if os.path.exists(output_path):
            logger.info(f"⏭️ Skipping existing: {output_filename}")
            continue

        pending_tasks.append({
            'idx': idx,
            'text': paragraph_text,
            'output_path': output_path
        })

    if not pending_tasks:
        logger.info("✅ All files already exist!")
        return

    # Wait for browser profile to be available (if another voiceover window is using it)
    # This ensures all windows share the same login cookies
    logger.info(f"🔍 Checking if browser profile is available...")
    if not wait_for_browser_profile_available(BROWSER_PROFILE_PATH):
        logger.error(f"❌ Browser profile locked, cannot proceed")
        return

    # Clean up any lock files from crashed sessions (keeps cookies intact)
    cleanup_browser_locks()

    with sync_playwright() as p:
        # Launch browser with better settings
        browser = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_PATH,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ],
            # Increase timeouts
            slow_mo=100  # Add slight delay between actions
        )

        try:
            # Initialize tabs with better error handling
            tabs = []
            # FAST TAB OPENING: Create all tabs first, then navigate them in parallel
            logger.info(f"🚀 Opening {num_tabs} tabs simultaneously...")
            
            # Step 1: Create all tabs quickly without navigation
            pages = []
            for i in range(num_tabs):
                try:
                    if i == 0 and browser.pages:
                        page = browser.pages[0]
                    else:
                        page = browser.new_page()
                    
                    # Set timeouts for the page
                    page.set_default_timeout(TAB_TIMEOUT * 1000)
                    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)
                    
                    pages.append((page, i + 1))
                    logger.info(f"📄 Created tab {i + 1}")
                    
                except Exception as e:
                    logger.error(f"Failed to create tab {i + 1}: {e}")
            
            # Step 2: Navigate all tabs in parallel (start all at once)
            logger.info(f"🌐 Navigating all {len(pages)} tabs to Fish Audio...")
            
            # Start navigation for all tabs simultaneously
            for page, tab_id in pages:
                try:
                    # Use async navigation without waiting
                    page.goto(VOICEOVER_URL, timeout=PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
                except Exception as e:
                    logger.error(f"Failed to navigate tab {tab_id}: {e}")
            
            # Step 3: Wait a short time for all pages to load, then create processors
            time.sleep(1)  # Faster wait for good PCs
            
            for page, tab_id in pages:
                try:
                    tab_processor = SmartTabProcessor(page, tab_id, browser)
                    tabs.append(tab_processor)
                    logger.info(f"✅ Tab {tab_id} ready")
                except Exception as e:
                    logger.error(f"Failed to initialize processor for tab {tab_id}: {e}")

            if not tabs:
                logger.error("No tabs could be initialized!")
                return

            # Wait a moment for tabs to fully initialize
            logger.info("⏳ Waiting 1 second for tabs to fully initialize...")
            time.sleep(1)
            
            logger.info("🚀 Starting fully automated parallel processing...")

            # PARALLEL processing - all tabs working together
            completed = 0
            failed = 0
            total_tasks = len(pending_tasks)
            start_time = time.time()

            # Track which tasks are assigned to which tabs
            task_assignments = {}  # {task_idx: tab}

            while pending_tasks or any(tab.is_busy for tab in tabs):

                # 1. BATCH ASSIGN NEW TASKS to ALL available tabs at once (OPTIMIZED)
                available_tabs = []
                for tab in tabs:
                    try:
                        if tab.is_ready_for_new_task():
                            available_tabs.append(tab)
                    except Exception as e:
                        logger.error(f"Error checking tab {tab.tab_id}: {e}")
                        if not tab.refresh_tab():
                            tab.recreate_tab()

                # Assign tasks to all available tabs simultaneously
                tasks_to_assign = [task for task in pending_tasks if task['idx'] not in task_assignments]
                for i, task in enumerate(tasks_to_assign):
                    if i < len(available_tabs):
                        tab = available_tabs[i]
                        try:
                            if tab.start_generation(task['text'], task['idx']):
                                task_assignments[task['idx']] = tab
                                logger.info(f"🚀 Batch assigned task {task['idx']} to Tab {tab.tab_id}")
                        except Exception as e:
                            logger.error(f"Error batch assigning task to Tab {tab.tab_id}: {e}")
                            if not tab.refresh_tab():
                                tab.recreate_tab()

                # 2. CHECK COMPLETED DOWNLOADS from all busy tabs
                for task in pending_tasks[:]:
                    if task['idx'] in task_assignments:
                        tab = task_assignments[task['idx']]

                        try:
                            # Check if download is ready for this tab
                            if tab.check_download_ready():
                                # Try to download
                                if tab.download_file(task['output_path'], task['idx']):
                                    completed += 1
                                    elapsed = time.time() - start_time
                                    remaining = total_tasks - completed
                                    avg_time = elapsed / completed if completed > 0 else 0
                                    eta = remaining * avg_time / len(tabs) if avg_time > 0 else 0

                                    logger.info(f"🎉 Progress: {completed}/{total_tasks} | ETA: {eta / 60:.1f}min")
                                else:
                                    logger.error(f"❌ Download failed for task {task['idx']}")
                                    failed += 1

                                # Remove completed task
                                del task_assignments[task['idx']]
                                pending_tasks.remove(task)

                        except Exception as e:
                            logger.error(f"Error processing task {task['idx']}: {e}")
                            # Remove failed task and try to recover tab
                            if task['idx'] in task_assignments:
                                del task_assignments[task['idx']]
                            pending_tasks.remove(task)
                            failed += 1

                            # Try to recover the tab
                            if not tab.refresh_tab():
                                tab.recreate_tab()

                # 3. CHECK FOR TIMEOUTS AND UNHEALTHY TABS
                current_time = time.time()
                for task_idx, tab in list(task_assignments.items()):
                    try:
                        # Check for timeout
                        if tab.current_task_start and current_time - tab.current_task_start > MAX_WAIT_TIME:
                            logger.warning(f"⏰ Task {task_idx} on Tab {tab.tab_id} timed out, resetting...")
                            tab.is_busy = False
                            tab.current_task_start = None
                            del task_assignments[task_idx]
                            failed += 1

                        # Check tab health periodically
                        elif not tab.is_tab_healthy():
                            logger.warning(f"🏥 Tab {tab.tab_id} unhealthy, attempting recovery...")
                            if not tab.refresh_tab():
                                if not tab.recreate_tab():
                                    logger.error(f"❌ Failed to recover Tab {tab.tab_id}")
                                    # Remove current task assignment
                                    if task_idx in task_assignments:
                                        del task_assignments[task_idx]
                                        failed += 1

                    except Exception as e:
                        logger.error(f"Error managing Tab {tab.tab_id}: {e}")

                # Optimized pause for faster coordination (reduced from 2s to 0.5s)
                time.sleep(0.2)  # Even faster polling for good PCs

            # Final summary
            total_time = time.time() - start_time
            success_rate = (completed / len(paragraphs_data)) * 100 if paragraphs_data else 0

            logger.info(f"\n{'🎉' * 20}")
            logger.info(f"🏁 SMART PARALLEL PROCESSING COMPLETED")
            logger.info(f"✅ Successful: {completed}/{len(paragraphs_data)}")
            logger.info(f"❌ Failed: {failed}")
            logger.info(f"📊 Success rate: {success_rate:.1f}%")
            logger.info(f"⏱️ Total time: {total_time / 60:.1f} minutes")
            if completed > 0:
                logger.info(f"⚡ Average: {total_time / completed:.1f} seconds per task")
            logger.info(f"{'🎉' * 20}")

        except Exception as e:
            logger.error(f"Processing error: {e}")
        finally:
            logger.info("🏁 Processing complete, closing browser...")
            browser.close()



def parse_arguments():
    """Parse command-line arguments"""
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate voiceovers using Fish Audio TTS",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("text_file", nargs="?", default=None,
                        help="Path to text/script file")
    parser.add_argument("--output-folder", "-o", default=None,
                        help="Output folder for voiceover files")
    parser.add_argument("--voice-url", default=None,
                        help="Fish Audio voice URL")
    parser.add_argument("--voice-name", default=None,
                        help="Voice name (for logging)")
    parser.add_argument("--num-tabs", "-t", type=int, default=2,
                        help="Number of browser tabs (default: 2)")
    parser.add_argument("--browser-profile", default=None,
                        help="Custom browser profile path (for parallel processing)")

    return parser.parse_args()


def run_multi_window_from_orchestrator(script_folders, num_tabs_per_window):
    """
    Function called by orchestrator for multi-window parallel processing.

    Opens ONE browser with multiple WINDOWS (not separate browsers).
    All windows share the same cookies = all logged into Fish Audio!
    Each window processes a different profile with multiple tabs for speed.
    """
    import threading

    logger.info(f"🎤 Starting MULTI-WINDOW voiceover generation...")
    logger.info(f"📁 Profiles to process: {len(script_folders)}")
    logger.info(f"🔢 Tabs per window: {num_tabs_per_window}")
    logger.info(f"🌐 Using ONE browser with multiple windows (shared cookies)")

    # Prepare profile data - find script files for each profile
    profiles_to_process = []
    for i, folder_info in enumerate(script_folders, 1):
        profile = folder_info.get('profile', f'profile_{i}')
        script_folder = folder_info['script_folder']
        output_folder = folder_info['output_folder']
        voice_url = folder_info.get('voice_url', VOICEOVER_URL)

        # Look for script file
        script_files = []
        for file in os.listdir(script_folder):
            if file.endswith(f'_{profile}.txt') and 'rewritten_script' in file:
                script_files.append(os.path.join(script_folder, file))

        if not script_files:
            for filename in ['script.txt', f'script_{profile}.txt']:
                script_path = os.path.join(script_folder, filename)
                if os.path.exists(script_path):
                    script_files.append(script_path)
                    break

        if not script_files:
            logger.error(f"❌ No script file found for profile {profile}")
            continue

        script_txt_path = script_files[0]
        os.makedirs(output_folder, exist_ok=True)

        # Load paragraphs for this profile
        paragraphs_data = load_text_file(script_txt_path)
        if not paragraphs_data:
            logger.error(f"❌ No paragraphs found in {script_txt_path}")
            continue

        profiles_to_process.append({
            'profile': profile,
            'script_path': script_txt_path,
            'output_folder': output_folder,
            'voice_url': voice_url,
            'paragraphs_data': paragraphs_data
        })
        logger.info(f"📋 Prepared profile {i}: {profile} ({len(paragraphs_data)} paragraphs)")

    if not profiles_to_process:
        logger.error("❌ No profiles to process!")
        return

    # Clean up locks and prepare browser profile
    os.makedirs(BROWSER_PROFILE_PATH, exist_ok=True)
    cleanup_browser_locks()

    # Open ONE browser with shared profile
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_PATH,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ],
            slow_mo=100
        )

        logger.info(f"🌐 Browser opened with shared profile (cookies preserved)")

        try:
            # Create a window (with tabs) for each profile
            window_processors = []

            for profile_info in profiles_to_process:
                profile = profile_info['profile']
                voice_url = profile_info['voice_url']
                paragraphs_data = profile_info['paragraphs_data']
                output_folder = profile_info['output_folder']

                # Calculate optimal tabs for this profile
                paragraphs = [item[0] for item in paragraphs_data]
                actual_tabs = num_tabs_per_window if num_tabs_per_window != "auto" else calculate_optimal_tabs(paragraphs)

                # Create pending tasks for this profile
                pending_tasks = []
                for idx, (paragraph_text, split_id) in enumerate(paragraphs_data, 1):
                    output_filename = f"paragraph_{split_id.zfill(3)}.mp3"
                    output_path = os.path.join(output_folder, output_filename)
                    if not os.path.exists(output_path):
                        pending_tasks.append({
                            'idx': idx,
                            'text': paragraph_text,
                            'output_path': output_path
                        })

                if not pending_tasks:
                    logger.info(f"⏭️ {profile}: All files already exist, skipping")
                    continue

                logger.info(f"🖥️ Creating window for {profile} with {actual_tabs} tabs...")

                # Create tabs for this profile (each tab is a "window" visually)
                tabs = []
                for tab_num in range(actual_tabs):
                    try:
                        page = browser.new_page()
                        page.set_default_timeout(TAB_TIMEOUT * 1000)
                        page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)

                        # Navigate to voice URL
                        page.goto(voice_url, timeout=PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

                        tab_processor = SmartTabProcessor(page, f"{profile}_T{tab_num+1}", browser)
                        tabs.append(tab_processor)
                        logger.info(f"✅ {profile}: Tab {tab_num+1} ready")
                    except Exception as e:
                        logger.error(f"❌ {profile}: Failed to create tab {tab_num+1}: {e}")

                if tabs:
                    window_processors.append({
                        'profile': profile,
                        'tabs': tabs,
                        'pending_tasks': pending_tasks,
                        'completed': 0,
                        'failed': 0,
                        'task_assignments': {}
                    })

            if not window_processors:
                logger.error("❌ No windows could be created!")
                return

            # Wait for all tabs to fully load (SPA needs time to render)
            logger.info(f"⏳ Waiting for all windows to initialize...")
            time.sleep(3)

            # Wait for Generate button to appear on each tab (ensures page fully loaded)
            for wp in window_processors:
                for tab in wp['tabs']:
                    try:
                        tab.page.wait_for_function("""
                            () => {
                                const buttons = document.querySelectorAll('button');
                                for (const btn of buttons) {
                                    const text = btn.textContent.trim();
                                    if ((text === 'Generate speech' || text === 'Generate' || text === 'Synthesize')
                                        && !btn.getAttribute('aria-haspopup')
                                        && btn.offsetParent !== null) {
                                        return true;
                                    }
                                }
                                return false;
                            }
                        """, timeout=15000)
                        logger.info(f"✅ {tab.tab_id}: Generate button found")
                    except Exception as e:
                        logger.warning(f"⚠️ {tab.tab_id}: Generate button not found after 15s: {e}")

            logger.info(f"🚀 Starting PARALLEL processing across {len(window_processors)} windows...")
            total_start_time = time.time()
            no_ready_count = 0

            # Process all windows in parallel using a main loop
            while any(wp['pending_tasks'] or any(tab.is_busy for tab in wp['tabs']) for wp in window_processors):

                for wp in window_processors:
                    profile = wp['profile']
                    tabs = wp['tabs']
                    pending_tasks = wp['pending_tasks']
                    task_assignments = wp['task_assignments']

                    # Assign new tasks to available tabs
                    for task in pending_tasks[:]:
                        if task['idx'] not in task_assignments:
                            for tab in tabs:
                                try:
                                    if tab.is_ready_for_new_task():
                                        if tab.start_generation(task['text'], task['idx']):
                                            task_assignments[task['idx']] = tab
                                            break
                                except Exception as e:
                                    logger.error(f"{profile}: Error assigning to {tab.tab_id}: {e}")

                    # Check for completed downloads
                    for task in pending_tasks[:]:
                        if task['idx'] in task_assignments:
                            tab = task_assignments[task['idx']]
                            try:
                                if tab.check_download_ready():
                                    if tab.download_file(task['output_path'], task['idx']):
                                        wp['completed'] += 1
                                        logger.info(f"🎉 {profile}: {wp['completed']}/{len(wp['pending_tasks']) + wp['completed']} done")
                                    else:
                                        wp['failed'] += 1

                                    del task_assignments[task['idx']]
                                    pending_tasks.remove(task)
                            except Exception as e:
                                logger.error(f"{profile}: Error downloading task {task['idx']}: {e}")
                                if task['idx'] in task_assignments:
                                    del task_assignments[task['idx']]
                                pending_tasks.remove(task)
                                wp['failed'] += 1

                    # Check for timeouts
                    current_time = time.time()
                    for task_idx, tab in list(task_assignments.items()):
                        if tab.current_task_start and current_time - tab.current_task_start > MAX_WAIT_TIME:
                            logger.warning(f"⏰ {profile}: Task {task_idx} timed out")
                            tab.is_busy = False
                            tab.current_task_start = None
                            del task_assignments[task_idx]
                            wp['failed'] += 1

                # Check if no tabs could accept tasks (all returned not ready)
                any_assigned = any(wp['task_assignments'] for wp in window_processors)
                any_pending_unassigned = any(
                    task['idx'] not in wp['task_assignments']
                    for wp in window_processors
                    for task in wp['pending_tasks']
                )
                if not any_assigned and any_pending_unassigned:
                    no_ready_count += 1
                    if no_ready_count % 20 == 1:  # Log every 10 seconds (20 * 0.5s)
                        logger.warning(f"⚠️ No tabs ready for {no_ready_count * 0.5:.0f}s — waiting for tabs to become available...")
                        # Debug: check what each tab sees
                        for wp in window_processors:
                            for tab in wp['tabs']:
                                try:
                                    gs_btn = tab.page.locator("button:has-text('Generate speech')").last
                                    gen_btn = tab.page.locator("button:has-text('Generate'):not([aria-haspopup])").last
                                    syn_btn = tab.page.locator("button:has-text('Synthesize')").first
                                    dl_btn = tab.page.locator("button:has-text('Download')").first
                                    logger.warning(f"  {tab.tab_id}: 'Generate speech'={gs_btn.is_visible()}, Generate(filtered)={gen_btn.is_visible()}, Synthesize={syn_btn.is_visible()}, Download={dl_btn.is_visible()}, busy={tab.is_busy}, errors={tab.error_count}")
                                except Exception as e:
                                    logger.warning(f"  {tab.tab_id}: Error checking state: {e}")
                    if no_ready_count > 120:  # 60 seconds with no progress
                        logger.error(f"❌ No tabs became ready after 60 seconds — aborting")
                        break
                else:
                    no_ready_count = 0

                # Small pause between iterations
                time.sleep(0.5)

            # Final summary
            total_time = time.time() - total_start_time
            logger.info(f"\n{'🎉' * 20}")
            logger.info(f"🏁 MULTI-WINDOW PROCESSING COMPLETED")
            logger.info(f"⏱️ Total time: {total_time / 60:.1f} minutes")
            for wp in window_processors:
                logger.info(f"  {wp['profile']}: ✅ {wp['completed']} completed, ❌ {wp['failed']} failed")
            logger.info(f"{'🎉' * 20}")

        except Exception as e:
            logger.error(f"❌ Multi-window processing error: {e}")
        finally:
            logger.info("🏁 Closing browser...")
            browser.close()


def run_smart_parallel_with_voice_url(text_file_path, output_folder, num_tabs, voice_url, profile_name, browser_profile_path=None):
    """
    Smart parallel processing with specific voice URL for a profile.

    Args:
        text_file_path: Path to the script/text file
        output_folder: Where to save voiceover MP3 files
        num_tabs: Number of browser tabs to use (or "auto")
        voice_url: Fish Audio voice URL
        profile_name: Name of the profile (for logging)
        browser_profile_path: Custom browser profile path (for parallel video processing)
                             If None, uses the default shared profile
    """

    paragraphs_data = load_text_file(text_file_path)
    if not paragraphs_data:
        return False

    # Extract paragraphs for tab calculation
    paragraphs = [item[0] for item in paragraphs_data]

    # AUTO-TAB FEATURE: Use smart calculation if num_tabs is "auto" or negative
    if num_tabs == "auto" or (isinstance(num_tabs, int) and num_tabs <= 0):
        num_tabs = calculate_optimal_tabs(paragraphs)
        logger.info(f"🤖 {profile_name} AUTO-TAB: Calculated {num_tabs} optimal tabs")
    elif isinstance(num_tabs, int) and num_tabs > 0:
        logger.info(f"👤 {profile_name} MANUAL: Using {num_tabs} tabs as specified")

    os.makedirs(output_folder, exist_ok=True)

    # Create task queue with smart naming
    pending_tasks = []
    for idx, (paragraph_text, split_id) in enumerate(paragraphs_data, 1):
        output_filename = f"paragraph_{split_id.zfill(3)}.mp3"
        output_path = os.path.join(output_folder, output_filename)

        if os.path.exists(output_path):
            logger.info(f"⏭️ {profile_name}: Skipping existing: {output_filename}")
            continue

        pending_tasks.append({
            'idx': idx,
            'text': paragraph_text,
            'output_path': output_path
        })

    if not pending_tasks:
        logger.info(f"✅ {profile_name}: All files already exist!")
        return True

    # Always use the SHARED browser profile (has Fish Audio login)
    # This ensures all voiceover tasks share the same login session
    actual_browser_path = BROWSER_PROFILE_PATH
    logger.info(f"🌐 {profile_name}: Using SHARED browser profile: {BROWSER_PROFILE_PATH}")

    # CRITICAL: Acquire exclusive lock BEFORE launching browser
    # This prevents multiple folders from trying to use the same profile simultaneously
    logger.info(f"🔐 {profile_name}: Waiting for voiceover lock (other folders may be processing)...")
    lock_handle = acquire_voiceover_lock(profile_name)
    if not lock_handle:
        logger.error(f"❌ {profile_name}: Could not acquire voiceover lock after timeout")
        return False
    logger.info(f"🔒 {profile_name}: Got exclusive voiceover lock!")

    # Now check if browser profile is available (cleanup any stale locks)
    logger.info(f"🔍 {profile_name}: Checking browser profile...")
    if not wait_for_browser_profile_available(actual_browser_path):
        logger.error(f"❌ {profile_name}: Browser profile locked after max retries")
        release_voiceover_lock(profile_name)
        return False
    logger.info(f"✅ {profile_name}: Browser profile is available!")

    os.makedirs(actual_browser_path, exist_ok=True)

    # Clean up any lock files from crashed sessions (keeps cookies intact)
    cleanup_browser_locks_for_path(actual_browser_path)

    with sync_playwright() as p:
        # Launch browser with profile (custom for parallel, shared for single)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=actual_browser_path,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                f'--window-position={hash(profile_name) % 500},{hash(profile_name) % 300}',  # Unique position
                '--new-window',  # Force new window instead of new profile
            ],
            slow_mo=100
        )

        try:
            # Initialize tabs
            tabs = []
            logger.info(f"🚀 {profile_name}: Opening {num_tabs} tabs...")

            # Create all tabs and navigate them in parallel
            pages = []
            for i in range(num_tabs):
                try:
                    if i == 0 and browser.pages:
                        page = browser.pages[0]
                    else:
                        page = browser.new_page()

                    page.set_default_timeout(TAB_TIMEOUT * 1000)
                    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)
                    pages.append((page, i + 1))

                except Exception as e:
                    logger.error(f"{profile_name}: Failed to create tab {i + 1}: {e}")

            # Navigate all tabs to the profile-specific voice URL
            logger.info(f"🌐 {profile_name}: Navigating all tabs to: {voice_url}")

            for page, tab_id in pages:
                try:
                    page.goto(voice_url, timeout=PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
                except Exception as e:
                    logger.error(f"{profile_name}: Failed to navigate tab {tab_id}: {e}")

            time.sleep(3)  # Wait for all pages to load

            # Create tab processors
            for page, tab_id in pages:
                try:
                    tab_processor = SmartTabProcessor(page, f"{profile_name}_T{tab_id}", browser)
                    tabs.append(tab_processor)
                    logger.info(f"✅ {profile_name}: Tab {tab_id} ready")
                except Exception as e:
                    logger.error(f"{profile_name}: Failed to initialize tab {tab_id}: {e}")

            if not tabs:
                logger.error(f"❌ {profile_name}: No tabs could be initialized!")
                return False

            time.sleep(3)
            logger.info(f"🚀 {profile_name}: Starting parallel processing with {len(tabs)} tabs...")

            # PARALLEL processing
            completed = 0
            failed = 0
            total_tasks = len(pending_tasks)
            start_time = time.time()
            task_assignments = {}

            while pending_tasks or any(tab.is_busy for tab in tabs):

                # Assign new tasks
                for task in pending_tasks[:]:
                    if task['idx'] not in task_assignments:
                        for tab in tabs:
                            try:
                                if tab.is_ready_for_new_task():
                                    if tab.start_generation(task['text'], task['idx']):
                                        task_assignments[task['idx']] = tab
                                        logger.info(f"🚀 {profile_name}: Assigned task {task['idx']} to {tab.tab_id}")
                                        break
                            except Exception as e:
                                logger.error(f"{profile_name}: Error assigning task to {tab.tab_id}: {e}")
                                if not tab.refresh_tab():
                                    tab.recreate_tab()

                # Check completed downloads
                for task in pending_tasks[:]:
                    if task['idx'] in task_assignments:
                        tab = task_assignments[task['idx']]

                        try:
                            if tab.check_download_ready():
                                if tab.download_file(task['output_path'], task['idx']):
                                    completed += 1
                                    elapsed = time.time() - start_time
                                    remaining = total_tasks - completed
                                    avg_time = elapsed / completed if completed > 0 else 0
                                    eta = remaining * avg_time / len(tabs) if avg_time > 0 else 0

                                    logger.info(f"🎉 {profile_name}: Progress: {completed}/{total_tasks} | ETA: {eta / 60:.1f}min")
                                else:
                                    logger.error(f"❌ {profile_name}: Download failed for task {task['idx']}")
                                    failed += 1

                                del task_assignments[task['idx']]
                                pending_tasks.remove(task)

                        except Exception as e:
                            logger.error(f"{profile_name}: Error processing task {task['idx']}: {e}")
                            if task['idx'] in task_assignments:
                                del task_assignments[task['idx']]
                            pending_tasks.remove(task)
                            failed += 1

                            if not tab.refresh_tab():
                                tab.recreate_tab()

                # Check for timeouts and unhealthy tabs
                current_time = time.time()
                for task_idx, tab in list(task_assignments.items()):
                    try:
                        if tab.current_task_start and current_time - tab.current_task_start > MAX_WAIT_TIME:
                            logger.warning(f"⏰ {profile_name}: Task {task_idx} on {tab.tab_id} timed out")
                            tab.is_busy = False
                            tab.current_task_start = None
                            del task_assignments[task_idx]
                            failed += 1

                        elif not tab.is_tab_healthy():
                            logger.warning(f"🏥 {profile_name}: {tab.tab_id} unhealthy, recovering...")
                            if not tab.refresh_tab():
                                if not tab.recreate_tab():
                                    logger.error(f"❌ {profile_name}: Failed to recover {tab.tab_id}")
                                    if task_idx in task_assignments:
                                        del task_assignments[task_idx]
                                        failed += 1

                    except Exception as e:
                        logger.error(f"{profile_name}: Error managing {tab.tab_id}: {e}")

                time.sleep(2)

            # Profile summary
            total_time = time.time() - start_time
            success_rate = (completed / len(paragraphs_data)) * 100 if paragraphs_data else 0

            logger.info(f"\n🎯 {profile_name} COMPLETED:")
            logger.info(f"✅ Successful: {completed}/{len(paragraphs_data)}")
            logger.info(f"❌ Failed: {failed}")
            logger.info(f"📊 Success rate: {success_rate:.1f}%")
            logger.info(f"⏱️ Time: {total_time / 60:.1f} minutes")

            return completed > 0

        except Exception as e:
            logger.error(f"❌ {profile_name}: Processing error: {e}")
            return False
        finally:
            logger.info(f"🏁 {profile_name}: Closing browser...")
            try:
                browser.close()
            except Exception as e:
                logger.warning(f"⚠️ {profile_name}: Error closing browser: {e}")
            # ALWAYS release the voiceover lock so other folders can proceed
            release_voiceover_lock(profile_name)


if __name__ == "__main__":
    print("🧠 IMPROVED SMART PARALLEL VOICEOVER GENERATOR")
    print("(Enhanced Tab Management + Error Recovery)")
    print("=" * 60)
    print("⚡ Features:")
    print("  - All tabs work in parallel")
    print("  - Smart timing based on text length")
    print("  - Automatic tab health monitoring")
    print("  - Tab refresh and recreation on errors")
    print("  - Better error handling and recovery")
    print("  - Progress tracking across all tabs")
    print("=" * 60)

    # Check if running with command-line arguments
    args = parse_arguments()

    if args.text_file:
        # Running from command line (e.g., from story_video_creator.py)
        text_file_path = args.text_file
        output_folder = args.output_folder or DEFAULT_OUTPUT_FOLDER
        num_tabs = args.num_tabs

        # Override voice URL if provided
        if args.voice_url:
            VOICEOVER_URL = args.voice_url
            print(f"🎤 Using voice URL: {args.voice_url}")

        if args.voice_name:
            print(f"🎤 Voice: {args.voice_name}")
    else:
        # Interactive mode - only works when running directly with a terminal
        if not sys.stdin or not sys.stdin.isatty():
            print("❌ Interactive mode requires a terminal. Use command-line arguments instead.")
            print("Usage: python 5_generate_voiceover.py <text_file> [--output-folder <folder>] [--num-tabs <n>]")
            sys.exit(1)
        text_file_path = input("Text file (default: script.txt): ").strip() or "script.txt"
        output_folder = input(f"Output folder (default: {DEFAULT_OUTPUT_FOLDER}): ").strip() or DEFAULT_OUTPUT_FOLDER

        num_tabs_input = input("Number of tabs (recommended: 2-3): ").strip()
        num_tabs = int(num_tabs_input) if num_tabs_input.isdigit() else 2

    print(f"\n🧠 IMPROVED SMART PARALLEL MODE")
    print(f"📁 Text file: {text_file_path}")
    print(f"📂 Output folder: {output_folder}")
    print(f"🔢 Tabs: {num_tabs}")
    print(f"⏱️ Wait time: {BASE_WAIT_TIME}s base + {SECONDS_PER_100_CHARS}s per 100 chars")
    print(f"🏥 Tab health monitoring: Every {TAB_REFRESH_INTERVAL}s")

    run_smart_parallel(text_file_path, output_folder, num_tabs)


# =============================================================================
# SHARED BROWSER INSTANCE FOR PARALLEL FOLDER PROCESSING
# =============================================================================
# This allows multiple folders to share ONE browser with multiple tabs
# Login once, all folders use the same session

_SHARED_BROWSER = None
_SHARED_BROWSER_LOCK = None

def get_shared_browser():
    """Get or create a shared browser instance for parallel folder processing"""
    global _SHARED_BROWSER, _SHARED_BROWSER_LOCK
    import threading

    if _SHARED_BROWSER_LOCK is None:
        _SHARED_BROWSER_LOCK = threading.Lock()

    return _SHARED_BROWSER

def init_shared_browser(playwright_instance):
    """Initialize the shared browser (call once before parallel processing)"""
    global _SHARED_BROWSER

    cleanup_browser_locks()
    os.makedirs(BROWSER_PROFILE_PATH, exist_ok=True)

    _SHARED_BROWSER = playwright_instance.chromium.launch_persistent_context(
        user_data_dir=BROWSER_PROFILE_PATH,
        headless=False,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--start-maximized',
        ],
        slow_mo=100
    )
    logger.info(f"🌐 Shared browser initialized with profile: {BROWSER_PROFILE_PATH}")
    return _SHARED_BROWSER

def close_shared_browser():
    """Close the shared browser"""
    global _SHARED_BROWSER
    if _SHARED_BROWSER:
        try:
            _SHARED_BROWSER.close()
        except:
            pass
        _SHARED_BROWSER = None
        logger.info("🌐 Shared browser closed")


def run_parallel_folders_voiceover(folder_tasks, voice_url, max_tabs_per_folder=3):
    """
    Process multiple folders using ONE shared browser with multiple tabs.

    Args:
        folder_tasks: List of dicts with keys:
            - 'folder_name': Name for logging
            - 'text_file': Path to voiceover script
            - 'output_folder': Where to save MP3s
            - 'profile_name': Profile name for logging
        voice_url: Fish Audio voice URL
        max_tabs_per_folder: Max tabs to use per folder (total tabs = folders * this)

    Returns:
        dict with results per folder
    """
    from playwright.sync_api import sync_playwright

    results = {}

    with sync_playwright() as p:
        # Initialize ONE shared browser
        browser = init_shared_browser(p)

        try:
            # Collect all tasks from all folders
            all_tasks = []
            for folder in folder_tasks:
                paragraphs_data = load_text_file(folder['text_file'])
                if not paragraphs_data:
                    results[folder['folder_name']] = {'success': False, 'error': 'No text'}
                    continue

                os.makedirs(folder['output_folder'], exist_ok=True)

                for idx, (paragraph_text, split_id) in enumerate(paragraphs_data, 1):
                    output_filename = f"paragraph_{split_id.zfill(3)}.mp3"
                    output_path = os.path.join(folder['output_folder'], output_filename)

                    if os.path.exists(output_path):
                        logger.info(f"⏭️ {folder['folder_name']}: Skipping existing: {output_filename}")
                        continue

                    all_tasks.append({
                        'folder_name': folder['folder_name'],
                        'profile_name': folder['profile_name'],
                        'idx': idx,
                        'text': paragraph_text,
                        'output_path': output_path
                    })

            if not all_tasks:
                logger.info("✅ All voiceovers already exist!")
                return {f['folder_name']: {'success': True} for f in folder_tasks}

            # Calculate total tabs needed
            total_tabs = min(len(all_tasks), len(folder_tasks) * max_tabs_per_folder, 12)
            logger.info(f"🚀 Opening {total_tabs} tabs for {len(all_tasks)} tasks across {len(folder_tasks)} folders")

            # Create tabs
            tabs = []
            for i in range(total_tabs):
                try:
                    if i == 0 and browser.pages:
                        page = browser.pages[0]
                    else:
                        page = browser.new_page()

                    page.set_default_timeout(TAB_TIMEOUT * 1000)
                    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)

                    # Navigate to Fish Audio
                    page.goto(voice_url, wait_until='networkidle', timeout=PAGE_LOAD_TIMEOUT)
                    time.sleep(1)

                    tabs.append({
                        'page': page,
                        'is_busy': False,
                        'tab_num': i + 1
                    })
                    logger.info(f"✅ Tab {i + 1}/{total_tabs} ready")

                except Exception as e:
                    logger.error(f"❌ Failed to create tab {i + 1}: {e}")

            if not tabs:
                logger.error("❌ No tabs created!")
                return {f['folder_name']: {'success': False, 'error': 'No tabs'} for f in folder_tasks}

            # Process all tasks
            pending = list(all_tasks)
            completed = {f['folder_name']: 0 for f in folder_tasks}
            failed = {f['folder_name']: 0 for f in folder_tasks}
            task_assignments = {}

            while pending or task_assignments:
                # Assign tasks to free tabs
                for tab in tabs:
                    if not tab['is_busy'] and pending:
                        task = pending.pop(0)
                        tab['is_busy'] = True
                        tab['current_task'] = task
                        tab['start_time'] = time.time()

                        try:
                            # Enter text
                            page = tab['page']
                            text_area = page.locator('textarea').first
                            text_area.click()
                            text_area.fill('')
                            text_area.fill(task['text'])

                            # Click generate (try "Generate speech" first, then filtered "Generate")
                            generate_btn = page.locator('button:has-text("Generate speech")')
                            if generate_btn.count() == 0:
                                generate_btn = page.locator('button:has-text("Generate"):not([aria-haspopup]), button:has-text("生成")')
                            if generate_btn.count() > 0:
                                generate_btn.last.click()
                                task_assignments[task['idx']] = tab
                                logger.info(f"🎤 Tab {tab['tab_num']}: Started {task['folder_name']} paragraph {task['idx']}")

                        except Exception as e:
                            logger.error(f"❌ Tab {tab['tab_num']}: Failed to start: {e}")
                            tab['is_busy'] = False
                            failed[task['folder_name']] += 1

                # Check for completed downloads
                for task_idx, tab in list(task_assignments.items()):
                    task = tab['current_task']
                    try:
                        page = tab['page']

                        # Check for download button
                        download_btn = page.locator('a[download], button:has-text("Download"), button:has-text("下载")')
                        if download_btn.count() > 0 and download_btn.first.is_visible():
                            # Download the file
                            with page.expect_download(timeout=30000) as download_info:
                                download_btn.first.click()
                            download = download_info.value
                            download.save_as(task['output_path'])

                            logger.info(f"✅ {task['folder_name']}: Saved paragraph {task['idx']}")
                            completed[task['folder_name']] += 1

                            # Reset tab
                            tab['is_busy'] = False
                            del task_assignments[task_idx]

                            # Refresh page for next task
                            page.goto(voice_url, wait_until='networkidle', timeout=PAGE_LOAD_TIMEOUT)
                            time.sleep(0.5)

                    except Exception as e:
                        # Check timeout
                        if time.time() - tab['start_time'] > MAX_WAIT_TIME:
                            logger.warning(f"⏰ {task['folder_name']}: Paragraph {task['idx']} timed out")
                            tab['is_busy'] = False
                            del task_assignments[task_idx]
                            failed[task['folder_name']] += 1

                            # Refresh page
                            try:
                                page.goto(voice_url, wait_until='networkidle', timeout=PAGE_LOAD_TIMEOUT)
                            except:
                                pass

                time.sleep(1)

            # Build results
            for folder in folder_tasks:
                name = folder['folder_name']
                results[name] = {
                    'success': failed[name] == 0,
                    'completed': completed[name],
                    'failed': failed[name]
                }

            logger.info(f"\n{'=' * 60}")
            logger.info("🏁 PARALLEL VOICEOVER COMPLETE")
            for name, result in results.items():
                status = "✅" if result['success'] else "❌"
                logger.info(f"  {status} {name}: {result['completed']} done, {result['failed']} failed")
            logger.info(f"{'=' * 60}")

        finally:
            close_shared_browser()

    return results