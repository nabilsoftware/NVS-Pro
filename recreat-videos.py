import os
import subprocess
import shutil
import argparse
import logging
import time
from pathlib import Path
import re
import json
import sys
from typing import List, Dict, Optional
import io
import threading

# Ensure bundled FFmpeg is on PATH (for fresh installs without system FFmpeg)
_assets_bin = Path(__file__).parent.resolve() / "assets" / "bin"
if _assets_bin.exists() and str(_assets_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_assets_bin) + ";" + os.environ.get("PATH", "")

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==============================================================================
# --- FROZEN/EXE DETECTION ---
# ==============================================================================
# Detect if running as PyInstaller bundled app or as Python script
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    # Running as compiled executable
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
    # Use embedded Python for running scripts
    EMBEDDED_PYTHON = SCRIPT_DIR / "python" / "python.exe"
    if EMBEDDED_PYTHON.exists():
        PYTHON_EXE = str(EMBEDDED_PYTHON)
    else:
        # Fallback to system Python if embedded not found
        PYTHON_EXE = sys.executable
else:
    # Running as script
    SCRIPT_DIR = Path(__file__).parent.resolve()
    PYTHON_EXE = sys.executable

# ==============================================================================
# --- CONFIGURATION LOADING ---
# ==============================================================================

def get_user_data_dir() -> Path:
    """Get the user data directory (AppData on Windows)"""
    if os.name == 'nt':  # Windows
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        user_dir = Path(appdata) / "NabilVideoStudioPro"
    else:  # Linux/Mac
        user_dir = Path.home() / ".nvspro"

    return user_dir

def load_configuration():
    """Load configuration from config.json file"""
    # Look in AppData (same location as UI)
    user_data_dir = get_user_data_dir()
    config_file = user_data_dir / "config.json"

    # Fallback to script directory if not found in AppData
    if not config_file.exists():
        config_file = SCRIPT_DIR / "config.json"

    if not config_file.exists():
        print(f"\n{'='*70}")
        print("❌ ERROR: Configuration file not found!")
        print(f"{'='*70}")
        print(f"Expected location: {config_file}")
        print("\nPlease create 'config.json' from the template:")
        print("1. Copy 'config.example.json' to 'config.json'")
        print("2. Edit 'config.json' with your paths and settings")
        print("3. Run this script again")
        print(f"{'='*70}\n")
        sys.exit(1)

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ Configuration loaded from: {config_file}")
        return config
    except json.JSONDecodeError as e:
        print(f"\n❌ ERROR: Invalid JSON in configuration file!")
        print(f"Error: {e}")
        print(f"File: {config_file}")
        print("\nPlease fix the JSON syntax and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: Could not load configuration!")
        print(f"Error: {e}")
        sys.exit(1)


def resolve_path(path_str: str, base_dir: Path = SCRIPT_DIR) -> Path:
    """Resolve a path string to absolute Path, handling relative paths"""
    if not path_str:
        return base_dir

    path = Path(path_str)

    # If already absolute, return as-is
    if path.is_absolute():
        return path

    # Otherwise, treat as relative to script directory
    return (base_dir / path).resolve()


# Load configuration
CONFIG = load_configuration()

# --- 1. SCRIPT PATHS ---
SPLITE_VIDEO_SCRIPT = SCRIPT_DIR / "1_diarize_cut_video.py"
STYLE_INTERVIEW_SCRIPT = SCRIPT_DIR / "2_style_interview_clips.py"
VIDEO_TO_SCRIPT_SCRIPT = SCRIPT_DIR / "3_transcribe_clips.py"
SCRIPT_WRITER_AI_SCRIPT = SCRIPT_DIR / "4_ai_rewrite_script.py"

# --- Select voiceover script based on Settings (Voiceover Method) ---
def get_voiceover_script():
    """Choose voiceover script based on user's setting in Settings page"""
    config_path = get_user_data_dir() / "config.json"

    # Default to browser
    use_api = False

    # Check user's setting
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                method = config.get("voiceover_settings", {}).get("method", "Fish Audio (Browser)")
                if "API" in method.upper():
                    use_api = True
        except:
            pass

    if use_api:
        api_script = SCRIPT_DIR / "5_generate_voiceover_api.py"
        if api_script.exists():
            return api_script

    return SCRIPT_DIR / "5_generate_voiceover.py"

# Note: Don't cache this - call get_voiceover_script() at runtime to respect user settings
# get_voiceover_script() = get_voiceover_script()  # OLD - cached at startup
CLIPS_MAKER_BATCH = SCRIPT_DIR / "6_rearrange_broll_clips.bat"
CLIPS_PLUS_VOICEOVER_SCRIPT = SCRIPT_DIR / "7_assemble_final_video.py"
RANK_VIDEO_SEQUENCE_SCRIPT = SCRIPT_DIR / "8_rank_video_sequence.py"
COMBINE_RANKED_SCRIPT = SCRIPT_DIR / "9_combine_ranked_videos.py"
YOUTUBE_UPLOAD_SCRIPT = SCRIPT_DIR / "10_youtube_upload.py"
THUMBNAIL_GENERATOR_SCRIPT = SCRIPT_DIR / "11_thumbnail_generator.py"
# --- 2. INPUT/OUTPUT FOLDERS (from config) ---
DEFAULT_INPUT_VIDEOS_FOLDER = resolve_path(CONFIG.get("paths", {}).get("input_videos_folder", "./input"))
DEFAULT_PROJECT_OUTPUT_BASE_DIR = resolve_path(CONFIG.get("paths", {}).get("output_base_dir", "./output"))

# --- 2A. CUSTOM B-ROLL INPUT (STEP 6) ---
USE_CUSTOM_BROLL_INPUT = CONFIG.get("processing_settings", {}).get("use_custom_broll_input", False)
CUSTOM_BROLL_INPUT_FOLDER = resolve_path(CONFIG.get("paths", {}).get("custom_broll_folder", "./custom_broll"))
USE_VOICEOVER_CLIPS_FOR_BROLL = CONFIG.get("processing_settings", {}).get("use_voiceover_clips_for_broll", True)
TRIM_VOICEOVER_CLIPS_SECONDS = CONFIG.get("processing_settings", {}).get("trim_voiceover_clips_seconds", 2.0)
TRIM_INTERVIEW_CLIPS_SECONDS = CONFIG.get("processing_settings", {}).get("trim_interview_clips_seconds", 0)

# --- 2A-NEW. GLOBAL B-ROLL FROM UI QUICK OPTIONS ---
QUICK_OPTIONS = CONFIG.get("quick_options", {})
USE_GLOBAL_BROLL = QUICK_OPTIONS.get("use_global_broll", False)
GLOBAL_BROLL_FOLDER = resolve_path(QUICK_OPTIONS.get("global_broll_folder", "")) if QUICK_OPTIONS.get("global_broll_folder") else None

# --- 2A-NEW2. PER-FOLDER SETTINGS FROM UI (Custom Channel, Custom B-roll) ---
PER_FOLDER_SETTINGS = CONFIG.get("per_folder_settings", [])
# Format: [{'path': 'D:/input/VD-1', 'channel': 'ChannelName', 'broll': 'D:/broll/folder'}, ...]

def get_per_folder_broll(input_folder_path: str) -> Path:
    """Get custom B-roll folder for a specific input folder, if configured"""
    input_path = str(Path(input_folder_path).resolve())
    for fs in PER_FOLDER_SETTINGS:
        fs_path = str(Path(fs.get('path', '')).resolve())
        if fs_path == input_path and fs.get('broll'):
            broll_path = resolve_path(fs['broll'])
            if broll_path and broll_path.exists():
                return broll_path
    return None

def get_per_folder_channel(input_folder_path: str) -> str:
    """Get custom channel for a specific input folder, if configured"""
    input_path = str(Path(input_folder_path).resolve())
    for fs in PER_FOLDER_SETTINGS:
        fs_path = str(Path(fs.get('path', '')).resolve())
        if fs_path == input_path and fs.get('channel'):
            return fs['channel']
    return None

# --- 2B. GLOBAL DEFAULTS ---
USE_MANUAL_CROP_DEFAULT = CONFIG.get("processing_settings", {}).get("use_manual_crop_default", True)
ENABLE_LOGO_IN_STEP7 = CONFIG.get("processing_settings", {}).get("enable_logo_in_step7", True)
USE_MULTI_FOLDER_MODE = CONFIG.get("multi_folder_mode", {}).get("enabled", False)
MULTI_INPUT_FOLDERS = [resolve_path(folder) for folder in CONFIG.get("multi_folder_mode", {}).get("input_folders", [])]
API_KEYS_FILE = resolve_path(CONFIG.get("ai_settings", {}).get("api_keys_file", "./api_keys.json"))
USE_FOLDER_NAME_FOR_OUTPUT = CONFIG.get("processing_settings", {}).get("use_folder_name_for_output", False)
# Thumbnail mode: "script" (use AI rewritten script) or "title" (extract from thumbnail_TITLE.jpg filename) or "off"
# For Recreate Videos: check quick_options.rv_thumb_mode FIRST
THUMBNAIL_MODE = CONFIG.get("quick_options", {}).get("rv_thumb_mode", "")
if not THUMBNAIL_MODE:
    THUMBNAIL_MODE = CONFIG.get("processing_settings", {}).get("thumbnail_mode", "script")

# --- UI MODE FLAG (set to True when running from UI with --profile argument) ---
UI_MODE = False  # Will be set to True in main() if --profile is specified


# --- 3A. DEFAULT ANIMATION SETTINGS FOR STEP 2 (from config) ---
DEFAULT_ENABLE_ANIMATION = CONFIG.get("animation_settings", {}).get("enable_animation", True)
DEFAULT_ANIMATION_TYPE = CONFIG.get("animation_settings", {}).get("animation_type", "slide")
DEFAULT_ANIMATION_DIRECTION = CONFIG.get("animation_settings", {}).get("animation_direction", "left")
DEFAULT_ANIMATION_DURATION = CONFIG.get("animation_settings", {}).get("animation_duration", 0.5)
DEFAULT_ENABLE_OUT_ANIMATION = CONFIG.get("animation_settings", {}).get("enable_out_animation", True)
DEFAULT_OUT_ANIMATION_DURATION = CONFIG.get("animation_settings", {}).get("out_animation_duration", 0.3)

# --- 3B. SOUND EFFECT SETTINGS FOR STEP 2 (from config) ---
_SFX_SETTINGS = CONFIG.get("sound_effect_settings", {})
SOUND_EFFECT_ENABLED = _SFX_SETTINGS.get("enabled", False)
SOUND_EFFECT_PATH = _SFX_SETTINGS.get("file_path", "")
SOUND_EFFECT_VOLUME = _SFX_SETTINGS.get("volume", 1.0)
SOUND_EFFECT_DURATION = _SFX_SETTINGS.get("duration", 0.8)


def get_sound_effect_args() -> list:
    """Get sound effect CLI arguments for styling script"""
    if SOUND_EFFECT_ENABLED and SOUND_EFFECT_PATH and Path(SOUND_EFFECT_PATH).exists():
        return [
            "--enable-sound-effect",
            "--sound-effect-path", str(SOUND_EFFECT_PATH),
            "--sound-effect-volume", str(SOUND_EFFECT_VOLUME),
            "--sound-effect-duration", str(SOUND_EFFECT_DURATION),
        ]
    else:
        return ["--disable-sound-effect"]


# --- 4. PROMPT-VOICE PROFILE SYSTEM (from config) ---
def load_profiles_from_config():
    """Load and process profiles from config, resolving file paths"""
    profiles = {}
    prompts_folder = resolve_path(CONFIG.get("paths", {}).get("prompts_folder", "./prompts"))
    backgrounds_folder = resolve_path(CONFIG.get("paths", {}).get("backgrounds_folder", "./backgrounds"))
    music_folder = resolve_path(CONFIG.get("paths", {}).get("background_music_folder", "./music"))

    for profile_key, profile_data in CONFIG.get("profiles", {}).items():
        profile = profile_data.copy()

        # Resolve prompt file path (can be relative to prompts folder or absolute)
        prompt_file_str = profile["prompt_file"]
        if Path(prompt_file_str).is_absolute():
            profile["prompt_file"] = Path(prompt_file_str)
        else:
            # Try relative to prompts folder first, then script dir
            prompt_path = prompts_folder / prompt_file_str
            if not prompt_path.exists():
                prompt_path = SCRIPT_DIR / prompt_file_str
            profile["prompt_file"] = prompt_path

        # Resolve background video path
        bg_video = profile.get("background_video", "")
        if bg_video:
            if Path(bg_video).is_absolute():
                profile["background_video"] = bg_video
            else:
                profile["background_video"] = str(backgrounds_folder / bg_video)

        # Resolve background music path
        bg_music = profile.get("background_music", "")
        if bg_music:
            if Path(bg_music).is_absolute():
                profile["background_music"] = bg_music
            else:
                profile["background_music"] = str(music_folder / bg_music)

        profiles[profile_key] = profile

    return profiles

PROMPT_PROFILES = load_profiles_from_config()

# --- 5. AVAILABLE VOICE MODELS (from config) ---
AVAILABLE_VOICES = CONFIG.get("voices", {})

# --- 6. BACKGROUND MUSIC CONFIGURATION (from config) ---
ENABLE_BACKGROUND_MUSIC = CONFIG.get("background_music", {}).get("enabled", True)
DEFAULT_VOICE_LEVEL = CONFIG.get("background_music", {}).get("default_voice_level", 1.2)
DEFAULT_MUSIC_LEVEL = CONFIG.get("background_music", {}).get("default_music_level", 0.1)
DEFAULT_BACKGROUND_MUSIC_FOLDER = resolve_path(CONFIG.get("paths", {}).get("background_music_folder", "./music"))

# --- 7. PROCESSING CONFIGURATION (from config) ---
PROCESSING_MODE = CONFIG.get("processing_settings", {}).get("processing_mode", "sequential")
ENABLE_PARALLEL_STEPS = CONFIG.get("processing_settings", {}).get("enable_parallel_steps", True)

# --- 7A. BACKGROUND UPLOAD CONFIGURATION ---
# When enabled, uploads run in background while next video starts processing
ENABLE_BACKGROUND_UPLOAD = CONFIG.get("processing_settings", {}).get("enable_background_upload", True)
_background_upload_threads = []  # Track active background upload threads
_background_upload_lock = threading.Lock()  # Thread-safe access to thread list

ORCHESTRATOR_LOG_FILE_NAME = "orchestrator_run.log"
STATUS_FILE_NAME = "pipeline_status.json"
STATUS_KEY_LAST_COMPLETED_STEP = "last_completed_step"
STATUS_KEY_STATE = "state"
STATUS_KEY_TIMESTAMP = "last_run_timestamp"

# --- 7. PROJECT SUBDIRECTORY NAMES ---
SUBDIR_ORIGINAL_VIDEO = "0_original_video"
SUBDIR_CLIPS_MAIN = "1_clips"
SUBDIR_PRIMARY_CLIPS = "voiceover"  # Subfolder inside 1_clips
SUBDIR_INVERSE_CLIPS = "interviews"  # Subfolder inside 1_clips
SUBDIR_STYLED_CLIPS = "2_styled_clips"  # NEW STEP 2 OUTPUT
SUBDIR_TRANSCRIPTS = "3_transcripts"
SUBDIR_AI_SCRIPTS = "4_ai_scripts"
SUBDIR_VOICEOVERS = "5_voiceovers"
SUBDIR_REARRANGED_BROLL_CLIPS = "6_6sec_clips"
SUBDIR_FINAL_VIDEOS = "7_final_videos"
SUBDIR_RANKED_SEQUENCE = "8_ranked_sequence"
SUBDIR_NEW_STEP9 = "9_combined_videos"
# SUBDIR_METADATA = "10_metadata"  # REMOVED - No longer needed
SUBDIR_YOUTUBE_UPLOADS = "10_youtube_uploads"
SUBDIR_LOGS = "logs"
SUBDIR_TEMP_SCRIPTS = "temp_scripts"

# --- 8. SUB-SCRIPT PARAMETERS (from config) ---
DIARIZATION_RE_ENCODE = CONFIG.get("diarization_settings", {}).get("re_encode", True)
DIARIZATION_USE_SPLEETER = CONFIG.get("diarization_settings", {}).get("use_spleeter", False)
TRANSCRIPTION_SAVE_SRT_FILES = CONFIG.get("transcription_settings", {}).get("save_srt_files", True)
TRANSCRIPTION_SAVE_INDIVIDUAL_TXT_FILES = CONFIG.get("transcription_settings", {}).get("save_individual_txt", True)
TRANSCRIPTION_SAVE_COMBINED_FILE = CONFIG.get("transcription_settings", {}).get("save_combined_file", True)
TRANSCRIPTION_SAVE_JSON_FILES = CONFIG.get("transcription_settings", {}).get("save_json_files", False)
TRANSCRIPTION_CREATE_FOLDER_PER_INPUT = CONFIG.get("transcription_settings", {}).get("create_folder_per_input", False)
TRANSCRIPTION_SHOW_PROGRESS_BAR = CONFIG.get("transcription_settings", {}).get("show_progress_bar", True)
TRANSCRIPTION_SHOW_DETAILED_LOGS = CONFIG.get("transcription_settings", {}).get("show_detailed_logs", False)

# Get AI provider from config
def get_ai_provider():
    """Get AI provider from config.json (gemini, claude, or openai)"""
    return CONFIG.get("ai_settings", {}).get("provider", "gemini")


# Get AI model name from api_keys.json (where UI saves it) for the selected provider
def get_ai_model_name(provider=None):
    """Get AI model name for the specified provider"""
    if provider is None:
        provider = get_ai_provider()

    # First try AppData (where UI saves)
    if os.name == 'nt':
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        appdata_api_keys = Path(appdata) / "NabilVideoStudioPro" / "api_keys.json"
    else:
        appdata_api_keys = Path.home() / ".nvspro" / "api_keys.json"

    if appdata_api_keys.exists():
        try:
            with open(appdata_api_keys, 'r', encoding='utf-8') as f:
                data = json.load(f)
                provider_data = data.get(provider, {})
                model = provider_data.get("model", "")
                if model:
                    return model
        except:
            pass

    # Default models per provider
    default_models = {
        "gemini": "gemini-2.5-pro",
        "claude": "claude-sonnet-4-20250514",
        "openai": "gpt-4o"
    }
    return default_models.get(provider, "gemini-2.5-pro")


AI_PROVIDER = get_ai_provider()
AI_REWRITE_MODEL_NAME = get_ai_model_name(AI_PROVIDER)
FISH_AUDIO_NUM_TABS = CONFIG.get("voiceover_settings", {}).get("num_tabs", 3)
FISH_AUDIO_BASE_WAIT_TIME = CONFIG.get("voiceover_settings", {}).get("base_wait_time", 5)
FISH_AUDIO_SECONDS_PER_100_CHARS = CONFIG.get("voiceover_settings", {}).get("seconds_per_100_chars", 3)
FISH_AUDIO_MAX_WAIT_TIME = CONFIG.get("voiceover_settings", {}).get("max_wait_time", 300)

# --- 9. VOCAL EXTRACTION PARAMETERS (from config) ---
VOCAL_EXTRACTION_ENABLED = CONFIG.get("vocal_extraction", {}).get("enabled", False)
VOCAL_EXTRACTION_PARALLEL_JOBS = CONFIG.get("vocal_extraction", {}).get("parallel_jobs", 4)
VOCAL_EXTRACTION_MODEL = CONFIG.get("vocal_extraction", {}).get("model", "htdemucs")
ASSEMBLE_VIDEO_USE_FAST_COPY = True

# --- 10. MULTI-WINDOW VOICEOVER SETTINGS (from config) ---
USE_MULTI_WINDOW_VOICEOVER = CONFIG.get("voiceover_settings", {}).get("use_multi_window", False)
TABS_PER_WINDOW = CONFIG.get("voiceover_settings", {}).get("tabs_per_window", 3)
ENABLE_PROFILE_PARALLEL_PROCESSING = CONFIG.get("voiceover_settings", {}).get("enable_parallel_processing", False)

# ==============================================================================4
# --- PIPELINE STEPS DEFINITION ---
# ==============================================================================

def get_pipeline_steps_info(multi_mode: bool = False):
    """Returns pipeline steps based on processing mode"""
    if multi_mode:
        return {
            0: {"name": "Copy & Rename Original Video"},
            1: {"name": "Diarize and Cut Video"},
            2: {"name": "Style Interview Clips"},  # NEW STEP 2
            3: {"name": "Transcribe Primary Clips"},
            4: {"name": "AI Rewrite Scripts (Selected Profiles)"},
            5: {"name": "Generate Voiceovers (Selected Profiles)"},
            6: {"name": "Rearrange B-roll Clips"},
            7: {"name": "Assemble Final Videos (Selected Profiles)"},
            8: {"name": "Rank Video Sequence (Interviews + Voiceovers)"},
            9: {"name": "Combine Ranked Videos"},  # NEW STEP 9
            10: {"name": "Upload to YouTube (Selected Profiles)"},  # STEP 11 BECOMES STEP 10
        }
    else:
        return {
            0: {"name": "Copy & Rename Original Video"},
            1: {"name": "Diarize and Cut Video"},
            2: {"name": "Style Interview Clips"},  # NEW STEP 2
            3: {"name": "Transcribe Primary Clips"},
            4: {"name": "AI Rewrite Script"},
            5: {"name": "Generate Voiceover"},
            6: {"name": "Rearrange B-roll Clips"},
            7: {"name": "Assemble Final Video"},
            8: {"name": "Rank Video Sequence (Interviews + Voiceovers)"},
            9: {"name": "Combine Ranked Videos"},  # NEW STEP 9
            10: {"name": "Upload to YouTube"},  # STEP 11 BECOMES STEP 10
        }


# ==============================================================================
# --- LOGGING SETUP ---
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(ORCHESTRATOR_LOG_FILE_NAME, mode='a', encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ])
logger = logging.getLogger(__name__)


# ==============================================================================
# --- STEP SELECTION FUNCTION ---
# ==============================================================================

