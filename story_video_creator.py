"""
Story Video Creator Pipeline
============================
Creates story-style videos from voiceover-only clips (no interviews).
Skips diarization (Step 1) and interview styling (Step 2).

Usage:
  python story_video_creator.py --input-folder "D:/videos" --output-folder "D:/output" --profiles Profile1 Profile2

This is a simplified pipeline for:
- Long-form story videos with voiceover narration
- Videos without interview segments
- Pre-edited voiceover clips ready for B-roll overlay
"""

import os
import subprocess
import shutil
import argparse
import logging
import time
from pathlib import Path
import json
import sys
import io
import threading

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==============================================================================
# --- FROZEN/EXE DETECTION ---
# ==============================================================================
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
    EMBEDDED_PYTHON = SCRIPT_DIR / "python" / "python.exe"
    if EMBEDDED_PYTHON.exists():
        PYTHON_EXE = str(EMBEDDED_PYTHON)
    else:
        PYTHON_EXE = sys.executable
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()
    PYTHON_EXE = sys.executable

# ==============================================================================
# --- CONFIGURATION LOADING ---
# ==============================================================================

def get_user_data_dir() -> Path:
    """Get the user data directory (AppData on Windows)"""
    if os.name == 'nt':
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        user_dir = Path(appdata) / "NabilVideoStudioPro"
    else:
        user_dir = Path.home() / ".nvspro"
    return user_dir

def load_configuration():
    """Load configuration from config.json file"""
    user_data_dir = get_user_data_dir()
    config_file = user_data_dir / "config.json"

    if not config_file.exists():
        config_file = SCRIPT_DIR / "config.json"

    if not config_file.exists():
        print(f"❌ ERROR: Configuration file not found!")
        print(f"Expected location: {config_file}")
        sys.exit(1)

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ Configuration loaded from: {config_file}")
        return config
    except Exception as e:
        print(f"❌ ERROR: Could not load configuration: {e}")
        sys.exit(1)

def resolve_path(path_str: str, base_dir: Path = SCRIPT_DIR) -> Path:
    """Resolve a path string to absolute Path"""
    if not path_str:
        return base_dir
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()

# Load configuration
CONFIG = load_configuration()

# --- SCRIPT PATHS ---
VIDEO_TO_SCRIPT_SCRIPT = SCRIPT_DIR / "3_transcribe_clips.py"
SCRIPT_WRITER_AI_SCRIPT = SCRIPT_DIR / "4_ai_rewrite_script.py"
SMART_BROLL_SCRIPT = SCRIPT_DIR / "4_smart_broll_processor.py"

def get_voiceover_script():
    """Choose voiceover script based on user's setting"""
    config_path = get_user_data_dir() / "config.json"
    use_api = False
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

SCRIPT_VOICE_SCRIPT = get_voiceover_script()
CLIPS_PLUS_VOICEOVER_SCRIPT = SCRIPT_DIR / "7_assemble_final_video.py"
RANK_VIDEO_SEQUENCE_SCRIPT = SCRIPT_DIR / "8_rank_video_sequence.py"
COMBINE_RANKED_SCRIPT = SCRIPT_DIR / "9_combine_ranked_videos.py"
YOUTUBE_UPLOAD_SCRIPT = SCRIPT_DIR / "10_youtube_upload.py"

# --- PATHS FROM CONFIG ---
DEFAULT_BACKGROUND_MUSIC_FOLDER = resolve_path(CONFIG.get("paths", {}).get("background_music_folder", "./music"))

# --- PROCESSING SETTINGS ---
ENABLE_PARALLEL_STEPS = CONFIG.get("processing_settings", {}).get("enable_parallel_steps", True)
ENABLE_BACKGROUND_MUSIC = CONFIG.get("background_music", {}).get("enabled", True)
DEFAULT_VOICE_LEVEL = CONFIG.get("background_music", {}).get("default_voice_level", 1.2)
DEFAULT_MUSIC_LEVEL = CONFIG.get("background_music", {}).get("default_music_level", 0.1)
ENABLE_LOGO_IN_STEP7 = CONFIG.get("processing_settings", {}).get("enable_logo_in_step7", True)

