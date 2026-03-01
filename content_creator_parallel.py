# ==============================================================================
# CONTENT CREATOR - PARALLEL MODE
# ==============================================================================
# This is the new fast parallel video processor using the Queue-Based Pipeline.
# It processes multiple videos simultaneously for maximum speed.
#
# Usage:
#   python content_creator_parallel.py --interviews-folder ./input --broll-folder ./broll
#
# Features:
#   - Process 3+ videos simultaneously (configurable)
#   - Each video gets its own browser window for voiceovers
#   - Smart resource management (GPU, CPU, memory)
#   - Real-time progress tracking
# ==============================================================================

import os
import sys
import json
import time
import shutil
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional
import io

# Fix encoding (only if not already wrapped)
try:
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer') and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer') and sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass  # Ignore encoding setup errors

# Import the queue manager
from video_queue_manager import (
    VideoQueueManager,
    VideoTask,
    QueueConfig,
    create_video_task,
    BrowserProfileManager
)

# Import content_creator module (lazy import to avoid encoding issues)
import content_creator as cc

# Re-export for convenience
PROMPT_PROFILES = cc.PROMPT_PROFILES
AVAILABLE_VOICES = cc.AVAILABLE_VOICES
DEFAULT_INTERVIEWS_FOLDER = cc.DEFAULT_INTERVIEWS_FOLDER
DEFAULT_BROLL_FOLDER = cc.DEFAULT_BROLL_FOLDER
DEFAULT_PROJECT_OUTPUT_BASE_DIR = cc.DEFAULT_PROJECT_OUTPUT_BASE_DIR
SCRIPT_DIR = cc.SCRIPT_DIR
STEP_1_DIR = cc.STEP_1_DIR
STEP_2_DIR = cc.STEP_2_DIR
STEP_3_DIR = cc.STEP_3_DIR
STEP_4_DIR = cc.STEP_4_DIR
STEP_5_DIR = cc.STEP_5_DIR
STEP_6_DIR = cc.STEP_6_DIR
STEP_7_DIR = cc.STEP_7_DIR
STEP_8_DIR = cc.STEP_8_DIR
SUBDIR_INTERVIEW_CLIPS = cc.SUBDIR_INTERVIEW_CLIPS
SUBDIR_BROLL_CLIPS = cc.SUBDIR_BROLL_CLIPS
SUBDIR_ORIGINAL_VIDEO = cc.SUBDIR_ORIGINAL_VIDEO
SUBDIR_LOGS = cc.SUBDIR_LOGS
logger = cc.logger

# ==============================================================================
# CONFIGURATION
# ==============================================================================

class ParallelConfig(QueueConfig):
    """Extended configuration for parallel processing"""

    # Override defaults for faster processing
    MAX_CONCURRENT_VIDEOS = 3  # Process 3 videos at once
    MAX_CONCURRENT_STEP3 = 3   # 3 browser windows for voiceovers


# ==============================================================================
# STEP CALLBACKS
# ==============================================================================

