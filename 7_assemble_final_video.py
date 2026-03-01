# Fix Windows console encoding for emoji/unicode
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import subprocess
import argparse
import random
from collections import deque
import json
import time
from pathlib import Path

# Get script directory and ensure it's in sys.path for module imports
SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Import cv2 and numpy for visual logo editor
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None
    np = None

# Import app utilities for portable paths
try:
    import app_utils
    FFMPEG_PATH = app_utils.get_ffmpeg_path()
    FFPROBE_PATH = app_utils.get_ffprobe_path()
except ImportError:
    # Fallback if app_utils not available
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"

# Try to import the NEW Video Editor Tool (best option - zoom, crop, pan + optional logo)
try:
    from video_editor_tool import VideoEditorDialog
    VIDEO_EDITOR_AVAILABLE = True
except ImportError:
    VIDEO_EDITOR_AVAILABLE = False

# Fallback to old logo editor
try:
    from logo_editor_tool import LogoEditorDialog
    LOGO_EDITOR_AVAILABLE = True
except ImportError:
    LOGO_EDITOR_AVAILABLE = False

# Try to import the professional logo GUI
try:
    from logo_preview_pro import ProfessionalLogoGUI
    PROFESSIONAL_GUI_AVAILABLE = True
except ImportError:
    PROFESSIONAL_GUI_AVAILABLE = False

# Try the enhanced GUI as fallback
try:
    from logo_preview_gui import LogoPreviewGUI
    ENHANCED_GUI_AVAILABLE = True
except ImportError:
    ENHANCED_GUI_AVAILABLE = False

# Try to import tkinter (optional - not available in embedded Python)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    tk = None

# Try to import PyQt5 as alternative GUI toolkit
try:
    from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                                  QLabel, QPushButton, QSlider, QFileDialog,
                                  QGridLayout, QButtonGroup, QRadioButton, QLineEdit,
                                  QGroupBox, QMessageBox)
    from PyQt5.QtCore import Qt
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False

# Removed hardcoded global paths: VOICEOVERS_FOLDER, CLIPS_FOLDER, OUTPUT_FOLDER

# Global cache for clip information
clip_info_cache = {}
_CACHE_FILE_PATH = None # This will be set by main() from args

# Global logo configuration
logo_config = None

# Global flag to enable/disable logo feature
ENABLE_LOGO_FEATURE = os.environ.get('ENABLE_LOGO_FEATURE', 'true').lower() == 'true'


def load_cache():
    """Load clip information cache from file if it exists."""
    global clip_info_cache
    if not _CACHE_FILE_PATH or not os.path.exists(_CACHE_FILE_PATH):
        print(f"No cache file path set or cache file not found: {_CACHE_FILE_PATH}")
        clip_info_cache = {}
        return

    try:
        with open(_CACHE_FILE_PATH, 'r') as f:
            clip_info_cache = json.load(f)
        print(f"Loaded cache with {len(clip_info_cache)} clip entries from {_CACHE_FILE_PATH}")
    except Exception as e:
        print(f"Error loading cache from {_CACHE_FILE_PATH}: {e}")
        clip_info_cache = {}


def save_cache():
    """Save clip information cache to file."""
    if not _CACHE_FILE_PATH:
        print("No cache file path set, skipping cache save.")
        return
    try:
        # Ensure the directory exists before saving the cache file
        os.makedirs(os.path.dirname(_CACHE_FILE_PATH), exist_ok=True)
        with open(_CACHE_FILE_PATH, 'w', encoding='utf-8') as f: # Added encoding for robustness
            json.dump(clip_info_cache, f, indent=2) # Added indent for readability
        print(f"Saved cache with {len(clip_info_cache)} clip entries to {_CACHE_FILE_PATH}")
    except Exception as e:
        print(f"Error saving cache to {_CACHE_FILE_PATH}: {e}")


def get_clip_info(file_path):
    """Get clip duration and resolution, using cache if available."""
    global clip_info_cache

    # Check if file exists and get modification time
    if not os.path.exists(file_path):
        return None

    file_mod_time = os.path.getmtime(file_path)

    # Use cached info if available and file hasn't changed
    if file_path in clip_info_cache:
        if clip_info_cache[file_path].get("mod_time", 0) == file_mod_time:
            return clip_info_cache[file_path]

    # Get both duration and resolution in a single FFprobe call
    cmd = [
        FFPROBE_PATH, "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-select_streams", "v:0",
        "-of", "json", file_path
    ]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        data = json.loads(result.stdout)

        # Extract info from JSON response
        info = {
            "duration": float(data["format"]["duration"]),
            "width": int(data["streams"][0]["width"]) if "width" in data["streams"][0] else 0,
            "height": int(data["streams"][0]["height"]) if "height" in data["streams"][0] else 0,
            "mod_time": file_mod_time
        }

        # Update cache
        clip_info_cache[file_path] = info
        return info

    except Exception as e:
        print(f"Error getting info for {os.path.basename(file_path)}: {e}")
        return {"duration": 0, "width": 0, "height": 0, "mod_time": file_mod_time}


def analyze_clips(clips_folder):
    """Pre-analyze all clips at once to avoid repeated FFprobe calls."""
    clips = [os.path.join(clips_folder, f) for f in os.listdir(clips_folder)
             if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))] # Use .lower() for case insensitivity

    if not clips:
        print(f"No video clips found in {clips_folder} for analysis.")
        return []

    print(f"Analyzing {len(clips)} clips...")
    start_time = time.time()

    for clip in clips:
        if clip not in clip_info_cache or not clip_info_cache[clip].get("duration"):
            get_clip_info(clip)

    elapsed = time.time() - start_time
    print(f"Analysis complete in {elapsed:.2f} seconds")

    # Save the updated cache
    save_cache()

    return clips


