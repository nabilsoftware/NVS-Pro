"""
Visual Crop Tool - Smart Cropping for Step 2
Shows video frames with draggable crop rectangle and live preview

Features:
- Video thumbnails on the side (green border = cropped)
- Large preview with draggable crop rectangle
- Quick aspect ratio buttons (9:16, 16:9, 1:1, 4:3)
- "Apply to All" option for batch cropping
- Remembers crop between videos
- Lock aspect ratio while resizing
"""

import sys
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Tuple, Optional, List

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV not available. Install with: pip install opencv-python")

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSlider, QFileDialog, QGroupBox, QCheckBox,
    QSpinBox, QFrame, QScrollArea, QWidget, QMessageBox, QSizePolicy,
    QProgressBar, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QRect, QPoint
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QPen, QBrush, QCursor

SCRIPT_DIR = Path(__file__).parent.resolve()


class VideoThumbnail(QLabel):
    """Clickable video thumbnail"""
    clicked = pyqtSignal(int)  # Emits video index

    def __init__(self, index: int, video_path: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.video_path = video_path
        self.is_cropped = False

        self.setFixedSize(140, 80)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.update_style()

    def update_style(self):
        border_color = "#4CAF50" if self.is_cropped else "#3a3a6a"
        self.setStyleSheet(f"""
            QLabel {{
                border: 3px solid {border_color};
                border-radius: 5px;
                background-color: #252545;
            }}
            QLabel:hover {{
                border: 3px solid #2196F3;
            }}
        """)

    def set_cropped(self, cropped: bool):
        self.is_cropped = cropped
        self.update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)