def step_0_copy_original(video: VideoTask, step_num: int) -> bool:
    """Step 0: Copy original video files"""
    try:
        original_dir = video.output_folder / SUBDIR_ORIGINAL_VIDEO
        original_dir.mkdir(parents=True, exist_ok=True)

        video_files = [f for f in video.input_folder.iterdir()
                      if f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']]

        for video_file in video_files:
            shutil.copy(video_file, original_dir / video_file.name)
            logger.info(f"[{video.video_name}] Copied: {video_file.name}")

        return True
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 0 error: {e}")
        return False


def step_1_smart_processing(video: VideoTask, step_num: int) -> bool:
    """Step 1: Smart Interview Processing"""
    try:
        step_1_dir = video.output_folder / STEP_1_DIR
        interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS

        # Check if already done
        if interview_clips_dir.exists():
            clips = list(interview_clips_dir.glob("*.mp4"))
            if len(clips) > 0:
                logger.info(f"[{video.video_name}] Step 1 already complete: {len(clips)} clips")
                return True

        # Run smart interview processing
        return cc.run_smart_interview_processing(
            video.input_folder,
            video.broll_folder,
            video.output_folder,
            video.profile_info
        )
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 1 error: {e}")
        return False


def step_2_styling(video: VideoTask, step_num: int) -> bool:
    """Step 2: Style Interview Clips"""
    try:
        step_1_dir = video.output_folder / STEP_1_DIR
        step_2_dir = video.output_folder / STEP_2_DIR
        interview_clips_dir = step_1_dir / SUBDIR_INTERVIEW_CLIPS

        # Check if already done
        if cc.check_step_complete(2, step_2_dir):
            logger.info(f"[{video.video_name}] Step 2 already complete")
            return True

        return cc.run_styling_step_single(
            video.video_name,
            interview_clips_dir,
            step_2_dir,
            video.profile_info
        )
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 2 error: {e}")
        return False


def step_3_voiceover(video: VideoTask, step_num: int) -> bool:
    """Step 3: Generate Voiceovers - Uses unique browser profile for parallel processing"""
    try:
        step_3_dir = video.output_folder / STEP_3_DIR

        # Check if already done
        if cc.check_step_complete(3, step_3_dir):
            logger.info(f"[{video.video_name}] Step 3 already complete")
            return True

        # Get voice URL
        voice_url = cc.get_voice_url_by_name(video.profile_info["default_voice"])

        # Pass the custom browser profile path for parallel processing
        return cc.run_voiceover_step_single_new(
            video.video_name,
            video.output_folder,
            step_3_dir,
            voice_url,
            video.output_folder / SUBDIR_LOGS / "temp_scripts",
            video.profile_info,
            browser_profile_path=str(video.browser_profile_path)  # NEW: Custom profile
        )
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 3 error: {e}")
        return False


def step_4_broll(video: VideoTask, step_num: int) -> bool:
    """Step 4: Rearrange B-roll Clips"""
    try:
        step_1_dir = video.output_folder / STEP_1_DIR
        step_3_dir = video.output_folder / STEP_3_DIR
        step_4_dir = video.output_folder / STEP_4_DIR
        broll_clips_dir = step_1_dir / SUBDIR_BROLL_CLIPS

        # Check if already done
        if cc.check_step_complete(4, step_4_dir, expected_patterns=["*.mp4"], min_files=5):
            logger.info(f"[{video.video_name}] Step 4 already complete")
            return True

        return cc.run_broll_step(broll_clips_dir, step_4_dir, step_3_dir)
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 4 error: {e}")
        return False


def step_5_assembly(video: VideoTask, step_num: int) -> bool:
    """Step 5: Assemble Final Videos"""
    try:
        step_3_dir = video.output_folder / STEP_3_DIR
        step_4_dir = video.output_folder / STEP_4_DIR
        step_5_dir = video.output_folder / STEP_5_DIR
        log_dir = video.output_folder / SUBDIR_LOGS

        # Check if already done
        if cc.check_step_complete(5, step_5_dir, expected_patterns=["*.mp4"], min_files=5):
            logger.info(f"[{video.video_name}] Step 5 already complete")
            return True

        return cc.run_assembly_step_single(
            video.video_name,
            step_3_dir,
            step_4_dir,
            step_5_dir,
            log_dir,
            video.profile_info
        )
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 5 error: {e}")
        return False


def step_6_ranking(video: VideoTask, step_num: int) -> bool:
    """Step 6: Rank Video Sequence"""
    try:
        step_2_dir = video.output_folder / STEP_2_DIR
        step_5_dir = video.output_folder / STEP_5_DIR
        step_6_dir = video.output_folder / STEP_6_DIR

        # Check if already done
        if check_step_complete(6, step_6_dir):
            logger.info(f"[{video.video_name}] Step 6 already complete")
            return True

        return run_ranking_step_single_new(
            video.video_name,
            step_2_dir,
            step_5_dir,
            step_6_dir,
            video.profile_info
        )
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 6 error: {e}")
        return False


def step_7_combine(video: VideoTask, step_num: int) -> bool:
    """Step 7: Combine Videos"""
    try:
        step_6_dir = video.output_folder / STEP_6_DIR
        step_7_dir = video.output_folder / STEP_7_DIR

        # Check if already done
        if check_step_complete(7, step_7_dir, expected_patterns=["*.mp4"], min_files=1):
            logger.info(f"[{video.video_name}] Step 7 already complete")
            return True

        return run_combination_step_single(
            video.video_name,
            step_6_dir,
            step_7_dir,
            None,
            video.profile_info
        )
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 7 error: {e}")
        return False


def step_8_upload(video: VideoTask, step_num: int) -> bool:
    """Step 8: YouTube Upload"""
    try:
        step_8_dir = video.output_folder / STEP_8_DIR

        if video.profile_info.get("enable_upload", False):
            return run_youtube_upload_step(
                video.video_name,
                video.output_folder,
                step_8_dir,
                video.profile_info
            )
        else:
            logger.info(f"[{video.video_name}] YouTube upload disabled")
            return True
    except Exception as e:
        logger.error(f"[{video.video_name}] Step 8 error: {e}")
        return False


# ==============================================================================
# MAIN PARALLEL PROCESSOR
# ==============================================================================

def run_parallel_processing(
    interviews_folder: Path,
    broll_folder: Path,
    output_base_dir: Path,
    profile_info: Dict,
    max_concurrent: int = 3
) -> bool:
    """
    Run parallel video processing for all videos in the interviews folder.

    Args:
        interviews_folder: Folder containing interview videos
        broll_folder: Folder containing B-roll clips
        output_base_dir: Base output directory
        profile_info: Profile configuration
        max_concurrent: Maximum concurrent videos

    Returns:
        True if all videos processed successfully
    """

    # Configure queue manager
    config = ParallelConfig()
    config.MAX_CONCURRENT_VIDEOS = max_concurrent

    manager = VideoQueueManager(config)

    # Register step callbacks
    step_callbacks = {
        0: step_0_copy_original,
        1: step_1_smart_processing,
        2: step_2_styling,
        3: step_3_voiceover,
        4: step_4_broll,
        5: step_5_assembly,
        6: step_6_ranking,
        7: step_7_combine,
        8: step_8_upload,
    }

    for step_num, callback in step_callbacks.items():
        manager.register_step_callback(step_num, callback)

    # Find all video files
    video_files = [f for f in interviews_folder.iterdir()
                   if f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']]

    if not video_files:
        logger.error(f"No video files found in: {interviews_folder}")
        return False

    logger.info(f"\n{'='*60}")
    logger.info(f"PARALLEL VIDEO PROCESSING")
    logger.info(f"{'='*60}")
    logger.info(f"Videos found: {len(video_files)}")
    logger.info(f"Max concurrent: {max_concurrent}")
    logger.info(f"Profile: {profile_info.get('name', 'Default')}")
    logger.info(f"{'='*60}\n")

    # Create video tasks
    for video_file in sorted(video_files):
        video_name = video_file.stem
        output_folder = output_base_dir / video_name / profile_info.get('suffix', 'default')

        task = create_video_task(
            video_name=video_name,
            input_folder=interviews_folder,
            output_folder=output_folder,
            broll_folder=broll_folder,
            profile_info=profile_info
        )

        manager.add_video(task)

    # Start processing
    logger.info("Starting parallel processing...")
    manager.start()

    # Monitor progress
    try:
        last_status = None
        while not manager.wait_for_completion(timeout=5):
            status = manager.get_status()
            if status != last_status:
                manager.print_status()
                last_status = status

    except KeyboardInterrupt:
        logger.info("\nStopping processing (Ctrl+C)...")
        manager.stop(wait_for_completion=False)
        return False

    # Final status
    manager.print_status()

    # Get results
    status = manager.get_status()
    success = status['failed'] == 0

    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Completed: {status['completed']}")
    logger.info(f"Failed: {status['failed']}")
    logger.info(f"{'='*60}\n")

    return success


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

def main():
    """Main entry point for parallel content creator"""

    parser = argparse.ArgumentParser(
        description="Parallel Video Content Creator - Process multiple videos simultaneously",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python content_creator_parallel.py --interviews-folder ./input --broll-folder ./broll
  python content_creator_parallel.py --max-concurrent 5 --profile BASKLY
        """
    )

    parser.add_argument('--interviews-folder', type=Path, default=DEFAULT_INTERVIEWS_FOLDER,
                        help="Folder containing interview videos")
    parser.add_argument('--broll-folder', type=Path, default=DEFAULT_BROLL_FOLDER,
                        help="Folder containing B-roll clips")
    parser.add_argument('--output-base-dir', type=Path, default=DEFAULT_PROJECT_OUTPUT_BASE_DIR,
                        help="Base output directory")
    parser.add_argument('--max-concurrent', type=int, default=3,
                        help="Maximum concurrent videos (default: 3)")
    parser.add_argument('--profile', type=str, default=None,
                        help="Profile name to use (default: first available)")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('parallel_processing.log', encoding='utf-8')
        ]
    )

    # Validate folders
    if not args.interviews_folder.exists():
        logger.error(f"Interviews folder not found: {args.interviews_folder}")
        sys.exit(1)

    if not args.broll_folder.exists():
        logger.warning(f"B-roll folder not found, creating: {args.broll_folder}")
        args.broll_folder.mkdir(parents=True, exist_ok=True)

    # Select profile
    if args.profile:
        if args.profile in PROMPT_PROFILES:
            profile_info = PROMPT_PROFILES[args.profile]
        else:
            logger.error(f"Profile not found: {args.profile}")
            logger.info(f"Available profiles: {list(PROMPT_PROFILES.keys())}")
            sys.exit(1)
    else:
        # Use first available profile
        profile_key = list(PROMPT_PROFILES.keys())[0]
        profile_info = PROMPT_PROFILES[profile_key]
        logger.info(f"Using default profile: {profile_key}")

    # Print configuration
    print("\n" + "="*60)
    print("PARALLEL CONTENT CREATOR")
    print("="*60)
    print(f"Interviews: {args.interviews_folder}")
    print(f"B-roll:     {args.broll_folder}")
    print(f"Output:     {args.output_base_dir}")
    print(f"Concurrent: {args.max_concurrent}")
    print(f"Profile:    {profile_info.get('name', 'Default')}")
    print("="*60 + "\n")

    # Run parallel processing
    success = run_parallel_processing(
        interviews_folder=args.interviews_folder,
        broll_folder=args.broll_folder,
        output_base_dir=args.output_base_dir,
        profile_info=profile_info,
        max_concurrent=args.max_concurrent
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