# --- VOICEOVER SETTINGS ---
USE_MULTI_WINDOW_VOICEOVER = CONFIG.get("voiceover_settings", {}).get("use_multi_window", False)
ENABLE_PROFILE_PARALLEL_PROCESSING = CONFIG.get("voiceover_settings", {}).get("enable_parallel_processing", False)

# --- AI SETTINGS ---
def get_ai_provider():
    return CONFIG.get("ai_settings", {}).get("provider", "gemini")

def get_ai_model_name(provider=None):
    if provider is None:
        provider = get_ai_provider()
    appdata_api_keys = get_user_data_dir() / "api_keys.json"
    if appdata_api_keys.exists():
        try:
            with open(appdata_api_keys, 'r', encoding='utf-8') as f:
                data = json.load(f)
                model = data.get(provider, {}).get("model", "")
                if model:
                    return model
        except:
            pass
    default_models = {
        "gemini": "gemini-2.5-pro",
        "claude": "claude-sonnet-4-20250514",
        "openai": "gpt-4o"
    }
    return default_models.get(provider, "gemini-2.5-pro")

AI_PROVIDER = get_ai_provider()
AI_REWRITE_MODEL_NAME = get_ai_model_name(AI_PROVIDER)

# --- SUBDIRECTORY NAMES (simplified for story videos) ---
SUBDIR_INPUT_CLIPS = "0_input_clips"
SUBDIR_TRANSCRIPTS = "1_transcripts"
SUBDIR_AI_SCRIPTS = "2_ai_scripts"
SUBDIR_VOICEOVERS = "3_voiceovers"
SUBDIR_BROLL_CLIPS = "4_broll_clips"
SUBDIR_FINAL_VIDEOS = "5_final_videos"
SUBDIR_COMBINED_VIDEOS = "6_combined_videos"
SUBDIR_YOUTUBE_UPLOADS = "7_youtube_uploads"
SUBDIR_LOGS = "logs"

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("story_video_run.log", mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# --- PROFILE LOADING ---
# ==============================================================================

def load_profiles_from_config():
    """Load and process profiles from config"""
    profiles = {}
    prompts_folder = resolve_path(CONFIG.get("paths", {}).get("prompts_folder", "./prompts"))
    backgrounds_folder = resolve_path(CONFIG.get("paths", {}).get("backgrounds_folder", "./backgrounds"))
    music_folder = resolve_path(CONFIG.get("paths", {}).get("background_music_folder", "./music"))

    for profile_key, profile_data in CONFIG.get("profiles", {}).items():
        profile = profile_data.copy()

        # Resolve prompt file path
        prompt_file_str = profile["prompt_file"]
        if Path(prompt_file_str).is_absolute():
            profile["prompt_file"] = Path(prompt_file_str)
        else:
            prompt_path = prompts_folder / prompt_file_str
            if not prompt_path.exists():
                prompt_path = SCRIPT_DIR / prompt_file_str
            profile["prompt_file"] = prompt_path

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
AVAILABLE_VOICES = CONFIG.get("voices", {})

# ==============================================================================
# --- HELPER FUNCTIONS ---
# ==============================================================================

def run_python_script(script_path, args=None, cwd=None, capture_output=True):
    """Run a Python script with arguments"""
    return run_python_script_with_env(script_path, args, cwd, capture_output, env=None)

def run_python_script_with_env(script_path, args=None, cwd=None, capture_output=True, env=None):
    """Run a Python script with arguments and custom environment"""
    if args is None:
        args = []

    cmd = [PYTHON_EXE, str(script_path)] + [str(arg) for arg in args]
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        if capture_output:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=cwd,
                bufsize=1,
                env=env
            )
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"   {line}")
            return_code = process.wait()
        else:
            result = subprocess.run(cmd, cwd=cwd, env=env)
            return_code = result.returncode

        return return_code == 0
    except Exception as e:
        logger.error(f"Error running script: {e}")
        return False

def get_voice_url_by_name(voice_name: str) -> str:
    """Get voice URL by voice name"""
    for voice_key, voice_info in AVAILABLE_VOICES.items():
        if voice_info["name"] == voice_name:
            return voice_info["url"]
    # Fallback
    if AVAILABLE_VOICES:
        return list(AVAILABLE_VOICES.values())[0]["url"]
    return ""