class CropPreviewWidget(QLabel):
    """Main preview with draggable crop rectangle"""
    crop_changed = pyqtSignal(int, int, int, int)  # x, y, w, h in original coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(700, 450)
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setStyleSheet("""
            background-color: #1a1a2e;
            border: 3px solid #4CAF50;
            border-radius: 10px;
        """)

        # Original frame data
        self.original_frame = None
        self.frame_width = 1920
        self.frame_height = 1080

        # Video info for frame skipping
        self.video_path = None
        self.current_frame_pos = 0
        self.total_frames = 0
        self.fps = 30

        # Crop rectangle (in original frame coordinates)
        self.crop_x = 0
        self.crop_y = 0
        self.crop_w = 0
        self.crop_h = 0

        # Display scaling
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.display_w = 0
        self.display_h = 0

        # Dragging state
        self.dragging = False
        self.drag_mode = None  # 'move', 'tl', 'tr', 'bl', 'br', 't', 'b', 'l', 'r'
        self.drag_start = None
        self.drag_crop_start = None

        # Aspect ratio lock
        self.lock_aspect = False
        self.locked_aspect = 9/16  # Default portrait

        self.setText("Load a video to start cropping")

    def load_video_frame(self, video_path: str) -> bool:
        """Load frame from video"""
        if not CV2_AVAILABLE:
            self.setText("OpenCV not available")
            return False

        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                self.setText(f"Cannot open video")
                return False

            self.video_path = video_path
            self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = cap.get(cv2.CAP_PROP_FPS) or 30

            # Get frame from 1/3 into video (usually shows the subject well)
            self.current_frame_pos = self.total_frames // 3
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_pos)
            ret, frame = cap.read()
            cap.release()

            if ret:
                self.original_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Initialize crop to 80% centered
                margin_x = int(self.frame_width * 0.1)
                margin_y = int(self.frame_height * 0.1)
                self.crop_x = margin_x
                self.crop_y = margin_y
                self.crop_w = self.frame_width - 2 * margin_x
                self.crop_h = self.frame_height - 2 * margin_y
                self.update_display()
                return True
            return False
        except Exception as e:
            self.setText(f"Error: {str(e)[:50]}")
            return False

    def skip_frame(self, seconds: float = 5.0) -> bool:
        """Skip forward by given seconds and load new frame"""
        if not CV2_AVAILABLE or not self.video_path:
            return False

        try:
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                return False

            # Calculate new frame position (skip forward by seconds)
            frames_to_skip = int(seconds * self.fps)
            new_pos = self.current_frame_pos + frames_to_skip

            # Wrap around if past end
            if new_pos >= self.total_frames:
                new_pos = new_pos % self.total_frames
                if new_pos < 10:  # Avoid very beginning
                    new_pos = int(self.total_frames * 0.1)

            self.current_frame_pos = new_pos
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_pos)
            ret, frame = cap.read()
            cap.release()

            if ret:
                self.original_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.update_display()
                return True
            return False
        except Exception as e:
            print(f"Skip frame error: {e}")
            return False

    def seek_to_frame(self, frame_pos: int) -> bool:
        """Seek to specific frame position"""
        if not CV2_AVAILABLE or not self.video_path:
            return False

        try:
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                return False

            # Clamp frame position
            frame_pos = max(0, min(frame_pos, self.total_frames - 1))
            self.current_frame_pos = frame_pos
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            cap.release()

            if ret:
                self.original_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.update_display()
                return True
            return False
        except Exception as e:
            print(f"Seek frame error: {e}")
            return False

    def set_crop(self, x: int, y: int, w: int, h: int):
        """Set crop rectangle (in original coords)"""
        self.crop_x = max(0, min(x, self.frame_width - 100))
        self.crop_y = max(0, min(y, self.frame_height - 100))
        self.crop_w = max(100, min(w, self.frame_width - self.crop_x))
        self.crop_h = max(100, min(h, self.frame_height - self.crop_y))
        self.update_display()

    def get_crop(self) -> Tuple[int, int, int, int]:
        """Get current crop (in original coords)"""
        return (self.crop_x, self.crop_y, self.crop_w, self.crop_h)

    def set_aspect_ratio(self, aspect: float):
        """Set locked aspect ratio (w/h)"""
        self.locked_aspect = aspect
        if self.lock_aspect and self.original_frame is not None:
            # Adjust crop to match aspect
            center_x = self.crop_x + self.crop_w // 2
            center_y = self.crop_y + self.crop_h // 2

            # Try to maintain width, adjust height
            new_h = int(self.crop_w / aspect)
            if new_h <= self.frame_height:
                self.crop_h = new_h
            else:
                # Height limited, adjust width
                self.crop_h = self.frame_height - 2 * self.crop_y
                self.crop_w = int(self.crop_h * aspect)

            # Re-center
            self.crop_x = center_x - self.crop_w // 2
            self.crop_y = center_y - self.crop_h // 2

            # Clamp to bounds
            self.crop_x = max(0, min(self.crop_x, self.frame_width - self.crop_w))
            self.crop_y = max(0, min(self.crop_y, self.frame_height - self.crop_h))

            self.update_display()
            self.emit_crop_changed()

    def update_display(self):
        """Redraw preview with crop overlay"""
        if self.original_frame is None:
            return

        # Calculate display size
        available_w = self.width() - 20
        available_h = self.height() - 20

        self.scale = min(available_w / self.frame_width, available_h / self.frame_height)
        self.display_w = int(self.frame_width * self.scale)
        self.display_h = int(self.frame_height * self.scale)
        self.offset_x = (self.width() - self.display_w) // 2
        self.offset_y = (self.height() - self.display_h) // 2

        # Create display image
        frame = self.original_frame.copy()

        # Darken outside crop area
        mask = np.zeros_like(frame)
        mask[self.crop_y:self.crop_y+self.crop_h, self.crop_x:self.crop_x+self.crop_w] = 1
        frame = (frame * 0.3).astype(np.uint8)
        frame[self.crop_y:self.crop_y+self.crop_h, self.crop_x:self.crop_x+self.crop_w] = \
            self.original_frame[self.crop_y:self.crop_y+self.crop_h, self.crop_x:self.crop_x+self.crop_w]

        # Draw crop rectangle
        cv2.rectangle(frame,
                     (self.crop_x, self.crop_y),
                     (self.crop_x + self.crop_w, self.crop_y + self.crop_h),
                     (76, 175, 80), 3)

        # Draw corner handles (reasonable size)
        handle_size = max(12, int(18 / self.scale))
        corners = [
            (self.crop_x, self.crop_y),  # TL
            (self.crop_x + self.crop_w, self.crop_y),  # TR
            (self.crop_x, self.crop_y + self.crop_h),  # BL
            (self.crop_x + self.crop_w, self.crop_y + self.crop_h),  # BR
        ]
        for cx, cy in corners:
            # Draw filled square handle
            cv2.rectangle(frame,
                         (cx - handle_size//2, cy - handle_size//2),
                         (cx + handle_size//2, cy + handle_size//2),
                         (33, 150, 243), -1)
            # Draw border for visibility
            cv2.rectangle(frame,
                         (cx - handle_size//2, cy - handle_size//2),
                         (cx + handle_size//2, cy + handle_size//2),
                         (255, 255, 255), 1)

        # Draw edge handles (middle of each edge)
        edge_handle_size = max(8, int(12 / self.scale))
        edges = [
            (self.crop_x + self.crop_w // 2, self.crop_y),  # Top
            (self.crop_x + self.crop_w // 2, self.crop_y + self.crop_h),  # Bottom
            (self.crop_x, self.crop_y + self.crop_h // 2),  # Left
            (self.crop_x + self.crop_w, self.crop_y + self.crop_h // 2),  # Right
        ]
        for ex, ey in edges:
            cv2.rectangle(frame,
                         (ex - edge_handle_size//2, ey - edge_handle_size//2),
                         (ex + edge_handle_size//2, ey + edge_handle_size//2),
                         (76, 175, 80), -1)

        # Draw center crosshair
        center_x = self.crop_x + self.crop_w // 2
        center_y = self.crop_y + self.crop_h // 2
        cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (255, 255, 255), 1)
        cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (255, 255, 255), 1)

        # Draw dimensions
        dim_text = f"{self.crop_w}x{self.crop_h}"
        cv2.putText(frame, dim_text,
                   (self.crop_x + 10, self.crop_y + 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Resize for display
        display_frame = cv2.resize(frame, (self.display_w, self.display_h))

        # Convert to QPixmap
        h, w = display_frame.shape[:2]
        qimg = QImage(display_frame.data, w, h, 3 * w, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(qimg))

    def _to_original_coords(self, mx: int, my: int) -> Tuple[int, int]:
        """Convert widget coords to original frame coords"""
        ox = int((mx - self.offset_x) / self.scale)
        oy = int((my - self.offset_y) / self.scale)
        return ox, oy

    def _get_drag_mode(self, mx: int, my: int) -> Optional[str]:
        """Determine what part of crop rect is being clicked"""
        ox, oy = self._to_original_coords(mx, my)

        # Reasonable hit area for handles
        handle_size = max(25, int(30 / self.scale))

        # Check corners
        if abs(ox - self.crop_x) < handle_size and abs(oy - self.crop_y) < handle_size:
            return 'tl'
        if abs(ox - (self.crop_x + self.crop_w)) < handle_size and abs(oy - self.crop_y) < handle_size:
            return 'tr'
        if abs(ox - self.crop_x) < handle_size and abs(oy - (self.crop_y + self.crop_h)) < handle_size:
            return 'bl'
        if abs(ox - (self.crop_x + self.crop_w)) < handle_size and abs(oy - (self.crop_y + self.crop_h)) < handle_size:
            return 'br'

        # Check edges
        if self.crop_x < ox < self.crop_x + self.crop_w:
            if abs(oy - self.crop_y) < handle_size:
                return 't'
            if abs(oy - (self.crop_y + self.crop_h)) < handle_size:
                return 'b'
        if self.crop_y < oy < self.crop_y + self.crop_h:
            if abs(ox - self.crop_x) < handle_size:
                return 'l'
            if abs(ox - (self.crop_x + self.crop_w)) < handle_size:
                return 'r'

        # Check inside
        if self.crop_x < ox < self.crop_x + self.crop_w and self.crop_y < oy < self.crop_y + self.crop_h:
            return 'move'

        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.original_frame is not None:
            self.drag_mode = self._get_drag_mode(event.x(), event.y())
            if self.drag_mode:
                self.dragging = True
                self.drag_start = (event.x(), event.y())
                self.drag_crop_start = (self.crop_x, self.crop_y, self.crop_w, self.crop_h)

    def mouseMoveEvent(self, event):
        if self.original_frame is None:
            return

        # Update cursor based on position
        mode = self._get_drag_mode(event.x(), event.y())
        if mode in ('tl', 'br'):
            self.setCursor(Qt.SizeFDiagCursor)
        elif mode in ('tr', 'bl'):
            self.setCursor(Qt.SizeBDiagCursor)
        elif mode in ('t', 'b'):
            self.setCursor(Qt.SizeVerCursor)
        elif mode in ('l', 'r'):
            self.setCursor(Qt.SizeHorCursor)
        elif mode == 'move':
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if not self.dragging:
            return

        dx = int((event.x() - self.drag_start[0]) / self.scale)
        dy = int((event.y() - self.drag_start[1]) / self.scale)
        sx, sy, sw, sh = self.drag_crop_start

        # Check if Shift is held for symmetric resize (from center)
        shift_held = event.modifiers() & Qt.ShiftModifier

        if self.drag_mode == 'move':
            self.crop_x = max(0, min(sx + dx, self.frame_width - sw))
            self.crop_y = max(0, min(sy + dy, self.frame_height - sh))

        elif shift_held and self.drag_mode in ('l', 'r', 't', 'b', 'tl', 'tr', 'bl', 'br'):
            # SHIFT = Symmetric resize from center
            center_x = sx + sw // 2
            center_y = sy + sh // 2

            if self.drag_mode in ('l', 'r', 'tl', 'tr', 'bl', 'br'):
                # Horizontal symmetric
                if self.drag_mode in ('r', 'tr', 'br'):
                    new_half_w = max(50, sw // 2 + dx)
                else:
                    new_half_w = max(50, sw // 2 - dx)
                self.crop_w = new_half_w * 2
                self.crop_x = center_x - new_half_w

            if self.drag_mode in ('t', 'b', 'tl', 'tr', 'bl', 'br'):
                # Vertical symmetric
                if self.drag_mode in ('b', 'bl', 'br'):
                    new_half_h = max(50, sh // 2 + dy)
                else:
                    new_half_h = max(50, sh // 2 - dy)
                self.crop_h = new_half_h * 2
                self.crop_y = center_y - new_half_h

        else:
            # Normal resize (one edge only)
            if self.drag_mode == 'tl':
                new_x = max(0, sx + dx)
                new_y = max(0, sy + dy)
                self.crop_w = sw + (sx - new_x)
                self.crop_h = sh + (sy - new_y)
                self.crop_x = new_x
                self.crop_y = new_y
            elif self.drag_mode == 'tr':
                new_y = max(0, sy + dy)
                self.crop_w = max(100, sw + dx)
                self.crop_h = sh + (sy - new_y)
                self.crop_y = new_y
            elif self.drag_mode == 'bl':
                new_x = max(0, sx + dx)
                self.crop_w = sw + (sx - new_x)
                self.crop_h = max(100, sh + dy)
                self.crop_x = new_x
            elif self.drag_mode == 'br':
                self.crop_w = max(100, sw + dx)
                self.crop_h = max(100, sh + dy)
            elif self.drag_mode == 't':
                new_y = max(0, sy + dy)
                self.crop_h = sh + (sy - new_y)
                self.crop_y = new_y
            elif self.drag_mode == 'b':
                self.crop_h = max(100, sh + dy)
            elif self.drag_mode == 'l':
                new_x = max(0, sx + dx)
                self.crop_w = sw + (sx - new_x)
                self.crop_x = new_x
            elif self.drag_mode == 'r':
                self.crop_w = max(100, sw + dx)

        # Ensure minimum size
        self.crop_w = max(100, self.crop_w)
        self.crop_h = max(100, self.crop_h)

        # Clamp to bounds
        self.crop_x = max(0, self.crop_x)
        self.crop_y = max(0, self.crop_y)
        self.crop_w = min(self.crop_w, self.frame_width - self.crop_x)
        self.crop_h = min(self.crop_h, self.frame_height - self.crop_y)

        # Apply aspect ratio lock if enabled
        if self.lock_aspect and self.drag_mode not in ('move', None):
            # Maintain aspect ratio
            if self.drag_mode in ('l', 'r', 'tl', 'tr', 'bl', 'br'):
                self.crop_h = int(self.crop_w / self.locked_aspect)
            else:
                self.crop_w = int(self.crop_h * self.locked_aspect)

            # Re-clamp
            self.crop_w = min(self.crop_w, self.frame_width - self.crop_x)
            self.crop_h = min(self.crop_h, self.frame_height - self.crop_y)

        self.update_display()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.drag_mode = None
            self.emit_crop_changed()

    def emit_crop_changed(self):
        self.crop_changed.emit(self.crop_x, self.crop_y, self.crop_w, self.crop_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_frame is not None:
            self.update_display()


class CropToolDialog(QDialog):
    """Visual Crop Tool - for Step 2 cropping"""

    def __init__(self, video_files: List[Path] = None, existing_crops: Dict = None, parent=None):
        super().__init__(parent)
        self.video_files = video_files or []
        self.crops = existing_crops.copy() if existing_crops else {}
        self.excluded_files = []  # Track removed/excluded filenames
        self.current_index = 0
        self.thumbnails = []  # Keep references

        # Remember last crop for applying to next video
        self.last_crop = None  # (x, y, w, h) - will be applied to next video

        self.setWindowTitle("Visual Crop Tool - Smart Cropping")
        self.setFixedSize(1500, 850)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.setup_style()
        self.create_ui()

        if self.video_files:
            self.load_thumbnails()
            self.load_video(0)
            # Play notification sound (delayed to ensure window is shown)
            QTimer.singleShot(500, self.play_notification)

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
            QPushButton:disabled {
                background-color: #2a2a4a;
                color: #666;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QComboBox {
                background-color: #252545;
                color: #e0e0e0;
                border: 2px solid #3a3a6a;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QComboBox:focus {
                border: 2px solid #4CAF50;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)

    def create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Top info bar
        info_layout = QHBoxLayout()
        self.video_label = QLabel("No videos loaded")
        self.video_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
        info_layout.addWidget(self.video_label)

        info_layout.addStretch()

        self.progress_label = QLabel("0/0")
        self.progress_label.setStyleSheet("font-size: 14px; color: #888;")
        info_layout.addWidget(self.progress_label)

        main_layout.addLayout(info_layout)

        # Main content
        content_layout = QHBoxLayout()

        # Left: Video thumbnails
        thumb_group = QGroupBox("Videos (green = cropped)")
        thumb_layout = QVBoxLayout(thumb_group)

        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setWidgetResizable(True)
        self.thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumb_scroll.setMinimumWidth(160)
        self.thumb_scroll.setMaximumWidth(180)

        self.thumb_container = QWidget()
        self.thumb_grid = QVBoxLayout(self.thumb_container)
        self.thumb_grid.setSpacing(8)
        self.thumb_grid.setAlignment(Qt.AlignTop)
        self.thumb_scroll.setWidget(self.thumb_container)

        thumb_layout.addWidget(self.thumb_scroll)
        content_layout.addWidget(thumb_group)

        # Center: Preview
        preview_group = QGroupBox("Preview - Drag corners/edges to adjust crop")
        preview_layout = QVBoxLayout(preview_group)

        self.preview = CropPreviewWidget()
        self.preview.crop_changed.connect(self.on_crop_changed)
        preview_layout.addWidget(self.preview, stretch=1)

        # Crop info
        self.crop_info = QLabel("Crop: 0x0 at (0, 0)")
        self.crop_info.setAlignment(Qt.AlignCenter)
        self.crop_info.setStyleSheet("font-size: 13px; color: #4CAF50; font-weight: bold;")
        preview_layout.addWidget(self.crop_info)

        # Frame Scrubber
        scrubber_layout = QHBoxLayout()
        scrubber_layout.setSpacing(12)

        scrub_label = QLabel("Frame:")
        scrub_label.setStyleSheet("color: #FFF; font-size: 12px; font-weight: bold;")
        scrubber_layout.addWidget(scrub_label)

        self.frame_scrubber = QSlider(Qt.Horizontal)
        self.frame_scrubber.setRange(0, 100)
        self.frame_scrubber.setValue(50)
        self.frame_scrubber.setMinimumHeight(25)
        self.frame_scrubber.valueChanged.connect(self.on_frame_scrubber_changed)
        scrubber_layout.addWidget(self.frame_scrubber, stretch=1)

        self.frame_label = QLabel("50%")
        self.frame_label.setMinimumWidth(120)
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px; background-color: #1a1a2e; border-radius: 4px; padding: 4px;")
        scrubber_layout.addWidget(self.frame_label)

        preview_layout.addLayout(scrubber_layout)

        content_layout.addWidget(preview_group, stretch=1)

        # Right: Controls
        controls_group = QGroupBox("Crop Settings")
        controls_group.setMaximumWidth(280)
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(12)

        # Quick actions
        controls_layout.addWidget(QLabel("Quick Actions:"))

        btn_center = QPushButton("Center Crop")
        btn_center.clicked.connect(self.center_crop)
        controls_layout.addWidget(btn_center)

        btn_maximize = QPushButton("Maximize (80%)")
        btn_maximize.clicked.connect(self.maximize_crop)
        controls_layout.addWidget(btn_maximize)

        btn_tight = QPushButton("Tight Crop (60%)")
        btn_tight.clicked.connect(self.tight_crop)
        controls_layout.addWidget(btn_tight)

        # New Frame button - skip 5 seconds to get different frame
        btn_new_frame = QPushButton("New Frame [N]")
        btn_new_frame.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                padding: 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #AB47BC;
            }
        """)
        btn_new_frame.setToolTip("Skip 5 seconds to get a different frame (Shortcut: N)")
        btn_new_frame.clicked.connect(self.get_new_frame)
        controls_layout.addWidget(btn_new_frame)

        controls_layout.addSpacing(10)

        # Apply to all
        self.apply_all_check = QCheckBox("Apply this crop to ALL remaining videos")
        self.apply_all_check.setStyleSheet("color: #FF9800; font-weight: bold;")
        controls_layout.addWidget(self.apply_all_check)

        controls_layout.addStretch()

        # Navigation buttons
        nav_layout = QHBoxLayout()

        self.btn_prev = QPushButton("< Prev")
        self.btn_prev.clicked.connect(self.prev_video)
        nav_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.next_video)
        nav_layout.addWidget(self.btn_next)

        controls_layout.addLayout(nav_layout)

        # Delete and Restore buttons
        delete_restore_layout = QHBoxLayout()

        self.btn_delete = QPushButton("Remove [R]")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                padding: 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.btn_delete.clicked.connect(self.delete_current_video)
        delete_restore_layout.addWidget(self.btn_delete)

        self.btn_restore = QPushButton("Restore")
        self.btn_restore.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                padding: 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.btn_restore.clicked.connect(self.restore_excluded_videos)
        delete_restore_layout.addWidget(self.btn_restore)

        controls_layout.addLayout(delete_restore_layout)

        # Save current (S or Enter = save and go next)
        btn_save_current = QPushButton("Save + Next  [S]")
        btn_save_current.setStyleSheet("background-color: #4CAF50; padding: 14px; font-size: 14px; font-weight: bold;")
        btn_save_current.clicked.connect(self.save_current_crop)
        controls_layout.addWidget(btn_save_current)

        controls_layout.addSpacing(10)

        # Keyboard shortcuts info
        shortcuts_label = QLabel("S=Save+Next | R=Remove | N=New Frame")
        shortcuts_label.setStyleSheet("color: #888; font-size: 10px;")
        shortcuts_label.setAlignment(Qt.AlignCenter)
        controls_layout.addWidget(shortcuts_label)

        controls_layout.addSpacing(10)

        # Finish buttons
        btn_finish = QPushButton("Finish All")
        btn_finish.setStyleSheet("background-color: #2196F3; padding: 14px; font-size: 14px;")
        btn_finish.clicked.connect(self.finish_all)
        controls_layout.addWidget(btn_finish)

        btn_cancel = QPushButton("Cancel  [Esc]")
        btn_cancel.setStyleSheet("background-color: #666; padding: 10px;")
        btn_cancel.clicked.connect(self.cancel)
        controls_layout.addWidget(btn_cancel)

        content_layout.addWidget(controls_group)
        main_layout.addLayout(content_layout, stretch=1)

    def load_thumbnails(self):
        """Create thumbnails for all videos"""
        # Clear existing
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.thumbnails = []

        if not CV2_AVAILABLE:
            return

        for i, video_path in enumerate(self.video_files):
            try:
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    continue

                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.set(cv2.CAP_PROP_POS_FRAMES, total // 3)
                ret, frame = cap.read()
                cap.release()

                if not ret:
                    continue

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame.shape[:2]
                qimg = QImage(frame.data, w, h, 3 * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(140, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                thumb = VideoThumbnail(i, str(video_path))
                thumb.setPixmap(scaled)
                thumb.setToolTip(video_path.name)
                thumb.clicked.connect(self.on_thumbnail_clicked)

                # Mark if already cropped
                if video_path.name in self.crops:
                    thumb.set_cropped(True)

                self.thumb_grid.addWidget(thumb)
                self.thumbnails.append(thumb)

            except Exception as e:
                print(f"Error creating thumbnail: {e}")

    def on_thumbnail_clicked(self, index: int):
        """Load clicked video"""
        self.save_current_crop_silent()
        self.load_video(index)

    def load_video(self, index: int):
        """Load video at index"""
        if not self.video_files or index < 0 or index >= len(self.video_files):
            return

        self.current_index = index
        video_path = self.video_files[index]

        self.video_label.setText(f"{video_path.name}")
        self.progress_label.setText(f"{index + 1}/{len(self.video_files)}")

        # Load frame
        self.preview.load_video_frame(str(video_path))

        # Apply existing crop if available
        if video_path.name in self.crops:
            crop = self.crops[video_path.name]
            self.preview.set_crop(*crop)
        # Or apply last crop (same position for all videos)
        elif self.last_crop is not None:
            self.preview.set_crop(*self.last_crop)

        self.update_crop_info()
        self.update_nav_buttons()

    def on_crop_changed(self, x: int, y: int, w: int, h: int):
        """Called when crop rectangle changes"""
        self.update_crop_info()

    def on_frame_scrubber_changed(self, value):
        """Handle frame scrubber change"""
        if self.preview.total_frames > 0:
            frame_pos = int(value / 100.0 * self.preview.total_frames)
            self.frame_label.setText(f"{frame_pos} / {self.preview.total_frames}")
            self.preview.seek_to_frame(frame_pos)
        else:
            self.frame_label.setText(f"{value}%")

    def update_crop_info(self):
        """Update crop info label"""
        x, y, w, h = self.preview.get_crop()
        aspect = w / h if h > 0 else 0
        self.crop_info.setText(f"Crop: {w}x{h} at ({x}, {y}) | Aspect: {aspect:.2f}")

    def update_nav_buttons(self):
        """Update navigation button states"""
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.video_files) - 1)

    def prev_video(self):
        if self.current_index > 0:
            self.save_current_crop_silent()
            self.load_video(self.current_index - 1)

    def next_video(self):
        if self.current_index < len(self.video_files) - 1:
            self.save_current_crop_silent()
            self.load_video(self.current_index + 1)

    def delete_current_video(self):
        """Delete current video (move to excluded folder)"""
        if not self.video_files:
            return

        video_path = self.video_files[self.current_index]
        video_name = video_path.name

        # Confirmation dialog
        reply = QMessageBox.question(
            self, "Delete Interview?",
            f"Move this interview to 'excluded' folder?\n\n"
            f"{video_name}\n\n"
            f"This interview will NOT be processed in Step 2.\n"
            f"(You can recover it from the 'excluded' folder later)",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # Create excluded folder in the same directory as the video
            excluded_folder = video_path.parent / "excluded"
            excluded_folder.mkdir(exist_ok=True)

            # Move the file
            dest_path = excluded_folder / video_name
            shutil.move(str(video_path), str(dest_path))

            print(f"Moved to excluded: {video_name}")

            # Track excluded file
            self.excluded_files.append(video_name)

            # Remove from crops if exists
            if video_name in self.crops:
                del self.crops[video_name]

            # Remove from video_files list
            del self.video_files[self.current_index]

            # Remove thumbnail
            if self.current_index < len(self.thumbnails):
                thumb = self.thumbnails[self.current_index]
                self.thumb_grid.removeWidget(thumb)
                thumb.deleteLater()
                del self.thumbnails[self.current_index]

                # Update remaining thumbnail indices
                for i, t in enumerate(self.thumbnails):
                    t.index = i

            # Update progress label
            self.progress_label.setText(f"{self.current_index + 1}/{len(self.video_files)}")

            # Load next video (or previous if at end)
            if len(self.video_files) == 0:
                QMessageBox.information(self, "No Videos", "All interviews have been deleted.")
                self.reject()
                return

            if self.current_index >= len(self.video_files):
                self.current_index = len(self.video_files) - 1

            self.load_video(self.current_index)

            QMessageBox.information(
                self, "Deleted",
                f"{video_name} moved to 'excluded' folder.\n\n"
                f"Remaining: {len(self.video_files)} interviews"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to delete interview:\n{str(e)}"
            )

    def restore_excluded_videos(self):
        """Restore videos from excluded folder"""
        if not self.video_files:
            QMessageBox.warning(self, "No Videos", "No videos loaded to find excluded folder.")
            return

        # Find excluded folder (same parent as current videos)
        parent_folder = self.video_files[0].parent
        excluded_folder = parent_folder / "excluded"

        if not excluded_folder.exists():
            QMessageBox.information(
                self, "No Excluded Videos",
                "No 'excluded' folder found.\n\nNo videos have been removed yet."
            )
            return

        # Find videos in excluded folder
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v'}
        excluded_videos = [f for f in sorted(excluded_folder.iterdir())
                          if f.is_file() and f.suffix.lower() in video_extensions]

        if not excluded_videos:
            QMessageBox.information(
                self, "No Excluded Videos",
                "The 'excluded' folder is empty.\n\nNo videos to restore."
            )
            return

        # Create selection dialog
        from PyQt5.QtWidgets import QDialog, QListWidget, QListWidgetItem, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Restore Excluded Videos")
        dialog.setMinimumSize(400, 300)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QListWidget {
                background-color: #252545;
                color: #e0e0e0;
                border: 2px solid #3a3a6a;
                border-radius: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
            QListWidget::item:hover {
                background-color: #3a3a6a;
            }
        """)

        layout = QVBoxLayout(dialog)

        label = QLabel(f"Select videos to restore ({len(excluded_videos)} excluded):")
        label.setStyleSheet("color: #FF9800; font-weight: bold;")
        layout.addWidget(label)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)
        for video in excluded_videos:
            item = QListWidgetItem(video.name)
            item.setData(Qt.UserRole, video)
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        # Select all button
        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(lambda: list_widget.selectAll())
        layout.addWidget(btn_select_all)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() != QDialog.Accepted:
            return

        # Get selected items
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return

        restored_count = 0
        for item in selected_items:
            video_path = item.data(Qt.UserRole)
            try:
                # Move back to parent folder
                dest_path = parent_folder / video_path.name
                shutil.move(str(video_path), str(dest_path))

                # Add to video_files list
                self.video_files.append(dest_path)
                restored_count += 1

                # Remove from excluded list
                if video_path.name in self.excluded_files:
                    self.excluded_files.remove(video_path.name)

                print(f"Restored: {video_path.name}")

            except Exception as e:
                print(f"Error restoring {video_path.name}: {e}")

        # Sort video files
        self.video_files.sort(key=lambda x: x.name)

        # Reload thumbnails
        self.load_thumbnails()

        # Update progress
        self.progress_label.setText(f"{self.current_index + 1}/{len(self.video_files)}")

        QMessageBox.information(
            self, "Restored",
            f"Restored {restored_count} video(s).\n\n"
            f"Total interviews: {len(self.video_files)}"
        )

    def save_current_crop_silent(self):
        """Save current crop without UI feedback"""
        if not self.video_files:
            return

        video_name = self.video_files[self.current_index].name
        crop = self.preview.get_crop()
        self.crops[video_name] = crop

        # Remember this crop for next video
        self.last_crop = crop

        # Update thumbnail
        self.update_thumbnail_status(self.current_index, True)

    def save_current_crop(self):
        """Save current crop and go to next video"""
        self.save_current_crop_silent()

        video_name = self.video_files[self.current_index].name
        crop = self.crops[video_name]

        # Apply to all if checked
        if self.apply_all_check.isChecked():
            for i in range(self.current_index + 1, len(self.video_files)):
                name = self.video_files[i].name
                self.crops[name] = crop
                self.update_thumbnail_status(i, True)

            QMessageBox.information(
                self, "Saved",
                f"Crop saved!\n\n"
                f"Applied to this + {len(self.video_files) - self.current_index - 1} remaining videos.\n"
                f"Size: {crop[2]}x{crop[3]}"
            )
        else:
            # Always move to next if available (auto-next)
            if self.current_index < len(self.video_files) - 1:
                self.load_video(self.current_index + 1)
            else:
                # Last video - S acts as Finish (no need to click button)
                self.finish_all()

    def update_thumbnail_status(self, index: int, cropped: bool):
        """Update thumbnail border to show cropped status"""
        if index < len(self.thumbnails):
            self.thumbnails[index].set_cropped(cropped)

    def apply_aspect_ratio(self, ratio: float):
        """Apply aspect ratio preset"""
        self.preview.locked_aspect = ratio
        self.preview.set_aspect_ratio(ratio)
        self.lock_aspect_check.setChecked(True)

    def on_lock_aspect_changed(self, state):
        self.preview.lock_aspect = state == Qt.Checked

    def center_crop(self):
        """Center current crop"""
        x, y, w, h = self.preview.get_crop()
        new_x = (self.preview.frame_width - w) // 2
        new_y = (self.preview.frame_height - h) // 2
        self.preview.set_crop(new_x, new_y, w, h)

    def maximize_crop(self):
        """Set crop to 80% of frame"""
        margin_x = int(self.preview.frame_width * 0.1)
        margin_y = int(self.preview.frame_height * 0.1)
        self.preview.set_crop(
            margin_x, margin_y,
            self.preview.frame_width - 2 * margin_x,
            self.preview.frame_height - 2 * margin_y
        )

    def tight_crop(self):
        """Set crop to 60% of frame (tight)"""
        margin_x = int(self.preview.frame_width * 0.2)
        margin_y = int(self.preview.frame_height * 0.2)
        self.preview.set_crop(
            margin_x, margin_y,
            self.preview.frame_width - 2 * margin_x,
            self.preview.frame_height - 2 * margin_y
        )

    def get_new_frame(self):
        """Skip 5 seconds to get a different frame"""
        if self.preview.skip_frame(5.0):
            # Keep the same crop position
            pass

    def finish_all(self):
        """Finish cropping and return results"""
        # Save current
        self.save_current_crop_silent()

        # Check for uncropped videos
        uncropped = []
        for video in self.video_files:
            if video.name not in self.crops:
                uncropped.append(video.name)

        if uncropped:
            reply = QMessageBox.question(
                self, "Uncropped Videos",
                f"{len(uncropped)} videos don't have crops set.\n\n"
                f"They will use AI auto-crop.\n\n"
                f"Continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.accept()

    def cancel(self):
        """Cancel and discard changes"""
        reply = QMessageBox.question(
            self, "Cancel?",
            "Discard all crop changes?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.crops = {}
            self.reject()

    def get_crops(self) -> Dict[str, Tuple[int, int, int, int]]:
        """Return all crop settings"""
        return self.crops

    def get_excluded_files(self) -> List[str]:
        """Return list of excluded/removed filenames"""
        return self.excluded_files

    def play_notification(self):
        """Play notification sound in background (no player window)"""
        try:
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

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        key = event.key()

        # S = Save and Next
        if key == Qt.Key_S:
            self.save_current_crop()
        # R = Remove current video
        elif key == Qt.Key_R:
            self.delete_current_video()
        # N = New Frame (skip 5 seconds)
        elif key == Qt.Key_N:
            self.get_new_frame()
        # Left/Right arrows for navigation
        elif key == Qt.Key_Left:
            self.prev_video()
        elif key == Qt.Key_Right:
            self.next_video()
        # Enter = Save and Next
        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            self.save_current_crop()
        # Escape = Cancel
        elif key == Qt.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)


def show_crop_tool(video_files: List[Path], existing_crops: Dict = None) -> Optional[Dict]:
    """Show crop tool dialog and return results

    This function is called from 2_style_interview_clips.py during Step 2.
    Returns dict of {filename: (x, y, w, h)} or None if cancelled.
    The returned dict includes a special "__excluded__" key with list of removed filenames.
    """
    print("")
    print("=" * 60)
    print("VISUAL CROP TOOL - Smart Cropping")
    print("=" * 60)
    print("-> Click on video thumbnails to preview")
    print("-> Drag corners/edges to resize crop area")
    print("-> Use aspect ratio buttons for quick presets")
    print("-> Check 'Apply to ALL' to batch crop")
    print("=" * 60)
    print("")

    app = QApplication.instance()
    if not app:
        app = QApplication([])

    dialog = CropToolDialog(video_files=video_files, existing_crops=existing_crops)
    result = dialog.exec_()

    if result == QDialog.Accepted:
        crops = dialog.get_crops()
        excluded = dialog.get_excluded_files()
        if excluded:
            crops["__excluded__"] = excluded
            print(f"\nCrop tool finished: {len(crops) - 1} videos cropped, {len(excluded)} excluded")
        else:
            print(f"\nCrop tool finished: {len(crops)} videos cropped")
        return crops

    print("\nCrop tool cancelled")
    return None


def main():
    """Standalone test / command line usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Visual Crop Tool")
    parser.add_argument('--input', '-i', help="Input folder with videos")
    parser.add_argument('--output', '-o', default="manual_crops.json", help="Output JSON file")

    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Find videos
    if args.input:
        folder = Path(args.input)
    else:
        folder = Path(".")

    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v'}
    videos = [f for f in sorted(folder.iterdir())
              if f.is_file() and f.suffix.lower() in video_extensions]

    if not videos:
        print(f"No videos found in: {folder}")
        sys.exit(1)

    print(f"Found {len(videos)} videos")

    # Load existing crops
    existing = {}
    output_file = Path(args.output)
    if output_file.exists():
        try:
            with open(output_file, 'r') as f:
                existing = json.load(f)
            print(f"Loaded {len(existing)} existing crops")
        except:
            pass

    # Show dialog
    dialog = CropToolDialog(video_files=videos, existing_crops=existing)
    if dialog.exec_() == QDialog.Accepted:
        crops = dialog.get_crops()

        # Merge and save
        all_crops = {**existing, **crops}
        with open(output_file, 'w') as f:
            json.dump(all_crops, f, indent=2)

        print(f"\nSaved {len(all_crops)} crops to: {output_file}")
    else:
        print("\nCancelled")


if __name__ == "__main__":
    main()
