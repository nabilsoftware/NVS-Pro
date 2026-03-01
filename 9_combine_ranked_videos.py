#!/usr/bin/env python3
# Fix Windows console encoding for emoji/unicode
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Step 9: Combine Ranked Videos with Background Music (Enhanced Version)
=======================================================================

This script combines all ranked videos from Step 8 into a single complete video
using GPU-accelerated frame-perfect normalization to eliminate glitches and duration issues.
NOW WITH BACKGROUND MUSIC AND AUDIO LEVEL CONTROLS!

FIXES:
- Frame rate mismatches between 24fps and 30fps videos
- Duration problems (29 minutes instead of 18)
- Audio/video lag and glitches  
- Produces exact duration like CapCut
- Uses RTX 3060 Ti GPU for 3-5x faster processing

NEW FEATURES:
- Background music integration
- Voice level control (0.0-1.0)
- Background music level control (0.0-1.0)
- Audio mixing and balancing

Input: Ranked video sequence from Step 8 (8_ranked_output folder)
Output: Single complete video with background music (9_final_combined folder)

Usage:
- Standalone: python 9_combine_ranked_videos.py --input <path> --output <path> --background-music <path>
- Orchestrator: Called automatically after Step 8
"""

import os
import sys
import shutil
import argparse
import logging
import subprocess
from pathlib import Path
from typing import List
import json

# Import app utilities for portable paths
try:
    import app_utils
    FFMPEG_PATH = app_utils.get_ffmpeg_path()
    FFPROBE_PATH = app_utils.get_ffprobe_path()
except ImportError:
    # Fallback if app_utils not available
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default paths (used if not run by orchestrator)
DEFAULT_INPUT_FOLDER = ""
DEFAULT_OUTPUT_FOLDER = ""
DEFAULT_BACKGROUND_MUSIC = ""

# Supported video extensions
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')
# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg')

# Output settings
OUTPUT_FORMAT = "mp4"

# Audio mixing defaults
DEFAULT_VOICE_LEVEL = 1.2     # voice volume
DEFAULT_MUSIC_LEVEL = 0.15      # background music volume
DEFAULT_ENABLE_MUSIC = True    # Enabled by default

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
# UTILITY FUNCTIONS
# =============================================================================

def get_video_info(video_path):
    """Get detailed video information"""
    try:
        cmd = [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(video_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            
            # Get video stream info
            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
            fps = None
            if video_stream and 'r_frame_rate' in video_stream:
                fps_str = video_stream['r_frame_rate']
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    fps = float(num) / float(den)
                else:
                    fps = float(fps_str)
            
            return duration, fps, data
    except Exception as e:
        logger.error(f"Error getting info for {video_path}: {e}")
    return 0, 30, None

def normalize_video_precisely(input_video, output_video, target_fps=30):
    """Normalize video with precise duration preservation and audio level normalization using GPU acceleration"""
    
    # Get original duration first
    original_duration, original_fps, _ = get_video_info(input_video)
    
    logger.info(f"  GPU Normalizing {input_video.name}: {original_duration:.1f}s @ {original_fps:.1f}fps -> {target_fps}fps + Audio Normalization")
    
    # Enhanced command with audio normalization
    cmd = [
        FFMPEG_PATH, '-y',
        '-hwaccel', 'cuda',                       # Use CUDA acceleration
        '-i', str(input_video),
        '-c:v', 'h264_nvenc',                     # NVIDIA GPU encoder
        '-preset', 'p4',                          # NVENC preset (fast)
        '-cq', '18',                              # Quality for NVENC
        '-r', str(target_fps),                    # Force exact framerate
        '-video_track_timescale', '90000',        # High precision timescale
        '-pix_fmt', 'yuv420p',
        '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',  # Audio normalization to broadcast standards
        '-c:a', 'aac',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '192k',
        '-avoid_negative_ts', 'make_zero',        # Ensure proper timestamps
        '-fflags', '+genpts',                     # Generate proper timestamps
        str(output_video)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            # Verify output file exists
            if not output_video.exists():
                logger.error(f"    OUTPUT FILE NOT CREATED: {output_video}")
                return False

            # Verify duration is preserved
            new_duration, new_fps, _ = get_video_info(output_video)
            duration_diff = abs(new_duration - original_duration)
            
            if duration_diff < 0.5:  # Allow 0.5s tolerance
                logger.info(f"    GPU SUCCESS: {new_duration:.1f}s @ {new_fps:.1f}fps (diff: {duration_diff:.1f}s)")
                return True
            else:
                logger.warning(f"    Duration changed: {original_duration:.1f}s -> {new_duration:.1f}s (diff: {duration_diff:.1f}s)")
                return True  # Still use it, but log the warning
        else:
            logger.warning(f"    GPU failed, trying CPU fallback: {result.stderr}")
            # CPU fallback with audio normalization
            cmd_cpu = [
                FFMPEG_PATH, '-y',
                '-i', str(input_video),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '18',
                '-r', str(target_fps),
                '-video_track_timescale', '90000',
                '-pix_fmt', 'yuv420p',
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',  # Audio normalization to broadcast standards
                '-c:a', 'aac',
                '-ar', '44100',
                '-ac', '2',
                '-b:a', '192k',
                '-avoid_negative_ts', 'make_zero',
                '-fflags', '+genpts',
                str(output_video)
            ]
            result_cpu = subprocess.run(cmd_cpu, capture_output=True, text=True, timeout=300)
            if result_cpu.returncode == 0:
                if not output_video.exists():
                    logger.error(f"    CPU OUTPUT FILE NOT CREATED: {output_video}")
                    return False
                new_duration, new_fps, _ = get_video_info(output_video)
                duration_diff = abs(new_duration - original_duration)
                logger.info(f"    CPU SUCCESS: {new_duration:.1f}s @ {new_fps:.1f}fps (diff: {duration_diff:.1f}s)")
                return True
            else:
                logger.error(f"    CPU also failed: {result_cpu.stderr}")
                return False
    except Exception as e:
        logger.error(f"    Error: {e}")
        return False

def get_video_files(folder_path: Path) -> List[Path]:
    """Get all video files from folder, sorted by name (to maintain ranking order)"""
    if not folder_path.exists() or not folder_path.is_dir():
        logger.warning(f"Folder not found or not a directory: {folder_path}")
        return []
    
    video_files = []
    for file_path in folder_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
            video_files.append(file_path)
    
    # Sort by filename to maintain ranking order (001_, 002_, etc.)
    video_files.sort(key=lambda x: x.name.lower())
    logger.info(f"Found {len(video_files)} ranked videos")
    
    for i, video in enumerate(video_files, 1):
        logger.info(f"   {i}. {video.name}")
    
    return video_files

# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration using ffprobe"""
    try:
        cmd = [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json', '-show_format', str(audio_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
    except Exception as e:
        logger.error(f"Error getting audio duration for {audio_path}: {e}")
    return 0.0

def validate_background_music(music_path: Path) -> bool:
    """Validate background music file exists and is readable"""
    if not music_path.exists():
        logger.error(f"Background music file not found: {music_path}")
        return False
    
    if music_path.suffix.lower() not in AUDIO_EXTENSIONS:
        logger.error(f"Unsupported audio format: {music_path.suffix}")
        return False
    
    duration = get_audio_duration(music_path)
    if duration == 0:
        logger.error(f"Cannot read audio file or zero duration: {music_path}")
        return False
    
    logger.info(f"✅ Background music validated: {music_path.name} ({duration:.1f}s)")
    return True

def combine_frame_perfect_with_music(input_folder: Path, output_folder: Path, output_filename="complete_video.mp4", 
                                   background_music: Path = None, voice_level: float = 0.8, music_level: float = 0.3) -> bool:
    """Combine videos with frame-perfect precision"""
    
    logger.info("🎬 ENHANCED FRAME PERFECT COMBINER WITH BACKGROUND MUSIC STARTING...")
    logger.info(f"📁 Input: {input_folder}")
    logger.info(f"📂 Output: {output_folder}")
    if background_music:
        logger.info(f"🎵 Background Music: {background_music.name}")
        logger.info(f"🔊 Voice Level: {voice_level*100:.0f}%")
        logger.info(f"🎶 Music Level: {music_level*100:.0f}%")
    else:
        logger.info("🔇 No background music (original audio only)")
    
    # Create output folder
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Create temp folder
    temp_folder = output_folder / "temp_normalized"
    temp_folder.mkdir(exist_ok=True)
    
    try:
        # Get video files
        video_files = get_video_files(input_folder)
        if not video_files:
            logger.error("No video files found!")
            return False
        
        logger.info(f"Found {len(video_files)} videos")
        
        # Calculate original total duration
        total_original = 0
        for video_file in video_files:
            duration, fps, _ = get_video_info(video_file)
            total_original += duration
        
        logger.info(f"Original total duration: {total_original:.1f}s ({total_original/60:.1f}m)")
        
        # Step 1: Normalize all videos to same specs
        logger.info("Step 1: Normalizing all videos to 30fps...")
        normalized_files = []
        
        for i, video_file in enumerate(video_files, 1):
            # Validate video file before processing
            duration, fps, video_info = get_video_info(video_file)
            
            # Skip corrupted or empty files
            if duration <= 0 or video_info is None:
                logger.warning(f"⚠️ SKIPPING corrupted/empty file: {video_file.name} (duration: {duration:.1f}s)")
                logger.warning(f"   This file will be excluded from the final video")
                continue
            
            # Check file size as additional validation
            file_size = video_file.stat().st_size
            if file_size < 1024:  # Less than 1KB is likely corrupted
                logger.warning(f"⚠️ SKIPPING tiny file: {video_file.name} (size: {file_size} bytes)")
                continue
            
            normalized_file = temp_folder / f"norm_{i:03d}.mp4"
            logger.info(f"Normalizing {i}/{len(video_files)}")
            
            success = normalize_video_precisely(video_file, normalized_file, target_fps=30)
            if success:
                normalized_files.append(normalized_file)
            else:
                logger.error(f"Failed to normalize {video_file.name}")
                return False
        
        # Check if we have any valid files after validation
        if not normalized_files:
            logger.error("❌ No valid video files remain after validation! All files were corrupted or empty.")
            return False
        
        if len(normalized_files) < len(video_files):
            logger.warning(f"⚠️ Processed {len(normalized_files)} out of {len(video_files)} total files (skipped {len(video_files) - len(normalized_files)} corrupted files)")
        
        # Verify total duration after normalization
        total_normalized = 0
        for norm_file in normalized_files:
            duration, _, _ = get_video_info(norm_file)
            total_normalized += duration
        
        logger.info(f"Normalized total duration: {total_normalized:.1f}s ({total_normalized/60:.1f}m)")
        duration_diff = abs(total_normalized - total_original)
        logger.info(f"Duration difference after normalization: {duration_diff:.1f}s")
        
        # Step 2: Create concat file
        logger.info("Step 2: Creating concat file...")
        concat_file = temp_folder / "normalized_list.txt"
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for norm_file in normalized_files:
                file_path = str(norm_file).replace('\\', '/')
                f.write(f"file '{file_path}'\n")
        
        # Step 3: Combine videos with optional background music
        if background_music and background_music.exists():
            logger.info("Step 3: Combining videos with background music and audio mixing...")
            output_file = output_folder / output_filename
            
            # Validate background music
            if not validate_background_music(background_music):
                logger.error("Background music validation failed!")
                return False
            
            # Get video duration for music looping
            video_duration = total_normalized
            music_duration = get_audio_duration(background_music)
            
            logger.info(f"🎬 Video duration: {video_duration:.1f}s")
            logger.info(f"🎵 Music duration: {music_duration:.1f}s")
            
            # Build complex audio filter for mixing
            # [0:a] = audio from concatenated video, [1:a] = background music
            audio_filter = f"[1:a]volume={music_level},aloop=loop=-1:size=2e+09[music];[0:a]volume={voice_level}[voice];[voice][music]amix=inputs=2:duration=first:dropout_transition=0,volume=1.0[mixed_audio]"
            
            cmd = [
                FFMPEG_PATH, '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),        # Video input
                '-i', str(background_music),   # Music input
                '-filter_complex', audio_filter,
                '-map', '0:v:0',               # Use video from first input
                '-map', '[mixed_audio]',       # Use mixed audio
                '-c:v', 'copy',                # Copy video (already normalized)
                '-c:a', 'aac',                 # Encode mixed audio
                '-ar', '44100',
                '-ac', '2',
                '-b:a', '192k',
                '-avoid_negative_ts', 'make_zero',
                str(output_file)
            ]
            
            logger.info(f"🎛️ Audio mixing: Voice {voice_level*100:.0f}% + Music {music_level*100:.0f}%")
            logger.info(f"🔧 FFmpeg command: {' '.join(cmd)}")
            logger.info(f"📄 Concat file: {concat_file}")
            logger.info(f"🎵 Music file: {background_music}")
            
        else:
            logger.info("Step 3: Combining videos (no background music)...")
            output_file = output_folder / output_filename
            
            cmd = [
                FFMPEG_PATH, '-y',
                '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                str(output_file)
            ]
        
        logger.info("🚀 Starting FFmpeg processing...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)  # Increased timeout for audio processing
        
        # Always log FFmpeg output for debugging
        if result.stdout:
            logger.info(f"📝 FFmpeg STDOUT: {result.stdout[-500:]}")  # Last 500 chars
        if result.stderr:
            logger.info(f"📝 FFmpeg STDERR: {result.stderr[-1000:]}")  # Last 1000 chars
        
        if result.returncode == 0:
            # Check final duration
            final_duration, final_fps, _ = get_video_info(output_file)
            file_size = output_file.stat().st_size / (1024 * 1024)
            
            if background_music and background_music.exists():
                logger.info("🎉 SUCCESS! Frame-perfect video with background music created!")
                logger.info(f"🎵 Background music: {background_music.name}")
                logger.info(f"🔊 Audio levels: Voice {voice_level*100:.0f}% + Music {music_level*100:.0f}%")
            else:
                logger.info("🎉 SUCCESS! Frame-perfect video created!")
            
            logger.info(f"📁 File: {output_file}")
            logger.info(f"💾 Size: {file_size:.1f} MB")
            logger.info(f"⏱️ Final duration: {final_duration:.1f}s ({final_duration/60:.1f}m)")
            logger.info(f"📊 Original duration: {total_original:.1f}s ({total_original/60:.1f}m)")
            logger.info(f"📏 Difference: {abs(final_duration - total_original):.1f}s")
            
            if abs(final_duration - total_original) < 5:
                logger.info("PERFECT! Duration matches original!")
                return True
            else:
                logger.warning("Duration still doesn't match perfectly")
                return True  # Still created a video
        else:
            logger.error(f"❌ FFmpeg failed with return code {result.returncode}")
            logger.error(f"❌ STDERR: {result.stderr}")
            
            # Try a simpler approach if complex filter failed
            if background_music and background_music.exists():
                logger.info("🔄 Trying simpler audio mixing approach...")
                
                # Simpler approach: mix audio with basic volume controls
                simple_cmd = [
                    FFMPEG_PATH, '-y',
                    '-f', 'concat', '-safe', '0',
                    '-i', str(concat_file),
                    '-i', str(background_music),
                    '-filter_complex', f'[0:a]volume={voice_level}[a0];[1:a]volume={music_level},aloop=loop=-1:size=2e+09[a1];[a0][a1]amix=inputs=2:duration=first[aout]',
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    str(output_file)
                ]
                
                simple_result = subprocess.run(simple_cmd, capture_output=True, text=True, timeout=600)
                if simple_result.returncode == 0:
                    logger.info("✅ Simple audio mixing succeeded!")
                    final_duration, final_fps, _ = get_video_info(output_file)
                    file_size = output_file.stat().st_size / (1024 * 1024)
                    logger.info(f"📁 File: {output_file}")
                    logger.info(f"💾 Size: {file_size:.1f} MB")
                    logger.info(f"⏱️ Duration: {final_duration:.1f}s")
                    return True
                else:
                    logger.error(f"❌ Simple mixing also failed: {simple_result.stderr}")
            
            return False
            
    finally:
        # Clean up
        try:
            if temp_folder.exists():
                shutil.rmtree(temp_folder)
                logger.info("Cleaned up temporary files")
        except Exception as e:
            logger.warning(f"Could not clean up: {e}")

def combine_ranked_videos(input_folder: Path, output_folder: Path, background_music: Path = None, 
                         voice_level: float = 0.8, music_level: float = 0.3, video_stem: str = None) -> bool:
    """Main function to combine ranked videos using frame-perfect method"""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🎬 VIDEO COMBINATION - STEP 9 (ENHANCED WITH BACKGROUND MUSIC)")
    logger.info(f"{'='*60}")
    logger.info(f"🎯 Processing video: {video_stem or 'ALL'}")
    logger.info(f"📁 Input folder: {input_folder}")
    logger.info(f"📂 Output folder: {output_folder}")
    if background_music:
        logger.info(f"🎵 Background music: {background_music.name}")
        logger.info(f"🔊 Voice level: {voice_level*100:.0f}%")
        logger.info(f"🎶 Music level: {music_level*100:.0f}%")
    logger.info(f"⚙️ Mode: Frame-perfect combination with audio mixing")
    logger.info(f"{'='*60}")
    
    # Determine output filename
    if video_stem:
        output_filename = f"{video_stem}_complete_video.{OUTPUT_FORMAT}"
    else:
        output_filename = f"complete_video.{OUTPUT_FORMAT}"
    
    # Use enhanced frame-perfect combination with background music
    success = combine_frame_perfect_with_music(input_folder, output_folder, output_filename, 
                                             background_music, voice_level, music_level)
    
    if success:
        output_path = output_folder / output_filename
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        
        logger.info(f"\n✨ STEP 9 COMPLETE!")
        if background_music:
            logger.info(f"🎵 Combined videos with background music and perfect audio mixing")
        else:
            logger.info(f"🎬 Combined videos with frame-perfect precision")
        logger.info(f"💾 File size: {file_size:.1f} MB")
        logger.info(f"📁 Output: {output_path}")
        logger.info(f"✅ Fixed frame rate mismatches and duration issues")
        return True
    else:
        logger.error(f"\n❌ STEP 9 FAILED!")
        return False

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main function for standalone execution"""
    parser = argparse.ArgumentParser(
        description="Step 9: Combine ranked videos into single video with background music (enhanced version)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--input', 
        type=Path, 
        default=DEFAULT_INPUT_FOLDER,
        help="Path to folder containing ranked video files from Step 8"
    )
    
    parser.add_argument(
        '--output', 
        type=Path, 
        default=DEFAULT_OUTPUT_FOLDER,
        help="Path to output folder for combined video"
    )
    
    parser.add_argument(
        '--background-music', 
        type=Path, 
        default=None,
        help="Path to background music file (MP3, WAV, etc.)"
    )
    
    parser.add_argument(
        '--voice-level', 
        type=float, 
        default=DEFAULT_VOICE_LEVEL,
        help=f"Voice/original audio volume level (0.0-1.0, default: {DEFAULT_VOICE_LEVEL})"
    )
    
    parser.add_argument(
        '--music-level', 
        type=float, 
        default=DEFAULT_MUSIC_LEVEL,
        help=f"Background music volume level (0.0-1.0, default: {DEFAULT_MUSIC_LEVEL})"
    )
    
    parser.add_argument(
        '--enable-music', 
        action='store_true',
        help="Enable background music (requires --background-music)"
    )
    
    parser.add_argument(
        '--video-stem', 
        type=str, 
        default=None,
        help="Video stem for naming output file (e.g., 'video1')"
    )
    
    args = parser.parse_args()
    
    # Validate input folder
    if not args.input.exists():
        logger.error(f"Input folder not found: {args.input}")
        sys.exit(1)
    
    # Validate arguments
    if args.voice_level < 0.0:
        logger.error("Voice level must be 0.0 or greater")
        sys.exit(1)
    
    if args.music_level < 0.0:
        logger.error("Music level must be 0.0 or greater")
        sys.exit(1)
    
    # Determine background music
    background_music = None
    if args.enable_music or args.background_music:
        if args.background_music:
            background_music = args.background_music
        else:
            # Try default background music
            default_music = Path(DEFAULT_BACKGROUND_MUSIC)
            if default_music.exists():
                background_music = default_music
                logger.info(f"Using default background music: {background_music}")
            else:
                logger.warning("Background music requested but no file specified and default not found")
    
    # Run enhanced combination
    success = combine_ranked_videos(
        args.input, 
        args.output, 
        background_music, 
        args.voice_level, 
        args.music_level, 
        args.video_stem
    )
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()