def get_background_music_for_profile(profile_info):
    """Get background music path and audio levels for a profile"""
    if not ENABLE_BACKGROUND_MUSIC:
        return None, DEFAULT_VOICE_LEVEL, DEFAULT_MUSIC_LEVEL

    background_music = profile_info.get("background_music")
    voice_level = profile_info.get("voice_level", DEFAULT_VOICE_LEVEL)
    music_level = profile_info.get("music_level", DEFAULT_MUSIC_LEVEL)

    if background_music and Path(background_music).exists():
        return background_music, voice_level, music_level

    # Try to find default music
    profile_suffix = profile_info.get("suffix", "DEFAULT")
    patterns = [
        f"{profile_suffix}-BG-MUSIC-1.mp3",
        f"{profile_suffix}-BG-MUSIC.mp3",
        f"{profile_suffix}.mp3",
        "music-background-1.MP3",
        "default-bg-music.mp3"
    ]

    for pattern in patterns:
        music_path = DEFAULT_BACKGROUND_MUSIC_FOLDER / pattern
        if music_path.exists():
            return str(music_path), voice_level, music_level

    return None, voice_level, music_level

def use_specific_profiles(profile_names: list):
    """Select specific profiles by name"""
    global PROMPT_PROFILES

    found_profiles = {}
    for profile_name in profile_names:
        for profile_key, profile_info in PROMPT_PROFILES.items():
            if profile_info['name'] == profile_name or profile_key == profile_name:
                found_profiles[profile_key] = profile_info
                break

    if not found_profiles:
        logger.error("No valid profiles found!")
        sys.exit(1)

    original_profiles = PROMPT_PROFILES.copy()
    PROMPT_PROFILES.clear()
    PROMPT_PROFILES.update(found_profiles)

    return original_profiles

# ==============================================================================
# --- PIPELINE STEPS ---
# ==============================================================================

def get_pipeline_steps_info():
    """Returns pipeline steps for Story Video (simplified - no ranking needed)"""
    return {
        0: {"name": "Copy Input Clips"},
        1: {"name": "Transcribe Clips"},
        2: {"name": "AI Rewrite Scripts"},
        3: {"name": "Generate Voiceovers"},
        4: {"name": "Create B-roll Clips"},
        5: {"name": "Assemble Final Videos"},
        6: {"name": "Combine Final Videos"},
        7: {"name": "Upload to YouTube"},
    }

def run_transcription_step(folder_name, input_clips_dir, transcripts_dir, temp_script_dir):
    """Run transcription step"""
    transcript_file = transcripts_dir / f"{folder_name}_raw_transcript.txt"

    args = [
        str(input_clips_dir),
        "--output-folder", str(transcripts_dir),
        "--save-combined", "--combined-name", f"{folder_name}_raw_transcript.txt"
    ]

    success = run_python_script(VIDEO_TO_SCRIPT_SCRIPT, args)

    # Verify transcript was created
    if success and not transcript_file.exists():
        logger.error(f"Transcription script returned success but transcript not found: {transcript_file}")
        return False

    if transcript_file.exists():
        logger.info(f"   Transcript created: {transcript_file.name} ({transcript_file.stat().st_size} bytes)")
        return True

    return False

def run_ai_script_step(folder_name, transcripts_dir, ai_scripts_dir, profile_info, api_key):
    """Run AI script rewriting step - uses channel's own prompt"""
    profile_suffix = profile_info.get('suffix', 'DEFAULT')
    input_transcript = transcripts_dir / f"{folder_name}_raw_transcript.txt"
    output_script = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_suffix}.txt"

    if not input_transcript.exists():
        logger.error(f"Transcript not found: {input_transcript}")
        return False

    # Use the channel's own prompt file
    prompt_file = str(profile_info["prompt_file"])
    logger.info(f"   Using prompt: {Path(prompt_file).name}")

    args = [
        "--input-file", str(input_transcript),
        "--output-file", str(output_script),
        "--prompt-file", prompt_file,
        "--provider", AI_PROVIDER,
        "--model-name", AI_REWRITE_MODEL_NAME
    ]

    return run_python_script(SCRIPT_WRITER_AI_SCRIPT, args)

