#!/usr/bin/env python3
"""
GPU-ACCELERATED Version: Style Interview Clips
- DEFAULT: Manual interactive cropping (GUI) for precise control
- Optional: AI auto-cropping with --auto-crop flag
- GPU-accelerated encoding (h264_nvenc) with CPU fallback
- Handles 9:16 cropping properly (removes white frames)
- 3-5x faster processing with NVIDIA GPU acceleration
- Automatic fallback to CPU if GPU unavailablewwwwwwwww
"""

# ===== EASY CONFIGURATION - EDIT THESE SETTINGS =====

# PATHS - Edit these for your setup
INPUT_FOLDER = ""  # Set by orchestrator via CLI args
BACKGROUND_PATH = ""  # Set by orchestrator via CLI args
OUTPUT_DIR = None  # Auto-creates INPUT_FOLDER/output if None

# OUTPUT SETTINGS
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
OUTPUT_FPS = 30

# PERFORMANCE SETTINGS
MAX_PARALLEL_VIDEOS = 1  # Process 1 video at a time for stability
USE_FAST_PRESET = True  # Use faster encoding preset

# GPU ACCELERATION SETTINGS
ENABLE_GPU_ENCODING = True  # Use NVIDIA GPU (h264_nvenc) for faster encoding
GPU_PRESET = 'p4'  # NVENC preset: p1 (slow/quality) to p7 (fast)
GPU_CQ = 18  # Quality for GPU (lower = better, 18-23 recommended)
CPU_FALLBACK = True  # Fallback to CPU if GPU fails

# VOCAL EXTRACTION SETTINGS
ENABLE_VOCAL_EXTRACTION = False  # Extract vocals before styling (OFF by default, use --enable-vocal-extraction to turn on)
VOCAL_PARALLEL_JOBS = 2  # Parallel vocal extraction (1-4 for RTX 3060 Ti)
VOCAL_MODEL = "htdemucs"  # Demucs model: "htdemucs", "htdemucs_ft", "mdx_extra"

# VIDEO STYLING
VIDEO_SCALE = 0.85  # Size of video on output (0.1-1.0)
FRAME_COLOR = '#888683'  # Frame color around video
FRAME_THICKNESS = 15  # Frame thickness in pixels

# ANIMATION SETTINGS (from original script)
ENABLE_ANIMATION = True  # True/False - enable slide animation
ANIMATION_DURATION = 0.8  # Animation duration in seconds (0.5-2.0)
ANIMATION_TYPE = 'slide'  # Options: 'slide', 'slide_fade', 'slide_scale' (=slide+fade), 'zoom' (=fade), 'bounce', 'blur_slide', 'glitch'
SLIDE_DIRECTION = 'left'  # 'left', 'right', 'top', 'bottom' (for slide-based animations)
FADE_DURATION = 0.5  # Fade duration for slide_fade animation
SCALE_START = 0.7  # No longer used (FFmpeg limitation - scale can't be animated with time)

# OUT ANIMATION SETTINGS (automatic reverse of IN animation)
ENABLE_OUT_ANIMATION = True  # True/False - enable exit animation (auto-mirrors IN)
OUT_ANIMATION_DURATION = 0.8  # Exit animation duration

# SOUND EFFECT SETTINGS
ENABLE_SOUND_EFFECT = True  # True/False - enable sound effect with animation
SOUND_EFFECT_PATH = ""  # Set by orchestrator or profile config
SOUND_EFFECT_VOLUME = 1.0  # Sound effect volume (0.1-1.0)
SOUND_EFFECT_DURATION = 0.8  # Duration to play sound effect (matches animation)

# Note: Crop notification is now handled by crop_tool.py (plays when popup opens)

# EXTRA TIGHT CROPPING (applied after AI detection)
EXTRA_TIGHT_CROP = True  # Enable extra tight crop to remove white frames
EXTRA_CROP_PIXELS = 35  # Extra pixels to crop from each side after AI detection

# ULTRA-STYLE SMART CROPPING (removes white frames like ULTRA)
# Portrait 9:16 (TikTok/Reels) - Aggressive cropping to remove white frames
PORTRAIT_CROP_FACTOR = 0.70    # Keep 70% width (removes white side borders)
PORTRAIT_HEIGHT_KEEP = 0.85    # Keep 85% height (removes white top/bottom)
PORTRAIT_VERTICAL_OFFSET = 0.05 # Start crop from top

# Landscape 16:9 (YouTube) - Aggressive cropping to remove white frames
LANDSCAPE_CROP_FACTOR = 0.75   # Keep 75% width (removes white borders)
LANDSCAPE_HEIGHT_FACTOR = 0.70 # Keep 70% height (removes white top/bottom)
LANDSCAPE_VERTICAL_CENTER = 0.3 # Position crop higher

# ===== DO NOT EDIT BELOW THIS LINE =====

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import tempfile
import json
import time
import hashlib
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor
import threading

# Get script directory and ensure it's in sys.path for module imports
SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Import app utilities for portable paths
try:
    import app_utils
    FFMPEG_PATH = app_utils.get_ffmpeg_path()
    FFPROBE_PATH = app_utils.get_ffprobe_path()
except ImportError:
    # Fallback if app_utils not available
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"

# Try importing OpenCV for AI detection
try:
    import cv2
    import numpy as np

    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Try importing the new Visual Crop Tool (PyQt5-based)
try:
    from crop_tool import show_crop_tool, CropToolDialog
    VISUAL_CROP_AVAILABLE = True
    print(f"[CROP] Visual crop tool imported successfully")
except ImportError as e:
    VISUAL_CROP_AVAILABLE = False
    print(f"[CROP] Visual crop tool import FAILED: {e}")