def display_step_selection_menu() -> int:
    """Display step selection menu and return chosen step number"""
    print("\n" + "=" * 70)
    print("🎯 STEP SELECTION:")
    print("=" * 70)
    print("0. Copy & Rename Original Video")
    print("1. Diarize and Cut Video")
    print("2. Style Interview Clips")
    print("3. Transcribe Primary Clips")
    print("4. AI Rewrite Scripts")
    print("5. Generate Voiceovers")
    print("6. Rearrange B-roll Clips")
    print("7. Assemble Final Videos")
    print("8. Rank Video Sequence")
    print("9. Combine Ranked Videos")
    print("10. Upload to YouTube")
    print("=" * 70)
    print("A. Auto-skip mode (skip completed steps)")
    print("=" * 70)

    while True:
        try:
            choice = input("Select step to start from (0-10) [Enter=start from 0]: ").strip().upper()

            if choice == '':
                print("📋 Selected: Start from Step 0")
                return 0
            elif choice == 'A':
                print("📋 Selected: Auto-skip mode")
                return -1

            if choice.isdigit():
                step_num = int(choice)
                if 0 <= step_num <= 10:
                    print(f"📋 Selected: Start from Step {step_num}")
                    return step_num
                else:
                    print("❌ Invalid step. Please enter 0-10 or 'A'.")
            else:
                print("❌ Invalid input. Please enter 0-10 or 'A'.")
        except ValueError:
            print("❌ Invalid input. Please enter 0-10 or 'A'.")


# ==============================================================================
# --- FIXED MODE SELECTION FUNCTIONS ---
# ==============================================================================

def use_specific_profile(profile_name: str) -> Dict:
    """Use a specific profile by name (for UI/command-line mode)"""
    global PROMPT_PROFILES

    # Find the profile by name
    found_profile = None
    found_key = None

    for profile_key, profile_info in PROMPT_PROFILES.items():
        if profile_info['name'] == profile_name or profile_key == profile_name:
            found_profile = profile_info
            found_key = profile_key
            break

    if not found_profile:
        print(f"❌ ERROR: Profile '{profile_name}' not found!")
        print("Available profiles:")
        for profile_key, profile_info in PROMPT_PROFILES.items():
            print(f"   • {profile_info['name']} (key: {profile_key})")
        sys.exit(1)

    # Check if prompt file exists
    if not found_profile["prompt_file"].exists():
        print(f"❌ ERROR: Profile '{profile_name}' prompt file not found: {found_profile['prompt_file']}")
        sys.exit(1)

    print(f"✅ Using profile: {found_profile['name']}")
    print(f"   Voice: {found_profile['default_voice']}")
    print(f"   Prompt: {found_profile['prompt_file']}")

    # Create temporary PROMPT_PROFILES with only this profile
    original_profiles = PROMPT_PROFILES.copy()
    PROMPT_PROFILES.clear()
    PROMPT_PROFILES[found_key] = found_profile

    return {"mode": "numbered", "count": 1, "restore_profiles": original_profiles}


def use_specific_profiles(profile_names: list) -> Dict:
    """Use specific profiles by name (for UI/command-line mode with multiple selections)"""
    global PROMPT_PROFILES

    # Find all requested profiles
    found_profiles = {}
    missing_profiles = []

    for profile_name in profile_names:
        found = False
        for profile_key, profile_info in PROMPT_PROFILES.items():
            if profile_info['name'] == profile_name or profile_key == profile_name:
                found_profiles[profile_key] = profile_info
                found = True
                break
        if not found:
            missing_profiles.append(profile_name)

    if missing_profiles:
        print(f"⚠️ WARNING: Some profiles not found: {', '.join(missing_profiles)}")
        print("Available profiles:")
        for profile_key, profile_info in PROMPT_PROFILES.items():
            print(f"   • {profile_info['name']} (key: {profile_key})")

    if not found_profiles:
        print("❌ ERROR: No valid profiles found!")
        sys.exit(1)

    # Save original and replace with selected profiles
    original_profiles = PROMPT_PROFILES.copy()
    PROMPT_PROFILES.clear()
    PROMPT_PROFILES.update(found_profiles)

    profile_names_str = ", ".join([p['name'] for p in found_profiles.values()])
    print(f"📹 Using {len(found_profiles)} selected profile(s): {profile_names_str}")

    return {"mode": "numbered", "count": len(found_profiles), "restore_profiles": original_profiles}


def determine_processing_mode(profile_arg=None, profile_count_arg=None, profiles_arg=None):
    """Determine the processing mode based on configuration or command-line argument"""
    # If multiple profiles specified via command line, use them
    if profiles_arg:
        return use_specific_profiles(profiles_arg)

    # If single profile specified via command line, use it directly
    if profile_arg:
        return use_specific_profile(profile_arg)

    # If profile count specified via command line, use numbered mode with that count
    if profile_count_arg:
        count = min(profile_count_arg, len(PROMPT_PROFILES))  # Don't exceed available profiles
        print(f"📹 Using {count} profile{'s' if count > 1 else ''} (specified via --profile-count)")
        return {"mode": "numbered", "count": count}

    if PROCESSING_MODE == "ASK_USER":
        return ask_user_processing_mode()
    else:
        return {"mode": "numbered", "count": len(PROMPT_PROFILES)}


def ask_user_processing_mode() -> Dict:
    """Ask user to choose number of videos to create or select single profile"""
    global PROMPT_PROFILES

    print("\n" + "=" * 70)
    print("🎬 VIDEO PROCESSING SELECTION:")
    print("=" * 70)
    print("Legend: ✅=Ready ❌=Missing prompt 📤=Upload enabled ⏭️=Upload disabled")

    # Show numbered options based on available prompts
    profile_list = list(PROMPT_PROFILES.items())
    for i in range(len(profile_list)):
        count = i + 1
        print(f"{count}. Create {count} video{'s' if count > 1 else ''}")

        # Show which profiles will be used
        for j in range(count):
            profile_key, profile_info = profile_list[j]
            status = "✅" if profile_info["prompt_file"].exists() else "❌"
            upload_status = "📤" if profile_info.get('enable_upload', True) else "⏭️"
            print(f"   → {profile_info['name']} using {profile_info['default_voice']} voice {status} {upload_status}")
        print()

    # Add select custom profiles option
    custom_profiles_option = len(profile_list) + 1
    print(f"{custom_profiles_option}. Select Custom Profiles")
    print("   → Choose any combination of profiles")
    for profile_key, profile_info in profile_list:
        status = "✅" if profile_info["prompt_file"].exists() else "❌"
        upload_status = "📤" if profile_info.get('enable_upload', True) else "⏭️"
        print(f"   → {profile_info['name']} using {profile_info['default_voice']} voice {status} {upload_status}")
    print("=" * 70)

    while True:
        try:
            choice = input(f"Select option (1-{custom_profiles_option}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(profile_list):
                # Numbered mode: create N videos
                print(f"📹 Selected: Create {choice_num} video{'s' if choice_num > 1 else ''}")
                print("   Will process:")
                for i in range(choice_num):
                    profile_key, profile_info = profile_list[i]
                    print(f"   • {profile_info['name']} using {profile_info['default_voice']} voice")
                return {"mode": "numbered", "count": choice_num}

            elif choice_num == custom_profiles_option:
                # NEW: Custom multiple profile selection
                print("📹 Selected: Custom Profiles Mode")
                selected_profiles = display_and_select_custom_profiles()

                # Create temporary PROMPT_PROFILES with only selected profiles
                original_profiles = PROMPT_PROFILES.copy()
                PROMPT_PROFILES.clear()
                for profile_key, profile_info in selected_profiles:
                    PROMPT_PROFILES[profile_key] = profile_info

                print(f"🎯 Will create {len(selected_profiles)} video{'s' if len(selected_profiles) > 1 else ''} using:")
                for profile_key, profile_info in selected_profiles:
                    print(f"   • {profile_info['name']} using {profile_info['default_voice']} voice")

                # Return numbered mode with count=number of selected profiles
                return {"mode": "numbered", "count": len(selected_profiles), "restore_profiles": original_profiles}

            else:
                print(f"❌ Invalid choice. Please enter 1-{custom_profiles_option}.")

        except ValueError:
            print("❌ Invalid input. Please enter a number.")


def validate_prompt_profiles() -> bool:
    """Validate that all profile prompt files exist"""
    all_exist = True
    for profile_key, profile_info in PROMPT_PROFILES.items():
        if not profile_info["prompt_file"].exists():
            logger.error(f"❌ Profile prompt file not found: {profile_info['prompt_file']}")
            all_exist = False

    if all_exist:
        logger.info("✅ All profile prompt files validated:")
        for profile_key, profile_info in PROMPT_PROFILES.items():
            logger.info(f"   • {profile_info['name']}: {profile_info['prompt_file']}")

    return all_exist


def display_and_select_single_profile() -> tuple:
    """Display available profiles and let user select one - returns (key, profile)"""
    print("\n" + "=" * 60)
    print("🎯 CHOOSE YOUR PROFILE:")
    print("=" * 60)

    profile_keys = list(PROMPT_PROFILES.keys())
    for i, (profile_key, profile_info) in enumerate(PROMPT_PROFILES.items(), 1):
        status = "✅" if profile_info["prompt_file"].exists() else "❌ (FILE NOT FOUND)"
        print(f"{i}. {profile_info['name']} {status}")
        print(f"   Description: {profile_info['description']}")
        print(f"   Voice: {profile_info['default_voice']}")
        print()

    while True:
        try:
            choice = input(f"Select profile (1-{len(profile_keys)}) or press Enter for default: ").strip()
            if choice == "":
                for profile_key, profile_info in PROMPT_PROFILES.items():
                    if profile_info["prompt_file"].exists():
                        print(f"🎯 Using default profile: {profile_info['name']}")
                        return profile_key, profile_info
                print("❌ No valid profiles found! Please check your prompt files.")
                continue

            choice_num = int(choice)
            if 1 <= choice_num <= len(profile_keys):
                selected_key = profile_keys[choice_num - 1]
                selected_profile = PROMPT_PROFILES[selected_key]
                if selected_profile["prompt_file"].exists():
                    print(f"🎯 Selected profile: {selected_profile['name']}")
                    return selected_key, selected_profile
                else:
                    print(f"❌ Selected profile file not found: {selected_profile['prompt_file']}")
                    continue
            else:
                print(f"❌ Invalid choice. Please enter 1-{len(profile_keys)} or press Enter.")
        except ValueError:
            print("❌ Invalid input. Please enter a number or press Enter.")


def display_and_select_custom_profiles() -> List[tuple]:
    """Display available profiles and let user select multiple - returns list of (key, profile) tuples"""
    print("\n" + "=" * 60)
    print("🎯 CHOOSE YOUR PROFILES:")
    print("=" * 60)

    profile_keys = list(PROMPT_PROFILES.keys())
    profile_items = list(PROMPT_PROFILES.items())

    for i, (profile_key, profile_info) in enumerate(profile_items, 1):
        status = "✅" if profile_info["prompt_file"].exists() else "❌ (FILE NOT FOUND)"
        print(f"{i}. {profile_info['name']} {status}")
        print(f"   Description: {profile_info['description']}")
        print(f"   Voice: {profile_info['default_voice']}")
        print()

    print("Examples:")
    print("  • Enter '1,3,5' to select profiles 1, 3, and 5")
    print("  • Enter '2,4' to select profiles 2 and 4")
    print("  • Enter '1' to select only profile 1")
    print()

    while True:
        try:
            choice = input(f"Enter profile numbers (1-{len(profile_keys)}) separated by commas: ").strip()
            if not choice:
                print("❌ Please enter at least one profile number.")
                continue

            # Parse the input
            selected_numbers = []
            for num_str in choice.split(','):
                num_str = num_str.strip()
                if num_str.isdigit():
                    num = int(num_str)
                    if 1 <= num <= len(profile_keys):
                        selected_numbers.append(num)
                    else:
                        print(f"❌ Invalid profile number: {num}. Please use numbers 1-{len(profile_keys)}.")
                        selected_numbers = []
                        break
                else:
                    print(f"❌ Invalid input: '{num_str}'. Please enter numbers only.")
                    selected_numbers = []
                    break

            if not selected_numbers:
                continue

            # Remove duplicates while preserving order
            selected_numbers = list(dict.fromkeys(selected_numbers))

            # Get the selected profiles
            selected_profiles = []
            for num in selected_numbers:
                profile_key = profile_keys[num - 1]
                profile_info = PROMPT_PROFILES[profile_key]
                if profile_info["prompt_file"].exists():
                    selected_profiles.append((profile_key, profile_info))
                else:
                    print(f"❌ Profile {num} ({profile_info['name']}) file not found: {profile_info['prompt_file']}")
                    selected_profiles = []
                    break

            if selected_profiles:
                print(f"\n🎯 Selected {len(selected_profiles)} profile{'s' if len(selected_profiles) > 1 else ''}:")
                for profile_key, profile_info in selected_profiles:
                    print(f"   • {profile_info['name']} using {profile_info['default_voice']} voice")
                print()
                return selected_profiles

        except ValueError:
            print("❌ Invalid input. Please enter numbers separated by commas (e.g., '1,3,5').")


def get_voice_url_by_name(voice_name: str) -> str:
    """Get voice URL by voice name"""
    logger.info(f"🔍 Looking for voice: '{voice_name}'")

    for voice_key, voice_info in AVAILABLE_VOICES.items():
        if voice_info["name"] == voice_name:
            logger.info(f"✅ Found voice '{voice_name}': {voice_info['url']}")
            return voice_info["url"]

    # Fallback to first available voice if not found
    logger.warning(f"❌ Voice '{voice_name}' not found, using default ALEX")
    fallback_url = list(AVAILABLE_VOICES.values())[0]["url"]
    logger.warning(f"🔄 Using fallback voice URL: {fallback_url}")
    return fallback_url


def validate_step_output_exists(step_num: int, video_output_dir: Path, folder_name: str, is_multi_mode: bool = False,
                                selected_profiles: list = None) -> bool:
    """Check if the output files for a specific step actually exist"""
    try:
        if step_num == 0:
            # Step 0: Original video copy
            original_video_dir = video_output_dir / SUBDIR_ORIGINAL_VIDEO
            return original_video_dir.exists() and len(list(original_video_dir.glob("*.mp4"))) > 0

        elif step_num == 1:
            # Step 1: Diarization clips
            clips_dir = video_output_dir / SUBDIR_CLIPS_MAIN
            primary_clips = clips_dir / SUBDIR_PRIMARY_CLIPS
            inverse_clips = clips_dir / SUBDIR_INVERSE_CLIPS
            return (primary_clips.exists() and len(list(primary_clips.glob("*.mp4"))) > 0 and
                    inverse_clips.exists() and len(list(inverse_clips.glob("*.mp4"))) > 0)

        elif step_num == 2:
            # Step 2: Styled clips
            styled_clips_dir = video_output_dir / SUBDIR_STYLED_CLIPS
            if is_multi_mode and selected_profiles:
                # Check for profile-specific styled clips for the SELECTED profiles
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    profile_styled_dir = styled_clips_dir / f"{folder_name}_styled_{profile_suffix}"
                    if not profile_styled_dir.exists() or len(list(profile_styled_dir.glob("*.mp4"))) == 0:
                        return False  # This profile doesn't have styled clips yet
                return True  # All selected profiles have styled clips
            elif is_multi_mode:
                # General check for any profile-specific styled clips
                return styled_clips_dir.exists() and len(list(styled_clips_dir.glob("*_styled_*/*.mp4"))) > 0
            else:
                return styled_clips_dir.exists() and len(list(styled_clips_dir.glob("*.mp4"))) > 0

        elif step_num == 3:
            # Step 3: Transcripts
            transcripts_dir = video_output_dir / SUBDIR_TRANSCRIPTS
            transcript_file = transcripts_dir / f"{folder_name}_raw_transcript.txt"
            return transcript_file.exists() and transcript_file.stat().st_size > 100

        elif step_num == 4:
            # Step 4: AI Scripts
            ai_scripts_dir = video_output_dir / SUBDIR_AI_SCRIPTS
            if is_multi_mode and selected_profiles:
                # Check for profile-specific scripts for the selected profiles
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_suffix}.txt"
                    if not script_file.exists() or script_file.stat().st_size < 100:
                        return False
                return ai_scripts_dir.exists()
            elif is_multi_mode:
                # General check for any profile-specific scripts
                return ai_scripts_dir.exists() and len(list(ai_scripts_dir.glob("*_rewritten_script_*.txt"))) > 0
            else:
                return ai_scripts_dir.exists() and len(list(ai_scripts_dir.glob("*.txt"))) > 0

        elif step_num == 5:
            # Step 5: Voiceovers
            voiceovers_dir = video_output_dir / SUBDIR_VOICEOVERS
            if is_multi_mode and selected_profiles:
                # Check for profile-specific voiceovers for the selected profiles
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    profile_voiceover_dir = voiceovers_dir / f"{folder_name}_voiceover_{profile_suffix}"
                    if not profile_voiceover_dir.exists() or len(list(profile_voiceover_dir.glob("*.mp3"))) == 0:
                        return False
                return voiceovers_dir.exists()
            elif is_multi_mode:
                # General check for any profile-specific voiceovers
                return voiceovers_dir.exists() and len(list(voiceovers_dir.glob("**/*.mp3"))) > 0
            else:
                return voiceovers_dir.exists() and len(list(voiceovers_dir.glob("*.mp3"))) > 0

        elif step_num == 6:
            # Step 6: B-roll clips
            broll_dir = video_output_dir / SUBDIR_REARRANGED_BROLL_CLIPS
            return broll_dir.exists() and len(list(broll_dir.glob("*.mp4"))) > 0

        elif step_num == 7:
            # Step 7: Final videos
            final_videos_dir = video_output_dir / SUBDIR_FINAL_VIDEOS
            if is_multi_mode and selected_profiles:
                # Check for profile-specific final videos for the SELECTED profiles
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_suffix}"
                    if not profile_final_dir.exists() or len(list(profile_final_dir.glob("*.mp4"))) == 0:
                        return False  # This profile doesn't have final videos yet
                return True  # All selected profiles have final videos
            elif is_multi_mode:
                # General check for any profile-specific final videos
                return final_videos_dir.exists() and len(list(final_videos_dir.glob("**/*.mp4"))) > 0
            else:
                return final_videos_dir.exists() and len(list(final_videos_dir.glob("*.mp4"))) > 0

        elif step_num == 8:
            # Step 8: Ranked sequence
            ranked_dir = video_output_dir / SUBDIR_RANKED_SEQUENCE
            if is_multi_mode:
                # Check for profile-specific ranked videos
                return ranked_dir.exists() and len(list(ranked_dir.glob("*_ranked_*/*.mp4"))) > 0
            else:
                return ranked_dir.exists() and len(list(ranked_dir.glob("*.mp4"))) > 0

        elif step_num == 9:
            # Step 9: Combined videos
            combined_dir = video_output_dir / SUBDIR_NEW_STEP9
            if is_multi_mode:
                # Check for profile-specific combined videos
                return combined_dir.exists() and len(list(combined_dir.glob("*_combined_*/*.mp4"))) > 0
            else:
                return combined_dir.exists() and len(list(combined_dir.glob("*.mp4"))) > 0

        elif step_num == 10:
            # Step 10: YouTube uploads (was Step 11)
            youtube_dir = video_output_dir / SUBDIR_YOUTUBE_UPLOADS
            if is_multi_mode:
                # Check for upload results JSON files
                return youtube_dir.exists() and len(list(youtube_dir.glob("*_youtube_uploads.json"))) > 0
            else:
                return youtube_dir.exists() and len(list(youtube_dir.glob("*.json"))) > 0

        return False

    except Exception as e:
        logger.warning(f"⚠️ Error validating step {step_num} output: {e}")
        return False


def display_current_status(folder_name: str, output_base_dir: Path, video_path: Path, max_step: int = 10) -> Dict:
    """Display current status for a video and return the status data"""
    try:
        video_output_dir = output_base_dir / folder_name
        log_dir = video_output_dir / SUBDIR_LOGS
        # Create video-specific status file name to avoid conflicts between videos in same folder
        video_base_name = video_path.stem.replace(' ', '_').replace("'", "").replace('"', '')[
                          :50]  # Sanitize and truncate
        status_filename = f"pipeline_status_{video_base_name}.json"
        status_filepath = log_dir / status_filename

        if status_filepath.exists():
            current_status = load_video_status(status_filepath)
            last_completed = current_status.get(STATUS_KEY_LAST_COMPLETED_STEP, -1)
            logger.info(f"\n📋 CURRENT STATUS for '{folder_name}':")
            logger.info(f"   Last completed step: {last_completed}")
            if last_completed >= 0:
                logger.info(f"   Next step will be: {last_completed + 1}")
                # Show step progress
                completed_steps = [i for i in range(last_completed + 1)]
                remaining_steps = [i for i in range(last_completed + 1, max_step + 1)]
                logger.info(f"   ✅ Completed: {completed_steps}")
                logger.info(f"   ⏳ Remaining: {remaining_steps}")
                logger.info(f"   Status file: {status_filepath}")
            else:
                logger.info(f"   No steps completed yet")
            return current_status
        else:
            logger.info(f"\n📋 STATUS for '{folder_name}': Starting fresh (no previous runs)")
            return {
                STATUS_KEY_LAST_COMPLETED_STEP: -1,
                STATUS_KEY_STATE: "new_run",
                STATUS_KEY_TIMESTAMP: time.strftime("%Y-%m-%d %H:%M:%S")
            }
    except Exception as e:
        logger.warning(f"⚠️ Error loading status for {folder_name}: {e}")
        return {
            STATUS_KEY_LAST_COMPLETED_STEP: -1,
            STATUS_KEY_STATE: "new_run",
            STATUS_KEY_TIMESTAMP: time.strftime("%Y-%m-%d %H:%M:%S")
        }


