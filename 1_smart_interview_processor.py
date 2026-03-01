#!/usr/bin/env python3
"""
Smart Interview Processor & Script Creator - Step 1 (UPDATED V2)
====================================================
Analyzes interview videos, extracts best moments, and creates engaging YouTube scripts
with alternating interview/voiceover structure.

NEW in V2:
- Validates that script starts with INTERVIEW (not voiceover)
- Enhanced anti-repetition checking
- Better pacing validation (short early, longer later)
"""

# ==============================================================================
# 📁 INPUT/OUTPUT PATHS - EDIT THESE FOR QUICK TESTING
# ==============================================================================
DEFAULT_INTERVIEWS_FOLDER = ""
DEFAULT_BROLL_FOLDER = ""
DEFAULT_OUTPUT_FOLDER = ""
# ==============================================================================

import os
import sys
import json
import subprocess
import whisper
import google.generativeai as genai

try:
    import anthropic
except ImportError:
    anthropic = None
from pathlib import Path
import shutil
import time
import logging
from typing import List, Dict, Tuple
import re
from datetime import timedelta

# Import centralized settings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_creator
get_pipeline_settings = content_creator.get_pipeline_settings

try:
    import torch
except ImportError:
    torch = None

# ====== CONFIGURATION ======
# Load centralized settings from control-2.py
SETTINGS = get_pipeline_settings()
AI_PROVIDER_SETTINGS = SETTINGS['ai_provider']
GEMINI_SETTINGS = SETTINGS['gemini']
CLIP_EXTRACTION_SETTINGS = SETTINGS['clip_extraction']
VOICEOVER_SETTINGS = SETTINGS['voiceover']

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import FFmpeg helpers from app_utils
try:
    from app_utils import get_ffmpeg_path, get_ffprobe_path
except ImportError:
    # Fallback if app_utils not available
    def get_ffmpeg_path():
        return "ffmpeg"
    def get_ffprobe_path():
        return "ffprobe"