print(f"[CROP] VISUAL_CROP_AVAILABLE = {VISUAL_CROP_AVAILABLE}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ===== VOCAL EXTRACTION CLASSES =====

class VocalExtractor:
    """Integrated vocal extraction for interview clips"""

    def __init__(self, model='htdemucs', parallel_jobs=2):
        self.model = model
        self.parallel_jobs = parallel_jobs

    def check_dependencies(self):
        """Check if required dependencies are installed"""
        missing = []
        
        # Check ffmpeg
        try:
            result = subprocess.run([FFMPEG_PATH, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info(f"+ ffmpeg is installed")
            else:
                missing.append('ffmpeg')
                logger.error(f"X ffmpeg check failed")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing.append('ffmpeg')
            logger.error(f"X ffmpeg is not installed")
        except Exception as e:
            missing.append('ffmpeg')
            logger.error(f"X Error checking ffmpeg: {e}")
        
        # Check demucs using python -m (handles paths with spaces)
        try:
            result = subprocess.run([sys.executable, '-m', 'demucs', '--help'], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info(f"+ demucs is installed")
            else:
                missing.append('demucs')
                logger.error(f"X demucs check failed")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing.append('demucs')
            logger.error(f"X demucs is not installed")
        except Exception as e:
            missing.append('demucs')
            logger.error(f"X Error checking demucs: {e}")

        return len(missing) == 0

    def extract_audio(self, video_file, output_dir):
        """Extract audio from video file"""
        audio_file = output_dir / f"{video_file.stem}.wav"

        cmd = [
            FFMPEG_PATH, '-y', '-i', str(video_file),
            '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
            str(audio_file), '-v', 'error'
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_file
        except subprocess.CalledProcessError:
            # Try alternative method
            cmd = [
                FFMPEG_PATH, '-y', '-i', str(video_file),
                '-acodec', 'pcm_s16le', str(audio_file), '-v', 'error'
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_file

    def separate_vocals(self, audio_file, output_dir):
        """Use demucs to separate vocals from audio"""
        # Use python -m demucs for better compatibility with embedded Python
        python_exe = sys.executable

        # Try CUDA first, fall back to CPU if it fails
        devices_to_try = ['cuda', 'cpu']

        for device in devices_to_try:
            cmd = [
                python_exe, '-m', 'demucs',
                '--two-stems', 'vocals',
                '-n', self.model,
                '--device', device,
                '-o', str(output_dir),
                str(audio_file)
            ]

            logger.info(f"Running demucs with device={device}: {audio_file.name}")

            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, bufsize=1, universal_newlines=True,
                                           encoding='utf-8', errors='ignore')

                # Read and log output in real-time
                output_lines = []
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        output_lines.append(line)
                        # Log progress lines
                        if '%' in line or 'Separating' in line or 'error' in line.lower():
                            logger.info(f"  demucs: {line}")

                process.wait()

                if process.returncode == 0:
                    logger.info(f"Demucs completed successfully with {device}")
                    return True
                else:
                    error_output = chr(10).join(output_lines[-5:]) if output_lines else 'No output'
                    logger.warning(f"Demucs failed with {device} (code {process.returncode}): {error_output}")
                    if device == 'cuda':
                        logger.info("Trying CPU fallback...")
                        continue
                    return False

            except Exception as e:
                logger.warning(f"Error with {device}: {e}")
                if device == 'cuda':
                    logger.info("Trying CPU fallback...")
                    continue
                return False

        logger.error("Demucs failed with all devices")
        return False

    def merge_vocals_to_video(self, video_file, vocals_audio, output_file):
        """Merge separated vocals back to video"""
        cmd = [
            FFMPEG_PATH, '-y',
            '-i', str(video_file),
            '-i', str(vocals_audio),
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-map', '0:v:0', '-map', '1:a:0',
            str(output_file), '-v', 'error'
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            # Try alternative method
            cmd = [
                FFMPEG_PATH, '-y',
                '-i', str(video_file),
                '-i', str(vocals_audio),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                str(output_file), '-v', 'error'
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return True
            except:
                return False

    def process_single_file(self, video_file, output_dir):
        """Process a single video file for vocal extraction"""
        logger.info(f"Processing: {video_file.name}")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract audio
                audio_file = self.extract_audio(video_file, temp_path)
                if not audio_file.exists():
                    logger.error(f"Failed to extract audio from {video_file.name}")
                    return False

                # Separate vocals
                if not self.separate_vocals(audio_file, temp_path):
                    logger.error(f"Failed to separate vocals for {video_file.name}")
                    return False

                # Find the vocals file
                vocals_dir = temp_path / self.model / audio_file.stem
                vocals_file = vocals_dir / "vocals.wav"

                if not vocals_file.exists():
                    logger.error(f"Vocals file not found for {video_file.name}")
                    return False

                # Create output filename
                output_file = output_dir / f"{video_file.stem}_vocals_only{video_file.suffix}"

                # Merge vocals back to video
                if self.merge_vocals_to_video(video_file, vocals_file, output_file):
                    logger.info(f"+ Success: {output_file.name}")
                    return output_file
                else:
                    logger.error(f"Failed to merge vocals for {video_file.name}")
                    return False

        except Exception as e:
            logger.error(f"Error processing {video_file.name}: {e}")
            return False

    def process_files_parallel(self, video_files, output_dir):
        """Process multiple video files in parallel"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self.check_dependencies():
            logger.error("Missing required dependencies")
            return []

        logger.info(f">> Processing {len(video_files)} files with {self.parallel_jobs} workers")

        def process_wrapper(video_file):
            return self.process_single_file(video_file, output_dir)

        successful_files = []

        if self.parallel_jobs > 1:
            with ThreadPoolExecutor(max_workers=self.parallel_jobs) as executor:
                results = list(executor.map(process_wrapper, video_files))
        else:
            results = [process_wrapper(f) for f in video_files]

        # Collect successful results
        for result in results:
            if result and result != False:
                successful_files.append(result)

        logger.info(f"+ Vocal extraction complete: {len(successful_files)}/{len(video_files)} successful")
        return successful_files


# ===== MANUAL CROP TOOL =====

class ManualCropTool:
    """Simple, clean manual cropping tool"""

    def __init__(self, video_files: List[Path]):
        if not OPENCV_AVAILABLE:
            raise RuntimeError("OpenCV is required for manual cropping")
        self.video_files = sorted(video_files)
        self.crops = {}
        self.current_index = 0
        self.crop_rect = None
        self.last_crop_size = None  # Remember crop size (width, height) between videos
        self.dragging = False
        self.drag_start = None
        self.resize_edge = None
        self.hover_edge = None

    def get_video_frame(self, video_path: Path) -> np.ndarray:
        """Get middle frame from video"""
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, frame = cap.read()
        cap.release()
        logger.info(f"   Extracted frame from middle of video ({frame.shape[1]}x{frame.shape[0]})")
        return frame if ret else None

    def get_edge_at_point(self, x: int, y: int) -> Optional[str]:
        """Check if clicking on a handle"""
        if not self.crop_rect:
            return None
        cx, cy, cw, ch = self.crop_rect
        # Check corners
        if abs(x - cx) < 35 and abs(y - cy) < 35:
            return 'top_left'
        if abs(x - (cx + cw)) < 35 and abs(y - cy) < 35:
            return 'top_right'
        if abs(x - cx) < 35 and abs(y - (cy + ch)) < 35:
            return 'bottom_left'
        if abs(x - (cx + cw)) < 35 and abs(y - (cy + ch)) < 35:
            return 'bottom_right'
        # Check edges
        mid_x, mid_y = cx + cw // 2, cy + ch // 2
        if abs(x - mid_x) < 40 and abs(y - cy) < 15:
            return 'top'
        if abs(x - mid_x) < 40 and abs(y - (cy + ch)) < 15:
            return 'bottom'
        if abs(x - cx) < 15 and abs(y - mid_y) < 40:
            return 'left'
        if abs(x - (cx + cw)) < 15 and abs(y - mid_y) < 40:
            return 'right'
        return None

    def is_inside_rect(self, x: int, y: int) -> bool:
        """Check if inside crop rect"""
        if not self.crop_rect:
            return False
        cx, cy, cw, ch = self.crop_rect
        return cx < x < cx + cw and cy < y < cy + ch

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events"""
        frame_w, frame_h = param
        shift_pressed = flags & cv2.EVENT_FLAG_SHIFTKEY

        if event == cv2.EVENT_MOUSEMOVE:
            self.hover_edge = self.get_edge_at_point(x, y)
            if self.dragging and self.drag_start and self.crop_rect:
                dx = x - self.drag_start[0]
                dy = y - self.drag_start[1]
                cx, cy, cw, ch = self.crop_rect
                if self.resize_edge:
                    # SHIFT key: Symmetrical resizing (both edges move together)
                    if shift_pressed and self.resize_edge in ['left', 'right', 'top', 'bottom']:
                        if self.resize_edge == 'left':
                            # Move both left and right edges symmetrically
                            new_cx = cx + dx
                            new_cw = cw - 2 * dx
                            if new_cw > 100 and new_cx >= 0 and new_cx + new_cw <= frame_w:
                                self.crop_rect[0] = new_cx
                                self.crop_rect[2] = new_cw
                                self.drag_start = (x, self.drag_start[1])
                        elif self.resize_edge == 'right':
                            # Move both left and right edges symmetrically
                            new_cx = cx - dx
                            new_cw = cw + 2 * dx
                            if new_cw > 100 and new_cx >= 0 and new_cx + new_cw <= frame_w:
                                self.crop_rect[0] = new_cx
                                self.crop_rect[2] = new_cw
                                self.drag_start = (x, self.drag_start[1])
                        elif self.resize_edge == 'top':
                            # Move both top and bottom edges symmetrically
                            new_cy = cy + dy
                            new_ch = ch - 2 * dy
                            if new_ch > 100 and new_cy >= 0 and new_cy + new_ch <= frame_h:
                                self.crop_rect[1] = new_cy
                                self.crop_rect[3] = new_ch
                                self.drag_start = (self.drag_start[0], y)
                        elif self.resize_edge == 'bottom':
                            # Move both top and bottom edges symmetrically
                            new_cy = cy - dy
                            new_ch = ch + 2 * dy
                            if new_ch > 100 and new_cy >= 0 and new_cy + new_ch <= frame_h:
                                self.crop_rect[1] = new_cy
                                self.crop_rect[3] = new_ch
                                self.drag_start = (self.drag_start[0], y)
                    else:
                        # Normal resizing (no SHIFT key)
                        if 'left' in self.resize_edge:
                            new_cx, new_cw = cx + dx, cw - dx
                            if new_cw > 50 and new_cx >= 0:
                                self.crop_rect[0], self.crop_rect[2] = new_cx, new_cw
                                self.drag_start = (x, self.drag_start[1])
                        if 'right' in self.resize_edge:
                            new_cw = cw + dx
                            if new_cw > 50 and cx + new_cw <= frame_w:
                                self.crop_rect[2] = new_cw
                                self.drag_start = (x, self.drag_start[1])
                        if 'top' in self.resize_edge:
                            new_cy, new_ch = cy + dy, ch - dy
                            if new_ch > 50 and new_cy >= 0:
                                self.crop_rect[1], self.crop_rect[3] = new_cy, new_ch
                                self.drag_start = (self.drag_start[0], y)
                        if 'bottom' in self.resize_edge:
                            new_ch = ch + dy
                            if new_ch > 50 and cy + new_ch <= frame_h:
                                self.crop_rect[3] = new_ch
                                self.drag_start = (self.drag_start[0], y)
                else:
                    new_cx, new_cy = cx + dx, cy + dy
                    if 0 <= new_cx and new_cx + cw <= frame_w and 0 <= new_cy and new_cy + ch <= frame_h:
                        self.crop_rect[0], self.crop_rect[1] = new_cx, new_cy
                        self.drag_start = (x, y)
        elif event == cv2.EVENT_LBUTTONDOWN:
            edge = self.get_edge_at_point(x, y)
            if edge:
                self.dragging, self.resize_edge, self.drag_start = True, edge, (x, y)
            elif self.is_inside_rect(x, y):
                self.dragging, self.resize_edge, self.drag_start = True, None, (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging, self.resize_edge = False, None

    def draw_crop_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw simple, clean crop overlay"""
        display = frame.copy()
        if not self.crop_rect:
            return display

        # Safety check: ensure crop rect is valid
        cx, cy, cw, ch = self.crop_rect
        h, w = frame.shape[:2]

        # Clamp crop rect to frame bounds
        cx = max(0, min(cx, w - 10))
        cy = max(0, min(cy, h - 10))
        cw = max(10, min(cw, w - cx))
        ch = max(10, min(ch, h - cy))

        # Update crop_rect with safe values
        self.crop_rect = [cx, cy, cw, ch]

        # Darken outside (30%)
        overlay = display.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        display = cv2.addWeighted(display, 1.0, overlay, 0.30, 0)

        # Safely restore crop area (with bounds checking to prevent crashes)
        try:
            # Make sure we're not going out of bounds
            end_y = min(cy + ch, h)
            end_x = min(cx + cw, w)
            actual_ch = end_y - cy
            actual_cw = end_x - cx

            if actual_ch > 0 and actual_cw > 0:
                display[cy:end_y, cx:end_x] = frame[cy:end_y, cx:end_x]
        except Exception as e:
            # If slicing fails, just skip restoring the crop area
            pass
        # White border
        cv2.rectangle(display, (cx, cy), (cx + cw, cy + ch), (255, 255, 255), 2)
        # Grid
        third_w, third_h = cw // 3, ch // 3
        grid_color = (180, 180, 180)
        cv2.line(display, (cx + third_w, cy), (cx + third_w, cy + ch), grid_color, 1)
        cv2.line(display, (cx + 2*third_w, cy), (cx + 2*third_w, cy + ch), grid_color, 1)
        cv2.line(display, (cx, cy + third_h), (cx + cw, cy + third_h), grid_color, 1)
        cv2.line(display, (cx, cy + 2*third_h), (cx + cw, cy + 2*third_h), grid_color, 1)
        # Corner handles
        corners = [(cx, cy, 1, 1), (cx+cw, cy, -1, 1), (cx, cy+ch, 1, -1), (cx+cw, cy+ch, -1, -1)]
        for corner_x, corner_y, dir_x, dir_y in corners:
            color = (0, 255, 0) if self.hover_edge in ['top_left', 'top_right', 'bottom_left', 'bottom_right'] else (255, 255, 255)
            cv2.line(display, (corner_x, corner_y), (corner_x + 25*dir_x, corner_y), color, 3)
            cv2.line(display, (corner_x, corner_y), (corner_x, corner_y + 25*dir_y), color, 3)
        # Edge handles
        mid_x, mid_y = cx + cw // 2, cy + ch // 2
        edge_color = (0, 255, 0) if self.hover_edge in ['top', 'bottom', 'left', 'right'] else (255, 255, 255)
        cv2.rectangle(display, (mid_x-30, cy-6), (mid_x+30, cy+6), edge_color, 2)
        cv2.rectangle(display, (mid_x-30, cy+ch-6), (mid_x+30, cy+ch+6), edge_color, 2)
        cv2.rectangle(display, (cx-6, mid_y-30), (cx+6, mid_y+30), edge_color, 2)
        cv2.rectangle(display, (cx+cw-6, mid_y-30), (cx+cw+6, mid_y+30), edge_color, 2)
        # Dimensions
        cv2.putText(display, f"{cw} x {ch} px", (cx + 10, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return display

    def crop_single_video(self, video_path: Path) -> Optional[Tuple[int, int, int, int]]:
        """Crop a single video"""
        logger.info(f"\n[{self.current_index + 1}/{len(self.video_files)}] Cropping: {video_path.name}")
        frame = self.get_video_frame(video_path)
        if frame is None:
            return None
        orig_h, orig_w = frame.shape[:2]
        # Scale down (max 1200x700)
        scale = min(1200 / orig_w, 700 / orig_h, 1.0)
        display_w, display_h = int(orig_w * scale), int(orig_h * scale)
        if scale != 1.0:
            frame = cv2.resize(frame, (display_w, display_h))
        # Padding
        padding = 100
        canvas_w, canvas_h = display_w + padding * 2, display_h + padding * 2 + 80
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        canvas.fill(45)
        offset_x, offset_y = padding, padding + 80
        canvas[offset_y:offset_y+display_h, offset_x:offset_x+display_w] = frame
        # Init crop - use last crop size if available for smooth workflow
        if self.last_crop_size:
            # Use the crop size from previous video (centered on new frame)
            cw, ch = self.last_crop_size
            # Ensure crop size fits within new frame
            cw = min(cw, display_w - 20)
            ch = min(ch, display_h - 20)
            self.crop_rect = [offset_x + (display_w - cw) // 2, offset_y + (display_h - ch) // 2, cw, ch]
        else:
            # First video: use default 80% crop
            cw, ch = int(display_w * 0.8), int(display_h * 0.8)
            self.crop_rect = [offset_x + (display_w - cw) // 2, offset_y + (display_h - ch) // 2, cw, ch]
        # Window
        window_name = "Manual Crop Tool - Simple & Clean"
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, canvas_w, canvas_h)

            # Try to set window to stay on top (Windows-specific)
            try:
                import ctypes
                # Get window handle
                hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
                if hwnd:
                    # HWND_TOPMOST = -1, SWP_NOMOVE | SWP_NOSIZE = 0x0003
                    ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0003)
                    logger.info("🔝 Crop window set to stay on top")
            except Exception as e:
                logger.debug(f"Could not set window on top: {e}")

            cv2.setMouseCallback(window_name, self.mouse_callback, (canvas_w, canvas_h))

            # Move window to center of screen and bring to front
            cv2.moveWindow(window_name, 100, 100)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

            # IMPORTANT: Display initial frame to ensure window renders properly
            display = canvas.copy()
            display = self.draw_crop_overlay(display)
            # Header
            cv2.rectangle(display, (0, 0), (canvas_w, 80), (30, 30, 30), -1)
            cv2.putText(display, f"INTERVIEW {self.current_index + 1}/{len(self.video_files)} - {video_path.name}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(display, "ENTER=Next  |  SHIFT+Drag=Centered  |  R=Reset  |  ESC=Cancel", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
            cv2.line(display, (0, 80), (canvas_w, 80), (80, 80, 80), 2)
            cv2.imshow(window_name, display)
            cv2.waitKey(100)  # Give window time to render before continuing

            # Flash the window to get user's attention (Windows)
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
                if hwnd:
                    # Flash the window 5 times
                    ctypes.windll.user32.FlashWindow(hwnd, True)
                    logger.info("⚡ Flashing crop window to get your attention!")
            except Exception as e:
                logger.debug(f"Could not flash window: {e}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create crop window: {e}")
            return None

        # Notification is now handled by the new visual crop tool (crop_tool.py)
        # This old ManualCropTool is only used as fallback

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"CROP WINDOW IS NOW OPEN!")
        logger.info(f"📸 Interview {self.current_index + 1}/{len(self.video_files)}: {video_path.name}")
        logger.info(f"👀 LOOK FOR THE WINDOW - It's flashing and on top!")
        logger.info(f"🖱️ Drag to select crop area, then press ENTER")
        logger.info("=" * 80)
        logger.info("")
        sys.stdout and sys.stdout.flush()

        while True:
            try:
                # Check if window still exists BEFORE trying to update it
                try:
                    window_visible = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                    if window_visible < 1:
                        logger.warning(f"⚠️ Crop window closed by user (X button or external close)")
                        logger.info(f"💾 Saving {len(self.crops)} crops completed so far...")
                        cv2.destroyAllWindows()
                        return None
                except cv2.error:
                    logger.warning(f"⚠️ Crop window no longer accessible")
                    cv2.destroyAllWindows()
                    return None

                # Safety check: ensure crop_rect is valid before drawing
                if self.crop_rect:
                    cx, cy, cw, ch = self.crop_rect
                    # Ensure all values are positive and within bounds
                    if cx < 0 or cy < 0 or cw <= 0 or ch <= 0:
                        logger.warning(f"⚠️ Invalid crop rect detected: {self.crop_rect}, resetting...")
                        # Reset to default
                        cw, ch = int(display_w * 0.8), int(display_h * 0.8)
                        self.crop_rect = [offset_x + (display_w - cw) // 2, offset_y + (display_h - ch) // 2, cw, ch]

                display = canvas.copy()
                display = self.draw_crop_overlay(display)
                # Header
                cv2.rectangle(display, (0, 0), (canvas_w, 80), (30, 30, 30), -1)
                cv2.putText(display, f"INTERVIEW {self.current_index + 1}/{len(self.video_files)} - {video_path.name}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(display, "ENTER=Next  |  SHIFT+Drag=Centered  |  R=Reset  |  ESC=Cancel", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                cv2.line(display, (0, 80), (canvas_w, 80), (80, 80, 80), 2)
                cv2.imshow(window_name, display)

                key = cv2.waitKey(30) & 0xFF  # 30ms for smooth display (was 1ms)
            except cv2.error as e:
                logger.error(f"❌ OpenCV error in crop window: {e}")
                logger.warning(f"   Crop rect was: {self.crop_rect}")
                logger.info(f"💾 Saving {len(self.crops)} crops completed so far...")
                cv2.destroyAllWindows()
                return None
            except Exception as e:
                logger.error(f"❌ Unexpected error in crop window: {e}")
                logger.warning(f"   Crop rect was: {self.crop_rect}")
                import traceback
                logger.error(f"Error details: {traceback.format_exc()}")
                logger.info(f"💾 Saving {len(self.crops)} crops completed so far...")
                cv2.destroyAllWindows()
                return None
            if key == 13:  # ENTER
                crop_x = int((self.crop_rect[0] - offset_x) / scale)
                crop_y = int((self.crop_rect[1] - offset_y) / scale)
                crop_w = int(self.crop_rect[2] / scale)
                crop_h = int(self.crop_rect[3] / scale)
                # Save crop size for next video (smooth workflow)
                self.last_crop_size = (self.crop_rect[2], self.crop_rect[3])
                cv2.destroyWindow(window_name)
                self.crop_rect = None
                return (crop_x, crop_y, crop_w, crop_h)
            elif key == 27:  # ESC
                cv2.destroyWindow(window_name)
                return None
            elif key == ord('r') or key == ord('R'):
                cw, ch = int(display_w * 0.8), int(display_h * 0.8)
                self.crop_rect = [offset_x + (display_w - cw) // 2, offset_y + (display_h - ch) // 2, cw, ch]
        return None

    def crop_all_videos(self) -> Dict[str, Tuple[int, int, int, int]]:
        """Crop all videos"""
        logger.info(f"\n{'='*60}")
        logger.info("MANUAL CROP MODE - Frame-Based Cropping")
        logger.info(f"{'='*60}")
        logger.info(f"Interviews to crop: {len(self.video_files)}")
        logger.info(f"Method: 1 frame per interview (from middle of video)")
        logger.info(f"Crop will apply to ENTIRE video")
        logger.info("")
        logger.info("Controls:")
        logger.info("  - Drag corners/edges to resize crop box")
        logger.info("  - SHIFT + Drag edge: Resize symmetrically (centered)")
        logger.info("  - Drag inside box to move it")
        logger.info("  - ENTER: Save crop and move to next interview")
        logger.info("  - R: Reset crop to default")
        logger.info("  - ESC: Cancel cropping")
        logger.info("")
        logger.info("Smooth Workflow:")
        logger.info("  - Crop size is remembered between videos")
        logger.info("  - Each new video starts with your last crop size")
        logger.info(f"{'='*60}\n")
        for i, video_file in enumerate(self.video_files):
            self.current_index = i
            try:
                crop = self.crop_single_video(video_file)
                if crop is None:
                    logger.warning(f"⚠️ Cropping cancelled at video {i+1}/{len(self.video_files)}")
                    logger.info(f"📊 Cropped: {len(self.crops)} videos manually")
                    logger.info(f"🤖 Remaining {len(self.video_files) - len(self.crops)} videos will use AI auto-crop")
                    sys.stdout and sys.stdout.flush()
                    break
                self.crops[video_file.name] = crop  # Use filename only, not full path
                logger.info(f"✓ Saved crop: {crop[2]}x{crop[3]} at ({crop[0]},{crop[1]})")
                sys.stdout and sys.stdout.flush()
            except Exception as e:
                logger.error(f"❌ Error cropping {video_file.name}: {e}")
                logger.info(f"📊 Cropped: {len(self.crops)} videos successfully")
                logger.info(f"🤖 Remaining {len(self.video_files) - len(self.crops)} videos will use AI auto-crop")
                sys.stdout and sys.stdout.flush()
                break

        logger.info(f"\n✅ Manual cropping loop finished!")
        logger.info(f"📊 Results: {len(self.crops)}/{len(self.video_files)} videos cropped")
        if len(self.crops) < len(self.video_files):
            logger.info(f"ℹ️ Videos without manual crops will automatically use AI detection")
        logger.info(f"🔄 Continuing to styling phase...")
        sys.stdout and sys.stdout.flush()
        return self.crops


class SimpleContentDetector:
    """Simplified content detection for FAST script"""

    def __init__(self):
        self.cache = {}

    def get_video_hash(self, video_path: str) -> str:
        """Generate unique hash for video"""
        stat = Path(video_path).stat()
        return hashlib.md5(f"{video_path}{stat.st_size}{stat.st_mtime}".encode()).hexdigest()

    def extract_sample_frames(self, video_path: str, num_frames: int = 6) -> List:
        """Extract sample frames using FFmpeg"""
        frames = []
        temp_dir = Path(tempfile.gettempdir()) / "fast_frame_extract"
        temp_dir.mkdir(exist_ok=True)

        for i in range(num_frames):
            time_pos = i * 3  # Sample every 3 seconds
            frame_path = temp_dir / f"frame_{i:03d}.jpg"

            cmd = [
                FFMPEG_PATH, '-y', '-ss', str(time_pos),
                '-i', str(video_path),
                '-frames:v', '1',
                '-q:v', '2',
                str(frame_path)
            ]

            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=5)
                if OPENCV_AVAILABLE:
                    frame = cv2.imread(str(frame_path))
                    if frame is not None:
                        frames.append(frame)
                else:
                    frames.append(str(frame_path))
            except:
                pass

        return frames

    def detect_edges_simple(self, frames: List) -> Optional[Tuple[int, int, int, int]]:
        """Simple edge detection to find content boundaries"""
        if not OPENCV_AVAILABLE or not frames:
            return None

        edge_regions = []

        for frame in frames:
            if isinstance(frame, str):  # Skip file paths
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Canny edge detection
            edges = cv2.Canny(blurred, 50, 150)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            # Look for rectangular shapes
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)

                if len(approx) == 4:  # Rectangle
                    x, y, w, h = cv2.boundingRect(approx)

                    # Check if reasonable size
                    frame_h, frame_w = frame.shape[:2]
                    area_ratio = (w * h) / (frame_w * frame_h)

                    if 0.2 < area_ratio < 0.9:  # 20-90% of frame
                        edge_regions.append((x, y, w, h))
                        break

        if edge_regions:
            # Average all regions
            avg_region = [
                sum(r[i] for r in edge_regions) // len(edge_regions)
                for i in range(4)
            ]
            return tuple(avg_region)

        return None

    def smart_detect_fast(self, video_path: str, video_info: Dict) -> Tuple[int, int, int, int]:
        """Fast smart detection - tries edge detection, falls back to aggressive crop"""
        video_hash = self.get_video_hash(video_path)

        # Check cache
        if video_hash in self.cache:
            logger.info("📦 Using cached crop coordinates")
            return self.cache[video_hash]

        width = video_info['width']
        height = video_info['height']
        orientation = video_info['orientation']

        logger.info(f"🔍 Fast AI detection for {orientation} video ({width}x{height})")

        # Try edge detection if OpenCV available
        detected_coords = None
        if OPENCV_AVAILABLE:
            frames = self.extract_sample_frames(video_path, 4)  # Just 4 frames for speed
            if frames:
                detected_coords = self.detect_edges_simple(frames)
                if detected_coords:
                    x, y, w, h = detected_coords
                    # Validate coordinates
                    if 0 <= x < width and 0 <= y < height and w > 0 and h > 0:
                        if x + w <= width and y + h <= height:
                            area_ratio = (w * h) / (width * height)
                            if 0.2 < area_ratio < 0.95:  # Reasonable size
                                logger.info(f"✅ 📐 Edge detection successful")
                                logger.info(f"✂️ AI crop: {w}x{h} at ({x},{y}) [{area_ratio:.0%} of original]")
                                self.cache[video_hash] = detected_coords
                                return detected_coords

        # Fallback to aggressive manual crop
        logger.info(f"📏 Using aggressive {orientation} fallback crop")

        if orientation == 'portrait':
            # Aggressive 9:16 crop
            crop_width = int(width * PORTRAIT_CROP_FACTOR)
            crop_height = int(height * PORTRAIT_HEIGHT_KEEP)
            crop_x = (width - crop_width) // 2
            crop_y = int(height * PORTRAIT_VERTICAL_OFFSET)
        elif orientation == 'landscape':
            # Aggressive 16:9 crop
            crop_width = int(width * LANDSCAPE_CROP_FACTOR)
            crop_height = int(height * LANDSCAPE_HEIGHT_FACTOR)
            crop_x = (width - crop_width) // 2
            crop_y = int((height - crop_height) * LANDSCAPE_VERTICAL_CENTER)
        else:  # square
            crop_width = int(width * 0.75)
            crop_height = int(height * 0.75)
            crop_x = (width - crop_width) // 2
            crop_y = (height - crop_height) // 2

        fallback_coords = (crop_x, crop_y, crop_width, crop_height)
        crop_ratio = (crop_width * crop_height) / (width * height)
        logger.info(
            f"✂️ Fallback crop: {crop_width}x{crop_height} at ({crop_x},{crop_y}) [{crop_ratio:.0%} of original]")

        # Cache results
        self.cache[video_hash] = fallback_coords

        # Clean up temp frames
        temp_dir = Path(tempfile.gettempdir()) / "fast_frame_extract"
        if temp_dir.exists():
            for frame_file in temp_dir.glob("frame_*.jpg"):
                try:
                    frame_file.unlink()
                except:
                    pass

        return fallback_coords


class FastReliableStyler:
    def __init__(self, background_path: str = None, output_dir: str = None, frame_color: str = None,
                 video_scale: float = None, trim_seconds: float = 0):
        self.background_path = background_path or BACKGROUND_PATH
        self.output_dir = Path(output_dir or OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.frame_color = frame_color or FRAME_COLOR
        self.video_scale = video_scale or VIDEO_SCALE
        self.trim_seconds = trim_seconds  # Trim from start and end of each clip

        # Initialize AI detection
        self.detector = SimpleContentDetector()

        # GPU encoding stats
        self.gpu_success_count = 0
        self.cpu_fallback_count = 0

        logger.info(f"⚡ Fast Interview Styler (ULTRA AI detection + GPU acceleration)")
        logger.info(f"📂 Output: {self.output_dir}")
        logger.info(f"🖼️ Background: {self.background_path}")
        if self.trim_seconds > 0:
            logger.info(f"✂️ Trim: {self.trim_seconds}s from start and end of each clip")

        # GPU status
        if ENABLE_GPU_ENCODING:
            logger.info(f"🚀 GPU encoding: ENABLED (h264_nvenc preset {GPU_PRESET})")
            if CPU_FALLBACK:
                logger.info(f"🔄 CPU fallback: ENABLED (libx264)")
        else:
            logger.info(f"💻 GPU encoding: DISABLED (using CPU libx264)")

        if OPENCV_AVAILABLE:
            logger.info(f"🤖 AI edge detection: Available")
        else:
            logger.info(f"📝 AI detection: Not available, using smart fallback")

    def get_video_info(self, video_path: str) -> Dict:
        """Get video info quickly"""
        cmd = [
            FFPROBE_PATH, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration',
            '-of', 'csv=p=0',
            str(video_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            parts = result.stdout.strip().split(',')
            width = int(parts[0])
            height = int(parts[1])
            duration = float(parts[2]) if len(parts) > 2 else 30.0

            # Determine orientation like ULTRA
            aspect_ratio = width / height
            if aspect_ratio > 1.2:
                orientation = 'landscape'  # 16:9 etc
            elif aspect_ratio < 0.8:
                orientation = 'portrait'  # 9:16 etc
            else:
                orientation = 'square'

            return {
                'width': width,
                'height': height,
                'duration': duration,
                'aspect_ratio': aspect_ratio,
                'orientation': orientation
            }
        except Exception as e:
            logger.error(f"❌ Video info failed: {e}")
            return {'width': 1920, 'height': 1080, 'duration': 30.0, 'orientation': 'landscape', 'aspect_ratio': 1.78}

    def get_ultra_style_crop(self, width: int, height: int, orientation: str) -> Tuple[int, int, int, int]:
        """Get ULTRA-style aggressive crop coordinates to remove white frames"""

        logger.info(f"📐 Using ULTRA-style {orientation} crop...")

        if orientation == 'portrait':
            # ULTRA-style 9:16 cropping - AGGRESSIVE to remove white frames
            crop_width = int(width * PORTRAIT_CROP_FACTOR)  # 70% width - removes white sides
            crop_height = int(height * PORTRAIT_HEIGHT_KEEP)  # 85% height - removes white top/bottom

            crop_x = (width - crop_width) // 2  # Center horizontally
            crop_y = int(height * PORTRAIT_VERTICAL_OFFSET)  # Start from top to remove white

            logger.info(f"📱 Portrait ULTRA crop: removes white frames, keeps 9:16 format")

        elif orientation == 'landscape':
            # ULTRA-style 16:9 cropping - AGGRESSIVE to remove white frames
            crop_width = int(width * LANDSCAPE_CROP_FACTOR)  # 75% width
            crop_height = int(height * LANDSCAPE_HEIGHT_FACTOR)  # 70% height - aggressive

            crop_x = (width - crop_width) // 2
            crop_y = int((height - crop_height) * LANDSCAPE_VERTICAL_CENTER)  # Higher position

            logger.info(f"🖥️ Landscape ULTRA crop: removes white frames aggressively")

        else:  # square
            crop_width = int(width * 0.75)  # Aggressive square crop
            crop_height = int(height * 0.75)
            crop_x = (width - crop_width) // 2
            crop_y = (height - crop_height) // 2

            logger.info(f"⬜ Square ULTRA crop: removes white borders")

        logger.info(f"✂️ ULTRA crop: {crop_width}x{crop_height} at ({crop_x}, {crop_y})")
        return crop_x, crop_y, crop_width, crop_height

    def create_shared_background(self, max_duration: float) -> str:
        """Create one background for all videos"""
        bg_output = self.output_dir / "shared_background.mp4"

        # Skip if exists and recent
        if bg_output.exists():
            age = time.time() - bg_output.stat().st_mtime
            if age < 300:  # Less than 5 minutes old
                logger.info(f"♻️ Reusing existing background")
                return str(bg_output)

        duration = max_duration + 10  # Extra buffer

        if not Path(self.background_path).exists():
            logger.warning(f"⚠️ Background not found, creating solid color")
            cmd = [
                FFMPEG_PATH, '-y',
                '-f', 'lavfi',
                '-i', f'color=c=black:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:d={duration}',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                str(bg_output)
            ]
        else:
            cmd = [
                FFMPEG_PATH, '-y',
                '-stream_loop', '-1',
                '-i', str(self.background_path),
                '-t', str(duration),
                '-vf',
                f'scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-an',  # Exclude audio from background video
                str(bg_output)
            ]

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            logger.info(f"✅ Shared background created: {duration:.1f}s")
            return str(bg_output)
        except Exception as e:
            logger.error(f"❌ Background creation failed: {e}")
            raise

    def get_opposite_direction(self, direction: str) -> str:
        """Get opposite direction for exit animation"""
        opposites = {
            'left': 'right',
            'right': 'left',
            'top': 'bottom',
            'bottom': 'top'
        }
        return opposites.get(direction, 'right')

    def build_animation_filter(self, crop_x: int, crop_y: int, crop_w: int, crop_h: int,
                               final_width: int, final_height: int, final_x: int, final_y: int,
                               duration: float) -> str:
        """Build FFmpeg filter with animations"""

        if not ENABLE_ANIMATION:
            # No animation - simple static overlay
            return (
                f'[1:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},'
                f'scale={final_width}:{final_height},'
                f'drawbox=x=0:y=0:w={final_width}:h={final_height}:color={self.frame_color}:t={FRAME_THICKNESS}[interview];'
                f'[0:v][interview]overlay={final_x}:{final_y}[v]'
            )

        # Build animated filter
        base_filter = (
            f'[1:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},'
            f'scale={final_width}:{final_height},'
            f'drawbox=x=0:y=0:w={final_width}:h={final_height}:color={self.frame_color}:t={FRAME_THICKNESS}'
        )

        if ANIMATION_TYPE == 'slide':
            return self.build_slide_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        elif ANIMATION_TYPE == 'slide_fade':
            return self.build_slide_fade_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        elif ANIMATION_TYPE == 'slide_scale':
            return self.build_slide_scale_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        elif ANIMATION_TYPE == 'zoom':
            return self.build_zoom_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        elif ANIMATION_TYPE == 'bounce':
            return self.build_bounce_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        elif ANIMATION_TYPE == 'blur_slide':
            return self.build_blur_slide_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        elif ANIMATION_TYPE == 'glitch':
            return self.build_glitch_animation(base_filter, final_width, final_height, final_x, final_y, duration)
        else:
            # Default to simple overlay
            return base_filter + f'[interview];[0:v][interview]overlay={final_x}:{final_y}[v]'

    def build_slide_animation(self, base_filter: str, final_width: int, final_height: int,
                              final_x: int, final_y: int, duration: float) -> str:
        """Build slide animation filter with IN and OUT"""

        # Calculate IN starting position
        if SLIDE_DIRECTION == 'left':
            in_start_x = -final_width
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'right':
            in_start_x = OUTPUT_WIDTH
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'top':
            in_start_x = final_x
            in_start_y = -final_height
        elif SLIDE_DIRECTION == 'bottom':
            in_start_x = final_x
            in_start_y = OUTPUT_HEIGHT
        else:
            in_start_x = final_x
            in_start_y = final_y

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation
            return (
                    base_filter +
                    f'[interview];'
                    f'[0:v][interview]overlay='
                    f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                    f'{final_x}):'
                    f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                    f'{final_y})[v]'
            )

        # Calculate OUT ending position (opposite direction)
        out_direction = self.get_opposite_direction(SLIDE_DIRECTION)
        if out_direction == 'left':
            out_end_x = -final_width
            out_end_y = final_y
        elif out_direction == 'right':
            out_end_x = OUTPUT_WIDTH
            out_end_y = final_y
        elif out_direction == 'top':
            out_end_x = final_x
            out_end_y = -final_height
        elif out_direction == 'bottom':
            out_end_x = final_x
            out_end_y = OUTPUT_HEIGHT
        else:
            out_end_x = OUTPUT_WIDTH
            out_end_y = final_y

        out_start_time = duration - OUT_ANIMATION_DURATION

        return (
                base_filter +
                f'[interview];'
                f'[0:v][interview]overlay='
                # X position: IN animation → static → OUT animation
                f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_x}\\,'
                f'{final_x}+({out_end_x}-{final_x})*(t-{out_start_time})/{OUT_ANIMATION_DURATION})):'
                # Y position: IN animation → static → OUT animation
                f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_y}\\,'
                f'{final_y}+({out_end_y}-{final_y})*(t-{out_start_time})/{OUT_ANIMATION_DURATION}))[v]'
        )

    def build_slide_fade_animation(self, base_filter: str, final_width: int, final_height: int,
                                   final_x: int, final_y: int, duration: float) -> str:
        """Build slide + fade animation filter with IN and OUT"""

        # Calculate IN starting position
        if SLIDE_DIRECTION == 'left':
            in_start_x = -final_width // 2
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'right':
            in_start_x = OUTPUT_WIDTH - final_width // 2
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'top':
            in_start_x = final_x
            in_start_y = -final_height // 2
        elif SLIDE_DIRECTION == 'bottom':
            in_start_x = final_x
            in_start_y = OUTPUT_HEIGHT - final_height // 2
        else:
            in_start_x = final_x
            in_start_y = final_y

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation with fade
            return (
                    base_filter +
                    f',fade=in:0:{int(FADE_DURATION * OUTPUT_FPS)}[interview];'
                    f'[0:v][interview]overlay='
                    f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                    f'{final_x}):'
                    f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                    f'{final_y})[v]'
            )

        # Calculate OUT ending position (opposite direction)
        out_direction = self.get_opposite_direction(SLIDE_DIRECTION)
        if out_direction == 'left':
            out_end_x = -final_width // 2
            out_end_y = final_y
        elif out_direction == 'right':
            out_end_x = OUTPUT_WIDTH - final_width // 2
            out_end_y = final_y
        elif out_direction == 'top':
            out_end_x = final_x
            out_end_y = -final_height // 2
        elif out_direction == 'bottom':
            out_end_x = final_x
            out_end_y = OUTPUT_HEIGHT - final_height // 2
        else:
            out_end_x = OUTPUT_WIDTH - final_width // 2
            out_end_y = final_y

        out_start_time = duration - OUT_ANIMATION_DURATION
        out_fade_start_frame = int(out_start_time * OUTPUT_FPS)
        out_fade_duration_frames = int(OUT_ANIMATION_DURATION * OUTPUT_FPS)

        return (
                base_filter +
                f',fade=in:0:{int(FADE_DURATION * OUTPUT_FPS)},'
                f'fade=out:{out_fade_start_frame}:{out_fade_duration_frames}[interview];'
                f'[0:v][interview]overlay='
                # X position: IN animation → static → OUT animation
                f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_x}\\,'
                f'{final_x}+({out_end_x}-{final_x})*(t-{out_start_time})/{OUT_ANIMATION_DURATION})):'
                # Y position: IN animation → static → OUT animation
                f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_y}\\,'
                f'{final_y}+({out_end_y}-{final_y})*(t-{out_start_time})/{OUT_ANIMATION_DURATION}))[v]'
        )

    def build_slide_scale_animation(self, base_filter: str, final_width: int, final_height: int,
                                    final_x: int, final_y: int, duration: float) -> str:
        """Build slide + fade animation (scale animation replaced with fade due to FFmpeg limitations)"""

        # NOTE: FFmpeg's scale filter doesn't support time-based expressions
        # So this uses slide + fade instead of slide + scale

        # Calculate IN starting position
        if SLIDE_DIRECTION == 'left':
            in_start_x = -final_width // 2
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'right':
            in_start_x = OUTPUT_WIDTH - final_width // 2
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'top':
            in_start_x = final_x
            in_start_y = -final_height // 2
        elif SLIDE_DIRECTION == 'bottom':
            in_start_x = final_x
            in_start_y = OUTPUT_HEIGHT - final_height // 2
        else:
            in_start_x = final_x
            in_start_y = final_y

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation with slide + fade
            return (
                    base_filter +
                    f',fade=in:0:{int(ANIMATION_DURATION * OUTPUT_FPS)}[interview];'
                    f'[0:v][interview]overlay='
                    f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                    f'{final_x}):'
                    f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                    f'{final_y})[v]'
            )

        # Calculate OUT ending position (opposite direction)
        out_direction = self.get_opposite_direction(SLIDE_DIRECTION)
        if out_direction == 'left':
            out_end_x = -final_width // 2
            out_end_y = final_y
        elif out_direction == 'right':
            out_end_x = OUTPUT_WIDTH - final_width // 2
            out_end_y = final_y
        elif out_direction == 'top':
            out_end_x = final_x
            out_end_y = -final_height // 2
        elif out_direction == 'bottom':
            out_end_x = final_x
            out_end_y = OUTPUT_HEIGHT - final_height // 2
        else:
            out_end_x = OUTPUT_WIDTH - final_width // 2
            out_end_y = final_y

        out_start_time = duration - OUT_ANIMATION_DURATION
        out_fade_start_frame = int(out_start_time * OUTPUT_FPS)
        out_fade_duration_frames = int(OUT_ANIMATION_DURATION * OUTPUT_FPS)

        return (
                base_filter +
                f',fade=in:0:{int(ANIMATION_DURATION * OUTPUT_FPS)},'
                f'fade=out:{out_fade_start_frame}:{out_fade_duration_frames}[interview];'
                f'[0:v][interview]overlay='
                # X position: slide IN → static → slide OUT
                f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_x}\\,'
                f'{final_x}+({out_end_x}-{final_x})*(t-{out_start_time})/{OUT_ANIMATION_DURATION})):'
                # Y position: slide IN → static → slide OUT
                f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_y}\\,'
                f'{final_y}+({out_end_y}-{final_y})*(t-{out_start_time})/{OUT_ANIMATION_DURATION}))[v]'
        )

    def build_zoom_animation(self, base_filter: str, final_width: int, final_height: int,
                            final_x: int, final_y: int, duration: float) -> str:
        """Build pure zoom animation - uses fade to simulate zoom effect"""

        # FFmpeg's scale filter doesn't support time-based expressions
        # So we'll use fade effect to simulate a zoom feel
        # This creates a fade-in/fade-out effect that gives visual impact similar to zoom

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation with fade
            return (
                    base_filter +
                    f',fade=in:0:{int(ANIMATION_DURATION * OUTPUT_FPS)}[interview];'
                    f'[0:v][interview]overlay={final_x}:{final_y}[v]'
            )

        # WITH OUT animation: fade in → static → fade out
        out_start_time = duration - OUT_ANIMATION_DURATION
        out_fade_start_frame = int(out_start_time * OUTPUT_FPS)
        out_fade_duration_frames = int(OUT_ANIMATION_DURATION * OUTPUT_FPS)

        return (
                base_filter +
                f',fade=in:0:{int(ANIMATION_DURATION * OUTPUT_FPS)},'
                f'fade=out:{out_fade_start_frame}:{out_fade_duration_frames}[interview];'
                f'[0:v][interview]overlay={final_x}:{final_y}[v]'
        )

    def build_bounce_animation(self, base_filter: str, final_width: int, final_height: int,
                               final_x: int, final_y: int, duration: float) -> str:
        """Build slide with bounce effect - elastic easing at the end"""

        # Calculate IN starting position (same as slide)
        if SLIDE_DIRECTION == 'left':
            in_start_x = -final_width
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'right':
            in_start_x = OUTPUT_WIDTH
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'top':
            in_start_x = final_x
            in_start_y = -final_height
        elif SLIDE_DIRECTION == 'bottom':
            in_start_x = final_x
            in_start_y = OUTPUT_HEIGHT
        else:
            in_start_x = final_x
            in_start_y = final_y

        # Bounce overshoot amount (bounces 10% past final position)
        bounce_overshoot = 0.1

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation with bounce
            # Simplified bounce: linear movement with slight overshoot
            return (
                    base_filter +
                    f'[interview];'
                    f'[0:v][interview]overlay='
                    f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_x}+({final_x}-{in_start_x})*1.1*t/{ANIMATION_DURATION}\\,'
                    f'{final_x}):'
                    f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_y}+({final_y}-{in_start_y})*1.1*t/{ANIMATION_DURATION}\\,'
                    f'{final_y})[v]'
            )

        # Calculate OUT ending position (opposite direction)
        out_direction = self.get_opposite_direction(SLIDE_DIRECTION)
        if out_direction == 'left':
            out_end_x = -final_width
            out_end_y = final_y
        elif out_direction == 'right':
            out_end_x = OUTPUT_WIDTH
            out_end_y = final_y
        elif out_direction == 'top':
            out_end_x = final_x
            out_end_y = -final_height
        elif out_direction == 'bottom':
            out_end_x = final_x
            out_end_y = OUTPUT_HEIGHT
        else:
            out_end_x = OUTPUT_WIDTH
            out_end_y = final_y

        out_start_time = duration - OUT_ANIMATION_DURATION

        return (
                base_filter +
                f'[interview];'
                f'[0:v][interview]overlay='
                # X position: bounce IN → static → bounce OUT
                f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_x}+({final_x}-{in_start_x})*1.1*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_x}\\,'
                f'{final_x}+({out_end_x}-{final_x})*(t-{out_start_time})/{OUT_ANIMATION_DURATION})):'
                # Y position: bounce IN → static → bounce OUT
                f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_y}+({final_y}-{in_start_y})*1.1*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_y}\\,'
                f'{final_y}+({out_end_y}-{final_y})*(t-{out_start_time})/{OUT_ANIMATION_DURATION}))[v]'
        )

    def build_blur_slide_animation(self, base_filter: str, final_width: int, final_height: int,
                                   final_x: int, final_y: int, duration: float) -> str:
        """Build slide with blur effect - blurred while sliding"""

        # Calculate IN starting position
        if SLIDE_DIRECTION == 'left':
            in_start_x = -final_width
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'right':
            in_start_x = OUTPUT_WIDTH
            in_start_y = final_y
        elif SLIDE_DIRECTION == 'top':
            in_start_x = final_x
            in_start_y = -final_height
        elif SLIDE_DIRECTION == 'bottom':
            in_start_x = final_x
            in_start_y = OUTPUT_HEIGHT
        else:
            in_start_x = final_x
            in_start_y = final_y

        # Blur intensity
        max_blur = 10  # Maximum blur radius

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation with blur
            return (
                    base_filter +
                    # Add animated blur that decreases as it slides in
                    f',boxblur=luma_radius=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{max_blur}-{max_blur}*t/{ANIMATION_DURATION}\\,0):luma_power=1'
                    f'[interview];'
                    f'[0:v][interview]overlay='
                    f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                    f'{final_x}):'
                    f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                    f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                    f'{final_y})[v]'
            )

        # Calculate OUT ending position (opposite direction)
        out_direction = self.get_opposite_direction(SLIDE_DIRECTION)
        if out_direction == 'left':
            out_end_x = -final_width
            out_end_y = final_y
        elif out_direction == 'right':
            out_end_x = OUTPUT_WIDTH
            out_end_y = final_y
        elif out_direction == 'top':
            out_end_x = final_x
            out_end_y = -final_height
        elif out_direction == 'bottom':
            out_end_x = final_x
            out_end_y = OUTPUT_HEIGHT
        else:
            out_end_x = OUTPUT_WIDTH
            out_end_y = final_y

        out_start_time = duration - OUT_ANIMATION_DURATION

        return (
                base_filter +
                # Animated blur: blur IN → sharp → blur OUT
                f',boxblur=luma_radius=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{max_blur}-{max_blur}*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,0\\,'
                f'{max_blur}*(t-{out_start_time})/{OUT_ANIMATION_DURATION})):luma_power=1'
                f'[interview];'
                f'[0:v][interview]overlay='
                # X position: slide IN → static → slide OUT
                f'x=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_x}+({final_x}-{in_start_x})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_x}\\,'
                f'{final_x}+({out_end_x}-{final_x})*(t-{out_start_time})/{OUT_ANIMATION_DURATION})):'
                # Y position: slide IN → static → slide OUT
                f'y=if(lt(t\\,{ANIMATION_DURATION})\\,'
                f'{in_start_y}+({final_y}-{in_start_y})*t/{ANIMATION_DURATION}\\,'
                f'if(lt(t\\,{out_start_time})\\,{final_y}\\,'
                f'{final_y}+({out_end_y}-{final_y})*(t-{out_start_time})/{OUT_ANIMATION_DURATION}))[v]'
        )

    def build_glitch_animation(self, base_filter: str, final_width: int, final_height: int,
                               final_x: int, final_y: int, duration: float) -> str:
        """Build digital glitch effect - RGB split/chromatic aberration"""

        # Glitch effect using RGB channel splits
        # This creates a chromatic aberration effect
        glitch_offset = 15  # Pixel offset for RGB channels

        if not ENABLE_OUT_ANIMATION:
            # Only IN animation with glitch
            # Glitch intensity decreases during IN animation
            return (
                    base_filter +
                    # Split into R, G, B channels and offset them for glitch effect
                    f',split=3[r][g][b];'
                    f'[r]lutrgb=g=0:b=0,crop={final_width}:{final_height}:0:0[r1];'
                    f'[g]lutrgb=r=0:b=0,crop={final_width}:{final_height}:0:0[g1];'
                    f'[b]lutrgb=r=0:g=0,crop={final_width}:{final_height}:0:0[b1];'
                    f'[r1][g1]blend=all_mode=addition[rg];'
                    f'[rg][b1]blend=all_mode=addition[interview];'
                    f'[0:v][interview]overlay={final_x}:{final_y}[v]'
            )

        out_start_time = duration - OUT_ANIMATION_DURATION

        # Simplified glitch without complex RGB split (FFmpeg limitation for time-based effects)
        # Using noise and fade to simulate glitch effect
        return (
                base_filter +
                # Add noise-based glitch effect that appears at start and end
                f',fade=in:0:{int(ANIMATION_DURATION * OUTPUT_FPS)},'
                f'fade=out:{int(out_start_time * OUTPUT_FPS)}:{int(OUT_ANIMATION_DURATION * OUTPUT_FPS)}'
                f'[interview];'
                f'[0:v][interview]overlay={final_x}:{final_y}[v]'
        )

    def add_sound_effect(self, cmd: List[str], output_file: str) -> List[str]:
        """Add sound effect to the command"""
        if not SOUND_EFFECT_PATH or not Path(SOUND_EFFECT_PATH).exists():
            return cmd

        # Find the output file in cmd and replace with temp file
        temp_video = output_file.replace('.mp4', '_temp.mp4')

        # Replace output file in original command
        cmd_with_temp = []
        for item in cmd:
            if item == output_file:
                cmd_with_temp.append(temp_video)
            else:
                cmd_with_temp.append(item)

        # Create new command to add sound effect
        new_cmd = [
            FFMPEG_PATH, '-y',
            '-i', temp_video,
            '-i', SOUND_EFFECT_PATH,
            '-filter_complex', (
                f'[1:a]volume={SOUND_EFFECT_VOLUME},atrim=0:{SOUND_EFFECT_DURATION}[sfx];'
                f'[0:a][sfx]amix=inputs=2:duration=longest[a]'
            ),
            '-map', '0:v',
            '-map', '[a]',
            '-c:v', 'copy',
            '-c:a', 'aac',
            output_file
        ]

        return cmd_with_temp, new_cmd

        return cmd

    def style_single_video_reliable(self, video_path: str, shared_background: str, manual_crop: Optional[Tuple[int, int, int, int]] = None, no_crop: bool = False) -> str:
        """Style one video with ULTRA cropping but reliable encoding"""
        video_file = Path(video_path)
        output_file = self.output_dir / f"fast_styled_{video_file.stem}.mp4"

        start_time = time.time()
        logger.info(f"🎬 Processing: {video_file.name}")

        # Get video info
        video_info = self.get_video_info(video_path)
        orientation = video_info['orientation']
        original_duration = video_info['duration']

        # Apply trim from start and end
        trim_start = 0
        trim_duration = original_duration
        if self.trim_seconds > 0:
            # Make sure we have enough duration to trim
            min_duration_needed = self.trim_seconds * 2 + 1  # At least 1 second after trimming
            if original_duration > min_duration_needed:
                trim_start = self.trim_seconds
                trim_duration = original_duration - (self.trim_seconds * 2)
                logger.info(f"✂️ Trimming: {self.trim_seconds}s from start, {self.trim_seconds}s from end")
                logger.info(f"   Original: {original_duration:.1f}s → Trimmed: {trim_duration:.1f}s")
            else:
                logger.warning(f"⚠️ Video too short to trim ({original_duration:.1f}s < {min_duration_needed:.1f}s needed)")

        duration = trim_duration  # Use trimmed duration for further calculations

        # NO-CROP MODE: Use full video without any cropping (for Create Video)
        if no_crop:
            crop_x, crop_y = 0, 0
            crop_w, crop_h = video_info['width'], video_info['height']
            logger.info(f"📐 NO-CROP MODE: Using full video {crop_w}x{crop_h}")
        # Get crop coordinates - manual or AI-detected
        elif manual_crop:
            crop_x, crop_y, crop_w, crop_h = manual_crop

            # Validate manual crop fits within video dimensions
            video_width = video_info['width']
            video_height = video_info['height']

            # Clamp coordinates to valid ranges
            crop_x = max(0, min(crop_x, video_width - 100))
            crop_y = max(0, min(crop_y, video_height - 100))
            crop_w = max(100, min(crop_w, video_width - crop_x))
            crop_h = max(100, min(crop_h, video_height - crop_y))

            logger.info(f"📐 Using manual crop: {crop_w}x{crop_h} at ({crop_x},{crop_y})")
            logger.info(f"   ✅ Skipping extra crop (manual crop is already precise)")
        else:
            # Get AI-detected crop coordinates (like ULTRA)
            crop_x, crop_y, crop_w, crop_h = self.detector.smart_detect_fast(video_path, video_info)

        # Apply extra tight crop to remove white frames (ONLY for AI auto-crop, not in no_crop mode)
        if not manual_crop and not no_crop and EXTRA_TIGHT_CROP and EXTRA_CROP_PIXELS > 0:
            original_area = crop_w * crop_h
            crop_x += EXTRA_CROP_PIXELS
            crop_y += EXTRA_CROP_PIXELS
            crop_w -= (2 * EXTRA_CROP_PIXELS)
            crop_h -= (2 * EXTRA_CROP_PIXELS)

            # Ensure minimum size
            crop_w = max(crop_w, 200)
            crop_h = max(crop_h, 200)

            # Ensure within bounds
            crop_x = max(0, min(crop_x, video_info['width'] - crop_w))
            crop_y = max(0, min(crop_y, video_info['height'] - crop_h))

            new_area = crop_w * crop_h
            removed_percent = ((original_area - new_area) / original_area) * 100
            logger.info(f"🔧 Extra tight crop: removed {removed_percent:.1f}% more to eliminate white frames")

        # Calculate final size on output - PRESERVE ASPECT RATIO
        crop_aspect = crop_w / crop_h

        # Special handling for 9:16 videos to keep them tall
        if orientation == 'portrait':
            # For 9:16: Make it tall but fit in the output frame
            max_height = int(OUTPUT_HEIGHT * self.video_scale)
            final_height = max_height
            final_width = int(final_height * crop_aspect)

            # If too wide, scale down proportionally
            if final_width > OUTPUT_WIDTH * self.video_scale:
                final_width = int(OUTPUT_WIDTH * self.video_scale)
                final_height = int(final_width / crop_aspect)

        else:
            # For 16:9 and square: normal scaling
            output_aspect = OUTPUT_WIDTH / OUTPUT_HEIGHT
            if crop_aspect > output_aspect:
                final_width = int(OUTPUT_WIDTH * self.video_scale)
                final_height = int(final_width / crop_aspect)
            else:
                final_height = int(OUTPUT_HEIGHT * self.video_scale)
                final_width = int(final_height * crop_aspect)

        final_x = (OUTPUT_WIDTH - final_width) // 2
        final_y = (OUTPUT_HEIGHT - final_height) // 2

        # Build FFmpeg command with animations
        filter_complex = self.build_animation_filter(
            crop_x, crop_y, crop_w, crop_h,
            final_width, final_height, final_x, final_y,
            duration
        )

        # Try GPU encoding first, fallback to CPU if it fails
        encoding_method = "unknown"
        gpu_attempted = False

        try:
            # === ATTEMPT 1: GPU ENCODING ===
            if ENABLE_GPU_ENCODING:
                gpu_attempted = True
                logger.info(f"   🚀 Attempting GPU encoding (h264_nvenc)...")

                cmd_gpu = [
                    FFMPEG_PATH, '-y',
                    '-hwaccel', 'cuda',  # Use CUDA acceleration
                    '-i', shared_background,
                ]
                # Add trim parameters for interview clip if trimming is enabled
                if trim_start > 0:
                    cmd_gpu.extend(['-ss', str(trim_start)])
                cmd_gpu.extend([
                    '-i', str(video_path),
                ])
                if trim_start > 0:
                    cmd_gpu.extend(['-t', str(trim_duration)])
                cmd_gpu.extend([
                    '-filter_complex', filter_complex,
                    '-map', '[v]',
                    '-map', '1:a?',
                    '-c:v', 'h264_nvenc',  # NVIDIA GPU encoder
                    '-preset', GPU_PRESET,  # NVENC preset (p4 = fast)
                    '-cq', str(GPU_CQ),  # Quality for NVENC
                    '-c:a', 'aac',
                    '-shortest',
                    str(output_file)
                ])

                # Process video with GPU
                if ENABLE_SOUND_EFFECT and SOUND_EFFECT_PATH and Path(SOUND_EFFECT_PATH).exists():
                    # Two-step process: video first, then add sound
                    cmd_video, cmd_sound = self.add_sound_effect(cmd_gpu, str(output_file))

                    # Step 1: Create video with animation (GPU)
                    subprocess.run(cmd_video, capture_output=True, check=True, timeout=120)

                    # Step 2: Add sound effect
                    subprocess.run(cmd_sound, capture_output=True, check=True, timeout=60)

                    # Clean up temp file
                    temp_video = str(output_file).replace('.mp4', '_temp.mp4')
                    try:
                        Path(temp_video).unlink()
                    except:
                        pass
                else:
                    # Single step: just video with animation (GPU)
                    subprocess.run(cmd_gpu, capture_output=True, check=True, timeout=120)

                # GPU SUCCESS!
                encoding_method = "GPU"
                self.gpu_success_count += 1

        except Exception as e_gpu:
            # GPU failed, try CPU fallback
            if CPU_FALLBACK and gpu_attempted:
                logger.warning(f"   ⚠️ GPU encoding failed, falling back to CPU...")
                logger.debug(f"   GPU error: {str(e_gpu)[:100]}")

                try:
                    # === ATTEMPT 2: CPU ENCODING ===
                    cmd_cpu = [
                        FFMPEG_PATH, '-y',
                        '-i', shared_background,
                    ]
                    # Add trim parameters for interview clip if trimming is enabled
                    if trim_start > 0:
                        cmd_cpu.extend(['-ss', str(trim_start)])
                    cmd_cpu.extend([
                        '-i', str(video_path),
                    ])
                    if trim_start > 0:
                        cmd_cpu.extend(['-t', str(trim_duration)])
                    cmd_cpu.extend([
                        '-filter_complex', filter_complex,
                        '-map', '[v]',
                        '-map', '1:a?',
                        '-c:v', 'libx264',  # CPU encoder
                        '-preset', 'ultrafast',  # Fast CPU encoding
                        '-crf', '22',  # Good quality
                        '-c:a', 'aac',
                        '-shortest',
                        str(output_file)
                    ])

                    # Process video with CPU
                    if ENABLE_SOUND_EFFECT and SOUND_EFFECT_PATH and Path(SOUND_EFFECT_PATH).exists():
                        cmd_video, cmd_sound = self.add_sound_effect(cmd_cpu, str(output_file))
                        subprocess.run(cmd_video, capture_output=True, check=True, timeout=120)
                        subprocess.run(cmd_sound, capture_output=True, check=True, timeout=60)

                        temp_video = str(output_file).replace('.mp4', '_temp.mp4')
                        try:
                            Path(temp_video).unlink()
                        except:
                            pass
                    else:
                        subprocess.run(cmd_cpu, capture_output=True, check=True, timeout=120)

                    # CPU SUCCESS!
                    encoding_method = "CPU"
                    self.cpu_fallback_count += 1

                except Exception as e_cpu:
                    logger.error(f"❌ Both GPU and CPU encoding failed!")
                    logger.error(f"GPU error: {str(e_gpu)[:100]}")
                    logger.error(f"CPU error: {str(e_cpu)[:100]}")
                    raise
            else:
                # No fallback or GPU not attempted
                raise

        # Calculate stats
        processing_time = time.time() - start_time
        speed_ratio = duration / processing_time if processing_time > 0 else 0

        # Log success
        logger.info(
            f"✅ {video_file.name} completed in {processing_time:.1f}s (speed: {speed_ratio:.1f}x) [{encoding_method}]")
        logger.info(f"   📊 {orientation} → {crop_w}x{crop_h} → {final_width}x{final_height}")

        return str(output_file)

    def process_folder_reliable(self, input_folder: str, manual_crops = None, excluded_files: list = None) -> List[str]:
        """Process all videos with reliable method

        manual_crops can be:
        - None: use AI auto-crop
        - "NO_CROP": skip all cropping (Create Video mode)
        - Dict[str, Tuple]: manual crop coordinates per video

        excluded_files: list of filenames to skip (removed in crop tool)
        """
        # Check for NO_CROP mode
        no_crop_mode = manual_crops == "NO_CROP"
        if no_crop_mode:
            manual_crops = None

        input_path = Path(input_folder)
        if not input_path.exists():
            raise FileNotFoundError(f"Input folder not found: {input_folder}")

        # Find video files
        video_files = []
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            video_files.extend(input_path.glob(f"*{ext}"))
            video_files.extend(input_path.glob(f"*{ext.upper()}"))

        # Remove duplicates (Windows is case-insensitive, so .mp4 and .MP4 match same files)
        video_files = list(set(str(f.resolve()) for f in video_files))
        video_files = [Path(f) for f in sorted(video_files)]

        # Filter out excluded files (removed in crop tool)
        if excluded_files:
            excluded_set = set(excluded_files)
            before_count = len(video_files)
            video_files = [vf for vf in video_files if vf.name not in excluded_set]
            if len(video_files) < before_count:
                logger.info(f"🗑️ Excluded {before_count - len(video_files)} removed interviews from processing")

        if not video_files:
            logger.warning(f"⚠️ No video files found")
            return []

        logger.info(f"📁 Found {len(video_files)} videos")

        if no_crop_mode:
            logger.info(f"📐 NO-CROP MODE: Using videos as-is without cropping")
        elif manual_crops:
            logger.info(f"📐 Using manual crops for {len(manual_crops)} videos")
            if len(manual_crops) < len(video_files):
                uncropped_count = len(video_files) - len(manual_crops)
                logger.info(f"🤖 {uncropped_count} videos will use AI auto-crop (no manual crop data)")

        # Quick analysis for background creation
        max_duration = 0
        orientations = {'landscape': 0, 'portrait': 0, 'square': 0}

        for video_file in video_files[:min(5, len(video_files))]:
            try:
                info = self.get_video_info(str(video_file))
                max_duration = max(max_duration, info['duration'])
                orientations[info['orientation']] += 1
            except:
                pass

        logger.info(f"📊 Video types: {dict(orientations)}")
        logger.info(f"⏱️ Max duration: {max_duration:.1f}s")
        logger.info(f"✂️ ULTRA-style aggressive cropping:")
        logger.info(
            f"   📱 Portrait (9:16): {PORTRAIT_CROP_FACTOR * 100:.0f}% width, {PORTRAIT_HEIGHT_KEEP * 100:.0f}% height")
        logger.info(
            f"   🖥️ Landscape (16:9): {LANDSCAPE_CROP_FACTOR * 100:.0f}% width, {LANDSCAPE_HEIGHT_FACTOR * 100:.0f}% height")

        # Create shared background once
        shared_background = self.create_shared_background(max_duration)

        # Process videos sequentially for maximum reliability
        results = []
        failed = []

        for i, video_file in enumerate(sorted(video_files), 1):
            logger.info(f"\\n🎬 [{i}/{len(video_files)}] Processing: {video_file.name}")
            try:
                # Get manual crop if available (lookup by filename, not full path)
                manual_crop = manual_crops.get(video_file.name) if manual_crops else None
                styled_video = self.style_single_video_reliable(str(video_file), shared_background, manual_crop, no_crop=no_crop_mode)
                results.append(styled_video)
            except Exception as e:
                logger.error(f"❌ Failed: {video_file.name} - {e}")
                failed.append(video_file.name)

        # Cleanup
        try:
            Path(shared_background).unlink()
        except:
            pass

        logger.info(f"\\n>> PROCESSING COMPLETE!")
        logger.info(f"+ Success: {len(results)} videos")
        if failed:
            logger.info(f"X Failed: {len(failed)} videos")

        # GPU/CPU stats
        if ENABLE_GPU_ENCODING:
            total_processed = self.gpu_success_count + self.cpu_fallback_count
            if total_processed > 0:
                gpu_percent = (self.gpu_success_count / total_processed) * 100
                logger.info(f"\\n📊 ENCODING STATS:")
                logger.info(f"   🚀 GPU: {self.gpu_success_count} videos ({gpu_percent:.0f}%)")
                logger.info(f"   💻 CPU fallback: {self.cpu_fallback_count} videos ({100 - gpu_percent:.0f}%)")

        return results


def main():
    import argparse

    # Declare globals at the start of the function
    global ENABLE_GPU_ENCODING, GPU_PRESET, GPU_CQ
    global ENABLE_ANIMATION, ANIMATION_TYPE, SLIDE_DIRECTION, ANIMATION_DURATION, ENABLE_OUT_ANIMATION, OUT_ANIMATION_DURATION
    global ENABLE_SOUND_EFFECT, SOUND_EFFECT_PATH, SOUND_EFFECT_VOLUME, SOUND_EFFECT_DURATION

    parser = argparse.ArgumentParser(description="Fast Interview Styler - Manual cropping (default) + GPU acceleration")
    parser.add_argument('input_folder', nargs='?', help='Input folder (positional)')
    parser.add_argument('output_folder', nargs='?', help='Output folder (positional)')
    parser.add_argument('--input', '-i', help='Input folder')
    parser.add_argument('--background', '-b', help='Background video')
    parser.add_argument('--output', '-o', help='Output folder')
    parser.add_argument('--frame-color', help='Frame color (hex code)')
    parser.add_argument('--video-scale', type=float, help='Video scale (0.1-1.0)')
    parser.add_argument('--fast', action='store_true', help='Use fastest settings (already fast)')

    # Animation arguments
    parser.add_argument('--enable-animation', action='store_true', default=ENABLE_ANIMATION,
                        help=f'Enable animations (default: {ENABLE_ANIMATION})')
    parser.add_argument('--disable-animation', action='store_true',
                        help='Disable all animations (static video only)')
    parser.add_argument('--animation-type', default=ANIMATION_TYPE,
                        choices=['slide', 'slide_fade', 'slide_scale', 'zoom', 'bounce', 'blur_slide', 'glitch'],
                        help=f'Animation type (default: {ANIMATION_TYPE})')
    parser.add_argument('--animation-direction', default=SLIDE_DIRECTION,
                        choices=['left', 'right', 'top', 'bottom'],
                        help=f'Slide direction for slide-based animations (default: {SLIDE_DIRECTION})')
    parser.add_argument('--animation-duration', type=float, default=ANIMATION_DURATION,
                        help=f'IN animation duration in seconds (default: {ANIMATION_DURATION})')
    parser.add_argument('--enable-out-animation', action='store_true', default=ENABLE_OUT_ANIMATION,
                        help=f'Enable OUT animation (auto-mirrors IN) (default: {ENABLE_OUT_ANIMATION})')
    parser.add_argument('--out-animation-duration', type=float, default=OUT_ANIMATION_DURATION,
                        help=f'OUT animation duration in seconds (default: {OUT_ANIMATION_DURATION})')

    # Sound effect arguments
    parser.add_argument('--enable-sound-effect', action='store_true', default=ENABLE_SOUND_EFFECT,
                        help=f'Enable sound effect with animation (default: {ENABLE_SOUND_EFFECT})')
    parser.add_argument('--disable-sound-effect', action='store_true',
                        help='Disable sound effect')
    parser.add_argument('--sound-effect-path', default=SOUND_EFFECT_PATH,
                        help='Path to sound effect audio file (mp3/wav)')
    parser.add_argument('--sound-effect-volume', type=float, default=SOUND_EFFECT_VOLUME,
                        help=f'Sound effect volume 0.1-1.0 (default: {SOUND_EFFECT_VOLUME})')
    parser.add_argument('--sound-effect-duration', type=float, default=SOUND_EFFECT_DURATION,
                        help=f'Sound effect duration in seconds (default: {SOUND_EFFECT_DURATION})')

    # Vocal extraction arguments
    parser.add_argument('--enable-vocal-extraction', action='store_true',
                        help='Extract vocals before styling (OFF by default)')
    parser.add_argument('--vocal-parallel', type=int, default=VOCAL_PARALLEL_JOBS,
                        help=f'Parallel vocal extraction jobs (default: {VOCAL_PARALLEL_JOBS})')
    parser.add_argument('--vocal-model', default=VOCAL_MODEL,
                        choices=['htdemucs', 'htdemucs_ft', 'mdx_extra'],
                        help=f'Demucs model for vocal extraction (default: {VOCAL_MODEL})')

    # GPU encoding arguments
    parser.add_argument('--enable-gpu', action='store_true', default=ENABLE_GPU_ENCODING,
                        help=f'Enable GPU encoding (h264_nvenc) (default: {ENABLE_GPU_ENCODING})')
    parser.add_argument('--disable-gpu', action='store_true',
                        help='Disable GPU encoding, use CPU only')
    parser.add_argument('--gpu-preset', default=GPU_PRESET,
                        choices=['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'],
                        help=f'NVENC preset: p1 (slow/quality) to p7 (fast) (default: {GPU_PRESET})')
    parser.add_argument('--gpu-cq', type=int, default=GPU_CQ,
                        help=f'GPU quality: lower=better (18-23 recommended) (default: {GPU_CQ})')

    # Crop mode arguments (manual is DEFAULT)
    parser.add_argument('--auto-crop', action='store_true',
                        help='Use AI auto-cropping instead of manual cropping (manual is default)')
    parser.add_argument('--no-crop', action='store_true',
                        help='Disable all cropping - use video as-is (for Create Video mode)')

    # Trim arguments
    parser.add_argument('--trim-seconds', type=float, default=0,
                        help='Trim seconds from start and end of each interview clip (default: 0)')

    args = parser.parse_args()

    # Manual crop is DEFAULT unless --auto-crop or --no-crop is specified
    args.manual_crop = not args.auto_crop and not args.no_crop

    # Apply GPU settings from args
    if args.disable_gpu:
        ENABLE_GPU_ENCODING = False
    elif args.enable_gpu:
        ENABLE_GPU_ENCODING = True
    GPU_PRESET = args.gpu_preset
    GPU_CQ = args.gpu_cq

    # Apply animation settings from args
    if args.disable_animation:
        ENABLE_ANIMATION = False
    elif args.enable_animation:
        ENABLE_ANIMATION = True
    ANIMATION_TYPE = args.animation_type
    SLIDE_DIRECTION = args.animation_direction
    ANIMATION_DURATION = args.animation_duration
    ENABLE_OUT_ANIMATION = args.enable_out_animation
    OUT_ANIMATION_DURATION = args.out_animation_duration

    # Apply sound effect settings from args
    if args.disable_sound_effect:
        ENABLE_SOUND_EFFECT = False
    elif args.enable_sound_effect:
        ENABLE_SOUND_EFFECT = True
    SOUND_EFFECT_PATH = args.sound_effect_path
    SOUND_EFFECT_VOLUME = args.sound_effect_volume
    SOUND_EFFECT_DURATION = args.sound_effect_duration

    # Use positional args first, then fallback to named args, then config
    input_folder = args.input_folder or args.input or INPUT_FOLDER

    # Determine output folder
    if args.output_folder:
        output_folder = args.output_folder
    elif args.output:
        output_folder = args.output
    elif OUTPUT_DIR:
        output_folder = OUTPUT_DIR
    else:
        output_folder = str(Path(input_folder) / "output")

    logger.info(f"📁 Input:  {input_folder}")
    logger.info(f"📁 Output: {output_folder}")

    try:
        # ===== PHASE 1: VOCAL EXTRACTION =====
        if args.enable_vocal_extraction:
            logger.info("=== PHASE 1: VOCAL EXTRACTION ===")
            vocal_extractor = VocalExtractor(args.vocal_model, args.vocal_parallel)

            # Get input files
            input_path = Path(input_folder)
            if not input_path.exists():
                raise ValueError(f"Input folder not found: {input_folder}")

            video_files = []
            for ext in ['*.mp4', '*.avi', '*.mov', '*.mkv']:
                video_files.extend(input_path.glob(ext))

            if not video_files:
                raise ValueError(f"No video files found in {input_folder}")

            logger.info(f"Found {len(video_files)} video files for vocal extraction")

            # Create temporary directory for vocal-extracted files
            import tempfile
            temp_vocals_dir = Path(tempfile.mkdtemp(prefix="vocals_"))

            # Extract vocals from all files
            vocal_files = vocal_extractor.process_files_parallel(video_files, temp_vocals_dir)

            if not vocal_files:
                logger.error("Vocal extraction failed for all files")
                raise ValueError("No files successfully processed for vocal extraction")

            logger.info(f"+ Phase 1 complete: {len(vocal_files)} files with clean vocals")

            # Use vocal-extracted files as input for styling
            styling_input = str(temp_vocals_dir)
        else:
            # Skip vocal extraction, use original input
            logger.info("Vocal extraction disabled - using original files")
            styling_input = input_folder

        # ===== PHASE 1.5: MANUAL CROPPING (if enabled) =====
        manual_crops = None
        excluded_files = []  # Track excluded/removed interviews from crop tool

        # Check for --no-crop mode (Create Video - no cropping at all)
        if args.no_crop:
            logger.info("=== NO-CROP MODE (Create Video) ===")
            logger.info("Using interview clips as-is without any cropping")
            manual_crops = "NO_CROP"  # Special flag to skip all cropping
        elif args.manual_crop:
            logger.info("=== MANUAL CROP MODE ===")

            # Get video files from styling_input
            input_path = Path(styling_input)
            video_files = []
            for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                video_files.extend(input_path.glob(f"*{ext}"))
                video_files.extend(input_path.glob(f"*{ext.upper()}"))

            # Remove duplicates (Windows is case-insensitive, so .mp4 and .MP4 match same files)
            video_files = list(set(str(f.resolve()) for f in video_files))
            video_files = [Path(f) for f in sorted(video_files)]

            if not video_files:
                raise ValueError(f"No video files found in {styling_input}")

            # Define shared crop file path (in parent directory of ORIGINAL input, shared across profiles)
            # If using vocal extraction, use original input folder, not temp folder
            if args.enable_vocal_extraction:
                original_input_path = Path(input_folder)
                crop_file = original_input_path.parent / "manual_crops.json"
            else:
                crop_file = input_path.parent / "manual_crops.json"

            logger.info(f"[CROP DEBUG] input_folder = {input_folder}")
            logger.info(f"[CROP DEBUG] crop_file = {crop_file}")
            logger.info(f"[CROP DEBUG] crop_file.exists() = {crop_file.exists()}")

            # Try to load existing crops first
            if crop_file.exists():
                try:
                    with open(crop_file, 'r') as f:
                        saved_crops = json.load(f)

                    # Extract excluded files list if saved
                    excluded_files = saved_crops.pop("__excluded__", [])
                    if excluded_files:
                        logger.info(f"🗑️ {len(excluded_files)} interviews previously excluded:")
                        for ef in excluded_files:
                            logger.info(f"   - {ef}")

                    # Convert saved crops to proper format, using FILENAME as key (not full path)
                    manual_crops = {}
                    for video_path, crop_data in saved_crops.items():
                        # Extract filename from saved path and use it as key
                        filename = Path(video_path).name
                        manual_crops[filename] = tuple(crop_data)

                    # Filter out excluded files from video_files list
                    if excluded_files:
                        before_count = len(video_files)
                        video_files = [vf for vf in video_files if vf.name not in excluded_files]
                        if len(video_files) < before_count:
                            logger.info(f"📋 Filtered: {before_count} → {len(video_files)} videos (excluded {before_count - len(video_files)})")

                    # Check if we have crops for ALL videos
                    video_filenames = {vf.name for vf in video_files}
                    cropped_filenames = set(manual_crops.keys())
                    missing_crops = video_filenames - cropped_filenames

                    if missing_crops:
                        logger.info("✅ Using manual crops from UI (pre-cropped)")
                        logger.info(f"📂 Loaded {len(manual_crops)} existing crops from: {crop_file}")
                        logger.warning(f"⚠️ Missing crops for {len(missing_crops)} videos:")
                        for missing in list(missing_crops)[:5]:  # Show first 5
                            logger.warning(f"   - {missing}")
                        logger.info(f"🤖 Missing videos will use AI auto-crop")
                    else:
                        logger.info("✅ Using manual crops from UI (pre-cropped)")
                        logger.info(f"📂 Loaded {len(manual_crops)} crops from file: {crop_file}")
                        logger.info(f"   → Using saved crops for all {len(manual_crops)} videos")

                except Exception as e:
                    logger.warning(f"⚠️ Could not load crop file: {e}")
                    manual_crops = None

            # If no existing crops, use manual crop tool directly
            if not manual_crops:
                logger.info("=" * 80)
                logger.info("MANUAL CROP MODE - Starting crop tool...")
                logger.info(f"Found {len(video_files)} interview clips to crop")
                logger.info("=" * 80)
                sys.stdout and sys.stdout.flush()

                # Use new Visual Crop Tool (PyQt5-based) if available
                use_visual_crop = VISUAL_CROP_AVAILABLE
                if use_visual_crop:
                    logger.info("Starting Visual Crop Tool (PyQt5)...")
                    sys.stdout and sys.stdout.flush()
                    sys.stderr and sys.stderr.flush()

                    try:
                        # Call the new visual crop tool
                        logger.info("Calling show_crop_tool()...")
                        manual_crops = show_crop_tool(video_files, existing_crops=None)

                        if manual_crops:
                            # Extract excluded files list from crop tool result
                            excluded_files = manual_crops.pop("__excluded__", [])
                            if excluded_files:
                                logger.info(f"🗑️ {len(excluded_files)} interviews excluded/removed:")
                                for ef in excluded_files:
                                    logger.info(f"   - {ef}")
                            logger.info(f"\nVisual Crop Tool finished!")
                            logger.info(f"Cropped {len(manual_crops)}/{len(video_files)} videos")
                        else:
                            logger.info("Crop tool cancelled or no crops defined")
                            manual_crops = None
                    except Exception as crop_error:
                        logger.error(f"Visual Crop Tool FAILED: {crop_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        logger.info("Falling back to OpenCV crop tool...")
                        use_visual_crop = False  # Force fallback
                        manual_crops = None

                    sys.stdout and sys.stdout.flush()
                    sys.stderr and sys.stderr.flush()

                # Fall back to OpenCV simple crop tool (only if visual crop wasn't used)
                elif OPENCV_AVAILABLE:
                    logger.info("Visual Crop Tool not available, using OpenCV fallback...")
                    logger.info("   -> Press ENTER to save crop")
                    logger.info("   -> Press ESC to skip video")
                    sys.stdout and sys.stdout.flush()
                    sys.stderr and sys.stderr.flush()

                    manual_crops = {}
                    import cv2

                    for idx, video_file in enumerate(video_files):
                        logger.info(f"\nVideo {idx + 1}/{len(video_files)}: {video_file.name}")
                        sys.stdout and sys.stdout.flush()

                        cap = cv2.VideoCapture(str(video_file))
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                        ret, frame = cap.read()
                        cap.release()

                        if not ret:
                            logger.warning(f"Could not read frame from {video_file.name}")
                            continue

                        orig_h, orig_w = frame.shape[:2]
                        scale = min(1200 / orig_w, 800 / orig_h, 1.0)

                        if scale < 1.0:
                            display_frame = cv2.resize(frame, (int(orig_w * scale), int(orig_h * scale)))
                        else:
                            display_frame = frame
                            scale = 1.0

                        roi = cv2.selectROI("Crop Tool", display_frame, showCrosshair=True, fromCenter=False)
                        cv2.destroyAllWindows()

                        if roi[2] > 0 and roi[3] > 0:
                            orig_roi = (int(roi[0]/scale), int(roi[1]/scale), int(roi[2]/scale), int(roi[3]/scale))
                            manual_crops[video_file.name] = orig_roi
                            logger.info(f"Saved crop: {orig_roi[2]}x{orig_roi[3]}")

                    logger.info(f"\nCrop tool finished! {len(manual_crops)}/{len(video_files)} videos cropped")
                    sys.stdout and sys.stdout.flush()

                else:
                    # No crop tool available at all
                    logger.error("No crop tool available (need PyQt5 or OpenCV)")
                    manual_crops = None
                    sys.stdout and sys.stdout.flush()

                # Save crops for future use (include excluded list)
                if manual_crops and len(manual_crops) > 0:
                    try:
                        crops_to_save = {Path(k).name: list(v) for k, v in manual_crops.items()}
                        # Save excluded files list so future runs know to skip them
                        if excluded_files:
                            crops_to_save["__excluded__"] = excluded_files
                        with open(crop_file, 'w') as f:
                            json.dump(crops_to_save, f, indent=2)
                        logger.info(f"💾 Saved manual crops to: {crop_file}")
                        sys.stdout and sys.stdout.flush()
                    except Exception as e:
                        logger.warning(f"⚠️ Could not save crop file: {e}")

            if not manual_crops or len(manual_crops) == 0:
                logger.warning("⚠️ No manual crops defined, will use AI auto-crop for all videos")
                manual_crops = None
                sys.stdout and sys.stdout.flush()
            elif len(manual_crops) < len(video_files):
                uncropped = len(video_files) - len(manual_crops)
                logger.info(f"ℹ️ {uncropped} videos without manual crops will use AI auto-crop")
                sys.stdout and sys.stdout.flush()

        # ===== PHASE 2: STYLING =====
        phase_name = "PHASE 2" if not args.enable_vocal_extraction else "PHASE 2" if not args.manual_crop else "PHASE 3"
        logger.info("=" * 80)
        logger.info(f"=== {phase_name}: VIDEO STYLING ===")
        logger.info(f"🎨 Starting video styling phase...")
        logger.info(f"📁 Input: {styling_input}")
        logger.info(f"📁 Output: {output_folder}")
        sys.stdout and sys.stdout.flush()

        styler = FastReliableStyler(
            args.background or BACKGROUND_PATH,
            output_folder,
            args.frame_color,
            args.video_scale,
            args.trim_seconds
        )

        logger.info(f"🚀 Processing videos with styler...")
        sys.stdout and sys.stdout.flush()
        results = styler.process_folder_reliable(styling_input, manual_crops, excluded_files)
        logger.info(f"✅ Styling phase complete! Processed {len(results) if results else 0} videos")
        sys.stdout and sys.stdout.flush()

        # Cleanup temporary vocal directory if used
        if args.enable_vocal_extraction and 'temp_vocals_dir' in locals():
            try:
                shutil.rmtree(temp_vocals_dir)
                logger.info("+ Cleaned up temporary vocal files")
            except:
                pass

        if results:
            phases = []
            if args.enable_vocal_extraction:
                phases.append(f"Vocal extraction with {args.vocal_parallel} parallel workers")
            if args.manual_crop and manual_crops:
                phases.append(f"Manual cropping ({len(manual_crops)} videos)")

            crop_type = "Manual crops" if (args.manual_crop and manual_crops) else "ULTRA-style AI cropping"
            encoding_type = "GPU (h264_nvenc)" if ENABLE_GPU_ENCODING else "CPU (libx264)"

            if phases:
                print(f"\\n>> SUCCESS! {len(phases) + 1}-Phase processing complete!")
                for i, phase in enumerate(phases, 1):
                    print(f">> Phase {i}: {phase}")
                print(f">> Phase {len(phases) + 1}: {crop_type} with {encoding_type}")
            else:
                print(f"\\n>> SUCCESS! {crop_type} with {encoding_type}")

            print(f"+ Created {len(results)} styled videos")
            print(f">> Output: {styler.output_dir}")

            if args.manual_crop and manual_crops:
                print(f"\\n>> All videos styled with YOUR manual crops!")
            else:
                print(f"\\n>> 9:16 videos: Aggressive crop removes white frames")
                print(f">> 16:9 videos: Aggressive crop removes white borders")

            # Show encoding details
            if ENABLE_GPU_ENCODING:
                print(f">> Encoding: GPU accelerated (preset {GPU_PRESET}, quality {GPU_CQ})")
            else:
                print(f">> Encoding: CPU (ultrafast preset)")
        else:
            print("X No videos were created")

    except Exception as e:
        print(f"X Failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())