def get_background_music_for_profile(profile_info: Dict) -> tuple:
    """
    Get background music path and audio levels for a profile.

    Returns:
        tuple: (background_music_path, voice_level, music_level)
    """
    if not ENABLE_BACKGROUND_MUSIC:
        return None, DEFAULT_VOICE_LEVEL, DEFAULT_MUSIC_LEVEL

    # Get profile-specific background music
    background_music = profile_info.get("background_music")
    voice_level = profile_info.get("voice_level", DEFAULT_VOICE_LEVEL)
    music_level = profile_info.get("music_level", DEFAULT_MUSIC_LEVEL)

    # Check if profile-specific music exists
    if background_music and Path(background_music).exists():
        logger.info(f"🎵 Using profile background music: {Path(background_music).name}")
        return background_music, voice_level, music_level

    # Try to find default music for this profile
    profile_suffix = profile_info.get("suffix", "DEFAULT")
    default_music_patterns = [
        f"{profile_suffix}-BG-MUSIC-1.mp3",
        f"{profile_suffix}-BG-MUSIC-1.MP3",
        f"{profile_suffix}-BG-MUSICE-1.MP3",  # Handle typo in existing files
        f"{profile_suffix}-BG-MUSIC.mp3",
        f"{profile_suffix}-BG-MUSIC.MP3",
        f"{profile_suffix}.mp3",
        f"{profile_suffix}.MP3",
        "music-background-1.MP3",  # Fallback to generic music
        "default-bg-music.mp3"
    ]

    for pattern in default_music_patterns:
        music_path = DEFAULT_BACKGROUND_MUSIC_FOLDER / pattern
        if music_path.exists():
            logger.info(f"🎵 Found default background music: {music_path.name}")
            return str(music_path), voice_level, music_level

    # No background music found
    logger.warning(f"⚠️ No background music found for profile {profile_info.get('name', 'Unknown')}")
    logger.warning(f"   Looked for: {', '.join(default_music_patterns)}")
    logger.warning(f"   In folder: {DEFAULT_BACKGROUND_MUSIC_FOLDER}")
    return None, voice_level, music_level


# ==============================================================================
# --- UTILITY FUNCTIONS ---
# ==============================================================================

