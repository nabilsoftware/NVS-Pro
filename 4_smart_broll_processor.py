#!/usr/bin/env python3
"""
Smart B-roll Clip Generator - No Merging
=========================================
Creates 6-second clips from individual videos without merging.
Intelligently distributes clips across all input videos.
"""

import os
import sys
import subprocess
import random
import shutil
import logging
from pathlib import Path
import json
import math

# Configuration
DEFAULT_MAX_CLIPS = 100          # Total maximum clips to generate
DEFAULT_CLIPS_PER_VIDEO = 20     # Default clips per video if not limited
SEGMENT_TIME = 6                 # Clip duration in seconds
BITRATE = "5M"
USE_CUDA = True                  # Use CUDA acceleration if available
MIN_VIDEO_DURATION = 10          # Minimum video duration to process (seconds)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_video_duration(video_path):
    """Get duration of video in seconds"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except Exception as e:
        logger.error(f"Failed to get duration for {video_path}: {e}")
        return 0


def create_clips_from_video(video_path, output_dir, num_clips, segment_time=SEGMENT_TIME, use_cuda=USE_CUDA):
    """Create specified number of clips from a single video"""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    
    # Get video duration
    duration = get_video_duration(video_path)
    if duration < MIN_VIDEO_DURATION:
        logger.warning(f"⚠️ Video {video_path.name} too short ({duration:.1f}s), skipping")
        return []
    
    # Calculate how many clips we can actually create
    max_possible_clips = int(duration / segment_time)
    actual_clips = min(num_clips, max_possible_clips)
    
    if actual_clips < num_clips:
        logger.info(f"  Video can only produce {actual_clips} clips (requested {num_clips})")
    
    # Calculate interval between clips
    if actual_clips == max_possible_clips:
        # Create sequential clips
        interval = segment_time
        logger.info(f"  Creating {actual_clips} sequential clips")
    else:
        # Sample clips evenly throughout the video
        # Calculate spacing to distribute clips evenly
        usable_duration = duration - segment_time  # Account for last clip duration
        interval = usable_duration / actual_clips if actual_clips > 1 else 0
        logger.info(f"  Creating {actual_clips} sampled clips (interval: {interval:.1f}s)")
    
    created_clips = []
    
    for i in range(actual_clips):
        if interval == segment_time:
            # Sequential mode
            start_time = i * segment_time
        else:
            # Sampling mode - distribute evenly
            start_time = i * interval
        
        # Ensure we don't go past the video end
        if start_time + segment_time > duration:
            break
        
        # Generate unique clip name
        clip_name = f"{random.randint(10000, 99999)}{random.randint(10000, 99999)}.mp4"
        clip_path = output_dir / clip_name
        
        # Create the clip using ffmpeg
        clip_cmd = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(segment_time),
            "-c:v", "h264_nvenc" if use_cuda else "libx264",
            "-preset", "fast",
            "-b:v", BITRATE,
            "-an",  # No audio
            str(clip_path),
            "-y",
            "-loglevel", "error"
        ]
        
        if use_cuda:
            # Add CUDA acceleration flags
            clip_cmd.insert(1, "-hwaccel")
            clip_cmd.insert(2, "cuda")
        
        result = subprocess.run(clip_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            created_clips.append(clip_path)
            if (i + 1) % 10 == 0 or (i + 1) == actual_clips:
                logger.info(f"    Created {i + 1}/{actual_clips} clips from {video_path.name}")
        else:
            logger.error(f"    Failed to create clip at {start_time:.1f}s: {result.stderr}")
    
    return created_clips


def process_videos_smart(source_dir, output_dir, max_clips=DEFAULT_MAX_CLIPS, clips_per_video=None, segment_time=SEGMENT_TIME):
    """
    Process multiple videos individually without merging.
    Intelligently distributes clip count across videos.
    """
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find video files
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(source_dir.glob(f"*{ext}"))
    
    if not video_files:
        logger.error("❌ No video files found in source directory!")
        return False
    
    logger.info(f"📹 Found {len(video_files)} video files to process")
    logger.info(f"🎯 Target: {max_clips} total clips maximum")
    
    # Analyze all videos
    video_info = []
    total_duration = 0
    
    for video in video_files:
        duration = get_video_duration(video)
        if duration >= MIN_VIDEO_DURATION:
            video_info.append({
                'path': video,
                'duration': duration,
                'max_clips': int(duration / segment_time)
            })
            total_duration += duration
            logger.info(f"  {video.name}: {duration:.1f}s (max {int(duration/segment_time)} clips)")
        else:
            logger.warning(f"  {video.name}: {duration:.1f}s - TOO SHORT, skipping")
    
    if not video_info:
        logger.error("❌ No videos long enough to process!")
        return False
    
    # Calculate clip distribution
    logger.info(f"\n📊 Clip Distribution Strategy:")
    logger.info(f"  Total duration: {total_duration:.1f}s")
    logger.info(f"  Videos to process: {len(video_info)}")
    
    # Determine clips per video
    if clips_per_video:
        # Use specified clips per video
        clips_distribution = []
        remaining_clips = max_clips
        
        for info in video_info:
            video_clips = min(clips_per_video, info['max_clips'], remaining_clips)
            clips_distribution.append(video_clips)
            remaining_clips -= video_clips
            if remaining_clips <= 0:
                break
    else:
        # Distribute proportionally based on video duration
        clips_distribution = []
        remaining_clips = max_clips
        
        for info in video_info:
            # Calculate proportional share
            proportion = info['duration'] / total_duration
            target_clips = int(max_clips * proportion)
            
            # Ensure at least 1 clip per video, respect max possible clips
            video_clips = max(1, min(target_clips, info['max_clips'], remaining_clips))
            clips_distribution.append(video_clips)
            remaining_clips -= video_clips
            
            if remaining_clips <= 0:
                break
    
    # Display distribution plan
    total_planned_clips = sum(clips_distribution)
    logger.info(f"  Planned distribution: {total_planned_clips} clips total")
    for i, (info, num_clips) in enumerate(zip(video_info, clips_distribution)):
        if i < len(clips_distribution):
            logger.info(f"    {info['path'].name}: {num_clips} clips")
    
    # Process each video
    logger.info(f"\n🎬 Starting clip generation...")
    all_clips = []
    
    for info, num_clips in zip(video_info[:len(clips_distribution)], clips_distribution):
        if num_clips > 0:
            logger.info(f"\n📹 Processing: {info['path'].name}")
            clips = create_clips_from_video(info['path'], output_dir, num_clips, segment_time, USE_CUDA)
            all_clips.extend(clips)
            logger.info(f"  ✅ Generated {len(clips)} clips")
    
    # Final summary
    logger.info(f"\n" + "="*60)
    logger.info(f"🎉 PROCESSING COMPLETE!")
    logger.info(f"="*60)
    logger.info(f"✅ Total clips created: {len(all_clips)}")
    logger.info(f"📁 Output directory: {output_dir}")
    
    # Verify clips exist
    final_clips = list(output_dir.glob("*.mp4"))
    if len(final_clips) != len(all_clips):
        logger.warning(f"⚠️ Mismatch: Created {len(all_clips)} but found {len(final_clips)} in directory")
    
    return len(all_clips) > 0


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Smart B-roll clip generator - processes videos individually without merging"
    )
    parser.add_argument(
        "source", 
        help="Source directory with video files"
    )
    parser.add_argument(
        "output", 
        help="Output directory for clips"
    )
    parser.add_argument(
        "--max-clips", 
        type=int, 
        default=DEFAULT_MAX_CLIPS,
        help=f"Maximum total clips to create (default: {DEFAULT_MAX_CLIPS})"
    )
    parser.add_argument(
        "--clips-per-video", 
        type=int,
        help="Fixed number of clips per video (default: proportional distribution)"
    )
    parser.add_argument(
        "--no-cuda", 
        action="store_true",
        help="Disable CUDA acceleration"
    )
    parser.add_argument(
        "--segment-time",
        type=int,
        default=SEGMENT_TIME,
        help=f"Clip duration in seconds (default: {SEGMENT_TIME})"
    )
    
    args = parser.parse_args()
    
    global USE_CUDA
    if args.no_cuda:
        USE_CUDA = False
    
    # Use the segment_time from args directly instead of modifying global
    segment_time = args.segment_time if args.segment_time else SEGMENT_TIME
    
    # Process videos
    success = process_videos_smart(
        args.source, 
        args.output, 
        args.max_clips,
        args.clips_per_video,
        segment_time
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()