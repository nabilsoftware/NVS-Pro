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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Thread lock for module loading to prevent I/O conflicts in parallel processing
_MODULE_LOAD_LOCK = threading.Lock()
_SMART_PROCESSOR_MODULE = None  # Pre-loaded module cache

# Thread locks for YouTube upload - one lock per channel to prevent browser profile conflicts
# When multiple videos upload to the same channel, they must wait for each other
_CHANNEL_UPLOAD_LOCKS = {}
_CHANNEL_LOCKS_LOCK = threading.Lock()  # Lock for creating channel locks

def get_channel_upload_lock(channel_name: str) -> threading.Lock:
    """Get or create a lock for uploading to a specific channel.
    This ensures only one upload at a time per channel (same browser profile).
    """
    with _CHANNEL_LOCKS_LOCK:
        if channel_name not in _CHANNEL_UPLOAD_LOCKS:
            _CHANNEL_UPLOAD_LOCKS[channel_name] = threading.Lock()
        return _CHANNEL_UPLOAD_LOCKS[channel_name]


# ==============================================================================
# FOLDER LOGGER - Adds folder prefix to all log messages for parallel processing
# ==============================================================================
class FolderLogger:
    """Logger wrapper that adds folder prefix to all messages for clear parallel logs"""
    def __init__(self, base_logger, folder_name: str):
        self._logger = base_logger
        self._prefix = f"[{folder_name}]"
        self.folder_name = folder_name

    def info(self, msg):
        self._logger.info(f"{self._prefix} {msg}")

    def warning(self, msg):
        self._logger.warning(f"{self._prefix} {msg}")

    def error(self, msg):
        self._logger.error(f"{self._prefix} {msg}")

    def debug(self, msg):
        self._logger.debug(f"{self._prefix} {msg}")


# Try to import google.generativeai, but don't fail if not available
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# ==============================================================================
# 🎛️ CONFIG LOADER - READS FROM config.json
# ==============================================================================

# Base directory where this orchestrator script resides
SCRIPT_DIR = Path(__file__).parent.resolve()

# Ensure bundled FFmpeg is on PATH (for fresh installs without system FFmpeg)
_assets_bin = SCRIPT_DIR / "assets" / "bin"
if _assets_bin.exists():
    os.environ["PATH"] = str(_assets_bin) + ";" + os.environ.get("PATH", "")

def get_user_data_dir() -> Path:
    """Get user data directory (same as UI)"""
    if os.name == 'nt':
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        user_dir = Path(appdata) / "NabilVideoStudioPro"
    else:
        user_dir = Path.home() / ".nvspro"
    return user_dir

def is_using_api_method():
    """Check if user selected API method in settings (reads fresh from config)"""
    config_path = get_user_data_dir() / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                method = config.get("voiceover_settings", {}).get("method", "Fish Audio (Browser)")
                return "API" in method.upper()
        except:
            pass
    return False

# Try user data dir first, then script dir
USER_CONFIG_FILE = get_user_data_dir() / "config.json"
SCRIPT_CONFIG_FILE = SCRIPT_DIR / "config.json"
CONFIG_FILE = USER_CONFIG_FILE if USER_CONFIG_FILE.exists() else SCRIPT_CONFIG_FILE