def get_duration(file_path):
    """Get the duration of an audio or video file in seconds (using cache for videos)."""
    if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
        info = get_clip_info(file_path)
        if info and info.get("duration"):
            return info["duration"]

    # For audio files or if cache failed, use direct FFprobe call
    cmd = [
        FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration for {os.path.basename(file_path)}: {e}")
        return 0.0


def filter_clips_by_resolution(clips, target_resolution=None, tolerance=0.1):
    """Filter clips to match a target resolution or find the most common resolution."""
    if not clips:
        return []

    # Get all resolutions
    resolutions = {}
    for clip in clips:
        info = get_clip_info(clip)
        if not info:
            continue

        res_key = f"{info['width']}x{info['height']}"
        if info['width'] > 0 and info['height'] > 0:  # Skip clips with unknown or zero resolution
            resolutions[res_key] = resolutions.get(res_key, 0) + 1

    # If no target resolution provided, find the most common one
    if not target_resolution and resolutions:
        most_common_res = max(resolutions.items(), key=lambda x: x[1])[0]
        width, height = map(int, most_common_res.split('x'))
        target_resolution = {"width": width, "height": height}
        print(f"Using most common resolution for filtering: {width}x{height}")
    elif not target_resolution:
        print("Could not determine a target resolution from clips.")
        return clips  # Return all clips if we can't determine a resolution

    # Calculate acceptable range based on tolerance
    min_width = target_resolution["width"] * (1 - tolerance)
    max_width = target_resolution["width"] * (1 + tolerance)
    min_height = target_resolution["height"] * (1 - tolerance)
    max_height = target_resolution["height"] * (1 + tolerance)

    # Filter clips that match the resolution criteria
    filtered_clips = []
    for clip in clips:
        info = get_clip_info(clip)
        if not info:
            continue

        if (min_width <= info["width"] <= max_width and
                min_height <= info["height"] <= max_height):
            filtered_clips.append(clip)

    print(f"Filtered {len(filtered_clips)} clips matching resolution around {target_resolution['width']}x{target_resolution['height']}")
    return filtered_clips


def select_clips_for_voiceover(voiceover_duration, clips, min_clip_duration=1.0, max_clip_duration=None):
    """Select completely random clips to cover the voiceover duration."""
    if not clips:
        print("No video clips available to select from.")
        return []

    # Get all valid clips first
    valid_clips = []
    for clip in clips:
        info = get_clip_info(clip)
        if not info:
            continue

        duration = info["duration"]
        if duration >= min_clip_duration and (max_clip_duration is None or duration <= max_clip_duration):
            valid_clips.append((clip, duration))

    if not valid_clips:
        print("No valid clips after duration filtering.")
        return []

    # Ensure we have a good shuffle by using system random
    system_random = random.SystemRandom()  # Uses os.urandom internally
    system_random.shuffle(valid_clips)

    # Debug - print the first few clips to verify shuffle
    print("First few selected clips after shuffle:")
    for i, (clip, _) in enumerate(valid_clips[:min(5, len(valid_clips))]):
        print(f"  {i + 1}: {os.path.basename(clip)}")

    # Select clips until we reach the required duration
    selected_clips = []
    current_duration = 0

    # Create a deque for efficient popping from the beginning
    clips_deque = deque(valid_clips)

    while current_duration < voiceover_duration and clips_deque:
        clip, duration = clips_deque.popleft()
        selected_clips.append(clip)
        current_duration += duration

        # If we run out of clips, re-shuffle what we have and continue
        if not clips_deque and current_duration < voiceover_duration:
            print("Re-using clips to fill duration...")
            remaining_clips = [(c, get_clip_info(c)["duration"]) for c, _ in valid_clips] # Re-use original set of valid clips
            system_random.shuffle(remaining_clips)
            clips_deque.extend(remaining_clips)
            if not clips_deque: # If still no clips, break to avoid infinite loop
                print("Cannot find enough clips to match voiceover duration even with re-use.")
                break

    return selected_clips


def show_logo_gui(clips_folder=None, channel_name=None):
    """Show GUI popup for logo configuration and return settings

    Args:
        clips_folder: Path to clips folder for video preview
        channel_name: Name of the channel being processed (displayed in GUI title)
    """

    # If no GUI toolkit is available, skip configuration
    if not VIDEO_EDITOR_AVAILABLE and not LOGO_EDITOR_AVAILABLE and not PROFESSIONAL_GUI_AVAILABLE and not ENHANCED_GUI_AVAILABLE and not TKINTER_AVAILABLE and not PYQT5_AVAILABLE:
        print("")
        print("=" * 60)
        print("⚠️  VIDEO EDITOR UNAVAILABLE")
        print("=" * 60)
        print("No GUI toolkit available for video editing.")
        print("→ Continuing without changes...")
        print("=" * 60)
        print("")
        return None

    # === NEW: Use Video Editor Tool (best option - zoom, crop, pan + optional logo) ===
    if VIDEO_EDITOR_AVAILABLE and PYQT5_AVAILABLE and clips_folder:
        print("")
        print("=" * 60)
        print("🎬 VIDEO EDITOR - Zoom, Crop & Pan")
        print("=" * 60)
        print("→ Click on a video clip to preview")
        print("→ Zoom in to hide borders/watermarks")
        print("→ Drag to pan when zoomed")
        print("→ Optionally add logo overlay")
        print("=" * 60)
        print("")

        # Create app if not exists
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        dialog = VideoEditorDialog(clips_folder=clips_folder, channel_name=channel_name)
        dialog.exec_()
        config = dialog.get_config()
        return config

    # Fallback to old Logo Editor Tool
    if LOGO_EDITOR_AVAILABLE and PYQT5_AVAILABLE and clips_folder:
        print("")
        print("=" * 60)
        print("🎨 LOGO EDITOR - Visual Logo Positioning")
        print("=" * 60)
        print("→ Click on a video clip to preview")
        print("→ Select your logo file (PNG with transparency recommended)")
        print("→ Drag the logo to position it")
        print("→ Adjust size and opacity with sliders")
        print("=" * 60)
        print("")

        # Create app if not exists
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        dialog = LogoEditorDialog(clips_folder=clips_folder, channel_name=channel_name)
        dialog.exec_()
        config = dialog.get_config()
        return config

    # Use professional GUI if available (tkinter-based)
    elif PROFESSIONAL_GUI_AVAILABLE and clips_folder:
        print("Loading Professional Logo Studio with accurate positioning...")
        gui = ProfessionalLogoGUI(video_clips_folder=clips_folder)
        gui.root.mainloop()
        config = gui.get_config()
        gui.cleanup()
        return config

    # Use enhanced GUI as third option
    elif ENHANCED_GUI_AVAILABLE and clips_folder:
        print("Loading enhanced logo preview with video frame...")
        gui = LogoPreviewGUI(video_clips_folder=clips_folder)
        gui.root.mainloop()
        config = gui.get_config()
        gui.cleanup()
        return config

    # Fall back to inline PyQt5 GUI if available (for embedded Python without tkinter)
    elif PYQT5_AVAILABLE and not TKINTER_AVAILABLE:
        print("Using PyQt5 visual logo editor...")

        class VisualLogoEditor(QDialog):
            """Visual logo editor - drag logo on video frame to position"""

            def __init__(self, clips_folder=None, channel_name=None):
                # Create app if not exists
                self.app = QApplication.instance()
                if not self.app:
                    self.app = QApplication([])

                super().__init__()
                # Show channel name in title if provided
                if channel_name:
                    self.setWindowTitle(f"🎨 Logo Editor for: {channel_name}")
                else:
                    self.setWindowTitle("Visual Logo Editor - Drag to Position")
                self.setMinimumSize(900, 700)

                self.clips_folder = clips_folder
                self.channel_name = channel_name
                self.use_logo = False
                self.logo_path = ""
                self.size_percent = 10
                self.opacity_percent = 80

                # Logo position (relative 0-1)
                self.logo_x = 0.85  # Right side
                self.logo_y = 0.85  # Bottom

                # Video frame data
                self.video_frame = None
                self.video_width = 1920
                self.video_height = 1080
                self.logo_image = None
                self.logo_original = None

                # For dragging
                self.dragging = False
                self.drag_offset_x = 0
                self.drag_offset_y = 0

                self.load_video_frame()
                self.create_widgets()

            def load_video_frame(self):
                """Load a frame from the first video clip"""
                if not self.clips_folder or not CV2_AVAILABLE:
                    return

                clips_path = Path(self.clips_folder)
                video_files = list(clips_path.glob("*.mp4")) + list(clips_path.glob("*.mov"))

                if video_files:
                    try:
                        cap = cv2.VideoCapture(str(video_files[0]))
                        # Seek to middle of video for better frame
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                        ret, frame = cap.read()
                        if ret:
                            self.video_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            self.video_height, self.video_width = frame.shape[:2]
                        cap.release()
                    except Exception as e:
                        print(f"Could not load video frame: {e}")

            def create_widgets(self):
                layout = QVBoxLayout()

                # Channel name header (if provided)
                if self.channel_name:
                    channel_label = QLabel(f"📺 SELECT LOGO FOR: {self.channel_name}")
                    channel_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ff00; background-color: #1a3a1a; padding: 10px; border-radius: 5px;")
                    channel_label.setAlignment(Qt.AlignCenter)
                    layout.addWidget(channel_label)

                # Title
                title = QLabel("Drag the logo to position it on your video")
                title.setStyleSheet("font-size: 14px; font-weight: bold;")
                title.setAlignment(Qt.AlignCenter)
                layout.addWidget(title)

                # Preview area - custom widget for dragging
                self.preview_label = QLabel()
                self.preview_label.setMinimumSize(800, 450)
                self.preview_label.setAlignment(Qt.AlignCenter)
                self.preview_label.setStyleSheet("background-color: #1a1a1a; border: 2px solid #333;")
                self.preview_label.mousePressEvent = self.on_mouse_press
                self.preview_label.mouseMoveEvent = self.on_mouse_move
                self.preview_label.mouseReleaseEvent = self.on_mouse_release
                layout.addWidget(self.preview_label)

                # Controls row
                controls_layout = QHBoxLayout()

                # Logo file selection
                file_group = QGroupBox("Logo File")
                file_layout = QHBoxLayout()
                self.path_edit = QLineEdit()
                self.path_edit.setPlaceholderText("Select logo file (PNG recommended)...")
                browse_btn = QPushButton("Browse")
                browse_btn.clicked.connect(self.browse_logo)
                file_layout.addWidget(self.path_edit)
                file_layout.addWidget(browse_btn)
                file_group.setLayout(file_layout)
                controls_layout.addWidget(file_group, 2)

                # Size slider
                size_group = QGroupBox("Size: 10%")
                self.size_group = size_group
                size_layout = QVBoxLayout()
                self.size_slider = QSlider(Qt.Horizontal)
                self.size_slider.setRange(3, 40)
                self.size_slider.setValue(10)
                self.size_slider.valueChanged.connect(self.on_size_change)
                size_layout.addWidget(self.size_slider)
                size_group.setLayout(size_layout)
                controls_layout.addWidget(size_group, 1)

                # Opacity slider
                opacity_group = QGroupBox("Opacity: 80%")
                self.opacity_group = opacity_group
                opacity_layout = QVBoxLayout()
                self.opacity_slider = QSlider(Qt.Horizontal)
                self.opacity_slider.setRange(20, 100)
                self.opacity_slider.setValue(80)
                self.opacity_slider.valueChanged.connect(self.on_opacity_change)
                opacity_layout.addWidget(self.opacity_slider)
                opacity_group.setLayout(opacity_layout)
                controls_layout.addWidget(opacity_group, 1)

                layout.addLayout(controls_layout)

                # Position info
                self.pos_label = QLabel("Position: Bottom-Right (drag logo to move)")
                self.pos_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(self.pos_label)

                # Buttons
                btn_layout = QHBoxLayout()
                apply_btn = QPushButton("Apply Logo")
                apply_btn.setStyleSheet("background-color: #2e7d32; color: white; padding: 12px 30px; font-size: 14px;")
                apply_btn.clicked.connect(self.apply_logo)
                skip_btn = QPushButton("Skip Logo")
                skip_btn.setStyleSheet("background-color: #666; color: white; padding: 12px 30px; font-size: 14px;")
                skip_btn.clicked.connect(self.skip_logo)
                btn_layout.addStretch()
                btn_layout.addWidget(apply_btn)
                btn_layout.addWidget(skip_btn)
                btn_layout.addStretch()
                layout.addLayout(btn_layout)

                self.setLayout(layout)
                self.update_preview()

            def browse_logo(self):
                path, _ = QFileDialog.getOpenFileName(
                    self, "Select Logo File", "",
                    "Image files (*.png *.jpg *.jpeg);;PNG files (*.png);;All files (*.*)"
                )
                if path:
                    self.path_edit.setText(path)
                    self.load_logo(path)

            def load_logo(self, path):
                """Load logo image"""
                if not CV2_AVAILABLE:
                    # Can't load logo preview without cv2, but still allow selection
                    self.logo_original = "placeholder"  # Mark as selected
                    self.update_preview()
                    return

                try:
                    # Load with alpha channel if available
                    self.logo_original = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                    if self.logo_original is not None:
                        # Convert BGR to RGB (keep alpha if present)
                        if len(self.logo_original.shape) == 3:
                            if self.logo_original.shape[2] == 4:
                                self.logo_original = cv2.cvtColor(self.logo_original, cv2.COLOR_BGRA2RGBA)
                            else:
                                self.logo_original = cv2.cvtColor(self.logo_original, cv2.COLOR_BGR2RGB)
                        self.update_preview()
                except Exception as e:
                    print(f"Error loading logo: {e}")

            def on_size_change(self, value):
                self.size_percent = value
                self.size_group.setTitle(f"Size: {value}%")
                self.update_preview()

            def on_opacity_change(self, value):
                self.opacity_percent = value
                self.opacity_group.setTitle(f"Opacity: {value}%")
                self.update_preview()

            def update_preview(self):
                """Update the preview with video frame and logo overlay"""
                from PyQt5.QtGui import QImage, QPixmap, QColor, QPainter, QFont

                # Get preview dimensions
                preview_w = self.preview_label.width() - 4
                preview_h = self.preview_label.height() - 4
                if preview_w < 100 or preview_h < 100:
                    preview_w, preview_h = 800, 450

                # Check if cv2/numpy are available
                if not CV2_AVAILABLE or np is None:
                    # Create simple placeholder using Qt
                    pixmap = QPixmap(preview_w, preview_h)
                    pixmap.fill(QColor(40, 40, 40))
                    painter = QPainter(pixmap)
                    painter.setPen(QColor(100, 100, 100))
                    painter.setFont(QFont("Arial", 14))
                    painter.drawText(preview_w//2 - 100, preview_h//2, "Video Preview (Select logo to continue)")
                    painter.end()
                    self.preview_label.setPixmap(pixmap)
                    self.preview_width = preview_w
                    self.preview_height = preview_h
                    return

                # Create base image
                if self.video_frame is not None:
                    # Scale video frame to fit preview
                    scale = min(preview_w / self.video_width, preview_h / self.video_height)
                    new_w = int(self.video_width * scale)
                    new_h = int(self.video_height * scale)
                    frame = cv2.resize(self.video_frame, (new_w, new_h))
                else:
                    # Create placeholder
                    new_w, new_h = preview_w, preview_h
                    frame = np.zeros((new_h, new_w, 3), dtype=np.uint8)
                    frame[:] = (40, 40, 40)
                    # Draw text
                    cv2.putText(frame, "Video Preview", (new_w//2 - 80, new_h//2),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)

                self.preview_width = new_w
                self.preview_height = new_h

                # Overlay logo if loaded (and is actual image data, not placeholder)
                if self.logo_original is not None and not isinstance(self.logo_original, str):
                    # Calculate logo size
                    logo_w = int(new_w * self.size_percent / 100)
                    logo_h = int(logo_w * self.logo_original.shape[0] / self.logo_original.shape[1])

                    # Resize logo
                    logo_resized = cv2.resize(self.logo_original, (logo_w, logo_h))

                    # Calculate position
                    logo_x = int(self.logo_x * new_w - logo_w / 2)
                    logo_y = int(self.logo_y * new_h - logo_h / 2)

                    # Clamp to bounds
                    logo_x = max(0, min(logo_x, new_w - logo_w))
                    logo_y = max(0, min(logo_y, new_h - logo_h))

                    # Store for hit testing
                    self.logo_rect = (logo_x, logo_y, logo_w, logo_h)

                    # Overlay with opacity
                    opacity = self.opacity_percent / 100.0
                    self.overlay_logo(frame, logo_resized, logo_x, logo_y, opacity)

                # Convert to QPixmap
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                from PyQt5.QtGui import QImage, QPixmap
                q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)
                self.preview_label.setPixmap(pixmap)

            def overlay_logo(self, frame, logo, x, y, opacity):
                """Overlay logo onto frame with opacity"""
                h, w = logo.shape[:2]
                fh, fw = frame.shape[:2]

                # Ensure bounds
                if x < 0 or y < 0 or x + w > fw or y + h > fh:
                    return

                if len(logo.shape) == 3 and logo.shape[2] == 4:
                    # Has alpha channel
                    alpha = (logo[:, :, 3] / 255.0) * opacity
                    for c in range(3):
                        frame[y:y+h, x:x+w, c] = (
                            alpha * logo[:, :, c] +
                            (1 - alpha) * frame[y:y+h, x:x+w, c]
                        ).astype(np.uint8)
                else:
                    # No alpha
                    frame[y:y+h, x:x+w] = cv2.addWeighted(
                        logo[:, :, :3], opacity,
                        frame[y:y+h, x:x+w], 1 - opacity, 0
                    )

            def on_mouse_press(self, event):
                """Start dragging if clicking on logo"""
                if self.logo_original is None or not hasattr(self, 'logo_rect'):
                    return

                # Get click position relative to preview
                lx, ly, lw, lh = self.logo_rect
                mx = event.pos().x() - (self.preview_label.width() - self.preview_width) // 2
                my = event.pos().y() - (self.preview_label.height() - self.preview_height) // 2

                if lx <= mx <= lx + lw and ly <= my <= ly + lh:
                    self.dragging = True
                    self.drag_offset_x = mx - (lx + lw // 2)
                    self.drag_offset_y = my - (ly + lh // 2)

            def on_mouse_move(self, event):
                """Update logo position while dragging"""
                if not self.dragging:
                    return

                mx = event.pos().x() - (self.preview_label.width() - self.preview_width) // 2
                my = event.pos().y() - (self.preview_label.height() - self.preview_height) // 2

                # Update relative position
                self.logo_x = (mx - self.drag_offset_x) / self.preview_width
                self.logo_y = (my - self.drag_offset_y) / self.preview_height

                # Clamp
                self.logo_x = max(0.05, min(0.95, self.logo_x))
                self.logo_y = max(0.05, min(0.95, self.logo_y))

                self.update_position_label()
                self.update_preview()

            def on_mouse_release(self, event):
                """Stop dragging"""
                self.dragging = False

            def update_position_label(self):
                """Update position text based on logo location"""
                # Determine quadrant
                if self.logo_x < 0.33:
                    h_pos = "Left"
                elif self.logo_x > 0.66:
                    h_pos = "Right"
                else:
                    h_pos = "Center"

                if self.logo_y < 0.33:
                    v_pos = "Top"
                elif self.logo_y > 0.66:
                    v_pos = "Bottom"
                else:
                    v_pos = "Middle"

                self.pos_label.setText(f"Position: {v_pos}-{h_pos} ({int(self.logo_x*100)}%, {int(self.logo_y*100)}%)")

            def get_position_name(self):
                """Convert relative position to named position"""
                # Map to standard positions for ffmpeg filter
                if self.logo_x < 0.33:
                    if self.logo_y < 0.33:
                        return "top-left"
                    elif self.logo_y > 0.66:
                        return "bottom-left"
                    else:
                        return "left"
                elif self.logo_x > 0.66:
                    if self.logo_y < 0.33:
                        return "top-right"
                    elif self.logo_y > 0.66:
                        return "bottom-right"
                    else:
                        return "right"
                else:
                    if self.logo_y < 0.33:
                        return "top"
                    elif self.logo_y > 0.66:
                        return "bottom"
                    else:
                        return "center"

            def apply_logo(self):
                if not self.path_edit.text():
                    QMessageBox.critical(self, "Error", "Please select a logo file!")
                    return
                if not os.path.exists(self.path_edit.text()):
                    QMessageBox.critical(self, "Error", "Logo file does not exist!")
                    return
                self.use_logo = True
                self.logo_path = self.path_edit.text()
                self.accept()

            def skip_logo(self):
                self.use_logo = False
                self.reject()

            def get_config(self):
                if not self.use_logo:
                    return None

                # Calculate padding based on position
                # Use relative position for more accurate placement
                position = self.get_position_name()

                return {
                    "logo_path": self.logo_path,
                    "position": position,
                    "size_percent": self.size_percent,
                    "opacity_percent": self.opacity_percent,
                    "padding_pixels": 20,
                    "relative_x": self.logo_x,
                    "relative_y": self.logo_y
                }

        dialog = VisualLogoEditor(clips_folder=clips_folder, channel_name=channel_name)
        dialog.exec_()
        return dialog.get_config()

    # Fall back to basic tkinter GUI
    elif TKINTER_AVAILABLE:
        print("Using tkinter logo configuration dialog...")

        # Basic GUI implementation (original code)
        class LogoGUI:
            def __init__(self):
                self.root = tk.Tk()
                self.root.title("Add Logo to Video")
                self.root.geometry("450x500")

                # Center the window on screen
                self.root.update_idletasks()
                width = self.root.winfo_width()
                height = self.root.winfo_height()
                x = (self.root.winfo_screenwidth() // 2) - (width // 2)
                y = (self.root.winfo_screenheight() // 2) - (height // 2)
                self.root.geometry(f'{width}x{height}+{x}+{y}')

                # Logo settings
                self.use_logo = False
                self.logo_path = tk.StringVar()
                self.position = tk.StringVar(value="bottom-right")
                self.size_percent = tk.IntVar(value=10)
                self.opacity_percent = tk.IntVar(value=80)
                self.padding_pixels = tk.IntVar(value=20)

                self.create_widgets()

            def create_widgets(self):
                # Title
                title = tk.Label(self.root, text="Add Logo Watermark",
                               font=("Arial", 14, "bold"))
                title.pack(pady=10)

                # Logo file selection
                file_frame = tk.Frame(self.root)
                file_frame.pack(pady=10, padx=20, fill="x")

                tk.Label(file_frame, text="Logo:").pack(side="left")
                tk.Entry(file_frame, textvariable=self.logo_path, width=25).pack(side="left", padx=5)
                tk.Button(file_frame, text="Browse", command=self.browse_logo).pack(side="left")

                # Position selection
                tk.Label(self.root, text="Select Position:", font=("Arial", 11)).pack(pady=10)

                position_frame = tk.Frame(self.root)
                position_frame.pack(pady=5)

                # Create 3x3 grid of position buttons
                positions = [
                    ["top-left", "top", "top-right"],
                    ["left", "center", "right"],
                    ["bottom-left", "bottom", "bottom-right"]
                ]

                for row_idx, row in enumerate(positions):
                    for col_idx, pos in enumerate(row):
                        btn = tk.Radiobutton(
                            position_frame,
                            text=pos.replace("-", "\n"),
                            variable=self.position,
                            value=pos,
                            indicatoron=0,
                            width=8,
                            height=2,
                            bg="lightgray",
                            selectcolor="lightgreen"
                        )
                        btn.grid(row=row_idx, column=col_idx, padx=2, pady=2)

                # Size slider
                size_label = tk.Label(self.root, text=f"Size: {self.size_percent.get()}%")
                size_label.pack(pady=(15,5))

                size_scale = tk.Scale(
                    self.root,
                    from_=5, to=30,
                    orient="horizontal",
                    variable=self.size_percent,
                    command=lambda v: size_label.config(text=f"Size: {int(float(v))}%"),
                    length=250
                )
                size_scale.pack()

                # Opacity slider
                opacity_label = tk.Label(self.root, text=f"Opacity: {self.opacity_percent.get()}%")
                opacity_label.pack(pady=(15,5))

                opacity_scale = tk.Scale(
                    self.root,
                    from_=20, to=100,
                    orient="horizontal",
                    variable=self.opacity_percent,
                    command=lambda v: opacity_label.config(text=f"Opacity: {int(float(v))}%"),
                    length=250
                )
                opacity_scale.pack()

                # Buttons
                button_frame = tk.Frame(self.root)
                button_frame.pack(pady=30)

                tk.Button(button_frame, text="Apply Logo",
                         command=self.apply_logo,
                         bg="green", fg="white",
                         width=12, height=2).pack(side="left", padx=5)

                tk.Button(button_frame, text="Skip Logo",
                         command=self.skip_logo,
                         bg="gray", fg="white",
                         width=12, height=2).pack(side="left", padx=5)

            def browse_logo(self):
                filename = filedialog.askopenfilename(
                    title="Select Logo File",
                    filetypes=[
                        ("Image files", "*.png *.jpg *.jpeg"),
                        ("PNG files", "*.png"),
                        ("All files", "*.*")
                    ]
                )
                if filename:
                    self.logo_path.set(filename)

            def apply_logo(self):
                if not self.logo_path.get():
                    messagebox.showerror("Error", "Please select a logo file!")
                    return

                if not os.path.exists(self.logo_path.get()):
                    messagebox.showerror("Error", "Logo file does not exist!")
                    return

                self.use_logo = True
                self.root.quit()
                self.root.destroy()

            def skip_logo(self):
                self.use_logo = False
                self.root.quit()
                self.root.destroy()

            def get_config(self):
                if not self.use_logo:
                    return None

                return {
                    "logo_path": self.logo_path.get(),
                    "position": self.position.get(),
                    "size_percent": self.size_percent.get(),
                    "opacity_percent": self.opacity_percent.get(),
                    "padding_pixels": self.padding_pixels.get()
                }

        # Create and run GUI
        gui = LogoGUI()
        gui.root.mainloop()
        return gui.get_config()


def get_overlay_position(position, padding):
    """Convert position name to FFmpeg overlay coordinates"""
    overlay_positions = {
        "top-left": f"{padding}:{padding}",
        "top": f"(W-w)/2:{padding}",
        "top-right": f"W-w-{padding}:{padding}",
        "left": f"{padding}:(H-h)/2",
        "center": f"(W-w)/2:(H-h)/2",
        "right": f"W-w-{padding}:(H-h)/2",
        "bottom-left": f"{padding}:H-h-{padding}",
        "bottom": f"(W-w)/2:H-h-{padding}",
        "bottom-right": f"W-w-{padding}:H-h-{padding}"
    }

    return overlay_positions.get(position, f"W-w-{padding}:H-h-{padding}")


def detect_gpu_acceleration():
    """Detect available GPU hardware acceleration"""
    gpu_info = {
        "nvidia": False,
        "intel": False,
        "amd": False,
        "encoder": "libx264",  # Default CPU encoder
        "decoder": None,
        "hw_accel": None
    }

    try:
        # Check for NVIDIA GPU (CUDA/NVENC)
        result = subprocess.run([FFMPEG_PATH, '-hide_banner', '-encoders'],
                              capture_output=True, text=True, timeout=5)
        encoders_output = result.stdout

        if 'h264_nvenc' in encoders_output:
            gpu_info["nvidia"] = True
            gpu_info["encoder"] = "h264_nvenc"
            gpu_info["hw_accel"] = "cuda"
            print("✓ NVIDIA GPU detected - Using NVENC hardware encoding")
        elif 'h264_qsv' in encoders_output:
            gpu_info["intel"] = True
            gpu_info["encoder"] = "h264_qsv"
            gpu_info["hw_accel"] = "qsv"
            print("✓ Intel QuickSync detected - Using QSV hardware encoding")
        elif 'h264_amf' in encoders_output:
            gpu_info["amd"] = True
            gpu_info["encoder"] = "h264_amf"
            gpu_info["hw_accel"] = "d3d11va"
            print("✓ AMD GPU detected - Using AMF hardware encoding")
        else:
            print("ℹ No GPU acceleration detected - Using CPU encoding")

    except Exception as e:
        print(f"Could not detect GPU: {e}")

    return gpu_info


# Cache GPU detection result
GPU_INFO = None

def create_video_from_voiceover(voiceover_path, clips, output_folder, use_copy=True):
    """Create a video from a voiceover file using clips with GPU acceleration."""
    global GPU_INFO

    if not clips:
        print("No video clips available.")
        return False

    # Detect GPU on first run
    if GPU_INFO is None:
        GPU_INFO = detect_gpu_acceleration()

    # Get voiceover duration
    voiceover_duration = get_duration(voiceover_path)
    if voiceover_duration <= 0:
        print(f"Could not determine voiceover duration or it's zero for {os.path.basename(voiceover_path)}. Skipping.")
        return False
    print(f"Voiceover duration: {voiceover_duration:.2f} seconds")

    # Select clips with completely random strategy
    selected_clips = select_clips_for_voiceover(
        voiceover_duration,
        clips,
        min_clip_duration=1.0 # Ensure clips are at least 1 second
    )

    if not selected_clips:
        print("Failed to select clips for the voiceover.")
        return False

    print(f"Using {len(selected_clips)} clips to cover the voiceover duration.")

    # Display selected clips for debugging
    for i, clip in enumerate(selected_clips, 1):
        info = get_clip_info(clip)
        # Ensure info is not None before accessing its keys
        duration_str = f"{info['duration']:.2f}s" if info and 'duration' in info else "N/A"
        print(f"  Clip {i}: {os.path.basename(clip)} - {duration_str}")


    # Create temporary folder for processed clips if needed
    temp_dir = os.path.join(output_folder, "temp_concat")
    os.makedirs(temp_dir, exist_ok=True)

    # Use timestamp in concat file name to avoid any caching issues
    timestamp = int(time.time())
    temp_concat_file = os.path.join(temp_dir, f"concat_list_{timestamp}.txt")

    with open(temp_concat_file, "w", encoding='utf-8') as f: # Added encoding
        for clip in selected_clips:
            # Escape single quotes in filenames for ffmpeg concat
            escaped_clip = clip.replace("'", "'\\''")
            f.write(f"file '{escaped_clip}'\n")

    # Get voiceover filename without extension
    voiceover_name = os.path.splitext(os.path.basename(voiceover_path))[0]
    output_path = os.path.join(output_folder, f"{voiceover_name}.mp4")

    print(f"Creating video: {output_path}")

    # Check if logo should be added (using global logo_config)
    global logo_config

    # Common FFmpeg arguments with GPU acceleration if available
    ffmpeg_base_cmd = [FFMPEG_PATH, "-y"]

    # Check if we need filters (crop or logo)
    needs_filters = (logo_config and (logo_config.get("logo_path") or logo_config.get('has_crop', False) or logo_config.get('zoom_level', 1.0) > 1.0))

    # Add hardware acceleration flags if GPU detected
    # BUT: Skip hardware DECODING when using filters (crop/scale/logo don't work with CUDA memory)
    # We'll still use hardware ENCODING later
    if GPU_INFO and GPU_INFO["hw_accel"] and not needs_filters:
        if GPU_INFO["nvidia"]:
            # NVIDIA CUDA acceleration
            ffmpeg_base_cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
        elif GPU_INFO["intel"]:
            # Intel QuickSync acceleration
            ffmpeg_base_cmd.extend(["-hwaccel", "qsv"])
        elif GPU_INFO["amd"]:
            # AMD acceleration
            ffmpeg_base_cmd.extend(["-hwaccel", "d3d11va"])

    # Add input files
    ffmpeg_base_cmd.extend([
        "-f", "concat", "-safe", "0",  # For concat demuxer
        "-i", temp_concat_file,
        "-i", voiceover_path
    ])

    # Determine encoder to use
    encoder = GPU_INFO["encoder"] if GPU_INFO else "libx264"

    # Check if we have crop/zoom settings from Video Editor
    has_crop = logo_config and logo_config.get('has_crop', False)
    has_zoom = logo_config and logo_config.get('zoom_level', 1.0) > 1.0  # Legacy support
    has_logo = logo_config and logo_config.get("logo_path")

    # Build crop filter if needed
    crop_filter = ""
    base_w, base_h = 1920, 1080  # Standard HD output

    if has_crop:
        # New visual crop selection format - values are in pixels
        crop_x = logo_config.get('crop_x', 0)
        crop_y = logo_config.get('crop_y', 0)
        crop_w = logo_config.get('crop_w', base_w)
        crop_h = logo_config.get('crop_h', base_h)

        # Crop then scale back to original 1920x1080
        # Add format=yuv420p to ensure compatibility with encoders
        crop_filter = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={base_w}:{base_h},format=yuv420p"
        print(f"  Crop: {crop_w}x{crop_h} at ({crop_x}, {crop_y}) -> scale to {base_w}x{base_h}")
    elif has_zoom:
        # Legacy zoom/pan format
        zoom_level = logo_config.get('zoom_level', 1.0)
        pan_x = logo_config.get('pan_x', 0.5)
        pan_y = logo_config.get('pan_y', 0.5)

        # For 1920x1080 video, calculate exact pixel values
        crop_w = int(base_w / zoom_level)
        crop_h = int(base_h / zoom_level)

        # Calculate crop position based on pan (0-1 range, 0.5 = center)
        max_x = base_w - crop_w
        max_y = base_h - crop_h
        crop_x = int(pan_x * max_x)
        crop_y = int(pan_y * max_y)

        # Crop then scale back to original 1920x1080
        crop_filter = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={base_w}:{base_h},format=yuv420p"
        print(f"  Zoom: {zoom_level:.0%}, Pan: ({pan_x:.2f}, {pan_y:.2f})")
        print(f"  Crop: {crop_w}x{crop_h} at ({crop_x}, {crop_y}) -> scale to {base_w}x{base_h}")

    # Add logo input if configured
    if has_logo:
        ffmpeg_base_cmd.extend(["-i", logo_config["logo_path"]])

        # Build filter complex for logo overlay
        # Check for new Video Editor format vs old Logo Editor format
        if 'logo_size_percent' in logo_config:
            # New Video Editor format
            size_percent = logo_config['logo_size_percent'] / 100.0
            opacity = logo_config.get('logo_opacity', 90) / 100.0
            logo_x = logo_config.get('logo_x', 0.9)
            logo_y = logo_config.get('logo_y', 0.1)
            # Calculate position expression for ffmpeg
            overlay_pos = f"W*{logo_x}-w/2:H*{logo_y}-h/2"
            video_width = 1920  # Assume HD
            logo_width_pixels = int(video_width * size_percent)
            print(f"  🎨 Logo size: {logo_width_pixels}px, Position: ({logo_x:.2f}, {logo_y:.2f})")
        else:
            # Old Logo Editor format
            size_percent = logo_config['size_percent'] / 100.0
            opacity = logo_config['opacity_percent'] / 100.0

            # Calculate EXACT logo width in pixels
            if 'logo_width_actual' in logo_config:
                logo_width_pixels = logo_config['logo_width_actual']
                print(f"  🎨 Using exact logo width from GUI: {logo_width_pixels}px")
            else:
                video_width = logo_config.get('actual_video_width', 1920)
                logo_width_pixels = int(video_width * size_percent)
                print(f"  🎨 Calculated logo width: {logo_width_pixels}px ({int(size_percent*100)}% of {video_width}px)")

            # Check if we have exact position expressions
            if 'position_x_expr' in logo_config and 'position_y_expr' in logo_config:
                overlay_pos = f"{logo_config['position_x_expr']}:{logo_config['position_y_expr']}"
                print(f"  📍 Using EXACT positioning: X={logo_config['position_x_expr']}, Y={logo_config['position_y_expr']}")
            else:
                overlay_pos = get_overlay_position(logo_config['position'], logo_config['padding_pixels'])
                print(f"  📍 Using SIMPLE positioning: {overlay_pos}")

        # Build filter - combine crop and logo if both present
        if has_crop or has_zoom:
            # Crop + Logo: apply crop first, then overlay logo
            filter_complex = (
                f"[0:v]{crop_filter}[cropped];"  # Apply crop to video
                f"[2:v]scale={logo_width_pixels}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"  # Prepare logo
                f"[cropped][logo]overlay={overlay_pos}[v]"  # Overlay logo on cropped video
            )
        else:
            # Logo only
            filter_complex = (
                f"[2:v]scale={logo_width_pixels}:-1,"  # Scale logo to exact pixels
                f"format=rgba,"  # Ensure alpha channel
                f"colorchannelmixer=aa={opacity}[logo];"  # Apply opacity
                f"[0:v][logo]overlay={overlay_pos}[v]"  # Overlay on video
            )

        print(f"  💧 Opacity: {int(opacity*100)}%")

        # Build encoding parameters based on GPU
        if GPU_INFO and GPU_INFO["nvidia"]:
            encode_params = [
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", "0"
            ]
        elif GPU_INFO and GPU_INFO["intel"]:
            encode_params = [
                "-c:v", "h264_qsv",
                "-preset", "medium",
                "-global_quality", "23"
            ]
        elif GPU_INFO and GPU_INFO["amd"]:
            encode_params = [
                "-c:v", "h264_amf",
                "-quality", "balanced",
                "-rc", "vbr_latency"
            ]
        else:
            encode_params = [
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22"
            ]

        cmd = ffmpeg_base_cmd + [
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "1:a"
        ] + encode_params + ["-shortest", output_path]

        print(f"Adding logo: {Path(logo_config['logo_path']).name}")
        if GPU_INFO and GPU_INFO["hw_accel"]:
            print(f"  ⚡ GPU ENCODING: {encoder}")
        else:
            print(f"  CPU encoding: {encoder}")

    elif has_crop or has_zoom:
        # Crop only (no logo) - apply crop filter
        print(f"  Applying crop only (no logo)")

        # Build encoding parameters
        if GPU_INFO and GPU_INFO["nvidia"]:
            encode_params = [
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", "0"
            ]
        elif GPU_INFO and GPU_INFO["intel"]:
            encode_params = [
                "-c:v", "h264_qsv",
                "-preset", "medium",
                "-global_quality", "23"
            ]
        elif GPU_INFO and GPU_INFO["amd"]:
            encode_params = [
                "-c:v", "h264_amf",
                "-quality", "balanced",
                "-rc", "vbr_latency"
            ]
        else:
            encode_params = [
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22"
            ]

        cmd = ffmpeg_base_cmd + [
            "-vf", crop_filter,
            "-map", "0:v:0", "-map", "1:a:0"
        ] + encode_params + ["-shortest", output_path]

        if GPU_INFO and GPU_INFO["hw_accel"]:
            print(f"  ⚡ GPU ENCODING: {encoder}")
        else:
            print(f"  CPU encoding: {encoder}")

    elif use_copy and not (GPU_INFO and GPU_INFO["hw_accel"]):
        # Fast mode - just copy video streams (only when no GPU)
        cmd = ffmpeg_base_cmd + [
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", output_path
        ]
    else:
        # Quality mode with GPU or CPU encoding
        if GPU_INFO and GPU_INFO["nvidia"]:
            encode_params = [
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", "0"
            ]
        elif GPU_INFO and GPU_INFO["intel"]:
            encode_params = [
                "-c:v", "h264_qsv",
                "-preset", "medium",
                "-global_quality", "23"
            ]
        elif GPU_INFO and GPU_INFO["amd"]:
            encode_params = [
                "-c:v", "h264_amf",
                "-quality", "balanced",
                "-rc", "vbr_latency"
            ]
        else:
            encode_params = [
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22"
            ]

        cmd = ffmpeg_base_cmd + [
            "-map", "0:v:0", "-map", "1:a:0"
        ] + encode_params + ["-shortest", output_path]

    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True, encoding='utf-8') # Added capture_output to see ffmpeg errors
        print(f"Created video: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating video (FFmpeg return code {e.returncode}):")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Error: FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during video creation: {e}")
        return False
    finally:
        # Clean up temporary files
        if os.path.exists(temp_concat_file):
            os.remove(temp_concat_file)
        if os.path.exists(temp_dir) and not os.listdir(temp_dir): # Remove temp_dir if empty
            os.rmdir(temp_dir)


def main():
    # Make an entirely new random seed on every run
    seed_value = int.from_bytes(os.urandom(8), byteorder='big')
    random.seed(seed_value)
    print(f"Using fresh random seed: {seed_value}")

    parser = argparse.ArgumentParser(description="Create videos from voiceovers using clips.")
    # Paths are now required arguments
    parser.add_argument("--voiceovers", required=True, help="Path to folder containing voiceover MP3 files")
    parser.add_argument("--clips", required=True, help="Path to folder containing video clips")
    parser.add_argument("--output", required=True, help="Path to output folder for created videos")
    parser.add_argument("--skip-resolution-match", action="store_true", help="Skip filtering clips by resolution")
    parser.add_argument("--quality", action="store_true", help="Use higher quality but slower encoding (re-encodes video)")
    parser.add_argument("--refresh-cache", action="store_true", help="Force refresh of clip info cache")
    parser.add_argument("--single", help="Process only a single voiceover file (specify filename)")
    parser.add_argument("--cache-file", type=str, default=None,
                        help="Path to the JSON file for caching clip info. Recommended for orchestrator use.")
    parser.add_argument("--channel-name", type=str, default=None,
                        help="Name of the channel being processed (shown in logo GUI)")

    args = parser.parse_args()

    # Set the global cache file path
    global _CACHE_FILE_PATH
    if args.cache_file:
        _CACHE_FILE_PATH = args.cache_file
        # Ensure the directory for the cache file exists
        os.makedirs(os.path.dirname(_CACHE_FILE_PATH), exist_ok=True)
    else:
        # Fallback to a default if not provided via CLI, but make it project specific
        # This fallback is unlikely to be hit if orchestrator always provides it
        _CACHE_FILE_PATH = os.path.join(args.output, "assemble_cache.json")
        os.makedirs(os.path.dirname(_CACHE_FILE_PATH), exist_ok=True)
        print(f"Warning: No --cache-file specified, using '{_CACHE_FILE_PATH}' as fallback.")


    voiceovers_folder = args.voiceovers
    clips_folder = args.clips
    output_folder = args.output
    use_copy = not args.quality  # Fast mode by default

    # Check if folders exist and exit if not (now sys.exit(1) for orchestrator to catch)
    if not os.path.isdir(voiceovers_folder):
        print(f"Error: Voiceovers folder not found: {voiceovers_folder}")
        sys.exit(1) # Signal failure
    if not os.path.isdir(clips_folder):
        print(f"Error: Clips folder not found: {clips_folder}")
        sys.exit(1)

    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Show logo GUI popup and get configuration (only if enabled)
    global logo_config
    channel_name = args.channel_name if hasattr(args, 'channel_name') and args.channel_name else None
    if ENABLE_LOGO_FEATURE:
        print("\n=== Logo Configuration ===")
        if channel_name:
            print(f"📺 Channel: {channel_name}")
        print("Opening logo configuration window...")
        # Pass clips_folder for enhanced preview and channel_name for display
        logo_config = show_logo_gui(clips_folder=clips_folder, channel_name=channel_name)

        if logo_config and logo_config.get('logo_path'):
            print(f"Logo will be added: {Path(logo_config['logo_path']).name}")
            if 'position' in logo_config:
                print(f"Position: {logo_config['position']}, Size: {logo_config['size_percent']}%, Opacity: {logo_config['opacity_percent']}%")
            else:
                # New video editor format
                if logo_config.get('has_crop'):
                    print(f"Crop: {logo_config.get('crop_w', 0)}x{logo_config.get('crop_h', 0)} at ({logo_config.get('crop_x', 0)}, {logo_config.get('crop_y', 0)})")
                print(f"Logo Size: {logo_config.get('logo_size_percent', 12)}%")

            # Clean up old videos with different logo to prevent confusion
            print("Cleaning up old videos to ensure fresh logo application...")
            existing_videos = list(Path(output_folder).glob("*.mp4"))
            if existing_videos:
                for old_video in existing_videos:
                    try:
                        old_video.unlink()
                        print(f"   Removed: {old_video.name}")
                    except:
                        pass
                print(f"   Deleted {len(existing_videos)} old video(s)")
        elif logo_config and logo_config.get('has_crop'):
            # User applied crop settings but no logo
            print(f"Crop: {logo_config.get('crop_w', 0)}x{logo_config.get('crop_h', 0)} at ({logo_config.get('crop_x', 0)}, {logo_config.get('crop_y', 0)})")
            print("No logo will be added to videos.")
        else:
            print("No changes will be applied to videos.")
        print("=" * 30 + "\n")
    else:
        print("\nLogo feature is disabled. Skipping logo configuration.")
        logo_config = None

    # Load cache unless refresh requested
    if not args.refresh_cache:
        load_cache()

    # Pre-analyze all clips once to build cache
    all_clips = analyze_clips(clips_folder)

    if not all_clips:
        print(f"No video clips found in {clips_folder} after analysis. Cannot create video.")
        sys.exit(1) # Signal failure

    # Critical: shuffle the clips right at the beginning
    random.shuffle(all_clips)
    print(f"Found and completely shuffled {len(all_clips)} video clips.")

    # Filter by resolution if needed
    working_clips = all_clips
    if not args.skip_resolution_match and len(all_clips) > 1:
        working_clips = filter_clips_by_resolution(all_clips)
        if not working_clips:
            print("No clips matching resolution criteria, using all clips instead (if any are available).")
            working_clips = all_clips
        else:
            # Re-shuffle after filtering, but only if filtering actually resulted in a subset
            random.shuffle(working_clips)
            print(f"Re-shuffled {len(working_clips)} clips after resolution filtering.")

    if not working_clips:
        print("No usable video clips after all filtering and shuffling. Cannot create video.")
        sys.exit(1) # Signal failure

    # Get all voiceover files
    if args.single:
        voiceover_path = os.path.join(voiceovers_folder, args.single)
        if os.path.isfile(voiceover_path) and voiceover_path.lower().endswith('.mp3'):
            voiceovers = [voiceover_path]
        else:
            print(f"Specified voiceover file not found or is not an MP3: {voiceover_path}")
            sys.exit(1) # Signal failure
    else:
        voiceovers = [os.path.join(voiceovers_folder, f) for f in os.listdir(voiceovers_folder)
                      if f.lower().endswith('.mp3')]

    if not voiceovers:
        print(f"No MP3 files found in {voiceovers_folder}. Cannot create video.")
        sys.exit(1) # Signal failure

    print(f"Found {len(voiceovers)} voiceover files.")

    # Process each voiceover
    total_successful_videos = 0
    for i, voiceover in enumerate(voiceovers, 1):
        print(f"\nProcessing voiceover {i}/{len(voiceovers)}: {os.path.basename(voiceover)}")

        # Re-shuffle clips for each voiceover to ensure complete randomness
        # This re-shuffles the 'working_clips' pool for each voiceover
        random.shuffle(working_clips)
        print(f"Re-shuffled clips for voiceover {i}.")

        if create_video_from_voiceover(
            voiceover,
            working_clips, # Pass the (potentially filtered) pool of clips
            output_folder,
            use_copy=use_copy
        ):
            total_successful_videos += 1

    print(f"\nCompleted processing all voiceovers.")
    print(f"Total videos successfully created: {total_successful_videos}/{len(voiceovers)}.")

    save_cache()  # Save clip info cache before exiting

    if total_successful_videos < len(voiceovers):
        print("Warning: Not all videos were created successfully.")
        sys.exit(1) # Indicate partial failure to orchestrator
    elif total_successful_videos == 0 and len(voiceovers) > 0:
        print("Error: No videos were created successfully.")
        sys.exit(1) # Indicate total failure to orchestrator


if __name__ == "__main__":
    main()