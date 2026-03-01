"""
Logo Editor Tool - Visual Logo Positioning for Step 7
Shows video frames and lets you position logo with live preview

Enhanced Features:
- Video Zoom/Crop to hide watermarks or borders
- Video Scrubber to preview different frames
- Text Overlay for custom text/subscribe buttons
- Preset save/load for quick configuration
- Blur region to hide specific areas
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV not available. Install with: pip install opencv-python")

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QSlider, QComboBox, QFileDialog,
    QGroupBox, QCheckBox, QSpinBox, QFrame, QScrollArea, QListWidget,
    QListWidgetItem, QWidget, QMessageBox, QSplitter, QSizePolicy,
    QTabWidget, QColorDialog, QFontDialog, QInputDialog, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QRectF
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QIcon, QPen, QBrush

SCRIPT_DIR = Path(__file__).parent.resolve()


def get_user_data_dir():
    if os.name == 'nt':
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        return Path(appdata) / "NabilVideoStudioPro"
    return Path.home() / ".nvspro"


class ClickableFrameLabel(QLabel):
    """A label that shows a video frame thumbnail and is clickable"""
    clicked = pyqtSignal(str)  # Emits video path when clicked

    def __init__(self, video_path="", parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.setFixedSize(160, 90)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #3a3a6a;
                border-radius: 5px;
                background-color: #252545;
            }
            QLabel:hover {
                border: 2px solid #4CAF50;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.video_path)


class LogoPreviewWidget(QLabel):
    """Main preview widget - shows video frame with draggable logo, zoom/crop, text overlay"""
    logo_position_changed = pyqtSignal(float, float)
    zoom_changed = pyqtSignal(float)
    text_position_changed = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            background-color: #1a1a2e;
            border: 3px solid #4CAF50;
            border-radius: 10px;
        """)

        # Video frame
        self.original_frame = None
        self.display_frame = None
        self.frame_width = 1920
        self.frame_height = 1080
        self.video_path = None
        self.video_cap = None
        self.total_frames = 0
        self.current_frame_pos = 0

        # Logo
        self.logo_image = None
        self.logo_original = None
        self.logo_path = ""

        # Logo position (normalized 0-1)
        self.logo_x = 0.85
        self.logo_y = 0.10  # Top right by default

        # Logo settings
        self.logo_size_percent = 12
        self.logo_opacity = 90

        # === NEW: Zoom/Crop settings ===
        self.zoom_level = 1.0  # 1.0 = no zoom, 1.5 = 150% etc
        self.crop_x = 0.5  # Center point for crop (0-1)
        self.crop_y = 0.5

        # === NEW: Text overlay settings ===
        self.text_overlays = []  # List of text overlay configs
        self.active_text_index = -1  # Which text is being dragged

        # === NEW: Blur regions ===
        self.blur_regions = []  # List of (x, y, w, h) normalized regions

        # For dragging
        self.dragging = False
        self.dragging_text = False
        self.dragging_blur = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.drag_mode = "logo"  # "logo", "text", "blur"

        # Display scaling
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.setText("Select a video clip to preview")
        self.setStyleSheet(self.styleSheet() + "color: #888; font-size: 16px;")

    def load_frame_from_video(self, video_path, frame_position=None):
        """Extract a frame from the video (middle by default, or specified position)"""
        if not CV2_AVAILABLE:
            self.setText("OpenCV not available")
            return False

        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                self.setText(f"Cannot open: {Path(video_path).name}")
                return False

            # Get video properties
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.video_path = video_path

            # Seek to specified position or middle
            if frame_position is not None:
                self.current_frame_pos = max(0, min(frame_position, self.total_frames - 1))
            else:
                self.current_frame_pos = self.total_frames // 2

            cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_pos)
            ret, frame = cap.read()
            cap.release()

            if ret:
                self.original_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.update_preview()
                return True
            else:
                self.setText("Failed to read frame")
                return False

        except Exception as e:
            self.setText(f"Error: {str(e)[:50]}")
            return False

    def seek_to_frame(self, frame_pos):
        """Seek to a specific frame in the video"""
        if self.video_path:
            self.load_frame_from_video(self.video_path, frame_pos)

    def set_zoom(self, zoom_level):
        """Set zoom level (1.0 = 100%, 2.0 = 200%)"""
        self.zoom_level = max(1.0, min(3.0, zoom_level))
        self.zoom_changed.emit(self.zoom_level)
        self.update_preview()

    def set_crop_center(self, x, y):
        """Set the center point for zoom/crop (normalized 0-1)"""
        self.crop_x = max(0.0, min(1.0, x))
        self.crop_y = max(0.0, min(1.0, y))
        self.update_preview()

    def add_text_overlay(self, text, x=0.5, y=0.9, font_size=48, color=(255, 255, 255), bg_color=None):
        """Add a text overlay"""
        overlay = {
            'text': text,
            'x': x,
            'y': y,
            'font_size': font_size,
            'color': color,
            'bg_color': bg_color,
            'font_name': 'Arial'
        }
        self.text_overlays.append(overlay)
        self.update_preview()
        return len(self.text_overlays) - 1

    def remove_text_overlay(self, index):
        """Remove a text overlay"""
        if 0 <= index < len(self.text_overlays):
            self.text_overlays.pop(index)
            self.update_preview()

    def add_blur_region(self, x, y, w, h):
        """Add a blur region (normalized coordinates)"""
        region = {'x': x, 'y': y, 'w': w, 'h': h, 'blur_strength': 25}
        self.blur_regions.append(region)
        self.update_preview()
        return len(self.blur_regions) - 1

    def remove_blur_region(self, index):
        """Remove a blur region"""
        if 0 <= index < len(self.blur_regions):
            self.blur_regions.pop(index)
            self.update_preview()

    def load_logo(self, logo_path):
        """Load logo image with alpha channel"""
        if not CV2_AVAILABLE:
            return False

        try:
            # Load with alpha
            logo = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
            if logo is None:
                return False

            # Ensure RGBA
            if len(logo.shape) == 2:
                logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2RGBA)
            elif logo.shape[2] == 3:
                logo = cv2.cvtColor(logo, cv2.COLOR_BGR2RGBA)
            elif logo.shape[2] == 4:
                logo = cv2.cvtColor(logo, cv2.COLOR_BGRA2RGBA)

            self.logo_original = logo
            self.logo_path = logo_path
            self.update_preview()
            return True

        except Exception as e:
            print(f"Error loading logo: {e}")
            return False

    def update_preview(self):
        """Redraw preview with current settings"""
        if self.original_frame is None:
            return

        # Start with copy of original
        frame = self.original_frame.copy()
        h, w = frame.shape[:2]

        # === Apply Zoom/Crop ===
        if self.zoom_level > 1.0:
            frame = self._apply_zoom_crop(frame)

        # === Apply Blur Regions ===
        for region in self.blur_regions:
            frame = self._apply_blur_region(frame, region)

        # === Overlay logo if available ===
        if self.logo_original is not None:
            frame = self._overlay_logo(frame)

        # === Apply Text Overlays ===
        for text_overlay in self.text_overlays:
            frame = self._apply_text_overlay(frame, text_overlay)

        # Convert to QPixmap
        h, w = frame.shape[:2]
        bytes_per_line = 3 * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # Scale to fit widget
        available_w = self.width() - 20
        available_h = self.height() - 20
        scaled = pixmap.scaled(available_w, available_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Calculate scaling for mouse events
        self.scale_factor = scaled.width() / w
        self.offset_x = (self.width() - scaled.width()) // 2
        self.offset_y = (self.height() - scaled.height()) // 2

        self.setPixmap(scaled)

    def _apply_zoom_crop(self, frame):
        """Apply zoom and crop to frame"""
        h, w = frame.shape[:2]

        # Calculate crop region based on zoom level
        crop_w = int(w / self.zoom_level)
        crop_h = int(h / self.zoom_level)

        # Calculate top-left corner of crop region
        x1 = int(self.crop_x * w - crop_w / 2)
        y1 = int(self.crop_y * h - crop_h / 2)

        # Clamp to frame bounds
        x1 = max(0, min(x1, w - crop_w))
        y1 = max(0, min(y1, h - crop_h))

        # Crop and resize back to original size
        cropped = frame[y1:y1+crop_h, x1:x1+crop_w]
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        return zoomed

    def _apply_blur_region(self, frame, region):
        """Apply blur to a specific region"""
        h, w = frame.shape[:2]

        # Calculate region in pixels
        x1 = int(region['x'] * w)
        y1 = int(region['y'] * h)
        x2 = int((region['x'] + region['w']) * w)
        y2 = int((region['y'] + region['h']) * h)

        # Clamp to bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 > x1 and y2 > y1:
            # Extract region and blur
            roi = frame[y1:y2, x1:x2]
            blur_size = region.get('blur_strength', 25)
            blur_size = blur_size if blur_size % 2 == 1 else blur_size + 1  # Must be odd
            blurred = cv2.GaussianBlur(roi, (blur_size, blur_size), 0)
            frame[y1:y2, x1:x2] = blurred

        return frame

    def _apply_text_overlay(self, frame, text_overlay):
        """Apply text overlay to frame"""
        h, w = frame.shape[:2]

        text = text_overlay['text']
        x = int(text_overlay['x'] * w)
        y = int(text_overlay['y'] * h)
        font_size = text_overlay.get('font_size', 48)
        color = text_overlay.get('color', (255, 255, 255))
        bg_color = text_overlay.get('bg_color', None)

        # Scale font size based on frame resolution
        font_scale = font_size / 48.0 * (w / 1920)
        thickness = max(1, int(font_scale * 2))

        # Get text size
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)

        # Center text at position
        text_x = x - text_w // 2
        text_y = y + text_h // 2

        # Draw background if specified
        if bg_color:
            padding = 10
            cv2.rectangle(frame,
                         (text_x - padding, text_y - text_h - padding),
                         (text_x + text_w + padding, text_y + baseline + padding),
                         bg_color, -1)

        # Draw text with outline for visibility
        cv2.putText(frame, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 2)  # Outline
        cv2.putText(frame, text, (text_x, text_y), font, font_scale, color, thickness)  # Text

        return frame

    def _overlay_logo(self, frame):
        """Composite logo onto frame"""
        if self.logo_original is None:
            return frame

        h, w = frame.shape[:2]

        # Calculate logo size
        logo_w = int(w * self.logo_size_percent / 100)
        aspect = self.logo_original.shape[0] / self.logo_original.shape[1]
        logo_h = int(logo_w * aspect)

        # Resize logo
        logo_resized = cv2.resize(self.logo_original, (logo_w, logo_h), interpolation=cv2.INTER_AREA)

        # Calculate position (logo_x, logo_y are center points)
        x = int(self.logo_x * w - logo_w / 2)
        y = int(self.logo_y * h - logo_h / 2)

        # Clamp to frame bounds
        x = max(0, min(x, w - logo_w))
        y = max(0, min(y, h - logo_h))

        # Alpha composite
        result = frame.copy()
        alpha = logo_resized[:, :, 3:4] / 255.0 * (self.logo_opacity / 100.0)

        roi = result[y:y+logo_h, x:x+logo_w]
        blended = (alpha * logo_resized[:, :, :3] + (1 - alpha) * roi).astype(np.uint8)
        result[y:y+logo_h, x:x+logo_w] = blended

        return result

    def _get_logo_rect(self):
        """Get logo rectangle in widget coordinates"""
        if self.original_frame is None or self.logo_original is None:
            return None

        h, w = self.original_frame.shape[:2]

        logo_w = w * self.logo_size_percent / 100
        aspect = self.logo_original.shape[0] / self.logo_original.shape[1]
        logo_h = logo_w * aspect

        # Video coordinates
        vx = self.logo_x * w - logo_w / 2
        vy = self.logo_y * h - logo_h / 2

        # Convert to widget coordinates
        wx = vx * self.scale_factor + self.offset_x
        wy = vy * self.scale_factor + self.offset_y
        ww = logo_w * self.scale_factor
        wh = logo_h * self.scale_factor

        return (wx, wy, ww, wh)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.logo_original is not None:
            rect = self._get_logo_rect()
            if rect:
                wx, wy, ww, wh = rect
                mx, my = event.x(), event.y()

                # Check if clicking on logo
                if wx <= mx <= wx + ww and wy <= my <= wy + wh:
                    self.dragging = True
                    # Calculate offset from logo center
                    logo_center_x = wx + ww / 2
                    logo_center_y = wy + wh / 2
                    self.drag_offset_x = mx - logo_center_x
                    self.drag_offset_y = my - logo_center_y
                    self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.dragging and self.original_frame is not None:
            # Convert widget coords to normalized video coords
            mx = event.x() - self.drag_offset_x
            my = event.y() - self.drag_offset_y

            # Remove offset and scale
            vx = (mx - self.offset_x) / self.scale_factor
            vy = (my - self.offset_y) / self.scale_factor

            # Normalize
            h, w = self.original_frame.shape[:2]
            self.logo_x = max(0.05, min(0.95, vx / w))
            self.logo_y = max(0.05, min(0.95, vy / h))

            self.update_preview()
            self.logo_position_changed.emit(self.logo_x, self.logo_y)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.ArrowCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_frame is not None:
            self.update_preview()