def load_video_status(status_filepath: Path) -> Dict:
    """Load pipeline status for a specific video"""
    logger.info(f"🔎 Attempting to load status from: {status_filepath}")
    if status_filepath.exists():
        try:
            with open(status_filepath, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
                logger.info(f"✅ Loaded status: {status_data}")
                return status_data
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Corrupted status file {status_filepath}: {e}. Starting fresh.")
            status_data = {
                STATUS_KEY_LAST_COMPLETED_STEP: -1,
                STATUS_KEY_STATE: "new_run",
                STATUS_KEY_TIMESTAMP: time.strftime("%Y-%m-%d %H:%M:%S")
            }
            return status_data

    status_data = {
        STATUS_KEY_LAST_COMPLETED_STEP: -1,
        STATUS_KEY_STATE: "new_run",
        STATUS_KEY_TIMESTAMP: time.strftime("%Y-%m-%d %H:%M:%S")
    }
    logger.info(f"✨ No status file found. Initializing new status: {status_data}")
    return status_data


def save_video_status(status_filepath: Path, status_data: Dict):
    """Save pipeline status for a specific video"""
    status_filepath.parent.mkdir(parents=True, exist_ok=True)
    status_data[STATUS_KEY_TIMESTAMP] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(status_filepath, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)
        logger.info(f"💾 Saved status: {status_data}")
    except Exception as e:
        logger.error(f"❌ Error saving status to {status_filepath}: {e}")


def run_steps_in_parallel(step_tasks: List[Dict]) -> bool:
    """
    Run multiple pipeline steps in parallel using threading.

    Args:
        step_tasks: List of dicts with format:
            {
                'name': 'Step Name',
                'function': callable,
                'args': tuple of args
            }

    Returns:
        bool: True if ALL steps succeeded, False if any failed
    """
    import threading

    results = {}
    threads = []

    def run_step_with_result(step_name: str, step_func, step_args):
        """Wrapper to capture step result"""
        try:
            logger.info(f"🔄 Starting parallel execution: {step_name}")
            result = step_func(*step_args)
            results[step_name] = result
            if result:
                logger.info(f"✅ Parallel step completed: {step_name}")
            else:
                logger.error(f"❌ Parallel step failed: {step_name}")
        except Exception as e:
            logger.error(f"❌ Parallel step error ({step_name}): {e}")
            results[step_name] = False

    # Start all threads
    for task in step_tasks:
        thread = threading.Thread(
            target=run_step_with_result,
            args=(task['name'], task['function'], task['args'])
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check if all succeeded
    all_success = all(results.values())

    if all_success:
        logger.info(f"🎉 All {len(step_tasks)} parallel steps completed successfully!")
    else:
        failed_steps = [name for name, success in results.items() if not success]
        logger.error(f"❌ {len(failed_steps)} parallel step(s) failed: {', '.join(failed_steps)}")

    return all_success


# ==============================================================================
# --- BACKGROUND UPLOAD FUNCTIONS ---
# ==============================================================================

def start_background_upload(upload_func, upload_args: tuple, video_name: str) -> threading.Thread:
    """
    Start an upload in a background thread.
    This allows the main pipeline to continue to the next video folder
    while the upload is still in progress.

    Args:
        upload_func: The function to run (typically run_python_script for youtube upload)
        upload_args: Arguments to pass to the function
        video_name: Name of the video being uploaded (for logging)

    Returns:
        The background thread object
    """
    def upload_wrapper():
        try:
            logger.info(f"📤 [BACKGROUND] Starting upload for: {video_name}")
            result = upload_func(*upload_args)
            if result:
                logger.info(f"📤 [BACKGROUND] ✅ Upload completed for: {video_name}")
            else:
                logger.error(f"📤 [BACKGROUND] ❌ Upload failed for: {video_name}")
        except Exception as e:
            logger.error(f"📤 [BACKGROUND] ❌ Upload error for {video_name}: {e}")
        finally:
            # Remove this thread from the tracking list when done
            with _background_upload_lock:
                thread = threading.current_thread()
                if thread in _background_upload_threads:
                    _background_upload_threads.remove(thread)

    thread = threading.Thread(target=upload_wrapper, name=f"upload_{video_name}")
    thread.daemon = False  # Don't exit until upload completes

    with _background_upload_lock:
        _background_upload_threads.append(thread)

    thread.start()
    logger.info(f"📤 [BACKGROUND] Upload started in background - continuing to next video...")
    return thread


def wait_for_all_background_uploads():
    """
    Wait for all background uploads to complete.
    Call this at the end of processing all videos.
    """
    with _background_upload_lock:
        active_threads = list(_background_upload_threads)

    if not active_threads:
        logger.info("📤 No background uploads pending")
        return

    logger.info(f"📤 Waiting for {len(active_threads)} background upload(s) to complete...")

    for thread in active_threads:
        if thread.is_alive():
            logger.info(f"📤 Waiting for: {thread.name}")
            thread.join()

    logger.info("📤 ✅ All background uploads completed!")


def load_api_keys_from_json_file(filepath: Path) -> Dict[str, str]:
    """Load API keys from JSON file"""
    if not filepath.exists():
        logger.info(f"ℹ️ API keys file not found at {filepath}.")
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"✅ Loaded API keys from {filepath}")
        return data
    except Exception as e:
        logger.error(f"❌ Error loading API keys from {filepath}: {e}")
        return {}


def run_python_script(script_path: Path, args: List[str], cwd: Path = None, capture_output: bool = True, env: Dict = None) -> bool:
    """Run a Python script as subprocess"""
    cmd = [PYTHON_EXE, str(script_path)] + args
    logger.info(f"  Running: {' '.join(str(c) for c in cmd)}")

    # Prepare environment variables
    run_env = os.environ.copy()
    # Ensure UTF-8 encoding for Python subprocesses (fixes emoji/unicode on Windows)
    run_env["PYTHONIOENCODING"] = "utf-8"
    if env:
        run_env.update(env)

    try:
        process = subprocess.run(cmd, cwd=cwd, check=True, capture_output=capture_output, text=True, encoding='utf-8',
                                 errors='replace', env=run_env)
        if capture_output:
            if process.stdout:
                logger.info(f"  STDOUT for {script_path.name}:\n{process.stdout.strip()}")
            if process.stderr:
                logger.warning(f"  STDERR for {script_path.name}:\n{process.stderr.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"  ❌ Script failed: {script_path.name}")
        logger.error(f"  Return Code: {e.returncode}")
        if capture_output:
            logger.error(f"  STDOUT:\n{e.stdout.strip()}")
            logger.error(f"  STDERR:\n{e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"  ❌ Unexpected error running {script_path.name}: {e}")
        return False


def run_batch_script(script_path: Path, cwd: Path) -> bool:
    """Run a batch script as subprocess"""
    cmd = [str(script_path)]
    logger.info(f"  Running batch script: {' '.join(cmd)}")
    try:
        process = subprocess.run(cmd, cwd=cwd, shell=True, check=True, capture_output=True, text=True, encoding='utf-8',
                                 errors='replace')
        if process.stdout:
            logger.info(f"  STDOUT for {script_path.name}:\n{process.stdout.strip()}")
        if process.stderr:
            logger.warning(f"  STDERR for {script_path.name}:\n{process.stderr.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"  ❌ Batch script failed: {script_path.name}")
        logger.error(f"  Return Code: {e.returncode}")
        logger.error(f"  STDOUT:\n{e.stdout.strip()}")
        logger.error(f"  STDERR:\n{e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"  ❌ Unexpected error running {script_path.name}: {e}")
        return False


def create_temp_modified_script(original_script_path: Path, modifications: Dict[str, str], temp_dir: Path) -> Optional[
    Path]:
    """Create temporary copy of script with modifications"""
    temp_script_path = temp_dir / f"temp_{original_script_path.name}"

    if not original_script_path.is_file():
        logger.error(f"❌ Original script file not found: {original_script_path}")
        return None

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"❌ Failed to create temp directory {temp_dir}: {e}")
        return None

    try:
        with open(original_script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Debug: Show original content snippet and modifications
        logger.info(f"🔧 Applying {len(modifications)} modifications to {original_script_path.name}")

        modification_count = 0
        for pattern, replacement in modifications.items():
            matches = re.findall(pattern, content, flags=re.MULTILINE | re.DOTALL)
            if matches:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
                modification_count += 1
                logger.info(f"   ✅ Applied: {pattern[:50]}... -> {replacement[:50]}...")
            else:
                logger.warning(f"   ❌ No match: {pattern[:50]}...")

        logger.info(f"🎯 Successfully applied {modification_count}/{len(modifications)} modifications")

        with open(temp_script_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Generated temporary script: {temp_script_path}")
        return temp_script_path
    except Exception as e:
        logger.error(f"❌ Error creating temp script for {original_script_path.name}: {e}")
        return None


# ==============================================================================
# --- STEP IMPLEMENTATION FUNCTIONS ---
# ==============================================================================

def run_transcription_step(folder_name: str, primary_clips_dir: Path, transcripts_dir: Path,
                           temp_script_dir: Path) -> bool:
    """Run transcription step with dynamic configuration using CLI arguments"""
    # Smart skip: Check if transcript already exists
    final_transcript_path = transcripts_dir / f"{folder_name}_raw_transcript.txt"
    if final_transcript_path.exists() and final_transcript_path.stat().st_size > 100:  # Check file exists and has content
        logger.info(f"⚡ SMART SKIP: Found existing transcript: {final_transcript_path}")
        logger.info("   → Skipping transcription (delete transcript file to regenerate)")
        return True
    else:
        logger.info(f"📝 No existing transcript found, proceeding with transcription...")

    # Use CLI arguments instead of regex modifications (works with PyArmor obfuscated scripts)
    transcribe_args = [
        str(primary_clips_dir),
        "--output-folder", str(transcripts_dir),
        "--save-combined",
        "--combined-name", f"{folder_name}_raw_transcript.txt",
    ]

    success = run_python_script(VIDEO_TO_SCRIPT_SCRIPT, transcribe_args, capture_output=False)

    # Handle transcript file naming - fallback rename if needed
    final_transcript_path = transcripts_dir / f"{folder_name}_raw_transcript.txt"
    if not final_transcript_path.exists():
        for f in transcripts_dir.iterdir():
            if f.is_file() and f.suffix == ".txt" and f.stem == SUBDIR_PRIMARY_CLIPS:
                try:
                    shutil.move(f, final_transcript_path)
                    logger.info(f"Renamed transcript file from {f.name} to {final_transcript_path.name}")
                    break
                except Exception as e:
                    logger.error(f"Error renaming transcript: {e}")
                    return False

    return success


def run_ai_script_step_single(folder_name: str, transcripts_dir: Path, ai_scripts_dir: Path, prompt_profile: Dict,
                              api_key: str) -> bool:
    """Run AI script rewriting step for single mode"""
    final_transcript_path = transcripts_dir / f"{folder_name}_raw_transcript.txt"
    # Fix: Use consistent naming with profile suffix like in multi mode
    rewritten_script_path = ai_scripts_dir / f"{folder_name}_rewritten_script_{prompt_profile['suffix']}.txt"

    # Debug: Check if input files exist
    logger.info(f"🔍 Checking transcript file: {final_transcript_path}")
    if not final_transcript_path.exists():
        logger.error(f"❌ Transcript file not found: {final_transcript_path}")
        return False
    else:
        logger.info(f"✅ Transcript file found: {final_transcript_path}")

    logger.info(f"🔍 Checking prompt file: {prompt_profile['prompt_file']}")
    if not prompt_profile["prompt_file"].exists():
        logger.error(f"❌ Prompt file not found: {prompt_profile['prompt_file']}")
        return False
    else:
        logger.info(f"✅ Prompt file found: {prompt_profile['prompt_file']}")

    logger.info(f"📝 Will create rewritten script at: {rewritten_script_path}")

    # Build arguments for AI script
    ai_args = [
        "--input-file", str(final_transcript_path),
        "--output-file", str(rewritten_script_path),
        "--prompt-file", str(prompt_profile["prompt_file"]),
        "--provider", AI_PROVIDER,
        "--model-name", AI_REWRITE_MODEL_NAME,
    ]

    logger.info(f"🤖 Using AI Provider: {AI_PROVIDER.upper()}")
    logger.info(f"📊 Model: {AI_REWRITE_MODEL_NAME}")

    success = run_python_script(SCRIPT_WRITER_AI_SCRIPT, ai_args, capture_output=False)

    # Debug: Check if output file was created
    if success and rewritten_script_path.exists():
        logger.info(f"✅ AI script created successfully: {rewritten_script_path}")
    elif success:
        logger.warning(f"⚠️ Script reported success but output file not found: {rewritten_script_path}")
    else:
        logger.error(f"❌ AI script creation failed")

    return success


def run_ai_script_step_multi(folder_name: str, transcripts_dir: Path, ai_scripts_dir: Path, prompt_profile: Dict,
                             api_key: str) -> bool:
    """Run AI script rewriting step for numbered mode"""
    final_transcript_path = transcripts_dir / f"{folder_name}_raw_transcript.txt"
    rewritten_script_path = ai_scripts_dir / f"{folder_name}_rewritten_script_{prompt_profile['suffix']}.txt"

    # Build arguments for AI script
    ai_args = [
        "--input-file", str(final_transcript_path),
        "--output-file", str(rewritten_script_path),
        "--prompt-file", str(prompt_profile["prompt_file"]),
        "--provider", AI_PROVIDER,
        "--model-name", AI_REWRITE_MODEL_NAME,
    ]

    logger.info(f"🤖 Using AI Provider: {AI_PROVIDER.upper()} | Model: {AI_REWRITE_MODEL_NAME}")

    return run_python_script(SCRIPT_WRITER_AI_SCRIPT, ai_args, capture_output=False)


def run_voiceover_step_single(folder_name: str, ai_scripts_dir: Path, voiceovers_dir: Path, voice_url: str,
                              temp_script_dir: Path, prompt_profile: Dict) -> bool:
    """Run voiceover generation step for single mode"""
    # Fix: Use consistent naming with profile suffix like in multi mode
    script_path = ai_scripts_dir / f"{folder_name}_rewritten_script_{prompt_profile['suffix']}.txt"

    # Debug: Check if the script file exists
    logger.info(f"🔍 Looking for script file: {script_path}")
    if not script_path.exists():
        logger.error(f"❌ Script file not found: {script_path}")
        # List all files in the ai_scripts_dir to help debug
        if ai_scripts_dir.exists():
            script_files = list(ai_scripts_dir.glob("*.txt"))
            logger.info(f"📝 Available script files in {ai_scripts_dir}:")
            for f in script_files:
                logger.info(f"   - {f.name}")
        return False
    else:
        logger.info(f"✅ Script file found: {script_path}")

    # Create profile-specific voiceover directory like in numbered mode
    version_voiceover_dir = voiceovers_dir / f"{folder_name}_voiceover_{prompt_profile['suffix']}"
    version_voiceover_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Created voiceover directory: {version_voiceover_dir}")

    # Check if using API method FIRST (API doesn't need browser modifications)
    if is_using_api_method():
        logger.info("🚀 Using Fish Audio API for voiceover generation...")
        return run_voiceover_api_single(script_path, version_voiceover_dir, voice_url, prompt_profile['name'])

    # Browser mode: use importlib wrapper script (works with PyArmor obfuscated scripts)
    temp_script_dir.mkdir(parents=True, exist_ok=True)
    temp_script = temp_script_dir / f"temp_voiceover_{prompt_profile['suffix']}.py"

    temp_script_content = f'''# -*- coding: utf-8 -*-
import os
import sys
import importlib

sys.path.insert(0, r"{SCRIPT_DIR}")
voiceover_module = importlib.import_module("5_generate_voiceover")
voiceover_module.VOICEOVER_URL = "{voice_url}"

text_file_path = r"{script_path}"
output_folder = r"{version_voiceover_dir}"
num_tabs = {FISH_AUDIO_NUM_TABS}
profile_name = "{prompt_profile.get('name', 'Default')}"

voiceover_module.run_smart_parallel_with_voice_url(text_file_path, output_folder, num_tabs, voiceover_module.VOICEOVER_URL, profile_name)
'''

    try:
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(temp_script_content)
    except Exception as e:
        logger.error(f"❌ Failed to create temp voiceover script: {e}")
        return False

    return run_python_script(temp_script, [], capture_output=False)


def run_voiceover_step_multi(folder_name: str, ai_scripts_dir: Path, voiceovers_dir: Path, prompt_profile: Dict,
                             temp_script_dir: Path) -> bool:
    """Run voiceover generation step for numbered mode"""
    script_path = ai_scripts_dir / f"{folder_name}_rewritten_script_{prompt_profile['suffix']}.txt"
    voice_url = get_voice_url_by_name(prompt_profile["default_voice"])

    # Debug logging
    logger.info(f"🎤 Setting up voiceover for profile: {prompt_profile['name']}")
    logger.info(f"🔊 Profile default voice: {prompt_profile['default_voice']}")
    logger.info(f"🌐 Voice URL to use: {voice_url}")

    version_voiceover_dir = voiceovers_dir / f"{folder_name}_voiceover_{prompt_profile['suffix']}"
    version_voiceover_dir.mkdir(parents=True, exist_ok=True)

    # Check if using API method FIRST (API doesn't need browser modifications)
    if is_using_api_method():
        logger.info("🚀 Using Fish Audio API for voiceover generation...")
        return run_voiceover_api_single(script_path, version_voiceover_dir, voice_url, prompt_profile['name'])

    # Browser mode: use importlib wrapper script (works with PyArmor obfuscated scripts)
    voiceover_temp_dir = temp_script_dir / f"voiceover_{prompt_profile['suffix']}"
    voiceover_temp_dir.mkdir(parents=True, exist_ok=True)
    temp_script = voiceover_temp_dir / f"temp_voiceover_{prompt_profile['suffix']}.py"

    temp_script_content = f'''# -*- coding: utf-8 -*-
import os
import sys
import importlib

sys.path.insert(0, r"{SCRIPT_DIR}")
voiceover_module = importlib.import_module("5_generate_voiceover")
voiceover_module.VOICEOVER_URL = "{voice_url}"

text_file_path = r"{script_path}"
output_folder = r"{version_voiceover_dir}"
num_tabs = {FISH_AUDIO_NUM_TABS}
profile_name = "{prompt_profile.get('name', 'Default')}"

voiceover_module.run_smart_parallel_with_voice_url(text_file_path, output_folder, num_tabs, voiceover_module.VOICEOVER_URL, profile_name)
'''

    try:
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(temp_script_content)
    except Exception as e:
        logger.error(f"❌ Failed to create temp voiceover script: {e}")
        return False

    # Debug logging
    logger.info(f"📄 Created temp voiceover script: {temp_script}")
    logger.info(f"📝 Script file input: {script_path}")
    logger.info(f"📁 Output directory: {version_voiceover_dir}")
    logger.info(f"🔢 Number of tabs: {FISH_AUDIO_NUM_TABS}")

    # Check if script file exists before running
    if not script_path.exists():
        logger.error(f"❌ Script file not found: {script_path}")
        return False

    # Run the voiceover script
    success = run_python_script(temp_script, [], capture_output=False)

    # Debug: Check if voiceover files were actually created
    if success:
        if version_voiceover_dir.exists():
            voiceover_files = list(version_voiceover_dir.glob("*.wav")) + list(version_voiceover_dir.glob("*.mp3"))
            logger.info(f"🎵 Found {len(voiceover_files)} voiceover files in {version_voiceover_dir}")
            if len(voiceover_files) > 0:
                for f in voiceover_files[:3]:  # Show first 3 files
                    logger.info(f"   • {f.name}")
                if len(voiceover_files) > 3:
                    logger.info(f"   • ... and {len(voiceover_files) - 3} more files")
            else:
                logger.warning(f"⚠️ No voiceover files found in {version_voiceover_dir}")
        else:
            logger.error(f"❌ Voiceover directory was not created: {version_voiceover_dir}")

    return success


def is_using_api_method():
    """Check if user selected API method in settings"""
    config_path = get_user_data_dir() / "config.json"
    logger.info(f"🔍 Checking voiceover method from: {config_path}")
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                method = config.get("voiceover_settings", {}).get("method", "Fish Audio (Browser)")
                is_api = "API" in method.upper()
                logger.info(f"📋 Voiceover method: '{method}' → API mode: {is_api}")
                return is_api
        except Exception as e:
            logger.error(f"❌ Error reading config for voiceover method: {e}")
    else:
        logger.warning(f"⚠️ Config file not found: {config_path}")
    return False


def run_voiceover_api_single(script_file: Path, output_folder: Path, voice_url: str, profile_name: str) -> bool:
    """Run voiceover generation using Fish Audio API for a single profile"""
    api_script = SCRIPT_DIR / "5_generate_voiceover_api.py"

    if not api_script.exists():
        logger.error(f"❌ API voiceover script not found: {api_script}")
        return False

    logger.info(f"🚀 Running API voiceover for {profile_name} (paragraph mode)...")
    success = run_python_script(api_script, [
        "--script", str(script_file),
        "--output", str(output_folder),
        "--voice", voice_url
    ], capture_output=False)

    if success:
        logger.info(f"✅ Generated {profile_name} voiceover via API")
    else:
        logger.error(f"❌ Failed to generate {profile_name} voiceover via API")

    return success


def run_voiceover_api_parallel(folder_name: str, ai_scripts_dir: Path, voiceovers_dir: Path,
                               selected_profiles: List, temp_script_dir: Path) -> bool:
    """Run voiceover generation using Fish Audio API (parallel processing - like browser version)

    Processes script file by splitting into paragraphs (by triple newline) and
    generates paragraph_001.mp3, paragraph_002.mp3, etc. - same as browser method.
    """
    all_success = True

    for profile_key, profile_info in selected_profiles:
        logger.info(f"🔍 Looking for voice: '{profile_info['default_voice']}'")

        # Get voice URL for this profile
        voice_url = get_voice_url_by_name(profile_info["default_voice"])
        if not voice_url:
            logger.error(f"❌ Voice '{profile_info['default_voice']}' not found!")
            all_success = False
            continue

        logger.info(f"✅ Found voice '{profile_info['default_voice']}': {voice_url}")

        # Find the rewritten script file for this profile (same naming as browser version)
        script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_info['suffix']}.txt"

        if not script_file.exists():
            logger.error(f"❌ Script file not found: {script_file}")
            all_success = False
            continue

        # Output folder for voiceovers
        output_folder = voiceovers_dir / f"{folder_name}_voiceover_{profile_info['suffix']}"
        output_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"📄 Script: {script_file}")
        logger.info(f"📁 Output: {output_folder}")

        # Run API script with --script parameter (paragraph mode - like browser)
        api_script = SCRIPT_DIR / "5_generate_voiceover_api.py"

        logger.info(f"🚀 Running API voiceover for {profile_info['name']} (paragraph mode)...")
        success = run_python_script(api_script, [
            "--script", str(script_file),  # Use --script for paragraph mode
            "--output", str(output_folder),
            "--voice", voice_url
        ], capture_output=False)

        if success:
            logger.info(f"✅ Generated {profile_info['name']} voiceover via API")
        else:
            logger.error(f"❌ Failed to generate {profile_info['name']} voiceover via API")
            all_success = False

    return all_success


def run_voiceover_step_multi_window(folder_name: str, ai_scripts_dir: Path, voiceovers_dir: Path,
                                    selected_profiles: List, temp_script_dir: Path) -> bool:
    """Run voiceover generation using multi-window parallel processing"""

    # Check if using API method FIRST (API doesn't need browser multi-window)
    if is_using_api_method():
        logger.info("🚀 Using Fish Audio API for voiceover generation...")
        return run_voiceover_api_parallel(folder_name, ai_scripts_dir, voiceovers_dir, selected_profiles, temp_script_dir)

    # Browser mode: check if multi-window is enabled
    if not USE_MULTI_WINDOW_VOICEOVER or not ENABLE_PROFILE_PARALLEL_PROCESSING:
        # Fallback to sequential processing
        logger.info("🧠 Using sequential browser voiceover processing...")
        all_success = True
        for profile_key, profile_info in selected_profiles:
            success = run_voiceover_step_multi(folder_name, ai_scripts_dir, voiceovers_dir, profile_info,
                                               temp_script_dir)
            if not success:
                all_success = False
                logger.error(f"   ❌ Failed to generate {profile_info['name']} voiceover")
            else:
                logger.info(f"   ✅ Generated {profile_info['name']} voiceover")
        return all_success

    logger.info("🚀 Using multi-window browser parallel voiceover processing...")

    # Prepare script folder info for multi-window function
    script_folders = []
    for profile_key, profile_info in selected_profiles:
        script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_info['suffix']}.txt"
        output_folder = voiceovers_dir / f"{folder_name}_voiceover_{profile_info['suffix']}"
        output_folder.mkdir(parents=True, exist_ok=True)

        # Get profile-specific voice URL
        voice_url = get_voice_url_by_name(profile_info["default_voice"])

        script_folders.append({
            'profile': profile_info['suffix'],
            'script_folder': str(ai_scripts_dir),
            'output_folder': str(output_folder),
            'voice_url': voice_url  # Add voice URL for each profile
        })
        logger.info(f"📋 Prepared {profile_info['name']} for parallel processing")
        logger.info(f"🔊 Profile voice: {profile_info['default_voice']} → {voice_url}")

    # Create a special temp script that calls the multi-window function
    multi_window_script_content = f'''
import sys
import os
import importlib

# Add script directory to path
sys.path.insert(0, r"{SCRIPT_DIR}")

# Import the voiceover script module
voiceover_module = importlib.import_module(os.path.splitext(os.path.basename(r"{get_voiceover_script()}"))[0])

# Script folders configuration from orchestrator
script_folders = {script_folders}

# Multi-window settings from orchestrator
num_tabs_per_window = {repr(TABS_PER_WINDOW)}

# Run multi-window parallel processing
voiceover_module.run_multi_window_from_orchestrator(script_folders, num_tabs_per_window)
'''

    # Save the multi-window script
    multi_window_script_path = temp_script_dir / "multi_window_voiceover.py"
    try:
        with open(multi_window_script_path, 'w', encoding='utf-8') as f:
            f.write(multi_window_script_content)

        logger.info(f"🎯 Starting multi-window processing for {len(selected_profiles)} profiles...")
        logger.info(f"🖥️ Browser windows: {len(selected_profiles)}")
        logger.info(f"🔢 Tabs per window: {TABS_PER_WINDOW}")
        logger.info(f"⚡ Total parallel tabs: {len(selected_profiles) * TABS_PER_WINDOW}")

        # Run the multi-window script
        success = run_python_script(multi_window_script_path, [], capture_output=False)

        if success:
            logger.info(f"✅ Multi-window voiceover processing completed successfully")
        else:
            logger.error(f"❌ Multi-window voiceover processing failed")

        return success

    except Exception as e:
        logger.error(f"❌ Failed to create multi-window script: {e}")
        return False


def run_broll_step(primary_clips_dir: Path, rearranged_broll_clips_dir: Path, voiceovers_dir: Path = None, per_folder_broll: Path = None) -> bool:
    """Run B-roll clips rearrangement step using direct Python implementation

    Priority order for B-roll source:
    1. per_folder_broll (if provided - from UI per-folder custom B-roll)
    2. Global B-roll (if enabled in Quick Options)
    3. Legacy custom B-roll from config
    4. Voiceover clips (use voiceover clips)
    5. Default: primary_clips_dir
    """

    # Track which source type is being used for trimming logic
    is_using_voiceover_source = False

    # RE-READ config fresh each time (so UI changes take effect immediately)
    fresh_config = load_configuration()
    quick_opts = fresh_config.get("quick_options", {})

    # Read from quick_options (what UI saves) - this is the source of truth
    use_global_broll = quick_opts.get("use_global_broll", False)
    global_broll_folder_raw = quick_opts.get("global_broll_folder", "")
    global_broll_folder = resolve_path(global_broll_folder_raw) if global_broll_folder_raw else None

    trim_seconds = fresh_config.get("processing_settings", {}).get("trim_voiceover_clips_seconds", 2.0)

    # DEBUG: Log what we read from config
    logger.info(f"📋 B-roll settings from config:")
    logger.info(f"   use_global_broll = {use_global_broll}")
    logger.info(f"   global_broll_folder = '{global_broll_folder_raw}'")

    # Determine source directory based on settings
    # Priority 1: Per-folder custom B-roll (from UI - highest priority)
    if per_folder_broll and Path(per_folder_broll).exists():
        source_dir = Path(per_folder_broll)
        logger.info(f"🎬 Starting B-roll processing using PER-FOLDER CUSTOM B-roll from {source_dir}")

    # Priority 2: Global B-roll checkbox checked = use B-roll folder
    elif use_global_broll:
        if global_broll_folder and global_broll_folder.exists():
            source_dir = global_broll_folder
            logger.info(f"🎬 Starting B-roll processing using GLOBAL B-ROLL folder from {source_dir}")
        else:
            logger.error(f"❌ Global B-roll folder not found: '{global_broll_folder_raw}'")
            logger.warning(f"⚠️ Please set a valid B-roll folder path in UI")
            source_dir = primary_clips_dir
            logger.info(f"🎬 Falling back to PRIMARY clips from {source_dir}")

    # Priority 3: Checkbox unchecked = use voiceover clips
    else:
        clips_base_dir = voiceovers_dir.parent / "1_clips" / "voiceover"
        if clips_base_dir.exists():
            test_files = list(clips_base_dir.glob("*.mp4"))
            if test_files:
                source_dir = clips_base_dir
                is_using_voiceover_source = True
                logger.info(f"🎬 Starting B-roll processing using VOICEOVER VIDEO clips from {source_dir}")
                logger.info(f"✂️ Trimming: {trim_seconds}s from start and end of each clip")
            else:
                logger.warning(f"⚠️ Voiceover directory contains no video files, falling back to primary clips")
                source_dir = primary_clips_dir
                logger.info(f"🎬 Starting B-roll processing using PRIMARY clips from {source_dir}")
        else:
            source_dir = primary_clips_dir
            logger.warning(f"⚠️ Voiceover video clips directory not found, falling back to primary clips")
            logger.info(f"🎬 Starting B-roll processing using PRIMARY clips from {source_dir}")

    # Ensure destination directory exists
    rearranged_broll_clips_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📂 Destination directory: {rearranged_broll_clips_dir}")

    # Get all video files in the source directory
    all_files = list(os.listdir(source_dir))
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv']
    video_files = [os.path.join(source_dir, f) for f in all_files if
                   any(f.lower().endswith(ext) for ext in video_extensions)]

    if is_using_voiceover_source:
        logger.info(f"📁 Found {len(video_files)} VIDEO files from Step 1 voiceover clips")
    else:
        logger.info(f"📁 Found {len(video_files)} video files in primary clips")

    if not video_files:
        logger.error("❌ No video/audio files found to process!")
        return False

    # Create temporary directory for processing
    temp_processing_dir = rearranged_broll_clips_dir / "temp_processing"
    temp_processing_dir.mkdir(exist_ok=True)

    # Change to temp processing directory for FFmpeg operations
    original_cwd = os.getcwd()
    os.chdir(temp_processing_dir)

    try:
        # STEP 1: Process files (with trimming if needed) and create file list
        logger.info("🔍 Processing files and creating file list for FFmpeg...")
        file_list_path = temp_processing_dir / "file_list.txt"
        processed_files = []

        # Process each file (trim if using voiceover clips)
        for i, video_file in enumerate(video_files):
            input_file = Path(video_file)

            if is_using_voiceover_source and TRIM_VOICEOVER_CLIPS_SECONDS > 0:
                # Trim voiceover clips
                output_file = temp_processing_dir / f"trimmed_{i:03d}{input_file.suffix}"

                logger.info(f"✂️ Trimming {input_file.name} ({TRIM_VOICEOVER_CLIPS_SECONDS}s from each end)...")

                # Get file duration first
                duration_cmd = [
                    "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(input_file)
                ]
                try:
                    duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
                    duration_info = json.loads(duration_result.stdout)
                    total_duration = float(duration_info['format']['duration'])

                    # Calculate trimmed duration
                    trimmed_duration = total_duration - (2 * TRIM_VOICEOVER_CLIPS_SECONDS)

                    if trimmed_duration <= 0.5:
                        logger.warning(
                            f"⚠️ Skipping {input_file.name} - too short after trimming ({trimmed_duration:.1f}s)")
                        continue

                    # Trim the file - use -ss before -i for faster seeking
                    # For short clips (< 3s), always re-encode to avoid keyframe issues
                    use_copy_first = trimmed_duration >= 3.0

                    # Stream copy (fast but may have keyframe issues)
                    trim_cmd_copy = [
                        "ffmpeg", "-y",
                        "-ss", str(TRIM_VOICEOVER_CLIPS_SECONDS),
                        "-i", str(input_file),
                        "-t", str(trimmed_duration),
                        "-c", "copy",
                        "-avoid_negative_ts", "make_zero",
                        str(output_file), "-v", "quiet"
                    ]

                    # Re-encode (slower but reliable, handles keyframe issues)
                    trim_cmd_encode = [
                        "ffmpeg", "-y",
                        "-ss", str(TRIM_VOICEOVER_CLIPS_SECONDS),
                        "-i", str(input_file),
                        "-t", str(trimmed_duration),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-c:a", "aac", "-b:a", "128k",
                        "-pix_fmt", "yuv420p",
                        "-avoid_negative_ts", "make_zero",
                        str(output_file), "-v", "quiet"
                    ]

                    # For short clips, skip copy and go straight to encode
                    trim_attempts = [trim_cmd_copy, trim_cmd_encode] if use_copy_first else [trim_cmd_encode]

                    trim_success = False
                    for trim_cmd in trim_attempts:
                        try:
                            subprocess.run(trim_cmd, check=True, capture_output=True)
                            # Verify the output has video
                            verify_cmd = ["ffprobe", "-v", "quiet", "-select_streams", "v", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(output_file)]
                            verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
                            if "video" in verify_result.stdout:
                                trim_success = True
                                break
                            else:
                                logger.warning(f"⚠️ Trimmed file has no video, trying re-encode...")
                                output_file.unlink(missing_ok=True)
                        except subprocess.CalledProcessError:
                            continue

                    if trim_success:
                        processed_files.append(str(output_file))
                        logger.info(f"✅ Trimmed: {input_file.name} → {output_file.name} ({trimmed_duration:.1f}s)")
                    else:
                        logger.warning(f"⚠️ Could not trim {input_file.name}, using original")
                        processed_files.append(str(input_file))

                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Failed to trim {input_file.name}: {e}")
                    # Use original file if trimming fails
                    processed_files.append(str(input_file))
                except Exception as e:
                    logger.error(f"❌ Error processing {input_file.name}: {e}")
                    processed_files.append(str(input_file))
            else:
                # Use original files without trimming
                processed_files.append(str(input_file))

        if not processed_files:
            logger.error("❌ No files available after processing!")
            return False

        # Create file list for concatenation
        with open(file_list_path, 'w') as f:
            for processed_file in processed_files:
                f.write(f"file '{processed_file}'\n")

        logger.info(f"📝 Created file list with {len(processed_files)} processed files")

        # STEP 2: Merge all processed files into one
        logger.info(f"🎬 Merging {len(processed_files)} processed files...")
        merged_video_path = temp_processing_dir / "merged_video.mp4"

        # First try: stream copy (fast)
        merge_cmd_copy = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(file_list_path),
            "-c", "copy", str(merged_video_path), "-v", "quiet", "-stats", "-y"
        ]

        # Fallback: re-encode to ensure compatibility (handles mixed formats)
        merge_cmd_encode = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(file_list_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            str(merged_video_path), "-v", "quiet", "-stats", "-y"
        ]

        merge_success = False
        for merge_cmd in [merge_cmd_copy, merge_cmd_encode]:
            try:
                result = subprocess.run(merge_cmd, capture_output=True, text=True, check=True)

                # Verify the merged file has video streams
                verify_cmd = ["ffprobe", "-v", "quiet", "-select_streams", "v",
                              "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                              str(merged_video_path)]
                verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)

                if "video" in verify_result.stdout:
                    merge_success = True
                    logger.info("✅ Files merged successfully!")
                    break
                else:
                    logger.warning("⚠️ Merged file has no video with copy mode, trying re-encode...")
                    merged_video_path.unlink(missing_ok=True)
            except subprocess.CalledProcessError as e:
                logger.warning(f"⚠️ Merge attempt failed: {e.stderr[:200] if e.stderr else 'unknown error'}")
                merged_video_path.unlink(missing_ok=True)
                continue

        if not merge_success:
            logger.error("❌ Failed to merge files after all attempts!")
            return False

        # Clean up file list
        file_list_path.unlink()

        # Check if merge was successful
        if not merged_video_path.exists():
            logger.error("❌ Merged video was not created!")
            return False

        # Debug: Check merged video properties
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(merged_video_path)
        ]
        try:
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            probe_info = json.loads(probe_result.stdout)
            streams = probe_info.get('streams', [])
            video_streams = [s for s in streams if s.get('codec_type') == 'video']
            audio_streams = [s for s in streams if s.get('codec_type') == 'audio']

            logger.info(f"🔍 Merged video analysis:")
            logger.info(f"   Video streams: {len(video_streams)}")
            logger.info(f"   Audio streams: {len(audio_streams)}")
            logger.info(f"   Total duration: {probe_info.get('format', {}).get('duration', 'unknown')}s")

            if len(video_streams) == 0:
                logger.error("❌ Merged video has no video streams! Cannot create video segments.")
                return False

        except Exception as e:
            logger.warning(f"⚠️ Could not analyze merged video: {e}")
            # Continue anyway, maybe segmentation will work

        # STEP 3: Create 6-second clips from merged file
        logger.info("✂️ Creating 6-second clips...")

        # Change to final output directory for clip creation
        os.chdir(rearranged_broll_clips_dir)

        # Try different segmentation approaches based on success

        # First try: Hardware accelerated (NVENC) - only if video streams exist
        segment_cmd_nvenc = [
            "ffmpeg", "-y", "-threads", "0", "-hwaccel", "cuda",
            "-i", str(merged_video_path),
            "-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "5M",
            "-sc_threshold", "0", "-forced-idr", "1", "-an",
            "-f", "segment", "-segment_time", "6", "-segment_format", "mp4",
            "-reset_timestamps", "1",
            "-force_key_frames", "expr:gte(t,n_forced*6)",
            "clip_%03d.mp4", "-v", "error"
        ]

        # Second try: Software encoding fallback
        segment_cmd_sw = [
            "ffmpeg", "-y", "-threads", "0",
            "-i", str(merged_video_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an", "-f", "segment", "-segment_time", "6",
            "-segment_format", "mp4", "-reset_timestamps", "1",
            "clip_%03d.mp4", "-v", "error"
        ]

        # Third try: Stream copy (fastest)
        segment_cmd_copy = [
            "ffmpeg", "-y", "-i", str(merged_video_path),
            "-c", "copy", "-f", "segment", "-segment_time", "6",
            "-segment_format", "mp4", "-reset_timestamps", "1",
            "clip_%03d.mp4", "-v", "error"
        ]

        success = False
        for attempt, (cmd, name) in enumerate([
            (segment_cmd_nvenc, "Hardware NVENC"),
            (segment_cmd_sw, "Software x264"),
            (segment_cmd_copy, "Stream Copy")
        ], 1):
            try:
                logger.info(f"🔄 Attempt {attempt}: {name} segmentation...")
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info("✅ 6-second B-roll clips created successfully!")
                success = True
                break
            except subprocess.CalledProcessError as e:
                logger.warning(f"⚠️ {name} failed: {e}")
                if e.stderr:
                    logger.warning(f"FFmpeg stderr: {e.stderr}")
                continue

        if not success:
            logger.error("❌ All segmentation methods failed!")
            return False

        # STEP 4: Rename clips with random names (clips are already in destination)
        logger.info("🔄 Renaming clips with random names...")

        import random
        clip_files = [f for f in os.listdir(rearranged_broll_clips_dir) if f.startswith('clip_') and f.endswith('.mp4')]
        moved_count = 0

        for clip_file in clip_files:
            try:
                # Generate random name
                random_name = f"{random.randint(10000, 99999)}{random.randint(10000, 99999)}.mp4"

                # Rename in destination directory
                source_path = rearranged_broll_clips_dir / clip_file
                dest_path = rearranged_broll_clips_dir / random_name

                shutil.move(str(source_path), str(dest_path))
                logger.info(f"✅ Renamed: {clip_file} → {random_name}")
                moved_count += 1

            except Exception as e:
                logger.error(f"❌ Failed to rename {clip_file}: {e}")

        # STEP 5: Clean up temporary files
        logger.info("🗑️ Cleaning up temporary files...")

        # Clean up temp processing directory
        try:
            shutil.rmtree(temp_processing_dir)
            logger.info("✅ Cleaned up temporary processing directory")
        except Exception as e:
            logger.warning(f"⚠️ Failed to clean up temp directory: {e}")

        logger.info(f"🎉 Successfully processed {moved_count} clips!")
        logger.info(f"📂 Clips saved to: {rearranged_broll_clips_dir}")

        return moved_count > 0

    except Exception as e:
        logger.error(f"❌ Unexpected error during processing: {e}")
        return False

    finally:
        # Always return to original directory
        os.chdir(original_cwd)


def run_assembly_step_single(folder_name: str, voiceovers_dir: Path, clips_dir: Path, final_videos_dir: Path,
                             log_dir: Path, prompt_profile: Dict) -> bool:
    """Run final video assembly for single mode"""
    cache_file = log_dir / f"{folder_name}_assemble_cache_{prompt_profile['suffix']}.json"

    # Create profile-specific directories like in numbered mode
    version_voiceover_dir = voiceovers_dir / f"{folder_name}_voiceover_{prompt_profile['suffix']}"
    version_final_dir = final_videos_dir / f"{folder_name}_final_{prompt_profile['suffix']}"
    version_final_dir.mkdir(parents=True, exist_ok=True)

    # Get channel name from profile
    channel_name = prompt_profile.get('name', prompt_profile.get('suffix', 'Unknown Channel'))

    assembly_args = [
        "--voiceovers", str(version_voiceover_dir),
        "--clips", str(clips_dir),
        "--output", str(version_final_dir),
        "--cache-file", str(cache_file),
        "--channel-name", channel_name,
    ]

    if not ASSEMBLE_VIDEO_USE_FAST_COPY:
        assembly_args.append("--quality")

    # Pass logo configuration as environment variable
    env_vars = {"ENABLE_LOGO_FEATURE": "true" if ENABLE_LOGO_IN_STEP7 else "false"}

    return run_python_script(CLIPS_PLUS_VOICEOVER_SCRIPT, assembly_args, capture_output=True, env=env_vars)


def run_assembly_step_multi(folder_name: str, voiceovers_dir: Path, clips_dir: Path, final_videos_dir: Path,
                            log_dir: Path, prompt_profile: Dict) -> bool:
    """Run final video assembly for numbered mode"""
    cache_file = log_dir / f"{folder_name}_assemble_cache_{prompt_profile['suffix']}.json"

    version_voiceover_dir = voiceovers_dir / f"{folder_name}_voiceover_{prompt_profile['suffix']}"
    version_final_dir = final_videos_dir / f"{folder_name}_final_{prompt_profile['suffix']}"
    version_final_dir.mkdir(parents=True, exist_ok=True)

    # Get channel name from profile
    channel_name = prompt_profile.get('name', prompt_profile.get('suffix', 'Unknown Channel'))

    assembly_args = [
        "--voiceovers", str(version_voiceover_dir),
        "--clips", str(clips_dir),
        "--output", str(version_final_dir),
        "--cache-file", str(cache_file),
        "--channel-name", channel_name,
    ]

    if not ASSEMBLE_VIDEO_USE_FAST_COPY:
        assembly_args.append("--quality")

    # Pass logo configuration as environment variable
    env_vars = {"ENABLE_LOGO_FEATURE": "true" if ENABLE_LOGO_IN_STEP7 else "false"}

    return run_python_script(CLIPS_PLUS_VOICEOVER_SCRIPT, assembly_args, capture_output=True, env=env_vars)


def run_audio_cleaning_step_single(folder_name: str, inverse_clips_dir: Path, cleaned_audio_dir: Path,
                                   prompt_profile: Dict) -> bool:
    """Run audio cleaning step for single mode - removes background music, keeps only voice"""
    from pathlib import Path
    import subprocess
    import logging
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    logger = logging.getLogger(__name__)
    cleaned_audio_dir.mkdir(parents=True, exist_ok=True)

    # Find interview audio/video files (check multiple patterns)
    interview_files = list(inverse_clips_dir.glob(f"{folder_name}_interview_*.wav"))
    if not interview_files:
        interview_files = list(inverse_clips_dir.glob(f"{folder_name}_interview_*.mp3"))
    if not interview_files:
        # Look for "others" pattern (common from diarization step)
        interview_files = list(inverse_clips_dir.glob(f"{folder_name}_others_*.mp4"))
    if not interview_files:
        # Look for any interview files
        interview_files = list(inverse_clips_dir.glob(f"*interview*.wav"))
        if not interview_files:
            interview_files = list(inverse_clips_dir.glob(f"*interview*.mp3"))
        if not interview_files:
            interview_files = list(inverse_clips_dir.glob(f"*interview*.mp4"))

    if not interview_files:
        logger.warning(f"No interview audio/video files found in {inverse_clips_dir}")
        return True  # Not a failure - just no files to process

    logger.info(f"🎵⚡ GPU-accelerated cleaning of {len(interview_files)} interview audio files...")

    def clean_single_audio_file(audio_file: Path) -> tuple[bool, str]:
        """Clean a single audio file with GPU acceleration and fallback"""
        # Create video file with cleaned audio (for ranking step compatibility)
        output_name = f"cleaned_{audio_file.stem}.mp4"
        output_file = cleaned_audio_dir / output_name

        # GPU-accelerated command with CUDA (fastest)
        cmd_gpu = [
            "ffmpeg", "-y", "-threads", "0", "-hwaccel", "cuda",
            "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",  # Black video
            "-i", str(audio_file),  # Input audio/video file
            "-af", "aresample=22050,volume=1.2",
            "-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "1M",  # GPU video encoding
            "-c:a", "aac", "-b:a", "128k", "-ar", "22050", "-ac", "1",
            "-shortest",  # Match duration to shortest input
            str(output_file)
        ]

        # CPU fallback command (if GPU fails)
        cmd_cpu = [
            "ffmpeg", "-y", "-threads", "0",
            "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",  # Black video
            "-i", str(audio_file),  # Input audio/video file
            "-af", "aresample=22050,volume=1.2",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",  # CPU video encoding
            "-c:a", "aac", "-b:a", "128k", "-ar", "22050", "-ac", "1",
            "-shortest",  # Match duration to shortest input
            str(output_file)
        ]

        # Try GPU first, then CPU fallback
        for attempt, (cmd, method) in enumerate([
            (cmd_gpu, "GPU CUDA"),
            (cmd_cpu, "CPU")
        ], 1):
            try:
                start_time = time.time()
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
                process_time = time.time() - start_time

                # Verify file was actually created
                if output_file.exists() and output_file.stat().st_size > 0:
                    return True, f"✅ {audio_file.name} ({method}, {process_time:.1f}s)"
                else:
                    return False, f"❌ {audio_file.name}: File not created by {method}"

            except subprocess.CalledProcessError as e:
                if attempt == 1:  # GPU failed, try CPU
                    continue
                return False, f"❌ {audio_file.name}: {e}"
            except subprocess.TimeoutExpired:
                if attempt == 1:  # GPU timeout, try CPU
                    continue
                return False, f"❌ {audio_file.name}: Timeout"
            except Exception as e:
                if attempt == 1:  # GPU error, try CPU
                    continue
                return False, f"❌ {audio_file.name}: {e}"

        return False, f"❌ {audio_file.name}: All methods failed"

    # Process files in parallel for maximum speed
    overall_success = True
    max_workers = min(len(interview_files), 4)  # Limit concurrent processes

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(clean_single_audio_file, audio_file): audio_file
            for audio_file in interview_files
        }

        # Process results as they complete
        for future in as_completed(future_to_file):
            success, message = future.result()
            logger.info(f"   {message}")
            if not success:
                overall_success = False

    if overall_success:
        logger.info(f"🎉 Successfully cleaned all {len(interview_files)} audio files using GPU acceleration!")
    else:
        logger.warning(f"⚠️ Some audio files failed to process")

    return overall_success


def run_audio_cleaning_step_multi(folder_name: str, inverse_clips_dir: Path, cleaned_audio_dir: Path) -> bool:
    """Run audio cleaning step for multi mode - uses same GPU acceleration as single mode"""
    return run_audio_cleaning_step_single(folder_name, inverse_clips_dir, cleaned_audio_dir, {})


def run_ranking_step_single(folder_name: str, inverse_clips_dir: Path, final_videos_dir: Path,
                            ranked_sequence_dir: Path, prompt_profile: Dict) -> bool:
    """Run video ranking step for single mode"""
    # Create profile-specific directories like in numbered mode
    version_final_dir = final_videos_dir / f"{folder_name}_final_{prompt_profile['suffix']}"
    profile_ranking_dir = ranked_sequence_dir / f"{folder_name}_ranked_{prompt_profile['suffix']}"
    profile_ranking_dir.mkdir(parents=True, exist_ok=True)

    ranking_args = [
        "--interviews", str(inverse_clips_dir),
        "--voiceovers", str(version_final_dir),
        "--output", str(profile_ranking_dir),
        "--video-stem", folder_name,
    ]

    return run_python_script(RANK_VIDEO_SEQUENCE_SCRIPT, ranking_args, capture_output=True)


def run_ranking_step_multi(folder_name: str, inverse_clips_dir: Path, final_videos_dir: Path,
                           ranked_sequence_dir: Path) -> bool:
    """Run video ranking step for numbered mode"""
    ranking_args = [
        "--interviews", str(inverse_clips_dir),
        "--voiceovers", str(final_videos_dir),
        "--output", str(ranked_sequence_dir),
        "--video-stem", folder_name,
    ]

    return run_python_script(RANK_VIDEO_SEQUENCE_SCRIPT, ranking_args, capture_output=True)


# REMOVED: run_metadata_step_single and run_metadata_step_multi functions
# These functions are no longer needed since Step 10 (metadata generation) was removed


def run_thumbnail_generator_step(video_stem: str, project_dir: Path, prompt_profile: Dict = None,
                                  mode: str = "script", input_folder: Path = None) -> bool:
    """Step 11: Generate viral thumbnail ideas and image prompts

    Args:
        video_stem: Video name (e.g., 'OG-1')
        project_dir: Project directory containing 1_processing with script
        prompt_profile: Profile info (for logging only now)
        mode: "script" (use script content) or "title" (extract from thumbnail filename)
        input_folder: For title mode - folder containing thumbnail_TITLE.jpg
    """
    # === CHECK IF THUMBNAIL GENERATION IS DISABLED ===
    if mode and mode.lower() == 'off':
        logger.info(f"⏭️ [{video_stem}] Thumbnail generation is OFF - skipping")
        return True

    # Get AI provider from config (thumbnail_ai_settings is the dedicated setting)
    ai_provider = 'claude'
    try:
        config_paths = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'NabilVideoStudioPro' / 'config.json',
            Path(__file__).parent / 'config.json',
        ]
        for config_path in config_paths:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    ai_provider = config.get('thumbnail_ai_settings', {}).get('provider', 'claude')
                    if not ai_provider:
                        ai_provider = 'claude'
                    break
    except Exception as e:
        logger.warning(f"Could not read AI provider from config: {e}")

    logger.info(f"🎨 [{video_stem}] Starting Thumbnail Generator...")
    logger.info(f"🎨 [{video_stem}] Mode: {mode}, AI: {ai_provider}")

    # Output goes to youtube_uploads folder (same as video)
    step_10_dir = project_dir / SUBDIR_YOUTUBE_UPLOADS
    step_10_dir.mkdir(parents=True, exist_ok=True)

    # Check if thumbnail already generated
    prompt_file = step_10_dir / "thumbnail_prompt.txt"
    if prompt_file.exists():
        logger.info(f"🎨 [{video_stem}] Thumbnail already generated, skipping...")
        return True

    # Prepare arguments based on mode
    if mode == "title" and input_folder:
        # Title mode: use input folder to extract title from thumbnail filename
        thumbnail_args = [
            "--project-dir", str(input_folder),
            "--output-dir", str(step_10_dir),
            "--mode", "title",
            "--provider", ai_provider,
        ]
        logger.info(f"🎨 [{video_stem}] Using TITLE mode from: {input_folder}")
    else:
        # Script mode: use project directory with script
        thumbnail_args = [
            "--project-dir", str(project_dir),
            "--output-dir", str(step_10_dir),
            "--mode", "script",
            "--provider", ai_provider,
        ]
        logger.info(f"🎨 [{video_stem}] Using SCRIPT mode from: {project_dir}")

    logger.info(f"🎨 [{video_stem}] Generating thumbnail ideas and prompt...")
    return run_python_script(THUMBNAIL_GENERATOR_SCRIPT, thumbnail_args, capture_output=False)


