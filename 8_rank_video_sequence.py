#!/usr/bin/env python3
# Fix Windows console encoding for emoji/unicode
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Step 7: Video Ranking & Sequence Organizer
==========================================

This script creates a ranked sequence of videos by alternating between:
- Interview clips (from 2_Interviews folder) 
- Voiceover videos (from 7_final_videos folder)

Output: Renamed files in pattern: interview → voiceover → interview → voiceover...
Saves to: 8_ranked_sequence folder

Usage:
- Standalone: python 7_rank_video_sequence.py --interviews <path> --voiceovers <path> --output <path>
- Orchestrator: Called automatically after Step 6
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from typing import List, Tuple
import json
import time
import subprocess

# Import app utilities for portable paths
try:
    import app_utils
    FFPROBE_PATH = app_utils.get_ffprobe_path()
except ImportError:
    FFPROBE_PATH = "ffprobe"

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default paths (used if not run by orchestrator)
DEFAULT_INTERVIEWS_FOLDER = ""
DEFAULT_VOICEOVERS_FOLDER = ""
DEFAULT_OUTPUT_FOLDER = ""

# Supported video extensions
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')

# Ranking settings
NUMBERING_FORMAT = "001"  # 001, 002, 003... format
INTERVIEW_PREFIX = "interview"
VOICEOVER_PREFIX = "voiceover"

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

def get_video_files(folder_path: Path, video_stem: str = None) -> List[Path]:
    """Get all video files from a folder and its subfolders, sorted by name"""
    if not folder_path.exists() or not folder_path.is_dir():
        logger.warning(f"Folder not found or not a directory: {folder_path}")
        return []
    
    video_files = []
    
    # First, check direct files in the folder
    for file_path in folder_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
            video_files.append(file_path)
            logger.info(f"📹 Found direct file: {file_path.name}")
    
    # Then, check subfolders (for numbered mode with multiple profiles)
    for subfolder in folder_path.iterdir():
        if subfolder.is_dir():
            logger.info(f"🔍 Checking subfolder: {subfolder.name}")
            for file_path in subfolder.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                    video_files.append(file_path)
                    logger.info(f"   📹 Found in subfolder: {file_path.name}")
    
    # Sort by filename for consistent ordering
    video_files.sort(key=lambda x: x.name.lower())
    logger.info(f"📊 Total found: {len(video_files)} videos in {folder_path}")
    return video_files