def load_config():
    """Load configuration from config.json (user data dir first, then script dir)"""
    if USER_CONFIG_FILE.exists():
        with open(USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    if SCRIPT_CONFIG_FILE.exists():
        with open(SCRIPT_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_api_keys():
    """Load API keys from api_keys.json (user data dir first, then script dir)"""
    user_api_keys_file = get_user_data_dir() / "api_keys.json"
    script_api_keys_file = SCRIPT_DIR / "api_keys.json"

    if user_api_keys_file.exists():
        with open(user_api_keys_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    if script_api_keys_file.exists():
        with open(script_api_keys_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Load config
_CONFIG = load_config()
_API_KEYS = load_api_keys()
_CC_CONFIG = _CONFIG.get('content_creator', {})
# Use cc_ai_settings for Create Video, fallback to ai_settings
_AI_SETTINGS = _CONFIG.get('cc_ai_settings', {}) or _CONFIG.get('ai_settings', {})

# === DEFAULT INPUT/OUTPUT FOLDERS (FROM CONFIG) ===
DEFAULT_INTERVIEWS_FOLDER = Path(_CC_CONFIG.get('interviews_folder', './input')) if _CC_CONFIG.get('interviews_folder') else Path('./input')
DEFAULT_BROLL_FOLDER = Path(_CC_CONFIG.get('broll_folder', './broll')) if _CC_CONFIG.get('broll_folder') else Path('./broll')
DEFAULT_PROJECT_OUTPUT_BASE_DIR = Path(_CC_CONFIG.get('output_folder', './output')) if _CC_CONFIG.get('output_folder') else Path('./output')
# Legacy support
DEFAULT_INPUT_VIDEOS_FOLDER = DEFAULT_INTERVIEWS_FOLDER

# === MULTI-FOLDER MODE SETTINGS (FROM CONFIG) ===
USE_MULTI_FOLDER_MODE = _CONFIG.get('multi_folder_mode', {}).get('enabled', False)
MULTI_INPUT_FOLDERS = [Path(p) for p in _CONFIG.get('multi_folder_mode', {}).get('input_folders', [])]

# === AI PROVIDER SETTINGS (FROM CONFIG & API_KEYS) ===
AI_PROVIDER = _AI_SETTINGS.get('provider', 'claude')
AI_GOOGLE_MODEL = _AI_SETTINGS.get('google_model', 'gemini-2.5-flash-preview-05-20')
AI_CLAUDE_MODEL = _AI_SETTINGS.get('claude_model', 'claude-sonnet-4-5-20250929')
# Support both flat keys (gemini_api_key) and nested keys (gemini.api_key)
GEMINI_API_KEY = _API_KEYS.get('gemini_api_key', '') or _API_KEYS.get('gemini', {}).get('api_key', '')
CLAUDE_API_KEY = _API_KEYS.get('claude_api_key', '') or _API_KEYS.get('claude', {}).get('api_key', '')
OPENAI_API_KEY = _API_KEYS.get('openai_api_key', '') or _API_KEYS.get('openai', {}).get('api_key', '')

# === LOAD PROFILES FROM CONFIG ===
def load_profiles_from_config():
    """Load profiles from config.json and convert to content_creator format"""
    profiles = {}
    config_profiles = _CONFIG.get('profiles', {})

    for name, profile in config_profiles.items():
        profiles[name] = {
            "name": profile.get('name', name),
            "description": profile.get('description', ''),
            "prompt_file": SCRIPT_DIR / profile.get('cc_prompt_file', f'prompts/{name}-CC-PROMPT.txt'),
            "default_voice": profile.get('default_voice', 'VOICE1'),
            "suffix": profile.get('suffix', name),
            "background_video": profile.get('background_video', ''),
            "frame_color": profile.get('frame_color', '#888683'),
            "video_scale": profile.get('video_scale', 0.85),
            "use_manual_crop": profile.get('use_manual_crop', False),
            "background_music": profile.get('background_music', ''),
            "voice_level": profile.get('voice_level', 1.0),
            "music_level": profile.get('music_level', 0.1),
            "youtube_channel": profile.get('youtube_channel', ''),
            "browser_profile": profile.get('browser_profile', name),
            "enable_upload": profile.get('enable_upload', False),
            "upload_privacy": profile.get('upload_privacy', 'private'),
            "upload_wait_minutes": profile.get('upload_wait_minutes', 5)
        }

    return profiles

def load_voices_from_config():
    """Load voices from config.json"""
    return _CONFIG.get('voices', {})

PROMPT_PROFILES = load_profiles_from_config()
AVAILABLE_VOICES = load_voices_from_config()
# === STEP 1: SMART INTERVIEW PROCESSOR SETTINGS (FROM CONFIG) ===
_step1_config = _CC_CONFIG.get('step_1_settings', {})
GEMINI_SETTINGS = {
    "min_interview_clips": _step1_config.get('min_interview_clips', 5),
    "max_interview_clips": _step1_config.get('max_interview_clips', 10),
    "interview_length_min": _step1_config.get('interview_length_min', 12),
    "interview_length_max": _step1_config.get('interview_length_max', 40),
    "total_target_minutes": _step1_config.get('total_target_minutes', 17),
    "require_interviews": _step1_config.get('require_interviews', True),
    "force_alternating": _step1_config.get('force_alternating', True),
    "temperature": _step1_config.get('temperature', 0.7),
}

# === FFmpeg CLIP EXTRACTION SETTINGS ===
CLIP_EXTRACTION_SETTINGS = {
    "video_codec": "libx264",  # Video encoding codec
    "audio_codec": "aac",  # Audio encoding codec
    "preset": "fast",  # Encoding speed (ultrafast, fast, medium, slow)
    "crf": 23,  # Quality (18=high quality, 23=good, 28=lower)
    "seek_offset": 0.5,  # Skip first N seconds to avoid black screens1
    "end_offset": 0.2,  # Stop N seconds early to avoid cutoffs
    "use_gpu": True,  # Use GPU for Whisper transcription - ENABLED for speed
    "whisper_model": "base",  # Whisper model size (tiny, base, small, medium, large) - base for better accuracy
}

# === QUALITY & PERFORMANCE SETTINGS ===
QUALITY_SETTINGS = {
    "transcription_model": "small",  # Whisper model size (tiny, base, small, medium, large) - small for speed+accuracy
    "transcription_device": "cuda",  # Device for Whisper (cuda, cpu) - GPU for speed
    "max_parallel_processes": 4,  # Max concurrent operations
    "temp_cleanup": True,  # Clean temporary files after processing
}

# === ERROR HANDLING SETTINGS ===
ERROR_SETTINGS = {
    "continue_on_clip_error": True,  # Continue if individual clip fails
    "max_retries_per_step": 2,  # Retry failed steps N times
    "skip_existing_outputs": True,  # Smart skip if outputs already exist
    "backup_on_failure": False,  # Backup partial results on failure
}

# === STEP 2: INTERVIEW STYLING SETTINGS ===
# Load sound effect settings from config
_SFX_SETTINGS = _CONFIG.get('sound_effect_settings', {})

STYLING_SETTINGS = {
    # Visual settings
    "video_width_scale": 0.85,  # Video size scale (0.1-1.0)
    "frame_color": "#888683",  # Frame color (hex color)
    "frame_thickness": 15,  # Frame border thickness in pixels
    "video_position": "center",  # Video position: left, right, center

    # Animation settings
    "enable_animation": True,  # Enable slide animation
    "animation_duration": 0.8,  # Animation duration in seconds
    "animation_type": "slide",  # slide, slide_fade, slide_scale
    "slide_direction": "left",  # left, right, top, bottom

    # Sound effect settings (loaded from config)
    "enable_sound_effect": _SFX_SETTINGS.get('enabled', False),
    "sound_effect_path": _SFX_SETTINGS.get('file_path', ''),
    "sound_effect_volume": _SFX_SETTINGS.get('volume', 1.0),
    "sound_effect_duration": _SFX_SETTINGS.get('duration', 0.8),

    # Background settings
    "background_path": "",

    # Quality settings
    "gpu_quality": 22,  # GPU encoding quality (lower = better)
    "cpu_quality": 23,  # CPU encoding quality (lower = better)
}

# === STEP 3: VOICEOVER GENERATION SETTINGS ===
VOICEOVER_SETTINGS = {
    "generation_timeout": 300,  # Max seconds to wait per voiceover
    "retry_attempts": 3,  # Retry failed generations
    "use_multi_window": True,  # Use multi-window parallel processing
    "enable_parallel": True,  # Enable parallel profile processing
    "tabs_per_window": "auto",  # Number of tabs per window ("auto" or specific number)
    "window_spacing": 2,  # Seconds between opening windows
    "close_tabs_when_done": True,  # Auto-close tabs after completion
}

# === STEP 4: B-ROLL REARRANGEMENT SETTINGS ===
BROLL_REARRANGEMENT_SETTINGS = {
    "clip_duration": 6.0,  # Target duration for each B-roll clip (seconds)
    "overlap_handling": "trim",  # How to handle overlapping clips: "trim", "skip", "merge"
    "quality_preset": "medium",  # FFmpeg quality preset
    "preserve_aspect_ratio": True,  # Maintain original aspect ratio
    "shuffle_clips": True,  # Randomize B-roll clip order
    "max_clips": 200,  # Maximum number of clips to generate (prevents excessive clips)
}

# === STEP 5: VIDEO ASSEMBLY SETTINGS ===
ASSEMBLY_SETTINGS = {
    "use_fast_copy": False,  # Use fast copy vs quality encoding
    "use_gpu_acceleration": True,  # Enable CUDA GPU acceleration for video assembly
    "gpu_codec": "h264_nvenc",  # NVIDIA GPU codec (h264_nvenc, hevc_nvenc)
    "video_resolution": "1920x1080",  # Target resolution
    "quality_preset": "fast",  # FFmpeg quality preset - faster for GPU
    "audio_normalization": True,  # Normalize audio levels
    "crossfade_duration": 0.2,  # Crossfade between clips (seconds)
    "background_music_volume": 0.15,  # Background music volume if enabled
    "max_clips": 999999,  # Use ALL available clips (remove 44 clip limit)
}

# === STEP 6: VIDEO RANKING/SEQUENCE SETTINGS ===
RANKING_SETTINGS = {
    "alternating_pattern": True,  # Force interview/voiceover alternating
    "start_with_interview": True,  # Start sequence with interview (True) or voiceover (False)
    "number_padding": 3,  # Number of digits in filenames (001, 002, etc.)
    "create_sequence_info": True,  # Generate sequence_info.json file
    "ranking_prefix_interview": "interview",  # Prefix for interview files
    "ranking_prefix_voiceover": "voiceover",  # Prefix for voiceover files
}

# === STEP 7: VIDEO COMBINATION SETTINGS (YOUTUBE OPTIMIZED) ===
COMBINATION_SETTINGS = {
    # Processing mode - OPTIMIZED FOR YOUTUBE & PREMIERE PRO
    "fast_gpu_mode": True,  # Use fast GPU mode without music for maximum speed
    "enable_background_music": True,  # Background music ENABLED with profile-specific settings

    # Video encoding settings (YouTube optimized)
    "output_codec": "h264_nvenc",  # GPU encoding (YouTube recommended: H.264)
    "output_preset": "fast",  # NVENC preset - fast for speed (p4=balanced, slow=quality)
    "output_crf": 20,  # Higher quality for YouTube (18=highest, 20=excellent, 23=good)
    "output_format": "mov",  # MOV format (Premiere Pro optimized)
    "output_profile": "high",  # H.264 profile for best compatibility
    "output_level": "4.1",  # H.264 level for 1080p support

    # YouTube recommended video settings
    "video_bitrate": None,  # Let CRF control quality (None = CRF mode)
    "max_bitrate": "8000k",  # Maximum bitrate for 1080p YouTube
    "buffer_size": "12000k",  # Buffer size (1.5x max_bitrate)
    "frame_rate": "preserve",  # Keep original frame rate
    "pixel_format": "yuv420p",  # YouTube compatible pixel format

    # Audio settings (Adobe Premiere Pro compatible)
    "audio_codec": "aac",  # AAC codec (YouTube/Premiere standard)
    "audio_sample_rate": 48000,  # 48kHz (professional standard, Premiere compatible)
    "audio_bitrate": "320k",  # High quality audio bitrate
    "audio_channels": 2,  # Stereo audio
    "audio_normalize": True,  # Normalize audio levels for consistency

    # Audio normalization settings
    "enable_audio_normalization": True,  # Enable/disable audio normalization
    "audio_level": 3,  # Audio normalization level (1-4: 1=quiet, 2=normal, 3=loud, 4=very loud)
    "normalization_method": "dynaudnorm",  # Normalization method: "loudnorm" or "dynaudnorm"

    # GPU acceleration settings
    "use_gpu_acceleration": True,  # Enable CUDA GPU acceleration
    "enable_fallback": True,  # Enable automatic fallback (GPU -> CPU) if GPU fails
    "cuda_device": 0,  # CUDA device ID (0 = first GPU)

    # YouTube upload optimization
    "faststart": True,  # Enable fast start for web streaming
    "optimize_for_streaming": True,  # Optimize file structure for YouTube
    "metadata_title": True,  # Include video title in metadata

    # Performance optimization
    "concat_method": "ffmpeg_concat",  # Use FFmpeg concat demuxer (fastest method)
    "temp_cleanup": True,  # Clean temporary files after processing
    "verify_output": True,  # Verify output file integrity
}

# === STEP 8: YOUTUBE UPLOAD SETTINGS ===
YOUTUBE_UPLOAD_SETTINGS = {
    # Upload configuration
    "auto_upload": False,  # Enable automatic upload after generation
    "upload_delay": 5,  # Delay in seconds between actions (for stability)
    "use_browser_profiles": True,  # Use browser profiles for different channels
    "browser": "chrome",  # Browser to use: "chrome", "firefox", "edge"

    # Upload defaults (can be overridden by profile settings)
    "privacy": "private",  # Default privacy: "private", "unlisted", "public"
    "category": "Sports",  # Default YouTube category
    "tags_from_script": True,  # Extract tags from video script
    "max_tags": 15,  # Maximum number of tags to use

    # Schedule settings
    "schedule_uploads": False,  # Enable scheduled uploads
    "schedule_time": "10:00",  # Default upload time (24h format)
    "schedule_days": ["Mon", "Wed", "Fri"],  # Days to schedule uploads

    # Notification settings
    "notify_on_success": True,  # Show notification on successful upload
    "notify_on_failure": True,  # Show notification on failed upload
    "log_upload_history": True,  # Keep log of all uploads

    # Safety settings
    "dry_run": False,  # Test mode - don't actually upload
    "require_confirmation": True,  # Ask for confirmation before upload
    "max_retries": 3,  # Max retries on failure
}

# === PARALLEL PROCESSING SETTINGS ===
# Enable parallel step execution for faster processing
# Read from processing_settings where the setting is actually stored in config.json
_PROCESSING_SETTINGS = _CONFIG.get('processing_settings', {})
ENABLE_PARALLEL_STEPS = _PROCESSING_SETTINGS.get('enable_parallel_steps', True)
# Step 1 (Interview) + Step 4 (B-roll) can run together since B-roll is provided by user
# Step 2 (Styling) + Step 3 (Voiceover) can run together after Step 1 finishes

# === PARALLEL FOLDER PROCESSING (NEW - Idea 1) ===
# When enabled, multiple video folders are processed simultaneously
# Each folder gets its own browser window for voiceover (no blocking!)
ENABLE_PARALLEL_FOLDERS = _PROCESSING_SETTINGS.get('enable_parallel_folders', True)
MAX_PARALLEL_FOLDERS = _PROCESSING_SETTINGS.get('max_parallel_folders', 4)  # Process 4 folders at once (optimized)

# === BACKGROUND UPLOAD SETTINGS ===
# When enabled, upload step runs in background while next video starts processing
ENABLE_BACKGROUND_UPLOAD = _CC_CONFIG.get('enable_background_upload', True)
# Track background upload threads
_background_upload_threads = []
_background_upload_lock = threading.Lock()

# === YOUTUBE UPLOAD SHARED BROWSER ===
# YouTube uploads use a SHARED browser with multiple tabs (not multiple browsers)
# This allows parallel uploads while using the same login session:
# - One browser with cookies/login
# - Each video opens in a new tab
# - All tabs upload simultaneously
_youtube_shared_browsers = {}  # profile_name -> driver instance
_youtube_browser_lock = threading.Lock()  # Lock for accessing shared browsers dict


# ==============================================================================
# 🚀 PARALLEL STEP EXECUTION FUNCTION
# ==============================================================================

def run_steps_in_parallel(step_tasks: List[Dict]) -> bool:
    """
    Run multiple pipeline steps in parallel using threading.

    Args:
        step_tasks: List of dicts with format:
            {'name': 'Step Name', 'function': callable, 'args': tuple}

    Returns:
        True if all steps succeeded, False if any failed
    """
    if not step_tasks:
        return True

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
            logger.error(f"❌ Exception in parallel step {step_name}: {e}")
            results[step_name] = False

    # Start all threads
    for task in step_tasks:
        t = threading.Thread(
            target=run_step_with_result,
            args=(task['name'], task['function'], task['args'])
        )
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Check results
    all_success = all(results.values())

    if all_success:
        logger.info(f"🎉 All {len(step_tasks)} parallel steps completed successfully!")
    else:
        failed_steps = [name for name, success in results.items() if not success]
        logger.error(f"❌ {len(failed_steps)} parallel step(s) failed: {', '.join(failed_steps)}")

    return all_success


def start_background_upload(upload_func, upload_args, video_name: str):
    """
    Start upload in background thread so next video can begin processing.

    Args:
        upload_func: The upload function to call
        upload_args: Arguments for the upload function
        video_name: Name of video being uploaded (for logging)
    """
    def upload_wrapper():
        try:
            logger.info(f"📤 [BACKGROUND] Starting upload for: {video_name}")
            result = upload_func(*upload_args)
            if result:
                logger.info(f"✅ [BACKGROUND] Upload completed for: {video_name}")
            else:
                logger.error(f"❌ [BACKGROUND] Upload failed for: {video_name}")
            return result
        except Exception as e:
            logger.error(f"❌ [BACKGROUND] Upload error for {video_name}: {e}")
            return False

    thread = threading.Thread(target=upload_wrapper, name=f"upload_{video_name}")
    thread.start()

    with _background_upload_lock:
        _background_upload_threads.append((thread, video_name))

    logger.info(f"🚀 [BACKGROUND] Upload started in background for: {video_name}")
    logger.info(f"   → Continuing to next video while upload runs...")


def wait_for_all_background_uploads():
    """Wait for all background uploads to complete at the end of processing."""
    with _background_upload_lock:
        pending_uploads = list(_background_upload_threads)

    if not pending_uploads:
        return

    logger.info(f"\n{'=' * 80}")
    logger.info(f"⏳ Waiting for {len(pending_uploads)} background upload(s) to complete...")
    logger.info(f"{'=' * 80}")

    for thread, video_name in pending_uploads:
        if thread.is_alive():
            logger.info(f"   ⏳ Waiting for: {video_name}")
            thread.join()
            logger.info(f"   ✅ Completed: {video_name}")

    logger.info(f"✅ All background uploads completed!")

    # Clear the list
    with _background_upload_lock:
        _background_upload_threads.clear()


# ==============================================================================
# 🎛️ CENTRALIZED SETTINGS FUNCTION - EASY CONFIGURATION ACCESS
# ==============================================================================

def get_pipeline_settings():
    """
    Get all pipeline settings in a centralized dictionary.
    This function allows easy access to all step configurations from other scripts.
    """
    return {
        # AI Provider Configuration
        "ai_provider": {
            "provider": AI_PROVIDER,
            "google_model": AI_GOOGLE_MODEL,
            "claude_model": AI_CLAUDE_MODEL,
            "gemini_api_key": GEMINI_API_KEY,
            "claude_api_key": CLAUDE_API_KEY,
        },

        # Step-by-step settings
        "step_1_smart_processor": GEMINI_SETTINGS,
        "step_1_clip_extraction": CLIP_EXTRACTION_SETTINGS,
        "step_2_styling": STYLING_SETTINGS,
        "step_3_voiceover": VOICEOVER_SETTINGS,
        "step_4_broll_rearrangement": BROLL_REARRANGEMENT_SETTINGS,
        "step_5_assembly": ASSEMBLY_SETTINGS,
        "step_6_ranking": RANKING_SETTINGS,
        "step_7_combination": COMBINATION_SETTINGS,
        "step_8_youtube_upload": YOUTUBE_UPLOAD_SETTINGS,

        # Global settings
        "quality": QUALITY_SETTINGS,
        "error_handling": ERROR_SETTINGS,

        # Paths and directories
        "default_paths": {
            "interviews_folder": DEFAULT_INTERVIEWS_FOLDER,
            "broll_folder": DEFAULT_BROLL_FOLDER,
            "project_output_base": DEFAULT_PROJECT_OUTPUT_BASE_DIR,
        }
    }


def get_step_settings(step_number: int) -> dict:
    """
    Get settings for a specific step.

    Args:
        step_number: Step number (1-8)

    Returns:
        Dictionary with settings for that step
    """
    settings = get_pipeline_settings()

    step_mapping = {
        1: ["step_1_smart_processor", "step_1_clip_extraction"],
        2: ["step_2_styling"],
        3: ["step_3_voiceover"],
        4: ["step_4_broll_rearrangement"],
        5: ["step_5_assembly"],
        6: ["step_6_ranking"],
        7: ["step_7_combination"],
        8: ["step_8_youtube_upload"],
    }

    if step_number not in step_mapping:
        return {}

    step_settings = {}
    for key in step_mapping[step_number]:
        if key in settings:
            step_settings.update(settings[key])

    # Always include global settings
    step_settings.update(settings.get("quality", {}))
    step_settings.update(settings.get("error_handling", {}))

    return step_settings


def print_pipeline_settings():
    """Print all pipeline settings in a readable format for debugging."""
    settings = get_pipeline_settings()

    print("\n" + "=" * 80)
    print("🎛️ CURRENT PIPELINE SETTINGS")
    print("=" * 80)

    for category, config in settings.items():
        print(f"\n📋 {category.upper().replace('_', ' ')}")
        print("-" * 50)
        if isinstance(config, dict):
            for key, value in config.items():
                print(f"  {key:30} = {value}")
        else:
            print(f"  {config}")

    print("\n" + "=" * 80)


# ==============================================================================
# --- GLOBAL ORCHESTRATOR CONFIGURATION ---
# ==============================================================================
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
1

# --- 1. SCRIPT PATHS ---
SMART_INTERVIEW_PROCESSOR_SCRIPT = SCRIPT_DIR / "1_smart_interview_processor.py"
STYLE_INTERVIEW_CLIPS_SCRIPT = SCRIPT_DIR / "2_style_interview_clips.py"  # NEW STEP 2
SCRIPT_VOICE_SCRIPT = SCRIPT_DIR / "5_generate_voiceover.py"  # Voiceover script
CLIPS_PLUS_VOICEOVER_SCRIPT = SCRIPT_DIR / "7_assemble_final_video.py"  # Shared with Recreate Video
RANK_VIDEO_SEQUENCE_SCRIPT = SCRIPT_DIR / "8_rank_video_sequence.py"  # Shared with Recreate Video
COMBINE_RANKED_VIDEOS_SCRIPT = SCRIPT_DIR / "9_combine_ranked_videos.py"  # Shared with Recreate Video
# GENERATE_THUMBNAIL_TITLE_SCRIPT removed - step 8 was eliminated
YOUTUBE_UPLOAD_SCRIPT = SCRIPT_DIR / "10_youtube_upload.py"  # Shared with Recreate Video
# Legacy batch file (may not be needed in new pipeline)
CLIPS_MAKER_BATCH = SCRIPT_DIR / "5_rearrange_broll_clips.bat"

# --- 3. API KEYS FILE CONFIGURATION ---
API_KEYS_FILE = SCRIPT_DIR / "api_keys.json"

# --- 4. AVAILABLE VOICE MODELS ---

# === GENERAL PIPELINE SETTINGS ===
PROCESSING_MODE = "ASK_USER"
ORCHESTRATOR_LOG_FILE_NAME = "orchestrator_run.log"
STATUS_FILE_NAME = "pipeline_status.json"
STATUS_KEY_LAST_COMPLETED_STEP = "last_completed_step"
STATUS_KEY_STATE = "state"
STATUS_KEY_TIMESTAMP = "last_run_timestamp"

# --- 7. PROJECT SUBDIRECTORY NAMES ---
SUBDIR_ORIGINAL_VIDEO = "0_originals"
# NEW CLEAN STEP-BASED PIPELINE STRUCTURE
STEP_1_DIR = "1_processing"  # Step 1: Smart processing (interview clips, broll clips, script)
STEP_2_DIR = "2_styled_clips"  # Step 2: Styled interview clips with frames and animations
STEP_3_DIR = "3_voiceovers"  # Step 3: Generated voiceovers
STEP_4_DIR = "4_rearranged_broll"  # Step 4: Rearranged B-roll clips (6-second clips)
STEP_5_DIR = "5_final_videos"  # Step 5: Assembled final videos
STEP_6_DIR = "6_ranked_output"  # Step 6: Final ranked output
STEP_7_DIR = "7_final_combined"  # Step 7: Combined video with background music
STEP_8_DIR = "8_youtube_upload"  # Step 8: YouTube upload

# Step 1 subdirectories - PROFILE-FIRST STRUCTURE
SUBDIR_INTERVIEW_CLIPS = "interview_clips"
SUBDIR_BROLL_CLIPS = "broll_clips"
SUBDIR_SCRIPT = "voiceover_script.txt"

# NEW: Profile-First Structure directories
SHARED_DIR = "shared"
PROFILE_INPUT_TRANSCRIPT = "input_transcript.txt"
PROFILE_OUTPUT_SCRIPT = "output_script.txt"
PROFILE_CLIPS_DIR = "clips"
PROFILE_METADATA = "metadata.json"
PROFILE_PROCESS_LOG = "process.log"

# LEGACY FOLDERS (for backwards compatibility)
SUBDIR_CLIPS_MAIN = "1_clips"
SUBDIR_PRIMARY_CLIPS = "voiceover"  # Subfolder inside 1_clips
SUBDIR_INVERSE_CLIPS = "interviews"  # Subfolder inside 1_clips
SUBDIR_AI_SCRIPTS = "3_ai_scripts"
SUBDIR_REARRANGED_BROLL_CLIPS = "5_6sec_clips"
SUBDIR_LOGS = "logs"
SUBDIR_TEMP_SCRIPTS = "temp_scripts"

# --- 8. SUB-SCRIPT PARAMETERS ---
DIARIZATION_RE_ENCODE = True
DIARIZATION_USE_SPLEETER = True
TRANSCRIPTION_SAVE_SRT_FILES = False
TRANSCRIPTION_SAVE_INDIVIDUAL_TXT_FILES = False
TRANSCRIPTION_SAVE_COMBINED_FILE = True
TRANSCRIPTION_SAVE_JSON_FILES = False
TRANSCRIPTION_CREATE_FOLDER_PER_INPUT = False
TRANSCRIPTION_SHOW_PROGRESS_BAR = True
TRANSCRIPTION_SHOW_DETAILED_LOGS = True
AI_REWRITE_MODEL_NAME = "gemini-2.5-flash-preview-05-20"
# 🎯 AUTO-TAB SYSTEM: Set to "auto" for dynamic tab calculation based on script content
FISH_AUDIO_NUM_TABS = "auto"  # "auto" = smart calculation, or integer (e.g., 15) for manual
FISH_AUDIO_BASE_WAIT_TIME = 10  # Reduced from 10s to 5s for faster processing
FISH_AUDIO_SECONDS_PER_100_CHARS = 4  # Reduced from 4s to 2s per 100 chars
FISH_AUDIO_MAX_WAIT_TIME = 300  # Reduced from 300s to 180s max wait
# --- 9. LEGACY SETTINGS (Using centralized settings from top of file) ---
USE_MULTI_WINDOW_VOICEOVER = VOICEOVER_SETTINGS["use_multi_window"]
TABS_PER_WINDOW = VOICEOVER_SETTINGS["tabs_per_window"]
ENABLE_PROFILE_PARALLEL_PROCESSING = VOICEOVER_SETTINGS["enable_parallel"]
ASSEMBLE_VIDEO_USE_FAST_COPY = ASSEMBLY_SETTINGS["use_fast_copy"]
FISH_AUDIO_NUM_TABS = VOICEOVER_SETTINGS["tabs_per_window"]

# --- 10. B-ROLL PROCESSING SETTINGS ---
USE_VOICEOVER_CLIPS_FOR_BROLL = False  # True = Use voiceover clips, False = Use primary clips
TRIM_VOICEOVER_CLIPS_SECONDS = 1.5  # Seconds to trim from start and end of voiceover clips (0 = no trimming)


# ==============================================================================4
# --- PIPELINE STEPS DEFINITION ---
# ==============================================================================

def get_pipeline_steps_info(multi_mode: bool = False):
    """Returns NEW STREAMLINED pipeline steps based on processing mode"""
    if multi_mode:
        return {
            0: {"name": "Copy Original Video"},
            1: {"name": "Smart Interview Processing (Transcribe + Extract + Script)"},
            2: {"name": "Style Interview Clips (Frames + Animation)"},
            3: {"name": "Generate Voiceovers (Selected Profiles)"},
            4: {"name": "Rearrange B-roll Clips (Create 6-Second Clips)"},
            5: {"name": "Assemble Final Videos (Selected Profiles)"},
            6: {"name": "Rank Video Sequence (Styled Clips + Voiceovers)"},
            7: {"name": "Combine Videos (Fast GPU)"},
            8: {"name": "YouTube Upload (Profile-Specific Channels)"},
        }
    else:
        return {
            0: {"name": "Copy Original Video"},
            1: {"name": "Smart Interview Processing (Transcribe + Extract + Script)"},
            2: {"name": "Style Interview Clips (Frames + Animation)"},
            3: {"name": "Generate Voiceover"},
            4: {"name": "Rearrange B-roll Clips (Create 6-Second Clips)"},
            5: {"name": "Assemble Final Video"},
            6: {"name": "Rank Video Sequence (Styled Clips + Voiceovers)"},
            7: {"name": "Combine Videos (Fast GPU)"},
            8: {"name": "YouTube Upload (Profile-Specific Channel)"},
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
# --- FIXED MODE SELECTION FUNCTIONS ---
# ==============================================================================

def determine_processing_mode(auto_mode=False):
    """Determine the processing mode based on configuration"""
    if PROCESSING_MODE == "ASK_USER" and not auto_mode:
        return ask_user_processing_mode()
    else:
        # Auto mode or not ASK_USER: use all profiles
        return {"mode": "numbered", "count": len(PROMPT_PROFILES)}


def ask_user_processing_mode() -> Dict:
    """Ask user to choose number of videos to create or select single profile"""
    global PROMPT_PROFILES

    print("\n" + "=" * 70)
    print("🎬 VIDEO PROCESSING SELECTION:")
    print("=" * 70)

    # Show numbered options based on available prompts
    profile_list = list(PROMPT_PROFILES.items())
    for i in range(len(profile_list)):
        count = i + 1
        print(f"{count}. Create {count} video{'s' if count > 1 else ''}")

        # Show which profiles will be used
        for j in range(count):
            profile_key, profile_info = profile_list[j]
            status = "✅" if profile_info["prompt_file"].exists() else "❌"
            print(f"   → {profile_info['name']} using {profile_info['default_voice']} voice {status}")
        print()

    # Add select custom profiles option
    custom_profiles_option = len(profile_list) + 1
    print(f"{custom_profiles_option}. Select Custom Profiles")
    print("   → Choose any combination of profiles")
    for profile_key, profile_info in profile_list:
        status = "✅" if profile_info["prompt_file"].exists() else "❌"
        print(f"   → {profile_info['name']} using {profile_info['default_voice']} voice {status}")
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

                # Auto-confirm selection - no prompt needed
                return selected_profiles

        except ValueError:
            print("❌ Invalid input. Please enter numbers separated by commas (e.g., '1,3,5').")


def get_clips_directories(project_dir, is_multi_profile=False):
    """Get the correct paths for interview_clips and broll_clips directories

    Returns correct paths based on structure mode:
    - Multi-profile + Clean structure: shared/interview_clips, shared/broll_clips
    - Single profile or legacy: 1_processing/interview_clips, 1_processing/broll_clips

    Args:
        project_dir: Project output directory
        is_multi_profile: True if processing multiple profiles

    Returns:
        Dict with 'interview_clips' and 'broll_clips' Path objects
    """
    step_1_dir = project_dir / STEP_1_DIR

    # Clips are directly in 1_processing/ (new clean structure)
    return {
        'interview_clips': step_1_dir / SUBDIR_INTERVIEW_CLIPS,
        'broll_clips': step_1_dir / SUBDIR_BROLL_CLIPS
    }


def get_profile_paths(project_dir, profile_suffix):
    """Get Profile-First Structure paths for each profile (LEGACY - NOT USED IN NEW SYSTEM)

    This function is kept for backwards compatibility but is not used in the new
    PROFILE_CLIP_MODE system.
    """
    # Legacy: profiles directly in 1_processing/
    profile_dir = project_dir / STEP_1_DIR / profile_suffix
    shared_dir = project_dir / STEP_1_DIR / SHARED_DIR

    return {
        # Profile directory
        "profile_dir": profile_dir,
        "shared_dir": shared_dir,

        # Clear inputs
        "input_transcript": profile_dir / PROFILE_INPUT_TRANSCRIPT,
        "input_prompt": profile_dir / "input_prompt.txt",

        # Clear outputs
        "output_script": profile_dir / PROFILE_OUTPUT_SCRIPT,
        "output_clips": profile_dir / PROFILE_CLIPS_DIR,
        "output_summary": profile_dir / "summary.txt",

        # Processing info
        "process_log": profile_dir / PROFILE_PROCESS_LOG,
        "metadata": profile_dir / PROFILE_METADATA,

        # Shared resources (interview_clips, broll_clips, script in shared/)
        "shared_video": shared_dir / "original_video.mp4",
        "shared_transcript": shared_dir / "raw_transcript.txt",
        "shared_base_script": shared_dir / "voiceover_script.txt",
        "shared_interview_clips": shared_dir / SUBDIR_INTERVIEW_CLIPS,
        "shared_broll_clips": shared_dir / SUBDIR_BROLL_CLIPS
    }


def create_profile_structure(project_dir, selected_profiles):
    """Create Profile-First Structure directories (LEGACY - NOT USED IN NEW SYSTEM)

    This function is kept for backwards compatibility but is not used in the new
    PROFILE_CLIP_MODE system which uses simpler flat structure.
    """
    logger.info(f"📁 Creating Profile Structure for {len(selected_profiles)} profiles...")

    # Create shared directory with subdirectories for clips
    shared_dir = project_dir / STEP_1_DIR / SHARED_DIR
    shared_dir.mkdir(parents=True, exist_ok=True)

    # Create shared subdirectories for interview clips and b-roll clips
    (shared_dir / SUBDIR_INTERVIEW_CLIPS).mkdir(exist_ok=True)
    (shared_dir / SUBDIR_BROLL_CLIPS).mkdir(exist_ok=True)

    logger.info(f"   ✅ Created shared directory: {shared_dir.relative_to(project_dir)}")

    # Create profile directories
    for profile_key, profile_info in selected_profiles:
        paths = get_profile_paths(project_dir, profile_info['suffix'])

        # Create profile directory structure
        paths["profile_dir"].mkdir(parents=True, exist_ok=True)
        paths["output_clips"].mkdir(exist_ok=True)

        # Create profile README
        create_profile_readme(paths["profile_dir"], profile_info)

        # Create processing status file
        status_file = paths["profile_dir"] / "⏳ PROCESSING.txt"
        status_file.write_text(f"Processing {profile_info['name']}...", encoding='utf-8')

        logger.info(f"   ✅ Created structure for {profile_info['name']}")

    logger.info(f"📁 Profile Structure ready!")


def create_profile_readme(profile_dir, profile_info):
    """Auto-generate README for each profile folder"""

    readme_content = f"""# {profile_info['name']} Profile Processing

## Profile Settings:
- Voice: {profile_info['default_voice']}
- Style: {profile_info['description']}
- Background: {profile_info.get('background_video', 'N/A')}
- Frame Color: {profile_info.get('frame_color', 'N/A')}

## Files in this folder:
- `{PROFILE_INPUT_TRANSCRIPT}` - Source transcript for this profile
- `{PROFILE_OUTPUT_SCRIPT}` - Generated voiceover script
- `{PROFILE_CLIPS_DIR}/` - Profile-specific video clips
- `{PROFILE_PROCESS_LOG}` - Processing details and logs
- `{PROFILE_METADATA}` - Settings and metadata used

## Processing Status:
Check the status files:
- ⏳ PROCESSING.txt - Currently being processed
- ✅ READY.txt - Completed successfully
- ❌ ERROR.txt - Failed (check process.log)
- ⚠️ PARTIAL.txt - Partially completed

## Quick Access:
- Script: `{PROFILE_OUTPUT_SCRIPT}`
- Clips: `{PROFILE_CLIPS_DIR}/`
- Logs: `{PROFILE_PROCESS_LOG}`
"""

    (profile_dir / "README.md").write_text(readme_content, encoding='utf-8')


def update_profile_status(profile_dir, status, message=""):
    """Update profile processing status"""
    status_files = {
        "processing": "⏳ PROCESSING.txt",
        "ready": "✅ READY.txt",
        "error": "❌ ERROR.txt",
        "partial": "⚠️ PARTIAL.txt"
    }

    # Remove old status files
    for status_file in status_files.values():
        status_path = profile_dir / status_file
        if status_path.exists():
            status_path.unlink()

    # Create new status file
    if status in status_files:
        new_status_file = profile_dir / status_files[status]
        content = message if message else f"Status: {status}"
        new_status_file.write_text(content, encoding='utf-8')


def save_profile_metadata(profile_dir, profile_info, processing_settings):
    """Save profile metadata and settings used"""
    import json

    metadata = {
        "profile_name": profile_info['name'],
        "profile_suffix": profile_info['suffix'],
        "default_voice": profile_info['default_voice'],
        "description": profile_info['description'],
        "processing_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "settings_used": processing_settings
    }

    metadata_path = profile_dir / PROFILE_METADATA
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def validate_prompt_profiles():
    """Validate all profiles have correct voice configurations"""
    logger.info("🔍 Validating prompt profiles...")
    errors_found = False

    for profile_name, profile_info in PROMPT_PROFILES.items():
        voice_name = profile_info.get("default_voice")
        if not voice_name:
            logger.error(f"❌ Profile '{profile_name}' missing default_voice")
            errors_found = True
            continue

        # Check if voice exists in AVAILABLE_VOICES
        voice_found = False
        for voice_key, voice_info in AVAILABLE_VOICES.items():
            if voice_info["name"] == voice_name:
                voice_found = True
                break

        if not voice_found:
            logger.error(f"❌ Profile '{profile_name}' voice '{voice_name}' not found in AVAILABLE_VOICES")
            available_voices = list(v['name'] for v in AVAILABLE_VOICES.values())
            logger.error(f"   Available voices: {available_voices}")
            errors_found = True
        else:
            logger.info(f"✅ Profile '{profile_name}' → voice '{voice_name}' validated")

    if errors_found:
        logger.warning("⚠️ Profile validation found errors - some voices may fallback to ALEX")
    else:
        logger.info("✅ All profiles validated successfully")


def get_voice_url_by_name(voice_name: str) -> str:
    """Get voice URL by voice name with better error handling"""
    logger.info(f"🔍 Looking for voice: '{voice_name}'")

    # First try exact match
    for voice_key, voice_info in AVAILABLE_VOICES.items():
        if voice_info["name"] == voice_name:
            logger.info(f"✅ Found exact match '{voice_name}': {voice_info['url']}")
            return voice_info["url"]

    # Try case-insensitive match
    for voice_key, voice_info in AVAILABLE_VOICES.items():
        if voice_info["name"].upper() == voice_name.upper():
            logger.warning(f"⚠️ Found case-insensitive match '{voice_name}' → '{voice_info['name']}'")
            return voice_info["url"]

    # Try partial match
    for voice_key, voice_info in AVAILABLE_VOICES.items():
        if voice_name.upper() in voice_info["name"].upper() or voice_info["name"].upper() in voice_name.upper():
            logger.warning(f"⚠️ Found partial match '{voice_name}' → '{voice_info['name']}'")
            return voice_info["url"]

    # Final fallback with clear error
    available_voices = list(v['name'] for v in AVAILABLE_VOICES.values())
    logger.error(f"❌ Voice '{voice_name}' not found! Available voices: {available_voices}")
    fallback_url = AVAILABLE_VOICES["ALEX"]["url"]
    logger.error(f"🔄 FORCED FALLBACK to ALEX voice: {fallback_url}")
    return fallback_url


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


def run_python_script(script_path: Path, args: List[str], cwd: Path = None, capture_output: bool = True, env_vars: Dict = None) -> bool:
    """Run a Python script as subprocess"""
    cmd = [sys.executable, str(script_path)] + args
    logger.info(f"  Running: {' '.join(str(c) for c in cmd)}")

    # Build environment with optional extra variables
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        process = subprocess.run(cmd, cwd=cwd, check=True, capture_output=capture_output, text=True, encoding='utf-8',
                                 errors='replace', env=env)
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


def validate_script_content(script_content: str, min_paragraphs: int = 3) -> bool:
    """Validate script has sufficient content"""
    if not script_content or not script_content.strip():
        logger.error("❌ Script is empty")
        return False

    paragraphs = [p.strip() for p in script_content.split('\n\n') if p.strip()]
    if len(paragraphs) < min_paragraphs:
        logger.warning(f"⚠️ Script only has {len(paragraphs)} paragraphs, expected at least {min_paragraphs}")
        return False

    logger.info(f"✅ Script validation passed: {len(paragraphs)} paragraphs")
    return True


def rewrite_script_with_ai_prompt(original_script: str, profile_prompt: str, profile_name: str) -> Optional[str]:
    """
    Use Google Gemini AI to rewrite a script based on a profile prompt.

    Args:
        original_script: The original script content to rewrite
        profile_prompt: The prompt that defines the rewriting style
        profile_name: The name of the profile for logging purposes

    Returns:
        The rewritten script content, or None if rewriting failed
    """
    try:
        # Configure Gemini API
        genai.configure(api_key=GEMINI_API_KEY)

        # Create the model
        model = genai.GenerativeModel(AI_GOOGLE_MODEL)

        # Construct the rewriting prompt
        rewrite_prompt = f"""
{profile_prompt}

Please rewrite the following script according to the above prompt and style guidelines:

---ORIGINAL SCRIPT---
{original_script}
---END ORIGINAL SCRIPT---

Important requirements:
1. Keep all interview clip references and timestamps exactly as they are
2. Maintain the overall structure and flow of the original script
3. Apply the style and tone specified in the prompt
4. Ensure the rewritten script maintains the same general length
5. Do not add any header comments or meta-text that would be read aloud
6. CRITICAL: Keep TWO empty lines between each paragraph (exactly like the original formatting)
7. Return ONLY the rewritten script content, nothing else

Rewritten script:
"""

        logger.info(f"   🤖 Sending script to AI for {profile_name} style rewriting...")

        # Generate the rewritten script
        response = model.generate_content(rewrite_prompt)

        if response and response.text:
            rewritten_script = response.text.strip()

            # Validate AI response quality
            if not validate_script_content(rewritten_script):
                logger.error(f"❌ AI returned poor quality script for {profile_name}")
                logger.info(f"📝 Using original script as fallback")
                return original_script

            # Better paragraph processing - handle multiple formats
            paragraphs = []
            lines = rewritten_script.split('\n')
            current_paragraph = []

            for line in lines:
                if line.strip() == '':
                    if current_paragraph:
                        paragraphs.append('\n'.join(current_paragraph).strip())
                        current_paragraph = []
                else:
                    current_paragraph.append(line)

            if current_paragraph:
                paragraphs.append('\n'.join(current_paragraph).strip())

            # Filter out empty paragraphs
            paragraphs = [p for p in paragraphs if p.strip()]
            rewritten_script = '\n\n\n'.join(paragraphs)

            # Log before/after comparison
            orig_paragraphs = len([p for p in original_script.split('\n\n') if p.strip()])
            new_paragraphs = len(paragraphs)
            logger.info(f"📊 Script rewrite: {orig_paragraphs} → {new_paragraphs} paragraphs")
            logger.info(f"   ✅ AI rewriting completed for {profile_name}")
            return rewritten_script
        else:
            logger.error(f"   ❌ Empty response from AI for {profile_name}")
            return None

    except Exception as e:
        logger.error(f"   ❌ AI rewriting failed for {profile_name}: {e}")
        return None


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

def get_pipeline_settings() -> Dict:
    """Export all pipeline settings for use by other scripts"""

    # Load API keys
    json_api_keys = load_api_keys_from_json_file(API_KEYS_FILE)
    fallback_gemini_key = json_api_keys.get("google_gemini_api_key") or GEMINI_API_KEY

    return {
        "ai_provider": {
            "provider": AI_PROVIDER,
            "google_model": AI_GOOGLE_MODEL,
            "claude_model": AI_CLAUDE_MODEL,
            "gemini_api_key": fallback_gemini_key,
            "claude_api_key": CLAUDE_API_KEY,
        },
        "gemini": {
            **GEMINI_SETTINGS,
            "api_key": fallback_gemini_key,
            "model": AI_GOOGLE_MODEL,
            "interviews_folder": str(DEFAULT_INTERVIEWS_FOLDER),
            "broll_folder": str(DEFAULT_BROLL_FOLDER),
            "output_base_folder": str(DEFAULT_PROJECT_OUTPUT_BASE_DIR),
        },
        "clip_extraction": CLIP_EXTRACTION_SETTINGS,
        "voiceover": VOICEOVER_SETTINGS,
        "assembly": ASSEMBLY_SETTINGS,
        "ranking": RANKING_SETTINGS,
        "step_7_combination": COMBINATION_SETTINGS,
        "quality": QUALITY_SETTINGS,
        "error_handling": ERROR_SETTINGS,
    }


def run_smart_interview_processing(interviews_folder: Path, broll_folder: Path, project_output_dir: Path, profile_info: dict = None) -> bool:
    """Run NEW smart interview processing step - combines transcription, extraction, and script creation

    Args:
        interviews_folder: Path to interview videos
        broll_folder: Path to b-roll clips
        project_output_dir: Output directory
        profile_info: Optional profile info with prompt_file for profile-specific script generation
    """
    logger.info(f"🧠 Starting Smart Interview Processing...")
    logger.info(f"   📹 Interviews folder: {interviews_folder}")
    logger.info(f"   🎬 B-roll folder: {broll_folder}")
    logger.info(f"   📁 Output dir: {project_output_dir}")
    if profile_info:
        logger.info(f"   🎯 Profile: {profile_info.get('name', 'Unknown')}")

    try:
        # Import and run the processor directly to pass profile_info
        from pathlib import Path as PathLib
        import sys

        global _SMART_PROCESSOR_MODULE

        # Add the script directory to path to import the processor
        script_dir = Path(__file__).parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))

        # Import the processor class from 1_smart_interview_processor.py
        # Use thread lock to prevent I/O conflicts when loading module in parallel
        with _MODULE_LOAD_LOCK:
            if _SMART_PROCESSOR_MODULE is None:
                # Python doesn't allow imports starting with numbers, so we use importlib
                import importlib
                _SMART_PROCESSOR_MODULE = importlib.import_module("1_smart_interview_processor")
            smart_processor_module = _SMART_PROCESSOR_MODULE
        SmartInterviewProcessor = smart_processor_module.SmartInterviewProcessor

        # Create processor instance with profile info
        processor = SmartInterviewProcessor(
            interviews_folder=interviews_folder,
            broll_folder=broll_folder,
            output_folder=project_output_dir,
            profile_info=profile_info  # Pass profile info for prompt selection
        )

        # Run the processing
        success = processor.process()

        if success:
            logger.info(f"✅ Smart Interview Processing completed successfully")

            # Reorganize smart processor outputs to clean step-based structure
            # Check if content is already in step 1 folder (new structure)
            step_1_dir = project_output_dir / STEP_1_DIR

            # Define final locations for verification
            final_script = step_1_dir / SUBDIR_SCRIPT
            final_interview_clips = step_1_dir / SUBDIR_INTERVIEW_CLIPS

            if step_1_dir.exists() and any(step_1_dir.iterdir()):
                logger.info(f"✅ Output already in clean step-based structure")
            else:
                logger.info(f"🔄 Reorganizing outputs to clean step-based structure...")

                # Create Step 1 directory
                step_1_dir.mkdir(exist_ok=True)

                # Move interview clips: interview_clips/ → 1_processing/interview_clips/
                old_interview_clips = project_output_dir / "interview_clips"
                new_interview_clips = step_1_dir / SUBDIR_INTERVIEW_CLIPS
                if old_interview_clips.exists():
                    if new_interview_clips.exists():
                        shutil.rmtree(new_interview_clips)
                    shutil.move(str(old_interview_clips), str(new_interview_clips))
                    logger.info(f"✅ Moved interview clips: interview_clips → {STEP_1_DIR}/{SUBDIR_INTERVIEW_CLIPS}")

                # B-roll clips are now created directly in 1_processing/broll_clips/ by Step 1
                broll_clips = step_1_dir / SUBDIR_BROLL_CLIPS
                if broll_clips.exists():
                    broll_count = len(list(broll_clips.glob("*.mp4")))
                    logger.info(f"✅ B-roll clips ready: {STEP_1_DIR}/{SUBDIR_BROLL_CLIPS}/ ({broll_count} clips)")

                # Move voiceover script: voiceover_script.txt → 1_processing/voiceover_script.txt
                old_script = project_output_dir / "voiceover_script.txt"
                new_script = step_1_dir / SUBDIR_SCRIPT
                if old_script.exists():
                    if new_script.exists():
                        new_script.unlink()
                    shutil.move(str(old_script), str(new_script))
                    logger.info(f"✅ Moved voiceover script: voiceover_script.txt → {STEP_1_DIR}/{SUBDIR_SCRIPT}")

                # Move transcripts folder: transcripts/ → 1_processing/transcripts/
                old_transcripts = project_output_dir / "transcripts"
                new_transcripts = step_1_dir / "transcripts"
                if old_transcripts.exists():
                    if new_transcripts.exists():
                        shutil.rmtree(new_transcripts)
                    shutil.move(str(old_transcripts), str(new_transcripts))
                    logger.info(f"✅ Moved transcripts: transcripts → {STEP_1_DIR}/transcripts")

                # Move script folder: script/ → 1_processing/script/
                old_script_folder = project_output_dir / "script"
                new_script_folder = step_1_dir / "script"
                if old_script_folder.exists():
                    if new_script_folder.exists():
                        shutil.rmtree(new_script_folder)
                    shutil.move(str(old_script_folder), str(new_script_folder))
                    logger.info(f"✅ Moved script folder: script → {STEP_1_DIR}/script")

            # Verify final outputs (works for both new structure and reorganized)
            if final_script.exists() and final_interview_clips.exists():
                interview_clips = list(final_interview_clips.glob("*.mp4"))
                logger.info(f"🎯 Generated voiceover script and {len(interview_clips)} interview clips in Step 1")
                return True
            else:
                logger.warning(f"⚠️ Smart processing completed but outputs missing")
                logger.warning(f"   Voiceover script exists: {final_script.exists()}")
                logger.warning(f"   Interview clips dir exists: {final_interview_clips.exists()}")
                return False
        else:
            logger.error(f"❌ Smart Interview Processing failed")
            return False

    except Exception as e:
        logger.error(f"❌ Error in smart interview processing: {e}")
        return False


def run_styling_step_single(video_stem: str, interview_clips_dir: Path, styled_clips_dir: Path,
                            prompt_profile: Dict = None) -> bool:
    """NEW: Run interview styling step with frames, animations, and backgrounds"""
    logger.info(f"🎨 Starting interview styling with frames and animations...")

    try:
        # Use profile-specific settings if available, otherwise use global settings
        if prompt_profile:
            video_scale = prompt_profile.get("video_scale", STYLING_SETTINGS["video_width_scale"])
            frame_color = prompt_profile.get("frame_color", STYLING_SETTINGS["frame_color"])
            background_video = prompt_profile.get("background_video", STYLING_SETTINGS["background_path"])

            logger.info(f"🎨 Using profile-specific styling:")
            logger.info(f"   Background: {background_video}")
            logger.info(f"   Frame Color: {frame_color}")
            logger.info(f"   Video Scale: {video_scale}")
        else:
            video_scale = STYLING_SETTINGS["video_width_scale"]
            frame_color = STYLING_SETTINGS["frame_color"]
            background_video = STYLING_SETTINGS["background_path"]
            logger.info(f"🎨 Using global styling settings")

        # Prepare arguments for the styling script (using correct argument names)
        # Create Video uses no-crop (use interview clips as-is without any cropping)
        script_args = [
            str(STYLE_INTERVIEW_CLIPS_SCRIPT),
            "--input", str(interview_clips_dir),
            "--output", str(styled_clips_dir),
            "--video-scale", str(video_scale),
            "--frame-color", str(frame_color),
            "--background", str(background_video),
            "--no-crop",  # No cropping for Create Video (use clips as-is)
        ]

        # Add sound effect arguments if enabled
        sfx_enabled = STYLING_SETTINGS.get("enable_sound_effect", False)
        sfx_path = STYLING_SETTINGS.get("sound_effect_path", "")
        if sfx_enabled and sfx_path and Path(sfx_path).exists():
            script_args.extend([
                "--enable-sound-effect",
                "--sound-effect-path", str(sfx_path),
                "--sound-effect-volume", str(STYLING_SETTINGS.get("sound_effect_volume", 1.0)),
                "--sound-effect-duration", str(STYLING_SETTINGS.get("sound_effect_duration", 0.8)),
            ])
        else:
            script_args.append("--disable-sound-effect")

        logger.info(f"🔧 Styling settings: {video_scale}x scale, {frame_color} frame")
        logger.info(f"📂 Background: {background_video}")

        # Run the styling script
        result = subprocess.run([sys.executable] + script_args,
                                capture_output=True, text=True, cwd=SCRIPT_DIR)

        if result.returncode == 0:
            # Count styled clips created
            styled_clips = list(styled_clips_dir.glob("*.mp4")) if styled_clips_dir.exists() else []
            logger.info(f"✅ Interview styling completed successfully! Created {len(styled_clips)} styled clips")
            return True
        else:
            logger.error(f"❌ Interview styling failed:")
            logger.error(f"   stdout: {result.stdout}")
            logger.error(f"   stderr: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Error in interview styling: {e}")
        return False


def run_voiceover_with_api(script_path: Path, voiceovers_dir: Path, video_stem: str, prompt_profile: Dict) -> bool:
    """Run voiceover generation using Fish Audio API"""
    try:
        # Get voice URL for this profile
        voice_url = get_voice_url_by_name(prompt_profile.get("default_voice", ""))
        if not voice_url:
            logger.error(f"❌ Voice '{prompt_profile.get('default_voice')}' not found!")
            return False

        # Create output directory
        voiceover_output_dir = voiceovers_dir / f"{video_stem}_voiceover_{prompt_profile.get('suffix', 'default')}"
        voiceover_output_dir.mkdir(parents=True, exist_ok=True)

        # Run the API voiceover script
        api_script = SCRIPT_DIR / "5_generate_voiceover_api.py"
        if not api_script.exists():
            logger.error(f"❌ API voiceover script not found: {api_script}")
            return False

        # API script expects: -s (script), -o (output), -v (voice URL)
        voiceover_args = [
            "-s", str(script_path),
            "-o", str(voiceover_output_dir),
            "-v", voice_url,
        ]

        logger.info(f"🎯 Running API voiceover for: {script_path.name}")
        logger.info(f"   Voice URL: {voice_url[:50]}...")
        success = run_python_script(api_script, voiceover_args, capture_output=False)

        # Verify files were created
        if voiceover_output_dir.exists():
            voiceover_files = list(voiceover_output_dir.glob("*.mp3"))
            if len(voiceover_files) > 0:
                logger.info(f"✅ Generated {len(voiceover_files)} voiceover files via API")
                return True
            else:
                logger.error(f"❌ API ran but no files were generated!")
                return False
        return False

    except Exception as e:
        logger.error(f"❌ Error in API voiceover: {e}")
        return False


def run_voiceover_step_single_new(video_stem: str, project_dir: Path, voiceovers_dir: Path,
                                  voice_url: str, temp_script_dir: Path, prompt_profile: Dict,
                                  browser_profile_path: str = None) -> bool:
    """
    NEW: Run voiceover step using profile-specific script.

    Args:
        video_stem: Video name/identifier
        project_dir: Project output directory
        voiceovers_dir: Directory for voiceover output
        voice_url: Fish Audio voice URL
        temp_script_dir: Temporary script directory
        prompt_profile: Profile configuration dict
        browser_profile_path: Optional custom browser profile path for parallel processing.
                             When provided, allows multiple videos to run voiceover
                             simultaneously without browser conflicts.
    """
    logger.info(f"🎤 Starting voiceover generation...")
    if browser_profile_path:
        logger.info(f"🌐 Using custom browser profile: {browser_profile_path}")

    # Use NEW standardized filename from Step 1: voiceover_script.txt
    profile_script_path = project_dir / STEP_1_DIR / "voiceover_script.txt"

    if not profile_script_path.exists():
        logger.error(f"❌ Script not found: {profile_script_path}")
        return False

    logger.info(f"📝 Using script: {profile_script_path}")

    # Check if using API method (read fresh from config)
    if is_using_api_method():
        logger.info("🚀 Using Fish Audio API for voiceover generation...")
        return run_voiceover_with_api(profile_script_path, voiceovers_dir, video_stem, prompt_profile)

    # For single-profile mode, create a temporary script that calls the voiceover function directly
    voiceover_output_dir = voiceovers_dir / f"{video_stem}_voiceover_{prompt_profile.get('suffix', 'default')}"
    voiceover_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"🎤 Creating temporary voiceover script for direct execution...")
    logger.info(f"   Script: {profile_script_path}")
    logger.info(f"   Output: {voiceover_output_dir}")
    logger.info(f"   Voice: {voice_url}")

    # Calculate optimal number of tabs based on script content
    try:
        script_content = profile_script_path.read_text(encoding='utf-8')
        # Count actual paragraphs (separated by double line breaks)
        paragraphs = [p.strip() for p in script_content.split('\n\n\n') if p.strip()]
        if not paragraphs:  # Fallback if triple line break doesn't work
            paragraphs = [p.strip() for p in script_content.split('\n\n') if p.strip()]

        optimal_tabs = len(paragraphs)
        # Cap at reasonable maximum to avoid browser issues
        optimal_tabs = min(optimal_tabs, 25)
        # Minimum of 2 tabs for safety
        optimal_tabs = max(optimal_tabs, 2)

        logger.info(f"📊 Script analysis: {len(paragraphs)} paragraphs → {optimal_tabs} tabs for maximum speed")
    except Exception as e:
        logger.warning(f"⚠️ Could not analyze script for tab optimization: {e}")
        optimal_tabs = 2

    # Create temporary script that calls the voiceover function directly
    # Use profile output directory for temp scripts (not hardcoded path)
    temp_scripts_dir = voiceover_output_dir.parent / "logs" / "temp_scripts"
    temp_scripts_dir.mkdir(parents=True, exist_ok=True)

    temp_script_path = temp_scripts_dir / f"temp_3_generate_voiceover.py"

    # Prepare browser profile parameter for parallel processing
    # When browser_profile_path is None, use the default path from 5_generate_voiceover.py
    # We use _CUSTOM_BROWSER_PROFILE variable name to avoid being overwritten by exec()
    if browser_profile_path:
        browser_profile_param = f'r"{browser_profile_path}"'
    else:
        browser_profile_param = 'None'

    temp_script_content = f'''# -*- coding: utf-8 -*-
import os
import sys
import importlib

# Add script directory to path
sys.path.insert(0, r"{Path(__file__).parent}")

# Import the voiceover module
voiceover_module = importlib.import_module("5_generate_voiceover")

# Override the voice URL in the module
voiceover_module.VOICEOVER_URL = "{voice_url}"

# Set the parameters
text_file_path = r"{profile_script_path}"
output_folder = r"{voiceover_output_dir}"
num_tabs = {optimal_tabs}
profile_name = "{prompt_profile.get('name', 'Default')}"
browser_profile = {browser_profile_param}

print("PARALLEL-ENABLED VOICEOVER GENERATOR")
print("=" * 60)
print(f"Text file: {{text_file_path}}")
print(f"Output folder: {{output_folder}}")
print(f"Voice URL: {{voiceover_module.VOICEOVER_URL}}")
print(f"Number of tabs: {{num_tabs}}")
print(f"Browser profile: {{browser_profile or 'Default shared profile'}}")
print("=" * 60)

# Call the processing function directly
voiceover_module.run_smart_parallel_with_voice_url(text_file_path, output_folder, num_tabs, voiceover_module.VOICEOVER_URL, profile_name, browser_profile)
'''

    # Write the temporary script
    with open(temp_script_path, 'w', encoding='utf-8') as f:
        f.write(temp_script_content)

    logger.info(f"✅ Created temporary voiceover script: {temp_script_path}")

    # Run the temporary script
    success = run_python_script(temp_script_path, [])

    # Log result
    if success:
        logger.info(f"✅ Voiceover generation completed for {prompt_profile.get('name', 'Unknown')}")
    else:
        logger.error(f"❌ Voiceover generation failed for {prompt_profile.get('name', 'Unknown')}")

    return success

    # OLD COMPLEX METHOD BELOW - keeping as backup
    """
    # Create temporary script folder structure for the old voiceover function  
    script_dir = project_dir / "temp_script"
    script_dir.mkdir(exist_ok=True)

    # Copy the smart-generated script to the expected location with profile naming
    profile_suffix = prompt_profile.get('suffix', 'default')
    expected_script_name = f"{video_stem}_rewritten_script_{profile_suffix}.txt"
    expected_script_path = script_dir / expected_script_name

    # Copy the voiceover script content
    import shutil
    shutil.copy2(voiceover_script_path, expected_script_path)
    logger.info(f"📝 Copied smart script to: {expected_script_path}")

    # Call the existing voiceover generation with the properly structured script
    return run_voiceover_step_single(video_stem, script_dir, voiceovers_dir,
                                   voice_url, temp_script_dir, prompt_profile)
    """


def run_ranking_step_single_new(video_stem: str, interview_clips_dir: Path, final_videos_dir: Path,
                                ranked_sequence_dir: Path, prompt_profile: Dict) -> bool:
    """NEW: Run ranking step using smart-extracted interview clips"""
    logger.info(f"🏆 Starting NEW ranking with smart-extracted interview clips...")

    # Use the existing ranking function with the new directory structure
    return run_ranking_step_single(video_stem, interview_clips_dir, final_videos_dir,
                                   ranked_sequence_dir, prompt_profile)


def run_combination_step_single(video_stem: str, ranked_videos_dir: Path, combined_videos_dir: Path,
                                profile_name: str = None, prompt_profile: Dict = None) -> bool:
    """NEW: Run video combination step with profile-specific background music and audio levels"""
    logger.info(f"🚀 Starting video combination with profile-specific audio settings...")

    try:
        # Adjust input path to include profile subfolder if provided
        if profile_name:
            actual_input_dir = ranked_videos_dir / profile_name
            # Create profile-specific output directory
            actual_output_dir = combined_videos_dir / profile_name
            actual_output_dir.mkdir(parents=True, exist_ok=True)
        else:
            actual_input_dir = ranked_videos_dir
            actual_output_dir = combined_videos_dir

        # Prepare arguments for the combination script with profile-specific settings
        script_args = [
            str(COMBINE_RANKED_VIDEOS_SCRIPT),
            "--input", str(actual_input_dir),
            "--output", str(actual_output_dir),
            "--video-stem", video_stem
        ]

        # Add profile-specific audio settings if available
        if prompt_profile:
            background_music = prompt_profile.get("background_music")
            voice_level = prompt_profile.get("voice_level", 1.2)
            music_level = prompt_profile.get("music_level", 0.05)

            if background_music:
                script_args.extend(["--background-music", str(background_music)])
                script_args.extend(["--voice-level", str(voice_level)])
                script_args.extend(["--music-level", str(music_level)])
                logger.info(f"🎵 Background Music: {background_music}")
                logger.info(f"🔊 Voice Level: {voice_level}")
                logger.info(f"🎶 Music Level: {music_level}")
            else:
                logger.info(f"⚡ Mode: Fast video combination (no background music)")
        else:
            logger.info(f"⚡ Mode: Fast video combination (no profile settings)")

        logger.info(f"📂 Input: {actual_input_dir}")
        logger.info(f"📂 Output: {actual_output_dir}")

        # Run the combination script with Unicode handling
        result = subprocess.run([sys.executable] + script_args,
                                capture_output=True, text=False, cwd=SCRIPT_DIR)

        if result.returncode == 0:
            # Check if combined video was created
            combined_videos = list(actual_output_dir.glob("*.mp4")) if actual_output_dir.exists() else []
            logger.info(
                f"✅ Fast video combination completed successfully! Created {len(combined_videos)} combined video(s)")
            return True
        else:
            logger.error(f"❌ Video combination failed:")
            try:
                stdout_text = result.stdout.decode('utf-8', errors='ignore') if result.stdout else 'None'
                stderr_text = result.stderr.decode('utf-8', errors='ignore') if result.stderr else 'None'
                logger.error(f"   stdout: {stdout_text}")
                logger.error(f"   stderr: {stderr_text}")
            except:
                logger.error(f"   Error details unavailable due to encoding issues")
            return False

    except Exception as e:
        logger.error(f"❌ Error in video combination: {e}")
        return False


# Thumbnail/title generation function removed - step 8 was eliminated


def run_youtube_upload_step(video_stem: str, project_dir: Path, step_8_dir: Path, prompt_profile: Dict = None,
                            browser_profile_path: str = None) -> bool:
    """NEW: Step 8 - Upload video to YouTube with profile-specific settings

    Args:
        video_stem: Video stem name
        project_dir: Project directory path
        step_8_dir: Step 8 output directory
        prompt_profile: Profile settings dictionary
        browser_profile_path: NOT USED for YouTube upload (kept for API compatibility)

    NOTE: Uses SHARED browser with multiple TABS for parallel uploads.
    Each video opens in a new tab of the same browser (same login session).
    """
    profile_name = prompt_profile.get('name', 'Unknown') if prompt_profile else 'Unknown'
    profile_suffix = prompt_profile.get("suffix", "DEFAULT") if prompt_profile else "DEFAULT"

    # Check if upload is enabled
    if prompt_profile and not prompt_profile.get("enable_upload", False):
        logger.info(f"⏭️ Upload disabled for profile: {profile_name}")
        return True

    # Check if already uploaded
    step_8_dir.mkdir(parents=True, exist_ok=True)
    result_files_to_check = [
        step_8_dir / f"{video_stem}_youtube_uploads.json",
        step_8_dir / f"{video_stem}_youtube_uploads_{profile_suffix}.json",
    ]

    for upload_result_file in result_files_to_check:
        if upload_result_file.exists():
            try:
                with open(upload_result_file, 'r', encoding='utf-8') as f:
                    upload_data = json.load(f)
                profile_data = upload_data.get(profile_suffix, {})
                if profile_data:
                    videos_list = profile_data.get("videos", [])
                    uploaded_count = profile_data.get("uploaded_count", 0)
                    if uploaded_count > 0 and videos_list:
                        has_valid_upload = any(
                            len(v) >= 2 and v[1] and (
                                "youtube" in str(v[1]).lower() or
                                "upload completed" in str(v[1]).lower()
                            )
                            for v in videos_list
                        )
                        if has_valid_upload:
                            logger.info(f"⏭️ [{video_stem}] Already uploaded: {profile_suffix}")
                            return True
                if upload_data.get("video_id") or upload_data.get("success") or upload_data.get("url"):
                    logger.info(f"⏭️ [{video_stem}] Already uploaded: {profile_suffix}")
                    return True
            except (json.JSONDecodeError, Exception):
                pass

    # Find the video to upload
    step_7_dir = project_dir / STEP_7_DIR
    video_patterns = ["*.mp4", "*combined*.mp4", "*complete*.mp4"]
    video_files = []
    search_dirs = [step_7_dir]

    if prompt_profile:
        suffix = prompt_profile.get("suffix", "")
        if suffix:
            profile_subdir = step_7_dir / suffix
            if profile_subdir.exists():
                search_dirs.insert(0, profile_subdir)

    for search_dir in search_dirs:
        for pattern in video_patterns:
            video_files = list(search_dir.glob(pattern))
            if video_files:
                step_7_dir = search_dir
                break
        if video_files:
            break

    if not video_files:
        logger.error(f"❌ [{video_stem}] No video found in: {search_dirs}")
        return False

    video_file = video_files[0]
    logger.info(f"📹 [{video_stem}] Found video to upload: {video_file.name}")

    # Prepare upload arguments
    step_8_dir = project_dir / STEP_8_DIR
    upload_args = [
        "--input", str(step_7_dir),
        "--output", str(step_8_dir),
        "--video-stem", video_stem,
    ]

    # IMPORTANT: Do NOT pass browser_profile_path for YouTube upload!
    # YouTube upload needs the CHANNEL'S browser profile (with saved YouTube cookies),
    # NOT the parallel processing profile (which is only for Fish Audio voiceover).
    # The 10_youtube_upload.py script will automatically use browser_profiles/profile_{channel_name}

    if prompt_profile:
        profile_suffix = prompt_profile.get("suffix", "BASKLY")
        upload_args.extend(["--profiles", profile_suffix])

        youtube_channel = prompt_profile.get("youtube_channel", "Default Channel")
        wait_minutes = prompt_profile.get("upload_wait_minutes", 5)
        upload_args.extend(["--wait-minutes", str(wait_minutes)])

        logger.info(f"📺 [{video_stem}] Uploading to channel: {youtube_channel}")
        logger.info(f"⏱️ [{video_stem}] Upload wait time: {wait_minutes} minutes")

    settings = get_pipeline_settings()
    if settings.get("step_8_youtube_upload", {}).get("dry_run", False):
        logger.info(f"🧪 [{video_stem}] DRY RUN MODE")

    # Use lock to prevent multiple browsers opening at the same time
    # Only one upload can run at a time for the same channel
    channel_lock = get_channel_upload_lock(profile_suffix)
    logger.info(f"🔒 [{video_stem}] Waiting for upload lock (channel: {profile_suffix})...")

    with channel_lock:
        logger.info(f"🚀 [{video_stem}] Lock acquired, starting YouTube upload...")
        return run_python_script(YOUTUBE_UPLOAD_SCRIPT, upload_args, capture_output=False)


# =============================================================================
# THUMBNAIL GENERATOR - STEP 11
# =============================================================================

THUMBNAIL_GENERATOR_SCRIPT = Path(__file__).parent / "11_thumbnail_generator.py"


def run_thumbnail_generator_step(video_stem: str, project_dir: Path, prompt_profile: Dict = None, input_folder: Path = None) -> bool:
    """Step 11: Generate viral thumbnail ideas and image prompts

    Args:
        video_stem: Video stem name
        project_dir: Project directory (e.g., OUTPUT/OG-1/BASKLY)
        prompt_profile: Profile settings dictionary
        input_folder: Input folder (for title mode - to find thumbnail_TITLE.jpg)

    Returns:
        bool: True if successful
    """
    profile_name = prompt_profile.get('name', 'Unknown') if prompt_profile else 'Unknown'

    # Read thumb_mode and AI provider from config
    # thumbnail_ai_settings.provider is the dedicated setting for thumbnail AI
    thumb_mode = 'title'
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
                    # Check cc_quick_options.thumb_mode FIRST (for Content Creator)
                    thumb_mode = config.get('cc_quick_options', {}).get('thumb_mode', '')
                    if not thumb_mode:
                        # Fallback to processing_settings.thumb_mode
                        thumb_mode = config.get('processing_settings', {}).get('thumb_mode', 'title')
                    if not thumb_mode:
                        thumb_mode = 'title'

                    # Get AI provider from thumbnail_ai_settings (separate setting for thumbnails)
                    ai_provider = config.get('thumbnail_ai_settings', {}).get('provider', 'claude')
                    if not ai_provider:
                        ai_provider = 'claude'
                    break
    except Exception as e:
        logger.warning(f"Could not read thumb_mode from config: {e}")

    # === CHECK IF THUMBNAIL GENERATION IS DISABLED ===
    if thumb_mode and thumb_mode.lower() == 'off':
        logger.info(f"⏭️ [{video_stem}] Thumbnail generation is OFF - skipping")
        return True

    logger.info(f"🎨 [{video_stem}] Starting Thumbnail Generator...")
    logger.info(f"🎨 [{video_stem}] Mode: {thumb_mode}")
    logger.info(f"🎨 [{video_stem}] Profile: {profile_name}")

    # Thumbnail files saved in 8_youtube_upload folder (with the final video)
    step_8_dir = project_dir / STEP_8_DIR
    prompt_file = step_8_dir / "thumbnail_prompt.txt"

    if prompt_file.exists():
        logger.info(f"⏭️ [{video_stem}] Thumbnail already generated: {prompt_file}")
        return True

    # Choose project-dir based on mode
    if thumb_mode == 'title' and input_folder and input_folder.exists():
        # Title mode: use input folder to find thumbnail_TITLE.jpg
        source_dir = str(input_folder)
        logger.info(f"🎨 [{video_stem}] Using input folder for title extraction: {input_folder}")
    else:
        # Script mode: use project dir for script content
        source_dir = str(project_dir)
        logger.info(f"🎨 [{video_stem}] Using project dir for script: {project_dir}")

    # Prepare arguments with AI provider
    thumbnail_args = [
        "--project-dir", source_dir,
        "--output-dir", str(step_8_dir),
        "--mode", thumb_mode,
        "--provider", ai_provider,
    ]

    logger.info(f"🎨 [{video_stem}] Generating thumbnail ideas and prompt (AI: {ai_provider})...")
    return run_python_script(THUMBNAIL_GENERATOR_SCRIPT, thumbnail_args, capture_output=False)


def run_voiceover_step_multi_window_new(video_stem: str, project_dir: Path, voiceovers_dir: Path,
                                        selected_profiles: List, temp_script_dir: Path) -> bool:
    """NEW: Run multi-window voiceover generation using smart-generated script"""
    logger.info(f"🎤 Starting NEW multi-window voiceover generation using smart-generated script...")

    # Create the expected script folder structure for the old voiceover function
    script_dir = project_dir / SUBDIR_SCRIPT
    script_dir.mkdir(exist_ok=True)

    # Copy the profile-specific scripts for each selected profile using Profile-First Structure
    import shutil
    for profile_key, profile_info in selected_profiles:
        # Use Profile-First Structure path
        paths = get_profile_paths(project_dir, profile_info['suffix'])
        profile_script_path = paths["output_script"]

        if not profile_script_path.exists():
            logger.error(f"❌ Profile script not found: {profile_script_path}")
            logger.error(f"   Expected Profile-First Structure path: {profile_script_path}")
            return False

        expected_script_name = f"{video_stem}_rewritten_script_{profile_key}.txt"
        expected_script_path = script_dir / expected_script_name
        shutil.copy2(profile_script_path, expected_script_path)
        logger.info(f"📝 Copied profile-specific script for {profile_key}: {expected_script_path}")
        logger.info(f"   Source: {profile_script_path}")

    # Call the existing multi-window voiceover generation with the properly structured scripts
    return run_voiceover_step_multi_window(video_stem, script_dir, voiceovers_dir,
                                           selected_profiles, temp_script_dir)


def run_transcription_step(video_stem: str, primary_clips_dir: Path, transcripts_dir: Path,
                           temp_script_dir: Path) -> bool:
    """Run transcription step with dynamic configuration"""
    # Smart skip: Check if transcript already exists
    final_transcript_path = transcripts_dir / f"{video_stem}_raw_transcript.txt"
    if final_transcript_path.exists() and final_transcript_path.stat().st_size > 100:  # Check file exists and has content
        logger.info(f"⚡ SMART SKIP: Found existing transcript: {final_transcript_path}")
        logger.info("   → Skipping transcription (delete transcript file to regenerate)")
        return True
    else:
        logger.info(f"📝 No existing transcript found, proceeding with transcription...")

    temp_video_to_script = create_temp_modified_script(
        VIDEO_TO_SCRIPT_SCRIPT,
        {
            r'INPUT_FOLDERS\s*=\s*\[.*?\]': f'INPUT_FOLDERS = [r"{primary_clips_dir.as_posix()}"]',
            r'OUTPUT_BASE_FOLDER\s*=\s*r".*?"': f'OUTPUT_BASE_FOLDER = r"{transcripts_dir.as_posix()}"',
            r'SAVE_SRT_FILES\s*=\s*False': f'SAVE_SRT_FILES = {TRANSCRIPTION_SAVE_SRT_FILES}',
            r'SAVE_INDIVIDUAL_TXT\s*=\s*False': f'SAVE_INDIVIDUAL_TXT = {TRANSCRIPTION_SAVE_INDIVIDUAL_TXT_FILES}',
            r'SAVE_COMBINED_FILE\s*=\s*False': f'SAVE_COMBINED_FILE = {TRANSCRIPTION_SAVE_COMBINED_FILE}',
            r'SAVE_JSON_FILES\s*=\s*False': f'SAVE_JSON_FILES = {TRANSCRIPTION_SAVE_JSON_FILES}',
            r'COMBINED_FILE_NAME\s*=\s*".*?"': f'COMBINED_FILE_NAME = "{video_stem}_raw_transcript.txt"',
            r'CREATE_FOLDER_PER_INPUT\s*=\s*True': f'CREATE_FOLDER_PER_INPUT = {TRANSCRIPTION_CREATE_FOLDER_PER_INPUT}',
            r'SHOW_PROGRESS_BAR\s*=\s*True': f'SHOW_PROGRESS_BAR = {TRANSCRIPTION_SHOW_PROGRESS_BAR}',
            r'SHOW_DETAILED_LOGS\s*=\s*True': f'SHOW_DETAILED_LOGS = {TRANSCRIPTION_SHOW_DETAILED_LOGS}',
        },
        temp_script_dir
    )

    if not temp_video_to_script:
        return False

    success = run_python_script(temp_video_to_script, [], capture_output=False)

    # Handle transcript file naming
    final_transcript_path = transcripts_dir / f"{video_stem}_raw_transcript.txt"
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


def run_ai_script_step_single(video_stem: str, transcripts_dir: Path, ai_scripts_dir: Path, prompt_profile: Dict,
                              api_key: str) -> bool:
    """Run AI script rewriting step for single mode"""
    final_transcript_path = transcripts_dir / f"{video_stem}_raw_transcript.txt"
    # Fix: Use consistent naming with profile suffix like in multi mode
    rewritten_script_path = ai_scripts_dir / f"{video_stem}_rewritten_script_{prompt_profile['suffix']}.txt"

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

    gemini_args = [
        "--input-file", str(final_transcript_path),
        "--output-file", str(rewritten_script_path),
        "--prompt-file", str(prompt_profile["prompt_file"]),
        "--model-name", AI_REWRITE_MODEL_NAME,
    ]

    if api_key:
        gemini_args.extend(["--api-key", api_key])
        logger.info("🔑 Using API key for Gemini")
    else:
        logger.warning("⚠️ No API key provided for Gemini")

    success = run_python_script(SCRIPT_WRITER_AI_SCRIPT, gemini_args, capture_output=False)

    # Debug: Check if output file was created
    if success and rewritten_script_path.exists():
        logger.info(f"✅ AI script created successfully: {rewritten_script_path}")
    elif success:
        logger.warning(f"⚠️ Script reported success but output file not found: {rewritten_script_path}")
    else:
        logger.error(f"❌ AI script creation failed")

    return success


def run_ai_script_step_multi(video_stem: str, transcripts_dir: Path, ai_scripts_dir: Path, prompt_profile: Dict,
                             api_key: str) -> bool:
    """Run AI script rewriting step for numbered mode"""
    final_transcript_path = transcripts_dir / f"{video_stem}_raw_transcript.txt"
    rewritten_script_path = ai_scripts_dir / f"{video_stem}_rewritten_script_{prompt_profile['suffix']}.txt"

    gemini_args = [
        "--input-file", str(final_transcript_path),
        "--output-file", str(rewritten_script_path),
        "--prompt-file", str(prompt_profile["prompt_file"]),
        "--model-name", AI_REWRITE_MODEL_NAME,
    ]

    if api_key:
        gemini_args.extend(["--api-key", api_key])

    return run_python_script(SCRIPT_WRITER_AI_SCRIPT, gemini_args, capture_output=False)


def run_voiceover_step_single(video_stem: str, ai_scripts_dir: Path, voiceovers_dir: Path, voice_url: str,
                              temp_script_dir: Path, prompt_profile: Dict) -> bool:
    """Run voiceover generation step for single mode"""
    # Fix: Use consistent naming with profile suffix like in multi mode
    script_path = ai_scripts_dir / f"{video_stem}_rewritten_script_{prompt_profile['suffix']}.txt"

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
    version_voiceover_dir = voiceovers_dir / f"{video_stem}_voiceover_{prompt_profile['suffix']}"
    version_voiceover_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Created voiceover directory: {version_voiceover_dir}")

    voiceover_modifications = {
        r'DEFAULT_OUTPUT_FOLDER\s*=\s*r".*?"': f'DEFAULT_OUTPUT_FOLDER = r"{version_voiceover_dir.as_posix()}"',
        r'VOICEOVER_URL\s*=\s*"[^"]*".*': f'VOICEOVER_URL = "{voice_url}"  # Profile-specific voice URL',
        r'BASE_WAIT_TIME\s*=\s*\d+': f'BASE_WAIT_TIME = {FISH_AUDIO_BASE_WAIT_TIME}',
        r'SECONDS_PER_100_CHARS\s*=\s*\d+': f'SECONDS_PER_100_CHARS = {FISH_AUDIO_SECONDS_PER_100_CHARS}',
        r'MAX_WAIT_TIME\s*=\s*\d+': f'MAX_WAIT_TIME = {FISH_AUDIO_MAX_WAIT_TIME}',
        r'text_file_path\s*=\s*input\(.*?\)\.strip\(\)\s*or\s*".*?"': f'text_file_path = r"{script_path.as_posix()}"',
        r'output_folder\s*=\s*input\(.*?\)\.strip\(\)\s*or\s*DEFAULT_OUTPUT_FOLDER': f'output_folder = r"{version_voiceover_dir.as_posix()}"',
        r'num_tabs\s*=\s*input\(.*?\)\.strip\(\)': f'num_tabs = "{FISH_AUDIO_NUM_TABS}"',
        r'num_tabs\s*=\s*int\(num_tabs\)\s*if\s*num_tabs\.isdigit\(\)\s*else\s*2': f'num_tabs = {FISH_AUDIO_NUM_TABS}',
        r'input\("🔑 Make sure all tabs are logged in and ready, then press Enter\.\.\."\)': f'# Automated mode ({prompt_profile["suffix"]}) - skipping manual confirmation',
        r'input\("Press Enter to close browser\.\.\."\)': f'# Automated mode ({prompt_profile["suffix"]}) - auto-closing browser',
    }

    temp_script = create_temp_modified_script(SCRIPT_VOICE_SCRIPT, voiceover_modifications, temp_script_dir)
    if not temp_script:
        return False

    return run_python_script(temp_script, [], capture_output=False)


def run_voiceover_step_multi(video_stem: str, ai_scripts_dir: Path, voiceovers_dir: Path, prompt_profile: Dict,
                             temp_script_dir: Path) -> bool:
    """Run voiceover generation step for numbered mode"""
    script_path = ai_scripts_dir / f"{video_stem}_rewritten_script_{prompt_profile['suffix']}.txt"
    voice_url = get_voice_url_by_name(prompt_profile["default_voice"])

    # Debug logging
    logger.info(f"🎤 Setting up voiceover for profile: {prompt_profile['name']}")
    logger.info(f"🔊 Profile default voice: {prompt_profile['default_voice']}")
    logger.info(f"🌐 Voice URL to use: {voice_url}")

    version_voiceover_dir = voiceovers_dir / f"{video_stem}_voiceover_{prompt_profile['suffix']}"
    version_voiceover_dir.mkdir(parents=True, exist_ok=True)

    # Only modify the VOICEOVER_URL in the temp script (voice URL must be set in code)
    voiceover_modifications = {
        r'VOICEOVER_URL\s*=\s*"[^"]*"\s*#?.*': f'VOICEOVER_URL = "{voice_url}"  # Profile-specific voice URL',
    }

    temp_script = create_temp_modified_script(SCRIPT_VOICE_SCRIPT, voiceover_modifications,
                                              temp_script_dir / f"voiceover_{prompt_profile['suffix']}")
    if not temp_script:
        return False

    # Debug: Log the temp script path and arguments
    logger.info(f"📄 Created temp voiceover script: {temp_script}")
    logger.info(f"📝 Script file input: {script_path}")
    logger.info(f"📁 Output directory: {version_voiceover_dir}")
    logger.info(f"🔢 Number of tabs: {FISH_AUDIO_NUM_TABS}")

    # Check if script file exists before running
    if not script_path.exists():
        logger.error(f"❌ Script file not found: {script_path}")
        return False

    # Run the voiceover script with command line arguments (instead of regex modifications)
    voiceover_args = [
        str(script_path),  # positional argument: text file
        "--output-folder", str(version_voiceover_dir),
        "--num-tabs", str(FISH_AUDIO_NUM_TABS),
        "--voice-url", voice_url,
        "--voice-name", prompt_profile['default_voice'],
    ]
    success = run_python_script(temp_script, voiceover_args, capture_output=False)

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


def run_voiceover_step_multi_window(video_stem: str, ai_scripts_dir: Path, voiceovers_dir: Path,
                                    selected_profiles: List, temp_script_dir: Path) -> bool:
    """Run voiceover generation using multi-window parallel processing"""

    # Check if using API method (read fresh from config at runtime)
    if is_using_api_method():
        logger.info("🚀 Using Fish Audio API for voiceover generation (multi-profile)...")
        all_success = True
        for profile_key, profile_info in selected_profiles:
            # Find the script file for this profile
            script_file = ai_scripts_dir / f"{video_stem}_rewritten_script_{profile_info['suffix']}.txt"
            if not script_file.exists():
                logger.error(f"❌ Script not found: {script_file}")
                all_success = False
                continue

            success = run_voiceover_with_api(script_file, voiceovers_dir, video_stem, profile_info)
            if not success:
                all_success = False
                logger.error(f"   ❌ Failed to generate {profile_info['name']} voiceover via API")
            else:
                logger.info(f"   ✅ Generated {profile_info['name']} voiceover via API")
        return all_success

    if not USE_MULTI_WINDOW_VOICEOVER or not ENABLE_PROFILE_PARALLEL_PROCESSING:
        # Fallback to sequential processing
        logger.info("🧠 Using sequential voiceover processing...")
        all_success = True
        for profile_key, profile_info in selected_profiles:
            success = run_voiceover_step_multi(video_stem, ai_scripts_dir, voiceovers_dir, profile_info,
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
        script_file = ai_scripts_dir / f"{video_stem}_rewritten_script_{profile_info['suffix']}.txt"
        output_folder = voiceovers_dir / f"{video_stem}_voiceover_{profile_info['suffix']}"
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
voiceover_module = importlib.import_module(os.path.splitext(os.path.basename(r"{SCRIPT_VOICE_SCRIPT}"))[0])

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


def run_broll_step(primary_clips_dir: Path, rearranged_broll_clips_dir: Path, voiceovers_dir: Path = None) -> bool:
    """Run B-roll clips generation using smart processor (no merging)"""

    # Determine source directory based on settings
    if USE_VOICEOVER_CLIPS_FOR_BROLL:
        # Use the original video clips from Step 1 (1_clips/voiceover folder)
        clips_base_dir = voiceovers_dir.parent / "1_clips" / "voiceover"
        if clips_base_dir.exists():
            # Check if this directory actually contains video files, not audio
            test_files = list(clips_base_dir.glob("*.mp4"))
            if test_files:
                source_dir = clips_base_dir
                logger.info(f"🎬 Starting B-roll processing using VOICEOVER VIDEO clips from {source_dir}")
            else:
                logger.warning(f"⚠️ Voiceover directory contains no video files, falling back to primary clips")
                source_dir = primary_clips_dir
                logger.info(f"🎬 Starting B-roll processing using PRIMARY clips from {source_dir}")
        else:
            source_dir = primary_clips_dir
            logger.warning(f"⚠️ Voiceover video clips directory not found, falling back to primary clips")
            logger.info(f"🎬 Starting B-roll processing using PRIMARY clips from {source_dir}")
    else:
        source_dir = primary_clips_dir
        logger.info(f"🎬 Starting B-roll processing using PRIMARY clips from {source_dir}")

    # Ensure destination directory exists
    rearranged_broll_clips_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📂 Destination directory: {rearranged_broll_clips_dir}")

    # Get max clips setting from configuration
    max_clips = BROLL_REARRANGEMENT_SETTINGS.get('max_clips', 100)
    logger.info(f"🎯 Maximum clips to generate: {max_clips}")

    # Check if Python script exists (preferred method)
    smart_processor_script = SCRIPT_DIR / "4_smart_broll_processor.py"

    if smart_processor_script.exists():
        # Use the smart Python processor (no merging)
        logger.info("🚀 Using smart B-roll processor (no merging)")
        logger.info("🎬 This will create 6-second clips from each video individually")

        try:
            # Run the Python script
            args = [
                str(source_dir),
                str(rearranged_broll_clips_dir),
                "--max-clips", str(max_clips)
            ]

            result = run_python_script(smart_processor_script, args, capture_output=False)

            if result:
                # Check if clips were created
                final_clips = list(rearranged_broll_clips_dir.glob("*.mp4"))
                clip_count = len(final_clips)
                logger.info(f"✅ Smart processing successful! Created {clip_count} clips")
                return True
            else:
                logger.error("❌ Smart processing failed")
                return False

        except Exception as e:
            logger.error(f"❌ Smart processing failed: {e}")
            # Fall back to batch file
            logger.info("⚠️ Falling back to batch file method...")

    # Fallback: Use batch file if Python script doesn't exist
    if CLIPS_MAKER_BATCH.exists():
        logger.info(f"🚀 Running batch file: {CLIPS_MAKER_BATCH.name}")
        logger.info("⚠️ Note: Batch file uses merging which may create too many clips")

        # Copy videos to destination for batch processing
        import shutil
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv']
        video_files = []

        for file_path in source_dir.glob("*"):
            if file_path.suffix.lower() in video_extensions:
                dest_path = rearranged_broll_clips_dir / file_path.name
                shutil.copy2(file_path, dest_path)
                video_files.append(dest_path)
                logger.info(f"📄 Copied: {file_path.name}")

        if not video_files:
            logger.error("❌ No video files found to process!")
            return False

        try:
            result = run_batch_script(CLIPS_MAKER_BATCH, cwd=rearranged_broll_clips_dir)

            # Check if clips were created
            final_clips = list(rearranged_broll_clips_dir.glob("*.mp4"))
            clip_count = len(final_clips)

            if clip_count > 0:
                logger.info(f"✅ Batch processing successful! Created {clip_count} clips")
                return True
            else:
                logger.error("❌ Batch processing failed - no clips created")
                return False

        except Exception as e:
            logger.error(f"❌ Batch processing failed: {e}")
            return False

    logger.error("❌ No B-roll processing script found!")
    return False


def run_assembly_step_single(video_stem: str, voiceovers_dir: Path, clips_dir: Path, final_videos_dir: Path,
                             log_dir: Path, prompt_profile: Dict) -> bool:
    """Run final video assembly for single mode with GPU acceleration"""
    cache_file = log_dir / f"{video_stem}_assemble_cache_{prompt_profile['suffix']}.json"

    # Create clean profile-specific directories using step-based structure
    step_3_dir = voiceovers_dir.parent / STEP_3_DIR
    version_voiceover_dir = step_3_dir / f"{video_stem}_voiceover_{prompt_profile['suffix']}"
    version_final_dir = final_videos_dir / prompt_profile['suffix']
    version_final_dir.mkdir(parents=True, exist_ok=True)

    assembly_args = [
        "--voiceovers", str(version_voiceover_dir),
        "--clips", str(clips_dir),
        "--output", str(version_final_dir),
        "--cache-file", str(cache_file),
    ]

    # Note: 7_assemble_final_video.py doesn't support GPU args, using default settings
    if not ASSEMBLE_VIDEO_USE_FAST_COPY:
        assembly_args.append("--quality")

    logger.info(f"🔧 Assembly args: {' '.join(assembly_args)}")
    # Disable logo for Create Video mode
    return run_python_script(CLIPS_PLUS_VOICEOVER_SCRIPT, assembly_args, capture_output=True,
                            env_vars={"ENABLE_LOGO_FEATURE": "false"})


def run_assembly_step_multi(video_stem: str, voiceovers_dir: Path, clips_dir: Path, final_videos_dir: Path,
                            log_dir: Path, prompt_profile: Dict) -> bool:
    """Run final video assembly for numbered mode"""
    cache_file = log_dir / f"{video_stem}_assemble_cache_{prompt_profile['suffix']}.json"

    step_3_dir = voiceovers_dir.parent / STEP_3_DIR
    version_voiceover_dir = step_3_dir / f"{video_stem}_voiceover_{prompt_profile['suffix']}"
    version_final_dir = final_videos_dir / prompt_profile['suffix']
    version_final_dir.mkdir(parents=True, exist_ok=True)

    assembly_args = [
        "--voiceovers", str(version_voiceover_dir),
        "--clips", str(clips_dir),
        "--output", str(version_final_dir),
        "--cache-file", str(cache_file),
    ]

    # Note: 7_assemble_final_video.py doesn't support GPU/preset args
    if not ASSEMBLE_VIDEO_USE_FAST_COPY:
        assembly_args.append("--quality")

    logger.info(f"🔧 Assembly args: {' '.join(assembly_args)}")
    # Disable logo for Create Video mode
    return run_python_script(CLIPS_PLUS_VOICEOVER_SCRIPT, assembly_args, capture_output=True,
                            env_vars={"ENABLE_LOGO_FEATURE": "false"})


def run_audio_cleaning_step_single(video_stem: str, inverse_clips_dir: Path, cleaned_audio_dir: Path,
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
    interview_files = list(inverse_clips_dir.glob(f"{video_stem}_interview_*.wav"))
    if not interview_files:
        interview_files = list(inverse_clips_dir.glob(f"{video_stem}_interview_*.mp3"))
    if not interview_files:
        # Look for "others" pattern (common from diarization step)
        interview_files = list(inverse_clips_dir.glob(f"{video_stem}_others_*.mp4"))
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


def run_audio_cleaning_step_multi(video_stem: str, inverse_clips_dir: Path, cleaned_audio_dir: Path) -> bool:
    """Run audio cleaning step for multi mode - uses same GPU acceleration as single mode"""
    return run_audio_cleaning_step_single(video_stem, inverse_clips_dir, cleaned_audio_dir, {})


def run_ranking_step_single(video_stem: str, inverse_clips_dir: Path, final_videos_dir: Path,
                            ranked_sequence_dir: Path, prompt_profile: Dict) -> bool:
    """Run video ranking step for single mode"""
    # Use the final_videos_dir directly with profile suffix (Step 4)
    version_final_dir = final_videos_dir / prompt_profile['suffix']

    # Use the passed ranked_sequence_dir directly (it's already profile-specific)
    ranking_args = [
        "--interviews", str(inverse_clips_dir),
        "--voiceovers", str(version_final_dir),
        "--output", str(ranked_sequence_dir),
        "--video-stem", video_stem,
    ]

    return run_python_script(RANK_VIDEO_SEQUENCE_SCRIPT, ranking_args, capture_output=True)


def run_ranking_step_multi(video_stem: str, inverse_clips_dir: Path, final_videos_dir: Path,
                           ranked_sequence_dir: Path) -> bool:
    """Run video ranking step for numbered mode"""
    ranking_args = [
        "--interviews", str(inverse_clips_dir),
        "--voiceovers", str(final_videos_dir),
        "--output", str(ranked_sequence_dir),
        "--video-stem", video_stem,
    ]

    return run_python_script(RANK_VIDEO_SEQUENCE_SCRIPT, ranking_args, capture_output=True)


def run_metadata_step_single(video_stem: str, ai_scripts_dir: Path, metadata_dir: Path,
                             prompt_profile: Dict, api_key: str) -> bool:
    """Run metadata generation step for single mode"""
    # Use profile-specific script file like other steps
    script_path = ai_scripts_dir / f"{video_stem}_rewritten_script_{prompt_profile['suffix']}.txt"

    # Create profile-specific metadata directory
    version_metadata_dir = metadata_dir / f"{video_stem}_metadata_{prompt_profile['suffix']}"
    version_metadata_dir.mkdir(parents=True, exist_ok=True)

    # Check if script file exists
    if not script_path.exists():
        logger.error(f"❌ Script file not found for metadata generation: {script_path}")
        return False

    # Set up the metadata prompt file path (should be in script directory)
    prompt_file = SCRIPT_DIR / "metadata-prompt-clean.txt"
    if not prompt_file.exists():
        logger.warning(f"⚠️ Metadata prompt file not found: {prompt_file}")
        logger.info("Will use default prompt built into the script")

    metadata_args = [
        "--script-folder", str(ai_scripts_dir),
        "--output-folder", str(version_metadata_dir),
        "--prompt-file", str(prompt_file),
        "--video-name", f"{video_stem}_{prompt_profile['suffix']}",
    ]

    if api_key:
        metadata_args.extend(["--api-key", api_key])
        logger.info("🔑 Using API key for metadata generation")
    else:
        logger.warning("⚠️ No API key provided for metadata generation")

    logger.info(f"📊 Generating metadata for {prompt_profile['name']} profile...")
    success = run_python_script(GENERATE_METADATA_SCRIPT, metadata_args, capture_output=False)

    if success:
        logger.info(f"✅ Metadata generated for {prompt_profile['name']}")
    else:
        logger.error(f"❌ Failed to generate metadata for {prompt_profile['name']}")

    return success


def run_metadata_step_multi(video_stem: str, ai_scripts_dir: Path, metadata_dir: Path,
                            prompt_profile: Dict, api_key: str) -> bool:
    """Run metadata generation step for numbered mode"""
    # Use profile-specific script file
    script_path = ai_scripts_dir / f"{video_stem}_rewritten_script_{prompt_profile['suffix']}.txt"

    # Create profile-specific metadata directory
    version_metadata_dir = metadata_dir / f"{video_stem}_metadata_{prompt_profile['suffix']}"
    version_metadata_dir.mkdir(parents=True, exist_ok=True)

    # Check if script file exists
    if not script_path.exists():
        logger.error(f"❌ Script file not found for metadata generation: {script_path}")
        return False

    # Set up the metadata prompt file path
    prompt_file = SCRIPT_DIR / "metadata-prompt-clean.txt"
    if not prompt_file.exists():
        logger.warning(f"⚠️ Metadata prompt file not found: {prompt_file}")

    metadata_args = [
        "--script-folder", str(ai_scripts_dir),
        "--output-folder", str(version_metadata_dir),
        "--prompt-file", str(prompt_file),
        "--video-name", f"{video_stem}_{prompt_profile['suffix']}",
    ]

    if api_key:
        metadata_args.extend(["--api-key", api_key])

    logger.info(f"📊 Generating {prompt_profile['name']} metadata...")
    success = run_python_script(GENERATE_METADATA_SCRIPT, metadata_args, capture_output=False)

    if success:
        logger.info(f"   ✅ Generated {prompt_profile['name']} metadata")
    else:
        logger.error(f"   ❌ Failed to generate {prompt_profile['name']} metadata")

    return success


# ==============================================================================
# --- MAIN PIPELINE FUNCTIONS (FIXED) ---
# ==============================================================================

def process_video_pipeline_custom(video_path: Path, project_base_dir: Path, api_key_gemini: str, selected_prompt: Dict,
                                  selected_voice: Dict, force_start_from: int = -1) -> bool:
    """Process video with custom prompt + voice selection"""
    video_stem = video_path.stem

    # Use parent folder name for output directory (same as batch mode)
    folder_name = video_path.parent.name
    if folder_name in ["vd-1", "videos", "interviews", "input", "input_videos"]:
        # Try to use grandparent folder name
        grandparent_name = video_path.parent.parent.name
        if grandparent_name and grandparent_name not in ["videos", "interviews", "input", "make-new-video"]:
            folder_name = grandparent_name
        else:
            # Use video stem as fallback
            folder_name = video_stem

    # Define directories
    video_output_dir = project_base_dir / folder_name
    log_dir = video_output_dir / SUBDIR_LOGS
    original_video_copy_dir = video_output_dir / SUBDIR_ORIGINAL_VIDEO
    clips_main_dir = video_output_dir / SUBDIR_CLIPS_MAIN
    primary_clips_dir = clips_main_dir / SUBDIR_PRIMARY_CLIPS
    inverse_clips_dir = clips_main_dir / SUBDIR_INVERSE_CLIPS
    # Step-based directory structure
    step_1_dir = video_output_dir / STEP_1_DIR
    step_2_dir = video_output_dir / STEP_2_DIR
    step_3_dir = video_output_dir / STEP_3_DIR
    step_4_dir = video_output_dir / STEP_4_DIR
    step_5_dir = video_output_dir / STEP_5_DIR
    step_6_dir = video_output_dir / STEP_6_DIR
    step_7_dir = video_output_dir / STEP_7_DIR
    step_8_dir = video_output_dir / STEP_8_DIR
    step_8_dir = video_output_dir / STEP_8_DIR

    # Step 1 subdirectories
    interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS
    broll_clips_dir = step_1_dir / SUBDIR_BROLL_CLIPS

    # Create only clean step-based directories (no legacy folders)
    for d in [video_output_dir, log_dir, original_video_copy_dir,
              step_1_dir, step_2_dir, step_3_dir, step_4_dir, step_5_dir, step_6_dir, step_7_dir, step_8_dir,
              interview_clips_dir, broll_clips_dir]:
        d.mkdir(parents=True, exist_ok=True)

    temp_script_dir = log_dir / SUBDIR_TEMP_SCRIPTS
    temp_script_dir.mkdir(parents=True, exist_ok=True)

    status_filepath = log_dir / STATUS_FILE_NAME
    current_status = load_video_status(status_filepath)
    pipeline_steps_info = get_pipeline_steps_info(multi_mode=False)

    logger.info(f"\n{'=' * 80}\nProcessing Video (CUSTOM MODE): {video_path.name}")
    logger.info(f"Custom Configuration:")
    logger.info(f"  Prompt: {selected_prompt['name']}")
    logger.info(f"  Voice: {selected_voice['name']}")
    logger.info(f"Output: {video_output_dir}\n{'=' * 80}")

    overall_success = True

    for step_num in sorted(pipeline_steps_info.keys()):
        if step_num < force_start_from and force_start_from != -1:
            continue

        step_info = pipeline_steps_info[step_num]
        logger.info(f"\n🚀 Step {step_num}: {step_info['name']}...")

        current_status[STATUS_KEY_STATE] = "running"
        save_video_status(status_filepath, current_status)

        step_success = False

        try:
            if step_num == 0:
                shutil.copy(video_path, original_video_copy_dir / video_path.name)
                step_success = True
            elif step_num == 1:
                # NEW: Smart Interview Processing - combines transcription, extraction, and script creation
                step_1_dir = video_output_dir / STEP_1_DIR
                transcripts_output_dir = video_output_dir / "1_transcripts"  # Legacy location
                interview_clips_output_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS
                script_output_dir = step_1_dir
                voiceover_script_path = video_output_dir / "voiceover_script.txt"

                # Smart skip: Check if smart processing outputs already exist
                interview_clips = list(
                    interview_clips_output_dir.glob("*.mp4")) if interview_clips_output_dir.exists() else []

                # Check for Profile-First Structure completion
                profile_suffix = selected_profiles[0][1]['suffix'] if selected_profiles else 'default'
                paths = get_profile_paths(video_output_dir, profile_suffix)

                # Check if Profile-First Structure exists and is complete
                profile_complete = (paths["profile_dir"].exists() and
                                    paths["output_script"].exists() and
                                    len(interview_clips) > 0)

                if profile_complete:
                    logger.info(
                        f"⚡ SMART SKIP: Found Profile-First Structure with {len(interview_clips)} interview clips")
                    logger.info(f"   → Profile: {selected_profiles[0][1]['name']}")
                    logger.info(f"   → Script: {paths['output_script']}")
                    logger.info("   → Skipping smart processing (delete profile folders to regenerate)")
                    step_success = True
                else:
                    logger.info(f"📁 No existing smart processing outputs found, proceeding...")
                    # For custom mode, use the original video copy directory as interviews folder
                    temp_interviews_folder = original_video_copy_dir
                    temp_broll_folder = broll_folder  # Use the B-roll folder passed from UI
                    # Run simple smart processing
                    step_success = run_smart_interview_processing(temp_interviews_folder,
                                                                  temp_broll_folder, video_output_dir)

            elif step_num == 2:
                # NEW: Style interview clips with frames, animations, and backgrounds (profile-specific)
                step_1_dir = video_output_dir / STEP_1_DIR
                step_2_dir = video_output_dir / STEP_2_DIR

                # All profiles use shared interview clips
                profile_name = selected_prompt['suffix']
                interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS

                # Create profile-specific styled clips directory
                profile_styled_dir = step_2_dir / profile_name
                profile_styled_dir.mkdir(parents=True, exist_ok=True)
                step_success = run_styling_step_single(folder_name, interview_clips_dir, profile_styled_dir,
                                                       selected_prompt)
            elif step_num == 3:
                # NEW: Generate voiceover from AI-created script
                step_3_dir = video_output_dir / STEP_3_DIR
                step_success = run_voiceover_step_single_new(folder_name, video_output_dir, step_3_dir,
                                                             selected_voice["url"], temp_script_dir, selected_prompt,
                                                             browser_profile_path)
            elif step_num == 4:
                # NEW: Rearrange B-roll clips (Create 6-second clips using batch file)
                step_1_dir = video_output_dir / STEP_1_DIR
                step_4_dir = video_output_dir / STEP_4_DIR
                step_4_dir.mkdir(parents=True, exist_ok=True)  # Create Step 4 directory

                # B-roll clips are ALWAYS shared (both modes use same broll_clips/)
                broll_clips_dir = step_1_dir / SUBDIR_BROLL_CLIPS

                logger.info(f"🎬 Rearranging B-roll clips - Creating 6-second clips for final assembly...")
                step_success = run_broll_step(broll_clips_dir, step_4_dir, video_output_dir / STEP_3_DIR)

                if step_success:
                    logger.info("✅ B-roll clips rearranged - 6-second clips created successfully!")
                    logger.info(f"📂 6-second clips saved to: {step_4_dir}")
                else:
                    logger.warning("⚠️ B-roll clips rearrangement failed, continuing with original clips")

            elif step_num == 5:
                # NEW: Assemble final videos using voiceovers and 6-second clips from Step 4
                step_3_dir = video_output_dir / STEP_3_DIR
                step_4_dir = video_output_dir / STEP_4_DIR  # Use 6-second clips from Step 4
                step_5_dir = video_output_dir / STEP_5_DIR
                step_success = run_assembly_step_single(folder_name, step_3_dir, step_4_dir,
                                                        step_5_dir, log_dir, selected_prompt)
            elif step_num == 6:
                # NEW: Rank video sequence using profile-specific styled clips and final videos
                step_2_dir = video_output_dir / STEP_2_DIR  # Use styled clips from Step 2
                step_5_dir = video_output_dir / STEP_5_DIR
                step_6_dir = video_output_dir / STEP_6_DIR
                # Use profile-specific styled clips folder
                profile_styled_dir = step_2_dir / selected_prompt['suffix']
                step_success = run_ranking_step_single_new(video_stem, profile_styled_dir,
                                                           step_5_dir, step_6_dir, selected_prompt)
            elif step_num == 7:
                # NEW: Combine ranked videos with background music
                step_6_dir = video_output_dir / STEP_6_DIR
                step_7_dir = video_output_dir / STEP_7_DIR
                step_success = run_combination_step_single(folder_name, step_6_dir, step_7_dir, selected_prompt['name'],
                                                           selected_prompt)
            elif step_num == 8:
                # NEW: Upload to YouTube with profile-specific settings
                step_8_dir = video_output_dir / STEP_8_DIR
                step_success = run_youtube_upload_step(folder_name, video_output_dir, step_8_dir, selected_prompt,
                                                       browser_profile_path)

        except Exception as e:
            logger.error(f"❌ Step {step_num} failed with error: {e}")
            step_success = False

        if step_success:
            logger.info(f"✅ Step {step_num} completed: {step_info['name']}")
            current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num
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


def process_video_pipeline_batch(project_name: str, project_base_dir: Path, api_key_gemini: str, num_videos: int,
                                 force_start_from: int = -1, interviews_folder: Path = None,
                                 broll_folder: Path = None, folder_name: str = None,
                                 browser_profile_path: str = None) -> bool:
    """NEW: Process ALL profiles - each profile gets its own complete folder structure

    Args:
        folder_name: Optional folder name for prefixed logging in parallel mode
        browser_profile_path: Custom browser profile path for parallel voiceover processing
    """
    # Use FolderLogger if folder_name provided (parallel mode), otherwise global logger
    flog = FolderLogger(logger, folder_name) if folder_name else logger

    # Get ONLY the first N profiles based on user selection
    all_profiles = list(PROMPT_PROFILES.items())
    selected_profiles = all_profiles[:num_videos]

    # Base project directory
    project_output_dir = project_base_dir / project_name
    project_output_dir.mkdir(parents=True, exist_ok=True)

    flog.info(f"\n{'=' * 80}")
    flog.info(f"🎬 MULTI-PROFILE PROCESSING: {project_name}")
    flog.info(f"📁 Creating {num_videos} separate profile folder(s):")
    for profile_key, profile_info in selected_profiles:
        flog.info(f"   • {profile_info['suffix']}/ - {profile_info['name']}")
    flog.info(f"{'=' * 80}\n")

    # Process EACH profile in its own folder
    all_success = True
    for profile_key, profile_info in selected_profiles:
        profile_name = profile_info['suffix']

        flog.info(f"\n{'=' * 80}")
        flog.info(f"🎯 Processing Profile: {profile_name}")
        flog.info(f"{'=' * 80}")

        # Create profile-specific folder: VD-1/BASKLY/
        profile_output_dir = project_output_dir / profile_name

        # Process this profile with single-profile pipeline
        success = process_single_profile_pipeline(
            project_name=project_name,
            profile_output_dir=profile_output_dir,
            profile_info=profile_info,
            interviews_folder=interviews_folder,
            broll_folder=broll_folder,
            force_start_from=force_start_from,
            folder_name=folder_name,
            browser_profile_path=browser_profile_path
        )

        if not success:
            flog.error(f"❌ Failed to process profile: {profile_name}")
            all_success = False
        else:
            flog.info(f"✅ Completed profile: {profile_name}")

    if all_success:
        flog.info(f"\n{'=' * 80}")
        flog.info(f"✅ ALL PROFILES COMPLETED SUCCESSFULLY!")
        flog.info(f"📁 Output location: {project_output_dir}")
        for profile_key, profile_info in selected_profiles:
            flog.info(f"   • {profile_info['suffix']}/")
        flog.info(f"{'=' * 80}\n")
        return True
    else:
        flog.error(f"\n❌ Some profiles failed to process")
        return False


def process_single_profile_pipeline(project_name: str, profile_output_dir: Path, profile_info: Dict,
                                    interviews_folder: Path, broll_folder: Path, force_start_from: int = -1,
                                    folder_name: str = None, browser_profile_path: str = None) -> bool:
    """Process a single profile with complete pipeline in its own folder

    Args:
        folder_name: Optional folder name for prefixed logging in parallel mode
        browser_profile_path: Custom browser profile path for parallel voiceover processing
    """
    # Use FolderLogger if folder_name provided (parallel mode), otherwise global logger
    flog = FolderLogger(logger, folder_name) if folder_name else logger

    # Profile-specific directories: BASKLY/1_processing/, BASKLY/2_styled_clips/, etc.
    log_dir = profile_output_dir / SUBDIR_LOGS
    original_video_copy_dir = profile_output_dir / SUBDIR_ORIGINAL_VIDEO

    # Step-based directory structure inside profile folder
    step_1_dir = profile_output_dir / STEP_1_DIR
    step_2_dir = profile_output_dir / STEP_2_DIR
    step_3_dir = profile_output_dir / STEP_3_DIR
    step_4_dir = profile_output_dir / STEP_4_DIR
    step_5_dir = profile_output_dir / STEP_5_DIR
    step_6_dir = profile_output_dir / STEP_6_DIR
    step_7_dir = profile_output_dir / STEP_7_DIR
    step_8_dir = profile_output_dir / STEP_8_DIR

    # Step 1 subdirectories
    interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS
    broll_clips_dir = step_1_dir / SUBDIR_BROLL_CLIPS

    # Create all directories
    for d in [profile_output_dir, log_dir, original_video_copy_dir,
              step_1_dir, step_2_dir, step_3_dir, step_4_dir, step_5_dir, step_6_dir, step_7_dir, step_8_dir,
              interview_clips_dir, broll_clips_dir]:
        d.mkdir(parents=True, exist_ok=True)

    temp_script_dir = log_dir / SUBDIR_TEMP_SCRIPTS
    temp_script_dir.mkdir(parents=True, exist_ok=True)

    # Status tracking
    status_filepath = log_dir / STATUS_FILE_NAME
    current_status = load_video_status(status_filepath)

    # Define pipeline steps
    pipeline_steps_info = get_pipeline_steps_info(multi_mode=False)

    flog.info(f"📁 Profile output: {profile_output_dir}")
    flog.info(f"🎤 Voice: {profile_info.get('default_voice', 'Unknown')}")

    overall_success = True

    for step_num in sorted(pipeline_steps_info.keys()):
        if step_num < force_start_from and force_start_from != -1:
            continue

        step_info = pipeline_steps_info[step_num]
        flog.info(f"\n🚀 Step {step_num}: {step_info['name']}...")

        current_status[STATUS_KEY_STATE] = "running"
        save_video_status(status_filepath, current_status)

        step_success = False

        try:
            if step_num == 0:
                # Copy interview videos to original folder
                flog.info(f"📁 Copying interview videos...")
                video_files = [f for f in interviews_folder.iterdir() if
                               f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']]
                for video_file in video_files:
                    shutil.copy(video_file, original_video_copy_dir / video_file.name)
                    flog.info(f"   ✅ Copied: {video_file.name}")
                step_success = True

            elif step_num == 1:
                # Smart Interview Processing
                interview_clips = list(interview_clips_dir.glob("*.mp4")) if interview_clips_dir.exists() else []

                if len(interview_clips) > 0:
                    flog.info(f"⚡ AUTO-SKIP STEP 1: Found {len(interview_clips)} interview clips")
                    flog.info("   → Skipping smart processing (delete 1_processing to regenerate)")
                    step_success = True
                else:
                    flog.info(f"📁 Running Smart Interview Processing...")
                    step_success = run_smart_interview_processing(interviews_folder, broll_folder,
                                                                  profile_output_dir, profile_info)

            elif step_num == 2:
                # Style interview clips
                if check_step_complete(2, step_2_dir):
                    styled_clips = list(step_2_dir.glob("*.mp4"))
                    flog.info(f"⚡ AUTO-SKIP STEP 2: Found {len(styled_clips)} styled clips")
                    step_success = True
                else:
                    step_success = run_styling_step_single(project_name, interview_clips_dir, step_2_dir,
                                                           profile_info)

            elif step_num == 3:
                # Generate voiceovers
                if check_step_complete(3, step_3_dir):
                    flog.info(f"⚡ AUTO-SKIP STEP 3: Voiceovers already generated")
                    step_success = True
                else:
                    voice_url = get_voice_url_by_name(profile_info["default_voice"])
                    step_success = run_voiceover_step_single_new(project_name, profile_output_dir,
                                                                 step_3_dir, voice_url,
                                                                 temp_script_dir, profile_info,
                                                                 browser_profile_path)

            elif step_num == 4:
                # Rearrange B-roll clips
                if check_step_complete(4, step_4_dir, expected_patterns=["*.mp4"], min_files=5):
                    broll_clips = list(step_4_dir.glob("*.mp4"))
                    flog.info(f"⚡ AUTO-SKIP STEP 4: Found {len(broll_clips)} B-roll clips")
                    step_success = True
                else:
                    flog.info(f"🎬 Rearranging B-roll clips...")
                    step_success = run_broll_step(broll_clips_dir, step_4_dir, step_3_dir)
                    if step_success:
                        flog.info("✅ B-roll clips rearranged!")
                    else:
                        flog.warning("⚠️ B-roll rearrangement failed")

            elif step_num == 5:
                # Assemble final videos
                if check_step_complete(5, step_5_dir, expected_patterns=["*.mp4"], min_files=5):
                    flog.info(f"⚡ AUTO-SKIP STEP 5: Videos already assembled")
                    step_success = True
                else:
                    step_success = run_assembly_step_single(project_name, step_3_dir, step_4_dir,
                                                           step_5_dir, log_dir, profile_info)

            elif step_num == 6:
                # Rank video sequence
                if check_step_complete(6, step_6_dir):
                    flog.info(f"⚡ AUTO-SKIP STEP 6: Sequence already ranked")
                    step_success = True
                else:
                    step_success = run_ranking_step_single_new(project_name, step_2_dir, step_5_dir,
                                                              step_6_dir, profile_info)

            elif step_num == 7:
                # Combine videos with music
                if check_step_complete(7, step_7_dir, expected_patterns=["*.mp4"], min_files=1):
                    flog.info(f"⚡ AUTO-SKIP STEP 7: Videos already combined")
                    step_success = True
                else:
                    # Don't add profile subfolder - Step 6 outputs directly to step_6_dir
                    step_success = run_combination_step_single(project_name, step_6_dir, step_7_dir,
                                                              None, profile_info)

            elif step_num == 8:
                # Generate Thumbnail (always runs, saved in 8_youtube_upload)
                step_8_dir = profile_output_dir / STEP_8_DIR
                if not (step_8_dir / "thumbnail_prompt.txt").exists():
                    flog.info(f"🎨 Generating thumbnail...")
                    try:
                        run_thumbnail_generator_step(project_name, profile_output_dir, profile_info, interviews_folder)
                        flog.info(f"🎨 ✅ Thumbnail generated!")
                    except Exception as e:
                        flog.warning(f"🎨 ⚠️ Thumbnail generation failed: {e}")
                else:
                    flog.info(f"🎨 Thumbnail already exists, skipping")

                # Upload to YouTube
                if profile_info.get("enable_upload", False):
                    step_success = run_youtube_upload_step(project_name, profile_output_dir, step_8_dir,
                                                           profile_info, browser_profile_path)
                else:
                    flog.info(f"⏭️  Skipping YouTube upload (disabled for this profile)")
                    step_success = True

        except Exception as e:
            flog.error(f"❌ Step {step_num} failed with error: {e}")
            step_success = False

        if step_success:
            flog.info(f"✅ Step {step_num} completed: {step_info['name']}")
            current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num
            save_video_status(status_filepath, current_status)
        else:
            flog.error(f"❌ Pipeline failed at Step {step_num}: {step_info['name']}")
            overall_success = False
            current_status[STATUS_KEY_STATE] = "failed"
            save_video_status(status_filepath, current_status)
            break

    if temp_script_dir.exists():
        try:
            shutil.rmtree(temp_script_dir)
        except:
            pass

    if overall_success:
        current_status[STATUS_KEY_STATE] = "completed"
        save_video_status(status_filepath, current_status)
        flog.info(f"\n✅ Profile pipeline completed successfully: {profile_info['suffix']}")
        return True
    else:
        flog.error(f"\n❌ Profile pipeline failed: {profile_info['suffix']}")
        return False




def process_video_pipeline_numbered(video_path: Path, project_base_dir: Path, api_key_gemini: str, num_videos: int,
                                    force_start_from: int = -1, interviews_folder: Path = None,
                                    broll_folder: Path = None) -> bool:
    """FIXED: Process video with SPECIFIC NUMBER of profiles (1, 2, 3, etc.)"""
    video_stem = video_path.stem

    # Get ONLY the first N profiles based on user selection
    all_profiles = list(PROMPT_PROFILES.items())
    selected_profiles = all_profiles[:num_videos]  # ⭐ KEY FIX: Only process first N profiles

    # Define shared directories
    video_output_dir = project_base_dir / video_stem
    log_dir = video_output_dir / SUBDIR_LOGS
    original_video_copy_dir = video_output_dir / SUBDIR_ORIGINAL_VIDEO
    clips_main_dir = video_output_dir / SUBDIR_CLIPS_MAIN
    primary_clips_dir = clips_main_dir / SUBDIR_PRIMARY_CLIPS
    inverse_clips_dir = clips_main_dir / SUBDIR_INVERSE_CLIPS
    # Step-based directory structure
    step_1_dir = video_output_dir / STEP_1_DIR
    step_2_dir = video_output_dir / STEP_2_DIR
    step_3_dir = video_output_dir / STEP_3_DIR
    step_4_dir = video_output_dir / STEP_4_DIR
    step_5_dir = video_output_dir / STEP_5_DIR
    step_6_dir = video_output_dir / STEP_6_DIR
    step_7_dir = video_output_dir / STEP_7_DIR
    step_8_dir = video_output_dir / STEP_8_DIR
    step_8_dir = video_output_dir / STEP_8_DIR

    # Step 1 subdirectories
    interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS
    broll_clips_dir = step_1_dir / SUBDIR_BROLL_CLIPS

    # Create only clean step-based directories (no legacy folders)
    for d in [video_output_dir, log_dir, original_video_copy_dir,
              step_1_dir, step_2_dir, step_3_dir, step_4_dir, step_5_dir, step_6_dir, step_7_dir, step_8_dir,
              interview_clips_dir, broll_clips_dir]:
        d.mkdir(parents=True, exist_ok=True)

    temp_script_dir = log_dir / SUBDIR_TEMP_SCRIPTS
    temp_script_dir.mkdir(parents=True, exist_ok=True)

    status_filepath = log_dir / STATUS_FILE_NAME
    current_status = load_video_status(status_filepath)
    pipeline_steps_info = get_pipeline_steps_info(multi_mode=True)

    logger.info(f"\n{'=' * 80}\nProcessing Video (NUMBERED MODE): {video_path.name}")
    logger.info(f"Will create {num_videos} video{'s' if num_videos > 1 else ''} using selected profiles:")
    for profile_key, profile_info in selected_profiles:
        logger.info(f"  • {profile_info['name']} using {profile_info['default_voice']} voice")
    logger.info(f"Output: {video_output_dir}\n{'=' * 80}")

    if ENABLE_PARALLEL_STEPS:
        logger.info("⚡ PARALLEL MODE ENABLED: Steps 2+3 will run simultaneously after Step 1")

    overall_success = True

    # Track which steps have been completed in parallel
    parallel_steps_completed = set()

    for step_num in sorted(pipeline_steps_info.keys()):
        if step_num < force_start_from and force_start_from != -1:
            continue

        # Skip if already completed in parallel
        if step_num in parallel_steps_completed:
            logger.info(f"⚡ Step {step_num} already completed in parallel mode, skipping...")
            continue

        step_info = pipeline_steps_info[step_num]
        logger.info(f"\n🚀 Step {step_num}: {step_info['name']}...")

        current_status[STATUS_KEY_STATE] = "running"
        save_video_status(status_filepath, current_status)

        step_success = False

        try:
            if step_num == 0:
                shutil.copy(video_path, original_video_copy_dir / video_path.name)
                step_success = True
            elif step_num == 1:
                # NEW MULTI-MODE: Smart Interview Processing with profile-specific scripts
                step_1_dir = video_output_dir / STEP_1_DIR
                interview_clips_output_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS

                # Smart skip: Check if Profile-First Structure exists for all profiles
                interview_clips = list(
                    interview_clips_output_dir.glob("*.mp4")) if interview_clips_output_dir.exists() else []
                all_profiles_complete = True
                for _, profile_info in selected_profiles:
                    paths = get_profile_paths(video_output_dir, profile_info['suffix'])
                    if not (paths["profile_dir"].exists() and paths["output_script"].exists()):
                        all_profiles_complete = False
                        break

                # 🚀 PARALLEL OPTIMIZATION: Run Step 1 + Step 4 together
                # Step 4 (B-roll) uses user-provided B-roll folder, doesn't need Step 1 output
                if ENABLE_PARALLEL_STEPS:
                    logger.info("\n" + "=" * 80)
                    logger.info("🚀 PARALLEL MODE: Running Step 1 (Interview) + Step 4 (B-roll) simultaneously!")
                    logger.info("=" * 80)

                    # Check if Step 1 needs to run
                    step1_needs_run = not (len(interview_clips) > 0 and all_profiles_complete)

                    # Check if Step 4 needs to run
                    step_4_dir_check = video_output_dir / STEP_4_DIR
                    step4_needs_run = not check_step_complete(4, step_4_dir_check, expected_patterns=["*.mp4"], min_files=5)

                    # Define Step 1 function
                    def execute_step1_parallel():
                        if not step1_needs_run:
                            logger.info("⚡ Step 1 already complete (parallel check)")
                            return True
                        logger.info(f"📁 [PARALLEL] Running Smart Interview Processing...")
                        return run_smart_interview_processing(interviews_folder, broll_folder, video_output_dir)

                    # Define Step 4 function
                    def execute_step4_parallel():
                        if not step4_needs_run:
                            broll_clips_count = len(list(step_4_dir_check.glob("*.mp4")))
                            logger.info(f"⚡ Step 4 already complete - {broll_clips_count} B-roll clips (parallel check)")
                            return True
                        step_4_dir_p = video_output_dir / STEP_4_DIR
                        step_4_dir_p.mkdir(parents=True, exist_ok=True)
                        logger.info(f"🎬 [PARALLEL] Rearranging B-roll clips from user folder...")
                        # Use user's broll_folder directly (not step_1_dir/broll_clips)
                        return run_broll_step(broll_folder, step_4_dir_p, None)

                    # Run both in parallel
                    parallel_tasks = [
                        {'name': 'Step 1 (Interview)', 'function': execute_step1_parallel, 'args': ()},
                        {'name': 'Step 4 (B-roll)', 'function': execute_step4_parallel, 'args': ()}
                    ]

                    parallel_success = run_steps_in_parallel(parallel_tasks)

                    if parallel_success:
                        logger.info("✅ Steps 1+4 completed successfully in parallel!")
                        parallel_steps_completed.add(4)
                        step_success = True
                    else:
                        logger.error("❌ Parallel Steps 1+4 failed!")
                        overall_success = False
                        break
                else:
                    # Sequential mode (parallel disabled)
                    if len(interview_clips) > 0 and all_profiles_complete:
                        logger.info(
                            f"⚡ SMART SKIP: Found Profile-First Structure with {len(interview_clips)} interview clips")
                        logger.info(f"   → Profiles: {[p[1]['name'] for p in selected_profiles]}")
                        logger.info("   → Skipping smart processing (delete profile folders to regenerate)")
                        step_success = True
                    else:
                        logger.info(f"📁 Running Smart Interview Processing...")
                        step_success = run_smart_interview_processing(interviews_folder, broll_folder,
                                                                      video_output_dir)

                # 🚀 PARALLEL OPTIMIZATION: After Step 1, run Steps 2+3 together
                if step_success and ENABLE_PARALLEL_STEPS:
                    logger.info("\n" + "=" * 80)
                    logger.info("🚀 PARALLEL MODE: Running Steps 2 (Styling) + 3 (Voiceover) simultaneously!")
                    logger.info("=" * 80)

                    # Define Step 2 function
                    def execute_step2_parallel():
                        step_2_dir_p = video_output_dir / STEP_2_DIR
                        step_1_dir_p = video_output_dir / STEP_1_DIR
                        interview_clips_dir_p = step_1_dir_p / SUBDIR_INTERVIEW_CLIPS

                        # Check if already complete
                        all_complete = True
                        for _, prof_info in selected_profiles:
                            if not check_step_complete(2, step_2_dir_p / prof_info['suffix']):
                                all_complete = False
                                break
                        if all_complete:
                            logger.info("⚡ Step 2 already complete (parallel check)")
                            return True

                        logger.info(f"🎨 [PARALLEL] Styling clips for {num_videos} profiles...")
                        all_success = True
                        for _, prof_info in selected_profiles:
                            profile_styled_dir = step_2_dir_p / prof_info['suffix']
                            profile_styled_dir.mkdir(parents=True, exist_ok=True)
                            if not run_styling_step_single(video_stem, interview_clips_dir_p, profile_styled_dir, prof_info):
                                all_success = False
                        return all_success

                    # Define Step 3 function
                    def execute_step3_parallel():
                        step_3_dir_p = video_output_dir / STEP_3_DIR

                        # Check if already complete
                        if check_step_complete(3, step_3_dir_p, min_files=num_videos):
                            logger.info("⚡ Step 3 already complete (parallel check)")
                            return True

                        logger.info(f"🎤 [PARALLEL] Generating voiceovers for {num_videos} profiles...")
                        if USE_MULTI_WINDOW_VOICEOVER and ENABLE_PROFILE_PARALLEL_PROCESSING:
                            return run_voiceover_step_multi_window_new(video_stem, video_output_dir, step_3_dir_p,
                                                                       selected_profiles, temp_script_dir)
                        else:
                            all_success = True
                            for _, prof_info in selected_profiles:
                                if not run_voiceover_step_single_new(video_stem, video_output_dir, step_3_dir_p,
                                                                     prof_info["default_voice"], temp_script_dir, prof_info):
                                    all_success = False
                            return all_success

                    # Run both in parallel
                    parallel_tasks = [
                        {'name': 'Step 2 (Styling)', 'function': execute_step2_parallel, 'args': ()},
                        {'name': 'Step 3 (Voiceover)', 'function': execute_step3_parallel, 'args': ()}
                    ]

                    parallel_success = run_steps_in_parallel(parallel_tasks)

                    if parallel_success:
                        logger.info("✅ Steps 2+3 completed successfully in parallel!")
                        parallel_steps_completed.add(2)
                        parallel_steps_completed.add(3)
                        # Update status
                        current_status[STATUS_KEY_LAST_COMPLETED_STEP] = 3
                        save_video_status(status_filepath, current_status)
                    else:
                        logger.error("❌ Parallel Steps 2+3 failed!")
                        overall_success = False
                        break

            elif step_num == 2:
                # Auto-skip check for Step 2 (Styling) - check all profile-specific folders
                step_2_dir = video_output_dir / STEP_2_DIR
                all_profiles_complete = True
                for profile_key, profile_info in selected_profiles:
                    profile_styled_dir = step_2_dir / profile_info['suffix']
                    if not check_step_complete(2, profile_styled_dir):
                        all_profiles_complete = False
                        break

                if all_profiles_complete:
                    total_styled_clips = sum(len(list((step_2_dir / profile_info['suffix']).glob("*.mp4")))
                                             for _, profile_info in selected_profiles
                                             if (step_2_dir / profile_info['suffix']).exists())
                    logger.info(
                        f"⚡ AUTO-SKIP STEP 2: Found {total_styled_clips} styled clips across {num_videos} profiles")
                    logger.info("   → Skipping styling step (delete step_2_dir to regenerate)")
                    step_success = True
                else:
                    # NEW MULTI-MODE: Style interview clips for each profile with different backgrounds
                    step_1_dir = video_output_dir / STEP_1_DIR
                    interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS
                    logger.info(f"🎨 Styling clips for {num_videos} selected profiles...")
                    all_styling_success = True
                    for profile_key, profile_info in selected_profiles:
                        logger.info(f"   Styling {profile_info['name']} clips...")
                        # Create profile-specific styled clips directory
                        profile_styled_dir = step_2_dir / profile_info['suffix']
                        profile_styled_dir.mkdir(parents=True, exist_ok=True)
                        styling_success = run_styling_step_single(video_stem, interview_clips_dir, profile_styled_dir,
                                                                  profile_info)
                        if not styling_success:
                            all_styling_success = False
                            logger.error(f"   ❌ Failed to style {profile_info['name']} clips")
                        else:
                            logger.info(f"   ✅ Styled {profile_info['name']} clips")
                    step_success = all_styling_success
            elif step_num == 3:
                # Auto-skip check for Step 3 (Voiceovers)
                if check_step_complete(3, step_3_dir, min_files=num_videos):
                    voiceover_folders = [d for d in step_3_dir.iterdir() if d.is_dir()]
                    logger.info(f"⚡ AUTO-SKIP STEP 3: Found {len(voiceover_folders)} voiceover folders")
                    logger.info("   → Skipping voiceover step (delete step_3_dir to regenerate)")
                    step_success = True
                else:
                    # NEW MULTI-MODE: Generate voiceovers for selected profiles using AI-created script
                    logger.info(
                        f"🎤 Generating voiceovers for {num_videos} selected profiles using smart-generated script...")
                    if USE_MULTI_WINDOW_VOICEOVER and ENABLE_PROFILE_PARALLEL_PROCESSING:
                        logger.info(
                            f"🚀 Multi-window mode: {len(selected_profiles)} browser windows will open simultaneously")
                        step_success = run_voiceover_step_multi_window_new(video_stem, video_output_dir, step_3_dir,
                                                                           selected_profiles, temp_script_dir)
                    else:
                        logger.info("🧠 Sequential mode: Processing profiles one by one")
                        all_voiceovers_success = True
                        for profile_key, profile_info in selected_profiles:
                            logger.info(f"   Generating {profile_info['name']} voiceover...")
                            voiceover_success = run_voiceover_step_single_new(video_stem, video_output_dir, step_3_dir,
                                                                              profile_info["default_voice"],
                                                                              temp_script_dir, profile_info)
                            if not voiceover_success:
                                all_voiceovers_success = False
                                logger.error(f"   ❌ Failed to generate {profile_info['name']} voiceover")
                            else:
                                logger.info(f"   ✅ Generated {profile_info['name']} voiceover")
                        step_success = all_voiceovers_success
            elif step_num == 4:
                # Auto-skip check for Step 4 (B-roll clips)
                step_4_dir = video_output_dir / STEP_4_DIR
                step_4_dir.mkdir(parents=True, exist_ok=True)  # Create Step 4 directory

                if check_step_complete(4, step_4_dir, expected_patterns=["*.mp4"], min_files=5):
                    broll_clips = list(step_4_dir.glob("*.mp4"))
                    logger.info(f"⚡ AUTO-SKIP STEP 4: Found {len(broll_clips)} B-roll clips")
                    logger.info("   → Skipping B-roll rearrangement (delete step_4_dir to regenerate)")
                    step_success = True
                else:
                    # NEW: Rearrange B-roll clips (Create 6-second clips using batch file)
                    step_1_dir = video_output_dir / STEP_1_DIR
                    broll_clips_dir = step_1_dir / SUBDIR_BROLL_CLIPS

                    logger.info(f"🎬 Rearranging B-roll clips - Creating 6-second clips for final assembly...")
                    step_success = run_broll_step(broll_clips_dir, step_4_dir, video_output_dir / STEP_3_DIR)

                    if step_success:
                        logger.info("✅ B-roll clips rearranged - 6-second clips created successfully!")
                        logger.info(f"📂 6-second clips saved to: {step_4_dir}")
                    else:
                        logger.warning("⚠️ B-roll clips rearrangement failed, continuing with original clips")

            elif step_num == 5:
                # Auto-skip check for Step 5 (Assembly) - check profile subfolders
                step_5_dir = video_output_dir / STEP_5_DIR
                all_profiles_complete = True
                total_videos = 0
                for profile_key, profile_info in selected_profiles:
                    profile_video_dir = step_5_dir / profile_info['suffix']
                    if profile_video_dir.exists():
                        profile_videos = list(profile_video_dir.glob("*.mp4"))
                        total_videos += len(profile_videos)
                        if len(profile_videos) < 5:  # Need at least 5 videos per profile
                            all_profiles_complete = False
                            break
                    else:
                        all_profiles_complete = False
                        break

                if all_profiles_complete and total_videos >= num_videos * 5:
                    logger.info(
                        f"⚡ AUTO-SKIP STEP 5: Found {total_videos} assembled videos across {num_videos} profiles")
                    logger.info("   → Skipping assembly step (delete step_5_dir to regenerate)")
                    step_success = True
                else:
                    # NEW MULTI-MODE: Assemble final videos for selected profiles using voiceovers and 6-second clips from Step 4
                    logger.info(f"🎬 Assembling final videos for {num_videos} selected profiles...")
                    step_3_dir = video_output_dir / STEP_3_DIR
                    step_4_dir = video_output_dir / STEP_4_DIR  # Use 6-second clips from Step 4
                    all_assembly_success = True
                    for profile_key, profile_info in selected_profiles:  # Only selected profiles
                        logger.info(f"   Assembling {profile_info['name']} final video...")
                        assembly_success = run_assembly_step_multi(video_stem, step_3_dir, step_4_dir,
                                                                   step_5_dir, log_dir, profile_info)
                        if not assembly_success:
                            all_assembly_success = False
                            logger.error(f"   ❌ Failed to assemble {profile_info['name']} final video")
                        else:
                            logger.info(f"   ✅ Assembled {profile_info['name']} final video")
                    step_success = all_assembly_success
            elif step_num == 6:
                # Auto-skip check for Step 6 (Ranking) - check profile-specific folders
                step_6_dir = video_output_dir / STEP_6_DIR

                # Check if all selected profiles have their ranking folders
                all_profiles_have_folders = True
                missing_profiles = []
                for profile_key, profile_info in selected_profiles:
                    profile_ranking_dir = step_6_dir / profile_info['suffix']
                    if not profile_ranking_dir.exists() or not any(profile_ranking_dir.iterdir()):
                        all_profiles_have_folders = False
                        missing_profiles.append(profile_info['name'])

                if all_profiles_have_folders:
                    existing_folders = [profile_info['suffix'] for _, profile_info in selected_profiles]
                    logger.info(
                        f"⚡ AUTO-SKIP STEP 6: All {len(selected_profiles)} profile folders exist: {existing_folders}")
                    logger.info("   → Skipping ranking step (delete profile folders to regenerate)")
                    step_success = True
                else:
                    # NEW MULTI-MODE: Rank video sequence for each profile using styled clips
                    logger.info(f"🎯 Ranking video sequences for {num_videos} selected profiles...")
                    all_ranking_success = True
                    for profile_key, profile_info in selected_profiles:  # Only selected profiles
                        logger.info(f"   Ranking {profile_info['name']} sequence...")

                        # Create clean ranking folder for this profile using step-based structure
                        step_2_dir = video_output_dir / STEP_2_DIR  # Use styled clips from Step 2
                        step_5_dir = video_output_dir / STEP_5_DIR
                        profile_ranking_dir = step_6_dir / profile_info['suffix']
                        profile_ranking_dir.mkdir(parents=True, exist_ok=True)

                        # Use styled clips from Step 2 profile-specific folder
                        styled_clips_dir = step_2_dir / profile_info['suffix']

                        ranking_success = run_ranking_step_single_new(video_stem, styled_clips_dir, step_5_dir,
                                                                      profile_ranking_dir, profile_info)
                        if not ranking_success:
                            all_ranking_success = False
                            logger.error(f"   ❌ Failed to rank {profile_info['name']} sequence")
                        else:
                            logger.info(f"   ✅ Ranked {profile_info['name']} sequence")
                    step_success = all_ranking_success
            elif step_num == 7:
                # Auto-skip check for Step 7 (Combination)
                step_7_dir = video_output_dir / STEP_7_DIR
                if check_step_complete(7, step_7_dir, expected_patterns=["*.mp4"], min_files=num_videos):
                    combined_videos = list(step_7_dir.glob("*.mp4"))
                    logger.info(f"⚡ AUTO-SKIP STEP 7: Found {len(combined_videos)} combined videos")
                    logger.info("   → Skipping combination step (delete step_7_dir to regenerate)")
                    step_success = True
                else:
                    # NEW: Combine ranked videos for each profile
                    logger.info(f"🎬 Combining videos for {num_videos} selected profiles...")
                    step_6_dir = video_output_dir / STEP_6_DIR
                    all_combination_success = True
                    for profile_key, profile_info in selected_profiles:
                        logger.info(f"   Combining {profile_info['name']} videos...")
                        profile_combination_success = run_combination_step_single(video_stem, step_6_dir, step_7_dir,
                                                                                  profile_info['suffix'], profile_info)
                        if not profile_combination_success:
                            all_combination_success = False
                            logger.error(f"   ❌ Failed to combine {profile_info['name']} videos")
                        else:
                            logger.info(f"   ✅ Combined {profile_info['name']} videos")
                    step_success = all_combination_success
            elif step_num == 8:
                # NEW: Upload to YouTube + Generate Thumbnail (parallel)
                step_8_dir = video_output_dir / STEP_8_DIR

                # Check if any profiles have upload enabled
                profiles_with_upload = [(k, p) for k, p in selected_profiles if p.get("enable_upload", False)]

                # === THUMBNAIL GENERATION (runs for ALL profiles, parallel with upload) ===
                logger.info(f"🎨 Starting thumbnail generation for {len(selected_profiles)} profile(s)...")
                thumbnail_threads = []
                for profile_key, profile_info in selected_profiles:
                    profile_output_dir = video_output_dir / profile_info['suffix']

                    def generate_thumbnail_for_profile(p_info, p_dir, input_dir):
                        try:
                            logger.info(f"   🎨 Generating thumbnail for {p_info['name']}...")
                            run_thumbnail_generator_step(video_stem, p_dir, p_info, input_dir)
                            logger.info(f"   🎨 ✅ Thumbnail ready for {p_info['name']}")
                        except Exception as e:
                            logger.warning(f"   🎨 ⚠️ Thumbnail failed for {p_info['name']}: {e}")

                    t = threading.Thread(target=generate_thumbnail_for_profile, args=(profile_info, profile_output_dir, interviews_folder))
                    t.start()
                    thumbnail_threads.append(t)

                # === YOUTUBE UPLOAD ===
                if not profiles_with_upload:
                    logger.info(f"⏭️ No profiles have upload enabled, skipping upload")
                    step_success = True
                elif ENABLE_BACKGROUND_UPLOAD:
                    # 🚀 BACKGROUND UPLOAD: Start upload in background, continue to next video
                    logger.info(f"📺 Starting BACKGROUND upload for {len(profiles_with_upload)} profile(s)...")

                    def do_all_uploads():
                        all_success = True
                        for profile_key, profile_info in profiles_with_upload:
                            logger.info(f"   [BG] Uploading {profile_info['name']} video to YouTube...")
                            if not run_youtube_upload_step(video_stem, video_output_dir, step_8_dir, profile_info):
                                all_success = False
                                logger.error(f"   [BG] ❌ Failed: {profile_info['name']}")
                            else:
                                logger.info(f"   [BG] ✅ Done: {profile_info['name']}")
                        return all_success

                    start_background_upload(do_all_uploads, (), video_stem)
                    step_success = True  # Consider successful since upload is running in background
                else:
                    # Sequential upload (background disabled)
                    logger.info(f"📺 Uploading videos for {num_videos} selected profiles...")
                    all_upload_success = True
                    for profile_key, profile_info in selected_profiles:
                        if profile_info.get("enable_upload", False):
                            logger.info(f"   Uploading {profile_info['name']} video to YouTube...")
                            profile_upload_success = run_youtube_upload_step(video_stem, video_output_dir, step_8_dir,
                                                                             profile_info)
                            if not profile_upload_success:
                                all_upload_success = False
                                logger.error(f"   ❌ Failed to upload {profile_info['name']} video")
                            else:
                                logger.info(f"   ✅ Uploaded {profile_info['name']} video")
                        else:
                            logger.info(f"   ⏭️ Skipping {profile_info['name']} (upload disabled)")
                    step_success = all_upload_success

                # Wait for all thumbnail threads to complete
                for t in thumbnail_threads:
                    t.join(timeout=120)  # Max 2 minutes per thumbnail
                logger.info(f"🎨 All thumbnail generation complete!")

        except Exception as e:
            logger.error(f"❌ Step {step_num} failed with error: {e}")
            step_success = False

        if step_success:
            logger.info(f"✅ Step {step_num} completed: {step_info['name']}")
            current_status[STATUS_KEY_LAST_COMPLETED_STEP] = step_num
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
# --- AUTO-SKIP SYSTEM ---
# ==============================================================================

def check_step_complete(step_num: int, step_dir: Path, expected_patterns: list = None, min_files: int = 1) -> bool:
    """
    Check if a pipeline step is already complete to enable auto-skipping

    Args:
        step_num: Step number (1-8)
        step_dir: Step output directory to check
        expected_patterns: List of file patterns to look for (e.g., ['*.mp4', '*.txt'])
        min_files: Minimum number of files expected

    Returns:
        bool: True if step appears complete, False otherwise
    """
    if not step_dir.exists():
        return False

    # Default patterns by step if not specified
    if expected_patterns is None:
        default_patterns = {
            1: ['*.mp4'],  # Interview clips
            2: ['*.mp4'],  # Styled clips
            3: ['*.mp3', '*.wav'],  # Voiceovers
            4: ['*.mp4'],  # Rearranged broll
            5: ['*.mp4'],  # Final videos
            6: ['*.mp4'],  # Ranked output
            7: ['*.mp4'],  # Combined video
            8: ['*.png', '*.jpg', '*.txt']  # Thumbnails and titles
        }
        expected_patterns = default_patterns.get(step_num, ['*'])

    # Count matching files
    total_files = 0
    for pattern in expected_patterns:
        matching_files = list(step_dir.glob(pattern))
        # Also check subdirectories for some steps
        if step_num in [1, 5, 6]:
            for subdir in step_dir.iterdir():
                if subdir.is_dir():
                    matching_files.extend(list(subdir.glob(pattern)))
        total_files += len(matching_files)

    # Special checks for certain steps
    if step_num == 1:
        # Step 1: Check for interview clips AND voiceover script
        interview_clips_dir = step_dir / "interview_clips"
        if interview_clips_dir.exists():
            clips = list(interview_clips_dir.glob("*.mp4"))
            script_file = step_dir.parent / "voiceover_script.txt"
            return len(clips) >= min_files and script_file.exists()
        return False

    elif step_num == 7:
        # Step 7: Look for the final combined video
        combined_files = list(step_dir.glob("*.mp4"))
        if combined_files:
            # Check if file is not empty and recent
            for file in combined_files:
                if file.stat().st_size > 1024 * 1024:  # At least 1MB
                    return True
        return False

    # Default check: sufficient number of files exist
    return total_files >= min_files


# ==============================================================================
# --- MAIN FUNCTION (FIXED) ---
# ==============================================================================

def main():
    global PROMPT_PROFILES
    parser = argparse.ArgumentParser(description="Smart video processing orchestrator with numbered selection system.")
    parser.add_argument('--interviews-folder', type=Path, default=DEFAULT_INTERVIEWS_FOLDER,
                        help=f"Path to the folder containing interview videos to process.")
    parser.add_argument('--broll-folder', type=Path, default=DEFAULT_BROLL_FOLDER,
                        help=f"Path to the folder containing b-roll clips for video assembly.")
    parser.add_argument('--output-base-dir', type=Path, default=DEFAULT_PROJECT_OUTPUT_BASE_DIR,
                        help=f"Base directory where all processed video project folders will be created.")
    parser.add_argument('--gemini-api-key', type=str, default=None, help="Google Gemini API Key.")
    parser.add_argument('--show-settings', action='store_true',
                        help="Display all current pipeline settings and exit.")
    parser.add_argument('--auto', action='store_true',
                        help="Run automatically without prompts (for GUI mode).")
    parser.add_argument('--channels', type=str, default=None,
                        help="Comma-separated list of channel names to use (for GUI mode).")

    # Legacy support for old --input-folder parameter
    parser.add_argument('--input-folder', type=Path, default=None,
                        help=f"Legacy parameter - will be used as interviews-folder if --interviews-folder not provided.")

    # NEW: Multi-folder queue mode (for UI parallel processing)
    parser.add_argument('--use-folder-queue', action='store_true',
                        help="Read folders from multi_folder_queue.json for parallel processing (used by GUI).")

    args = parser.parse_args()

    # Handle --show-settings option
    if args.show_settings:
        print_pipeline_settings()
        print("\n" + "=" * 80)
        print("💡 To modify settings, edit the configuration constants at the top of content_creator.py")
        print("   Each step has its own settings section (STEP_X_SETTINGS)")
        print("💡 Use get_pipeline_settings() function to access settings from other scripts")
        print("=" * 80)
        return

    # === MULTI-FOLDER MODE LOGIC ===
    # Determine which folders to process based on USE_MULTI_FOLDER_MODE or --use-folder-queue
    folders_to_process = []

    # NEW: Check for folder queue file (from GUI parallel processing)
    if args.use_folder_queue:
        queue_file = get_user_data_dir() / 'multi_folder_queue.json'
        if queue_file.exists():
            try:
                with open(queue_file, 'r', encoding='utf-8') as f:
                    queue_data = json.load(f)
                if queue_data.get('use_multi_folder_mode', False):
                    queue_folders = [Path(p) for p in queue_data.get('folders', [])]
                    if queue_folders:
                        folders_to_process = queue_folders
                        logger.info(f"\n{'=' * 80}")
                        logger.info(f"🚀 PARALLEL FOLDER MODE (from GUI queue)")
                        logger.info(f"{'=' * 80}")
                        logger.info(f"📁 Will process {len(folders_to_process)} folder(s) in PARALLEL:")
                        for i, folder in enumerate(folders_to_process, 1):
                            logger.info(f"   {i}. {folder}")
                        logger.info(f"{'=' * 80}\n")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read folder queue: {e}")

    # Fallback to config-based multi-folder mode
    if not folders_to_process and USE_MULTI_FOLDER_MODE:
        # Use predefined list of folders from MULTI_INPUT_FOLDERS
        logger.info(f"\n{'=' * 80}")
        logger.info(f"🔁 MULTI-FOLDER MODE ENABLED")
        logger.info(f"{'=' * 80}")
        logger.info(f"📁 Will process {len(MULTI_INPUT_FOLDERS)} folder(s) sequentially:")
        for i, folder in enumerate(MULTI_INPUT_FOLDERS, 1):
            logger.info(f"   {i}. {folder}")
        logger.info(f"{'=' * 80}\n")
        folders_to_process = MULTI_INPUT_FOLDERS

    # Final fallback: single folder mode
    if not folders_to_process:
        # Single folder mode - use the command line argument or default
        folders_to_process = [args.interviews_folder]

    # === FILTER CHANNELS IF --channels IS PROVIDED ===
    if args.channels:
        selected_channel_names = [c.strip() for c in args.channels.split(',')]
        filtered_channels = {}
        for channel_key, channel_data in PROMPT_PROFILES.items():
            # Match by channel key or channel name
            if channel_key in selected_channel_names or channel_data.get('name', '') in selected_channel_names:
                filtered_channels[channel_key] = channel_data
        if filtered_channels:
            PROMPT_PROFILES.clear()
            PROMPT_PROFILES.update(filtered_channels)
            logger.info(f"🎯 Using {len(filtered_channels)} selected channel(s): {', '.join(filtered_channels.keys())}")
        else:
            logger.warning(f"⚠️ No matching channels found for: {args.channels}")

    # === CONFIGURATION SETUP (Done once before processing all folders) ===
    # Get processing configuration (skip prompts in auto mode)
    processing_config = determine_processing_mode(auto_mode=args.auto)

    # Interactive prompt for starting step (skip in auto mode)
    force_start_from_value = -1
    is_multi_mode = processing_config["mode"] == "numbered"
    pipeline_steps = get_pipeline_steps_info(multi_mode=is_multi_mode)
    max_step = max(pipeline_steps.keys())

    if not args.auto:
        while True:
            user_input = input(
                f"Start from specific step (0-{max_step})? Enter step number or press Enter for normal run: ").strip()
            if user_input == "":
                break
            try:
                step_num = int(user_input)
                if 0 <= step_num <= max_step:
                    force_start_from_value = step_num
                    break
                else:
                    print(f"Invalid step number. Please enter 0-{max_step}.")
            except ValueError:
                print("Invalid input. Please enter a number or press Enter.")

    # Handle profile restoration for single profile mode
    restore_profiles = processing_config.get("restore_profiles", None)

    # Load API keys
    json_api_keys = load_api_keys_from_json_file(API_KEYS_FILE)
    final_gemini_api_key = (
            args.gemini_api_key or json_api_keys.get("google_gemini_api_key") or os.environ.get("GOOGLE_API_KEY",
                                                                                                ""))

    # Validate profile configurations
    validate_prompt_profiles()

    # === LOOP THROUGH ALL FOLDERS ===
    # Initialize counters for all folders
    total_folders = len(folders_to_process)
    successful_folders = 0
    failed_folders = 0
    all_folders_total_videos = 0
    all_folders_successful_videos = 0
    all_folders_output_videos = 0

    # === HELPER FUNCTION FOR PROCESSING A SINGLE FOLDER ===
    def process_single_folder_task(folder_idx: int, current_interview_folder: Path,
                                   broll_folder: Path, output_base_dir: Path,
                                   processing_config: dict, force_start_from: int,
                                   browser_profile_id: str = None,
                                   browser_profile_path: str = None) -> dict:
        """
        Process a single folder - can be called in parallel.
        Returns dict with: success, total_videos, output_videos, folder_name
        """
        # Create folder-specific logger for clear parallel logs
        folder_name = current_interview_folder.name
        flog = FolderLogger(logger, folder_name)

        result = {
            'success': False,
            'total_videos': 0,
            'output_videos': 0,
            'folder_name': folder_name,
            'folder_idx': folder_idx
        }

        try:
            flog.info(f"{'#' * 60}")
            flog.info(f"📁 PROCESSING FOLDER {folder_idx}/{total_folders}")
            if ENABLE_PARALLEL_FOLDERS and browser_profile_path:
                flog.info(f"🌐 Browser Profile: {browser_profile_id} -> {browser_profile_path}")
            flog.info(f"{'#' * 60}")

            # Create broll folder if it doesn't exist
            if not broll_folder.exists():
                flog.info(f"📁 Creating broll folder: {broll_folder}")
                broll_folder.mkdir(parents=True, exist_ok=True)

            # Validate folders exist
            if not current_interview_folder.exists():
                flog.error(f"❌ Interviews folder does not exist: {current_interview_folder}")
                flog.warning(f"⚠️ Skipping folder {folder_idx}/{total_folders}")
                return result

            # Find video files
            video_files = [f for f in current_interview_folder.iterdir() if
                           f.is_file() and f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']]

            if not video_files:
                flog.warning(f"❌ No video files found in: {current_interview_folder}")
                flog.warning(f"⚠️ Skipping folder {folder_idx}/{total_folders}")
                return result

            video_files.sort()
            total_videos = len(video_files)
            result['total_videos'] = total_videos

            flog.info(f"📹 Found {total_videos} video file(s)")
            for i, video_file in enumerate(video_files):
                flog.info(f"   {i + 1}. {video_file.name}")

            # Display configuration for this folder
            num_videos = processing_config["count"]
            flog.info(f"🎬 Will create {num_videos} video{'s' if num_videos > 1 else ''}")
            selected_profiles = list(PROMPT_PROFILES.items())[:num_videos]
            for profile_key, profile_info in selected_profiles:
                flog.info(f"   • {profile_info['name']} → {profile_info['default_voice']} voice")

            # Process ALL videos together as one batch
            flog.info(f"{'=' * 60}")
            flog.info(f"🚀 STARTING BATCH PROCESSING")
            flog.info(f"{'=' * 60}")

            # Always use the input folder name directly
            project_name = current_interview_folder.name

            # Only fall back to timestamp if folder name is empty or just whitespace
            if not project_name or not project_name.strip():
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                project_name = f"video_project_{timestamp}"
                flog.info(f"   → Empty folder name, using timestamp: {project_name}")

            # Process all videos together in ONE pipeline run
            # Pass folder_name for prefixed logging in parallel mode
            # Pass browser_profile_path for unique browser profiles in parallel voiceover processing
            success = process_video_pipeline_batch(project_name, output_base_dir, final_gemini_api_key,
                                                   processing_config["count"], force_start_from,
                                                   current_interview_folder, broll_folder,
                                                   folder_name=folder_name,
                                                   browser_profile_path=browser_profile_path)

            # Update result
            if success:
                result['success'] = True
                result['output_videos'] = processing_config["count"]
                flog.info(f"✅ COMPLETED - Output videos: {result['output_videos']}")
            else:
                flog.error(f"❌ FAILED")

        except Exception as e:
            flog.error(f"❌ ERROR: {e}")
            result['success'] = False

        return result

    # === PROCESS FOLDERS (PARALLEL OR SEQUENTIAL) ===
    if ENABLE_PARALLEL_FOLDERS and total_folders > 1:
        # === PARALLEL FOLDER PROCESSING ===
        logger.info(f"\n{'=' * 80}")
        logger.info(f"🚀 PARALLEL FOLDER PROCESSING ENABLED")
        logger.info(f"📁 Total folders: {total_folders}")
        logger.info(f"⚡ Max concurrent: {MAX_PARALLEL_FOLDERS}")
        logger.info(f"{'=' * 80}\n")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        # SIMPLE APPROACH: All folders share ONE browser profile for voiceover
        # Steps 0-2 run in parallel, Step 3 (voiceover) uses shared profile with login
        # The voiceover script will wait if profile is busy (auto-retry)
        logger.info(f"🌐 All folders will share ONE browser profile for voiceover")
        logger.info(f"💡 Login to Fish Audio ONCE, all voiceovers use that login!")
        logger.info(f"📋 Steps 0-2 run in parallel, voiceover waits for browser")

        # Process folders in parallel - NO custom browser profiles
        # Each folder will use the shared browser_profile (with Fish Audio login)
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FOLDERS) as executor:
            future_to_folder = {}
            for folder_idx, current_interview_folder in enumerate(folders_to_process, 1):
                future = executor.submit(
                    process_single_folder_task,
                    folder_idx,
                    current_interview_folder,
                    args.broll_folder,
                    args.output_base_dir,
                    processing_config,
                    force_start_from_value,
                    None,  # No custom browser profile ID
                    None   # No custom browser profile path - use shared profile
                )
                future_to_folder[future] = (folder_idx, current_interview_folder.name, None)

            # Collect results as they complete
            for future in as_completed(future_to_folder):
                folder_idx, folder_name, browser_profile_id = future_to_folder[future]
                try:
                    result = future.result()
                    all_folders_total_videos += result['total_videos']
                    if result['success']:
                        successful_folders += 1
                        all_folders_successful_videos += 1
                        all_folders_output_videos += result['output_videos']
                    else:
                        failed_folders += 1

                    # No cleanup needed - we use shared profile that persists

                except Exception as e:
                    logger.error(f"❌ Folder {folder_name} raised exception: {e}")
                    failed_folders += 1

    else:
        # === SEQUENTIAL FOLDER PROCESSING (Original behavior) ===
        if total_folders > 1:
            logger.info(f"\n📋 Sequential folder processing (set enable_parallel_folders=true for parallel)")

        for folder_idx, current_interview_folder in enumerate(folders_to_process, 1):
            result = process_single_folder_task(
                folder_idx,
                current_interview_folder,
                args.broll_folder,
                args.output_base_dir,
                processing_config,
                force_start_from_value
            )

            all_folders_total_videos += result['total_videos']
            if result['success']:
                successful_folders += 1
                all_folders_successful_videos += 1
                all_folders_output_videos += result['output_videos']
            else:
                failed_folders += 1

    # === END OF FOLDER LOOP ===

    # Wait for any background uploads to complete before final summary
    if ENABLE_BACKGROUND_UPLOAD:
        wait_for_all_background_uploads()

    # Restore original profiles if this was single profile mode
    if restore_profiles:
        PROMPT_PROFILES.clear()
        PROMPT_PROFILES.update(restore_profiles)

    # === FINAL MULTI-FOLDER SUMMARY ===
    logger.info(f"\n{'#' * 80}")
    logger.info(f"🚀 {'MULTI-FOLDER' if USE_MULTI_FOLDER_MODE else 'SINGLE-FOLDER'} ORCHESTRATION COMPLETE")
    logger.info(f"{'#' * 80}")

    if USE_MULTI_FOLDER_MODE:
        logger.info(f"📁 Total Folders Processed: {total_folders}")
        logger.info(f"✅ Successful Folders: {successful_folders}")
        logger.info(f"❌ Failed Folders: {failed_folders}")
        logger.info(f"📊 Total Input Videos (all folders): {all_folders_total_videos}")
        logger.info(f"🎬 Total Output Videos Created: {all_folders_output_videos}")
    else:
        total_output_videos = all_folders_output_videos
        logger.info(f"📊 Total Input Videos: {all_folders_total_videos}")
        logger.info(f"✅ Successfully Processed: {successful_folders}")
        logger.info(f"❌ Failed to Process: {failed_folders}")
        logger.info(f"🎬 Total Output Videos Created: {total_output_videos}")

    logger.info(f"📝 Processing: {processing_config['count']} video{'s' if processing_config['count'] > 1 else ''} per input")
    logger.info(f"💡 System is expandable: Add new prompts to PROMPT_PROFILES and they automatically appear as options!")
    logger.info(f"📄 Full log: {ORCHESTRATOR_LOG_FILE_NAME}")
    logger.info(f"{'#' * 80}")


if __name__ == "__main__":
    main()


def transform_script_for_fastiq_style(base_script: str) -> str:
    """Transform base script for FASTIQ fast-paced style - complete rewrite for social media"""
    paragraphs = base_script.split('\n\n')
    transformed_paragraphs = []

    for para in paragraphs:
        if para.strip() and not para.startswith('[INTERVIEW_CLIP'):
            # Split into sentences for transformation
            sentences = para.replace('. ', '.|').split('|')
            new_sentences = []

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # FASTIQ style: Short, punchy, dramatic
                # Remove filler words and make it more direct
                sentence = sentence.replace("But here's where this gets absolutely wild", "BOOM! Plot twist")
                sentence = sentence.replace("Think about it:", "Check this -")
                sentence = sentence.replace("And here's the thing:", "Listen -")
                sentence = sentence.replace("Let me break down", "Quick breakdown:")
                sentence = sentence.replace("You need to understand", "Facts:")
                sentence = sentence.replace("This is exactly why", "THIS is why")
                sentence = sentence.replace("And check out this reality check", "Reality check!")
                sentence = sentence.replace("What's really happening here is", "The truth?")
                sentence = sentence.replace("The situation is", "Here's what's up:")

                # Make language more energetic and social media friendly
                sentence = sentence.replace("interesting", "WILD")
                sentence = sentence.replace("fascinating", "MIND-BLOWING")
                sentence = sentence.replace("reveals", "EXPOSES")
                sentence = sentence.replace("important", "HUGE")
                sentence = sentence.replace("significant", "MASSIVE")
                sentence = sentence.replace("concerning", "sketchy")
                sentence = sentence.replace("disappointed", "NOT happy")
                sentence = sentence.replace("excited", "HYPED")

                # Shorten long explanations
                if len(sentence) > 150:
                    # Break long sentences into shorter ones
                    if ' because ' in sentence:
                        parts = sentence.split(' because ', 1)
                        sentence = parts[0] + '.' + '\nWhy? Because ' + parts[1]
                    elif ' which means ' in sentence:
                        parts = sentence.split(' which means ', 1)
                        sentence = parts[0] + '.' + '\nTranslation? ' + parts[1]
                    elif ', and ' in sentence:
                        parts = sentence.split(', and ', 1)
                        sentence = parts[0] + '.' + '\nAND ' + parts[1]

                # Add emphasis and energy
                if sentence.endswith('.'):
                    # Occasionally replace periods with exclamations for emphasis
                    if any(word in sentence.lower() for word in ['wild', 'crazy', 'huge', 'massive', 'boom']):
                        sentence = sentence[:-1] + '!'

                new_sentences.append(sentence)

            # Join sentences with better flow for fast-paced delivery
            transformed_para = ' '.join(new_sentences)
            # Break into shorter chunks for faster pacing
            transformed_para = transformed_para.replace('. ', '.\n\n')
            transformed_paragraphs.append(transformed_para)
        else:
            # Keep interview clips as-is
            transformed_paragraphs.append(para)

    return '\n\n'.join(transformed_paragraphs)


def transform_script_for_baskly_style(base_script: str) -> str:
    """Transform base script for BASKLY analytical deep-dive style"""
    paragraphs = base_script.split('\n\n')
    transformed_paragraphs = []

    for para in paragraphs:
        if para.strip() and not para.startswith('[INTERVIEW_CLIP'):
            # BASKLY style: Analytical, detailed, thoughtful
            # Add more context and analysis

            # Enhance analytical language
            para = para.replace("This is", "What we're seeing here is")
            para = para.replace("Look at", "Let's analyze")
            para = para.replace("Check this out", "Consider this carefully")
            para = para.replace("Here's what happened", "Let me walk you through exactly what transpired")
            para = para.replace("The thing is", "The critical factor to understand is")

            # Add analytical depth
            para = para.replace(" is happening", " is happening, and the implications are significant")
            para = para.replace(" shows", " clearly demonstrates")
            para = para.replace(" means", " indicates")
            para = para.replace(" says", " stated, and it's worth examining why")
            para = para.replace(" wants", " is strategically positioning for")

            # Make it more formal and professional
            para = para.replace("crazy", "remarkable")
            para = para.replace("wild", "extraordinary")
            para = para.replace("huge", "substantial")
            para = para.replace("big deal", "significant development")
            para = para.replace("messed up", "problematic")
            para = para.replace("got to", "need to")
            para = para.replace("gonna", "going to")

            # Add connecting phrases for better flow
            if not para.startswith(('Now', 'First', 'Next', 'Finally', 'However', 'Moreover')):
                # Add analytical transition if appropriate
                if 'because' in para.lower()[:50]:
                    para = "To understand this situation, " + para[0].lower() + para[1:]
                elif 'but' in para.lower()[:30]:
                    para = "However, " + para[0].lower() + para[1:]
                elif any(word in para.lower()[:50] for word in ['shows', 'demonstrates', 'reveals']):
                    para = "What's particularly noteworthy is that " + para[0].lower() + para[1:]

            transformed_paragraphs.append(para)
        else:
            # Keep interview clips as-is
            transformed_paragraphs.append(para)

    return '\n\n'.join(transformed_paragraphs)


def transform_script_for_elite_style(base_script: str) -> str:
    """Transform base script for WNBA-ELITE expert analysis style"""
    return base_script


def transform_script_for_wahib_style(base_script: str) -> str:
    """Transform base script for WAHIB-PROMPT custom style"""
    return base_script