def run_voiceover_step(folder_name, ai_scripts_dir, voiceovers_dir, profile_info, temp_script_dir):
    """Run voiceover generation step"""
    profile_suffix = profile_info.get('suffix', 'DEFAULT')
    script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_suffix}.txt"
    voiceover_output_dir = voiceovers_dir / f"{folder_name}_voiceover_{profile_suffix}"
    voiceover_output_dir.mkdir(parents=True, exist_ok=True)

    if not script_file.exists():
        logger.error(f"Script file not found: {script_file}")
        return False

    voice_name = profile_info.get('default_voice', 'ALEX')
    voice_url = get_voice_url_by_name(voice_name)

    args = [
        str(script_file),
        "--output-folder", str(voiceover_output_dir),
        "--voice-url", voice_url,
        "--voice-name", voice_name
    ]

    return run_python_script(SCRIPT_VOICE_SCRIPT, args)

def run_broll_step(input_clips_dir, broll_clips_dir, voiceovers_dir, global_broll_folder=None):
    """Run B-roll clip creation step"""

    # If global B-roll folder is specified, use it directly
    if global_broll_folder and Path(global_broll_folder).exists():
        source_folder = Path(global_broll_folder)
        logger.info(f"Using GLOBAL B-roll folder: {source_folder}")
    else:
        source_folder = input_clips_dir

    # Use smart B-roll processor if available, otherwise use simple copy
    if SMART_BROLL_SCRIPT.exists():
        # Build arguments for smart B-roll processor (positional: source, output)
        args = [
            str(source_folder),  # source (positional)
            str(broll_clips_dir),  # output (positional)
        ]

        return run_python_script(SMART_BROLL_SCRIPT, args)
    else:
        # Fallback: Copy source clips as B-roll
        logger.info(f"Copying clips from {source_folder} as B-roll")
        broll_clips_dir.mkdir(parents=True, exist_ok=True)

        clips_copied = 0
        for clip in source_folder.glob("*.mp4"):
            dest = broll_clips_dir / clip.name
            if not dest.exists():
                shutil.copy(clip, dest)
                clips_copied += 1

        logger.info(f"Copied {clips_copied} B-roll clips")
        return True

def run_assembly_step(folder_name, voiceovers_dir, broll_clips_dir, final_videos_dir, log_dir, profile_info, enable_logo=True):
    """Run final video assembly step"""
    profile_suffix = profile_info.get('suffix', 'DEFAULT')
    profile_name = profile_info.get('name', profile_suffix)
    voiceover_folder = voiceovers_dir / f"{folder_name}_voiceover_{profile_suffix}"
    output_folder = final_videos_dir / f"{folder_name}_final_{profile_suffix}"
    output_folder.mkdir(parents=True, exist_ok=True)

    args = [
        "--voiceovers", str(voiceover_folder),
        "--clips", str(broll_clips_dir),
        "--output", str(output_folder),
        "--channel-name", profile_name,
    ]

    # Set environment variable for logo feature
    env = os.environ.copy()
    env['ENABLE_LOGO_FEATURE'] = 'true' if enable_logo else 'false'

    return run_python_script_with_env(CLIPS_PLUS_VOICEOVER_SCRIPT, args, env=env)

def run_combine_step(folder_name, final_videos_dir, combined_dir, profile_info):
    """Run combine videos step - combines final videos directly"""
    profile_suffix = profile_info.get('suffix', 'DEFAULT')
    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_suffix}"
    profile_combined_dir = combined_dir / f"{folder_name}_combined_{profile_suffix}"
    profile_combined_dir.mkdir(parents=True, exist_ok=True)

    background_music_path, voice_level, music_level = get_background_music_for_profile(profile_info)

    args = [
        "--input", str(profile_final_dir),
        "--output", str(profile_combined_dir),
        "--video-stem", folder_name,
        "--voice-level", str(voice_level),
        "--music-level", str(music_level)
    ]

    if background_music_path:
        args.extend([
            "--enable-music",
            "--background-music", str(background_music_path)
        ])
        logger.info(f"Using background music: {Path(background_music_path).name}")

    return run_python_script(COMBINE_RANKED_SCRIPT, args)