# ====== MAIN PROCESSOR CLASS ======
class SmartInterviewProcessor:
    def __init__(self, interviews_folder: Path, broll_folder: Path, output_folder: Path, api_key: str = None,
                 model_name: str = None, profile_info: dict = None):
        self.interviews_folder = Path(interviews_folder)
        self.broll_folder = Path(broll_folder)
        self.output_folder = Path(output_folder)
        self.profile_info = profile_info  # Store profile info for prompt selection

        # AI Provider configuration
        self.ai_provider = AI_PROVIDER_SETTINGS['provider']
        if self.ai_provider == "google":
            self.api_key = api_key or AI_PROVIDER_SETTINGS['gemini_api_key']
            self.model_name = model_name or AI_PROVIDER_SETTINGS['google_model']
        elif self.ai_provider == "claude":
            self.api_key = api_key or AI_PROVIDER_SETTINGS['claude_api_key']
            self.model_name = model_name or AI_PROVIDER_SETTINGS['claude_model']
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

        # Create output subdirectories directly in step 1 folder structure
        self.step_1_dir = self.output_folder / "1_processing"
        self.step_1_dir.mkdir(parents=True, exist_ok=True)

        self.transcripts_dir = self.step_1_dir / "transcripts"
        self.clips_dir = self.step_1_dir / "interview_clips"
        self.broll_clips_dir = self.step_1_dir / "broll_clips"
        self.script_dir = self.step_1_dir

        for dir in [self.transcripts_dir, self.clips_dir, self.broll_clips_dir, self.script_dir]:
            dir.mkdir(parents=True, exist_ok=True)

        # Initialize AI models
        self.init_models()

    def init_models(self):
        """Initialize Whisper and AI models"""
        logger.info(f"Loading AI models (Provider: {self.ai_provider})...")

        # Load Whisper
        device = "cuda" if CLIP_EXTRACTION_SETTINGS['use_gpu'] and torch and torch.cuda.is_available() else "cpu"
        self.whisper_model = whisper.load_model(CLIP_EXTRACTION_SETTINGS['whisper_model'], device=device)
        logger.info(f"✅ Whisper model loaded ({CLIP_EXTRACTION_SETTINGS['whisper_model']} on {device})")

        # Configure AI provider
        if self.ai_provider == "google":
            genai.configure(api_key=self.api_key)
            self.ai_model = genai.GenerativeModel(self.model_name)
            logger.info(f"✅ Google Gemini model configured ({self.model_name})")
        elif self.ai_provider == "claude":
            if anthropic is None:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
            logger.info(f"🔍 DEBUG - Using Claude API key: {self.api_key[:20]}...")
            logger.info(f"🔍 DEBUG - Using Claude model: {self.model_name}")
            self.ai_model = anthropic.Anthropic(api_key=self.api_key)
            logger.info(f"✅ Claude model configured ({self.model_name})")
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

    def find_interview_videos(self) -> List[Path]:
        """Find all video files in interviews folder"""
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        videos = []

        for ext in video_extensions:
            videos.extend(self.interviews_folder.glob(f"*{ext}"))

        videos.sort()
        logger.info(f"Found {len(videos)} interview videos")
        return videos

    def transcribe_video(self, video_path: Path) -> Dict:
        """Transcribe a single video using Whisper"""
        logger.info(f"Transcribing: {video_path.name}")

        # Extract audio if needed (Whisper works with audio)
        audio_path = self.transcripts_dir / f"{video_path.stem}_audio.wav"

        # Extract audio using ffmpeg
        ffmpeg = get_ffmpeg_path()
        logger.info(f"  FFmpeg path: {ffmpeg} (exists: {Path(ffmpeg).exists() if ffmpeg != 'ffmpeg' else 'system PATH'})")
        cmd = [
            ffmpeg, "-i", str(video_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(audio_path), "-y", "-loglevel", "quiet"
        ]
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            logger.error(f"  FFmpeg not found at: {ffmpeg}")
            raise

        # Transcribe with Whisper (thread-safe: redirect stdout/stderr to prevent I/O conflicts)
        import io
        import contextlib

        # Capture stdout/stderr to prevent "I/O operation on closed file" errors in parallel mode
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = self.whisper_model.transcribe(
                str(audio_path),
                task="transcribe",
                verbose=False
            )

        # Clean up audio file
        audio_path.unlink()

        # Add video info to result
        result['video_path'] = str(video_path)
        result['video_name'] = video_path.name
        result['duration'] = self.get_video_duration(video_path)

        # Save transcript
        transcript_file = self.transcripts_dir / f"{video_path.stem}_transcript.json"
        with open(transcript_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Transcribed: {video_path.name} ({len(result['segments'])} segments)")
        return result

    def get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds"""
        ffprobe = get_ffprobe_path()
        cmd = [
            ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])

    def analyze_and_create_script(self, transcripts: List[Dict]) -> Dict:
        """Send transcripts to AI for analysis and script creation"""
        logger.info("🤖 Analyzing interviews and creating script...")

        # Prepare transcript data for AI
        transcript_text = self.format_transcripts_for_ai(transcripts)

        # Build dynamic prompt based on centralized settings
        prompt = self._build_gemini_prompt(transcript_text)

        # Get AI response
        try:
            logger.info(f"📤 Sending request to {self.ai_provider.upper()} API (this may take 30-60 seconds)...")
            script_text = self._generate_ai_content(prompt)
            logger.info(f"✅ {self.ai_provider.upper()} response received successfully!")
            logger.info("✅ Script created successfully")

            # Parse the script to extract structure
            parsed_script = self.parse_script(script_text)

            # CRITICAL VALIDATION: Reject invalid scripts
            self._validate_script_requirements(parsed_script)

            return parsed_script

        except Exception as e:
            logger.error(f"❌ Error creating script: {e}")
            raise

    def _build_gemini_prompt(self, transcript_text: str) -> str:
        """Build dynamic AI prompt based on centralized settings and profile-specific prompt"""

        # Extract settings
        min_interviews = GEMINI_SETTINGS['min_interview_clips']
        max_interviews = GEMINI_SETTINGS['max_interview_clips']
        target_minutes = GEMINI_SETTINGS['total_target_minutes']
        min_clip_duration = GEMINI_SETTINGS['interview_length_min']
        max_clip_duration = GEMINI_SETTINGS['interview_length_max']

        # Determine which prompt file to use
        if self.profile_info and 'prompt_file' in self.profile_info:
            prompt_file = self.profile_info['prompt_file']
            logger.info(f"🎯 Using profile-specific prompt: {self.profile_info.get('name', 'Unknown')}")
        else:
            # Fallback to default prompt
            prompt_file = Path(__file__).parent / "prompts" / "script_generation_prompt.txt"
            logger.info(f"📄 Using default prompt (no profile specified)")

        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # Replace placeholders with actual values
            prompt = prompt_template.format(
                transcript_text=transcript_text,
                min_interviews=min_interviews,
                max_interviews=max_interviews,
                min_clip_duration=min_clip_duration,
                max_clip_duration=max_clip_duration,
                target_minutes=target_minutes
            )

            logger.info(f"✅ Loaded prompt template from: {prompt_file.name}")
            return prompt

        except FileNotFoundError:
            logger.error(f"❌ Prompt file not found: {prompt_file}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading prompt: {e}")
            raise

    def _generate_ai_content(self, prompt: str) -> str:
        """Generate content using the configured AI provider"""
        if self.ai_provider == "google":
            response = self.ai_model.generate_content(prompt)
            return response.text
        elif self.ai_provider == "claude":
            response = self.ai_model.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False
            )
            return response.content[0].text
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

    def _validate_script_requirements(self, parsed_script: Dict):
        """
        Validate that script meets ALL requirements:
        1. Minimum interview clips
        2. Script STARTS with INTERVIEW (not voiceover)
        3. Proper alternating pattern
        """

        interview_count = parsed_script.get('interview_count', 0)
        total_segments = parsed_script.get('total_segments', 0)
        segments = parsed_script.get('segments', [])
        min_required = GEMINI_SETTINGS['min_interview_clips']

        # Check 1: Minimum interview count
        if interview_count < min_required:
            error_msg = f"""
🚨 SCRIPT VALIDATION FAILED 🚨

REASON: Insufficient interview clips
- Required minimum: {min_required} interview clips
- Found: {interview_count} interview clips
- Total segments: {total_segments}

This appears to be a VOICEOVER-ONLY script, which is STRICTLY FORBIDDEN.

The script has been REJECTED. Please ensure AI follows the requirements:
1. Minimum {min_required} interview clips
2. Script MUST start with [INTERVIEW] clip
3. Alternating pattern: interview → voiceover → interview → voiceover
"""
            logger.error(error_msg)
            raise ValueError(
                f"Script validation failed: Only {interview_count} interview clips found, minimum {min_required} required")

        # Check 2: Script MUST start with INTERVIEW
        if len(segments) > 0 and segments[0]['type'] != 'interview':
            error_msg = f"""
🚨 SCRIPT VALIDATION FAILED 🚨

REASON: Script does NOT start with [INTERVIEW] clip
- First segment type: {segments[0]['type']}
- REQUIRED: First segment MUST be [INTERVIEW]

This violates the MANDATORY interview-first structure.

The script has been REJECTED. Script MUST start with:
[INTERVIEW: filename.mp4, timestamp-timestamp]

NOT with:
[VOICEOVER]
"""
            logger.error(error_msg)
            raise ValueError(
                f"Script validation failed: First segment is '{segments[0]['type']}' but MUST be 'interview'")

        # Check 3: No interview segments at all
        if len(segments) > 0:
            interview_segments = [s for s in segments if s['type'] == 'interview']
            if len(interview_segments) == 0:
                logger.error("🚨 NO INTERVIEW SEGMENTS FOUND - This is a voiceover-only script!")
                raise ValueError("Script validation failed: No interview segments found")

        logger.info(f"✅ Script validation passed:")
        logger.info(f"   - {interview_count} interview clips (minimum {min_required} required)")
        logger.info(f"   - First segment is INTERVIEW ✓")
        logger.info(f"   - Total segments: {total_segments}")

    def format_transcripts_for_ai(self, transcripts: List[Dict]) -> str:
        """Format transcripts for AI analysis"""
        formatted = []

        for transcript in transcripts:
            formatted.append(f"\n=== {transcript['video_name']} ===")
            formatted.append(f"Duration: {transcript['duration']:.1f} seconds\n")

            # Add timestamped segments
            for segment in transcript['segments']:
                timestamp = self.seconds_to_timestamp(segment['start'])
                text = segment['text'].strip()
                formatted.append(f"[{timestamp}] {text}")

        return '\n'.join(formatted)

    def seconds_to_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format"""
        return str(timedelta(seconds=int(seconds)))

    def timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert HH:MM:SS or MM:SS to seconds"""
        parts = timestamp.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(timestamp)

    def parse_script(self, script_text: str) -> Dict:
        """Parse the AI-generated script to extract structure"""
        segments = []

        # Split by markers
        parts = re.split(r'\[(VOICEOVER|INTERVIEW)[:\])]', script_text)

        i = 0
        while i < len(parts):
            part = parts[i].strip()

            if part == 'VOICEOVER' and i + 1 < len(parts):
                voiceover_text = parts[i + 1].strip()
                if voiceover_text:
                    # Clean voiceover text - remove any production notes
                    voiceover_text = self._clean_voiceover_text(voiceover_text)
                    segments.append({
                        'type': 'voiceover',
                        'text': voiceover_text
                    })
                i += 2

            elif part == 'INTERVIEW' and i + 1 < len(parts):
                interview_info = parts[i + 1].strip()

                # Parse interview info: filename, start-end
                match = re.search(r'([^,]+\.mp4)[,\s]+(\d{1,2}:\d{2}:?\d{0,2})-(\d{1,2}:\d{2}:?\d{0,2})',
                                  interview_info)
                if match:
                    filename = match.group(1).strip()
                    start_time = self.timestamp_to_seconds(match.group(2))
                    end_time = self.timestamp_to_seconds(match.group(3))

                    segments.append({
                        'type': 'interview',
                        'filename': filename,
                        'start': start_time,
                        'end': end_time,
                        'duration': end_time - start_time
                    })
                i += 2
            else:
                i += 1

        return {
            'segments': segments,
            'total_segments': len(segments),
            'voiceover_count': sum(1 for s in segments if s['type'] == 'voiceover'),
            'interview_count': sum(1 for s in segments if s['type'] == 'interview')
        }

    def _clean_voiceover_text(self, text: str) -> str:
        """
        Clean voiceover text by removing production notes, metadata, etc.
        Keep ONLY the speakable narration.
        """
        # Remove lines that start with production markers
        lines = text.split('\n')
        clean_lines = []

        for line in lines:
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # Skip lines that are production notes
            if line.startswith(('---', '###', '##', '**', '- ', '* ', '1.', '2.', '3.')):
                continue
            # Skip lines with parenthetical annotations
            if line.startswith('(') and line.endswith(')'):
                continue
            # Skip all-caps metadata lines
            if line.isupper() and len(line.split()) <= 5:
                continue
            # Keep this line
            clean_lines.append(line)

        return ' '.join(clean_lines)

    def extract_interview_clips(self, parsed_script: Dict):
        """Extract interview clips based on script"""
        logger.info("✂️ Extracting interview clips...")

        clip_count = 0
        for segment in parsed_script['segments']:
            if segment['type'] != 'interview':
                continue

            # Find the video file
            video_path = self.find_video_by_name(segment['filename'])
            if not video_path:
                logger.warning(f"⚠️ Video not found: {segment['filename']}")
                continue

            # Extract clip
            clip_name = f"clip_{clip_count:03d}_interview.mp4"
            output_path = self.clips_dir / clip_name

            duration = segment['end'] - segment['start']

            ffmpeg = get_ffmpeg_path()
            cmd = [
                ffmpeg,
                "-ss", str(segment['start']),
                "-i", str(video_path),
                "-t", str(duration),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-preset", "fast",
                "-crf", "23",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path),
                "-loglevel", "quiet"
            ]

            try:
                subprocess.run(cmd, check=True)
                logger.info(f"✅ Extracted: {clip_name} ({duration:.1f}s)")

                # Update segment with output path
                segment['output_path'] = str(output_path)
                clip_count += 1

            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to extract clip: {e}")

    def find_video_by_name(self, filename: str) -> Path:
        """Find video file by name in interviews folder"""
        # First try exact match
        exact_match = self.interviews_folder / filename
        if exact_match.exists():
            return exact_match

        # Try case-insensitive search
        for video in self.interviews_folder.iterdir():
            if video.name.lower() == filename.lower():
                return video

        # Try partial match - AI sometimes returns partial filename
        filename_lower = filename.lower()
        for video in self.interviews_folder.iterdir():
            video_name_lower = video.name.lower()
            # Check if the AI-returned filename is contained in the actual filename
            if filename_lower in video_name_lower or video_name_lower in filename_lower:
                logger.info(f"   📎 Partial match: '{filename}' → '{video.name}'")
                return video

        # Try matching without extension
        filename_stem = Path(filename).stem.lower()
        for video in self.interviews_folder.iterdir():
            video_stem = video.stem.lower()
            if filename_stem in video_stem or video_stem in filename_stem:
                logger.info(f"   📎 Stem match: '{filename}' → '{video.name}'")
                return video

        return None

    def create_readable_full_script(self, parsed_script: Dict):
        """Create human-readable version of full script"""
        logger.info("📄 Creating readable full script...")

        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append("COMPLETE VIDEO SCRIPT - READABLE VERSION")
        output_lines.append("=" * 80)
        output_lines.append("")
        output_lines.append("This is the FULL SCRIPT with interview clips and voiceover narration.")
        output_lines.append("Read this to review the complete video flow before it's produced.")
        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append("")

        # Add each segment
        for i, segment in enumerate(parsed_script['segments'], 1):
            if segment['type'] == 'interview':
                output_lines.append("")
                output_lines.append("🎤 " + "=" * 75)
                output_lines.append(f"   INTERVIEW CLIP #{i}")
                output_lines.append("=" * 78)
                output_lines.append(f"📹 File: {segment['filename']}")

                # Format timestamps
                start_ts = self.seconds_to_timestamp(segment['start'])
                end_ts = self.seconds_to_timestamp(segment['end'])
                output_lines.append(f"⏱️  Time: {start_ts} → {end_ts} ({segment['duration']:.1f}s)")
                output_lines.append("")

                # Get transcript text for this clip
                transcript_text = self._get_transcript_for_clip(segment)
                output_lines.append(transcript_text)
                output_lines.append("")
                output_lines.append("=" * 78)

            elif segment['type'] == 'voiceover':
                output_lines.append("")
                output_lines.append("")
                output_lines.append("🎙️  " + "=" * 75)
                output_lines.append(f"   VOICEOVER NARRATION #{i}")
                output_lines.append("=" * 78)
                output_lines.append("")
                output_lines.append(segment['text'])
                output_lines.append("")
                output_lines.append("=" * 78)

        # Add summary
        output_lines.append("")
        output_lines.append("")
        output_lines.append("---")
        output_lines.append("")
        output_lines.append("**SCRIPT COMPLETE**")

        total_duration = sum(s['duration'] for s in parsed_script['segments'] if s['type'] == 'interview')
        interview_count = parsed_script['interview_count']
        voiceover_count = parsed_script['voiceover_count']

        output_lines.append(
            f"**Total Interview Clips: {interview_count} | Total Duration: ~{int(total_duration / 60)} minutes**")
        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append("")

        # Statistics
        output_lines.append("")
        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append("📊 SCRIPT SUMMARY & STATISTICS")
        output_lines.append("=" * 80)
        output_lines.append("")
        output_lines.append(f"📌 Total Segments: {parsed_script['total_segments']}")
        output_lines.append(f"   • Interview Clips: {interview_count}")
        output_lines.append(f"   • Voiceover Sections: {voiceover_count}")
        output_lines.append("")
        output_lines.append("⏱️  Total Duration:")
        output_lines.append(f"   • Interview Clips: {total_duration:.1f}s ({total_duration / 60:.1f} min)")

        # Estimate voiceover duration (150 words per minute average speaking rate)
        total_vo_words = sum(len(s['text'].split()) for s in parsed_script['segments'] if s['type'] == 'voiceover')
        estimated_vo_duration = (total_vo_words / 150) * 60  # Convert to seconds

        output_lines.append(
            f"   • Estimated Voiceover: {estimated_vo_duration:.1f}s ({estimated_vo_duration / 60:.1f} min)")
        output_lines.append(f"   • TOTAL VIDEO LENGTH: ~{(total_duration + estimated_vo_duration) / 60:.1f} minutes")
        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append("")
        output_lines.append("✅ Review this script and provide feedback if needed!")

        # Write to file
        output_file = self.step_1_dir / "full_script_readable.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))

        logger.info(f"✅ Created readable script: {output_file}")

    def _get_transcript_for_clip(self, segment: Dict) -> str:
        """Get transcript text for a specific interview clip"""
        # Find the matching transcript
        for transcript in self.transcripts:
            if transcript['video_name'] == segment['filename']:
                # Extract text for this time range
                clip_text = []
                for seg in transcript['segments']:
                    if seg['start'] >= segment['start'] and seg['end'] <= segment['end']:
                        clip_text.append(seg['text'])
                return ' '.join(clip_text) if clip_text else "[Transcript not available]"

        return "[Transcript not available]"

    def create_final_outputs(self, parsed_script: Dict):
        """Create final output files for next pipeline step"""
        logger.info("📦 Creating final output files...")

        # 1. Create voiceover script (clean text for TTS)
        voiceover_parts = []
        for segment in parsed_script['segments']:
            if segment['type'] == 'voiceover':
                voiceover_parts.append(segment['text'])

        voiceover_script = '\n\n\n'.join(voiceover_parts)
        voiceover_file = self.step_1_dir / "voiceover_script.txt"
        with open(voiceover_file, 'w', encoding='utf-8') as f:
            f.write(voiceover_script)
        logger.info(f"✅ Created voiceover script: {voiceover_file}")

        # 2. Save clean script as JSON
        script_json = {
            'segments': parsed_script['segments'],
            'metadata': {
                'total_segments': parsed_script['total_segments'],
                'interview_count': parsed_script['interview_count'],
                'voiceover_count': parsed_script['voiceover_count'],
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }

        script_file = self.step_1_dir / "script_data.json"
        with open(script_file, 'w', encoding='utf-8') as f:
            json.dump(script_json, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Created script data: {script_file}")

        # 3. Create sequence map for assembly
        sequence_map = []
        for i, segment in enumerate(parsed_script['segments']):
            if segment['type'] == 'voiceover':
                sequence_map.append({
                    'index': i,
                    'type': 'voiceover',
                    'text_preview': segment['text'][:100] + '...'
                })
            else:
                sequence_map.append({
                    'index': i,
                    'type': 'interview',
                    'clip_path': segment.get('output_path', ''),
                    'duration': segment['duration']
                })

        sequence_file = self.step_1_dir / "sequence_map.json"
        with open(sequence_file, 'w', encoding='utf-8') as f:
            json.dump(sequence_map, f, indent=2)
        logger.info(f"✅ Created sequence map: {sequence_file}")

        logger.info(f"✅ B-roll clips location: {self.broll_clips_dir}")
        logger.info(f"✅ Interview videos location: {self.interviews_folder}")

    def generate_summary(self, parsed_script: Dict):
        """Generate summary statistics"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 PROCESSING SUMMARY")
        logger.info("=" * 60)

        total_interview_time = sum(
            s['duration'] for s in parsed_script['segments']
            if s['type'] == 'interview'
        )

        logger.info(f"✅ Total segments: {parsed_script['total_segments']}")
        logger.info(f"   - Voiceover sections: {parsed_script['voiceover_count']}")
        logger.info(f"   - Interview clips: {parsed_script['interview_count']}")
        logger.info(f"⏱️ Total interview footage: {total_interview_time:.1f} seconds")
        logger.info(f"📁 Output location: {self.step_1_dir}")
        logger.info("=" * 60)

    def copy_broll_clips(self):
        """Copy b-roll clips from source folder to output directory"""
        if not self.broll_folder.exists():
            logger.warning(f"⚠️ B-roll folder not found: {self.broll_folder}")
            return False

        # Find all video files in b-roll folder
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        broll_files = []
        for ext in video_extensions:
            broll_files.extend(self.broll_folder.glob(f"*{ext}"))

        if not broll_files:
            logger.warning(f"⚠️ No video files found in b-roll folder: {self.broll_folder}")
            return False

        logger.info(f"📁 Copying {len(broll_files)} b-roll clips...")
        copied_count = 0
        for broll_file in broll_files:
            dest_path = self.broll_clips_dir / broll_file.name
            try:
                shutil.copy2(str(broll_file), str(dest_path))
                copied_count += 1
                logger.info(f"   ✅ Copied: {broll_file.name}")
            except Exception as e:
                logger.error(f"   ❌ Failed to copy {broll_file.name}: {e}")

        if copied_count > 0:
            logger.info(f"✅ Copied {copied_count} b-roll clips to {self.broll_clips_dir}")
            return True
        else:
            logger.error("❌ Failed to copy any b-roll clips")
            return False

    def process(self):
        """Main processing pipeline"""
        logger.info("🚀 Starting Smart Interview Processing...")

        # 1. Find interview videos
        videos = self.find_interview_videos()
        if not videos:
            logger.error("❌ No interview videos found!")
            return False

        # 2. Transcribe all videos
        transcripts = []
        for video in videos:
            transcript = self.transcribe_video(video)
            transcripts.append(transcript)

        # Store transcripts for use in readable script generation
        self.transcripts = transcripts

        # 3. Analyze and create script
        parsed_script = self.analyze_and_create_script(transcripts)

        # 4. Extract interview clips
        self.extract_interview_clips(parsed_script)

        # 5. Copy b-roll clips
        self.copy_broll_clips()

        # 6. Create readable full script (for user review)
        self.create_readable_full_script(parsed_script)

        # 7. Create final outputs
        self.create_final_outputs(parsed_script)

        # 8. Generate summary
        self.generate_summary(parsed_script)

        # 9. Optional: Clean up transcript files to save space
        self.cleanup_transcripts()

        logger.info("\n✨ Processing complete! Ready for next pipeline steps.")
        return True

    def cleanup_transcripts(self):
        """Delete transcript JSON files after processing to save disk space"""
        try:
            transcript_files = list(self.transcripts_dir.glob("*_transcript.json"))
            if transcript_files:
                for transcript_file in transcript_files:
                    transcript_file.unlink()
                logger.info(
                    f"🗑️ Cleaned up {len(transcript_files)} transcript files (saved ~{len(transcript_files) * 2}MB)")
        except Exception as e:
            logger.warning(f"⚠️ Could not clean up transcripts: {e}")


# ====== MAIN EXECUTION ======
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Smart Interview Processor V2 - Analyzes interviews and creates engaging scripts"
    )

    parser.add_argument(
        "--interviews",
        type=str,
        default=DEFAULT_INTERVIEWS_FOLDER,
        help="Path to folder containing interview videos"
    )

    parser.add_argument(
        "--broll",
        type=str,
        default=DEFAULT_BROLL_FOLDER,
        help="Path to folder containing b-roll clips"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_FOLDER,
        help="Path to output folder"
    )

    # Dynamic defaults based on AI provider
    if AI_PROVIDER_SETTINGS['provider'] == 'google':
        default_api_key = AI_PROVIDER_SETTINGS['gemini_api_key']
        default_model = AI_PROVIDER_SETTINGS['google_model']
        help_text = "Google Gemini API key"
        model_help = "Google Gemini model name"
    else:  # Claude
        default_api_key = AI_PROVIDER_SETTINGS['claude_api_key']
        default_model = AI_PROVIDER_SETTINGS['claude_model']
        help_text = "Claude API key"
        model_help = "Claude model name"

    parser.add_argument(
        "--api-key",
        type=str,
        default=default_api_key,
        help=help_text
    )

    parser.add_argument(
        "--model",
        type=str,
        default=default_model,
        help=model_help
    )

    args = parser.parse_args()

    # Create processor and run
    processor = SmartInterviewProcessor(
        interviews_folder=args.interviews,
        broll_folder=args.broll,
        output_folder=args.output,
        api_key=args.api_key,
        model_name=args.model
    )

    try:
        success = processor.process()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()