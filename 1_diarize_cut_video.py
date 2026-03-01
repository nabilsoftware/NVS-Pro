#!/usr/bin/env python3
"""
Optimized Speaker-Based Video Cutter - SIMPLIFIED VERSION
Takes EVERYTHING between voiceovers for complete interview coverage!

Features:
- Simple "take everything" logic - no over-filtering
- Full orchestrator integration with command-line arguments
- Optional Spleeter vocal isolation for better accuracy
- Stream copy (fast) or re-encode (compatible) modes
- GPU acceleration support (CUDA + NVENC)
"""

# =============================================================================
# DEFAULT CONFIGURATION
# =============================================================================
DEFAULT_INPUT_FOLDERS = [
    "",
]

# Default output directories (used if orchestrator doesn't provide paths)
BASE_OUTPUT_DIR_PRIMARY_CLIPS = ""
BASE_OUTPUT_DIR_INVERSE_CLIPS = ""

# Hugging Face token for pyannote.audio (loaded from cache if available)
HUGGINGFACE_TOKEN = ""  # Loaded from ~/.cache/huggingface/token via API Keys page

# Processing settings
MIN_VOICEOVER_DURATION = 2.0  # Minimum voiceover duration (seconds)
VOICEOVER_MERGE_GAP = 5.0  # Merge voiceovers within this gap (seconds)
MIN_INTERVIEW_GAP = 0.1  # Minimum interview gap to create clip (seconds)

AUDIO_SAMPLE_RATE = 16000  # Audio sample rate for extraction (16kHz is faster and pyannote works fine)
DEFAULT_USE_GPU = True
DEFAULT_RE_ENCODE = False  # False = fast stream copy, True = re-encode
DEFAULT_USE_SPLEETER = False

# =============================================================================

import os
import sys
import subprocess
import inspect
from pathlib import Path

# Fix PyArmor + speechbrain recursion: speechbrain's importutils calls
# inspect.getframeinfo() which infinitely recurses on PyArmor frozen frames.
# Patch inspect.getmodule to handle obfuscated/frozen filenames immediately
# instead of letting it recurse through getsourcefile -> getmodule -> repeat.
_original_getmodule = inspect.getmodule
_getmodule_active = False
def _safe_getmodule(obj, _filename=None):
    global _getmodule_active
    if _getmodule_active:
        return None
    _getmodule_active = True
    try:
        return _original_getmodule(obj, _filename)
    except (TypeError, RecursionError, ValueError):
        return None
    finally:
        _getmodule_active = False
inspect.getmodule = _safe_getmodule

import torch
# PyTorch 2.6+ compatibility fix - disable strict weights_only for trusted model files
import os
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'

# Also patch torch.load to use weights_only=False by default
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False  # Always force False for trusted models
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

import json
import time
import tempfile
from typing import List, Dict, Tuple, Optional
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing

