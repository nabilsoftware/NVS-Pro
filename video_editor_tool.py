"""
Smart Video Editor - NEW DESIGN
- Easy zoom and crop controls
- Logo library with history
- Simple, clean interface
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
    print("Warning: OpenCV not available")

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSlider, QFileDialog,
    QGroupBox, QCheckBox, QFrame, QScrollArea, QGridLayout,
    QWidget, QSizePolicy, QMessageBox, QListWidget, QListWidgetItem, QToolButton,
    QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush, QIcon

SCRIPT_DIR = Path(__file__).parent.resolve()


def get_user_data_dir():
    if os.name == 'nt':
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        return Path(appdata) / "NabilVideoStudioPro"
    return Path.home() / ".nvspro"


def get_logo_history_file():
    """Get path to logo history file"""
    data_dir = get_user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "logo_history.json"


def load_logo_history():
    """Load logo usage history"""
    history_file = get_logo_history_file()
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def save_logo_to_history(logo_path):
    """Save logo to history"""
    if not logo_path or not Path(logo_path).exists():
        return

    history = load_logo_history()

    # Check if already in history
    for item in history:
        if item.get('path') == str(logo_path):
            # Update last used time
            item['last_used'] = datetime.now().isoformat()
            item['count'] = item.get('count', 0) + 1
            break
    else:
        # Add new entry
        history.append({
            'path': str(logo_path),
            'name': Path(logo_path).name,
            'last_used': datetime.now().isoformat(),
            'count': 1
        })

    # Keep only last 20 logos
    history = sorted(history, key=lambda x: x['last_used'], reverse=True)[:20]

    # Save
    history_file = get_logo_history_file()
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


class SmartCropPreview(QLabel):
    """Video preview with smart 16:9 crop selection"""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 450)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            background-color: #0a0a0a;
            border: 3px solid #4CAF50;
            border-radius: 10px;
        """)
        self.setCursor(Qt.OpenHandCursor)

        # Video
        self.original_frame = None
        self.video_path = None
        self.total_frames = 0
        self.current_frame_pos = 0
        self.frame_width = 1920
        self.frame_height = 1080

        # Zoom and Pan
        self.zoom_level = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 3.0
        self.pan_x = 0.5
        self.pan_y = 0.5

        # Logo
        self.logo_enabled = False
        self.logo_original = None
        self.logo_path = ""
        self.logo_x = 0.90
        self.logo_y = 0.10
        self.logo_size_percent = 12
        self.logo_opacity = 90

        # Dragging
        self.dragging = False
        self.drag_mode = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_pan = (0.5, 0.5)

        # Display
        self.scale_factor = 1.0
        self.display_offset_x = 0
        self.display_offset_y = 0
        self.display_width = 0
        self.display_height = 0

        self.setText("Click a video to preview\nScroll to zoom • Drag to pan")
        self.setStyleSheet(self.styleSheet() + "color: #666; font-size: 16px;")

    def load_video_frame(self, video_path, frame_position=None):
        """Load a frame from video"""
        if not CV2_AVAILABLE:
            self.setText("OpenCV not available")
            return False

        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                self.setText(f"Cannot open: {Path(video_path).name}")
                return False

            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.video_path = video_path

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

            self.setText("Failed to read frame")
            return False

        except Exception as e:
            self.setText(f"Error: {str(e)[:50]}")
            return False

    def seek_frame(self, frame_pos):
        """Seek to specific frame"""
        if self.video_path:
            self.load_video_frame(self.video_path, frame_pos)

    def set_zoom(self, zoom_level):
        """Set zoom level"""
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, zoom_level))
        self._clamp_pan()
        self.update_preview()
        self.settings_changed.emit()

    def reset_crop(self):
        """Reset to full frame"""
        self.zoom_level = 1.0
        self.pan_x = 0.5
        self.pan_y = 0.5
        self.update_preview()
        self.settings_changed.emit()

    def _clamp_pan(self):
        """Keep pan within valid range"""
        if self.zoom_level <= 1.0:
            self.pan_x = 0.5
            self.pan_y = 0.5
            return

        visible_fraction = 1.0 / self.zoom_level
        half_visible = visible_fraction / 2.0

        self.pan_x = max(half_visible, min(1.0 - half_visible, self.pan_x))
        self.pan_y = max(half_visible, min(1.0 - half_visible, self.pan_y))

    def load_logo(self, logo_path):
        """Load logo image"""
        if not CV2_AVAILABLE:
            return False

        try:
            logo = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
            if logo is None:
                return False

            if len(logo.shape) == 2:
                logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2RGBA)
            elif logo.shape[2] == 3:
                logo = cv2.cvtColor(logo, cv2.COLOR_BGR2RGBA)
            elif logo.shape[2] == 4:
                logo = cv2.cvtColor(logo, cv2.COLOR_BGRA2RGBA)

            self.logo_original = logo
            self.logo_path = logo_path
            self.update_preview()

            # Save to history
            save_logo_to_history(logo_path)

            return True

        except Exception as e:
            print(f"Error loading logo: {e}")
            return False

    def update_preview(self):
        """Redraw preview"""
        if self.original_frame is None:
            return

        frame = self.original_frame.copy()
        h, w = frame.shape[:2]

        bytes_per_line = 3 * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        available_w = self.width() - 20
        available_h = self.height() - 20
        scaled = pixmap.scaled(available_w, available_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.scale_factor = scaled.width() / w
        self.display_width = scaled.width()
        self.display_height = scaled.height()
        self.display_offset_x = (self.width() - scaled.width()) // 2
        self.display_offset_y = (self.height() - scaled.height()) // 2

        painter = QPainter(scaled)
        painter.setRenderHint(QPainter.Antialiasing)

        # Crop overlay
        visible_w = self.display_width / self.zoom_level
        visible_h = self.display_height / self.zoom_level
        center_x = self.pan_x * self.display_width
        center_y = self.pan_y * self.display_height
        crop_x = center_x - visible_w / 2
        crop_y = center_y - visible_h / 2

        # Dark overlay
        dark_brush = QBrush(QColor(0, 0, 0, 150))
        if crop_y > 0:
            painter.fillRect(0, 0, self.display_width, int(crop_y), dark_brush)
        if crop_y + visible_h < self.display_height:
            painter.fillRect(0, int(crop_y + visible_h), self.display_width, int(self.display_height - crop_y - visible_h), dark_brush)
        if crop_x > 0:
            painter.fillRect(0, int(crop_y), int(crop_x), int(visible_h), dark_brush)
        if crop_x + visible_w < self.display_width:
            painter.fillRect(int(crop_x + visible_w), int(crop_y), int(self.display_width - crop_x - visible_w), int(visible_h), dark_brush)

        # Crop border
        pen = QPen(QColor(76, 175, 80), 3)
        painter.setPen(pen)
        painter.drawRect(int(crop_x), int(crop_y), int(visible_w), int(visible_h))

        # Crosshair
        if self.zoom_level > 1.0:
            pen = QPen(QColor(76, 175, 80, 100), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(int(crop_x), int(center_y), int(crop_x + visible_w), int(center_y))
            painter.drawLine(int(center_x), int(crop_y), int(center_x), int(crop_y + visible_h))

        painter.setPen(QColor(76, 175, 80))
        painter.drawText(int(crop_x + 8), int(crop_y + 18), "16:9 Full Screen")

        # Logo preview
        if self.logo_enabled and self.logo_original is not None:
            logo_w = int(visible_w * self.logo_size_percent / 100)
            aspect = self.logo_original.shape[0] / self.logo_original.shape[1]
            logo_h = int(logo_w * aspect)

            logo_x = int(crop_x + self.logo_x * visible_w - logo_w / 2)
            logo_y = int(crop_y + self.logo_y * visible_h - logo_h / 2)

            logo_resized = cv2.resize(self.logo_original, (logo_w, logo_h), interpolation=cv2.INTER_AREA)
            opacity = self.logo_opacity / 100.0

            if logo_resized.shape[2] == 4:
                logo_resized = logo_resized.copy()
                logo_resized[:, :, 3] = (logo_resized[:, :, 3] * opacity).astype(np.uint8)
                qimg_logo = QImage(logo_resized.data, logo_w, logo_h, logo_w * 4, QImage.Format_RGBA8888)
            else:
                qimg_logo = QImage(logo_resized.data, logo_w, logo_h, logo_w * 3, QImage.Format_RGB888)

            logo_pixmap = QPixmap.fromImage(qimg_logo)
            painter.setOpacity(opacity if logo_resized.shape[2] != 4 else 1.0)
            painter.drawPixmap(logo_x, logo_y, logo_pixmap)
            painter.setOpacity(1.0)

            pen = QPen(QColor(255, 152, 0), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(logo_x, logo_y, logo_w, logo_h)

        painter.end()
        self.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.original_frame is not None:
            mx, my = event.x(), event.y()

            # Check logo click
            if self.logo_enabled and self.logo_original is not None and self.zoom_level >= 1.0:
                visible_w = self.display_width / self.zoom_level
                visible_h = self.display_height / self.zoom_level
                center_x = self.pan_x * self.display_width
                center_y = self.pan_y * self.display_height
                crop_x = center_x - visible_w / 2 + self.display_offset_x
                crop_y = center_y - visible_h / 2 + self.display_offset_y

                logo_w = int(visible_w * self.logo_size_percent / 100)
                aspect = self.logo_original.shape[0] / self.logo_original.shape[1]
                logo_h = int(logo_w * aspect)
                logo_x = int(crop_x + self.logo_x * visible_w - logo_w / 2)
                logo_y = int(crop_y + self.logo_y * visible_h - logo_h / 2)

                if logo_x <= mx <= logo_x + logo_w and logo_y <= my <= logo_y + logo_h:
                    self.dragging = True
                    self.drag_mode = "logo"
                    self.drag_start_x = mx
                    self.drag_start_y = my
                    self.setCursor(Qt.ClosedHandCursor)
                    return

            # Pan mode
            self.dragging = True
            self.drag_mode = "pan"
            self.drag_start_x = mx
            self.drag_start_y = my
            self.drag_start_pan = (self.pan_x, self.pan_y)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if not self.dragging or self.original_frame is None:
            return

        mx, my = event.x(), event.y()

        if self.drag_mode == "pan" and self.zoom_level > 1.0:
            dx = (mx - self.drag_start_x) / self.display_width
            dy = (my - self.drag_start_y) / self.display_height

            self.pan_x = self.drag_start_pan[0] + dx
            self.pan_y = self.drag_start_pan[1] + dy
            self._clamp_pan()

            self.update_preview()
            self.settings_changed.emit()

        elif self.drag_mode == "logo":
            visible_w = self.display_width / self.zoom_level
            visible_h = self.display_height / self.zoom_level

            dx = (mx - self.drag_start_x) / visible_w
            dy = (my - self.drag_start_y) / visible_h

            self.logo_x = max(0.05, min(0.95, self.logo_x + dx))
            self.logo_y = max(0.05, min(0.95, self.logo_y + dy))
            self.drag_start_x = mx
            self.drag_start_y = my

            self.update_preview()
            self.settings_changed.emit()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.drag_mode = None
            self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, event):
        """Scroll to zoom"""
        if self.original_frame is None:
            return

        delta = event.angleDelta().y()
        zoom_change = 0.1 if delta > 0 else -0.1

        new_zoom = self.zoom_level + zoom_change
        self.set_zoom(new_zoom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_frame is not None:
            self.update_preview()

    def get_crop_pixels(self):
        """Get crop coordinates for ffmpeg"""
        base_w, base_h = 1920, 1080

        crop_w = int(base_w / self.zoom_level)
        crop_h = int(base_h / self.zoom_level)

        center_x = self.pan_x * base_w
        center_y = self.pan_y * base_h
        crop_x = int(center_x - crop_w / 2)
        crop_y = int(center_y - crop_h / 2)

        crop_x = max(0, min(base_w - crop_w, crop_x))
        crop_y = max(0, min(base_h - crop_h, crop_y))

        return crop_x, crop_y, crop_w, crop_h


class LogoThumbnail(QToolButton):
    """Clickable logo thumbnail with image"""
    clicked_path = pyqtSignal(str)

    def __init__(self, logo_path, logo_name, count=0, parent=None):
        super().__init__(parent)
        self.logo_path = logo_path
        self.logo_name = logo_name
        self.count = count

        self.setFixedSize(95, 70)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setText(f"{count}x")
        self.setToolTip(f"{logo_name}\nClick to use")
        self.setStyleSheet("""
            QToolButton {
                background-color: #0d0d1a;
                border: 2px solid #2a2a4a;
                border-radius: 6px;
                color: #888;
                font-size: 8px;
                padding: 3px;
            }
            QToolButton:hover {
                border: 2px solid #4CAF50;
                background-color: #1a2a1a;
                color: #4CAF50;
            }
            QToolButton:pressed {
                background-color: #2a4a2a;
                border: 2px solid #66BB6A;
            }
        """)
        self.clicked.connect(lambda: self.clicked_path.emit(self.logo_path))

        # Load thumbnail
        self.load_thumbnail()

    def load_thumbnail(self):
        """Load logo thumbnail"""
        if not CV2_AVAILABLE or not Path(self.logo_path).exists():
            return

        try:
            logo = cv2.imread(str(self.logo_path), cv2.IMREAD_UNCHANGED)
            if logo is None:
                return

            # Convert to RGB
            if len(logo.shape) == 2:
                logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2RGB)
            elif logo.shape[2] == 4:
                logo = cv2.cvtColor(logo, cv2.COLOR_BGRA2RGB)
            elif logo.shape[2] == 3:
                logo = cv2.cvtColor(logo, cv2.COLOR_BGR2RGB)

            # Resize to compact thumbnail
            h, w = logo.shape[:2]
            thumb_h = 50
            thumb_w = int(w * thumb_h / h)
            if thumb_w > 85:
                thumb_w = 85
                thumb_h = int(h * thumb_w / w)

            thumb = cv2.resize(logo, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)

            # Convert to QPixmap
            bytes_per_line = 3 * thumb_w
            qimg = QImage(thumb.data, thumb_w, thumb_h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.setIcon(QIcon(pixmap))
            self.setIconSize(QSize(thumb_w, thumb_h))

        except:
            pass


class ClickableFrameLabel(QLabel):
    """Clickable video thumbnail"""
    clicked = pyqtSignal(str)

    def __init__(self, video_path="", parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self._pixmap = None
        self.setFixedSize(150, 85)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #2a2a4a;
                border-radius: 6px;
                background-color: #0d0d1a;
            }
            QLabel:hover {
                border: 2px solid #4CAF50;
                background-color: #1a2a1a;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)

    def setThumbnail(self, pixmap):
        if pixmap:
            self._pixmap = pixmap
            scaled = pixmap.scaled(
                self.width() - 4, self.height() - 4,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            super().setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.video_path)


class VideoEditorDialog(QDialog):
    """NEW Smart Video Editor - Simple & Easy"""

    def __init__(self, clips_folder=None, channel_name=None, parent=None):
        super().__init__(parent)
        self.clips_folder = clips_folder
        self.channel_name = channel_name
        self.video_files = []
        self.accepted_config = None

        title = "Smart Video Editor"
        if channel_name:
            title += f" - {channel_name}"
        self.setWindowTitle(title)

        # Fixed size - large for better preview
        self.setFixedSize(1500, 850)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.setup_style()
        self.create_ui()
        self.load_saved_config()

        if clips_folder:
            self.folder_edit.setText(str(clips_folder))
            self.scan_for_clips()
            # Play notification sound (delayed to ensure window is shown)
            QTimer.singleShot(500, self.play_notification)

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

    def setup_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #0d0d1a; }
            QLabel { color: #e0e0e0; }
            QGroupBox {
                color: #4CAF50;
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #2a2a4a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
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
                padding: 12px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #4a4a8a; }
            QPushButton:pressed { background-color: #2a2a5a; }
            QPushButton:disabled {
                background-color: #2a2a3a;
                color: #666;
            }
            QLineEdit {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 2px solid #3a3a6a;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QSlider::groove:horizontal {
                height: 10px;
                background: #2a2a4a;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 22px;
                height: 22px;
                margin: -6px 0;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover { background: #66BB6A; }
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #1a1a2e;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a6a;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #4a4a8a; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QListWidget {
                background-color: #1a1a2e;
                border: 2px solid #3a3a6a;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                color: #e0e0e0;
                padding: 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #2a2a4a;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)

    def create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QLabel("VIDEO EDITOR" + (f" - {self.channel_name}" if self.channel_name else ""))
        header.setStyleSheet("""
            font-size: 16px; font-weight: bold; color: #4CAF50;
            background-color: #1a2a1a; padding: 10px;
            border-radius: 6px; border: 1px solid #2a4a2a;
        """)
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # Folder row
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(8)

        folder_label = QLabel("Folder:")
        folder_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        folder_layout.addWidget(folder_label)

        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select folder with video clips...")
        folder_layout.addWidget(self.folder_edit, stretch=1)

        btn_browse = QPushButton("Browse")
        btn_browse.setMaximumWidth(90)
        btn_browse.clicked.connect(self.browse_folder)
        folder_layout.addWidget(btn_browse)

        btn_scan = QPushButton("Scan")
        btn_scan.setMaximumWidth(80)
        btn_scan.setStyleSheet("background-color: #2196F3;")
        btn_scan.clicked.connect(self.scan_for_clips)
        folder_layout.addWidget(btn_scan)

        main_layout.addLayout(folder_layout)

        # Main content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # === LEFT: Clips ===
        clips_group = QGroupBox("Clips")
        clips_group.setFixedWidth(170)
        clips_layout = QVBoxLayout(clips_group)
        clips_layout.setSpacing(6)
        clips_layout.setContentsMargins(8, 18, 8, 8)

        self.clips_scroll = QScrollArea()
        self.clips_scroll.setWidgetResizable(True)
        self.clips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.clips_container = QWidget()
        self.clips_grid = QVBoxLayout(self.clips_container)
        self.clips_grid.setSpacing(8)
        self.clips_grid.setContentsMargins(2, 2, 2, 2)
        self.clips_scroll.setWidget(self.clips_container)

        clips_layout.addWidget(self.clips_scroll)

        self.clips_count_label = QLabel("No clips")
        self.clips_count_label.setStyleSheet("color: #888; font-size: 11px;")
        self.clips_count_label.setAlignment(Qt.AlignCenter)
        clips_layout.addWidget(self.clips_count_label)

        content_layout.addWidget(clips_group)

        # === CENTER: Preview ===
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(10, 20, 10, 10)

        self.preview = SmartCropPreview()
        self.preview.settings_changed.connect(self.on_settings_changed)
        preview_layout.addWidget(self.preview, stretch=1)

        # Frame Scrubber - better design
        scrubber_layout = QHBoxLayout()
        scrubber_layout.setSpacing(12)

        scrub_label = QLabel("Frame:")
        scrub_label.setStyleSheet("color: #FFF; font-size: 12px; font-weight: bold;")
        scrubber_layout.addWidget(scrub_label)

        self.scrubber = QSlider(Qt.Horizontal)
        self.scrubber.setRange(0, 100)
        self.scrubber.setValue(50)
        self.scrubber.setMinimumHeight(25)
        self.scrubber.valueChanged.connect(self.on_scrubber_changed)
        scrubber_layout.addWidget(self.scrubber, stretch=1)

        self.frame_label = QLabel("50%")
        self.frame_label.setMinimumWidth(120)
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px; background-color: #1a1a2e; border-radius: 4px; padding: 4px;")
        scrubber_layout.addWidget(self.frame_label)

        preview_layout.addLayout(scrubber_layout)

        content_layout.addWidget(preview_group, stretch=1)

        # === RIGHT: Controls - SIMPLE DESIGN ===
        controls_group = QGroupBox()
        controls_group.setFixedWidth(260)
        controls_group.setStyleSheet("QGroupBox { border: none; }")
        controls_main_layout = QVBoxLayout(controls_group)
        controls_main_layout.setSpacing(6)
        controls_main_layout.setContentsMargins(8, 8, 8, 8)

        # === ZOOM SECTION ===
        zoom_box = QGroupBox("Zoom")
        zoom_box.setStyleSheet("QGroupBox { font-size: 12px; font-weight: bold; color: #4CAF50; border: 1px solid #3a3a5a; border-radius: 4px; margin-top: 8px; padding-top: 8px; }")
        zoom_layout = QVBoxLayout(zoom_box)
        zoom_layout.setSpacing(4)
        zoom_layout.setContentsMargins(8, 12, 8, 8)

        self.zoom_label = QLabel("1.0x")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 16px;")
        zoom_layout.addWidget(self.zoom_label)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(100, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedHeight(20)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)

        controls_main_layout.addWidget(zoom_box)

        # === LOGO SECTION ===
        logo_box = QGroupBox("Logo")
        logo_box.setStyleSheet("QGroupBox { font-size: 12px; font-weight: bold; color: #FF9800; border: 1px solid #3a3a5a; border-radius: 4px; margin-top: 8px; padding-top: 8px; }")
        logo_layout = QVBoxLayout(logo_box)
        logo_layout.setSpacing(6)
        logo_layout.setContentsMargins(8, 12, 8, 8)

        # Enable logo - BIG TOGGLE at top
        self.logo_checkbox = QCheckBox("Enable Logo")
        self.logo_checkbox.setStyleSheet("""
            QCheckBox { font-size: 12px; font-weight: bold; color: #FFF; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border: 2px solid #4CAF50; border-radius: 3px; }
            QCheckBox::indicator:unchecked { background-color: #333; border: 2px solid #555; border-radius: 3px; }
        """)
        self.logo_checkbox.stateChanged.connect(self.on_logo_toggle)
        logo_layout.addWidget(self.logo_checkbox)

        # Logo gallery - compact
        self.logo_scroll = QScrollArea()
        self.logo_scroll.setWidgetResizable(True)
        self.logo_scroll.setFixedHeight(90)
        self.logo_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.logo_scroll.setStyleSheet("QScrollArea { background-color: #0a0a0a; border: 1px solid #3a3a5a; border-radius: 4px; }")

        self.logo_gallery_widget = QWidget()
        self.logo_gallery_widget.setStyleSheet("background-color: transparent;")
        self.logo_gallery_grid = QGridLayout(self.logo_gallery_widget)
        self.logo_gallery_grid.setSpacing(4)
        self.logo_gallery_grid.setContentsMargins(4, 4, 4, 4)

        self.logo_scroll.setWidget(self.logo_gallery_widget)
        logo_layout.addWidget(self.logo_scroll)

        self.refresh_logo_gallery()

        # Browse button
        btn_browse_new = QPushButton("+ Add Logo")
        btn_browse_new.setMinimumHeight(30)
        btn_browse_new.setMinimumWidth(200)
        btn_browse_new.setStyleSheet("QPushButton { background-color: #3a3a5a; color: #FFF; font-size: 12px; font-weight: bold; border-radius: 4px; padding: 6px; } QPushButton:hover { background-color: #4a4a6a; }")
        btn_browse_new.clicked.connect(self.browse_logo)
        logo_layout.addWidget(btn_browse_new)

        # Size slider
        size_row = QHBoxLayout()
        size_row.setSpacing(8)
        size_lbl = QLabel("Size")
        size_lbl.setFixedWidth(55)
        size_lbl.setStyleSheet("color: #FFF; font-size: 11px;")
        size_row.addWidget(size_lbl)
        self.logo_size_slider = QSlider(Qt.Horizontal)
        self.logo_size_slider.setRange(5, 30)
        self.logo_size_slider.setValue(12)
        self.logo_size_slider.setFixedHeight(20)
        self.logo_size_slider.setEnabled(False)
        self.logo_size_slider.valueChanged.connect(self.on_logo_size_changed)
        size_row.addWidget(self.logo_size_slider, stretch=1)
        self.logo_size_label = QLabel("12%")
        self.logo_size_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        self.logo_size_label.setFixedWidth(45)
        self.logo_size_label.setAlignment(Qt.AlignRight)
        size_row.addWidget(self.logo_size_label)
        logo_layout.addLayout(size_row)

        # Opacity slider
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(8)
        opacity_lbl = QLabel("Opacity")
        opacity_lbl.setFixedWidth(55)
        opacity_lbl.setStyleSheet("color: #FFF; font-size: 11px;")
        opacity_row.addWidget(opacity_lbl)
        self.logo_opacity_slider = QSlider(Qt.Horizontal)
        self.logo_opacity_slider.setRange(30, 100)
        self.logo_opacity_slider.setValue(90)
        self.logo_opacity_slider.setFixedHeight(20)
        self.logo_opacity_slider.setEnabled(False)
        self.logo_opacity_slider.valueChanged.connect(self.on_logo_opacity_changed)
        opacity_row.addWidget(self.logo_opacity_slider, stretch=1)
        self.logo_opacity_label = QLabel("90%")
        self.logo_opacity_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        self.logo_opacity_label.setFixedWidth(45)
        self.logo_opacity_label.setAlignment(Qt.AlignRight)
        opacity_row.addWidget(self.logo_opacity_label)
        logo_layout.addLayout(opacity_row)

        # Logo path - small
        self.logo_edit = QLineEdit()
        self.logo_edit.setPlaceholderText("No logo")
        self.logo_edit.setEnabled(False)
        self.logo_edit.setFixedHeight(20)
        self.logo_edit.setStyleSheet("font-size: 9px; padding: 2px; background-color: #1a1a2e;")
        logo_layout.addWidget(self.logo_edit)

        controls_main_layout.addWidget(logo_box)

        controls_main_layout.addStretch()

        # === ACTION BUTTONS - Side by side ===
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        btn_apply_all = QPushButton("ALL")
        btn_apply_all.setMinimumHeight(30)
        btn_apply_all.setStyleSheet("QPushButton { background-color: #FF9800; color: #000; font-size: 12px; font-weight: bold; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #FFB040; }")
        btn_apply_all.clicked.connect(self.apply_to_all_videos)
        btn_row.addWidget(btn_apply_all)

        btn_apply = QPushButton("Apply")
        btn_apply.setMinimumHeight(30)
        btn_apply.setStyleSheet("QPushButton { background-color: #4CAF50; color: #FFF; font-size: 12px; font-weight: bold; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #66BB6A; }")
        btn_apply.clicked.connect(self.apply_settings)
        btn_row.addWidget(btn_apply)

        btn_skip = QPushButton("Skip")
        btn_skip.setMinimumHeight(30)
        btn_skip.setStyleSheet("QPushButton { background-color: #444; color: #CCC; font-size: 12px; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #555; color: #FFF; }")
        btn_skip.clicked.connect(self.skip_settings)
        btn_row.addWidget(btn_skip)

        controls_main_layout.addLayout(btn_row)

        content_layout.addWidget(controls_group)

        main_layout.addLayout(content_layout, stretch=1)

    def refresh_logo_gallery(self):
        """Refresh logo gallery with thumbnail grid"""
        # Clear existing
        while self.logo_gallery_grid.count():
            item = self.logo_gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        history = load_logo_history()

        if not CV2_AVAILABLE:
            return

        row = 0
        col = 0
        max_cols = 2  # 2 logos per row

        for item in history[:10]:  # Show last 10 logos
            path = item.get('path', '')
            if not Path(path).exists():
                continue

            name = item.get('name', Path(path).name)
            count = item.get('count', 0)

            # Create thumbnail button
            thumb = LogoThumbnail(path, name, count)
            thumb.clicked_path.connect(self.on_logo_gallery_clicked)

            self.logo_gallery_grid.addWidget(thumb, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Add stretch at bottom
        self.logo_gallery_grid.setRowStretch(row + 1, 1)

    def on_logo_gallery_clicked(self, logo_path):
        """Load logo from gallery"""
        if logo_path and Path(logo_path).exists():
            self.logo_edit.setText(logo_path)
            if self.preview.load_logo(logo_path):
                self.preview.update_preview()
                self.refresh_logo_gallery()  # Update counts

    def set_crop_preset(self, zoom, pan_x, pan_y):
        """Apply crop preset with zoom and pan"""
        self.preview.zoom_level = zoom
        self.preview.pan_x = pan_x
        self.preview.pan_y = pan_y
        self.preview._clamp_pan()
        self.preview.update_preview()
        self.zoom_slider.setValue(int(zoom * 100))
        self.preview.settings_changed.emit()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_edit.setText(folder)
            self.scan_for_clips()

    def browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "",
            "Images (*.png *.jpg *.jpeg);;PNG Files (*.png)"
        )
        if path:
            self.logo_edit.setText(path)
            if self.preview.load_logo(path):
                self.preview.update_preview()
                self.refresh_logo_gallery()

    def scan_for_clips(self):
        while self.clips_grid.count():
            item = self.clips_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.video_files = []
        folder = self.folder_edit.text()

        if not folder or not Path(folder).exists():
            self.clips_count_label.setText("Invalid folder")
            return

        patterns = ["**/*.mp4", "*.mp4"]
        found = set()

        for pattern in patterns:
            for f in Path(folder).glob(pattern):
                if f not in found:
                    found.add(f)
                    self.video_files.append(f)

        self.video_files.sort(key=lambda x: x.name)

        for video_path in self.video_files[:20]:
            thumb = self.create_thumbnail(video_path)
            if thumb:
                self.clips_grid.addWidget(thumb)

        self.clips_grid.addStretch()
        count = len(self.video_files)
        self.clips_count_label.setText(f"{count} clip{'s' if count != 1 else ''}")

        if self.video_files:
            self.preview.load_video_frame(self.video_files[0])

    def create_thumbnail(self, video_path):
        if not CV2_AVAILABLE:
            return None

        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return None

            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            qimg = QImage(frame.data, w, h, 3 * w, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            label = ClickableFrameLabel(str(video_path))
            label.setThumbnail(pixmap)
            label.setToolTip(video_path.name)
            label.clicked.connect(self.on_clip_clicked)

            return label
        except:
            return None

    def on_clip_clicked(self, video_path):
        self.preview.load_video_frame(video_path)

    def on_scrubber_changed(self, value):
        if self.preview.total_frames > 0:
            frame_pos = int(value / 100.0 * self.preview.total_frames)
            self.frame_label.setText(f"{frame_pos} / {self.preview.total_frames}")
            self.preview.seek_frame(frame_pos)
        else:
            self.frame_label.setText(f"{value}%")

    def on_zoom_changed(self, value):
        zoom = value / 100.0
        self.zoom_label.setText(f"{zoom:.1f}x")
        self.preview.set_zoom(zoom)

    def set_quick_zoom(self, zoom_level):
        """Set zoom to preset"""
        self.preview.set_zoom(zoom_level)
        self.zoom_slider.setValue(int(zoom_level * 100))

    def on_settings_changed(self):
        zoom = self.preview.zoom_level
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(int(zoom * 100))
        self.zoom_slider.blockSignals(False)

        # Update description
        if zoom <= 1.0:
            desc = "Full Frame"
        elif zoom <= 1.3:
            desc = "Wide"
        elif zoom <= 1.7:
            desc = "Close"
        elif zoom <= 2.5:
            desc = "Tight"
        else:
            desc = "Max Zoom"

        self.zoom_label.setText(f"{zoom:.1f}x - {desc}")

    def on_logo_toggle(self, state):
        enabled = state == Qt.Checked
        self.preview.logo_enabled = enabled
        self.logo_size_slider.setEnabled(enabled)
        self.logo_opacity_slider.setEnabled(enabled)
        self.preview.update_preview()

    def on_logo_size_changed(self, value):
        self.logo_size_label.setText(f"{value}%")
        self.preview.logo_size_percent = value
        self.preview.update_preview()

    def on_logo_opacity_changed(self, value):
        self.logo_opacity_label.setText(f"{value}%")
        self.preview.logo_opacity = value
        self.preview.update_preview()

    def set_logo_position(self, x, y):
        """Set logo position"""
        self.preview.logo_x = x
        self.preview.logo_y = y
        self.preview.update_preview()

    def load_saved_config(self):
        config_file = get_user_data_dir() / "video_editor_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Load logo path
                if config.get('logo_path') and Path(config['logo_path']).exists():
                    self.logo_edit.setText(config['logo_path'])
                    self.preview.load_logo(config['logo_path'])

                # Load size and opacity settings
                if config.get('logo_size'):
                    size = config['logo_size']
                    self.logo_size_slider.setValue(size)
                    self.preview.logo_size_percent = size
                    self.logo_size_label.setText(f"{size}%")

                if config.get('logo_opacity'):
                    opacity = config['logo_opacity']
                    self.logo_opacity_slider.setValue(opacity)
                    self.preview.logo_opacity = opacity
                    self.logo_opacity_label.setText(f"{opacity}%")

            except:
                pass

    def save_config(self):
        config = {
            'zoom_level': self.preview.zoom_level,
            'pan_x': self.preview.pan_x,
            'pan_y': self.preview.pan_y,
            'logo_enabled': self.preview.logo_enabled,
            'logo_path': self.preview.logo_path,
            'logo_x': self.preview.logo_x,
            'logo_y': self.preview.logo_y,
            'logo_size': self.preview.logo_size_percent,
            'logo_opacity': self.preview.logo_opacity,
        }

        config_file = get_user_data_dir() / "video_editor_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

    def apply_to_all_videos(self):
        """Apply to all videos"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Apply to ALL?")
        msg.setText("Apply current settings to ALL videos?")
        msg.setInformativeText("This will skip the editor for remaining videos.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() != QMessageBox.Yes:
            return

        self.save_config()

        crop_x, crop_y, crop_w, crop_h = self.preview.get_crop_pixels()
        has_crop = self.preview.zoom_level > 1.01

        self.accepted_config = {
            'has_crop': has_crop,
            'crop_x': crop_x,
            'crop_y': crop_y,
            'crop_w': crop_w,
            'crop_h': crop_h,
            'logo_enabled': self.preview.logo_enabled,
            'logo_path': self.preview.logo_path if self.preview.logo_enabled else None,
            'logo_x': self.preview.logo_x,
            'logo_y': self.preview.logo_y,
            'logo_size_percent': self.preview.logo_size_percent,
            'logo_opacity': self.preview.logo_opacity,
            'apply_to_all': True
        }

        self.accept()

    def apply_settings(self):
        self.save_config()

        crop_x, crop_y, crop_w, crop_h = self.preview.get_crop_pixels()
        has_crop = self.preview.zoom_level > 1.01

        self.accepted_config = {
            'has_crop': has_crop,
            'crop_x': crop_x,
            'crop_y': crop_y,
            'crop_w': crop_w,
            'crop_h': crop_h,
            'logo_enabled': self.preview.logo_enabled,
            'logo_path': self.preview.logo_path if self.preview.logo_enabled else None,
            'logo_x': self.preview.logo_x,
            'logo_y': self.preview.logo_y,
            'logo_size_percent': self.preview.logo_size_percent,
            'logo_opacity': self.preview.logo_opacity,
        }

        self.accept()

    def skip_settings(self):
        self.accepted_config = None
        self.reject()

    def get_config(self):
        return self.accepted_config


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = VideoEditorDialog(channel_name="Test Channel")
    if dialog.exec_() == QDialog.Accepted:
        print("Config:", dialog.get_config())
    else:
        print("Skipped")
    sys.exit()