def run_combine_step_direct(folder_name, final_videos_dir, combined_dir, profile_info):
    """Run combine step directly from final_videos (no ranking step for story videos)"""
    profile_suffix = profile_info.get('suffix', 'DEFAULT')
    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_suffix}"
    profile_combined_dir = combined_dir / f"{folder_name}_combined_{profile_suffix}"
    profile_combined_dir.mkdir(parents=True, exist_ok=True)

    background_music_path, voice_level, music_level = get_background_music_for_profile(profile_info)

    args = [
        "--input", str(profile_final_dir),
        "--output", str(profile_combined_dir),
        "--video-stem", folder_name,
        "--voice-level", str(voice_level),
        "--music-level", str(music_level)
    ]

    if background_music_path:
        args.extend([
            "--enable-music",
            "--background-music", str(background_music_path)
        ])
        logger.info(f"Using background music: {Path(background_music_path).name}")

    return run_python_script(COMBINE_RANKED_SCRIPT, args)

# ==============================================================================
# --- MAIN PIPELINE ---
# ==============================================================================

def process_story_video(input_folder: Path, output_folder: Path, selected_profiles: list,
                        start_step: int = 0, options: dict = None):
    """
    Main Story Video pipeline - simplified for voiceover-only content.

    Args:
        input_folder: Folder containing voiceover video clips
        output_folder: Base output directory
        selected_profiles: List of (profile_key, profile_info) tuples
        start_step: Step to start from (0-8)
        options: Dict with options (music, logo, parallel, clean, global_broll, broll_path)
    """
    if options is None:
        options = {}

    folder_name = input_folder.name
    video_output_dir = output_folder / folder_name

    # Create directories
    input_clips_dir = video_output_dir / SUBDIR_INPUT_CLIPS
    transcripts_dir = video_output_dir / SUBDIR_TRANSCRIPTS
    ai_scripts_dir = video_output_dir / SUBDIR_AI_SCRIPTS
    voiceovers_dir = video_output_dir / SUBDIR_VOICEOVERS
    broll_clips_dir = video_output_dir / SUBDIR_BROLL_CLIPS
    final_videos_dir = video_output_dir / SUBDIR_FINAL_VIDEOS
    combined_dir = video_output_dir / SUBDIR_COMBINED_VIDEOS
    youtube_dir = video_output_dir / SUBDIR_YOUTUBE_UPLOADS
    log_dir = video_output_dir / SUBDIR_LOGS
    temp_script_dir = log_dir / "temp_scripts"

    for d in [video_output_dir, input_clips_dir, transcripts_dir, ai_scripts_dir,
              voiceovers_dir, broll_clips_dir, final_videos_dir,
              combined_dir, youtube_dir, log_dir, temp_script_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Clean output if requested
    if options.get('clean', False):
        logger.info("Cleaning output folder...")
        for subdir in [transcripts_dir, ai_scripts_dir, voiceovers_dir, broll_clips_dir,
                       final_videos_dir, combined_dir]:
            if subdir.exists():
                shutil.rmtree(subdir)
                subdir.mkdir(parents=True, exist_ok=True)

    pipeline_steps = get_pipeline_steps_info()
    max_step = max(pipeline_steps.keys())
    num_profiles = len(selected_profiles)

    logger.info(f"\n{'='*80}")
    logger.info(f"📖 STORY VIDEO PIPELINE: {folder_name}")
    logger.info(f"   Creating {num_profiles} video(s) using:")
    for profile_key, profile_info in selected_profiles:
        logger.info(f"   • {profile_info['name']} ({profile_info['default_voice']})")
    logger.info(f"   Output: {video_output_dir}")
    logger.info(f"{'='*80}")

    overall_success = True
    enable_logo = options.get('logo', True)
    enable_music = options.get('music', True)
    global_broll_folder = options.get('broll_path', '') if options.get('global_broll', False) else None

    for step_num in sorted(pipeline_steps.keys()):
        if step_num < start_step:
            logger.info(f"⏭️ Skipping Step {step_num}: {pipeline_steps[step_num]['name']}")
            continue

        step_info = pipeline_steps[step_num]
        logger.info(f"\n🚀 Step {step_num}: {step_info['name']}...")

        step_success = False

        try:
            if step_num == 0:
                # Copy input clips
                logger.info(f"📁 Copying input clips from {input_folder}...")
                for clip in input_folder.glob("*.mp4"):
                    dest = input_clips_dir / clip.name
                    if not dest.exists():
                        shutil.copy(clip, dest)
                        logger.info(f"   Copied: {clip.name}")
                step_success = True

            elif step_num == 1:
                # Transcribe clips
                existing_transcripts = list(transcripts_dir.glob("*.txt"))
                if existing_transcripts:
                    logger.info(f"⚡ SMART SKIP: Found {len(existing_transcripts)} existing transcripts")
                    step_success = True
                else:
                    step_success = run_transcription_step(folder_name, input_clips_dir, transcripts_dir, temp_script_dir)

            elif step_num == 2:
                # AI Rewrite Scripts for each profile
                logger.info(f"📝 Creating scripts for {num_profiles} profiles...")
                all_success = True
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    script_file = ai_scripts_dir / f"{folder_name}_rewritten_script_{profile_suffix}.txt"

                    if script_file.exists() and script_file.stat().st_size > 100:
                        logger.info(f"   ⚡ SMART SKIP: Found existing script for {profile_info['name']}")
                        continue

                    logger.info(f"   Creating {profile_info['name']} script...")
                    success = run_ai_script_step(folder_name, transcripts_dir, ai_scripts_dir, profile_info, "")
                    if not success:
                        all_success = False
                        logger.error(f"   ❌ Failed: {profile_info['name']}")
                    else:
                        logger.info(f"   ✅ Created: {profile_info['name']}")
                step_success = all_success

            elif step_num == 3:
                # Generate Voiceovers for each profile
                logger.info(f"🎤 Generating voiceovers for {num_profiles} profiles...")
                all_success = True
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    voiceover_dir = voiceovers_dir / f"{folder_name}_voiceover_{profile_suffix}"

                    if voiceover_dir.exists() and list(voiceover_dir.glob("*.mp3")):
                        logger.info(f"   ⚡ SMART SKIP: Found existing voiceovers for {profile_info['name']}")
                        continue

                    logger.info(f"   Generating {profile_info['name']} voiceover...")
                    success = run_voiceover_step(folder_name, ai_scripts_dir, voiceovers_dir, profile_info, temp_script_dir)
                    if not success:
                        all_success = False
                        logger.error(f"   ❌ Failed: {profile_info['name']}")
                    else:
                        logger.info(f"   ✅ Generated: {profile_info['name']}")
                step_success = all_success

            elif step_num == 4:
                # Create B-roll clips
                existing_clips = list(broll_clips_dir.glob("*.mp4"))
                if existing_clips:
                    logger.info(f"⚡ SMART SKIP: Found {len(existing_clips)} existing B-roll clips")
                    step_success = True
                else:
                    step_success = run_broll_step(input_clips_dir, broll_clips_dir, voiceovers_dir, global_broll_folder)

            elif step_num == 5:
                # Assemble Final Videos for each profile
                logger.info(f"🎬 Assembling final videos for {num_profiles} profiles...")
                all_success = True
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_suffix}"

                    if profile_final_dir.exists() and list(profile_final_dir.glob("*.mp4")):
                        logger.info(f"   ⚡ SMART SKIP: Found existing final videos for {profile_info['name']}")
                        continue

                    logger.info(f"   Assembling {profile_info['name']}...")
                    success = run_assembly_step(folder_name, voiceovers_dir, broll_clips_dir,
                                                final_videos_dir, log_dir, profile_info, enable_logo)
                    if not success:
                        all_success = False
                        logger.error(f"   ❌ Failed: {profile_info['name']}")
                    else:
                        logger.info(f"   ✅ Assembled: {profile_info['name']}")
                step_success = all_success

            elif step_num == 6:
                # Combine Final Videos for each profile (no ranking needed for story videos)
                logger.info(f"🎬 Combining final videos for {num_profiles} profiles...")
                all_success = True
                for profile_key, profile_info in selected_profiles:
                    profile_suffix = profile_info.get('suffix', profile_key)
                    # For story videos, combine directly from final_videos (no ranking)
                    profile_final_dir = final_videos_dir / f"{folder_name}_final_{profile_suffix}"
                    profile_combined_dir = combined_dir / f"{folder_name}_combined_{profile_suffix}"

                    if profile_combined_dir.exists() and list(profile_combined_dir.glob("*.mp4")):
                        logger.info(f"   ⚡ SMART SKIP: Found existing combined video for {profile_info['name']}")
                        continue

                    # Temporarily modify profile to respect music option
                    if not enable_music:
                        profile_info = profile_info.copy()
                        profile_info['background_music'] = None

                    logger.info(f"   Combining {profile_info['name']}...")
                    success = run_combine_step_direct(folder_name, final_videos_dir, combined_dir, profile_info)
                    if not success:
                        all_success = False
                        logger.error(f"   ❌ Failed: {profile_info['name']}")
                    else:
                        logger.info(f"   ✅ Combined: {profile_info['name']}")
                step_success = all_success

            elif step_num == 7:
                # Upload to YouTube (optional)
                logger.info("📤 YouTube upload step (manual)")
                logger.info("   Final videos are ready in combined_videos folder")
                logger.info("   Upload manually or use YouTube upload script")
                step_success = True

        except Exception as e:
            logger.error(f"❌ Step {step_num} failed with error: {e}")
            step_success = False

        if step_success:
            logger.info(f"✅ Step {step_num} completed: {step_info['name']}")
        else:
            logger.error(f"❌ Pipeline failed at Step {step_num}: {step_info['name']}")
            overall_success = False
            break

    # Cleanup
    if temp_script_dir.exists():
        try:
            shutil.rmtree(temp_script_dir)
        except:
            pass

    if overall_success:
        logger.info(f"\n{'='*80}")
        logger.info(f"✨ STORY VIDEO PIPELINE COMPLETE: {folder_name}")
        logger.info(f"📹 Created {num_profiles} video(s):")
        for profile_key, profile_info in selected_profiles:
            combined_path = combined_dir / f"{folder_name}_combined_{profile_info['suffix']}"
            logger.info(f"   • {profile_info['name']}: {combined_path}")
        logger.info(f"{'='*80}")
    else:
        logger.info(f"\n{'='*80}")
        logger.info(f"🛑 STORY VIDEO PIPELINE FAILED: {folder_name}")
        logger.info(f"{'='*80}")

    return overall_success