class LogoEditorDialog(QDialog):
    """Logo Editor - Visual tool for positioning logos on video clips

    Used as popup during Step 7 to let user position logo on video.
    Returns config dict when Apply is clicked, None when Skip is clicked.
    """

    def __init__(self, clips_folder=None, output_folder=None, parent=None, channel_name=None):
        super().__init__(parent)
        # Support both parameter names for compatibility
        self.clips_folder = clips_folder
        self.output_folder = output_folder or clips_folder
        self.video_files = []
        self.channel_name = channel_name

        # Track if user wants logo
        self.use_logo = False
        self.accepted_config = None

        # Show channel name in title if provided
        if channel_name:
            self.setWindowTitle(f"🎨 Logo Editor - {channel_name}")
        else:
            self.setWindowTitle("🎨 Logo Editor - Position Your Logo")
        self.setMinimumSize(1100, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setup_style()
        self.create_ui()
        self.load_saved_config()

        # Auto-load clips from provided folder
        folder = clips_folder or output_folder
        if folder:
            self.folder_edit.setText(str(folder))
            self.scan_for_clips()
            # Play notification sound when popup opens (delayed to ensure window is shown)
            QTimer.singleShot(500, self.play_notification)

    def play_notification(self):
        """Play notification sound in background (no player window)"""
        try:
            import os
            import json

            # Read notification settings from config
            config_path = Path(os.environ.get('LOCALAPPDATA', '')) / "NabilVideoStudioPro" / "config.json"
            enabled = True
            sound_file = SCRIPT_DIR / "notifications.mp3"

            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    notif_settings = config.get("notification_settings", {})
                    enabled = notif_settings.get("enabled", True)
                    custom_sound = notif_settings.get("sound_file", "")
                    if custom_sound:
                        custom_path = Path(custom_sound)
                        if custom_path.exists():
                            sound_file = custom_path
                        elif (SCRIPT_DIR / custom_sound).exists():
                            sound_file = SCRIPT_DIR / custom_sound
                except:
                    pass

            if not enabled:
                return

            if sound_file.exists():
                # Use PyQt5 QMediaPlayer - plays in background, no window
                from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
                from PyQt5.QtCore import QUrl

                self._player = QMediaPlayer()
                self._player.setMedia(QMediaContent(QUrl.fromLocalFile(str(sound_file))))
                self._player.play()
            else:
                # System beep fallback
                try:
                    import winsound
                    winsound.Beep(800, 150)
                    winsound.Beep(1000, 150)
                except:
                    pass
        except Exception as e:
            print(f"Notification: {e}")

    def setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QGroupBox {
                color: #4CAF50;
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #3a3a6a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
            QPushButton {
                background-color: #3a3a6a;
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a8a;
            }
            QPushButton:pressed {
                background-color: #2a2a5a;
            }
            QLineEdit {
                background-color: #252545;
                color: #e0e0e0;
                border: 2px solid #3a3a6a;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #4CAF50;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #3a3a6a;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 20px;
                height: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
            QSlider::handle:horizontal:hover {
                background: #66BB6A;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

    def create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Channel name header (if provided)
        if self.channel_name:
            channel_header = QLabel(f"📺 SELECT LOGO FOR: {self.channel_name}")
            channel_header.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #00ff00;
                    background-color: #1a3a1a;
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #00aa00;
                }
            """)
            channel_header.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(channel_header)

        # Top: Folder selection
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("📁 Output Folder:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select your output folder to find video clips...")
        folder_layout.addWidget(self.folder_edit, stretch=1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_folder)
        folder_layout.addWidget(btn_browse)

        btn_scan = QPushButton("🔍 Scan")
        btn_scan.clicked.connect(self.scan_for_clips)
        btn_scan.setStyleSheet("background-color: #2196F3;")
        folder_layout.addWidget(btn_scan)

        main_layout.addLayout(folder_layout)

        # Middle: Clips + Preview + Controls
        content_layout = QHBoxLayout()

        # Left: Video clips thumbnails
        clips_group = QGroupBox("📹 Video Clips (click to preview)")
        clips_layout = QVBoxLayout(clips_group)

        self.clips_scroll = QScrollArea()
        self.clips_scroll.setWidgetResizable(True)
        self.clips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.clips_scroll.setMinimumWidth(180)
        self.clips_scroll.setMaximumWidth(200)

        self.clips_container = QWidget()
        self.clips_grid = QGridLayout(self.clips_container)
        self.clips_grid.setSpacing(8)
        self.clips_scroll.setWidget(self.clips_container)

        clips_layout.addWidget(self.clips_scroll)

        self.clips_count_label = QLabel("No clips found")
        self.clips_count_label.setStyleSheet("color: #888; font-size: 11px;")
        clips_layout.addWidget(self.clips_count_label)

        content_layout.addWidget(clips_group)

        # Center: Preview
        preview_group = QGroupBox("👁️ Live Preview - Drag logo to position")
        preview_layout = QVBoxLayout(preview_group)

        self.preview = LogoPreviewWidget()
        self.preview.logo_position_changed.connect(self.on_position_changed)
        preview_layout.addWidget(self.preview, stretch=1)

        self.position_label = QLabel("Position: X=85%, Y=10% (Top-Right)")
        self.position_label.setAlignment(Qt.AlignCenter)
        self.position_label.setStyleSheet("font-size: 13px; color: #4CAF50; font-weight: bold;")
        preview_layout.addWidget(self.position_label)

        content_layout.addWidget(preview_group, stretch=1)

        # Right: Controls with Tabs
        controls_group = QGroupBox("⚙️ Logo Controls")
        controls_group.setMaximumWidth(350)
        controls_group.setMinimumWidth(330)
        controls_main_layout = QVBoxLayout(controls_group)

        # Create tab widget for different features
        self.controls_tabs = QTabWidget()
        self.controls_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3a3a6a;
                border-radius: 5px;
                background: #1a1a2e;
            }
            QTabBar::tab {
                background: #252545;
                color: #888;
                padding: 8px 12px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3a3a6a;
                color: #4CAF50;
            }
        """)

        # === TAB 1: Logo Settings ===
        logo_tab = QWidget()
        logo_layout = QVBoxLayout(logo_tab)
        logo_layout.setSpacing(10)

        # Logo file
        logo_layout.addWidget(QLabel("Logo File (PNG):"))
        logo_file_layout = QHBoxLayout()
        self.logo_edit = QLineEdit()
        self.logo_edit.setPlaceholderText("Select logo...")
        logo_file_layout.addWidget(self.logo_edit)
        btn_logo = QPushButton("📁")
        btn_logo.setMaximumWidth(40)
        btn_logo.clicked.connect(self.browse_logo)
        logo_file_layout.addWidget(btn_logo)
        logo_layout.addLayout(logo_file_layout)

        # Size
        size_group = QHBoxLayout()
        size_group.addWidget(QLabel("Size:"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(5, 30)
        self.size_slider.setValue(12)
        self.size_slider.valueChanged.connect(self.on_size_changed)
        size_group.addWidget(self.size_slider)
        self.size_label = QLabel("12%")
        self.size_label.setMinimumWidth(35)
        self.size_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        size_group.addWidget(self.size_label)
        logo_layout.addLayout(size_group)

        # Opacity
        opacity_group = QHBoxLayout()
        opacity_group.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(90)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_group.addWidget(self.opacity_slider)
        self.opacity_label = QLabel("90%")
        self.opacity_label.setMinimumWidth(35)
        self.opacity_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        opacity_group.addWidget(self.opacity_label)
        logo_layout.addLayout(opacity_group)

        # Quick positions - 4 corners only (simpler)
        logo_layout.addWidget(QLabel("📍 Quick Position:"))
        pos_grid = QGridLayout()
        pos_grid.setSpacing(8)

        positions = [
            ("↖ Top Left", 0.10, 0.10), ("↗ Top Right", 0.90, 0.10),
            ("↙ Bottom Left", 0.10, 0.90), ("↘ Bottom Right", 0.90, 0.90),
        ]

        for i, (label, x, y) in enumerate(positions):
            btn = QPushButton(label)
            btn.setStyleSheet("padding: 10px; font-size: 12px; font-weight: bold;")
            btn.clicked.connect(lambda checked, px=x, py=y: self.set_position(px, py))
            pos_grid.addWidget(btn, i // 2, i % 2)

        logo_layout.addLayout(pos_grid)

        # Add Apply to All button
        logo_layout.addWidget(QLabel(""))  # Spacer
        btn_apply_all = QPushButton("✨ Apply to ALL Videos")
        btn_apply_all.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFB74D;
            }
        """)
        btn_apply_all.clicked.connect(self.apply_to_all_videos)
        logo_layout.addWidget(btn_apply_all)

        logo_layout.addStretch()

        self.controls_tabs.addTab(logo_tab, "🎨 Logo")

        # === TAB 2: Zoom/Crop ===
        zoom_tab = QWidget()
        zoom_layout = QVBoxLayout(zoom_tab)
        zoom_layout.setSpacing(10)

        zoom_layout.addWidget(QLabel("🔍 Zoom to hide borders/watermarks:"))

        # Zoom slider
        zoom_slider_layout = QHBoxLayout()
        zoom_slider_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(100, 200)  # 100% to 200%
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_slider_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(45)
        self.zoom_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        zoom_slider_layout.addWidget(self.zoom_label)
        zoom_layout.addLayout(zoom_slider_layout)

        # Crop position - simplified to 4 corners + center
        zoom_layout.addWidget(QLabel("📍 Crop Focus:"))
        crop_grid = QGridLayout()
        crop_grid.setSpacing(8)

        crop_positions = [
            ("↖ Top-Left", 0.25, 0.25), ("↗ Top-Right", 0.75, 0.25),
            ("● Center", 0.50, 0.50), ("● Center", 0.50, 0.50),
            ("↙ Bottom-Left", 0.25, 0.75), ("↘ Bottom-Right", 0.75, 0.75),
        ]

        for i, (label, x, y) in enumerate(crop_positions):
            if i == 2:  # Center button - make it span 2 columns
                btn = QPushButton(label)
                btn.setStyleSheet("padding: 10px; font-size: 12px; font-weight: bold;")
                btn.clicked.connect(lambda checked, px=x, py=y: self.set_crop_center(px, py))
                crop_grid.addWidget(btn, 1, 0, 1, 2)  # Row 1, col 0, span 2 cols
            elif i == 3:  # Skip duplicate center
                continue
            else:
                btn = QPushButton(label)
                btn.setStyleSheet("padding: 10px; font-size: 12px;")
                btn.clicked.connect(lambda checked, px=x, py=y: self.set_crop_center(px, py))
                if i < 2:
                    crop_grid.addWidget(btn, 0, i)  # Top row
                else:
                    crop_grid.addWidget(btn, 2, i - 4)  # Bottom row

        zoom_layout.addLayout(crop_grid)

        # Reset zoom button
        btn_reset_zoom = QPushButton("🔄 Reset Zoom")
        btn_reset_zoom.clicked.connect(self.reset_zoom)
        zoom_layout.addWidget(btn_reset_zoom)

        zoom_layout.addStretch()
        self.controls_tabs.addTab(zoom_tab, "🔍 Zoom")

        # NOTE: Text Overlay and Blur tabs removed for simplicity - uncomment below if needed
        if False:  # Change to True to enable Text/Blur features
            # === TAB 3: Text Overlay ===
            text_tab = QWidget()
            text_layout = QVBoxLayout(text_tab)
        text_layout.setSpacing(10)

        text_layout.addWidget(QLabel("📝 Add text overlay:"))

        # Text input
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter text (e.g., SUBSCRIBE)")
        text_layout.addWidget(self.text_input)

        # Font size
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("Size:"))
        self.font_size_slider = QSlider(Qt.Horizontal)
        self.font_size_slider.setRange(20, 100)
        self.font_size_slider.setValue(48)
        font_size_layout.addWidget(self.font_size_slider)
        self.font_size_label = QLabel("48")
        self.font_size_label.setMinimumWidth(30)
        font_size_layout.addWidget(self.font_size_label)
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_label.setText(str(v)))
        text_layout.addLayout(font_size_layout)

        # Text color button
        color_layout = QHBoxLayout()
        self.text_color = (255, 255, 255)
        self.btn_text_color = QPushButton("Text Color")
        self.btn_text_color.setStyleSheet("background-color: #ffffff;")
        self.btn_text_color.clicked.connect(self.pick_text_color)
        color_layout.addWidget(self.btn_text_color)

        self.text_bg_enabled = QCheckBox("Background")
        color_layout.addWidget(self.text_bg_enabled)
        text_layout.addLayout(color_layout)

        # Add text button
        btn_add_text = QPushButton("➕ Add Text")
        btn_add_text.setStyleSheet("background-color: #FF9800;")
        btn_add_text.clicked.connect(self.add_text_overlay)
        text_layout.addWidget(btn_add_text)

        # Text list
        self.text_list = QListWidget()
        self.text_list.setMaximumHeight(100)
        text_layout.addWidget(self.text_list)

        # Remove text button
        btn_remove_text = QPushButton("🗑️ Remove Selected")
        btn_remove_text.clicked.connect(self.remove_text_overlay)
        text_layout.addWidget(btn_remove_text)

        text_layout.addStretch()
        self.controls_tabs.addTab(text_tab, "📝 Text")

        # === TAB 4: Blur Region ===
        blur_tab = QWidget()
        blur_layout = QVBoxLayout(blur_tab)
        blur_layout.setSpacing(10)

        blur_layout.addWidget(QLabel("🌫️ Blur regions to hide content:"))

        # Blur strength
        blur_strength_layout = QHBoxLayout()
        blur_strength_layout.addWidget(QLabel("Strength:"))
        self.blur_strength_slider = QSlider(Qt.Horizontal)
        self.blur_strength_slider.setRange(5, 51)
        self.blur_strength_slider.setValue(25)
        blur_strength_layout.addWidget(self.blur_strength_slider)
        self.blur_strength_label = QLabel("25")
        self.blur_strength_label.setMinimumWidth(30)
        blur_strength_layout.addWidget(self.blur_strength_label)
        self.blur_strength_slider.valueChanged.connect(lambda v: self.blur_strength_label.setText(str(v)))
        blur_layout.addLayout(blur_strength_layout)

        # Preset blur regions
        blur_layout.addWidget(QLabel("Quick Blur Regions:"))
        blur_presets_layout = QGridLayout()

        blur_presets = [
            ("Top Bar", 0, 0, 1, 0.1),
            ("Bottom Bar", 0, 0.9, 1, 0.1),
            ("Top-Left", 0, 0, 0.2, 0.15),
            ("Top-Right", 0.8, 0, 0.2, 0.15),
            ("Bottom-Left", 0, 0.85, 0.2, 0.15),
            ("Bottom-Right", 0.8, 0.85, 0.2, 0.15),
        ]

        for i, (label, x, y, w, h) in enumerate(blur_presets):
            btn = QPushButton(label)
            btn.setStyleSheet("padding: 5px; font-size: 10px;")
            btn.clicked.connect(lambda checked, bx=x, by=y, bw=w, bh=h: self.add_blur_preset(bx, by, bw, bh))
            blur_presets_layout.addWidget(btn, i // 2, i % 2)

        blur_layout.addLayout(blur_presets_layout)

        # Blur list
        self.blur_list = QListWidget()
        self.blur_list.setMaximumHeight(80)
        blur_layout.addWidget(self.blur_list)

        # Remove blur button
        btn_remove_blur = QPushButton("🗑️ Remove Selected Blur")
        btn_remove_blur.clicked.connect(self.remove_blur_region)
        blur_layout.addWidget(btn_remove_blur)

        # Clear all blurs
        btn_clear_blur = QPushButton("🧹 Clear All Blurs")
        btn_clear_blur.clicked.connect(self.clear_all_blurs)
        blur_layout.addWidget(btn_clear_blur)

        # === TAB 3: Presets ===
        presets_tab = QWidget()
        presets_layout = QVBoxLayout(presets_tab)
        presets_layout.setSpacing(10)

        presets_layout.addWidget(QLabel("💾 Save/Load Configurations:"))

        # Preset name input
        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("Preset name...")
        presets_layout.addWidget(self.preset_name_input)

        # Save preset button
        btn_save_preset = QPushButton("💾 Save Preset")
        btn_save_preset.setStyleSheet("background-color: #9C27B0;")
        btn_save_preset.clicked.connect(self.save_preset)
        presets_layout.addWidget(btn_save_preset)

        # Preset list
        presets_layout.addWidget(QLabel("Saved Presets:"))
        self.preset_list = QListWidget()
        self.preset_list.setMaximumHeight(120)
        presets_layout.addWidget(self.preset_list)

        # Load/Delete buttons
        preset_btn_layout = QHBoxLayout()
        btn_load_preset = QPushButton("📂 Load")
        btn_load_preset.clicked.connect(self.load_preset)
        preset_btn_layout.addWidget(btn_load_preset)

        btn_delete_preset = QPushButton("🗑️ Delete")
        btn_delete_preset.clicked.connect(self.delete_preset)
        preset_btn_layout.addWidget(btn_delete_preset)
        presets_layout.addLayout(preset_btn_layout)

        presets_layout.addStretch()
        self.controls_tabs.addTab(presets_tab, "💾 Presets")

        controls_main_layout.addWidget(self.controls_tabs)

        # === Video Scrubber (below tabs) ===
        scrubber_group = QGroupBox("🎬 Video Scrubber")
        scrubber_layout = QVBoxLayout(scrubber_group)

        self.scrubber_slider = QSlider(Qt.Horizontal)
        self.scrubber_slider.setRange(0, 100)
        self.scrubber_slider.setValue(50)
        self.scrubber_slider.valueChanged.connect(self.on_scrubber_changed)
        scrubber_layout.addWidget(self.scrubber_slider)

        self.scrubber_label = QLabel("Frame: 50%")
        self.scrubber_label.setAlignment(Qt.AlignCenter)
        self.scrubber_label.setStyleSheet("color: #888; font-size: 11px;")
        scrubber_layout.addWidget(self.scrubber_label)

        controls_main_layout.addWidget(scrubber_group)

        # === Action Buttons ===
        btn_apply = QPushButton("✅ Apply Settings")
        btn_apply.setStyleSheet("background-color: #4CAF50; padding: 14px; font-size: 14px;")
        btn_apply.clicked.connect(self.apply_logo)
        controls_main_layout.addWidget(btn_apply)

        btn_skip = QPushButton("⏭️ Skip (No Changes)")
        btn_skip.setStyleSheet("background-color: #666; padding: 14px; font-size: 14px;")
        btn_skip.clicked.connect(self.skip_logo)
        controls_main_layout.addWidget(btn_skip)

        content_layout.addWidget(controls_group)

        main_layout.addLayout(content_layout, stretch=1)

        # Load saved presets
        self.refresh_preset_list()

    # === NEW FEATURE HANDLERS ===

    def on_zoom_changed(self, value):
        """Handle zoom slider change"""
        zoom_level = value / 100.0
        self.zoom_label.setText(f"{value}%")
        self.preview.set_zoom(zoom_level)

    def set_crop_center(self, x, y):
        """Set crop center position"""
        self.preview.set_crop_center(x, y)

    def reset_zoom(self):
        """Reset zoom to 100%"""
        self.zoom_slider.setValue(100)
        self.preview.set_zoom(1.0)
        self.preview.set_crop_center(0.5, 0.5)

    def on_scrubber_changed(self, value):
        """Handle video scrubber change"""
        if self.preview.total_frames > 0:
            frame_pos = int(value / 100.0 * self.preview.total_frames)
            self.scrubber_label.setText(f"Frame: {value}% ({frame_pos}/{self.preview.total_frames})")
            self.preview.seek_to_frame(frame_pos)
        else:
            self.scrubber_label.setText(f"Frame: {value}%")

    def pick_text_color(self):
        """Open color picker for text color"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = (color.red(), color.green(), color.blue())
            self.btn_text_color.setStyleSheet(f"background-color: {color.name()};")

    def add_text_overlay(self):
        """Add a text overlay to the preview"""
        text = self.text_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Please enter text first!")
            return

        font_size = self.font_size_slider.value()
        bg_color = (0, 0, 0) if self.text_bg_enabled.isChecked() else None

        idx = self.preview.add_text_overlay(text, 0.5, 0.9, font_size, self.text_color, bg_color)
        self.text_list.addItem(f"{idx+1}. {text}")
        self.text_input.clear()

    def remove_text_overlay(self):
        """Remove selected text overlay"""
        current = self.text_list.currentRow()
        if current >= 0:
            self.preview.remove_text_overlay(current)
            self.text_list.takeItem(current)
            # Refresh list numbering
            self.refresh_text_list()

    def refresh_text_list(self):
        """Refresh the text list display"""
        self.text_list.clear()
        for i, overlay in enumerate(self.preview.text_overlays):
            self.text_list.addItem(f"{i+1}. {overlay['text']}")

    def add_blur_preset(self, x, y, w, h):
        """Add a blur region from preset"""
        strength = self.blur_strength_slider.value()
        idx = self.preview.add_blur_region(x, y, w, h)
        self.preview.blur_regions[idx]['blur_strength'] = strength
        self.preview.update_preview()
        self.refresh_blur_list()

    def remove_blur_region(self):
        """Remove selected blur region"""
        current = self.blur_list.currentRow()
        if current >= 0:
            self.preview.remove_blur_region(current)
            self.refresh_blur_list()

    def clear_all_blurs(self):
        """Clear all blur regions"""
        self.preview.blur_regions.clear()
        self.preview.update_preview()
        self.refresh_blur_list()

    def refresh_blur_list(self):
        """Refresh the blur list display"""
        self.blur_list.clear()
        for i, region in enumerate(self.preview.blur_regions):
            x, y, w, h = region['x'], region['y'], region['w'], region['h']
            self.blur_list.addItem(f"{i+1}. Region ({int(x*100)}%, {int(y*100)}%)")

    def get_presets_file(self):
        """Get path to presets file"""
        return get_user_data_dir() / "logo_presets.json"

    def save_preset(self):
        """Save current settings as a preset"""
        name = self.preset_name_input.text().strip()
        if not name:
            name = f"Preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        preset = {
            'name': name,
            'logo_path': self.logo_edit.text(),
            'logo_x': self.preview.logo_x,
            'logo_y': self.preview.logo_y,
            'logo_size': self.preview.logo_size_percent,
            'logo_opacity': self.preview.logo_opacity,
            'zoom_level': self.preview.zoom_level,
            'crop_x': self.preview.crop_x,
            'crop_y': self.preview.crop_y,
            'text_overlays': self.preview.text_overlays.copy(),
            'blur_regions': self.preview.blur_regions.copy(),
        }

        # Load existing presets
        presets_file = self.get_presets_file()
        presets = {}
        if presets_file.exists():
            try:
                with open(presets_file, 'r', encoding='utf-8') as f:
                    presets = json.load(f)
            except:
                pass

        presets[name] = preset

        # Save
        presets_file.parent.mkdir(parents=True, exist_ok=True)
        with open(presets_file, 'w', encoding='utf-8') as f:
            json.dump(presets, f, indent=2)

        self.preset_name_input.clear()
        self.refresh_preset_list()
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved!")

    def load_preset(self):
        """Load selected preset"""
        current = self.preset_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Error", "Please select a preset first!")
            return

        name = current.text()
        presets_file = self.get_presets_file()
        if not presets_file.exists():
            return

        try:
            with open(presets_file, 'r', encoding='utf-8') as f:
                presets = json.load(f)

            if name in presets:
                preset = presets[name]

                # Apply settings
                if preset.get('logo_path') and Path(preset['logo_path']).exists():
                    self.logo_edit.setText(preset['logo_path'])
                    self.preview.load_logo(preset['logo_path'])

                self.preview.logo_x = preset.get('logo_x', 0.85)
                self.preview.logo_y = preset.get('logo_y', 0.10)
                self.preview.logo_size_percent = preset.get('logo_size', 12)
                self.preview.logo_opacity = preset.get('logo_opacity', 90)
                self.preview.zoom_level = preset.get('zoom_level', 1.0)
                self.preview.crop_x = preset.get('crop_x', 0.5)
                self.preview.crop_y = preset.get('crop_y', 0.5)
                self.preview.text_overlays = preset.get('text_overlays', [])
                self.preview.blur_regions = preset.get('blur_regions', [])

                # Update UI
                self.size_slider.setValue(int(self.preview.logo_size_percent))
                self.opacity_slider.setValue(int(self.preview.logo_opacity))
                self.zoom_slider.setValue(int(self.preview.zoom_level * 100))

                self.preview.update_preview()
                self.refresh_text_list()
                self.refresh_blur_list()

                QMessageBox.information(self, "Loaded", f"Preset '{name}' loaded!")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load preset: {e}")

    def delete_preset(self):
        """Delete selected preset"""
        current = self.preset_list.currentItem()
        if not current:
            return

        name = current.text()
        presets_file = self.get_presets_file()
        if not presets_file.exists():
            return

        try:
            with open(presets_file, 'r', encoding='utf-8') as f:
                presets = json.load(f)

            if name in presets:
                del presets[name]

                with open(presets_file, 'w', encoding='utf-8') as f:
                    json.dump(presets, f, indent=2)

                self.refresh_preset_list()
        except:
            pass

    def refresh_preset_list(self):
        """Refresh the preset list"""
        self.preset_list.clear()
        presets_file = self.get_presets_file()
        if presets_file.exists():
            try:
                with open(presets_file, 'r', encoding='utf-8') as f:
                    presets = json.load(f)
                for name in presets.keys():
                    self.preset_list.addItem(name)
            except:
                pass

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.folder_edit.setText(folder)
            self.output_folder = folder
            self.scan_for_clips()

    def browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;PNG Files (*.png)"
        )
        if path:
            self.logo_edit.setText(path)
            if self.preview.load_logo(path):
                self.preview.update_preview()

    def scan_for_clips(self):
        """Find video clips in output folder"""
        # Clear existing thumbnails
        while self.clips_grid.count():
            item = self.clips_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.video_files = []
        folder = self.folder_edit.text()

        if not folder or not Path(folder).exists():
            self.clips_count_label.setText("Invalid folder")
            return

        # Search for clips
        search_patterns = [
            "*/07_final_videos/*.mp4",
            "*/06_rearranged_broll_clips/*.mp4",
            "*/02_styled_clips/**/*.mp4",
            "*/01_clips_main/**/*.mp4",
            "*.mp4"
        ]

        found = set()
        for pattern in search_patterns:
            for f in Path(folder).glob(pattern):
                if f not in found:
                    found.add(f)
                    self.video_files.append(f)

        # Sort by name
        self.video_files.sort(key=lambda x: x.name)

        # Create thumbnails
        row, col = 0, 0
        for video_path in self.video_files[:20]:  # Limit to 20 for performance
            thumb = self.create_thumbnail(video_path)
            if thumb:
                self.clips_grid.addWidget(thumb, row, col)
                col += 1
                if col >= 1:  # Single column
                    col = 0
                    row += 1

        count = len(self.video_files)
        self.clips_count_label.setText(f"Found {count} clip{'s' if count != 1 else ''}")

    def create_thumbnail(self, video_path):
        """Create clickable thumbnail for a video"""
        if not CV2_AVAILABLE:
            return None

        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return None

            # Get frame from middle
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            # Convert and create pixmap
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            qimg = QImage(frame.data, w, h, 3 * w, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(160, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Create label
            label = ClickableFrameLabel(str(video_path))
            label.setPixmap(scaled)
            label.setToolTip(video_path.name)
            label.clicked.connect(self.on_clip_clicked)

            return label

        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            return None

    def on_clip_clicked(self, video_path):
        """Load clicked clip into preview"""
        self.preview.load_frame_from_video(video_path)

    def on_position_changed(self, x, y):
        """Update position label when logo is dragged"""
        # Determine position name
        if x < 0.33:
            h_pos = "Left"
        elif x > 0.66:
            h_pos = "Right"
        else:
            h_pos = "Center"

        if y < 0.33:
            v_pos = "Top"
        elif y > 0.66:
            v_pos = "Bottom"
        else:
            v_pos = "Middle"

        pos_name = f"{v_pos}-{h_pos}" if v_pos != "Middle" or h_pos != "Center" else "Center"
        self.position_label.setText(f"Position: X={int(x*100)}%, Y={int(y*100)}% ({pos_name})")

    def on_size_changed(self, value):
        self.size_label.setText(f"{value}%")
        self.preview.logo_size_percent = value
        self.preview.update_preview()

    def on_opacity_changed(self, value):
        self.opacity_label.setText(f"{value}%")
        self.preview.logo_opacity = value
        self.preview.update_preview()

    def set_position(self, x, y):
        self.preview.logo_x = x
        self.preview.logo_y = y
        self.preview.update_preview()
        self.on_position_changed(x, y)

    def load_saved_config(self):
        """Load previously saved config"""
        config_path = SCRIPT_DIR / "logo_config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)

                if config.get('logo_path'):
                    self.logo_edit.setText(config['logo_path'])
                    self.preview.load_logo(config['logo_path'])

                self.preview.logo_x = config.get('position_x', 0.85)
                self.preview.logo_y = config.get('position_y', 0.10)
                self.size_slider.setValue(config.get('size_percent', 12))
                self.opacity_slider.setValue(config.get('opacity_percent', 90))

                self.on_position_changed(self.preview.logo_x, self.preview.logo_y)

            except Exception as e:
                print(f"Error loading config: {e}")

    def apply_to_all_videos(self):
        """Apply logo to ALL videos in the folder"""
        logo_path = self.logo_edit.text()

        if not logo_path:
            QMessageBox.warning(self, "No Logo", "Please select a logo file first!")
            return

        if not Path(logo_path).exists():
            QMessageBox.warning(self, "File Not Found", f"Logo file not found:\n{logo_path}")
            return

        if not self.video_files:
            QMessageBox.warning(self, "No Videos", "No video files found. Please scan a folder first.")
            return

        # Confirm
        reply = QMessageBox.question(
            self, "Apply to All Videos",
            f"Apply logo to {len(self.video_files)} videos?\n\nThis will add logo to all videos in the folder.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Process all videos
        from PyQt5.QtWidgets import QProgressDialog
        progress = QProgressDialog("Applying logo to videos...", "Cancel", 0, len(self.video_files), self)
        progress.setWindowTitle("Processing Videos")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        success_count = 0
        failed_count = 0

        for i, video_path in enumerate(self.video_files):
            if progress.wasCanceled():
                break

            progress.setValue(i)
            progress.setLabelText(f"Processing {i+1}/{len(self.video_files)}:\n{Path(video_path).name}")
            QApplication.processEvents()

            try:
                # Apply logo to this video
                output_path = self._apply_logo_to_video(video_path, logo_path)
                if output_path:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"Error processing {video_path}: {e}")
                failed_count += 1

        progress.setValue(len(self.video_files))
        progress.close()

        # Show result
        QMessageBox.information(
            self, "Complete",
            f"✅ Successfully processed: {success_count}\n❌ Failed: {failed_count}"
        )

    def _apply_logo_to_video(self, video_path, logo_path):
        """Apply logo to a single video file"""
        if not CV2_AVAILABLE:
            return None

        try:
            import subprocess

            # Get video info
            cap = cv2.VideoCapture(str(video_path))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()

            # Calculate logo size and position
            logo_size_percent = self.size_slider.value()
            logo_x = self.preview.logo_x
            logo_y = self.preview.logo_y
            opacity = self.opacity_slider.value() / 100.0

            # Calculate pixel positions
            logo_width = int(width * logo_size_percent / 100)
            x_pos = int(width * logo_x - logo_width / 2)
            y_pos = int(height * logo_y - logo_width / 2)

            # Output path
            output_path = str(Path(video_path).parent / f"{Path(video_path).stem}_logo{Path(video_path).suffix}")

            # FFmpeg command with logo overlay
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(logo_path),
                "-filter_complex",
                f"[1:v]scale={logo_width}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
                f"[0:v][logo]overlay={x_pos}:{y_pos}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                str(output_path)
            ]

            # Run FFmpeg
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path

        except Exception as e:
            print(f"Error applying logo: {e}")
            return None

    def apply_logo(self):
        """Apply logo and close dialog"""
        logo_path = self.logo_edit.text()

        if not logo_path:
            QMessageBox.warning(self, "No Logo", "Please select a logo file first!")
            return

        if not Path(logo_path).exists():
            QMessageBox.warning(self, "File Not Found", f"Logo file not found:\n{logo_path}")
            return

        self.use_logo = True

        # Build config in format expected by Step 7
        self.accepted_config = {
            "logo_path": logo_path,
            "position": self._get_position_name(),
            "size_percent": self.size_slider.value(),
            "opacity_percent": self.opacity_slider.value(),
            "padding_pixels": 20,
            "relative_x": self.preview.logo_x,
            "relative_y": self.preview.logo_y,
            # For accurate positioning - calculate exact pixel values
            "actual_video_width": self.preview.frame_width,
            "actual_video_height": self.preview.frame_height,
        }

        # Save config for future use
        self._save_config_to_file()

        self.accept()

    def skip_logo(self):
        """Skip adding logo"""
        self.use_logo = False
        self.accepted_config = None
        self.reject()

    def get_config(self):
        """Return the configuration (for Step 7 compatibility)"""
        if not self.use_logo:
            return None
        return self.accepted_config

    def _save_config_to_file(self):
        """Save logo configuration to file for future sessions"""
        config = {
            "enabled": True,
            "logo_path": self.logo_edit.text(),
            "position_x": self.preview.logo_x,
            "position_y": self.preview.logo_y,
            "size_percent": self.size_slider.value(),
            "opacity_percent": self.opacity_slider.value(),
            "position": self._get_position_name()
        }

        config_path = SCRIPT_DIR / "logo_config.json"

        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"Logo config saved to: {config_path}")
        except Exception as e:
            print(f"Warning: Could not save logo config: {e}")

    def _get_position_name(self):
        x, y = self.preview.logo_x, self.preview.logo_y

        if y < 0.33:
            v = "top"
        elif y > 0.66:
            v = "bottom"
        else:
            v = ""

        if x < 0.33:
            h = "left"
        elif x > 0.66:
            h = "right"
        else:
            h = "" if v else "center"

        return f"{v}-{h}".strip("-") or "center"


def main():
    app = QApplication(sys.argv)
    dialog = LogoEditorDialog(output_folder=sys.argv[1] if len(sys.argv) > 1 else None)
    dialog.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