# ==============================================================================
# --- MAIN PIPELINE FUNCTIONS (FIXED) ---
# ==============================================================================

def process_video_pipeline_custom(video_path: Path, folder_name: str, project_base_dir: Path, api_key_gemini: str,
                                  selected_prompt: Dict,
                                  selected_voice: Dict, force_start_from: int = -1, input_folder_path: Path = None) -> bool:
    """Process video with custom prompt + voice selection"""
    # Use the passed folder_name parameter instead of video_path.stem

    # Get per-folder B-roll if configured
    per_folder_broll = None
    if input_folder_path:
        per_folder_broll = get_per_folder_broll(str(input_folder_path))
        if per_folder_broll:
            logger.info(f"📂 Using per-folder custom B-roll: {per_folder_broll}")

    # Define directories - use folder name for output directory
    video_output_dir = project_base_dir / folder_name
    log_dir = video_output_dir / SUBDIR_LOGS
    original_video_copy_dir = video_output_dir / SUBDIR_ORIGINAL_VIDEO
    clips_main_dir = video_output_dir / SUBDIR_CLIPS_MAIN
    primary_clips_dir = clips_main_dir / SUBDIR_PRIMARY_CLIPS
    inverse_clips_dir = clips_main_dir / SUBDIR_INVERSE_CLIPS
    styled_clips_dir = video_output_dir / SUBDIR_STYLED_CLIPS  # NEW STEP 2
    transcripts_dir = video_output_dir / SUBDIR_TRANSCRIPTS
    ai_scripts_dir = video_output_dir / SUBDIR_AI_SCRIPTS
    voiceovers_dir = video_output_dir / SUBDIR_VOICEOVERS
    rearranged_broll_clips_dir = video_output_dir / SUBDIR_REARRANGED_BROLL_CLIPS
    final_videos_dir = video_output_dir / SUBDIR_FINAL_VIDEOS
    ranked_sequence_dir = video_output_dir / SUBDIR_RANKED_SEQUENCE
    new_step9_dir = video_output_dir / SUBDIR_NEW_STEP9
    # metadata_dir = video_output_dir / SUBDIR_METADATA  # REMOVED - No longer needed
    youtube_uploads_dir = video_output_dir / SUBDIR_YOUTUBE_UPLOADS

    # Create directories
    for d in [video_output_dir, log_dir, original_video_copy_dir, clips_main_dir, primary_clips_dir, inverse_clips_dir,
              styled_clips_dir, transcripts_dir, ai_scripts_dir, voiceovers_dir, rearranged_broll_clips_dir,
              final_videos_dir,
              ranked_sequence_dir, new_step9_dir, youtube_uploads_dir]:
        d.mkdir(parents=True, exist_ok=True)

    temp_script_dir = log_dir / SUBDIR_TEMP_SCRIPTS
    temp_script_dir.mkdir(parents=True, exist_ok=True)

    # Create video-specific status file name to avoid conflicts between videos in same folder
    video_base_name = video_path.stem.replace(' ', '_').replace("'", "").replace('"', '')[:50]  # Sanitize and truncate
    status_filename = f"pipeline_status_{video_base_name}.json"
    status_filepath = log_dir / status_filename
    pipeline_steps_info = get_pipeline_steps_info(multi_mode=False)
    max_step = max(pipeline_steps_info.keys())

    # Display current status and load status data
    current_status = display_current_status(folder_name, project_base_dir, video_path, max_step)

    logger.info(f"\n{'=' * 80}\nProcessing Video (CUSTOM MODE): {video_path.name}")
    logger.info(f"Custom Configuration:")
    logger.info(f"  Prompt: {selected_prompt['name']}")
    logger.info(f"  Voice: {selected_voice['name']}")
    logger.info(f"Output: {video_output_dir}\n{'=' * 80}")

    overall_success = True

    for step_num in sorted(pipeline_steps_info.keys()):
        if step_num < force_start_from and force_start_from != -1:
            continue

        # ⏭️ Check if step is already completed (AUTO-SKIP with output validation)
        last_completed = current_status.get(STATUS_KEY_LAST_COMPLETED_STEP, -1)
        if step_num <= last_completed and force_start_from == -1:
            # Validate that output files actually exist
            output_exists = validate_step_output_exists(step_num, video_output_dir, folder_name, is_multi_mode=False)
            if output_exists:
                step_info = pipeline_steps_info[step_num]
                logger.info(f"\n⏭️ STEP {step_num} ALREADY COMPLETED: {step_info['name']}")
                logger.info(f"   → Skipping (output files verified)")
                continue
            else:
                step_info = pipeline_steps_info[step_num]
                logger.info(f"\n🔄 STEP {step_num} OUTPUT MISSING: {step_info['name']}")
                logger.info(f"   → Status says completed but output files not found, will re-run")
                # Update status to reflect that this step needs to be re-run
                current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num - 1

        step_info = pipeline_steps_info[step_num]
        logger.info(f"\n🚀 Step {step_num}: {step_info['name']}...")

        current_status[STATUS_KEY_STATE] = "running"
        save_video_status(status_filepath, current_status)

        step_success = False

        try:
            if step_num == 0:
                # Rename video file to use folder name instead of long original filename
                new_video_name = f"{folder_name}{video_path.suffix}"
                destination_path = original_video_copy_dir / new_video_name
                shutil.copy(video_path, destination_path)
                logger.info(f"📁 Renamed video: {video_path.name} → {new_video_name}")
                step_success = True
            elif step_num == 1:
                # Smart skip: Check if clips already exist
                primary_clips = list(primary_clips_dir.glob("*.mp4")) if primary_clips_dir.exists() else []
                inverse_clips = list(inverse_clips_dir.glob("*.mp4")) if inverse_clips_dir.exists() else []

                if len(primary_clips) > 0 and len(inverse_clips) > 0:
                    logger.info(
                        f"⚡ SMART SKIP: Found {len(primary_clips)} primary clips and {len(inverse_clips)} inverse clips")
                    logger.info("   → Skipping diarization (delete clip folders to regenerate)")
                    step_success = True
                else:
                    logger.info(f"📁 No existing clips found, proceeding with diarization...")
                    # Use renamed video file from step 0
                    new_video_name = f"{folder_name}{video_path.suffix}"
                    step_success = run_python_script(SPLITE_VIDEO_SCRIPT, [
                        str(original_video_copy_dir / new_video_name),
                        "--output-primary-clips-final", str(primary_clips_dir),
                        "--output-inverse-clips-final", str(inverse_clips_dir),
                        "--output-logs-final", str(log_dir / "diarization_logs"),
                        "--re-encode" if DIARIZATION_RE_ENCODE else "--no-re-encode",
                        "--use-spleeter" if DIARIZATION_USE_SPLEETER else "--no-spleeter"
                    ], capture_output=True)
            elif step_num == 2:
                # Check if manual cropping is needed (GUI cannot run in background thread)
                needs_manual_crop = selected_prompt.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)

                # 🚀 PARALLEL OPTIMIZATION: Run Step 2+3 together if enabled
                # BUT: Disable parallel mode if manual crop is needed (GUI requires main thread)
                if ENABLE_PARALLEL_STEPS and step_num + 1 <= max_step and not needs_manual_crop:
                    logger.info("=" * 80)
                    logger.info("🚀 PARALLEL MODE: Running Steps 2 (Style) + 3 (Transcribe) simultaneously!")
                    logger.info("=" * 80)

                    # Define Step 2 function
                    def execute_step2():
                        interviews_dir = clips_main_dir / "interviews"
                        if not interviews_dir.exists():
                            logger.warning(f"⚠️ Interviews directory not found: {interviews_dir}")
                            return False

                        # Check for smart skip
                        if styled_clips_dir.exists():
                            existing_clips = list(styled_clips_dir.glob("*.mp4"))
                            if len(existing_clips) > 0:
                                logger.info(f"⚡ SMART SKIP (Step 2): Found {len(existing_clips)} existing styled clips")
                                return True

                        logger.info("🎨 Step 2: Styling interview clips...")
                        style_args = [
                            str(interviews_dir),
                            str(styled_clips_dir),
                            "--background", selected_prompt["background_video"],
                            "--frame-color", selected_prompt["frame_color"],
                            "--video-scale", str(selected_prompt["video_scale"]),
                            "--animation-type", selected_prompt.get("animation_type", "slide"),
                            "--animation-direction", selected_prompt.get("animation_direction", "left"),
                            "--animation-duration", str(selected_prompt.get("animation_duration", 0.8)),
                            "--out-animation-duration", str(selected_prompt.get("out_animation_duration", 0.8)),
                            "--vocal-parallel", str(VOCAL_EXTRACTION_PARALLEL_JOBS),
                            "--vocal-model", VOCAL_EXTRACTION_MODEL,
                            "--trim-seconds", str(TRIM_INTERVIEW_CLIPS_SECONDS)
                        ]
                        # Add sound effect arguments
                        style_args.extend(get_sound_effect_args())
                        if not selected_prompt.get("enable_animation", True):
                            style_args.append("--disable-animation")
                        if VOCAL_EXTRACTION_ENABLED:
                            style_args.append("--enable-vocal-extraction")
                        if selected_prompt.get("enable_out_animation", True):
                            style_args.append("--enable-out-animation")
                        use_manual_crop = selected_prompt.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)
                        if use_manual_crop is False:
                            style_args.append("--auto-crop")

                        # Use capture_output=False when manual crop is enabled (GUI needs to display)
                        return run_python_script(STYLE_INTERVIEW_SCRIPT, style_args, capture_output=(not use_manual_crop))

                    # Define Step 3 function
                    def execute_step3():
                        # Check for smart skip
                        if transcripts_dir.exists():
                            existing_transcripts = list(transcripts_dir.glob("*.txt"))
                            if len(existing_transcripts) > 0:
                                logger.info(f"⚡ SMART SKIP (Step 3): Found {len(existing_transcripts)} existing transcripts")
                                return True

                        logger.info("📝 Step 3: Transcribing clips...")
                        return run_transcription_step(folder_name, primary_clips_dir, transcripts_dir, temp_script_dir)

                    # Run both steps in parallel
                    parallel_tasks = [
                        {'name': 'Step 2 (Style Clips)', 'function': execute_step2, 'args': ()},
                        {'name': 'Step 3 (Transcribe)', 'function': execute_step3, 'args': ()}
                    ]

                    step_success = run_steps_in_parallel(parallel_tasks)

                    if step_success:
                        # Mark both steps as completed
                        logger.info("✅ Steps 2+3 completed successfully in parallel!")
                        current_step = step_num + 1  # Skip to step 4
                        save_video_status(status_filepath, {STATUS_KEY_LAST_COMPLETED_STEP: current_step})
                        continue  # Skip the normal Step 3 execution

                # FALLBACK: Sequential execution if parallel disabled or manual crop needed
                else:
                    if needs_manual_crop:
                        logger.info("=" * 80)
                        logger.info("⚠️ SEQUENTIAL MODE: Manual crop enabled - GUI requires main thread")
                        logger.info("   Running Steps 2 and 3 sequentially (not in parallel)")
                        logger.info("=" * 80)
                        logger.info("")
                        logger.info("👀 MANUAL CROP: A GUI window will appear for you to select crop area")
                        logger.info("   Please look for the crop selection window and interact with it")
                        logger.info("   The window may appear behind other windows - check your taskbar!")
                        logger.info("")

                # Step 2: Style Interview Clips (runs when NOT in parallel mode)
                # Smart skip: Check if styled clips already exist
                logger.info("=" * 80)
                logger.info("🚀 Step 2: Style Interview Clips")
                logger.info("=" * 80)
                logger.info(f"📁 Checking for existing styled clips in: {styled_clips_dir}")

                if styled_clips_dir.exists():
                    existing_clips = list(styled_clips_dir.glob("*.mp4"))
                    logger.info(f"📊 Found {len(existing_clips)} existing styled clips")
                    if len(existing_clips) > 0:
                        logger.info(
                            f"⚡ SMART SKIP: Found {len(existing_clips)} existing styled clips in {styled_clips_dir}")
                        logger.info("   → Skipping interview styling (delete the folder to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 Styled clips directory exists but is empty, proceeding with styling...")
                        interviews_dir = clips_main_dir / "interviews"
                        if interviews_dir.exists():
                            style_args = [
                                str(interviews_dir),
                                str(styled_clips_dir),
                                "--background", selected_prompt["background_video"],
                                "--frame-color", selected_prompt["frame_color"],
                                "--video-scale", str(selected_prompt["video_scale"]),
                                "--animation-type", selected_prompt.get("animation_type", "slide"),
                                "--animation-direction", selected_prompt.get("animation_direction", "left"),
                                "--animation-duration", str(selected_prompt.get("animation_duration", 0.8)),
                                "--out-animation-duration", str(selected_prompt.get("out_animation_duration", 0.8)),
                                "--trim-seconds", str(TRIM_INTERVIEW_CLIPS_SECONDS)
                            ]
                            # Add sound effect arguments
                            style_args.extend(get_sound_effect_args())
                            # Add animation flags
                            if not selected_prompt.get("enable_animation", True):
                                style_args.append("--disable-animation")
                            if selected_prompt.get("enable_out_animation", True):
                                style_args.append("--enable-out-animation")

                            # Add manual crop flag (check profile override first, then global default)
                            use_manual_crop = selected_prompt.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)
                            if use_manual_crop is False:  # Explicitly set to False = use AI auto-crop
                                style_args.append("--auto-crop")

                            # Use capture_output=False when manual crop is enabled (GUI needs to display)
                            step_success = run_python_script(STYLE_INTERVIEW_SCRIPT, style_args, capture_output=(not use_manual_crop))
                        else:
                            logger.warning(f"⚠️ Interviews directory not found: {interviews_dir}")
                            step_success = False
                else:
                    logger.info(f"🎨 Running Step 2: Style Interview Clips...")
                    interviews_dir = clips_main_dir / "interviews"
                    logger.info(f"📁 Interviews directory: {interviews_dir}")
                    logger.info(f"📁 Output directory: {styled_clips_dir}")

                    if interviews_dir.exists():
                        # Count interview files
                        interview_files = list(interviews_dir.glob("*.mp4"))
                        logger.info(f"📹 Found {len(interview_files)} interview clips to style")

                        if len(interview_files) == 0:
                            logger.warning("⚠️ No interview clips found to style!")
                            step_success = False
                        else:
                            # Build arguments list
                            style_args = [
                                str(interviews_dir),
                                str(styled_clips_dir),
                                "--background", selected_prompt["background_video"],
                                "--frame-color", selected_prompt["frame_color"],
                                "--video-scale", str(selected_prompt["video_scale"]),
                                "--animation-type", selected_prompt.get("animation_type", "slide"),
                                "--animation-direction", selected_prompt.get("animation_direction", "left"),
                                "--animation-duration", str(selected_prompt.get("animation_duration", 0.8)),
                                "--out-animation-duration", str(selected_prompt.get("out_animation_duration", 0.8)),
                                "--vocal-parallel", str(VOCAL_EXTRACTION_PARALLEL_JOBS),
                                "--vocal-model", VOCAL_EXTRACTION_MODEL,
                                "--trim-seconds", str(TRIM_INTERVIEW_CLIPS_SECONDS)
                            ]
                            # Add sound effect arguments
                            style_args.extend(get_sound_effect_args())
                            # Add animation flags
                            if not selected_prompt.get("enable_animation", True):
                                style_args.append("--disable-animation")
                            if VOCAL_EXTRACTION_ENABLED:
                                style_args.append("--enable-vocal-extraction")
                            if selected_prompt.get("enable_out_animation", True):
                                style_args.append("--enable-out-animation")

                            # Add manual crop flag (check profile override first, then global default)
                            use_manual_crop = selected_prompt.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)
                            if use_manual_crop is False:  # Explicitly set to False = use AI auto-crop
                                style_args.append("--auto-crop")
                                logger.info("🤖 Using AI auto-crop")
                            else:
                                logger.info("✂️ Using manual crop (GUI will appear)")

                            logger.info(f"🚀 Calling style script: {STYLE_INTERVIEW_SCRIPT}")
                            logger.info(f"📋 Arguments: {' '.join(str(arg) for arg in style_args[:6])}...")

                            # Use capture_output=False when manual crop is enabled (GUI needs to display)
                            logger.info("⏳ Starting style script...")
                            step_success = run_python_script(STYLE_INTERVIEW_SCRIPT, style_args, capture_output=(not use_manual_crop))
                            logger.info(f"✅ Style script completed with success={step_success}")
                    else:
                        logger.warning(f"⚠️ Interviews directory not found: {interviews_dir}")
                        step_success = False
            elif step_num == 3:
                # Check if Step 3 was already executed in parallel with Step 2
                if ENABLE_PARALLEL_STEPS and current_status.get(STATUS_KEY_LAST_COMPLETED_STEP, -1) >= 3:
                    logger.info("⚡ Step 3 already completed in parallel mode, skipping...")
                    step_success = True
                    continue

                # Smart skip: Check if transcripts already exist
                if transcripts_dir.exists():
                    existing_transcripts = list(transcripts_dir.glob("*.txt"))
                    if len(existing_transcripts) > 0:
                        logger.info(
                            f"⚡ SMART SKIP: Found {len(existing_transcripts)} existing transcripts in {transcripts_dir}")
                        logger.info("   → Skipping transcription (delete the folder to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 Transcripts directory exists but is empty, proceeding with transcription...")
                        step_success = run_transcription_step(folder_name, primary_clips_dir, transcripts_dir,
                                                              temp_script_dir)
                else:
                    step_success = run_transcription_step(folder_name, primary_clips_dir, transcripts_dir,
                                                          temp_script_dir)
            elif step_num == 4:
                # 🚀 PARALLEL OPTIMIZATION: Run Step 4+6 together if enabled
                if ENABLE_PARALLEL_STEPS and step_num + 2 <= max_step:
                    logger.info("=" * 80)
                    logger.info("🚀 PARALLEL MODE: Running Steps 4 (AI Rewrite) + 6 (B-roll) simultaneously!")
                    logger.info("=" * 80)

                    # Define Step 4 function
                    def execute_step4():
                        # Check for smart skip
                        if ai_scripts_dir.exists():
                            existing_scripts = list(ai_scripts_dir.glob("*.txt"))
                            if len(existing_scripts) > 0:
                                logger.info(f"⚡ SMART SKIP (Step 4): Found {len(existing_scripts)} existing AI scripts")
                                return True

                        logger.info("📝 Step 4: Generating AI script...")
                        return run_ai_script_step_single(folder_name, transcripts_dir, ai_scripts_dir,
                                                        selected_prompt, api_key_gemini)

                    # Define Step 6 function
                    def execute_step6():
                        # Check for smart skip
                        if rearranged_broll_clips_dir.exists():
                            existing_clips = list(rearranged_broll_clips_dir.glob("*.mp4"))
                            if len(existing_clips) > 0:
                                logger.info(f"⚡ SMART SKIP (Step 6): Found {len(existing_clips)} existing B-roll clips")
                                return True

                        logger.info("🎬 Step 6: Creating B-roll clips...")
                        return run_broll_step(primary_clips_dir, rearranged_broll_clips_dir, voiceovers_dir, per_folder_broll)

                    # Run both steps in parallel
                    parallel_tasks = [
                        {'name': 'Step 4 (AI Rewrite)', 'function': execute_step4, 'args': ()},
                        {'name': 'Step 6 (B-roll)', 'function': execute_step6, 'args': ()}
                    ]

                    step_success = run_steps_in_parallel(parallel_tasks)

                    if step_success:
                        # Mark Step 4 as completed (Step 5 will run normally, then Step 6 will be skipped)
                        logger.info("✅ Steps 4+6 completed successfully in parallel!")
                        # Don't skip Step 5 (voiceover), but mark Step 6 as done
                        save_video_status(status_filepath, {STATUS_KEY_LAST_COMPLETED_STEP: 6})
                        # Continue normally to Step 5 - skip the sequential fallback
                    else:
                        logger.error("❌ Parallel Steps 4+6 failed!")
                        overall_success = False
                        current_status[STATUS_KEY_STATE] = "failed"
                        save_video_status(status_filepath, current_status)
                        break
                else:
                    # FALLBACK: Sequential execution if parallel disabled
                    # Smart skip: Check if AI scripts already exist
                    if ai_scripts_dir.exists():
                        existing_scripts = list(ai_scripts_dir.glob("*.txt"))
                        if len(existing_scripts) > 0:
                            logger.info(
                                f"⚡ SMART SKIP: Found {len(existing_scripts)} existing AI scripts in {ai_scripts_dir}")
                            logger.info("   → Skipping AI script generation (delete the folder to regenerate)")
                            step_success = True
                        else:
                            logger.info(f"📁 AI scripts directory exists but is empty, proceeding with generation...")
                            step_success = run_ai_script_step_single(folder_name, transcripts_dir, ai_scripts_dir,
                                                                     selected_prompt,
                                                                     api_key_gemini)
                    else:
                        step_success = run_ai_script_step_single(folder_name, transcripts_dir, ai_scripts_dir,
                                                                 selected_prompt,
                                                                 api_key_gemini)
            elif step_num == 5:
                # Smart skip: Check if voiceovers already exist
                if voiceovers_dir.exists():
                    existing_voiceovers = list(voiceovers_dir.glob("**/*.mp3"))
                    if len(existing_voiceovers) > 0:
                        logger.info(
                            f"⚡ SMART SKIP: Found {len(existing_voiceovers)} existing voiceovers in {voiceovers_dir}")
                        logger.info("   → Skipping voiceover generation (delete the folder to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 Voiceovers directory exists but is empty, proceeding with generation...")
                        step_success = run_voiceover_step_single(folder_name, ai_scripts_dir, voiceovers_dir,
                                                                 selected_voice["url"], temp_script_dir,
                                                                 selected_prompt)
                else:
                    step_success = run_voiceover_step_single(folder_name, ai_scripts_dir, voiceovers_dir,
                                                             selected_voice["url"], temp_script_dir, selected_prompt)
            elif step_num == 6:
                # Check if Step 6 was already executed in parallel with Step 4
                if ENABLE_PARALLEL_STEPS and current_status.get(STATUS_KEY_LAST_COMPLETED_STEP, -1) >= 6:
                    logger.info("⚡ Step 6 already completed in parallel mode, skipping...")
                    step_success = True
                    continue

                step_success = run_broll_step(primary_clips_dir, rearranged_broll_clips_dir, voiceovers_dir, per_folder_broll)
            elif step_num == 7:
                # Smart skip: Check if final videos already exist
                if final_videos_dir.exists():
                    existing_videos = list(final_videos_dir.glob("*.mp4"))
                    if len(existing_videos) > 0:
                        logger.info(
                            f"⚡ SMART SKIP: Found {len(existing_videos)} existing final videos in {final_videos_dir}")
                        logger.info("   → Skipping final video assembly (delete the folder to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 Final videos directory exists but is empty, proceeding with assembly...")
                        step_success = run_assembly_step_single(folder_name, voiceovers_dir, rearranged_broll_clips_dir,
                                                                final_videos_dir, log_dir, selected_prompt)
                else:
                    step_success = run_assembly_step_single(folder_name, voiceovers_dir, rearranged_broll_clips_dir,
                                                            final_videos_dir, log_dir, selected_prompt)
            elif step_num == 8:
                step_success = run_ranking_step_single(folder_name, styled_clips_dir, final_videos_dir,
                                                       ranked_sequence_dir, selected_prompt)
            elif step_num == 9:
                # Step 9: Combine Ranked Videos
                logger.info(f"🎯 Running Step 9: Combine Ranked Videos...")
                # Use profile-specific directories like other steps
                profile_ranked_dir = ranked_sequence_dir / f"{folder_name}_ranked_{selected_prompt['suffix']}"
                profile_combined_dir = new_step9_dir / f"{folder_name}_combined_{selected_prompt['suffix']}"
                profile_combined_dir.mkdir(parents=True, exist_ok=True)

                # Get background music settings for the selected profile
                background_music_path, voice_level, music_level = get_background_music_for_profile(selected_prompt)

                # Build Step 9 arguments with background music
                step9_args = [
                    "--input", str(profile_ranked_dir),
                    "--output", str(profile_combined_dir),
                    "--video-stem", folder_name,
                    "--voice-level", str(voice_level),
                    "--music-level", str(music_level)
                ]

                if background_music_path:
                    step9_args.extend([
                        "--enable-music",
                        "--background-music", str(background_music_path)
                    ])
                    logger.info(f"🎵 Using background music: {Path(background_music_path).name}")
                else:
                    logger.info(f"🔇 No background music for {selected_prompt['name']}")

                step_success = run_python_script(COMBINE_RANKED_SCRIPT, step9_args, capture_output=True)
            elif step_num == 10:
                # Step 10: Upload to YouTube (was Step 11)
                youtube_uploads_dir = video_output_dir / SUBDIR_YOUTUBE_UPLOADS
                youtube_uploads_dir.mkdir(parents=True, exist_ok=True)

                # Check if upload is enabled for this profile
                if selected_prompt.get('enable_upload', True):
                    logger.info(f"🎯 Running Step 10: Upload to YouTube (Clean & Simple - NO metadata)...")

                    # Build arguments for YouTube upload script
                    youtube_args = [
                        "--input", str(new_step9_dir),
                        "--output", str(youtube_uploads_dir),
                        "--video-stem", folder_name,
                        "--profiles", selected_prompt['suffix'],
                        "--wait-minutes", str(selected_prompt.get('upload_wait_minutes', 5))
                    ]

                    logger.info(f"🎬 Uploading {selected_prompt['name']} to YouTube (just upload - add metadata manually later)...")
                    step_success = run_python_script(YOUTUBE_UPLOAD_SCRIPT, youtube_args, capture_output=True)
                else:
                    logger.info(f"⏭️ Skipping Step 10: Upload disabled for {selected_prompt['name']}")
                    # Create empty results file to mark step as completed
                    results_file = youtube_uploads_dir / f"{folder_name}_youtube_uploads.json"
                    results_file.write_text('{"skipped": "Upload disabled for this profile"}')
                    step_success = True

        except Exception as e:
            logger.error(f"❌ Step {step_num} failed with error: {e}")
            step_success = False

        if step_success:
            logger.info(f"✅ Step {step_num} completed: {step_info['name']}")
            current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num
            current_step = step_num  # Update current_step tracker
            save_video_status(status_filepath, current_status)
        else:
            logger.error(f"❌ Pipeline failed at Step {step_num}: {step_info['name']}")
            overall_success = False
            current_status[STATUS_KEY_STATE] = "failed"
            save_video_status(status_filepath, current_status)
            break

    if temp_script_dir.exists():
        try:
            shutil.rmtree(temp_script_dir)
        except Exception as e:
            logger.warning(f"Failed to remove temp script folder: {e}")

    if overall_success:
        current_status[STATUS_KEY_STATE] = "completed"
        current_status[STATUS_KEY_LAST_COMPLETED_STEP] = max(pipeline_steps_info.keys())
        save_video_status(status_filepath, current_status)
        logger.info(f"\n{'=' * 80}\n✨ CUSTOM PIPELINE COMPLETE for: {video_path.name}")
        logger.info(f"Custom Configuration: {selected_prompt['name']} + {selected_voice['name']}\n{'=' * 80}")
    else:
        logger.info(f"\n{'=' * 80}\n🛑 CUSTOM PIPELINE FAILED for: {video_path.name}\n{'=' * 80}")

    return overall_success