# ==============================================================================
# --- MAIN ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Story Video Creator - Process voiceover-only videos",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--input-folder", "-i", required=True,
                        help="Input folder containing voiceover video clips")
    parser.add_argument("--output-folder", "-o", required=True,
                        help="Output base directory")
    parser.add_argument("--profiles", "-p", nargs="+",
                        help="Profile names to use")
    parser.add_argument("--start-step", "-s", type=int, default=0,
                        help="Step to start from (0-8)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean output folder before processing")
    parser.add_argument("--no-music", action="store_true",
                        help="Disable background music")
    parser.add_argument("--no-logo", action="store_true",
                        help="Disable logo overlay")
    parser.add_argument("--global-broll", type=str, default="",
                        help="Path to global B-roll folder")

    args = parser.parse_args()

    input_folder = Path(args.input_folder)
    output_folder = Path(args.output_folder)

    if not input_folder.exists():
        logger.error(f"Input folder not found: {input_folder}")
        sys.exit(1)

    output_folder.mkdir(parents=True, exist_ok=True)

    # Select profiles
    if args.profiles:
        use_specific_profiles(args.profiles)

    selected_profiles = list(PROMPT_PROFILES.items())

    if not selected_profiles:
        logger.error("No profiles selected!")
        sys.exit(1)

    options = {
        'clean': args.clean,
        'music': not args.no_music,
        'logo': not args.no_logo,
        'parallel': True,
        'global_broll': bool(args.global_broll),
        'broll_path': args.global_broll
    }

    success = process_story_video(
        input_folder=input_folder,
        output_folder=output_folder,
        selected_profiles=selected_profiles,
        start_step=args.start_step,
        options=options
    )

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