def get_video_duration(video_path: Path) -> float:
    """Get video duration using ffprobe (optional, for logging)"""
    try:
        cmd = [
            FFPROBE_PATH, '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def create_ranking_sequence(interview_files: List[Path], voiceover_files: List[Path]) -> List[Tuple[Path, str, str]]:
    """
    Create alternating sequence: interview → voiceover → interview → voiceover...
    
    Returns: List of (source_file, new_name, file_type) tuples
    """
    sequence = []
    counter = 1
    
    # Get the maximum number of files from either source
    max_files = max(len(interview_files), len(voiceover_files))
    
    logger.info(f"📊 Creating sequence from {len(interview_files)} interviews and {len(voiceover_files)} voiceovers")
    
    for i in range(max_files):
        # Add interview if available
        if i < len(interview_files):
            interview_file = interview_files[i]
            new_name = f"{counter:03d}_{INTERVIEW_PREFIX}{interview_file.suffix}"
            sequence.append((interview_file, new_name, "interview"))
            counter += 1
        
        # Add voiceover if available  
        if i < len(voiceover_files):
            voiceover_file = voiceover_files[i]
            new_name = f"{counter:03d}_{VOICEOVER_PREFIX}{voiceover_file.suffix}"
            sequence.append((voiceover_file, new_name, "voiceover"))
            counter += 1
    
    return sequence

def copy_and_rename_files(sequence: List[Tuple[Path, str, str]], output_folder: Path) -> bool:
    """Copy files to output folder with new names"""
    
    # Create output folder
    output_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Output folder: {output_folder}")
    
    success_count = 0
    total_duration = 0.0
    
    for source_file, new_name, file_type in sequence:
        try:
            destination = output_folder / new_name
            
            # Copy file
            shutil.copy2(source_file, destination)
            
            # Get duration for logging
            duration = get_video_duration(source_file)
            total_duration += duration
            
            logger.info(f"✅ {file_type.capitalize()}: {source_file.name} → {new_name} ({duration:.1f}s)")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to copy {source_file.name}: {e}")
            return False
    
    logger.info(f"\n🎉 RANKING COMPLETE!")
    logger.info(f"✅ Successfully ranked {success_count} videos")
    logger.info(f"⏱️ Total duration: {total_duration/60:.1f} minutes")
    logger.info(f"📁 Sequence saved to: {output_folder}")
    
    return True

def save_sequence_info(sequence: List[Tuple[Path, str, str]], output_folder: Path):
    """Save sequence information to JSON file for reference"""
    sequence_info = {
        "creation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(sequence),
        "sequence": []
    }
    
    for i, (source_file, new_name, file_type) in enumerate(sequence, 1):
        sequence_info["sequence"].append({
            "position": i,
            "new_name": new_name,
            "original_name": source_file.name,
            "original_path": str(source_file),
            "file_type": file_type,
            "duration_seconds": get_video_duration(source_file)
        })
    
    info_file = output_folder / "sequence_info.json"
    try:
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(sequence_info, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Sequence info saved: {info_file}")
    except Exception as e:
        logger.warning(f"⚠️ Could not save sequence info: {e}")

# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def rank_video_sequence(interviews_folder: Path, voiceovers_folder: Path, output_folder: Path, video_stem: str = None) -> bool:
    """Main function to rank and organize video sequence for a specific video"""
    
    # Extract video stem from folder path if not provided
    if video_stem is None:
        # Try to extract from parent folder name
        parent_folder = interviews_folder.parent
        video_stem = parent_folder.name
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🎬 VIDEO SEQUENCE RANKING - STEP 7")
    logger.info(f"{'='*60}")
    logger.info(f"🎯 Processing video: {video_stem}")
    logger.info(f"📁 Interviews folder: {interviews_folder}")
    logger.info(f"🎤 Voiceovers folder: {voiceovers_folder}")
    logger.info(f"📂 Output folder: {output_folder}")
    logger.info(f"{'='*60}")
    
    # Get video files from both sources - ONLY for this specific video
    interview_files = get_video_files(interviews_folder, video_stem)
    voiceover_files = get_video_files(voiceovers_folder, video_stem)
    
    if not interview_files and not voiceover_files:
        logger.error("❌ No video files found in either interviews or voiceovers folder!")
        return False
    
    if not interview_files:
        logger.warning("⚠️ No interview files found - will only rank voiceover files")
    
    if not voiceover_files:
        logger.warning("⚠️ No voiceover files found - will only rank interview files")
    
    # Display found files
    logger.info(f"\n📋 FOUND FILES:")
    logger.info(f"🎤 Interview files ({len(interview_files)}):")
    for i, file in enumerate(interview_files, 1):
        duration = get_video_duration(file)
        logger.info(f"   {i}. {file.name} ({duration:.1f}s)")
    
    logger.info(f"🎬 Voiceover files ({len(voiceover_files)}):")
    for i, file in enumerate(voiceover_files, 1):
        duration = get_video_duration(file)
        logger.info(f"   {i}. {file.name} ({duration:.1f}s)")
    
    # Create ranking sequence
    logger.info(f"\n🔄 Creating alternating sequence...")
    sequence = create_ranking_sequence(interview_files, voiceover_files)
    
    if not sequence:
        logger.error("❌ Failed to create sequence!")
        return False
    
    # Display sequence preview
    logger.info(f"\n📝 SEQUENCE PREVIEW:")
    for i, (source_file, new_name, file_type) in enumerate(sequence[:10], 1):  # Show first 10
        logger.info(f"   {i}. {new_name} ← {source_file.name} [{file_type}]")
    
    if len(sequence) > 10:
        logger.info(f"   ... and {len(sequence) - 10} more files")
    
    # Copy and rename files
    logger.info(f"\n📋 Copying and renaming files...")
    success = copy_and_rename_files(sequence, output_folder)
    
    if success:
        # Save sequence information
        save_sequence_info(sequence, output_folder)
        
        logger.info(f"\n✨ STEP 7 COMPLETE!")
        logger.info(f"🎯 Videos are now ranked in alternating sequence")
        logger.info(f"📁 Ready for manual editing: {output_folder}")
        return True
    else:
        logger.error(f"\n❌ STEP 7 FAILED!")
        return False

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main function for standalone execution"""
    parser = argparse.ArgumentParser(
        description="Step 7: Rank and organize video sequences in alternating pattern",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--interviews', 
        type=Path, 
        default=DEFAULT_INTERVIEWS_FOLDER,
        help="Path to folder containing interview video clips"
    )
    
    parser.add_argument(
        '--voiceovers', 
        type=Path, 
        default=DEFAULT_VOICEOVERS_FOLDER,
        help="Path to folder containing voiceover videos"
    )
    
    parser.add_argument(
        '--output', 
        type=Path, 
        default=DEFAULT_OUTPUT_FOLDER,
        help="Path to output folder for ranked sequence"
    )
    
    parser.add_argument(
        '--video-stem', 
        type=str, 
        default=None,
        help="Video stem to filter files for (e.g., 'video1' will only process files containing 'video1')"
    )
    
    parser.add_argument(
        '--preview-only', 
        action='store_true',
        help="Only show sequence preview without copying files"
    )
    
    args = parser.parse_args()
    
    # Validate input folders
    if not args.interviews.exists():
        logger.error(f"❌ Interviews folder not found: {args.interviews}")
        sys.exit(1)
    
    if not args.voiceovers.exists():
        logger.error(f"❌ Voiceovers folder not found: {args.voiceovers}")
        sys.exit(1)
    
    # Run ranking
    if args.preview_only:
        logger.info("🔍 PREVIEW MODE - No files will be copied")
        
        interview_files = get_video_files(args.interviews, args.video_stem)
        voiceover_files = get_video_files(args.voiceovers, args.video_stem)
        sequence = create_ranking_sequence(interview_files, voiceover_files)
        
        logger.info(f"\n📝 COMPLETE SEQUENCE PREVIEW:")
        for i, (source_file, new_name, file_type) in enumerate(sequence, 1):
            logger.info(f"   {i:03d}. {new_name} ← {source_file.name} [{file_type}]")
        
        logger.info(f"\n📊 Total files in sequence: {len(sequence)}")
        
    else:
        success = rank_video_sequence(args.interviews, args.voiceovers, args.output, args.video_stem)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()