# Get optimal number of workers for parallel processing
CPU_COUNT = multiprocessing.cpu_count()
MAX_PARALLEL_CUTS = min(CPU_COUNT, 8)  # Use up to 8 parallel FFmpeg processes
MAX_PARALLEL_VIDEOS = min(CPU_COUNT // 4, 3)  # Process up to 3 videos at once (each needs resources)

# Import app utilities for portable paths
try:
    import app_utils
    FFMPEG_PATH = app_utils.get_ffmpeg_path()
    FFPROBE_PATH = app_utils.get_ffprobe_path()
    HF_TOKEN_FROM_CACHE = app_utils.load_huggingface_token()
except ImportError:
    # Fallback if app_utils not available
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"
    HF_TOKEN_FROM_CACHE = None

# Direct fallback: Read HuggingFace token from cache file if not loaded
if not HF_TOKEN_FROM_CACHE:
    try:
        hf_token_path = Path.home() / ".cache" / "huggingface" / "token"
        if hf_token_path.exists():
            HF_TOKEN_FROM_CACHE = hf_token_path.read_text().strip()
    except Exception:
        pass

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check CUDA availability
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    logger.info(f"✓ GPU Available: {torch.cuda.get_device_name(0)}")
else:
    logger.info("ℹ️ Using CPU (GPU not available)")

# Check dependencies
try:
    from pyannote.audio import Pipeline
except ImportError:
    logger.error("❌ pyannote.audio not installed. Run: pip install pyannote.audio")
    sys.exit(1)

# Check FFmpeg capabilities
ffmpeg_capabilities = {'nvenc_available': False, 'cuda_decoder_available': False}

def check_ffmpeg_capabilities():
    """Check FFmpeg for NVENC and CUDA support"""
    try:
        result = subprocess.run([FFMPEG_PATH, '-encoders'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        ffmpeg_capabilities['nvenc_available'] = 'h264_nvenc' in result.stdout

        result = subprocess.run([FFMPEG_PATH, '-decoders'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        ffmpeg_capabilities['cuda_decoder_available'] = 'h264_cuvid' in result.stdout or 'hevc_cuvid' in result.stdout

        if ffmpeg_capabilities['nvenc_available']:
            logger.info("✓ FFmpeg NVENC encoder available")
        if ffmpeg_capabilities['cuda_decoder_available']:
            logger.info("✓ FFmpeg CUDA decoder available")
    except Exception as e:
        logger.warning(f"⚠️ Could not check FFmpeg capabilities: {e}")

check_ffmpeg_capabilities()

logger.info(f"✓ Parallel processing: {MAX_PARALLEL_CUTS} cuts, {MAX_PARALLEL_VIDEOS} videos")

# Check Spleeter availability
spleeter_available = False
try:
    result = subprocess.run(['spleeter', '--help'], capture_output=True, timeout=5)
    spleeter_available = result.returncode == 0
    if spleeter_available:
        logger.info("✓ Spleeter available")
except:
    logger.info("ℹ️ Spleeter not available (optional)")


# =============================================================================
# VIDEO PROCESSOR CLASS
# =============================================================================

class SimplifiedVideoProcessor:
    """Simplified video processor that takes EVERYTHING between voiceovers"""

    def __init__(self, hf_token: str, use_gpu: bool = True, re_encode: bool = False, use_spleeter: bool = False):
        self.hf_token = hf_token
        self.use_gpu = use_gpu
        self.re_encode = re_encode
        self.use_spleeter = use_spleeter and spleeter_available
        self.pipeline = None
        self.device = device if use_gpu else torch.device("cpu")

    def load_diarization_model(self):
        """Load pyannote diarization model"""
        if self.pipeline:
            return

        try:
            logger.info("🔄 Loading pyannote diarization model...")
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=self.hf_token
            )
            if self.use_gpu and torch.cuda.is_available():
                self.pipeline.to(self.device)
            logger.info("✓ Diarization model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load diarization model: {e}")
            logger.error("   Make sure you have accepted the user agreement at:")
            logger.error("   https://huggingface.co/pyannote/speaker-diarization-3.1")
            raise

    def extract_audio(self, video_path: Path, output_path: Path) -> bool:
        """Extract audio from video - with GPU acceleration if available"""
        try:
            cmd = [FFMPEG_PATH]
            # Use GPU decoding for faster video reading
            if ffmpeg_capabilities['cuda_decoder_available'] and self.use_gpu:
                cmd.extend(['-hwaccel', 'cuda'])
            cmd.extend([
                '-i', str(video_path),
                '-vn', '-acodec', 'pcm_s16le',
                '-ar', str(AUDIO_SAMPLE_RATE),
                '-ac', '1',
                str(output_path),
                '-y', '-loglevel', 'error'
            ])
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to extract audio: {e}")
            return False

    def run_spleeter_separation(self, audio_path: Path, temp_dir: Path) -> Optional[Path]:
        """Separate vocals using Spleeter"""
        if not self.use_spleeter:
            return None

        try:
            logger.info("🎵 Running Spleeter vocal separation...")
            output_dir = temp_dir / "spleeter_output"

            cmd = [
                'spleeter', 'separate',
                '-p', 'spleeter:2stems',
                '-o', str(output_dir),
                str(audio_path)
            ]

            subprocess.run(cmd, check=True, capture_output=True, timeout=300)

            # Find separated vocals
            vocals_path = output_dir / audio_path.stem / "vocals.wav"
            if vocals_path.exists():
                logger.info("✓ Spleeter separation successful")
                return vocals_path
            else:
                logger.warning("⚠️ Spleeter output not found, using original audio")
                return None
        except Exception as e:
            logger.warning(f"⚠️ Spleeter separation failed: {e}")
            return None

    def get_duration(self, file_path: Path) -> float:
        """Get media file duration"""
        try:
            cmd = [
                FFPROBE_PATH, '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json', str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(json.loads(result.stdout)['format']['duration'])
        except Exception as e:
            logger.error(f"❌ Failed to get duration: {e}")
            return 0.0

    def find_voiceover_segments(self, diarization) -> Tuple[List[Dict], str, List[Dict]]:
        """Find and merge voiceover segments with smart adaptive merging"""
        # Collect all speaker segments
        speaker_times = {}
        all_segments = []

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segment = {
                'start': turn.start,
                'end': turn.end,
                'duration': turn.end - turn.start,
                'speaker': speaker
            }
            all_segments.append(segment)

            if speaker not in speaker_times:
                speaker_times[speaker] = 0
            speaker_times[speaker] += segment['duration']

        if not speaker_times:
            return [], None, []

        # Primary speaker = most speaking time (narrator/voiceover)
        primary_speaker = max(speaker_times, key=speaker_times.get)
        logger.info(f"🎯 Primary speaker (voiceover): {primary_speaker} ({speaker_times[primary_speaker]:.1f}s total)")

        # Get only primary speaker segments
        voiceover_raw = [s for s in all_segments if s['speaker'] == primary_speaker]
        voiceover_raw.sort(key=lambda x: x['start'])

        # DEBUG: Show all primary speaker raw segments
        logger.info(f"📋 Raw primary speaker segments found: {len(voiceover_raw)}")
        for i, seg in enumerate(voiceover_raw[-3:] if len(voiceover_raw) > 3 else voiceover_raw):
            logger.info(f"   Segment {i}: {seg['start']:.1f}s - {seg['end']:.1f}s ({seg['duration']:.1f}s)")

        # DEBUG: Check what's happening at the start of the video
        logger.info(f"🔍 Analyzing start of video (first 30 seconds):")
        for seg in all_segments:
            if seg['start'] < 30:  # First 30 seconds
                speaker_type = "PRIMARY" if seg['speaker'] == primary_speaker else f"OTHER ({seg['speaker']})"
                logger.info(f"   {speaker_type}: {seg['start']:.1f}s - {seg['end']:.1f}s ({seg['duration']:.1f}s)")

        # IMPROVED: Adaptive merging with smarter gap handling AND orphan tracking
        voiceover_segments = []
        orphaned_voiceovers = []  # Track segments that didn't merge
        current = None
        merged_indices = set()  # Track which raw segments got merged

        for i, seg in enumerate(voiceover_raw):
            if current is None:
                current = seg.copy()
                current['_indices'] = [i]  # Track source segments
            else:
                gap = seg['start'] - current['end']

                # Adaptive merging logic
                should_merge = False

                if gap <= 2.0:
                    # Small gap: Always merge (natural pauses)
                    should_merge = True
                elif gap <= VOICEOVER_MERGE_GAP:
                    # Medium gap: Merge if next segment is substantial
                    if seg['duration'] >= 30:  # 30+ seconds = likely continuation
                        should_merge = True
                        logger.info(f"  📎 Merging across {gap:.1f}s gap (next segment is {seg['duration']:.1f}s)")
                elif gap <= 10.0:
                    # Large gap: Only merge if next segment is very long (likely missed voiceover)
                    if seg['duration'] >= 120:  # 2+ minutes = definitely continuation
                        should_merge = True
                        logger.info(f"  📎 Merging across {gap:.1f}s gap (long segment detected: {seg['duration']:.1f}s)")
                elif gap <= 15.0:
                    # Extra large gap: STILL merge if it's a VERY long segment at the END
                    if seg['duration'] >= 180 and i == len(voiceover_raw) - 1:  # 3+ minutes at end
                        should_merge = True
                        logger.info(f"  📎 SPECIAL: Merging end segment across {gap:.1f}s gap ({seg['duration']:.1f}s voiceover)")

                if should_merge:
                    # Merge with current segment
                    current['end'] = seg['end']
                    current['duration'] = current['end'] - current['start']
                    current['_indices'].append(i)
                else:
                    # Save current and start new
                    if current['duration'] >= MIN_VOICEOVER_DURATION:
                        voiceover_segments.append(current)
                        merged_indices.update(current['_indices'])
                    else:
                        # Too short - becomes orphaned
                        for idx in current['_indices']:
                            if voiceover_raw[idx]['duration'] >= MIN_VOICEOVER_DURATION:
                                orphaned_voiceovers.append(voiceover_raw[idx])
                                logger.info(f"  ⚠️ Orphaned short segment: {voiceover_raw[idx]['duration']:.1f}s at {voiceover_raw[idx]['start']:.1f}s")
                    current = seg.copy()
                    current['_indices'] = [i]

        # Don't forget last segment
        if current:
            if current['duration'] >= MIN_VOICEOVER_DURATION:
                voiceover_segments.append(current)
                merged_indices.update(current['_indices'])
            else:
                # Last segment too short - check original segments
                for idx in current['_indices']:
                    if voiceover_raw[idx]['duration'] >= MIN_VOICEOVER_DURATION:
                        orphaned_voiceovers.append(voiceover_raw[idx])
                        logger.info(f"  ⚠️ Orphaned end segment: {voiceover_raw[idx]['duration']:.1f}s at {voiceover_raw[idx]['start']:.1f}s")

        # Check for any segments that got completely missed
        for i, seg in enumerate(voiceover_raw):
            if i not in merged_indices and seg['duration'] >= MIN_VOICEOVER_DURATION:
                # This segment wasn't included in any merge
                orphaned_voiceovers.append(seg)
                logger.info(f"  🔍 Found completely orphaned segment: {seg['duration']:.1f}s at {seg['start']:.1f}s")

        logger.info(f"✓ Found {len(voiceover_segments)} voiceover segments after adaptive merging")

        # Add orphaned segments back
        if orphaned_voiceovers:
            logger.info(f"🔧 Adding {len(orphaned_voiceovers)} orphaned voiceover segments back")
            voiceover_segments.extend(orphaned_voiceovers)
            # Re-sort by start time
            voiceover_segments.sort(key=lambda x: x['start'])
            logger.info(f"✅ Total voiceover segments: {len(voiceover_segments)}")

        # DEBUG: Show final voiceover segments
        if voiceover_segments:
            logger.info(f"📋 Final voiceover segments (including recovered):")
            for i, seg in enumerate(voiceover_segments[-3:] if len(voiceover_segments) > 3 else voiceover_segments):
                logger.info(f"   Voiceover {i+1}: {seg['start']:.1f}s - {seg['end']:.1f}s ({seg['duration']:.1f}s)")

        return voiceover_segments, primary_speaker, all_segments

    def calculate_interview_segments(self, voiceover_segments: List[Dict], total_duration: float) -> List[Dict]:
        """Calculate interview segments as gaps between voiceovers"""
        interview_segments = []

        if not voiceover_segments:
            return interview_segments

        # Before first voiceover
        first_voiceover_start = voiceover_segments[0]['start']
        logger.info(f"  🔍 First voiceover starts at: {first_voiceover_start:.1f}s")

        if first_voiceover_start > 1.0:
            interview_segments.append({
                'start': 0,
                'end': first_voiceover_start,
                'duration': first_voiceover_start
            })
            logger.info(f"  ✓ Added interview segment at start: 0.0s - {first_voiceover_start:.1f}s")
        else:
            logger.info(f"  ⚠️ No interview at start (first voiceover at {first_voiceover_start:.1f}s < 1.0s threshold)")

        # Between voiceovers - TAKE EVERYTHING!
        for i in range(len(voiceover_segments) - 1):
            start = voiceover_segments[i]['end']
            end = voiceover_segments[i + 1]['start']
            duration = end - start

            # Only skip if basically nothing (0.1s threshold)
            if duration > MIN_INTERVIEW_GAP:
                interview_segments.append({
                    'start': start,
                    'end': end,
                    'duration': duration
                })

        # After last voiceover - simple check
        last_end = voiceover_segments[-1]['end']
        remaining_duration = total_duration - last_end

        if remaining_duration > 1.0:
            # Since we already handled all voiceover segments properly,
            # anything left at the end is truly interview/other content
            interview_segments.append({
                'start': last_end,
                'end': total_duration,
                'duration': remaining_duration
            })
            logger.info(f"  ✓ Added ending segment to interviews ({remaining_duration:.1f}s after last voiceover)")

        logger.info(f"✓ Found {len(interview_segments)} interview segments (gaps between voiceovers)")
        return interview_segments

    def _cut_single_segment(self, args: Tuple) -> Tuple[int, bool, str]:
        """Cut a single segment - used for parallel processing"""
        video_path, seg, output_file, clip_type, idx, total, re_encode, use_gpu = args
        cut_success = False

        # Try stream copy first (fast), fallback to re-encode if needed
        if not re_encode:
            # Use GPU decoding if available for faster seeking
            cmd = [FFMPEG_PATH]
            if ffmpeg_capabilities['cuda_decoder_available'] and use_gpu:
                cmd.extend(['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])
            cmd.extend([
                '-ss', str(seg['start']),  # Seek BEFORE input for speed
                '-i', str(video_path),
                '-t', str(seg['end'] - seg['start']),  # Duration instead of -to
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                str(output_file), '-y', '-loglevel', 'error'
            ])
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                # Verify the output has video stream
                probe_cmd = [FFPROBE_PATH, '-v', 'error', '-select_streams', 'v',
                            '-show_entries', 'stream=codec_type', '-of', 'json', str(output_file)]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                if '"codec_type": "video"' in probe_result.stdout or 'codec_type' in probe_result.stdout:
                    cut_success = True
            except Exception:
                pass  # Will try re-encode

        # Re-encode (either requested or fallback)
        if not cut_success:
            cmd = [FFMPEG_PATH]
            # Use GPU decoding if available
            if ffmpeg_capabilities['cuda_decoder_available'] and use_gpu:
                cmd.extend(['-hwaccel', 'cuda'])
            cmd.extend([
                '-ss', str(seg['start']),
                '-i', str(video_path),
                '-t', str(seg['end'] - seg['start']),
            ])
            # Video encoding with GPU if available
            if ffmpeg_capabilities['nvenc_available'] and use_gpu:
                cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'fast', '-b:v', '5M'])
            else:
                cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '18'])
            # Audio encoding
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
            cmd.extend([str(output_file), '-y', '-loglevel', 'error'])

            try:
                subprocess.run(cmd, check=True, capture_output=True)
                cut_success = True
            except Exception as e:
                return (idx, False, f"❌ Failed: {e}")

        if cut_success:
            return (idx, True, f"✓ {clip_type.capitalize()} {idx+1}/{total}: {seg['duration']:.1f}s")
        return (idx, False, f"❌ Failed: unknown error")

    def cut_video_segments(self, video_path: Path, segments: List[Dict], output_dir: Path,
                          clip_type: str, video_name: str) -> int:
        """Cut video into segments - PARALLEL VERSION"""
        output_dir.mkdir(parents=True, exist_ok=True)

        if not segments:
            return 0

        # Prepare arguments for parallel processing
        cut_args = []
        for i, seg in enumerate(segments):
            output_file = output_dir / f"{video_name}_{clip_type}_{i+1:03d}.mp4"
            cut_args.append((
                video_path, seg, output_file, clip_type, i, len(segments),
                self.re_encode, self.use_gpu
            ))

        success_count = 0

        # Use ThreadPoolExecutor for parallel FFmpeg execution
        # FFmpeg is I/O bound so threads work well
        logger.info(f"  🚀 Cutting {len(segments)} clips in parallel (up to {MAX_PARALLEL_CUTS} at once)...")

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_CUTS) as executor:
            futures = {executor.submit(self._cut_single_segment, args): args[4] for args in cut_args}

            for future in as_completed(futures):
                idx, success, msg = future.result()
                if success:
                    success_count += 1
                logger.info(f"  {msg}")

        return success_count

    def process_video(self, video_path: Path, output_primary_dir: Path,
                     output_inverse_dir: Path, output_logs_dir: Path) -> bool:
        """Main processing pipeline"""

        video_name = video_path.stem
        logger.info(f"\n{'=' * 80}")
        logger.info(f"🎬 Processing: {video_name}")
        logger.info(f"{'=' * 80}")

        start_time = time.time()

        # Load model
        self.load_diarization_model()

        with tempfile.TemporaryDirectory(prefix="video_cut_") as temp_dir:
            temp_path = Path(temp_dir)

            # Step 1: Extract audio
            logger.info("📀 Step 1/5: Extracting audio...")
            audio_path = temp_path / f"{video_name}_audio.wav"
            if not self.extract_audio(video_path, audio_path):
                return False

            video_duration = self.get_duration(video_path)
            logger.info(f"  ✓ Audio extracted ({video_duration:.1f}s)")

            # Step 2: Optional Spleeter separation
            audio_for_diarization = audio_path
            if self.use_spleeter:
                logger.info("📀 Step 2/5: Separating vocals with Spleeter...")
                vocals_path = self.run_spleeter_separation(audio_path, temp_path)
                if vocals_path:
                    audio_for_diarization = vocals_path
            else:
                logger.info("📀 Step 2/5: Skipping Spleeter (disabled)")

            # Step 3: Diarization
            logger.info("📀 Step 3/5: Running speaker diarization...")
            diarization_result = self.pipeline(str(audio_for_diarization))
            # pyannote-audio 4.0+ returns DiarizeOutput, extract the Annotation
            if hasattr(diarization_result, 'speaker_diarization'):
                diarization = diarization_result.speaker_diarization
            else:
                diarization = diarization_result

            # Step 4: Find segments
            logger.info("📀 Step 4/5: Analyzing segments...")
            voiceover_segments, primary_speaker, all_segments = self.find_voiceover_segments(diarization)

            if not voiceover_segments:
                logger.error("❌ No voiceover segments found!")
                return False

            interview_segments = self.calculate_interview_segments(voiceover_segments, video_duration)

            # Step 5: Cut videos
            logger.info("📀 Step 5/5: Cutting video segments...")
            logger.info(f"  🎤 Cutting {len(voiceover_segments)} voiceover clips...")
            voiceover_count = self.cut_video_segments(
                video_path, voiceover_segments, output_primary_dir, "voiceover", video_name
            )

            logger.info(f"  🎥 Cutting {len(interview_segments)} interview clips...")
            interview_count = self.cut_video_segments(
                video_path, interview_segments, output_inverse_dir, "interview", video_name
            )

            # Save processing info
            processing_time = time.time() - start_time

            output_logs_dir.mkdir(parents=True, exist_ok=True)
            info_file = output_logs_dir / "processing_info.json"

            processing_info = {
                'video_processed': str(video_path),
                'video_name': video_name,
                'total_duration': video_duration,
                'total_clips_created': voiceover_count + interview_count,
                'voiceover_clips': voiceover_count,
                'interview_clips': interview_count,
                'total_processing_time_seconds': round(processing_time, 2),
                'processing_method': 'simplified_take_everything_between_voiceovers',
                'configuration_settings': {
                    'use_gpu': self.use_gpu,
                    'device': str(self.device),
                    're_encode': self.re_encode,
                    'use_spleeter': self.use_spleeter,
                    'min_voiceover_duration': MIN_VOICEOVER_DURATION,
                    'voiceover_merge_gap': VOICEOVER_MERGE_GAP,
                    'min_interview_gap': MIN_INTERVIEW_GAP,
                    'final_output_primary_clip_path': str(output_primary_dir),
                    'final_output_inverse_clip_path': str(output_inverse_dir),
                },
                'clip_creation_distribution': {
                    str(output_primary_dir): voiceover_count,
                    str(output_inverse_dir): interview_count
                }
            }

            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(processing_info, f, indent=2, ensure_ascii=False)

            logger.info(f"\n{'=' * 80}")
            logger.info(f"✅ COMPLETE: {video_name}")
            logger.info(f"  📊 Voiceover clips: {voiceover_count} → {output_primary_dir}")
            logger.info(f"  📊 Interview clips: {interview_count} → {output_inverse_dir}")
            logger.info(f"  ⏱️  Processing time: {processing_time:.2f}s")
            logger.info(f"  📝 Logs saved: {info_file}")
            logger.info(f"{'=' * 80}\n")

            return True


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Simplified Speaker-Based Video Cutter - Takes EVERYTHING between voiceovers',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Input
    parser.add_argument('input', nargs='?', default=None,
                       help='Input video file or folder path')

    # Output paths (for orchestrator integration)
    parser.add_argument('--output-primary-clips-final', type=str, default=None,
                       help='Output directory for voiceover/primary clips')
    parser.add_argument('--output-inverse-clips-final', type=str, default=None,
                       help='Output directory for interview/inverse clips')
    parser.add_argument('--output-logs-final', type=str, default=None,
                       help='Output directory for processing logs')

    # Processing options
    parser.add_argument('--re-encode', action='store_true', default=DEFAULT_RE_ENCODE,
                       help='Re-encode video (slower but more compatible)')
    parser.add_argument('--no-re-encode', action='store_true',
                       help='Use stream copy (faster, default)')
    parser.add_argument('--use-spleeter', action='store_true', default=DEFAULT_USE_SPLEETER,
                       help='Use Spleeter for vocal isolation')
    parser.add_argument('--no-spleeter', action='store_true',
                       help='Disable Spleeter (default)')
    parser.add_argument('--cpu', action='store_true',
                       help='Force CPU processing (disable GPU)')

    # HuggingFace token - prefer token from cache (set via UI), fallback to hardcoded default
    parser.add_argument('--token', type=str, default=HF_TOKEN_FROM_CACHE or HUGGINGFACE_TOKEN,
                       help='HuggingFace authentication token')

    args = parser.parse_args()

    # Determine settings
    use_gpu = not args.cpu and torch.cuda.is_available()
    re_encode = args.re_encode or not args.no_re_encode if args.re_encode or args.no_re_encode else DEFAULT_RE_ENCODE
    use_spleeter = args.use_spleeter or not args.no_spleeter if args.use_spleeter or args.no_spleeter else DEFAULT_USE_SPLEETER

    # Get input path
    if args.input:
        input_path = Path(args.input)
    elif DEFAULT_INPUT_FOLDERS:
        input_path = Path(DEFAULT_INPUT_FOLDERS[0])
    else:
        logger.error("❌ No input specified!")
        return 1

    if not input_path.exists():
        logger.error(f"❌ Input not found: {input_path}")
        return 1

    # Initialize processor
    processor = SimplifiedVideoProcessor(
        hf_token=args.token,
        use_gpu=use_gpu,
        re_encode=re_encode,
        use_spleeter=use_spleeter
    )

    # Process videos
    if input_path.is_file():
        # Single video
        video_name = input_path.stem
        output_primary = Path(args.output_primary_clips_final or BASE_OUTPUT_DIR_PRIMARY_CLIPS)
        output_inverse = Path(args.output_inverse_clips_final or BASE_OUTPUT_DIR_INVERSE_CLIPS)
        output_logs = Path(args.output_logs_final or f"{video_name}_logs")

        success = processor.process_video(input_path, output_primary, output_inverse, output_logs)
        return 0 if success else 1

    elif input_path.is_dir():
        # Folder of videos
        videos = list(input_path.glob('*.mp4')) + list(input_path.glob('*.mkv')) + list(input_path.glob('*.avi'))

        if not videos:
            logger.error(f"❌ No video files found in: {input_path}")
            return 1

        logger.info(f"📁 Found {len(videos)} video(s) to process\n")

        success_count = 0
        for video in videos:
            try:
                video_name = video.stem
                output_primary = Path(args.output_primary_clips_final or BASE_OUTPUT_DIR_PRIMARY_CLIPS) / video_name
                output_inverse = Path(args.output_inverse_clips_final or BASE_OUTPUT_DIR_INVERSE_CLIPS) / video_name
                output_logs = Path(args.output_logs_final or f"{video_name}_logs")

                if processor.process_video(video, output_primary, output_inverse, output_logs):
                    success_count += 1
            except Exception as e:
                logger.error(f"❌ Error processing {video.name}: {e}")

        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ Completed: {success_count}/{len(videos)} videos processed successfully")
        logger.info(f"{'=' * 80}")

        return 0 if success_count > 0 else 1

    else:
        logger.error(f"❌ Invalid input: {input_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