def process_video_pipeline_numbered(video_path: Path, folder_name: str, project_base_dir: Path, api_key_gemini: str,
                                    num_videos: int,
                                    force_start_from: int = -1, input_folder_path: Path = None) -> bool:
    """FIXED: Process video with SPECIFIC NUMBER of profiles (1, 2, 3, etc.)"""
    global UI_MODE

    # Use the passed folder_name parameter instead of video_path.stem

    # Get per-folder B-roll if configured
    per_folder_broll = None
    if input_folder_path:
        per_folder_broll = get_per_folder_broll(str(input_folder_path))
        if per_folder_broll:
            logger.info(f"📂 Using per-folder custom B-roll: {per_folder_broll}")

    # Get ONLY the first N profiles based on user selection
    all_profiles = list(PROMPT_PROFILES.items())
    selected_profiles = all_profiles[:num_videos]  # ⭐ KEY FIX: Only process first N profiles

    # Define shared directories - use folder name for output directory
    video_output_dir = project_base_dir / folder_name
    log_dir = video_output_dir / SUBDIR_LOGS
    original_video_copy_dir = video_output_dir / SUBDIR_ORIGINAL_VIDEO
    clips_main_dir = video_output_dir / SUBDIR_CLIPS_MAIN
    primary_clips_dir = clips_main_dir / SUBDIR_PRIMARY_CLIPS
    inverse_clips_dir = clips_main_dir / SUBDIR_INVERSE_CLIPS
    styled_clips_dir = video_output_dir / SUBDIR_STYLED_CLIPS  # NEW STEP 2 - Profile-specific directories
    transcripts_dir = video_output_dir / SUBDIR_TRANSCRIPTS
    ai_scripts_dir = video_output_dir / SUBDIR_AI_SCRIPTS
    voiceovers_dir = video_output_dir / SUBDIR_VOICEOVERS
    rearranged_broll_clips_dir = video_output_dir / SUBDIR_REARRANGED_BROLL_CLIPS
    final_videos_dir = video_output_dir / SUBDIR_FINAL_VIDEOS
    ranked_sequence_dir = video_output_dir / SUBDIR_RANKED_SEQUENCE
    new_step9_dir = video_output_dir / SUBDIR_NEW_STEP9
    # metadata_dir = video_output_dir / SUBDIR_METADATA  # REMOVED - No longer needed
    youtube_uploads_dir = video_output_dir / SUBDIR_YOUTUBE_UPLOADS

    # Create directories
    for d in [video_output_dir, log_dir, original_video_copy_dir, clips_main_dir, primary_clips_dir, inverse_clips_dir,
              styled_clips_dir, transcripts_dir, ai_scripts_dir, voiceovers_dir, rearranged_broll_clips_dir,
              final_videos_dir,
              ranked_sequence_dir, new_step9_dir, youtube_uploads_dir]:
        d.mkdir(parents=True, exist_ok=True)

    temp_script_dir = log_dir / SUBDIR_TEMP_SCRIPTS
    temp_script_dir.mkdir(parents=True, exist_ok=True)

    # Create video-specific status file name to avoid conflicts between videos in same folder
    video_base_name = video_path.stem.replace(' ', '_').replace("'", "").replace('"', '')[:50]  # Sanitize and truncate
    status_filename = f"pipeline_status_{video_base_name}.json"
    status_filepath = log_dir / status_filename
    pipeline_steps_info = get_pipeline_steps_info(multi_mode=True)
    max_step = max(pipeline_steps_info.keys())

    # Display current status and load status data
    current_status = display_current_status(folder_name, project_base_dir, video_path, max_step)

    logger.info(f"\n{'=' * 80}\nProcessing Video (NUMBERED MODE): {video_path.name}")
    logger.info(f"Will create {num_videos} video{'s' if num_videos > 1 else ''} using selected profiles:")
    for profile_key, profile_info in selected_profiles:
        logger.info(f"  • {profile_info['name']} using {profile_info['default_voice']} voice")
    logger.info(f"Output: {video_output_dir}\n{'=' * 80}")

    overall_success = True
    current_step = force_start_from if force_start_from != -1 else 0  # Initialize current_step

    for step_num in sorted(pipeline_steps_info.keys()):
        if step_num < force_start_from and force_start_from != -1:
            continue

        # ⏭️ Check if step is already completed (AUTO-SKIP with output validation)
        last_completed = current_status.get(STATUS_KEY_LAST_COMPLETED_STEP, -1)
        if step_num <= last_completed and force_start_from == -1:
            # Validate that output files actually exist
            output_exists = validate_step_output_exists(step_num, video_output_dir, folder_name, is_multi_mode=True,
                                                        selected_profiles=selected_profiles)
            if output_exists:
                step_info = pipeline_steps_info[step_num]
                logger.info(f"\n⏭️ STEP {step_num} ALREADY COMPLETED: {step_info['name']}")
                logger.info(f"   → Skipping (output files verified)")
                continue
            else:
                step_info = pipeline_steps_info[step_num]
                logger.info(f"\n🔄 STEP {step_num} OUTPUT MISSING: {step_info['name']}")
                logger.info(f"   → Status says completed but output files not found, will re-run")
                # Update status to reflect that this step needs to be re-run
                current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num - 1

        step_info = pipeline_steps_info[step_num]
        logger.info(f"\n🚀 Step {step_num}: {step_info['name']}...")

        current_status[STATUS_KEY_STATE] = "running"
        save_video_status(status_filepath, current_status)

        step_success = False

        try:
            if step_num == 0:
                # Rename video file to use folder name instead of long original filename
                new_video_name = f"{folder_name}{video_path.suffix}"
                destination_path = original_video_copy_dir / new_video_name
                shutil.copy(video_path, destination_path)
                logger.info(f"📁 Renamed video: {video_path.name} → {new_video_name}")
                step_success = True
            elif step_num == 1:
                # Smart skip: Check if clips already exist
                primary_clips = list(primary_clips_dir.glob("*.mp4")) if primary_clips_dir.exists() else []
                inverse_clips = list(inverse_clips_dir.glob("*.mp4")) if inverse_clips_dir.exists() else []

                if len(primary_clips) > 0 and len(inverse_clips) > 0:
                    logger.info(
                        f"⚡ SMART SKIP: Found {len(primary_clips)} primary clips and {len(inverse_clips)} inverse clips")
                    logger.info("   → Skipping diarization (delete clip folders to regenerate)")
                    step_success = True
                else:
                    logger.info(f"📁 No existing clips found, proceeding with diarization...")
                    # Use renamed video file from step 0
                    new_video_name = f"{folder_name}{video_path.suffix}"
                    step_success = run_python_script(SPLITE_VIDEO_SCRIPT, [
                        str(original_video_copy_dir / new_video_name),
                        "--output-primary-clips-final", str(primary_clips_dir),
                        "--output-inverse-clips-final", str(inverse_clips_dir),
                        "--output-logs-final", str(log_dir / "diarization_logs"),
                        "--re-encode" if DIARIZATION_RE_ENCODE else "--no-re-encode",
                        "--use-spleeter" if DIARIZATION_USE_SPLEETER else "--no-spleeter"
                    ], capture_output=True)
            elif step_num == 2:
                # Check if any profile needs manual cropping (GUI cannot run in background thread)
                needs_manual_crop = any(
                    profile_info.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)
                    for _, profile_info in selected_profiles
                )

                # 🚀 PARALLEL OPTIMIZATION: Run Step 2+3 together if enabled
                # BUT: Disable parallel mode if manual crop is needed (GUI requires main thread)
                if ENABLE_PARALLEL_STEPS and step_num + 1 <= max_step and not needs_manual_crop:
                    logger.info("=" * 80)
                    logger.info("🚀 PARALLEL MODE (MULTI): Running Steps 2 (Style) + 3 (Transcribe) simultaneously!")
                    logger.info("=" * 80)

                    # Define Step 2 function (styling)
                    def execute_step2_multi():
                        logger.info(f"🎨 Running Step 2: Style Interview Clips for {num_videos} selected profiles...")
                        interviews_dir = clips_main_dir / "interviews"

                        if not interviews_dir.exists():
                            logger.warning(f"⚠️ Interviews directory not found: {interviews_dir}")
                            return False
                        else:
                            all_styling_success = True
                            for profile_key, profile_info in selected_profiles:  # Process each profile
                                logger.info(f"   Styling interviews for {profile_info['name']} profile...")

                                # Create profile-specific styled clips directory
                                profile_styled_dir = styled_clips_dir / f"{folder_name}_styled_{profile_info['suffix']}"
                                profile_styled_dir.mkdir(parents=True, exist_ok=True)

                                # Smart skip: Check if profile-specific styled clips already exist
                                existing_clips = list(profile_styled_dir.glob("*.mp4"))
                                if len(existing_clips) > 0:
                                    logger.info(
                                        f"   ⚡ SMART SKIP: Found {len(existing_clips)} existing styled clips for {profile_info['name']}")
                                    logger.info(f"      → Skipping (delete {profile_styled_dir.name} to regenerate)")
                                else:
                                    # Build arguments list for profile-specific styling
                                    profile_style_args = [
                                        str(interviews_dir),
                                        str(profile_styled_dir),
                                        "--background",
                                        profile_info.get("background_video", ""),
                                        "--frame-color", profile_info.get("frame_color", "#888683"),
                                        "--video-scale", str(profile_info.get("video_scale", 0.85)),
                                        "--animation-type", profile_info.get("animation_type", "slide"),
                                        "--animation-direction", profile_info.get("animation_direction", "left"),
                                        "--animation-duration", str(profile_info.get("animation_duration", 0.8)),
                                        "--out-animation-duration", str(profile_info.get("out_animation_duration", 0.8)),
                                        "--vocal-parallel", str(VOCAL_EXTRACTION_PARALLEL_JOBS),
                                        "--vocal-model", VOCAL_EXTRACTION_MODEL,
                                        "--trim-seconds", str(TRIM_INTERVIEW_CLIPS_SECONDS)
                                    ]
                                    # Add sound effect arguments
                                    profile_style_args.extend(get_sound_effect_args())
                                    # Add animation flags
                                    if not profile_info.get("enable_animation", True):
                                        profile_style_args.append("--disable-animation")
                                    if VOCAL_EXTRACTION_ENABLED:
                                        profile_style_args.append("--enable-vocal-extraction")
                                    if profile_info.get("enable_out_animation", True):
                                        profile_style_args.append("--enable-out-animation")

                                    # Add manual crop flag (check profile override first, then global default)
                                    use_manual_crop = profile_info.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)
                                    if use_manual_crop is False:  # Explicitly set to False = use AI auto-crop
                                        profile_style_args.append("--auto-crop")

                                    # Run styling with profile-specific settings
                                    # Use capture_output=False when manual crop is enabled (GUI needs to display)
                                    styling_success = run_python_script(STYLE_INTERVIEW_SCRIPT, profile_style_args,
                                                                        capture_output=(not use_manual_crop))

                                    if not styling_success:
                                        all_styling_success = False
                                        logger.error(f"   ❌ Failed to style interviews for {profile_info['name']}")
                                    else:
                                        logger.info(f"   ✅ Styled interviews for {profile_info['name']} with custom settings")

                            return all_styling_success

                    # Define Step 3 function (transcription)
                    def execute_step3_multi():
                        # Smart skip: Check if transcripts already exist
                        if transcripts_dir.exists():
                            existing_transcripts = list(transcripts_dir.glob("*.txt"))
                            if len(existing_transcripts) > 0:
                                logger.info(
                                    f"⚡ SMART SKIP: Found {len(existing_transcripts)} existing transcripts in {transcripts_dir}")
                                logger.info("   → Skipping transcription (delete the folder to regenerate)")
                                return True
                            else:
                                logger.info(f"📁 Transcripts directory exists but is empty, proceeding with transcription...")
                                return run_transcription_step(folder_name, primary_clips_dir, transcripts_dir, temp_script_dir)
                        else:
                            return run_transcription_step(folder_name, primary_clips_dir, transcripts_dir, temp_script_dir)

                    # Run both steps in parallel
                    parallel_tasks = [
                        {'name': 'Step 2 (Style Clips)', 'function': execute_step2_multi, 'args': ()},
                        {'name': 'Step 3 (Transcribe)', 'function': execute_step3_multi, 'args': ()}
                    ]

                    step_success = run_steps_in_parallel(parallel_tasks)

                    if step_success:
                        logger.info("✅ Steps 2+3 completed successfully in parallel!")
                        current_step = step_num + 1  # Skip to step 4
                        save_video_status(status_filepath, {STATUS_KEY_LAST_COMPLETED_STEP: current_step})
                        continue  # Skip step 3 since it ran in parallel
                    else:
                        logger.error("❌ Parallel Steps 2+3 failed!")
                        overall_success = False
                        current_status[STATUS_KEY_STATE] = "failed"
                        save_video_status(status_filepath, current_status)
                        break
                else:
                    # Sequential mode: Either parallel disabled OR manual crop needs main thread
                    if needs_manual_crop:
                        logger.info("=" * 80)
                        logger.info("⚠️ SEQUENTIAL MODE: Manual crop enabled - GUI requires main thread")
                        logger.info(f"   Running Step 2 (Style) for {num_videos} selected profiles...")
                        logger.info("=" * 80)
                        logger.info("")
                        logger.info("👀 MANUAL CROP: A GUI window will appear for you to select crop area")
                        logger.info("   Please look for the crop selection window and interact with it")
                        logger.info("   The window may appear behind other windows - check your taskbar!")
                        logger.info("")
                    else:
                        logger.info(f"🎨 Running Step 2: Style Interview Clips for {num_videos} selected profiles...")

                    interviews_dir = clips_main_dir / "interviews"

                    if not interviews_dir.exists():
                        logger.warning(f"⚠️ Interviews directory not found: {interviews_dir}")
                        step_success = False
                    else:
                        all_styling_success = True
                        for profile_key, profile_info in selected_profiles:  # Process each profile
                            logger.info(f"   Styling interviews for {profile_info['name']} profile...")

                            # Create profile-specific styled clips directory
                            profile_styled_dir = styled_clips_dir / f"{folder_name}_styled_{profile_info['suffix']}"
                            profile_styled_dir.mkdir(parents=True, exist_ok=True)

                            # Smart skip: Check if profile-specific styled clips already exist
                            existing_clips = list(profile_styled_dir.glob("*.mp4"))
                            if len(existing_clips) > 0:
                                logger.info(
                                    f"   ⚡ SMART SKIP: Found {len(existing_clips)} existing styled clips for {profile_info['name']}")
                                logger.info(f"      → Skipping (delete {profile_styled_dir.name} to regenerate)")
                            else:
                                # Build arguments list for profile-specific styling
                                profile_style_args = [
                                    str(interviews_dir),
                                    str(profile_styled_dir),
                                    "--background",
                                    profile_info.get("background_video", ""),
                                    "--frame-color", profile_info.get("frame_color", "#888683"),
                                    "--video-scale", str(profile_info.get("video_scale", 0.85)),
                                    "--animation-type", profile_info.get("animation_type", "slide"),
                                    "--animation-direction", profile_info.get("animation_direction", "left"),
                                    "--animation-duration", str(profile_info.get("animation_duration", 0.8)),
                                    "--out-animation-duration", str(profile_info.get("out_animation_duration", 0.8)),
                                    "--vocal-parallel", str(VOCAL_EXTRACTION_PARALLEL_JOBS),
                                    "--vocal-model", VOCAL_EXTRACTION_MODEL,
                                    "--trim-seconds", str(TRIM_INTERVIEW_CLIPS_SECONDS)
                                ]
                                # Add sound effect arguments
                                profile_style_args.extend(get_sound_effect_args())
                                # Add animation flags
                                if not profile_info.get("enable_animation", True):
                                    profile_style_args.append("--disable-animation")
                                if VOCAL_EXTRACTION_ENABLED:
                                    profile_style_args.append("--enable-vocal-extraction")
                                if profile_info.get("enable_out_animation", True):
                                    profile_style_args.append("--enable-out-animation")

                                # Add manual crop flag (check profile override first, then global default)
                                use_manual_crop = profile_info.get("use_manual_crop", USE_MANUAL_CROP_DEFAULT)
                                if use_manual_crop is False:  # Explicitly set to False = use AI auto-crop
                                    profile_style_args.append("--auto-crop")

                                # Run styling with profile-specific settings
                                # Use capture_output=False when manual crop is enabled (GUI needs to display)
                                styling_success = run_python_script(STYLE_INTERVIEW_SCRIPT, profile_style_args,
                                                                    capture_output=(not use_manual_crop))

                                if not styling_success:
                                    all_styling_success = False
                                    logger.error(f"   ❌ Failed to style interviews for {profile_info['name']}")
                                else:
                                    logger.info(f"   ✅ Styled interviews for {profile_info['name']} with custom settings")

                        step_success = all_styling_success
            elif step_num == 3:
                # Skip check: If we just ran Step 2+3 in parallel, skip this
                if ENABLE_PARALLEL_STEPS and current_step > step_num:
                    logger.info("⚡ Skipping Step 3 (already completed in parallel with Step 2)")
                    continue
                # Normal Step 3 execution (sequential mode)
                # Smart skip: Check if transcripts already exist
                if transcripts_dir.exists():
                    existing_transcripts = list(transcripts_dir.glob("*.txt"))
                    if len(existing_transcripts) > 0:
                        logger.info(
                            f"⚡ SMART SKIP: Found {len(existing_transcripts)} existing transcripts in {transcripts_dir}")
                        logger.info("   → Skipping transcription (delete the folder to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 Transcripts directory exists but is empty, proceeding with transcription...")
                        step_success = run_transcription_step(folder_name, primary_clips_dir, transcripts_dir,
                                                              temp_script_dir)
                else:
                    step_success = run_transcription_step(folder_name, primary_clips_dir, transcripts_dir,
                                                          temp_script_dir)
            elif step_num == 4:
                # 🚀 PARALLEL OPTIMIZATION: Run Step 4+6 together if enabled
                if ENABLE_PARALLEL_STEPS and step_num + 2 <= max_step:
                    logger.info("=" * 80)
                    logger.info("🚀 PARALLEL MODE (MULTI): Running Steps 4 (AI Rewrite) + 6 (B-roll) simultaneously!")
                    logger.info("=" * 80)

                    # Define Step 4 function (AI rewrite)
                    def execute_step4_multi():
                        logger.info(f"📝 Creating scripts for {num_videos} selected profiles...")
                        all_scripts_success = True

                        for profile_key, profile_info in selected_profiles:  # Only selected profiles
                            profile_suffix = profile_info.get('suffix', profile_key)
                            script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_suffix}.txt"

                            if script_file.exists() and script_file.stat().st_size > 100:
                                logger.info(f"   ⚡ SMART SKIP: Found existing script for {profile_info['name']}")
                                logger.info(f"      → Skipping (delete {script_file.name} to regenerate)")
                                continue  # Skip this profile

                            logger.info(f"   Creating {profile_info['name']} script...")
                            script_success = run_ai_script_step_multi(folder_name, transcripts_dir, ai_scripts_dir,
                                                                      profile_info,
                                                                      api_key_gemini)
                            if not script_success:
                                all_scripts_success = False
                                logger.error(f"   ❌ Failed to create {profile_info['name']} script")
                            else:
                                logger.info(f"   ✅ Created {profile_info['name']} script")
                        return all_scripts_success

                    # Define Step 6 function (B-roll)
                    def execute_step6_multi():
                        # Smart skip: Check if B-roll clips already exist
                        if rearranged_broll_clips_dir.exists():
                            existing_clips = list(rearranged_broll_clips_dir.glob("*.mp4"))
                            if len(existing_clips) > 0:
                                logger.info(
                                    f"⚡ SMART SKIP: Found {len(existing_clips)} existing B-roll clips in {rearranged_broll_clips_dir}")
                                logger.info("   → Skipping B-roll generation (delete the folder to regenerate)")
                                return True
                            else:
                                logger.info(f"📁 B-roll directory exists but is empty, proceeding with generation...")
                                return run_broll_step(primary_clips_dir, rearranged_broll_clips_dir, voiceovers_dir, per_folder_broll)
                        else:
                            return run_broll_step(primary_clips_dir, rearranged_broll_clips_dir, voiceovers_dir, per_folder_broll)

                    # Run both steps in parallel
                    parallel_tasks = [
                        {'name': 'Step 4 (AI Rewrite)', 'function': execute_step4_multi, 'args': ()},
                        {'name': 'Step 6 (B-roll)', 'function': execute_step6_multi, 'args': ()}
                    ]

                    step_success = run_steps_in_parallel(parallel_tasks)

                    if step_success:
                        logger.info("✅ Steps 4+6 completed successfully in parallel!")
                        # Mark Step 6 as completed (we'll still run Step 5 next)
                        current_step = 6  # Update to Step 6 so we can skip it when we reach it
                        save_video_status(status_filepath, {STATUS_KEY_LAST_COMPLETED_STEP: current_step})
                        # Note: We continue to Step 5 (voiceover) which depends on Step 4
                    else:
                        logger.error("❌ Parallel Steps 4+6 failed!")
                        overall_success = False
                        current_status[STATUS_KEY_STATE] = "failed"
                        save_video_status(status_filepath, current_status)
                        break
                else:
                    # Sequential mode: Run Step 4 alone
                    logger.info(f"📝 Creating scripts for {num_videos} selected profiles...")
                    all_scripts_success = True

                    for profile_key, profile_info in selected_profiles:  # Only selected profiles
                        profile_suffix = profile_info.get('suffix', profile_key)
                        script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_suffix}.txt"

                        if script_file.exists() and script_file.stat().st_size > 100:
                            logger.info(f"   ⚡ SMART SKIP: Found existing script for {profile_info['name']}")
                            logger.info(f"      → Skipping (delete {script_file.name} to regenerate)")
                            continue  # Skip this profile

                        logger.info(f"   Creating {profile_info['name']} script...")
                        script_success = run_ai_script_step_multi(folder_name, transcripts_dir, ai_scripts_dir,
                                                                  profile_info,
                                                                  api_key_gemini)
                        if not script_success:
                            all_scripts_success = False
                            logger.error(f"   ❌ Failed to create {profile_info['name']} script")
                        else:
                            logger.info(f"   ✅ Created {profile_info['name']} script")
                    step_success = all_scripts_success
            elif step_num == 5:
                # Generate voiceovers - check API mode first, then browser mode
                logger.info(f"🎤 Generating voiceovers for {num_videos} selected profiles...")

                # Check if using API method (reads from config at runtime)
                if is_using_api_method():
                    logger.info(f"🚀 Using Fish Audio API for voiceover generation...")
                    step_success = run_voiceover_api_parallel(folder_name, ai_scripts_dir, voiceovers_dir,
                                                              selected_profiles, temp_script_dir)
                elif USE_MULTI_WINDOW_VOICEOVER and ENABLE_PROFILE_PARALLEL_PROCESSING:
                    logger.info(
                        f"🚀 Multi-window browser mode: {len(selected_profiles)} browser windows will open simultaneously")
                    step_success = run_voiceover_step_multi_window(folder_name, ai_scripts_dir, voiceovers_dir,
                                                                   selected_profiles, temp_script_dir)
                else:
                    logger.info("🧠 Sequential browser mode: Processing profiles one by one")
                    all_voiceovers_success = True
                    for profile_key, profile_info in selected_profiles:  # Only selected profiles
                        logger.info(
                            f"   Generating {profile_info['name']} voiceover using {profile_info['default_voice']} voice...")
                        voiceover_success = run_voiceover_step_multi(folder_name, ai_scripts_dir, voiceovers_dir,
                                                                     profile_info, temp_script_dir)
                        if not voiceover_success:
                            all_voiceovers_success = False
                            logger.error(f"   ❌ Failed to generate {profile_info['name']} voiceover")
                        else:
                            logger.info(f"   ✅ Generated {profile_info['name']} voiceover")
                    step_success = all_voiceovers_success
            elif step_num == 6:
                # Skip check: If we just ran Step 4+6 in parallel, skip this
                if ENABLE_PARALLEL_STEPS and current_step > step_num:
                    logger.info("⚡ Skipping Step 6 (already completed in parallel with Step 4)")
                    continue
                # Normal Step 6 execution (sequential mode)
                # Smart skip: Check if B-roll clips already exist
                if rearranged_broll_clips_dir.exists():
                    existing_clips = list(rearranged_broll_clips_dir.glob("*.mp4"))
                    if len(existing_clips) > 0:
                        logger.info(
                            f"⚡ SMART SKIP: Found {len(existing_clips)} existing B-roll clips in {rearranged_broll_clips_dir}")
                        logger.info("   → Skipping B-roll generation (delete the folder to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 B-roll directory exists but is empty, proceeding with generation...")
                        step_success = run_broll_step(primary_clips_dir, rearranged_broll_clips_dir, voiceovers_dir, per_folder_broll)
                else:
                    step_success = run_broll_step(primary_clips_dir, rearranged_broll_clips_dir, voiceovers_dir, per_folder_broll)
            elif step_num == 7:
                # Smart skip: Check if final videos already exist for selected profiles
                all_assembly_success = True
                profiles_to_process = []

                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_suffix}"

                    if profile_final_dir.exists():
                        existing_videos = list(profile_final_dir.glob("*.mp4"))
                        if len(existing_videos) > 0:
                            logger.info(
                                f"   ⚡ SMART SKIP: Found {len(existing_videos)} existing final videos for {profile_info['name']}")
                            continue  # Skip this profile

                    # Add to processing list if not skipped
                    profiles_to_process.append((profile_key, profile_info))

                if profiles_to_process:
                    logger.info(f"🎬 Assembling final videos for {len(profiles_to_process)} profiles...")
                    for profile_key, profile_info in profiles_to_process:
                        logger.info(f"   Assembling {profile_info['name']} final video...")
                        assembly_success = run_assembly_step_multi(folder_name, voiceovers_dir,
                                                                   rearranged_broll_clips_dir,
                                                                   final_videos_dir, log_dir, profile_info)
                        if not assembly_success:
                            all_assembly_success = False
                            logger.error(f"   ❌ Failed to assemble {profile_info['name']} final video")
                        else:
                            logger.info(f"   ✅ Assembled {profile_info['name']} final video")
                else:
                    logger.info(f"⚡ SMART SKIP: All final videos already exist for selected profiles")
                    logger.info("   → Delete profile folders in final_videos directory to regenerate")

                step_success = all_assembly_success
            elif step_num == 8:
                # Rank video sequence for each profile separately (like Step 6)
                logger.info(f"🎯 Ranking video sequences for {num_videos} selected profiles...")
                all_ranking_success = True
                for profile_key, profile_info in selected_profiles:  # Only selected profiles
                    logger.info(f"   Ranking {profile_info['name']} sequence...")

                    # Create separate ranking folder for this profile
                    profile_ranking_dir = ranked_sequence_dir / f"{folder_name}_ranked_{profile_info['suffix']}"
                    profile_ranking_dir.mkdir(parents=True, exist_ok=True)

                    # Use the specific profile's final video folder and styled clips
                    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_info['suffix']}"
                    profile_styled_dir = styled_clips_dir / f"{folder_name}_styled_{profile_info['suffix']}"

                    ranking_success = run_ranking_step_multi(folder_name, profile_styled_dir, profile_final_dir,
                                                             profile_ranking_dir)
                    if not ranking_success:
                        all_ranking_success = False
                        logger.error(f"   ❌ Failed to rank {profile_info['name']} sequence")
                    else:
                        logger.info(f"   ✅ Ranked {profile_info['name']} sequence")
                step_success = all_ranking_success
            elif step_num == 9:
                # Step 9: Combine Ranked Videos for each profile
                logger.info(f"🎯 Running Step 9: Combine Ranked Videos for {num_videos} selected profiles...")
                all_combine_success = True
                for profile_key, profile_info in selected_profiles:  # Only selected profiles
                    logger.info(f"   Combining {profile_info['name']} ranked videos...")

                    # Use profile-specific directories like other steps
                    profile_ranked_dir = ranked_sequence_dir / f"{folder_name}_ranked_{profile_info['suffix']}"
                    profile_combined_dir = new_step9_dir / f"{folder_name}_combined_{profile_info['suffix']}"
                    profile_combined_dir.mkdir(parents=True, exist_ok=True)

                    # Get background music settings for this profile
                    background_music_path, voice_level, music_level = get_background_music_for_profile(profile_info)

                    # Build Step 9 arguments with background music
                    step9_args = [
                        "--input", str(profile_ranked_dir),
                        "--output", str(profile_combined_dir),
                        "--video-stem", folder_name,
                        "--voice-level", str(voice_level),
                        "--music-level", str(music_level)
                    ]

                    if background_music_path:
                        step9_args.extend([
                            "--enable-music",
                            "--background-music", str(background_music_path)
                        ])
                        logger.info(
                            f"🎵 {profile_info['name']}: Using background music: {Path(background_music_path).name}")
                    else:
                        logger.info(f"🔇 {profile_info['name']}: No background music")

                    combine_success = run_python_script(COMBINE_RANKED_SCRIPT, step9_args, capture_output=True)

                    if not combine_success:
                        all_combine_success = False
                        logger.error(f"   ❌ Failed to combine {profile_info['name']} ranked videos")
                    else:
                        logger.info(f"   ✅ Combined {profile_info['name']} ranked videos")
                step_success = all_combine_success
            elif step_num == 10:
                # ⭐ Upload to YouTube for each selected profile (was Step 11)
                youtube_uploads_dir = video_output_dir / SUBDIR_YOUTUBE_UPLOADS
                youtube_uploads_dir.mkdir(parents=True, exist_ok=True)

                # 🎨 Generate thumbnail BEFORE upload (for each profile)
                for profile_key, profile_info in selected_profiles:
                    # Check profile-specific folder first, then main folder
                    profile_output_dir = video_output_dir / profile_info['suffix']
                    if profile_output_dir.exists():
                        thumb_check_dir = profile_output_dir
                    else:
                        thumb_check_dir = video_output_dir

                    thumb_output_dir = thumb_check_dir / SUBDIR_YOUTUBE_UPLOADS if (thumb_check_dir / SUBDIR_YOUTUBE_UPLOADS).exists() else youtube_uploads_dir

                    # Check if thumbnail mode is OFF - skip generation if disabled
                    if THUMBNAIL_MODE and THUMBNAIL_MODE.lower() == 'off':
                        logger.info(f"⏭️ Thumbnail generation is OFF - skipping for {profile_info['name']}")
                    elif not (thumb_output_dir / "thumbnail_prompt.txt").exists():
                        logger.info(f"🎨 Generating thumbnail for {profile_info['name']}...")
                        run_thumbnail_generator_step(
                            folder_name, thumb_check_dir, profile_info,
                            mode=THUMBNAIL_MODE,
                            input_folder=input_folder_path
                        )

                # Filter profiles that have upload enabled
                upload_enabled_profiles = [
                    (profile_key, profile_info) for profile_key, profile_info in selected_profiles
                    if profile_info.get('enable_upload', True)
                ]

                upload_disabled_profiles = [
                    (profile_key, profile_info) for profile_key, profile_info in selected_profiles
                    if not profile_info.get('enable_upload', True)
                ]

                # Check which profiles are already uploaded (skip those)
                already_uploaded_profiles = []
                profiles_to_upload = []

                # Check main results file (10_youtube_upload.py saves all profiles to one file)
                main_results_file = youtube_uploads_dir / f"{folder_name}_youtube_uploads.json"
                main_results_data = {}

                if main_results_file.exists():
                    try:
                        with open(main_results_file, 'r', encoding='utf-8') as f:
                            main_results_data = json.load(f)
                    except (json.JSONDecodeError, Exception):
                        main_results_data = {}

                for profile_key, profile_info in upload_enabled_profiles:
                    profile_suffix = profile_info['suffix']
                    is_uploaded = False

                    # Check in main results file (nested structure)
                    # Format: {profile_name: {videos: [(filename, url), ...], uploaded_count: N}}
                    profile_data = main_results_data.get(profile_suffix, {})
                    if profile_data:
                        videos_list = profile_data.get("videos", [])
                        uploaded_count = profile_data.get("uploaded_count", 0)

                        # Only skip if videos were actually uploaded (has URLs or user confirmed)
                        if uploaded_count > 0 and videos_list:
                            # Check if any video has a valid result (URL or user confirmed)
                            has_valid_upload = any(
                                len(v) >= 2 and v[1] and (
                                    "youtube" in str(v[1]).lower() or
                                    "upload completed" in str(v[1]).lower()  # User closed browser = done
                                )
                                for v in videos_list
                            )
                            if has_valid_upload:
                                is_uploaded = True
                                logger.info(f"⏭️ Already uploaded: {profile_info['name']} - skipping")
                                for vid_name, vid_url in videos_list:
                                    logger.info(f"   URL: {vid_url}")

                    # Also check profile-specific file (legacy format)
                    if not is_uploaded:
                        results_file = youtube_uploads_dir / f"{folder_name}_youtube_uploads_{profile_suffix}.json"
                        if results_file.exists():
                            try:
                                with open(results_file, 'r', encoding='utf-8') as f:
                                    upload_data = json.load(f)
                                # Check if upload was successful (has video_id or success flag)
                                if upload_data.get("video_id") or upload_data.get("success") or upload_data.get("url"):
                                    is_uploaded = True
                                    logger.info(f"⏭️ Already uploaded: {profile_info['name']} - skipping")
                            except (json.JSONDecodeError, Exception) as e:
                                # File corrupted or invalid - re-upload
                                logger.warning(f"⚠️ Upload result file invalid for {profile_info['name']}, will re-upload")

                    if is_uploaded:
                        already_uploaded_profiles.append((profile_key, profile_info))
                    else:
                        # Not uploaded yet or failed - add to upload list
                        profiles_to_upload.append((profile_key, profile_info))

                logger.info(
                    f"🎯 Running Step 10: Upload to YouTube (Clean & Simple - NO metadata) for {len(profiles_to_upload)}/{num_videos} profiles...")

                # Log status
                if already_uploaded_profiles:
                    uploaded_names = [p[1]['name'] for p in already_uploaded_profiles]
                    logger.info(f"✅ Already uploaded (skipping): {', '.join(uploaded_names)}")

                if profiles_to_upload:
                    to_upload_names = [p[1]['name'] for p in profiles_to_upload]
                    logger.info(f"📤 Will upload: {', '.join(to_upload_names)}")

                if upload_disabled_profiles:
                    disabled_names = [p[1]['name'] for p in upload_disabled_profiles]
                    logger.info(f"⏭️ Upload disabled: {', '.join(disabled_names)}")

                all_upload_success = True

                if profiles_to_upload:
                    # Build list of profile names for the upload script (only ones that need upload)
                    profile_names = [profile_info['suffix'] for profile_key, profile_info in profiles_to_upload]

                    # Get maximum wait time from all enabled profiles
                    max_wait = max([profile_info.get('upload_wait_minutes', 5) for profile_key, profile_info in
                                    upload_enabled_profiles])

                    # Build arguments for YouTube upload script
                    youtube_args = [
                                       "--input", str(new_step9_dir),
                                       "--output", str(youtube_uploads_dir),
                                       "--video-stem", folder_name,
                                       "--profiles"
                                   ] + profile_names + [
                                       "--wait-minutes", str(max_wait)
                                   ]

                    logger.info(f"🎬 Uploading {len(profile_names)} profiles to YouTube (just upload - add metadata manually later)...")
                    logger.info(f"📝 Profiles: {', '.join(profile_names)} (works with ANY profile name - no hardcoding!)")

                    # Check if background upload is enabled
                    if ENABLE_BACKGROUND_UPLOAD:
                        # Start upload in background thread - allows next video to start processing immediately
                        logger.info(f"📤 [BACKGROUND UPLOAD] Starting background upload for {folder_name}...")
                        start_background_upload(
                            run_python_script,
                            (YOUTUBE_UPLOAD_SCRIPT, youtube_args, None, True),  # cwd=None, capture_output=True
                            folder_name
                        )
                        # Consider step successful - upload continues in background
                        upload_success = True
                        all_upload_success = True
                        logger.info(f"📤 [BACKGROUND UPLOAD] Upload started in background - pipeline continues!")
                    else:
                        # Original synchronous upload
                        upload_success = run_python_script(YOUTUBE_UPLOAD_SCRIPT, youtube_args, capture_output=True)
                        all_upload_success = upload_success
                else:
                    # No profiles to upload - either all uploaded already or all disabled
                    if already_uploaded_profiles:
                        logger.info("✅ All profiles already uploaded - nothing to do!")
                    else:
                        logger.info("⏭️ No profiles have upload enabled - skipping YouTube upload")
                    upload_success = True  # Consider it successful

                # Create skip results for disabled profiles
                for profile_key, profile_info in upload_disabled_profiles:
                    results_file = youtube_uploads_dir / f"{folder_name}_youtube_uploads_{profile_info['suffix']}.json"
                    results_file.write_text('{"skipped": "Upload disabled for this profile"}')

                step_success = all_upload_success

                if already_uploaded_profiles and not profiles_to_upload:
                    logger.info(f"   ✅ All videos already uploaded - skipped re-upload")
                elif ENABLE_BACKGROUND_UPLOAD and profiles_to_upload:
                    logger.info(f"   ✅ Upload started in background for {folder_name}")
                    logger.info(f"   📤 Upload will complete while next video processes")
                elif not upload_success:
                    logger.error(f"   ❌ Failed to upload videos to YouTube")
                else:
                    logger.info(f"   ✅ Successfully uploaded all videos to YouTube as UNLISTED")
                    logger.info(f"   🎨 Thumbnail prompts saved to {SUBDIR_YOUTUBE_UPLOADS}/thumbnail_prompt.txt")
                    logger.info(f"   👨‍💻 Next: Create thumbnails and make videos public manually")

                step_success = upload_success

        except Exception as e:
            logger.error(f"❌ Step {step_num} failed with error: {e}")
            step_success = False

        if step_success:
            logger.info(f"✅ Step {step_num} completed: {step_info['name']}")
            current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num
            current_step = step_num  # Update current_step tracker
            save_video_status(status_filepath, current_status)
        else:
            logger.error(f"❌ Pipeline failed at Step {step_num}: {step_info['name']}")
            overall_success = False
            current_status[STATUS_KEY_STATE] = "failed"
            save_video_status(status_filepath, current_status)
            break

    if temp_script_dir.exists():
        try:
            shutil.rmtree(temp_script_dir)
        except Exception as e:
            logger.warning(f"Failed to remove temp script folder: {e}")

    if overall_success:
        current_status[STATUS_KEY_STATE] = "completed"
        current_status[STATUS_KEY_LAST_COMPLETED_STEP] = max(pipeline_steps_info.keys())
        save_video_status(status_filepath, current_status)
        logger.info(f"\n{'=' * 80}\n✨ NUMBERED PIPELINE COMPLETE for: {video_path.name}")
        logger.info(f"📹 Created {num_videos} final video{'s' if num_videos > 1 else ''}:")
        for profile_key, profile_info in selected_profiles:
            logger.info(f"   • {profile_info['name']} using {profile_info['default_voice']} voice")
        logger.info(f"{'=' * 80}")
    else:
        logger.info(f"\n{'=' * 80}\n🛑 NUMBERED PIPELINE FAILED for: {video_path.name}\n{'=' * 80}")

    return overall_success


