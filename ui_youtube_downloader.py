"""
YouTube Downloader Tool for Nabil Video Studio Pro
Modern clean design - matching Script to Voice style
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QProgressBar, QFileDialog,
    QFrame, QMessageBox, QWidget, QTextEdit, QApplication,
    QButtonGroup, QScrollArea, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette


def get_script_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


def find_yt_dlp():
    """Find yt-dlp - prefer standalone exe over Python script."""
    script_dir = get_script_dir()
    # Prefer standalone exe in app root (doesn't need Python)
    standalone = script_dir / 'yt-dlp.exe'
    if standalone.exists():
        return str(standalone)
    # Fall back to Python Scripts version
    scripts_version = script_dir / 'python' / 'Scripts' / 'yt-dlp.exe'
    if scripts_version.exists():
        return str(scripts_version)
    # Try system PATH
    try:
        result = subprocess.run(['where', 'yt-dlp'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    return None


def find_yt_dlp_standalone():
    """Find standalone yt-dlp.exe (not Python script version)."""
    script_dir = get_script_dir()
    standalone = script_dir / 'yt-dlp.exe'
    if standalone.exists():
        return str(standalone)
    return None


def find_ffmpeg():
    script_dir = get_script_dir()
    locations = [
        script_dir / 'ffmpeg.exe',
        script_dir / 'ffmpeg' / 'ffmpeg.exe',
        script_dir / 'ffmpeg' / 'bin' / 'ffmpeg.exe',
        script_dir / 'assets' / 'bin' / 'ffmpeg.exe',
    ]
    for loc in locations:
        if loc.exists():
            return str(loc.parent)
    return None


def find_node():
    """Find bundled Node.js for yt-dlp JS challenge solving."""
    script_dir = get_script_dir()
    node_path = script_dir / 'node' / 'node.exe'
    if node_path.exists():
        return str(node_path.parent)
    return None


def find_node_exe():
    """Find bundled Node.js executable path for yt-dlp --js-runtimes."""
    script_dir = get_script_dir()
    node_exe = script_dir / 'node' / 'node.exe'
    if node_exe.exists():
        return str(node_exe)
    return None


class DownloadWorker(QThread):
    progress = pyqtSignal(str)
    percent = pyqtSignal(int)
    video_progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, urls, output_dirs, quality, audio_only, subtitles, playlist, thumbnail=False):
        super().__init__()
        self.urls = urls
        self.output_dirs = output_dirs
        self.quality = quality
        self.audio_only = audio_only
        self.subtitles = subtitles
        self.playlist = playlist
        self.thumbnail = thumbnail
        self._cancelled = False
        self.process = None

    def cancel(self):
        self._cancelled = True
        if self.process:
            try:
                self.process.terminate()
            except:
                pass

    def run(self):
        total_videos = len(self.urls)
        successful = 0
        failed = 0

        for idx, (url, output_dir) in enumerate(zip(self.urls, self.output_dirs)):
            if self._cancelled:
                break

            video_num = idx + 1
            self.video_progress.emit(video_num, total_videos)
            self.progress.emit(f"\n{'='*50}")
            self.progress.emit(f"Video {video_num}/{total_videos}: Starting...")
            self.progress.emit(f"Folder: {Path(output_dir).name}")
            self.percent.emit(0)

            try:
                yt_dlp_path = find_yt_dlp()
                if yt_dlp_path:
                    cmd = [yt_dlp_path]
                else:
                    python_exe = sys.executable
                    if 'pythonw' in python_exe.lower():
                        python_exe = python_exe.replace('pythonw', 'python')
                    cmd = [python_exe, '-m', 'yt_dlp']

                folder_name = Path(output_dir).name

                # Use different naming for playlist vs single video
                if self.playlist:
                    # For playlists: use video title
                    output_template = os.path.join(output_dir, '%(title).100s.%(ext)s')
                else:
                    # For single video: use folder name
                    output_template = os.path.join(output_dir, f'{folder_name}.%(ext)s')
                cmd.extend(['-o', output_template])

                if self.thumbnail:
                    thumb_template = os.path.join(output_dir, '%(title)s.%(ext)s')
                    cmd.extend(['-o', f'thumbnail:{thumb_template}'])

                if self.audio_only:
                    # Download audio - use format 18 audio track or best available
                    cmd.extend(['-f', 'ba/b'])
                    cmd.extend(['-x'])  # Extract audio only
                else:
                    # Due to YouTube restrictions (Jan 2025), only format 18 (360p) is reliably available
                    # without authentication. Use fallback chain to get best available.
                    quality_map = {
                        'Best': 'bv*+ba/b/18/best',
                        '1080p': 'bv*[height<=1080]+ba/b[height<=1080]/18/best',
                        '720p': 'bv*[height<=720]+ba/b[height<=720]/18/best',
                        '480p': 'bv*[height<=480]+ba/b[height<=480]/18/best',
                    }
                    format_str = quality_map.get(self.quality, 'bv*+ba/b/18/best')
                    cmd.extend(['-f', format_str])
                    cmd.extend(['--merge-output-format', 'mp4'])

                # Sanitize filenames for Windows
                cmd.append('--windows-filenames')

                if self.subtitles:
                    cmd.extend(['--write-subs', '--write-auto-subs', '--sub-lang', 'en'])
                if self.thumbnail:
                    cmd.extend(['--write-thumbnail', '--convert-thumbnails', 'jpg'])
                if not self.playlist:
                    cmd.append('--no-playlist')

                ffmpeg_path = find_ffmpeg()
                if ffmpeg_path:
                    cmd.extend(['--ffmpeg-location', ffmpeg_path])

                # yt-dlp 2026.02+ uses JS challenge solving for YouTube bot detection
                # --js-runtimes points to bundled Node.js, --remote-components fetches solver from GitHub
                # NOTE: Do NOT use web_embedded player client — causes error 152 on yt-dlp 2026.02+
                node_exe = find_node_exe()
                js_runtime_arg = f'node:{node_exe}' if node_exe else 'node'

                cmd.extend([
                    '--js-runtimes', js_runtime_arg,
                    '--remote-components', 'ejs:github',
                    '--no-check-certificates',
                    '--retries', '15',
                    '--fragment-retries', '15',
                    '--file-access-retries', '5',
                    '--concurrent-fragments', '8',
                    '--buffer-size', '1M',
                    '--socket-timeout', '30',
                    '--throttled-rate', '100K',
                ])

                # For playlists: download 10 videos at once (parallel)
                if self.playlist:
                    cmd.extend(['-N', '10'])  # 10 parallel downloads

                cmd.extend(['--newline', '--progress'])
                cmd.append(url)

                # Add bundled Node.js to PATH for yt-dlp JS challenge solving
                env = os.environ.copy()
                node_path = find_node()
                if node_path:
                    env['PATH'] = node_path + os.pathsep + env.get('PATH', '')
                    self.progress.emit(f"[info] Using bundled Node.js: {node_path}")
                else:
                    self.progress.emit("[warning] Node.js not found - JS challenges may fail")

                # Debug: show yt-dlp path
                self.progress.emit(f"[info] yt-dlp: {yt_dlp_path}")

                # Test yt-dlp version first
                try:
                    test_result = subprocess.run(
                        [yt_dlp_path, '--version'],
                        capture_output=True, text=True, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                        env=env
                    )
                    if test_result.returncode == 0:
                        self.progress.emit(f"[info] yt-dlp version: {test_result.stdout.strip()}")
                    else:
                        self.progress.emit(f"[error] yt-dlp failed (code {test_result.returncode})")
                        self.progress.emit(f"[error] stdout: {test_result.stdout.strip()}")
                        self.progress.emit(f"[error] stderr: {test_result.stderr.strip()}")
                        # Try standalone yt-dlp.exe instead
                        standalone = find_yt_dlp_standalone()
                        if standalone:
                            self.progress.emit(f"[info] Trying standalone: {standalone}")
                            yt_dlp_path = standalone
                            cmd[0] = standalone
                except Exception as e:
                    self.progress.emit(f"[error] yt-dlp test error: {str(e)}")

                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    if self._cancelled:
                        break

                    if attempt > 1:
                        wait_sec = attempt * 3
                        self.progress.emit(f"[retry] Attempt {attempt}/{max_attempts} in {wait_sec}s...")
                        self.percent.emit(0)
                        import time
                        time.sleep(wait_sec)

                    try:
                        self.process = subprocess.Popen(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace',
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                            env=env
                        )
                    except Exception as e:
                        self.progress.emit(f"[error] Failed to start yt-dlp: {str(e)}")
                        if attempt == max_attempts:
                            failed += 1
                        continue

                    for line in self.process.stdout:
                        if self._cancelled:
                            break
                        line = line.strip()
                        if line:
                            self.progress.emit(line)
                            if '[download]' in line and '%' in line:
                                match = re.search(r'(\d+\.?\d*)%', line)
                                if match:
                                    self.percent.emit(int(float(match.group(1))))

                    return_code = self.process.wait()
                    if self._cancelled:
                        self.progress.emit(f"Video {video_num}: Cancelled")
                        break
                    elif return_code == 0:
                        self.progress.emit(f"✓ Video {video_num}: Done!")
                        successful += 1
                        break
                    else:
                        if attempt < max_attempts:
                            self.progress.emit(f"✗ Video {video_num}: Failed (attempt {attempt}/{max_attempts})")
                        else:
                            self.progress.emit(f"✗ Video {video_num}: Failed after {max_attempts} attempts")
                            failed += 1

            except Exception as e:
                self.progress.emit(f"✗ Video {video_num}: Error - {str(e)}")
                failed += 1

        if self._cancelled:
            self.finished.emit(False, "Cancelled")
        elif failed == 0:
            self.finished.emit(True, f"All {successful} videos downloaded!")
        elif successful > 0:
            self.finished.emit(True, f"{successful} done, {failed} failed")
        else:
            self.finished.emit(False, f"All {failed} failed")


class YouTubeDownloaderPage(QWidget):
    """YouTube Downloader - Modern clean style"""

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.worker = None
        self.category_buttons = {}
        self.selected_category = None
        self.settings_file = self._get_settings_file()
        self.setup_ui()
        self.check_yt_dlp()
        self._refresh_category_buttons()
        self._load_settings()  # Load saved preferences

    def _get_settings_file(self) -> Path:
        """Get path to settings file in AppData"""
        if os.name == 'nt':
            appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
            settings_dir = Path(appdata) / "NabilVideoStudioPro"
        else:
            settings_dir = Path.home() / ".nvspro"
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir / "ytdl_settings.json"

    def _load_settings(self):
        """Load saved settings"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)

                # Apply saved settings
                self.cb_subs.setChecked(settings.get('subtitles', False))
                self.cb_thumbnail.setChecked(settings.get('thumbnail', False))
                self.cb_playlist.setChecked(settings.get('playlist', False))

                # Quality combo
                quality = settings.get('quality', '1080p')
                idx = self.quality_combo.findText(quality)
                if idx >= 0:
                    self.quality_combo.setCurrentIndex(idx)

                # Format combo
                format_val = settings.get('format', 'Video')
                idx = self.format_combo.findText(format_val)
                if idx >= 0:
                    self.format_combo.setCurrentIndex(idx)

                # Output path
                output = settings.get('output_path', '')
                if output and Path(output).parent.exists():
                    self.output_path.setText(output)
        except Exception as e:
            print(f"Load settings error: {e}")

    def _save_settings(self):
        """Save current settings"""
        try:
            settings = {
                'subtitles': self.cb_subs.isChecked(),
                'thumbnail': self.cb_thumbnail.isChecked(),
                'playlist': self.cb_playlist.isChecked(),
                'quality': self.quality_combo.currentText(),
                'format': self.format_combo.currentText(),
                'output_path': self.output_path.text()
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Save settings error: {e}")

    def setup_ui(self):
        # Force background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#1a1a1a"))
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ============ HEADER ============
        header = QHBoxLayout()

        title = QLabel("YouTube Downloader")
        title.setStyleSheet("""
            color: #f0f6fc;
            font-size: 22px;
            font-weight: 700;
            padding: 4px 0;
        """)
        header.addWidget(title)

        header.addStretch()

        self.status_label = QLabel("Checking...")
        self.status_label.setStyleSheet("""
            background-color: #2a2a2a;
            color: #888888;
            padding: 6px 14px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        """)
        header.addWidget(self.status_label)

        layout.addLayout(header)

        # ============ CATEGORY BUTTONS ============
        cat_row = QHBoxLayout()
        cat_row.setSpacing(8)

        cat_label = QLabel("Category")
        cat_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 500;")
        cat_label.setFixedWidth(60)
        cat_row.addWidget(cat_label)

        self.cat_buttons_layout = QHBoxLayout()
        self.cat_buttons_layout.setSpacing(6)
        cat_row.addLayout(self.cat_buttons_layout)
        cat_row.addStretch()

        layout.addLayout(cat_row)

        # ============ MODE TOGGLE (Recreate / Create) ============
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        mode_label = QLabel("Mode")
        mode_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 500;")
        mode_label.setFixedWidth(60)
        mode_row.addWidget(mode_label)

        self.recreate_btn = QPushButton("  Recreate Video  ")
        self.recreate_btn.setCheckable(True)
        self.recreate_btn.setChecked(True)
        self.recreate_btn.setFixedHeight(34)
        self.recreate_btn.setMinimumWidth(130)
        self.recreate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D35400, stop:1 #E67E22);
                border: none;
                border-radius: 6px;
                color: white;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:!checked {
                background: #2a2a2a;
                color: #888888;
                border: none;
            }
            QPushButton:hover:!checked {
                background: #3a3a3a;
                border-color: #D35400;
            }
        """)
        self.recreate_btn.clicked.connect(lambda: self._set_mode(True))
        mode_row.addWidget(self.recreate_btn)

        self.create_btn = QPushButton("  Create Video  ")
        self.create_btn.setCheckable(True)
        self.create_btn.setFixedHeight(34)
        self.create_btn.setMinimumWidth(120)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8957e5, stop:1 #a371f7);
                border: none;
                border-radius: 6px;
                color: white;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:!checked {
                background: #2a2a2a;
                color: #888888;
                border: none;
            }
            QPushButton:hover:!checked {
                background: #3a3a3a;
                border-color: #8957e5;
            }
        """)
        self.create_btn.clicked.connect(lambda: self._set_mode(False))
        mode_row.addWidget(self.create_btn)

        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ============ URL INPUTS ============
        url_header = QHBoxLayout()
        url_label = QLabel("YouTube URLs")
        url_label.setStyleSheet("color: #E67E22; font-size: 12px; font-weight: 600;")
        url_header.addWidget(url_label)
        url_header.addStretch()

        # Add URL button
        self.add_url_btn = QPushButton("  + Add URL  ")
        self.add_url_btn.setFixedHeight(28)
        self.add_url_btn.setStyleSheet("""
            QPushButton {
                background-color: #D35400;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 12px;
            }
            QPushButton:hover { background-color: #E67E22; }
        """)
        self.add_url_btn.clicked.connect(self._add_url_row)
        url_header.addWidget(self.add_url_btn)

        layout.addLayout(url_header)

        # Scroll area for URL rows (only scrolls after 6 URLs)
        self.url_scroll = QScrollArea()
        self.url_scroll.setWidgetResizable(True)
        self.url_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.url_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.url_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: #E67E22;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #E67E22;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        # Container for URL rows
        self.url_container = QWidget()
        self.url_layout = QVBoxLayout(self.url_container)
        self.url_layout.setContentsMargins(0, 0, 4, 0)
        self.url_layout.setSpacing(8)

        self.url_inputs = []
        self.url_rows = []
        self.max_urls = 10
        self.scroll_after = 6  # Start scrolling after this many URLs
        self.row_height = 48  # Height per URL row

        # Start with 3 URL inputs
        for _ in range(3):
            self._add_url_row()

        self.url_scroll.setWidget(self.url_container)
        self._update_scroll_height()
        layout.addWidget(self.url_scroll)

        # ============ SETTINGS ROW ============
        settings_row = QHBoxLayout()
        settings_row.setSpacing(16)

        # Output Folder
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(4)
        output_label = QLabel("Output Folder")
        output_label.setStyleSheet("color: #27AE60; font-size: 11px; font-weight: 600;")
        output_layout.addWidget(output_label)

        output_row = QHBoxLayout()
        output_row.setSpacing(6)
        self.output_path = QLineEdit()
        self.output_path.setFixedHeight(38)
        self.output_path.setText(str(Path.home() / "Videos" / "YouTube"))
        self.output_path.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                color: #e6edf3;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #E67E22; }
        """)
        output_row.addWidget(self.output_path)

        browse_btn = QPushButton("...")
        browse_btn.setFixedSize(38, 38)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #27AE60;
                border-radius: 8px;
                color: #27AE60;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #D35400;
                color: white;
            }
        """)
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(browse_btn)
        output_layout.addLayout(output_row)
        settings_row.addWidget(output_widget, 1)

        # Quality
        quality_widget = QWidget()
        quality_layout = QVBoxLayout(quality_widget)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.setSpacing(4)
        quality_label = QLabel("Quality")
        quality_label.setStyleSheet("color: #F39C12; font-size: 11px; font-weight: 600;")
        quality_layout.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "720p", "480p", "Best"])
        self.quality_combo.setFixedHeight(38)
        self.quality_combo.setFixedWidth(100)
        self.quality_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #F39C12;
                border-radius: 8px;
                color: #F39C12;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #F39C12;
                color: #e0e0e0;
                selection-background-color: #F39C12;
            }
        """)
        quality_layout.addWidget(self.quality_combo)
        settings_row.addWidget(quality_widget)

        # Format
        format_widget = QWidget()
        format_layout = QVBoxLayout(format_widget)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(4)
        format_label = QLabel("Format")
        format_label.setStyleSheet("color: #a371f7; font-size: 11px; font-weight: 600;")
        format_layout.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Video", "Audio"])
        self.format_combo.setFixedHeight(38)
        self.format_combo.setFixedWidth(90)
        self.format_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #a371f7;
                border-radius: 8px;
                color: #a371f7;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #a371f7;
                color: #e0e0e0;
                selection-background-color: #a371f7;
            }
        """)
        format_layout.addWidget(self.format_combo)
        settings_row.addWidget(format_widget)

        # Auto-save when combos change
        self.quality_combo.currentTextChanged.connect(self._save_settings)
        self.format_combo.currentTextChanged.connect(self._save_settings)
        self.output_path.textChanged.connect(self._save_settings)

        layout.addLayout(settings_row)

        # ============ OPTIONS CHECKBOXES ============
        options_row = QHBoxLayout()
        options_row.setSpacing(24)

        self.cb_subs = QCheckBox("  Subtitles")
        self.cb_subs.setStyleSheet("""
            QCheckBox { color: #E67E22; font-size: 12px; font-weight: 500; }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border-radius: 4px;
                background-color: #2a2a2a;
                border: 2px solid #E67E22;
            }
            QCheckBox::indicator:checked {
                background-color: #D35400;
                border-color: #D35400;
            }
            QCheckBox::indicator:hover { border-color: #E67E22; }
        """)
        options_row.addWidget(self.cb_subs)

        self.cb_thumbnail = QCheckBox("  Thumbnail")
        self.cb_thumbnail.setStyleSheet("""
            QCheckBox { color: #d2a8ff; font-size: 12px; font-weight: 500; }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border-radius: 4px;
                background-color: #2a2a2a;
                border: 2px solid #d2a8ff;
            }
            QCheckBox::indicator:checked {
                background-color: #8957e5;
                border-color: #8957e5;
            }
            QCheckBox::indicator:hover { border-color: #a371f7; }
        """)
        options_row.addWidget(self.cb_thumbnail)

        self.cb_playlist = QCheckBox("  Playlist")
        self.cb_playlist.setStyleSheet("""
            QCheckBox { color: #F39C12; font-size: 12px; font-weight: 500; }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border-radius: 4px;
                background-color: #2a2a2a;
                border: 2px solid #F39C12;
            }
            QCheckBox::indicator:checked {
                background-color: #d29922;
                border-color: #d29922;
            }
            QCheckBox::indicator:hover { border-color: #e3b341; }
        """)
        options_row.addWidget(self.cb_playlist)

        # Auto-save when options change
        self.cb_subs.stateChanged.connect(self._save_settings)
        self.cb_thumbnail.stateChanged.connect(self._save_settings)
        self.cb_playlist.stateChanged.connect(self._save_settings)

        options_row.addStretch()
        layout.addLayout(options_row)

        # ============ LOG BOX ============
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Download log...")
        self.log_box.setStyleSheet("""
            QTextEdit {
                background-color: #252525;
                border: none;
                border-radius: 8px;
                color: #27AE60;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_box, 1)

        # ============ PROGRESS BAR ============
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #D35400;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # ============ BOTTOM ROW ============
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888888; font-size: 12px;")
        bottom_row.addWidget(self.progress_label)

        bottom_row.addStretch()

        # Open Folder button
        folder_btn = QPushButton("  Open Folder  ")
        folder_btn.setFixedHeight(42)
        folder_btn.setMinimumWidth(110)
        folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 2px solid #E67E22;
                border-radius: 8px;
                color: #E67E22;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #D35400;
                color: white;
                border-color: #D35400;
            }
        """)
        folder_btn.clicked.connect(self._open_folder)
        bottom_row.addWidget(folder_btn)

        # Stop button
        self.stop_btn = QPushButton("  Stop  ")
        self.stop_btn.setFixedHeight(42)
        self.stop_btn.setMinimumWidth(80)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #da3633, stop:1 #f85149);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f85149, stop:1 #ff7b72);
            }
        """)
        self.stop_btn.clicked.connect(self._cancel_download)
        self.stop_btn.setVisible(False)
        bottom_row.addWidget(self.stop_btn)

        # Download button
        self.download_btn = QPushButton("  Download  ")
        self.download_btn.setFixedHeight(42)
        self.download_btn.setMinimumWidth(130)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D35400, stop:1 #E67E22);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 700;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D35400, stop:1 #E67E22);
            }
            QPushButton:disabled {
                background: #2a2a2a;
                color: #484f58;
            }
        """)
        self.download_btn.clicked.connect(self._start_download)
        bottom_row.addWidget(self.download_btn)

        layout.addLayout(bottom_row)

    def _set_mode(self, recreate):
        """Toggle between Recreate and Create modes"""
        self.recreate_btn.setChecked(recreate)
        self.create_btn.setChecked(not recreate)
        self._refresh_category_buttons()

    def _refresh_category_buttons(self):
        """Create category buttons"""
        # Clear existing
        for i in reversed(range(self.cat_buttons_layout.count())):
            widget = self.cat_buttons_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.category_buttons.clear()

        if not self.config_manager:
            return

        categories = self.config_manager.get_categories()
        is_create = self.create_btn.isChecked()
        path_key = "cc_interviews_path" if is_create else "input_path"

        for cat_name in categories:
            cat_data = self.config_manager.get_category_data(cat_name)
            cat_path = cat_data.get(path_key, "")

            if cat_path:  # Only show if path configured
                btn = QPushButton(f"  {cat_name}  ")
                btn.setCheckable(True)
                btn.setFixedHeight(32)
                btn.setMinimumWidth(80)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2a2a2a;
                        border: 2px solid #3a3a3a;
                        border-radius: 6px;
                        color: #888888;
                        padding: 4px 14px;
                        font-size: 12px;
                        font-weight: 500;
                    }
                    QPushButton:checked {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #D35400, stop:1 #E67E22);
                        border-color: #D35400;
                        color: white;
                    }
                    QPushButton:hover:!checked {
                        border-color: #27AE60;
                        color: #27AE60;
                    }
                """)
                btn.clicked.connect(lambda c, name=cat_name: self._select_category(name))
                self.cat_buttons_layout.addWidget(btn)
                self.category_buttons[cat_name] = btn

    def _add_url_row(self):
        """Add a new URL input row (max 10)"""
        if len(self.url_inputs) >= self.max_urls:
            return  # Max reached

        row_index = len(self.url_inputs)

        row_widget = QWidget()
        url_row = QHBoxLayout(row_widget)
        url_row.setContentsMargins(0, 0, 0, 0)
        url_row.setSpacing(8)

        num = QLabel(f"{row_index + 1}")
        num.setFixedWidth(20)
        num.setStyleSheet("color: #f85149; font-weight: bold; font-size: 14px;")
        url_row.addWidget(num)

        url_input = QLineEdit()
        url_input.setPlaceholderText("https://youtube.com/watch?v=...")
        url_input.setFixedHeight(40)
        url_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: none;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 8px 14px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #E67E22; border-width: 2px; }
        """)
        url_row.addWidget(url_input)

        paste_btn = QPushButton("  Paste  ")
        paste_btn.setFixedHeight(40)
        paste_btn.setMinimumWidth(70)
        paste_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #D35400;
                border-radius: 8px;
                color: #E67E22;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #D35400;
                color: white;
            }
        """)
        paste_btn.clicked.connect(lambda c, inp=url_input: inp.setText(QApplication.clipboard().text()))
        url_row.addWidget(paste_btn)

        # Remove button (only show if more than 1 row)
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(40, 40)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #f85149;
                border-radius: 8px;
                color: #f85149;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f85149;
                color: white;
            }
        """)
        remove_btn.clicked.connect(lambda c, w=row_widget, inp=url_input: self._remove_url_row(w, inp))
        url_row.addWidget(remove_btn)

        self.url_inputs.append(url_input)
        self.url_rows.append(row_widget)
        self.url_layout.addWidget(row_widget)

        # Update button states and scroll behavior
        self._update_add_button()
        self._update_scroll_height()

    def _remove_url_row(self, row_widget, url_input):
        """Remove a URL input row"""
        if len(self.url_inputs) <= 1:
            # Don't remove the last one, just clear it
            url_input.clear()
            return

        # Remove from lists
        if url_input in self.url_inputs:
            self.url_inputs.remove(url_input)
        if row_widget in self.url_rows:
            self.url_rows.remove(row_widget)

        # Remove widget
        row_widget.deleteLater()

        # Renumber remaining rows and update scroll
        self._renumber_rows()
        self._update_add_button()
        self._update_scroll_height()

    def _renumber_rows(self):
        """Renumber the URL rows after removal"""
        for i, row_widget in enumerate(self.url_rows):
            layout = row_widget.layout()
            if layout and layout.count() > 0:
                num_label = layout.itemAt(0).widget()
                if isinstance(num_label, QLabel):
                    num_label.setText(f"{i + 1}")

    def _update_add_button(self):
        """Show/hide add button based on row count"""
        if len(self.url_inputs) >= self.max_urls:
            self.add_url_btn.setVisible(False)
        else:
            self.add_url_btn.setVisible(True)

    def _update_scroll_height(self):
        """Adjust scroll area height - no scroll for 1-6 URLs, scroll for 7+"""
        num_urls = len(self.url_inputs)
        if num_urls <= self.scroll_after:
            # Show all rows naturally, no fixed height restriction
            self.url_scroll.setMaximumHeight(16777215)  # Default Qt max
            self.url_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            # Lock height at 6 rows worth, enable scrolling with visible scrollbar
            max_height = self.scroll_after * self.row_height
            self.url_scroll.setMaximumHeight(max_height)
            self.url_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

    def _select_category(self, cat_name):
        """Select category and set output path"""
        for name, btn in self.category_buttons.items():
            btn.setChecked(name == cat_name)

        self.selected_category = cat_name

        is_create = self.create_btn.isChecked()
        path_key = "cc_interviews_path" if is_create else "input_path"

        cat_data = self.config_manager.get_category_data(cat_name)
        cat_path = cat_data.get(path_key, "")

        if cat_path:
            self.output_path.setText(cat_path)
            prefix = "OG" if is_create else "VD"
            self.log_box.append(f"Category: {cat_name} → {prefix}-X folders")

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_path.setText(folder)

    def _open_folder(self):
        folder = self.output_path.text()
        if Path(folder).exists():
            os.startfile(folder)

    def check_yt_dlp(self):
        if find_yt_dlp():
            self.status_label.setText("✓ Ready")
            self.status_label.setStyleSheet("""
                background-color: #D35400;
                color: white;
                padding: 6px 12px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
            """)
        else:
            try:
                import yt_dlp
                self.status_label.setText("✓ Ready")
                self.status_label.setStyleSheet("""
                    background-color: #D35400;
                    color: white;
                    padding: 6px 12px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 500;
                """)
            except:
                self.status_label.setText("✗ yt-dlp Missing")
                self.status_label.setStyleSheet("""
                    background-color: #da3633;
                    color: white;
                    padding: 6px 12px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 500;
                """)
                self.log_box.append("ERROR: yt-dlp not found!")

    def _get_folder_prefix(self):
        return "OG" if self.create_btn.isChecked() else "VD"

    def _get_next_folder(self, base_dir, prefix):
        """Get next available numbered folder"""
        base_path = Path(base_dir)
        existing = []
        if base_path.exists():
            for item in base_path.iterdir():
                if item.is_dir() and item.name.startswith(f"{prefix}-"):
                    try:
                        num = int(item.name.split("-")[1])
                        existing.append(num)
                    except:
                        pass
        next_num = max(existing, default=0) + 1
        return str(base_path / f"{prefix}-{next_num}")

    def _start_download(self):
        # Collect URLs
        urls = []
        for inp in self.url_inputs:
            url = inp.text().strip()
            if url:
                if 'youtube.com' in url or 'youtu.be' in url:
                    urls.append(url)
                else:
                    QMessageBox.warning(self, "Error", f"Invalid URL: {url}")
                    return

        if not urls:
            QMessageBox.warning(self, "Error", "Enter at least one YouTube URL")
            return

        base_dir = self.output_path.text().strip()
        Path(base_dir).mkdir(parents=True, exist_ok=True)

        prefix = self._get_folder_prefix()

        # Create folders for each video
        output_dirs = []
        self.log_box.clear()
        self.log_box.append(f"Downloading {len(urls)} video(s)...")

        for i, url in enumerate(urls):
            folder = self._get_next_folder(base_dir, prefix)
            Path(folder).mkdir(parents=True, exist_ok=True)
            output_dirs.append(folder)
            self.log_box.append(f"  {i+1}. → {Path(folder).name}/")

        # UI state
        self.download_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Downloading 0/{len(urls)}...")

        audio_only = self.format_combo.currentText() == "Audio"

        self.worker = DownloadWorker(
            urls=urls,
            output_dirs=output_dirs,
            quality=self.quality_combo.currentText(),
            audio_only=audio_only,
            subtitles=self.cb_subs.isChecked(),
            playlist=self.cb_playlist.isChecked(),
            thumbnail=self.cb_thumbnail.isChecked()
        )
        self.worker.progress.connect(self.log_box.append)
        self.worker.percent.connect(self.progress_bar.setValue)
        self.worker.video_progress.connect(lambda c, t: self.progress_label.setText(f"Downloading {c}/{t}..."))
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _cancel_download(self):
        if self.worker:
            self.worker.cancel()
            self.progress_label.setText("Cancelling...")

    def _on_finished(self, success, message):
        self.download_btn.setEnabled(True)
        self.stop_btn.setVisible(False)

        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText(f"✓ {message}")
            QMessageBox.information(self, "Done", message)
        else:
            self.progress_label.setText(f"✗ {message}")

        self.worker = None


# Backward compatibility
YouTubeDownloaderDialog = YouTubeDownloaderPage


if __name__ == "__main__":
    from PyQt5.QtWidgets import QMainWindow
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("YouTube Downloader Test")
    window.resize(700, 700)
    page = YouTubeDownloaderPage()
    window.setCentralWidget(page)
    window.show()
    sys.exit(app.exec_())