# ==============================================================================
# --- MAIN FUNCTION (FIXED) ---
# ==============================================================================

def main():
    global PROMPT_PROFILES, UI_MODE
    parser = argparse.ArgumentParser(
        description="Smart video processing orchestrator with numbered selection system.",
        epilog="""
USAGE EXAMPLES:
  Original single folder mode (output by video names):
    python control-2.py --input-folder "D:\\videos\\sports"

  Multi-folder mode (output by folder names):
    python control-2.py --input-folders "D:\\videos\\sports" "D:\\videos\\news" "D:\\videos\\tutorials"

  Custom output directory:
    python control-2.py --input-folders "D:\\videos\\folder1" "D:\\videos\\folder2" --output-base-dir "D:\\MyProjects"

OUTPUT STRUCTURE:
  Single folder mode (original): OutputDir/video1/, OutputDir/video2/
  Multi-folder mode (new): OutputDir/sports/, OutputDir/news/, OutputDir/tutorials/
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--input-folder', type=Path, default=DEFAULT_INPUT_VIDEOS_FOLDER,
                        help=f"Path to folder containing original video files. Default: {DEFAULT_INPUT_VIDEOS_FOLDER}")
    parser.add_argument('--input-folders', type=Path, nargs='+', default=None,
                        help=f"MULTI-FOLDER MODE: Path(s) to multiple folders containing video files. EXAMPLES: --input-folders \"D:\\videos\\sports\" \"D:\\videos\\news\" \"D:\\videos\\tutorials\"")
    parser.add_argument('--output-base-dir', type=Path, default=DEFAULT_PROJECT_OUTPUT_BASE_DIR,
                        help=f"Base directory where all processed video project folders will be created. Default: {DEFAULT_PROJECT_OUTPUT_BASE_DIR}")
    parser.add_argument('--gemini-api-key', type=str, default=None, help="Google Gemini API Key.")
    parser.add_argument('--start-step', type=int, default=-1,
                        help="Force start from specific step (0-10). Use -1 for auto-skip mode (default).")
    parser.add_argument('--profile', type=str, default=None,
                        help="Profile name to use (bypasses interactive selection). Example: --profile BASKLY")
    parser.add_argument('--profile-count', type=int, default=None,
                        help="Number of profiles to use (1, 2, 3, etc.). Uses first N profiles from config. Example: --profile-count 3")
    parser.add_argument('--profiles', type=str, nargs='+', default=None,
                        help="Multiple profile names to use (bypasses interactive selection). Example: --profiles StrikeX MMA-STAR")
    parser.add_argument('--manual-crop', action='store_true', default=False,
                        help="Enable manual crop tool for video cropping instead of AI auto-crop")

    args = parser.parse_args()

    # Override manual crop setting if --manual-crop flag is passed
    global USE_MANUAL_CROP_DEFAULT
    if args.manual_crop:
        USE_MANUAL_CROP_DEFAULT = True
        print("✂️ Manual crop mode enabled via command line")

    # Detect UI mode: when --profile, --profiles, or --profile-count is specified, we're running from UI (non-interactive)
    UI_MODE = args.profile is not None or args.profile_count is not None or args.profiles is not None

    # Get processing configuration
    processing_config = determine_processing_mode(args.profile, args.profile_count, args.profiles)

    # Handle step selection
    if args.start_step == -1:
        # If profile, profiles, or profile-count was specified (UI mode), use auto-skip without interactive menu
        if args.profile or args.profile_count or args.profiles:
            force_start_from_value = -1  # Auto-skip mode
            print("📋 Using auto-skip mode (will skip completed steps)")
        else:
            # Interactive step selection menu
            force_start_from_value = display_step_selection_menu()
    else:
        force_start_from_value = args.start_step

    # Handle profile restoration for single profile mode
    restore_profiles = processing_config.get("restore_profiles", None)

    # Load API keys
    json_api_keys = load_api_keys_from_json_file(API_KEYS_FILE)
    # Support both old format (google_gemini_api_key) and new format (gemini.api_key)
    gemini_key_from_json = (
        json_api_keys.get("gemini", {}).get("api_key") or
        json_api_keys.get("google_gemini_api_key")
    )
    final_gemini_api_key = (
            args.gemini_api_key or gemini_key_from_json or os.environ.get("GOOGLE_API_KEY", ""))

    # Display configuration
    logger.info(f"\n{'#' * 80}")
    logger.info(f"🤖 Starting Smart Video Processing Orchestrator")
    logger.info(f"{'#' * 80}")
    # Determine processing mode - prioritize script configuration
    if USE_MULTI_FOLDER_MODE:
        # Use predefined multi-folder configuration from script
        if not MULTI_INPUT_FOLDERS:
            logger.error("❌ USE_MULTI_FOLDER_MODE is True but MULTI_INPUT_FOLDERS is empty!")
            logger.error("   Please add folder paths to MULTI_INPUT_FOLDERS in the script configuration.")
            sys.exit(1)

        input_folders = MULTI_INPUT_FOLDERS
        multi_folder_mode = True
        logger.info(f"📁 Script Multi-Folder Mode: {len(input_folders)} folders (configured in script)")
        for folder in input_folders:
            logger.info(f"   📂 {folder}")
    elif args.input_folders:
        # Multi-folder mode from command line
        input_folders = args.input_folders
        multi_folder_mode = True
        logger.info(f"📁 Command Multi-Folder Mode: {len(input_folders)} folders")
        for folder in input_folders:
            logger.info(f"   📂 {folder}")
    else:
        # Single folder mode (original behavior)
        input_folders = [args.input_folder]
        multi_folder_mode = False
        logger.info(f"📁 Single Folder Mode: {args.input_folder}")

    logger.info(f"📂 Project Output Base Dir: {args.output_base_dir}")

    num_videos = processing_config["count"]
    logger.info(f"🎬 Processing: Will create {num_videos} video{'s' if num_videos > 1 else ''}")
    selected_profiles = list(PROMPT_PROFILES.items())[:num_videos]
    for profile_key, profile_info in selected_profiles:
        logger.info(f"   • {profile_info['name']} → {profile_info['default_voice']} voice")

    logger.info(f"🔑 API Keys: Gemini={'Yes' if final_gemini_api_key else 'No'}")
    logger.info(f"🚀 Force start step: {force_start_from_value if force_start_from_value != -1 else 'Auto'}")
    logger.info(f"📊 Fish Audio Settings: {FISH_AUDIO_NUM_TABS} tabs")
    logger.info(f"📝 Orchestrator Log: {ORCHESTRATOR_LOG_FILE_NAME}")
    logger.info(f"{'#' * 80}\n")

    # Validate inputs and collect all video files from all folders
    all_video_files = []
    for input_folder in input_folders:
        if not input_folder.is_dir():
            logger.error(f"❌ Input folder not found: {input_folder}")
            continue

        # Find video files in this folder
        folder_video_files = [f for f in input_folder.iterdir() if
                              f.is_file() and f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
                                                                   '.webm']]

        if not folder_video_files:
            logger.warning(f"❌ No video files found in: {input_folder}")
            continue

        # Create tuples of (video_file, folder_name) for output naming
        for video_file in folder_video_files:
            if multi_folder_mode:
                # Use folder name for output in multi-folder mode
                output_name = input_folder.name
            elif USE_FOLDER_NAME_FOR_OUTPUT:
                # Use folder name when configured (cleaner output structure)
                output_name = input_folder.name
            else:
                # Use video name for output in single folder mode (original behavior)
                output_name = video_file.stem
            all_video_files.append((video_file, output_name))

        logger.info(f"📹 Found {len(folder_video_files)} videos in folder: {input_folder.name}")

    if not all_video_files:
        logger.error("❌ No video files found in any input folder!")
        sys.exit(1)

    all_video_files.sort(key=lambda x: x[0].name)  # Sort by video filename
    total_videos = len(all_video_files)
    successful_videos = 0

    # Process videos sequentially
    for i, (video_file, output_name) in enumerate(all_video_files):
        logger.info(f"\n{'=' * 80}")
        if multi_folder_mode:
            logger.info(f"STARTING VIDEO {i + 1}/{total_videos}: {video_file.name} from folder '{output_name}'")
        else:
            logger.info(f"STARTING VIDEO {i + 1}/{total_videos}: {video_file.name}")
        logger.info(f"{'=' * 80}")

        # All modes now use numbered pipeline - single profile is just numbered with count=1
        # Pass input_folder_path for per-folder B-roll settings
        input_folder_path = video_file.parent
        success = process_video_pipeline_numbered(video_file, output_name, args.output_base_dir, final_gemini_api_key,
                                                  processing_config["count"], force_start_from_value, input_folder_path)

        if success:
            successful_videos += 1

        if multi_folder_mode:
            logger.info(
                f"FINISHED VIDEO {i + 1}/{total_videos}: {video_file.name} from '{output_name}'. Success: {'YES' if success else 'NO'}")
        else:
            logger.info(
                f"FINISHED VIDEO {i + 1}/{total_videos}: {video_file.name}. Success: {'YES' if success else 'NO'}")
        time.sleep(2)

    # Restore original profiles if this was single profile mode
    if restore_profiles:
        PROMPT_PROFILES.clear()
        PROMPT_PROFILES.update(restore_profiles)

    # Wait for any background uploads to complete before showing final summary
    if ENABLE_BACKGROUND_UPLOAD:
        logger.info(f"\n{'=' * 80}")
        logger.info("📤 Waiting for background uploads to complete...")
        logger.info(f"{'=' * 80}")
        wait_for_all_background_uploads()

    # Final summary
    total_output_videos = successful_videos * processing_config["count"]

    logger.info(f"\n{'#' * 80}")
    logger.info(f"🚀 ORCHESTRATION COMPLETE")
    logger.info(f"{'#' * 80}")
    if multi_folder_mode:
        logger.info(
            f"📊 Total Input Videos: {total_videos} from {len(input_folders)} folder{'s' if len(input_folders) > 1 else ''}")
        logger.info(f"📁 Output organized by SOURCE FOLDER NAMES")
    else:
        logger.info(f"📊 Total Input Videos: {total_videos}")
        logger.info(f"📁 Output organized by video filenames (original mode)")

    logger.info(f"✅ Successfully Processed: {successful_videos}")
    logger.info(f"❌ Failed to Process: {total_videos - successful_videos}")
    logger.info(f"🎬 Total Output Videos Created: {total_output_videos}")
    logger.info(
        f"📝 Processing: {processing_config['count']} video{'s' if processing_config['count'] > 1 else ''} per input")

    logger.info(f"💡 System is expandable: Add new prompts to PROMPT_PROFILES and they automatically appear as options!")
    logger.info(f"📄 Full log: {ORCHESTRATOR_LOG_FILE_NAME}")
    logger.info(f"{'#' * 80}")


if __name__ == "__main__":
    main()