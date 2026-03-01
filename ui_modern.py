"""
Nabil Video Studio Pro - MODERN UI VERSION
Professional desktop interface with modern sidebar design
"""

import sys
import os
import json
import subprocess
import shutil
import time
import traceback
import ctypes
from pathlib import Path

# Ensure bundled FFmpeg is on PATH (for fresh installs without system FFmpeg)
_app_dir = Path(__file__).parent.resolve()
_assets_bin = _app_dir / "assets" / "bin"
if _assets_bin.exists() and str(_assets_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_assets_bin) + ";" + os.environ.get("PATH", "")

# Set Windows AppUserModelID BEFORE importing PyQt5
# This is critical for taskbar pinning to work correctly
try:
    myappid = 'NabilSoftware.NVSPro.VideoStudio.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QProgressBar, QTextEdit, QFileDialog,
    QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QGroupBox, QScrollArea, QCheckBox,
    QFrame, QSizePolicy, QStackedWidget, QGraphicsDropShadowEffect, QSpacerItem,
    QDialog, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QRadioButton, QSpinBox,
    QSplashScreen
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QSize, QPoint
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtGui import QFont, QTextCursor, QColor, QPixmap, QIcon

# Enable high-DPI scaling
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# Import existing modules
from ui_config_manager import ConfigManager
from ui_voice_manager import VoiceManagerDialog
from ui_profile_wizard import ProfileWizard
from ui_settings_editor import SettingsEditor
from ui_api_manager import APIKeysManager
from license_manager import LicenseManager
from ui_styles import get_accent_color, get_accent_gradient, get_accent_hover, get_accent_secondary

# Theme color helpers - call these functions to get current theme colors
def _accent():
    return get_accent_color()

def _accent2():
    return get_accent_secondary()

def _gradient():
    return get_accent_gradient()

def _hover():
    return get_accent_hover()
from ui_license_dialog import LicenseActivationDialog, LicenseInfoDialog
from ui_subscription_dialog import SubscriptionDialog
from ui_youtube_downloader import YouTubeDownloaderPage, DownloadWorker as YtdlDownloadWorker

# Version information - import from central version.py
try:
    from version import VERSION, APP_NAME, COPYRIGHT
except ImportError:
    VERSION = "1.3.7"
    APP_NAME = "Nabil Video Studio Pro"
    COPYRIGHT = "Copyright (C) 2025 Nabil Software"

# Get directories
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()

MAIN_SCRIPT = SCRIPT_DIR / "recreat-videos.py"
CONTENT_CREATOR_SCRIPT = SCRIPT_DIR / "content_creator.py"
STORY_VIDEO_SCRIPT = SCRIPT_DIR / "story_video_creator.py"

def get_user_data_dir() -> Path:
    if os.name == 'nt':
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        user_dir = Path(appdata) / "NabilVideoStudioPro"
    else:
        user_dir = Path.home() / ".nvspro"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def ensure_user_files():
    user_dir = get_user_data_dir()
    files_to_ensure = [
        ("config.json", {}),
        ("api_keys.json", {"gemini_api_key": "", "_instructions": "Get your FREE Gemini API key from: https://aistudio.google.com/app/apikey"})
    ]
    for filename, default_content in files_to_ensure:
        user_file = user_dir / filename
        install_file = SCRIPT_DIR / filename
        if not user_file.exists():
            if install_file.exists():
                shutil.copy2(install_file, user_file)
            else:
                with open(user_file, 'w') as f:
                    json.dump(default_content, f, indent=2)

ensure_user_files()
USER_DATA_DIR = get_user_data_dir()
CONFIG_FILE = USER_DATA_DIR / "config.json"
API_KEYS_FILE = USER_DATA_DIR / "api_keys.json"

# ============================================================================
# MODERN DARK THEME V7 - Dynamic Theme Support
# ============================================================================

def get_theme_style():
    """Generate stylesheet with current theme colors"""
    from ui_styles import get_accent_color, get_accent_secondary, get_accent_hover, get_accent_gradient

    # Get theme colors
    accent = get_accent_color()
    accent2 = get_accent_secondary()
    hover = get_accent_hover()
    grad_start, grad_end = get_accent_gradient()

    style = """
/* ==================== BASE ==================== */
QMainWindow {
    background-color: #1a1a1a;
}

QWidget {
    background-color: transparent;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
    font-size: 13px;
}

/* ==================== MAIN CONTENT AREA ==================== */
#content_area {
    background: #1a1a1a;
    border-radius: 12px;
    margin: 8px;
    border: none;
}

/* ==================== SIDEBAR ==================== */
#sidebar {
    background: #141414;
    min-width: 220px;
    max-width: 220px;
    border-right: 1px solid #2a2a2a;
}

#sidebar_logo {
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    padding: 20px 0;
    min-height: 30px;
}

#sidebar_version {
    font-size: 11px;
    color: #888888;
    margin-top: -10px;
}

#sidebar_section {
    color: #888888;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 18px 24px 10px 24px;
}

#sidebar_btn {
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    padding: 14px 24px;
    text-align: left;
    font-size: 14px;
    color: #888888;
    margin: 2px 0;
}

#sidebar_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(230, 126, 34, 0.15), stop:1 transparent);
    color: {accent};
    border-left: 3px solid {accent};
}

#sidebar_btn_active {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(230, 126, 34, 0.25), stop:0.7 rgba(230, 126, 34, 0.08), stop:1 transparent);
    color: {accent};
    border: none;
    border-left: 4px solid {accent};
    border-radius: 0;
    padding: 14px 24px 14px 20px;
    text-align: left;
    font-size: 14px;
    margin: 2px 12px 2px 0;
    font-weight: 600;
}

/* ==================== CARDS ==================== */
#card {
    background: #252525;
    border: none;
    border-radius: 12px;
    padding: 20px;
}

#card:hover {
    border-color: {accent};
}

#stat_card {
    background: #252525;
    border: none;
    border-radius: 12px;
    padding: 20px;
    min-width: 160px;
}

#stat_card:hover {
    border-color: {accent};
}

#stat_value {
    font-size: 36px;
    font-weight: 700;
    color: {accent};
}

#stat_label {
    font-size: 12px;
    color: #888888;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Action Cards */
#action_card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {grad_end});
    border: none;
    border-radius: 12px;
    padding: 20px;
    min-height: 100px;
}

#action_card:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_end}, stop:1 {accent});
}

#action_card_blue {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {grad_end});
    border: none;
    border-radius: 12px;
    padding: 20px;
    min-height: 100px;
}

#action_card_blue:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_end}, stop:1 {accent});
}

/* ==================== BUTTONS ==================== */
QPushButton {
    background-color: #2a2a2a;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    color: #e0e0e0;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #3a3a3a;
    border-color: #888888;
}

QPushButton:pressed {
    background-color: #252525;
}

QPushButton:disabled {
    background-color: #252525;
    color: #555555;
    border-color: #2a2a2a;
}

#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {grad_end});
    border: none;
    color: #ffffff;
    font-weight: 600;
    font-size: 14px;
    padding: 12px 28px;
    border-radius: 6px;
}

#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_end}, stop:1 {accent});
}

#btn_primary:disabled {
    background: #2a2a2a;
    color: #555555;
}

#btn_success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {grad_end});
    border: none;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
}

#btn_success:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_end}, stop:1 {accent});
}

#btn_danger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #E74C3C, stop:1 #E74C3C);
    border: none;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
}

#btn_danger:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #E74C3C, stop:1 #C0392B);
}

#btn_icon {
    background-color: transparent;
    border: none;
    padding: 10px;
    border-radius: 6px;
    color: #888888;
}

#btn_icon:hover {
    background: rgba(56, 139, 253, 0.15);
    color: {accent};
}

#btn_browse {
    background-color: {grad_start};
    border: none;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
    padding: 8px 16px;
}

#btn_browse:hover {
    background-color: {accent};
}

#btn_accent {
    background-color: {grad_start};
    border: none;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
}

#btn_accent:hover {
    background-color: {accent};
}

#btn_accent_outline {
    background-color: transparent;
    border: 2px solid {accent};
    color: {accent};
    font-weight: 600;
    border-radius: 6px;
}

#btn_accent_outline:hover {
    background-color: {accent};
    color: #ffffff;
}

#btn_remove {
    background-color: #E74C3C;
    border: none;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
}

#btn_remove:hover {
    background-color: #C0392B;
}

#btn_settings {
    background-color: {grad_start};
    border: none;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
}

#btn_settings:hover {
    background-color: {accent};
}

/* ==================== INPUTS ==================== */
QLineEdit {
    background-color: #252525;
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    color: #e0e0e0;
    font-size: 13px;
    selection-background-color: {grad_start};
}

QLineEdit:focus {
    background-color: #2a2a2a;
}

QLineEdit:hover:!focus {
    background-color: #2a2a2a;
}

QLineEdit:disabled {
    background-color: #1a1a1a;
    color: #555555;
    border-color: #2a2a2a;
}

QLineEdit::placeholder {
    color: #555555;
}

QComboBox {
    background-color: #252525;
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    color: #e0e0e0;
    min-height: 20px;
}

QComboBox:focus {
    background-color: #2a2a2a;
}

QComboBox:hover:!focus {
    background-color: #2a2a2a;
}

QComboBox::drop-down {
    border: none;
    padding-right: 14px;
    width: 20px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #252525;
    border: none;
    border-radius: 6px;
    selection-background-color: {grad_start};
    color: #e0e0e0;
    padding: 6px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 10px 14px;
    border-radius: 4px;
    margin: 2px;
}

QComboBox QAbstractItemView::item:hover {
    background: rgba(56, 139, 253, 0.15);
}

/* ==================== CHECKBOX ==================== */
QCheckBox {
    spacing: 10px;
    color: #e0e0e0;
    font-size: 13px;
    padding: 4px;
}

QCheckBox:hover {
    color: #f0f6fc;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    background-color: #1a1a1a;
    border: none;
}

QCheckBox::indicator:hover {
    border-color: {accent};
}

QCheckBox::indicator:checked {
    background-color: {grad_start};
    border-color: {grad_start};
}

QCheckBox::indicator:checked:hover {
    background-color: {grad_end};
    border-color: {grad_end};
}

/* ==================== PROGRESS BAR ==================== */
QProgressBar {
    background-color: #2a2a2a;
    border: none;
    border-radius: 6px;
    height: 20px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {accent});
    border-radius: 6px;
}

/* Large Progress */
#progress_large {
    height: 28px;
    border-radius: 6px;
    font-size: 12px;
}

#progress_large::chunk {
    border-radius: 6px;
}

/* ==================== SCROLL AREA ==================== */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #252525;
    width: 14px;
    border-radius: 7px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a3a3a, stop:1 #555555);
    border-radius: 7px;
    min-height: 50px;
}

QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #555555, stop:1 #888888);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #252525;
    height: 14px;
    border-radius: 7px;
    margin: 2px 4px;
}

QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3a3a, stop:1 #555555);
    border-radius: 7px;
    min-width: 50px;
}

QScrollBar::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #555555, stop:1 #888888);
}

/* ==================== TEXT EDIT / LOG ==================== */
QTextEdit {
    background-color: #1a1a1a;
    border: none;
    border-radius: 10px;
    padding: 15px;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #27AE60;
    line-height: 1.5;
    selection-background-color: {grad_start};
}

/* ==================== GROUP BOX ==================== */
QGroupBox {
    font-weight: 600;
    font-size: 13px;
    border: none;
    border-radius: 12px;
    margin-top: 6px;
    padding: 10px;
    padding-top: 28px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #252525, stop:1 #1a1a1a);
    color: #e0e0e0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 3px 10px;
    color: {accent};
    background: #252525;
    border: none;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}

/* ==================== LIST WIDGET ==================== */
QListWidget {
    background-color: #1a1a1a;
    border: none;
    border-radius: 10px;
    padding: 8px;
    color: #e0e0e0;
    outline: none;
}

QListWidget::item {
    padding: 12px 15px;
    border-radius: 8px;
    margin: 2px 0;
}

QListWidget::item:selected {
    background-color: {grad_start};
    color: #ffffff;
}

QListWidget::item:hover:!selected {
    background-color: #2a2a2a;
}

/* ==================== TABLE ==================== */
QTableWidget {
    background-color: #1a1a1a;
    border: none;
    border-radius: 10px;
    gridline-color: #2a2a2a;
    color: #e0e0e0;
}

QTableWidget::item {
    padding: 10px;
    border-bottom: 1px solid #2a2a2a;
}

QTableWidget::item:selected {
    background-color: {grad_start};
}

QHeaderView::section {
    background-color: #252525;
    color: #e0e0e0;
    padding: 12px 15px;
    border: none;
    border-bottom: 1px solid #3a3a3a;
    font-weight: 600;
}

/* ==================== TAB WIDGET ==================== */
QTabWidget::pane {
    border: none;
    border-radius: 10px;
    background-color: #252525;
    padding: 15px;
}

QTabBar::tab {
    background-color: #1a1a1a;
    border: none;
    border-bottom: none;
    padding: 12px 25px;
    margin-right: 2px;
    border-radius: 8px 8px 0 0;
    color: #888888;
}

QTabBar::tab:selected {
    background-color: #252525;
    color: #e0e0e0;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #2a2a2a;
}

/* ==================== LABELS ==================== */
#title {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    padding-bottom: 5px;
}

#page_title {
    font-size: 24px;
    font-weight: 600;
    color: #e1e4e8;
}

#subtitle {
    font-size: 14px;
    color: #888888;
    padding-top: 2px;
}

#section_header {
    font-size: 16px;
    font-weight: 600;
    color: #e1e4e8;
    padding: 8px 0;
}

#label_muted {
    color: #6e7681;
    font-size: 12px;
}

#label_accent {
    color: {accent};
    font-weight: 600;
}

/* Status Labels */
#status_success {
    color: {accent};
    font-weight: 600;
    font-size: 13px;
}

#status_error {
    color: #E74C3C;
    font-weight: 600;
    font-size: 13px;
}

#status_warning {
    color: #d29922;
    font-weight: 600;
    font-size: 13px;
}

#status_info {
    color: {accent};
    font-weight: 600;
    font-size: 13px;
}

/* Badge Styles */
#badge_green {
    background-color: rgba(63, 185, 80, 0.2);
    color: {accent};
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

#badge_blue {
    background-color: rgba(56, 139, 253, 0.2);
    color: {accent};
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

#badge_red {
    background-color: rgba(248, 81, 73, 0.2);
    color: #E74C3C;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

#badge_orange {
    background-color: rgba(210, 153, 34, 0.2);
    color: #d29922;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

/* ==================== SPIN BOX ==================== */
QSpinBox, QDoubleSpinBox {
    background-color: #1a1a1a;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e0e0e0;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: {accent};
}

/* ==================== SLIDER ==================== */
QSlider::groove:horizontal {
    background-color: #2a2a2a;
    height: 8px;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background-color: {accent};
    width: 18px;
    height: 18px;
    margin: -5px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background-color: #79b8ff;
}

QSlider::sub-page:horizontal {
    background-color: {grad_start};
    border-radius: 4px;
}

/* ==================== TOOLTIPS ==================== */
QToolTip {
    background-color: #252525;
    border: none;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 8px 12px;
    font-size: 12px;
}

/* ==================== MENU ==================== */
QMenu {
    background-color: #252525;
    border: none;
    border-radius: 10px;
    padding: 8px;
}

QMenu::item {
    padding: 10px 20px;
    border-radius: 6px;
    color: #e0e0e0;
}

QMenu::item:selected {
    background-color: {grad_start};
}

QMenu::separator {
    height: 1px;
    background-color: #3a3a3a;
    margin: 5px 10px;
}

/* ==================== MESSAGE BOX ==================== */
QMessageBox {
    background-color: #252525;
}

QMessageBox QLabel {
    color: #e0e0e0;
}

/* ==================== DIALOG ==================== */
QDialog {
    background-color: #1a1a1a;
}

/* ==================== FOLDER CARDS ==================== */
#folder_card {
    background-color: #252525;
    border: none;
    border-radius: 12px;
    padding: 16px;
    margin: 4px 0;
}

#folder_card:hover {
    border-color: #3a3a3a;
    background-color: #252525;
}

#folder_path {
    color: #e1e4e8;
    font-size: 13px;
    font-weight: 500;
}

#folder_info {
    color: #888888;
    font-size: 11px;
}

/* ==================== CHANNEL CARDS ==================== */
#channel_card {
    background-color: #252525;
    border: none;
    border-radius: 14px;
    padding: 18px;
    min-width: 200px;
}

#channel_card:hover {
    border-color: {accent};
    background-color: #252525;
}

#channel_card_selected {
    background-color: #252525;
    border: 2px solid {accent};
    border-radius: 14px;
    padding: 17px;
    min-width: 200px;
}

#channel_name {
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
}

#channel_category {
    font-size: 11px;
    color: {accent};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ==================== STEP INDICATOR ==================== */
#step_indicator {
    background-color: #2a2a2a;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    color: #888888;
}

#step_indicator_active {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {accent});
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    color: #ffffff;
}

#step_indicator_done {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {grad_start}, stop:1 {accent});
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    color: #ffffff;
}

/* ==================== DIVIDER ==================== */
#divider {
    background-color: #2a2a2a;
    min-height: 1px;
    max-height: 1px;
    margin: 10px 0;
}

/* ==================== SEARCH ==================== */
#search_input {
    background-color: #1a1a1a;
    border: 2px solid #2a2a2a;
    border-radius: 20px;
    padding: 10px 20px;
    padding-left: 40px;
    color: #e1e4e8;
}

#search_input:focus {
    border-color: {accent};
}

/* ==================== CUSTOM TITLE BAR ==================== */
#title_bar {
    background: #1a1a1a;
    min-height: 38px;
    max-height: 38px;
    border-bottom: 2px solid {accent};
}

#title_bar_label {
    color: {accent};
    font-weight: 700;
    font-size: 13px;
    padding-left: 10px;
}

#title_bar_version {
    color: #7a8599;
    font-size: 11px;
    padding-left: 8px;
}

#title_bar_btn {
    background: transparent;
    border: none;
    color: #7a8599;
    font-family: "Segoe MDL2 Assets", "Arial";
    font-size: 11px;
    min-width: 50px;
    max-width: 50px;
    min-height: 38px;
    max-height: 38px;
    padding: 0;
    margin: 0;
}

#title_bar_btn:hover {
    background: #2a2a2a;
    color: {accent};
}

#title_bar_close {
    background: transparent;
    border: none;
    color: #7a8599;
    font-family: "Segoe MDL2 Assets", "Arial";
    font-size: 11px;
    min-width: 50px;
    max-width: 50px;
    min-height: 38px;
    max-height: 38px;
    padding: 0;
    margin: 0;
}

#title_bar_close:hover {
    background: #E74C3C;
    color: #ffffff;
}
"""
    # Replace theme placeholders
    style = style.replace("{accent}", accent)
    style = style.replace("{accent2}", accent2)
    style = style.replace("{hover}", hover)
    style = style.replace("{grad_start}", grad_start)
    style = style.replace("{grad_end}", grad_end)
    return style

# Legacy reference for compatibility
MODERN_STYLE = get_theme_style()

# ============================================================================
# PIPELINE WORKER (same as original)
# ============================================================================

def find_python_exe():
    """Find Python executable for running scripts"""
    # Always check for embedded Python first (works for both frozen and script mode)
    python_locations = [
        SCRIPT_DIR / 'python' / 'python.exe',  # Embedded Python (installed app)
        Path(sys.executable).parent / 'python.exe',  # Same folder as pythonw.exe
        Path(sys.executable).parent / 'python' / 'python.exe',
    ]
    for loc in python_locations:
        if loc.exists():
            return loc

    # Fallback: use sys.executable but ensure it's python.exe not pythonw.exe
    exe_path = Path(sys.executable)
    if exe_path.name.lower() == 'pythonw.exe':
        python_exe = exe_path.parent / 'python.exe'
        if python_exe.exists():
            return python_exe

    return exe_path


class VoiceoverWorker(QThread):
    """Worker thread for Script to Voice generation"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, script_path, output_folder, voice_url, num_tabs, use_api):
        super().__init__()
        self.script_path = script_path
        self.output_folder = output_folder
        self.voice_url = voice_url
        self.num_tabs = num_tabs
        self.use_api = use_api

    def run(self):
        try:
            from importlib.machinery import SourceFileLoader
            method = "API" if self.use_api else "Browser"

            self.progress.emit(f"Starting {method} generation...")
            print(f"VoiceoverWorker: Starting {method} method")

            if self.use_api:
                api_script = SCRIPT_DIR / "5_generate_voiceover_api.py"
                api_module = SourceFileLoader("voiceover_api", str(api_script)).load_module()

                self.progress.emit("Generating via API...")
                result = api_module.generate_voiceovers_from_script(
                    self.script_path,
                    self.output_folder,
                    self.voice_url,
                    self.num_tabs
                )
                count = len(result) if result else 0
                print(f"VoiceoverWorker: API returned {count} files")
            else:
                voiceover_script = SCRIPT_DIR / "5_generate_voiceover.py"
                voiceover_module = SourceFileLoader("voiceover", str(voiceover_script)).load_module()

                self.progress.emit("Generating via Browser...")
                voiceover_module.run_smart_parallel_with_voice_url(
                    self.script_path,
                    self.output_folder,
                    self.num_tabs,
                    self.voice_url,
                    "ScriptToVoice"
                )

            print("VoiceoverWorker: Generation complete!")
            self.finished.emit(True, self.output_folder)

        except Exception as e:
            print(f"VoiceoverWorker ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.finished.emit(False, str(e))


class PipelineWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool)
    step_notification = pyqtSignal(str, str)

    def __init__(self, main_script, profile_name=None, profile_count=None, input_folders=None,
                 start_step=-1, selected_profiles=None, manual_crop=False):
        super().__init__()
        self.main_script = main_script
        self.profile_name = profile_name
        self.profile_count = profile_count
        self.selected_profiles = selected_profiles  # List of selected profile names
        self.input_folders = input_folders
        self.start_step = start_step
        self.manual_crop = manual_crop  # Enable manual crop tool
        self.process = None
        self._stopped = False
        self._step2_notified = False
        self._step7_notified = False

    def run(self):
        try:
            self.progress.emit("🚀 Starting pipeline...")

            python_exe = find_python_exe()
            if python_exe is None:
                self.progress.emit('❌ Error: Python not found. Please install Python.')
                self.finished.emit(False)
                return

            cmd = [str(python_exe), str(self.main_script)]

            # Use --profiles for multiple selected profiles (new way)
            if self.selected_profiles and len(self.selected_profiles) > 0:
                cmd.append("--profiles")
                cmd.extend(self.selected_profiles)
            elif self.profile_name:
                # Fallback to single profile
                cmd.extend(["--profile", self.profile_name])
            elif self.profile_count is not None:
                # Fallback to profile count (legacy)
                cmd.extend(["--profile-count", str(self.profile_count)])

            if self.input_folders and len(self.input_folders) > 0:
                cmd.append('--input-folders')
                cmd.extend(self.input_folders)

            if self.start_step >= 0:
                cmd.extend(["--start-step", str(self.start_step)])

            if self.manual_crop:
                cmd.append("--manual-crop")

            print(f"DEBUG: Command: {cmd}")
            print("DEBUG: Starting subprocess...")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW  # Hide CMD window
            )
            print("DEBUG: Subprocess started, reading output...")

            for line in self.process.stdout:
                if self._stopped:
                    break
                line = line.strip()
                if line:
                    self.progress.emit(line)

                    line_lower = line.lower()
                    if "step 2:" in line_lower and "style" in line_lower and not self._step2_notified:
                        self._step2_notified = True
                        self.step_notification.emit("Step 2 - Manual Crop", "crop")
                    elif "step 7:" in line_lower and "assemble" in line_lower and not self._step7_notified:
                        self._step7_notified = True
                        self.step_notification.emit("Step 7 - Add Logo", "logo")

            return_code = self.process.wait()

            if self._stopped:
                self.progress.emit("⏹️ Pipeline stopped by user")
                self.finished.emit(False)
            else:
                success = return_code == 0
                if success:
                    self.progress.emit("✅ Pipeline completed successfully!")
                else:
                    self.progress.emit(f"❌ Pipeline failed with code {return_code}")
                self.finished.emit(success)

        except Exception as e:
            self.progress.emit(f"❌ Error: {str(e)}")
            self.finished.emit(False)

    def stop(self):
        self._stopped = True
        if self.process:
            try:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    self.process.terminate()
            except:
                pass


# ============================================================================
# STORY VIDEO WORKER
# ============================================================================

class StoryVideoWorker(QThread):
    """Worker thread for running story_video_creator.py pipeline"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, script_path, input_folders, output_folder, selected_profiles,
                 start_step=-1, options=None):
        super().__init__()
        self.script_path = script_path
        self.input_folders = input_folders if isinstance(input_folders, list) else [input_folders]
        self.output_folder = output_folder
        self.selected_profiles = selected_profiles or []
        self.start_step = start_step
        self.options = options or {}
        self.process = None
        self._stopped = False

    def run(self):
        try:
            total_folders = len(self.input_folders)
            self.progress.emit(f"📖 Starting Story Video pipeline for {total_folders} folder(s)...")

            python_exe = find_python_exe()
            if python_exe is None:
                self.progress.emit('❌ Error: Python not found.')
                self.finished.emit(False)
                return

            success_count = 0
            fail_count = 0

            # Process each input folder
            for idx, input_folder in enumerate(self.input_folders, 1):
                if self._stopped:
                    break

                folder_name = Path(input_folder).name
                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📁 Processing folder {idx}/{total_folders}: {folder_name}")
                self.progress.emit(f"{'='*60}")

                cmd = [str(python_exe), str(self.script_path)]

                # Input and output folders
                cmd.extend(["--input-folder", str(input_folder)])
                cmd.extend(["--output-folder", str(self.output_folder)])

                # Profiles
                if self.selected_profiles:
                    cmd.append("--profiles")
                    cmd.extend(self.selected_profiles)

                # Start step
                if self.start_step >= 0:
                    cmd.extend(["--start-step", str(self.start_step)])

                # Options
                if self.options.get('clean', False):
                    cmd.append("--clean")
                if not self.options.get('music', True):
                    cmd.append("--no-music")
                if not self.options.get('logo', True):
                    cmd.append("--no-logo")
                if self.options.get('global_broll', False) and self.options.get('broll_path'):
                    cmd.extend(["--global-broll", self.options['broll_path']])

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                for line in self.process.stdout:
                    if self._stopped:
                        break
                    line = line.strip()
                    if line:
                        self.progress.emit(line)

                return_code = self.process.wait()

                if self._stopped:
                    break
                elif return_code == 0:
                    success_count += 1
                    self.progress.emit(f"✅ Folder {idx}/{total_folders} completed: {folder_name}")
                else:
                    fail_count += 1
                    self.progress.emit(f"❌ Folder {idx}/{total_folders} failed: {folder_name}")

            # Final summary
            if self._stopped:
                self.progress.emit("⏹️ Story Video pipeline stopped by user")
                self.finished.emit(False)
            else:
                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📊 SUMMARY: {success_count} succeeded, {fail_count} failed")
                self.progress.emit(f"{'='*60}")
                if fail_count == 0:
                    self.progress.emit("✅ All Story Videos completed successfully!")
                    self.finished.emit(True)
                else:
                    self.progress.emit(f"⚠️ {fail_count} folder(s) failed")
                    self.finished.emit(False)

        except Exception as e:
            self.progress.emit(f"❌ Error: {str(e)}")
            self.finished.emit(False)

    def stop(self):
        self._stopped = True
        if self.process:
            try:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    self.process.terminate()
            except:
                pass


# ============================================================================
# CONTENT CREATOR WORKER
# ============================================================================

class ContentCreatorWorker(QThread):
    """Worker thread for running content_creator.py pipeline"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, script_path, interviews_folders, broll_folder, output_folder, selected_channels=None):
        super().__init__()
        self.script_path = script_path
        # Support both single folder (string) and list of folders
        if isinstance(interviews_folders, list):
            self.interviews_folders = interviews_folders
        else:
            self.interviews_folders = [interviews_folders] if interviews_folders else []
        self.broll_folder = broll_folder
        self.output_folder = output_folder
        self.selected_channels = selected_channels or []
        self.process = None
        self._stopped = False

    def run(self):
        try:
            total_folders = len(self.interviews_folders)
            if total_folders == 0:
                self.progress.emit("❌ No interview folders to process.")
                self.finished.emit(False)
                return

            self.progress.emit(f"🎬 Starting Content Creator pipeline for {total_folders} folder(s)...")

            python_exe = find_python_exe()
            if python_exe is None:
                self.progress.emit('❌ Error: Python not found.')
                self.finished.emit(False)
                return

            # === PARALLEL FOLDER PROCESSING (NEW) ===
            # Pass ALL folders to content_creator.py at once for parallel processing
            # The script will handle parallel execution internally

            # Create a temporary config to pass multiple folders
            import json
            import tempfile

            # Build the multi-folder config
            multi_folder_config = {
                "use_multi_folder_mode": True,
                "folders": [str(f) for f in self.interviews_folders]
            }

            # Write to a temp file that content_creator.py can read
            config_dir = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / 'NabilVideoStudioPro'
            config_dir.mkdir(parents=True, exist_ok=True)
            multi_folder_file = config_dir / 'multi_folder_queue.json'

            with open(multi_folder_file, 'w', encoding='utf-8') as f:
                json.dump(multi_folder_config, f, indent=2)

            self.progress.emit(f"📁 Queued {total_folders} folders for parallel processing")
            for idx, folder in enumerate(self.interviews_folders, 1):
                self.progress.emit(f"   {idx}. {Path(folder).name}")

            # Build command - use first folder as base, script reads the rest from queue file
            cmd = [str(python_exe), str(self.script_path)]
            cmd.extend(["--interviews-folder", str(self.interviews_folders[0])])
            cmd.extend(["--broll-folder", str(self.broll_folder)])
            cmd.extend(["--output-base-dir", str(self.output_folder)])
            cmd.append("--auto")  # Skip all prompts in GUI mode
            cmd.append("--use-folder-queue")  # NEW: Tell script to read from queue file

            # Pass selected channels if any
            if self.selected_channels:
                cmd.extend(["--channels", ",".join(self.selected_channels)])

            print(f"DEBUG: Content Creator Command: {cmd}")
            self.progress.emit(f"📁 B-Roll: {self.broll_folder}")
            self.progress.emit(f"📁 Output: {self.output_folder}")
            self.progress.emit(f"🚀 Starting parallel processing...")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for line in self.process.stdout:
                if self._stopped:
                    break
                line = line.strip()
                if line:
                    self.progress.emit(line)

            return_code = self.process.wait()

            # Cleanup temp file
            try:
                if multi_folder_file.exists():
                    os.remove(multi_folder_file)
            except:
                pass

            if self._stopped:
                self.progress.emit("⏹️ Content Creator stopped by user")
                self.finished.emit(False)
                return
            elif return_code == 0:
                self.progress.emit(f"✅ All {total_folders} folders processed successfully!")
                self.finished.emit(True)
            else:
                self.progress.emit(f"❌ Processing failed with code {return_code}")
                self.finished.emit(False)

        except Exception as e:
            self.progress.emit(f"❌ Error: {str(e)}")
            self.finished.emit(False)

    def stop(self):
        self._stopped = True
        if self.process:
            try:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    self.process.terminate()
            except:
                pass


# ============================================================================
# PROFILE EDITOR DIALOG
# ============================================================================

class ProfileEditorDialog(QDialog):
    """Clean editor for important channel settings"""

    def __init__(self, config_manager, profile_name: str, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.profile_name = profile_name
        self.profile_data = self.config_manager.get_profile(profile_name) or {}

        self.setWindowTitle(f"Edit: {profile_name}")
        self.setMinimumSize(580, 480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a1a; }}
            QLabel#field {{ color: #888888; font-size: 11px; font-weight: bold; }}
            QLineEdit {{
                background-color: #252525;
                color: #e0e0e0;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_accent()}; }}
            QComboBox {{
                background-color: #252525;
                color: #e0e0e0;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
            }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox QAbstractItemView {{ background-color: #252525; color: #e0e0e0; }}
            QCheckBox {{ color: #e0e0e0; font-size: 13px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; background: #2a2a2a; border: none; }}
            QCheckBox::indicator:checked {{ background: {_gradient()[0]}; border-color: {_gradient()[0]}; }}
            QPushButton {{ padding: 10px 16px; border-radius: 6px; font-weight: 600; font-size: 13px; }}
            QPushButton#browse {{ background: #2a2a2a; border: none; color: {_accent()}; padding: 10px 12px; }}
            QPushButton#browse:hover {{ background: #3a3a3a; }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header
        header = QLabel(profile_name)
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(header)

        # Name + Suffix row
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row1.addLayout(self._field("NAME", "name_edit", self.profile_data.get('name', '')), 2)
        row1.addLayout(self._field("SUFFIX", "suffix_edit", self.profile_data.get('suffix', ''), "e.g. baskly"), 1)
        layout.addLayout(row1)

        # Category + Voice row
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        # Category dropdown
        cat_box = QVBoxLayout()
        lbl = QLabel("CATEGORY")
        lbl.setObjectName("field")
        cat_box.addWidget(lbl)
        self.category_combo = QComboBox()
        for cat in self.config_manager.get_categories():
            self.category_combo.addItem(cat)
        idx = self.category_combo.findText(self.profile_data.get('category', 'Default'))
        if idx >= 0: self.category_combo.setCurrentIndex(idx)
        cat_box.addWidget(self.category_combo)
        row2.addLayout(cat_box, 1)

        # Voice dropdown
        voice_box = QVBoxLayout()
        voice_lbl = QLabel("VOICE")
        voice_lbl.setObjectName("field")
        voice_box.addWidget(voice_lbl)
        self.voice_combo = QComboBox()
        voices = self.config_manager.get_voices()
        current_voice = self.profile_data.get('default_voice', '')
        for voice_name in voices.keys():
            self.voice_combo.addItem(voice_name)
        voice_idx = self.voice_combo.findText(current_voice)
        if voice_idx >= 0:
            self.voice_combo.setCurrentIndex(voice_idx)
        elif current_voice:
            self.voice_combo.addItem(current_voice)
            self.voice_combo.setCurrentText(current_voice)
        voice_box.addWidget(self.voice_combo)
        row2.addLayout(voice_box, 1)

        layout.addLayout(row2)

        # Prompt file (for Recreate Video)
        layout.addLayout(self._file_field("PROMPT FILE (Recreate Video)", "prompt_edit", self.profile_data.get('prompt_file', ''), "Text (*.txt)"))

        # CC Prompt file (for Create Video)
        layout.addLayout(self._file_field("CC PROMPT FILE (Create Video)", "cc_prompt_edit", self.profile_data.get('cc_prompt_file', ''), "Text (*.txt)"))

        # Background video
        layout.addLayout(self._file_field("BACKGROUND VIDEO", "bg_video_edit", self.profile_data.get('background_video', ''), "Video (*.mp4 *.mov)"))

        # Background music
        layout.addLayout(self._file_field("BACKGROUND MUSIC", "bg_music_edit", self.profile_data.get('background_music', ''), "Audio (*.mp3 *.wav)"))

        # Options row: checkboxes + upload wait
        options_row = QHBoxLayout()
        options_row.setSpacing(20)
        self.cb_manual_crop = QCheckBox("Manual Crop")
        self.cb_manual_crop.setChecked(self.profile_data.get('use_manual_crop', False))
        options_row.addWidget(self.cb_manual_crop)
        self.cb_upload = QCheckBox("Auto Upload")
        self.cb_upload.setChecked(self.profile_data.get('enable_upload', True))
        options_row.addWidget(self.cb_upload)
        options_row.addSpacing(20)
        wait_lbl = QLabel("Upload Wait:")
        wait_lbl.setStyleSheet("color: #888888;")
        options_row.addWidget(wait_lbl)
        self.wait_edit = QLineEdit(str(self.profile_data.get('upload_wait_minutes', 5)))
        self.wait_edit.setFixedWidth(50)
        self.wait_edit.setPlaceholderText("5")
        options_row.addWidget(self.wait_edit)
        min_lbl = QLabel("min")
        min_lbl.setStyleSheet("color: #888888;")
        options_row.addWidget(min_lbl)
        options_row.addStretch()
        layout.addLayout(options_row)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_json = QPushButton("View JSON")
        btn_json.setStyleSheet(f"background: #2a2a2a; border: none; color: {_accent()};")
        btn_json.clicked.connect(self.show_json)
        btn_row.addWidget(btn_json)
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background: #2a2a2a; border: none; color: #e0e0e0;")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet(f"background: {_gradient()[0]}; border: none; color: white;")
        btn_save.clicked.connect(self.save_profile)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _field(self, label, attr, value, placeholder=""):
        box = QVBoxLayout()
        box.setSpacing(4)
        lbl = QLabel(label)
        lbl.setObjectName("field")
        box.addWidget(lbl)
        edit = QLineEdit(value)
        if placeholder: edit.setPlaceholderText(placeholder)
        setattr(self, attr, edit)
        box.addWidget(edit)
        return box

    def _file_field(self, label, attr, value, filter_str):
        box = QVBoxLayout()
        box.setSpacing(4)
        lbl = QLabel(label)
        lbl.setObjectName("field")
        box.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(8)
        edit = QLineEdit(value)
        setattr(self, attr, edit)
        row.addWidget(edit)
        btn = QPushButton("...")
        btn.setObjectName("browse")
        btn.setFixedWidth(40)
        btn.clicked.connect(lambda: self._browse(edit, filter_str))
        row.addWidget(btn)
        box.addLayout(row)
        return box

    def _browse(self, field, filter_str):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if path: field.setText(path)

    def _folder_field(self, label, attr, value):
        """Create a folder selection field"""
        box = QVBoxLayout()
        box.setSpacing(4)
        lbl = QLabel(label)
        lbl.setObjectName("field")
        box.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(8)
        edit = QLineEdit(value)
        setattr(self, attr, edit)
        row.addWidget(edit)
        btn = QPushButton("...")
        btn.setObjectName("browse")
        btn.setFixedWidth(40)
        btn.clicked.connect(lambda: self._browse_folder(edit))
        row.addWidget(btn)
        box.addLayout(row)
        return box

    def _browse_folder(self, field):
        path = QFileDialog.getExistingDirectory(self, "Select Folder", "")
        if path: field.setText(path)

    def show_json(self):
        """Show full JSON in editable dialog"""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"JSON: {self.profile_name}")
        dlg.setMinimumSize(500, 400)
        dlg.setStyleSheet("QDialog { background: #1a1a1a; } QTextEdit { background: #252525; color: #e0e0e0; border: none; border-radius: 6px; padding: 10px; font-family: Consolas; font-size: 12px; }")
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setPlainText(json.dumps(self.profile_data, indent=2))
        layout.addWidget(text_edit)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background: #2a2a2a; border: none; color: #e0e0e0; padding: 8px 16px; border-radius: 6px;")
        btn_close.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_close)
        btn_apply = QPushButton("Apply JSON")
        btn_apply.setStyleSheet(f"background: {_gradient()[0]}; border: none; color: white; padding: 8px 16px; border-radius: 6px;")
        def apply_json():
            try:
                new_data = json.loads(text_edit.toPlainText())
                self.profile_data = new_data
                # Update UI fields
                self.name_edit.setText(new_data.get('name', ''))
                self.suffix_edit.setText(new_data.get('suffix', ''))
                self.voice_combo.setCurrentText(new_data.get('default_voice', ''))
                self.prompt_edit.setText(new_data.get('prompt_file', ''))
                self.cc_prompt_edit.setText(new_data.get('cc_prompt_file', ''))
                self.bg_video_edit.setText(new_data.get('background_video', ''))
                self.bg_music_edit.setText(new_data.get('background_music', ''))
                self.cb_manual_crop.setChecked(new_data.get('use_manual_crop', False))
                self.cb_upload.setChecked(new_data.get('enable_upload', True))
                self.wait_edit.setText(str(new_data.get('upload_wait_minutes', 5)))
                dlg.accept()
                QMessageBox.information(self, "OK", "JSON applied to form!")
            except Exception as e:
                QMessageBox.critical(dlg, "Error", f"Invalid JSON: {e}")
        btn_apply.clicked.connect(apply_json)
        btn_row.addWidget(btn_apply)
        layout.addLayout(btn_row)
        dlg.exec_()

    def save_profile(self):
        data = self.profile_data.copy()
        data['name'] = self.name_edit.text().strip()
        data['suffix'] = self.suffix_edit.text().strip()
        data['category'] = self.category_combo.currentText()
        data['default_voice'] = self.voice_combo.currentText()
        data['prompt_file'] = self.prompt_edit.text().strip()
        data['cc_prompt_file'] = self.cc_prompt_edit.text().strip()
        data['background_video'] = self.bg_video_edit.text().strip()
        data['background_music'] = self.bg_music_edit.text().strip()
        data['use_manual_crop'] = self.cb_manual_crop.isChecked()
        data['enable_upload'] = self.cb_upload.isChecked()
        try:
            data['upload_wait_minutes'] = int(self.wait_edit.text().strip() or 5)
        except:
            data['upload_wait_minutes'] = 5

        if not data['name'] or not data['suffix']:
            QMessageBox.warning(self, "Error", "Name and Suffix are required!")
            return

        if self.config_manager.update_profile(self.profile_name, data):
            QMessageBox.information(self, "Success", "Saved!")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save!")


# ============================================================================
# CATEGORY MANAGER DIALOG
# ============================================================================

class CategoryManagerDialog(QDialog):
    """Dialog to manage channel categories with default paths"""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.category_widgets = {}  # Store references to path fields

        # Migrate old categories to new format
        self.config_manager.migrate_categories_to_data()

        self.setWindowTitle("Manage Categories")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a1a; }}
            QLabel {{ color: #e0e0e0; }}
            QLineEdit {{ background-color: #2a2a2a; color: #e0e0e0; border: none; border-radius: 6px; padding: 8px; }}
            QLineEdit:focus {{ border-color: {_accent()}; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: bold; background-color: #2a2a2a; border: none; color: #e0e0e0; }}
            QPushButton:hover {{ background-color: #3a3a3a; }}
            QScrollArea {{ border: none; background-color: transparent; }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title
        title = QLabel("Category Manager - Default Paths")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; padding: 10px; color: {_accent()};")
        layout.addWidget(title)

        # Info label
        info = QLabel("Set default input/output folders for each category. When you select channels from a category, these paths will auto-fill.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #888888; padding: 5px 10px;")
        layout.addWidget(info)

        # Scrollable area for categories
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.categories_container = QWidget()
        self.categories_layout = QVBoxLayout(self.categories_container)
        self.categories_layout.setSpacing(10)

        scroll.setWidget(self.categories_container)
        layout.addWidget(scroll)

        # Add new category section
        add_frame = QFrame()
        add_frame.setStyleSheet("QFrame { background-color: #252525; border: none; border-radius: 6px; padding: 10px; }")
        add_layout = QHBoxLayout(add_frame)

        add_label = QLabel("➕ Add New Category:")
        add_label.setStyleSheet("font-weight: bold;")
        add_layout.addWidget(add_label)

        self.new_category_input = QLineEdit()
        self.new_category_input.setPlaceholderText("Enter category name...")
        self.new_category_input.setMinimumWidth(200)
        add_layout.addWidget(self.new_category_input)

        btn_add = QPushButton("Add Category")
        btn_add.setStyleSheet(f"background-color: {_gradient()[0]}; border: 1px solid {_gradient()[0]}; color: white;")
        btn_add.clicked.connect(self.add_category)
        add_layout.addWidget(btn_add)

        add_layout.addStretch()
        layout.addWidget(add_frame)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        btn_save = QPushButton("Save All Paths")
        btn_save.setStyleSheet(f"background-color: {_gradient()[0]}; border: 1px solid {_gradient()[0]}; color: white; padding: 10px 20px;")
        btn_save.clicked.connect(self.save_all_paths)
        btn_layout.addWidget(btn_save)

        btn_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Load categories
        self.load_categories()

    def load_categories(self):
        """Load all categories with their paths"""
        # Clear existing
        for i in reversed(range(self.categories_layout.count())):
            widget = self.categories_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.category_widgets.clear()

        categories = self.config_manager.get_categories()

        for cat in categories:
            self.add_category_widget(cat)

        self.categories_layout.addStretch()

    def add_category_widget(self, cat_name: str):
        """Add a category widget with path fields"""
        cat_data = self.config_manager.get_category_data(cat_name)
        profiles = self.config_manager.get_profiles()
        count = sum(1 for p in profiles.values() if p.get("category", "Default") == cat_name)

        # Category frame
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background-color: #252525; border: none; border-radius: 8px; }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(8)

        # Header row
        header_layout = QHBoxLayout()

        cat_label = QLabel(f"{cat_name}")
        cat_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {_accent()};")
        header_layout.addWidget(cat_label)

        count_label = QLabel(f"({count} channels)")
        count_label.setStyleSheet("color: #888888;")
        header_layout.addWidget(count_label)

        header_layout.addStretch()

        # Auto Create Folders button
        btn_auto_create = QPushButton("Auto Create")
        btn_auto_create.setFixedWidth(100)
        btn_auto_create.setToolTip("Select a base location and auto-create all folder structure")
        btn_auto_create.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #0891b2);
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #0e7490);
            }
        """)
        btn_auto_create.clicked.connect(lambda checked, n=cat_name: self.auto_create_folders(n))
        header_layout.addWidget(btn_auto_create)

        # Clean All button - cleans both input and output folders
        btn_clean_all = QPushButton("Clean All")
        btn_clean_all.setFixedWidth(80)
        btn_clean_all.setToolTip("Clean all files from Input and Output folders")
        btn_clean_all.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ea580c);
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #c2410c);
            }
        """)
        btn_clean_all.clicked.connect(lambda checked, n=cat_name: self.clean_category_folders(n))
        header_layout.addWidget(btn_clean_all)

        # Rename button (not for Default)
        if cat_name != "Default":
            btn_rename = QPushButton("Edit")
            btn_rename.setFixedSize(50, 30)
            btn_rename.setToolTip("Rename category")
            btn_rename.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            btn_rename.clicked.connect(lambda checked, n=cat_name: self.rename_category(n))
            header_layout.addWidget(btn_rename)

            btn_delete = QPushButton("X")
            btn_delete.setFixedSize(30, 30)
            btn_delete.setToolTip("Delete category")
            btn_delete.setStyleSheet("""
                QPushButton {
                    background-color: #E74C3C;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #C0392B;
                }
            """)
            btn_delete.clicked.connect(lambda checked, n=cat_name: self.delete_category(n))
            header_layout.addWidget(btn_delete)

        frame_layout.addLayout(header_layout)

        # Input path row
        input_layout = QHBoxLayout()
        input_label = QLabel("Default Input:")
        input_label.setMinimumWidth(120)
        input_layout.addWidget(input_label)

        input_edit = QLineEdit()
        input_edit.setPlaceholderText("Select default input folder for this category...")
        input_edit.setText(cat_data.get("input_path", ""))
        input_layout.addWidget(input_edit)

        btn_input_browse = QPushButton("...")
        btn_input_browse.setFixedWidth(40)
        btn_input_browse.setToolTip("Browse folder")
        btn_input_browse.clicked.connect(lambda: self.browse_folder(input_edit))
        input_layout.addWidget(btn_input_browse)

        frame_layout.addLayout(input_layout)

        # Output path row
        output_layout = QHBoxLayout()
        output_label = QLabel("Default Output:")
        output_label.setMinimumWidth(120)
        output_layout.addWidget(output_label)

        output_edit = QLineEdit()
        output_edit.setPlaceholderText("Select default output folder for this category...")
        output_edit.setText(cat_data.get("output_path", ""))
        output_layout.addWidget(output_edit)

        btn_output_browse = QPushButton("...")
        btn_output_browse.setFixedWidth(40)
        btn_output_browse.setToolTip("Browse folder")
        btn_output_browse.clicked.connect(lambda: self.browse_folder(output_edit))
        output_layout.addWidget(btn_output_browse)

        frame_layout.addLayout(output_layout)

        # Separator for Create Video paths
        separator = QLabel("─── Create Video Paths ───")
        separator.setStyleSheet(f"color: {_accent()}; font-size: 11px; padding: 5px 0;")
        separator.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(separator)

        # CC Interviews path row
        cc_interviews_layout = QHBoxLayout()
        cc_interviews_label = QLabel("CC Interviews:")
        cc_interviews_label.setMinimumWidth(120)
        cc_interviews_layout.addWidget(cc_interviews_label)

        cc_interviews_edit = QLineEdit()
        cc_interviews_edit.setPlaceholderText("Interviews folder for Create Video...")
        cc_interviews_edit.setText(cat_data.get("cc_interviews_path", ""))
        cc_interviews_layout.addWidget(cc_interviews_edit)

        btn_cc_interviews_browse = QPushButton("...")
        btn_cc_interviews_browse.setFixedWidth(40)
        btn_cc_interviews_browse.setToolTip("Browse folder")
        btn_cc_interviews_browse.clicked.connect(lambda: self.browse_folder(cc_interviews_edit))
        cc_interviews_layout.addWidget(btn_cc_interviews_browse)

        frame_layout.addLayout(cc_interviews_layout)

        # CC B-Roll path row
        cc_broll_layout = QHBoxLayout()
        cc_broll_label = QLabel("CC B-Roll:")
        cc_broll_label.setMinimumWidth(120)
        cc_broll_layout.addWidget(cc_broll_label)

        cc_broll_edit = QLineEdit()
        cc_broll_edit.setPlaceholderText("B-Roll folder for Create Video...")
        cc_broll_edit.setText(cat_data.get("cc_broll_path", ""))
        cc_broll_layout.addWidget(cc_broll_edit)

        btn_cc_broll_browse = QPushButton("...")
        btn_cc_broll_browse.setFixedWidth(40)
        btn_cc_broll_browse.setToolTip("Browse folder")
        btn_cc_broll_browse.clicked.connect(lambda: self.browse_folder(cc_broll_edit))
        cc_broll_layout.addWidget(btn_cc_broll_browse)

        frame_layout.addLayout(cc_broll_layout)

        # CC Output path row
        cc_output_layout = QHBoxLayout()
        cc_output_label = QLabel("CC Output:")
        cc_output_label.setMinimumWidth(120)
        cc_output_layout.addWidget(cc_output_label)

        cc_output_edit = QLineEdit()
        cc_output_edit.setPlaceholderText("Output folder for Create Video...")
        cc_output_edit.setText(cat_data.get("cc_output_path", ""))
        cc_output_layout.addWidget(cc_output_edit)

        btn_cc_output_browse = QPushButton("...")
        btn_cc_output_browse.setFixedWidth(40)
        btn_cc_output_browse.setToolTip("Browse folder")
        btn_cc_output_browse.clicked.connect(lambda: self.browse_folder(cc_output_edit))
        cc_output_layout.addWidget(btn_cc_output_browse)

        frame_layout.addLayout(cc_output_layout)

        # Store references
        self.category_widgets[cat_name] = {
            "frame": frame,
            "input_edit": input_edit,
            "output_edit": output_edit,
            "cc_interviews_edit": cc_interviews_edit,
            "cc_broll_edit": cc_broll_edit,
            "cc_output_edit": cc_output_edit
        }

        self.categories_layout.addWidget(frame)

    def browse_folder(self, line_edit):
        """Browse for folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", line_edit.text())
        if folder:
            line_edit.setText(folder)

    def auto_create_folders(self, cat_name: str):
        """Auto create folder structure for a category"""
        # Check if category already has paths configured
        if cat_name in self.category_widgets:
            widgets = self.category_widgets[cat_name]
            has_paths = any([
                widgets["input_edit"].text().strip(),
                widgets["output_edit"].text().strip(),
                widgets["cc_interviews_edit"].text().strip(),
                widgets["cc_broll_edit"].text().strip(),
                widgets["cc_output_edit"].text().strip()
            ])

            if has_paths:
                reply = QMessageBox.warning(
                    self,
                    "Paths Already Exist",
                    f"Category '{cat_name}' already has paths configured.\n\n"
                    f"Do you want to replace them with new auto-created folders?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        # Ask user to select base location
        base_folder = QFileDialog.getExistingDirectory(
            self,
            f"Select Base Location for '{cat_name}' Folders",
            "",
            QFileDialog.ShowDirsOnly
        )

        if not base_folder:
            return  # User cancelled

        # Build folder structure
        # Base/CategoryName/Recreate-Video/INPUT, OUTPUT
        # Base/CategoryName/Create-Video/INPUT, OUTPUT, CLIPS

        category_root = os.path.join(base_folder, cat_name)

        folders_to_create = {
            "recreate_input": os.path.join(category_root, "Recreate-Video", "INPUT"),
            "recreate_output": os.path.join(category_root, "Recreate-Video", "OUTPUT"),
            "create_input": os.path.join(category_root, "Create-Video", "INPUT"),
            "create_output": os.path.join(category_root, "Create-Video", "OUTPUT"),
            "create_clips": os.path.join(category_root, "Create-Video", "CLIPS"),
        }

        # Create all folders
        try:
            for folder_path in folders_to_create.values():
                os.makedirs(folder_path, exist_ok=True)

            # Auto-fill the path fields
            if cat_name in self.category_widgets:
                widgets = self.category_widgets[cat_name]
                widgets["input_edit"].setText(folders_to_create["recreate_input"])
                widgets["output_edit"].setText(folders_to_create["recreate_output"])
                widgets["cc_interviews_edit"].setText(folders_to_create["create_input"])
                widgets["cc_output_edit"].setText(folders_to_create["create_output"])
                widgets["cc_broll_edit"].setText(folders_to_create["create_clips"])

            QMessageBox.information(
                self,
                "Folders Created",
                f"✅ All folders created successfully!\n\n"
                f"📁 {cat_name}\n"
                f"   ├── Recreate-Video\n"
                f"   │   ├── INPUT\n"
                f"   │   └── OUTPUT\n"
                f"   └── Create-Video\n"
                f"       ├── INPUT\n"
                f"       ├── OUTPUT\n"
                f"       └── CLIPS\n\n"
                f"Location: {category_root}\n\n"
                f"Path fields have been auto-filled. Click 'Save All Paths' to save."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create folders:\n{str(e)}"
            )

    def save_all_paths(self):
        """Save all category paths"""
        for cat_name, widgets in self.category_widgets.items():
            input_path = widgets["input_edit"].text().strip()
            output_path = widgets["output_edit"].text().strip()
            cc_interviews_path = widgets["cc_interviews_edit"].text().strip()
            cc_broll_path = widgets["cc_broll_edit"].text().strip()
            cc_output_path = widgets["cc_output_edit"].text().strip()
            self.config_manager.set_category_paths(
                cat_name, input_path, output_path,
                cc_interviews_path, cc_broll_path, cc_output_path
            )

        QMessageBox.information(self, "Success", "All category paths saved!")

    def add_category(self):
        """Add new category"""
        name = self.new_category_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a category name.")
            return

        if self.config_manager.add_category(name):
            self.new_category_input.clear()
            self.load_categories()
            QMessageBox.information(self, "Success", f"Category '{name}' added!")
        else:
            QMessageBox.warning(self, "Error", "Category already exists.")

    def rename_category(self, old_name: str):
        """Rename category"""
        from PyQt5.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=old_name)

        if ok and new_name.strip():
            if self.config_manager.rename_category(old_name, new_name.strip()):
                self.load_categories()
                QMessageBox.information(self, "Success", f"Category renamed to '{new_name}'!")
            else:
                QMessageBox.warning(self, "Error", "Failed to rename category.")

    def delete_category(self, name: str):
        """Delete category"""
        reply = QMessageBox.question(
            self, "Delete Category",
            f"Delete '{name}'?\n\nChannels will be moved to 'Default'.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.config_manager.delete_category(name):
                self.load_categories()
                QMessageBox.information(self, "Success", f"Category '{name}' deleted!")
            else:
                QMessageBox.warning(self, "Error", "Failed to delete category.")

    def clean_category_folders(self, cat_name: str):
        """Clean all files from category's input and output folders"""
        cat_data = self.config_manager.get_category_data(cat_name)

        input_path = cat_data.get("input_path", "")
        output_path = cat_data.get("output_path", "")

        # Check if paths exist
        folders_to_clean = []
        if input_path and os.path.exists(input_path):
            folders_to_clean.append(("Input", input_path))
        if output_path and os.path.exists(output_path):
            folders_to_clean.append(("Output", output_path))

        if not folders_to_clean:
            QMessageBox.warning(self, "No Folders", f"No valid folders configured for '{cat_name}'.\n\nPlease set Input and Output paths first.")
            return

        # Build confirmation message
        folder_list = "\n".join([f"  • {name}: {path}" for name, path in folders_to_clean])

        # Custom dialog for confirmation
        msg = QMessageBox(self)
        msg.setWindowTitle(f"🧹 Clean Category: {cat_name}")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"<b>Are you sure you want to clean all files?</b>")
        msg.setInformativeText(f"This will permanently delete all files and folders in:\n\n{folder_list}\n\n⚠️ This action cannot be undone!")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        # Style the dialog
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1a1a2e;
            }
            QMessageBox QLabel {
                color: #e2e8f0;
                font-size: 13px;
            }
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: 600;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)

        if msg.exec_() == QMessageBox.Yes:
            cleaned_count = 0
            errors = []

            for folder_name, folder_path in folders_to_clean:
                try:
                    items = os.listdir(folder_path)
                    for item in items:
                        item_path = os.path.join(folder_path, item)
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                cleaned_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                cleaned_count += 1
                        except Exception as e:
                            errors.append(f"{item}: {str(e)}")
                except Exception as e:
                    errors.append(f"{folder_name}: {str(e)}")

            if errors:
                QMessageBox.warning(self, "Partial Success",
                    f"Cleaned {cleaned_count} items but had some errors:\n\n" + "\n".join(errors[:5]))
            else:
                QMessageBox.information(self, "Success",
                    f"✅ Successfully cleaned {cleaned_count} items from '{cat_name}' folders!")


# ============================================================================
# SIDEBAR BUTTON
# ============================================================================

class SidebarButton(QPushButton):
    """Modern sidebar button with icon and label"""
    def __init__(self, icon_text, label, parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.label = label
        self.setText(f"  {icon_text}    {label}")
        self.setObjectName("sidebar_btn")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setMinimumWidth(200)

    def set_active(self, active):
        self.setObjectName("sidebar_btn_active" if active else "sidebar_btn")
        self.style().unpolish(self)
        self.style().polish(self)


# ============================================================================
# PATH SELECTOR WIDGET
# ============================================================================

class ModernPathSelector(QWidget):
    def __init__(self, placeholder="Select folder...", is_file=False, parent=None):
        super().__init__(parent)
        self.is_file = is_file

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        layout.addWidget(self.line_edit)

        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setObjectName("btn_browse")
        self.btn_browse.clicked.connect(self.browse)
        layout.addWidget(self.btn_browse)

    def browse(self):
        if self.is_file:
            path, _ = QFileDialog.getOpenFileName(self, "Select File")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            self.line_edit.setText(path)

    def get_path(self):
        return self.line_edit.text()

    def set_path(self, path):
        self.line_edit.setText(path)


# ============================================================================
# MAIN WINDOW
# ============================================================================

class ModernMainWindow(QMainWindow):
    def __init__(self, skip_license_check=False):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(1280, 800)
        self.resize(1500, 900)
        self.setStyleSheet(get_theme_style())

        # Set application icon (window, taskbar)
        icon_path = Path(__file__).parent / "assets" / "logo.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Drag state for custom title bar
        self._drag_pos = None

        # Center window on screen
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().availableGeometry()
        x = (screen.width() - 1500) // 2
        y = (screen.height() - 900) // 2
        self.move(x, y)

        # Initialize managers
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.license_manager = LicenseManager()

        # Check license (skip if already checked in main())
        if not skip_license_check and not self.check_license():
            sys.exit(1)

        # Media player for notifications
        self.media_player = QMediaPlayer()

        # Setup UI
        self.setup_ui()

        # Load saved settings
        self.load_settings()

        # Pipeline workers
        self.worker = None
        self.sv_worker = None

        # Track last width for resize optimization
        self._last_width = 0

        # Refresh channel list after window is fully shown
        QTimer.singleShot(100, self.update_channel_list)

        # SECURITY: Periodic license re-check every 30 minutes
        self._license_timer = QTimer(self)
        self._license_timer.timeout.connect(self._periodic_license_check)
        self._license_timer.start(30 * 60 * 1000)  # 30 minutes in ms

    def _periodic_license_check(self):
        """Silent license re-check while app is running.
        If license expired/revoked mid-session, block the app."""
        try:
            is_licensed, message, _ = self.license_manager.check_license()
            if not is_licensed:
                # Stop any running pipelines
                if self.worker and self.worker.isRunning():
                    self.worker.stop()
                if self.sv_worker and self.sv_worker.isRunning():
                    self.sv_worker.stop()
                if hasattr(self, 'cc_worker') and self.cc_worker and self.cc_worker.isRunning():
                    self.cc_worker.stop()

                # Show license dialog - must re-activate or quit
                QMessageBox.warning(
                    self, "License Expired",
                    f"Your license is no longer valid:\n{message}\n\nPlease re-activate or upgrade."
                )
                dialog = LicenseActivationDialog(self)
                if dialog.exec_() != dialog.Accepted:
                    sys.exit(1)
        except Exception:
            pass  # Don't crash app on check failure

    def resizeEvent(self, event):
        """Handle window resize - update channel grid columns"""
        super().resizeEvent(event)
        # Only update if width changed significantly (avoid too many updates)
        new_width = self.width()
        if abs(new_width - self._last_width) > 100:
            self._last_width = new_width
            # Update channel list if on channels page
            if hasattr(self, 'content_stack') and self.content_stack.currentIndex() == 1:
                self.update_channel_list()

    def check_license(self):
        is_licensed, message, license_info = self.license_manager.check_license()
        if not is_licensed:
            dialog = LicenseActivationDialog(self)
            if dialog.exec_() != dialog.Accepted:
                return False
        return True

    def apply_theme(self, theme_name: str):
        """Apply a new theme live without restart"""
        from ui_styles import set_current_theme, apply_theme_live

        # Update the theme
        set_current_theme(theme_name)

        # Apply to QApplication (global styles)
        apply_theme_live()

        # Re-apply main window stylesheet
        self.setStyleSheet(get_theme_style())

        # Refresh all themed widgets throughout the application
        self._refresh_themed_widgets()

        # Force repaint
        self.update()
        self.repaint()

    def _refresh_themed_widgets(self):
        """Refresh all widgets that use theme colors"""
        from ui_styles import THEMES

        # Get new theme colors
        new_accent = _accent()
        new_accent2 = _accent2()
        new_grad_start, new_grad_end = _gradient()
        new_hover = _hover()

        # Collect all possible old accent colors from all themes
        old_colors = set()
        for theme_name, theme_data in THEMES.items():
            old_colors.add(theme_data['accent_primary'].lower())
            old_colors.add(theme_data['accent_secondary'].lower())
            old_colors.add(theme_data['accent_hover'].lower())
            old_colors.add(theme_data['accent_gradient_start'].lower())
            old_colors.add(theme_data['accent_gradient_end'].lower())

        # Remove current theme colors from old_colors (we don't want to replace those)
        current_colors = {new_accent.lower(), new_accent2.lower(), new_hover.lower(),
                         new_grad_start.lower(), new_grad_end.lower()}

        # Create color replacement map
        # Map old accent colors to new ones based on their role
        color_map = {}
        for theme_name, theme_data in THEMES.items():
            color_map[theme_data['accent_primary'].lower()] = new_accent
            color_map[theme_data['accent_secondary'].lower()] = new_accent2
            color_map[theme_data['accent_hover'].lower()] = new_hover
            color_map[theme_data['accent_gradient_start'].lower()] = new_grad_start
            color_map[theme_data['accent_gradient_end'].lower()] = new_grad_end

        # Scan all widgets and replace old accent colors in stylesheets
        for widget in self.findChildren(QWidget):
            style = widget.styleSheet()
            if style:
                new_style = style
                style_lower = style.lower()

                # Check if this widget's style contains any old theme colors
                needs_update = False
                for old_color in old_colors:
                    if old_color in style_lower and old_color not in current_colors:
                        needs_update = True
                        break

                if needs_update:
                    # Replace colors (case-insensitive)
                    import re
                    for old_color, new_color in color_map.items():
                        pattern = re.compile(re.escape(old_color), re.IGNORECASE)
                        new_style = pattern.sub(new_color, new_style)

                    widget.setStyleSheet(new_style)

        # Clear inline styles for widgets that should use the main stylesheet
        for widget in self.findChildren(QWidget):
            obj_name = widget.objectName()
            if obj_name in ('action_card', 'action_card_blue', 'btn_primary', 'btn_success', 'stat_value'):
                widget.setStyleSheet("")

        # Force style recalculation on all child widgets
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self.create_title_bar()
        outer_layout.addWidget(self.title_bar)

        # Body: sidebar + content
        body_widget = QWidget()
        main_layout = QHBoxLayout(body_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        outer_layout.addWidget(body_widget)

        # Sidebar
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)

        # Content area
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)

        # Add pages
        self.content_stack.addWidget(self.create_project_page())      # 0 - Project/Run
        self.content_stack.addWidget(self.create_channels_page())     # 1 - Channels
        self.content_stack.addWidget(self.create_settings_page())     # 2 - Settings
        self.content_stack.addWidget(self.create_voices_page())       # 3 - Voices
        self.content_stack.addWidget(self.create_api_keys_page())     # 4 - API Keys
        self.content_stack.addWidget(self.create_log_page())          # 5 - Log
        self.content_stack.addWidget(QWidget())                       # 6 - (removed)
        self.content_stack.addWidget(self.create_youtube_page())      # 7 - YouTube Downloader
        self.content_stack.addWidget(self.create_content_creator_page())  # 8 - Content Creator
        self.content_stack.addWidget(QWidget())                       # 9 - (removed)
        self.content_stack.addWidget(self.create_script_to_voice_page())  # 10 - Script to Voice
        self.content_stack.addWidget(self.create_story_video_page())      # 11 - Story Video
        self.content_stack.addWidget(self.create_thumbnail_viewer_page()) # 12 - Thumbnail Viewer

        self.switch_page(0)

        # System tray (for minimize-to-tray when automation is running)

    # ------------------------------------------------------------------
    # Custom title bar
    # ------------------------------------------------------------------

    def create_title_bar(self):
        bar = QWidget()
        bar.setObjectName("title_bar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # App icon
        icon_path = Path(__file__).parent / "assets" / "logo.ico"
        if icon_path.exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path)).scaled(
                18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(18, 18)
            layout.addWidget(icon_label)

        # App name
        name_label = QLabel(APP_NAME)
        name_label.setObjectName("title_bar_label")
        layout.addWidget(name_label)

        # Version
        ver_label = QLabel(f"v{VERSION}")
        ver_label.setObjectName("title_bar_version")
        layout.addWidget(ver_label)

        # Spacer
        layout.addStretch()

        # Window control buttons (using Unicode symbols that render well)
        btn_min = QPushButton("\u2014")  # em dash for minimize
        btn_min.setObjectName("title_bar_btn")
        btn_min.setToolTip("Minimize")
        btn_min.clicked.connect(self.showMinimized)
        layout.addWidget(btn_min)

        self._btn_max = QPushButton("\u25A1")  # white square for maximize
        self._btn_max.setObjectName("title_bar_btn")
        self._btn_max.setToolTip("Maximize")
        self._btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._btn_max)

        btn_close = QPushButton("\u2715")  # multiplication X for close
        btn_close.setObjectName("title_bar_close")
        btn_close.setToolTip("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        return bar

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self._btn_max.setText("\u25A1")  # white square
            self._btn_max.setToolTip("Maximize")
        else:
            self.showMaximized()
            self._btn_max.setText("\u25A3")  # white square with fill (restore icon)
            self._btn_max.setToolTip("Restore")

    # ------------------------------------------------------------------
    # Frameless window drag / resize support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Only start drag when clicking inside the title bar area
            if self.title_bar.geometry().contains(event.pos()):
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            # If maximized, restore first then adjust drag position
            if self.isMaximized():
                self.showNormal()
                # Place window so cursor stays proportionally in the title bar
                self._drag_pos = QPoint(self.width() // 2, 19)
                self._btn_max.setText("□")
                self._btn_max.setToolTip("Maximize")
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.title_bar.geometry().contains(event.pos()):
            self._toggle_maximize()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 25, 0, 20)
        layout.setSpacing(2)

        # Logo section
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(20, 0, 20, 0)
        logo_layout.setSpacing(2)

        logo = QLabel("Nabil Video Studio Pro")
        logo.setObjectName("sidebar_logo")
        logo.setAlignment(Qt.AlignLeft)
        logo_layout.addWidget(logo)

        layout.addWidget(logo_container)
        layout.addSpacing(25)

        # Main section label
        section1 = QLabel("MAIN")
        section1.setObjectName("sidebar_section")
        layout.addWidget(section1)

        # Navigation - Main
        self.nav_buttons = []
        main_nav = [
            ("🔄", "Recreate Video", 0),
            ("🎬", "Create Video", 8),
            ("📺", "Channels", 1),
        ]

        for icon, label, index in main_nav:
            btn = SidebarButton(icon, label)
            btn.page_index = index
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacing(10)

        # Tools section label
        section2 = QLabel("TOOLS")
        section2.setObjectName("sidebar_section")
        layout.addWidget(section2)

        tools_nav = [
            ("🎨", "Thumbnails", 12),
            ("📥", "YouTube DL", 7),
            ("🎤", "Script to Voice", 10),
        ]

        for icon, label, index in tools_nav:
            btn = SidebarButton(icon, label)
            btn.page_index = index
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacing(10)

        # Settings section label
        section3 = QLabel("SETTINGS")
        section3.setObjectName("sidebar_section")
        layout.addWidget(section3)

        settings_nav = [
            ("⚙️", "Settings", 2),
            ("🎤", "Voices", 3),
            ("🔑", "API Keys", 4),
        ]

        for icon, label, index in settings_nav:
            btn = SidebarButton(icon, label)
            btn.page_index = index
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacing(10)

        # Info section label
        section4 = QLabel("INFO")
        section4.setObjectName("sidebar_section")
        layout.addWidget(section4)

        info_nav = [
            ("📋", "Log", 5),
        ]

        for icon, label, index in info_nav:
            btn = SidebarButton(icon, label)
            btn.page_index = index
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # License info container
        license_container = QWidget()
        license_layout = QVBoxLayout(license_container)
        license_layout.setContentsMargins(15, 10, 15, 0)

        license_info = self.license_manager.get_license_info()
        if license_info:
            license_type = license_info.get('license_type', 'Unknown').upper()
            is_trial = license_info.get('is_trial', False)
            days_left = license_info.get('days_left', 0)

            if is_trial and days_left > 0:
                license_text = f"TRIAL ({days_left} days left)"
                bg_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d29922, stop:1 #f0b429)"
            elif is_trial:
                license_text = "TRIAL EXPIRED"
                bg_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #E74C3C)"
            else:
                license_text = license_type
                from ui_styles import get_accent_color, get_accent_gradient
                gs, ge = get_accent_gradient()
                ac = get_accent_color()
                bg_gradient = f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {gs}, stop:1 {ac})"

            license_btn = QPushButton(f"  {license_text}")
            license_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg_gradient};
                    color: white;
                    padding: 12px 16px;
                    border-radius: 10px;
                    font-weight: 600;
                    font-size: 12px;
                    text-align: left;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {bg_gradient};
                    opacity: 0.9;
                }}
            """)
            license_btn.setCursor(Qt.PointingHandCursor)
            license_btn.setToolTip("Click to view subscription details")
            license_btn.clicked.connect(self.show_subscription_dialog)
            license_layout.addWidget(license_btn)
        else:
            activate_btn = QPushButton("  Activate License")
            activate_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #E74C3C);
                    color: white;
                    padding: 12px 16px;
                    border-radius: 10px;
                    font-weight: 600;
                    font-size: 12px;
                    text-align: left;
                    border: none;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #C0392B);
                }
            """)
            activate_btn.setCursor(Qt.PointingHandCursor)
            activate_btn.clicked.connect(self.show_license_activation)
            license_layout.addWidget(activate_btn)

        layout.addWidget(license_container)

        return sidebar

    def show_subscription_dialog(self):
        """Show the subscription details dialog"""
        dialog = SubscriptionDialog(self)
        dialog.exec_()

    def show_license_activation(self):
        """Show license activation dialog"""
        dialog = LicenseActivationDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "Success", "License activated! Please restart the application.")
            self.close()

    def switch_page(self, index):
        self.content_stack.setCurrentIndex(index)
        # Use stored page_index to match buttons correctly
        for btn in self.nav_buttons:
            btn.set_active(getattr(btn, 'page_index', -1) == index)

    # ========================================================================
    # PROJECT PAGE (Recreate Video)
    # ========================================================================

    def create_project_page(self):
        """Recreate Video Page - Modern Minimal Design"""
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        # ============ HEADER ============
        header = QHBoxLayout()
        header.setSpacing(16)

        title = QLabel("Recreate Video")
        title.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 600; letter-spacing: -0.5px;")
        header.addWidget(title)

        header.addStretch()

        self.rv_status_label = QLabel("Ready")
        self.rv_status_label.setStyleSheet("""
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 6px 16px;
            border-radius: 16px;
            font-size: 12px;
            font-weight: 500;
        """)
        header.addWidget(self.rv_status_label)

        layout.addLayout(header)
        layout.addSpacing(24)

        # ============ MAIN CONTENT SCROLL ============
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; margin: 4px 0; }
            QScrollBar::handle:vertical { background: #3a3a3a; border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #3a3d45; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(20)

        # ============ CHANNELS SECTION ============
        channels_card = QFrame()
        channels_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        channels_layout = QVBoxLayout(channels_card)
        channels_layout.setContentsMargins(20, 16, 20, 16)
        channels_layout.setSpacing(14)

        # Channels header
        ch_header = QHBoxLayout()
        ch_header.setSpacing(12)

        ch_title = QLabel("Channels")
        ch_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        ch_header.addWidget(ch_title)

        # Category filter buttons
        self.category_buttons_widget = QWidget()
        self.category_buttons_widget.setStyleSheet("background: transparent;")
        self.category_buttons_layout = QHBoxLayout(self.category_buttons_widget)
        self.category_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.category_buttons_layout.setSpacing(6)
        self.category_buttons = {}
        self.selected_category = "ALL"
        self.selected_profile_names = set()
        self.refresh_category_buttons()
        ch_header.addWidget(self.category_buttons_widget)

        ch_header.addStretch()

        # All/None buttons
        btn_all = QPushButton("Select All")
        btn_all.setFixedHeight(32)
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_all.clicked.connect(self.select_all_profiles)
        ch_header.addWidget(btn_all)

        btn_none = QPushButton("Clear")
        btn_none.setFixedHeight(32)
        btn_none.setCursor(Qt.PointingHandCursor)
        btn_none.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
        """)
        btn_none.clicked.connect(self.select_no_profiles)
        ch_header.addWidget(btn_none)

        channels_layout.addLayout(ch_header)

        # Channel chips container
        self.profile_checkboxes_container = QWidget()
        self.profile_checkboxes_container.setStyleSheet("background: transparent;")
        self.profile_checkboxes_layout = QHBoxLayout(self.profile_checkboxes_container)
        self.profile_checkboxes_layout.setContentsMargins(0, 4, 0, 0)
        self.profile_checkboxes_layout.setSpacing(8)
        self.profile_checkboxes_layout.setAlignment(Qt.AlignLeft)
        self.profile_checkboxes = {}
        self.update_profile_checkboxes()
        channels_layout.addWidget(self.profile_checkboxes_container)

        content_layout.addWidget(channels_card)

        # ============ FOLDERS SECTION ============
        folders_card = QFrame()
        folders_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        folders_layout = QVBoxLayout(folders_card)
        folders_layout.setContentsMargins(20, 16, 20, 16)
        folders_layout.setSpacing(16)

        # Input folders header
        input_header = QHBoxLayout()
        input_header.setSpacing(12)

        input_title = QLabel("Input Folders")
        input_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        input_header.addWidget(input_title)

        input_header.addStretch()

        btn_add = QPushButton("+ Add Folder")
        btn_add.setFixedHeight(32)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_add.clicked.connect(self.add_folder_input)
        input_header.addWidget(btn_add)

        self.btn_add_from_cat = QPushButton("+ From Category")
        self.btn_add_from_cat.setFixedHeight(32)
        self.btn_add_from_cat.setCursor(Qt.PointingHandCursor)
        self.btn_add_from_cat.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
        """)
        self.btn_add_from_cat.clicked.connect(self.show_category_menu)
        input_header.addWidget(self.btn_add_from_cat)

        folders_layout.addLayout(input_header)

        # Input folders list
        self.multi_folder_container = QWidget()
        self.multi_folder_container.setStyleSheet("background: transparent;")
        self.multi_folder_layout = QVBoxLayout(self.multi_folder_container)
        self.multi_folder_layout.setContentsMargins(0, 0, 0, 0)
        self.multi_folder_layout.setSpacing(8)
        self.multi_folder_list = []
        self.cb_enable_custom_settings = QCheckBox()
        self.cb_enable_custom_settings.setChecked(False)
        self.cb_enable_custom_settings.setVisible(False)
        folders_layout.addWidget(self.multi_folder_container)

        # Spacer between sections
        folders_layout.addSpacing(10)

        # Output folder
        output_header = QLabel("Output Folder")
        output_header.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        folders_layout.addWidget(output_header)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)

        self.output_line_edit = QLineEdit()
        self.output_line_edit.setPlaceholderText("Select output folder...")
        self.output_line_edit.setFixedHeight(42)
        self.output_line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        output_row.addWidget(self.output_line_edit)

        btn_browse_out = QPushButton("Browse")
        btn_browse_out.setObjectName("btn_browse")
        btn_browse_out.setFixedSize(90, 42)
        btn_browse_out.setCursor(Qt.PointingHandCursor)
        btn_browse_out.clicked.connect(self._browse_output_folder)
        output_row.addWidget(btn_browse_out)

        btn_clean_out = QPushButton("Clean")
        btn_clean_out.setFixedSize(90, 42)
        btn_clean_out.setCursor(Qt.PointingHandCursor)
        btn_clean_out.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #b91c1c; }
        """)
        btn_clean_out.clicked.connect(self._manual_clean_output_folder)
        output_row.addWidget(btn_clean_out)

        # Clean All button - cleans both input and output
        btn_clean_all = QPushButton("Clean All")
        btn_clean_all.setFixedSize(100, 42)
        btn_clean_all.setCursor(Qt.PointingHandCursor)
        btn_clean_all.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ea580c);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #c2410c);
            }
        """)
        btn_clean_all.setToolTip("Clean ALL files from both Input and Output folders")
        btn_clean_all.clicked.connect(self._clean_all_folders)
        output_row.addWidget(btn_clean_all)

        folders_layout.addLayout(output_row)
        content_layout.addWidget(folders_card)

        # ============ OPTIONS SECTION ============
        options_card = QFrame()
        options_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(20, 16, 20, 16)
        options_layout.setSpacing(16)

        options_title = QLabel("Options")
        options_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        options_layout.addWidget(options_title)

        saved_opts = self.config_manager.config.get('quick_options', {})

        # Options toggles row
        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(10)

        self.cb_clean_output = self._create_toggle_chip("Clean", saved_opts.get('clean_output', False))
        self.cb_clean_output.stateChanged.connect(self._save_quick_options)
        toggles_row.addWidget(self.cb_clean_output)

        self.cb_parallel = self._create_toggle_chip("Parallel", saved_opts.get('parallel', True))
        self.cb_parallel.stateChanged.connect(self._save_quick_options)
        toggles_row.addWidget(self.cb_parallel)

        self.cb_manual_crop = self._create_toggle_chip("Crop", saved_opts.get('manual_crop', True))
        self.cb_manual_crop.stateChanged.connect(self._save_quick_options)
        toggles_row.addWidget(self.cb_manual_crop)

        self.cb_music = self._create_toggle_chip("Music", saved_opts.get('music', True))
        self.cb_music.stateChanged.connect(self._save_quick_options)
        toggles_row.addWidget(self.cb_music)

        self.cb_logo = self._create_toggle_chip("Logo", saved_opts.get('logo', False))
        self.cb_logo.stateChanged.connect(self._save_quick_options)
        toggles_row.addWidget(self.cb_logo)

        self.cb_animations = self._create_toggle_chip("Anim", saved_opts.get('animations', True))
        self.cb_animations.stateChanged.connect(self._save_quick_options)
        toggles_row.addWidget(self.cb_animations)

        toggles_row.addStretch()

        # Step selector
        step_container = QHBoxLayout()
        step_container.setSpacing(8)

        step_label = QLabel("Start Step")
        step_label.setStyleSheet("color: #888888; font-size: 13px;")
        step_container.addWidget(step_label)

        self.combo_start_step = QComboBox()
        self.combo_start_step.addItem("Auto", -1)
        for i in range(11):
            self.combo_start_step.addItem(f"{i}", i)
        self.combo_start_step.setFixedSize(75, 34)
        self.combo_start_step.setStyleSheet(f"""
            QComboBox {{
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 0 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{ background: #3a3a3a; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ image: none; }}
            QComboBox QAbstractItemView {{
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #e0e0e0;
                selection-background-color: {_gradient()[0]};
            }}
        """)
        step_container.addWidget(self.combo_start_step)
        toggles_row.addLayout(step_container)

        options_layout.addLayout(toggles_row)

        # B-roll row
        broll_row = QHBoxLayout()
        broll_row.setSpacing(10)

        self.cb_global_broll = self._create_toggle_chip("Global B-roll", saved_opts.get('use_global_broll', False))
        self.cb_global_broll.stateChanged.connect(self._save_quick_options)
        self.cb_global_broll.stateChanged.connect(self._toggle_global_broll_path)
        broll_row.addWidget(self.cb_global_broll)

        self.global_broll_path = QLineEdit()
        self.global_broll_path.setPlaceholderText("B-roll folder path...")
        self.global_broll_path.setText(saved_opts.get('global_broll_folder', ''))
        self.global_broll_path.setFixedHeight(34)
        self.global_broll_path.textChanged.connect(self._save_quick_options)
        self.global_broll_path.setEnabled(saved_opts.get('use_global_broll', False))
        self.global_broll_path.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:disabled {{ color: #555555; background: #252525; }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        broll_row.addWidget(self.global_broll_path, 1)

        self.btn_browse_global_broll = QPushButton("...")
        self.btn_browse_global_broll.setFixedSize(34, 34)
        self.btn_browse_global_broll.setCursor(Qt.PointingHandCursor)
        self.btn_browse_global_broll.clicked.connect(self._browse_global_broll)
        self.btn_browse_global_broll.setEnabled(saved_opts.get('use_global_broll', False))
        self.btn_browse_global_broll.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #888888;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
            QPushButton:disabled { background: #252525; color: #555555; }
        """)
        broll_row.addWidget(self.btn_browse_global_broll)

        options_layout.addLayout(broll_row)

        # Thumbnail Mode row
        thumb_mode_row = QHBoxLayout()
        thumb_mode_row.setSpacing(10)

        thumb_mode_label = QLabel("Thumbnail Mode")
        thumb_mode_label.setStyleSheet("color: #888888; font-size: 13px;")
        thumb_mode_row.addWidget(thumb_mode_label)

        # Get saved mode (default to title)
        rv_thumb_saved = saved_opts.get('rv_thumb_mode', 'title')

        # OFF button - disable thumbnail generation
        self.rv_thumb_mode_off = QPushButton("OFF")
        self.rv_thumb_mode_off.setCheckable(True)
        self.rv_thumb_mode_off.setChecked(rv_thumb_saved == 'off')
        self.rv_thumb_mode_off.setFixedHeight(32)
        self.rv_thumb_mode_off.setCursor(Qt.PointingHandCursor)
        self.rv_thumb_mode_off.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
            QPushButton:checked { background: #ef4444; color: #ffffff; }
        """)
        self.rv_thumb_mode_off.clicked.connect(lambda: self._rv_set_thumb_mode("off"))
        thumb_mode_row.addWidget(self.rv_thumb_mode_off)

        # Title mode button (DEFAULT)
        self.rv_thumb_mode_title = QPushButton("Title")
        self.rv_thumb_mode_title.setCheckable(True)
        self.rv_thumb_mode_title.setChecked(rv_thumb_saved == 'title')
        self.rv_thumb_mode_title.setFixedHeight(32)
        self.rv_thumb_mode_title.setCursor(Qt.PointingHandCursor)
        self.rv_thumb_mode_title.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
            QPushButton:checked { background: #f59e0b; color: #000; }
        """)
        self.rv_thumb_mode_title.clicked.connect(lambda: self._rv_set_thumb_mode("title"))
        thumb_mode_row.addWidget(self.rv_thumb_mode_title)

        # Script mode button
        self.rv_thumb_mode_script = QPushButton("Script")
        self.rv_thumb_mode_script.setCheckable(True)
        self.rv_thumb_mode_script.setChecked(rv_thumb_saved == 'script')
        self.rv_thumb_mode_script.setFixedHeight(32)
        self.rv_thumb_mode_script.setCursor(Qt.PointingHandCursor)
        self.rv_thumb_mode_script.setStyleSheet(f"""
            QPushButton {{
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: #3a3a3a; color: #ffffff; }}
            QPushButton:checked {{ background: {_gradient()[0]}; color: #ffffff; }}
        """)
        self.rv_thumb_mode_script.clicked.connect(lambda: self._rv_set_thumb_mode("script"))
        thumb_mode_row.addWidget(self.rv_thumb_mode_script)

        thumb_mode_row.addStretch()
        options_layout.addLayout(thumb_mode_row)

        content_layout.addWidget(options_card)

        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Hidden compatibility widgets
        self.cb_folder_name = QCheckBox()
        self.cb_folder_name.setChecked(True)
        self.cb_folder_name.setVisible(False)
        self.cb_voiceover_broll = QCheckBox()
        self.cb_voiceover_broll.setChecked(True)
        self.cb_voiceover_broll.setVisible(False)
        self.cb_custom_broll = QCheckBox()
        self.cb_custom_broll.setChecked(False)
        self.cb_custom_broll.setVisible(False)
        self.broll_folder_widget = QWidget()
        self.broll_folder_widget.setVisible(False)
        self.broll_folder_edit = QLineEdit()
        self.broll_folder_edit.setVisible(False)

        # ============ BOTTOM ACTION BAR ============
        layout.addSpacing(16)

        action_bar = QFrame()
        action_bar.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(20, 14, 20, 14)
        action_layout.setSpacing(16)

        self.status_label = QLabel("Ready to process")
        self.status_label.setStyleSheet("color: #888888; font-size: 13px;")
        action_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setMinimumWidth(180)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #2a2a2a;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                border-radius: 3px;
            }}
        """)
        action_layout.addWidget(self.progress_bar)

        action_layout.addStretch()

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedSize(90, 42)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_pipeline)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #ef4444; }
            QPushButton:disabled { background: #2a2a2a; color: #555555; }
        """)
        action_layout.addWidget(self.btn_stop)

        self.btn_run = QPushButton("Start Processing")
        self.btn_run.setFixedSize(150, 42)
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self.run_pipeline)
        self.btn_run.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_gradient()[0]});
            }}
            QPushButton:disabled {{ background: #2a2a2a; color: #555555; }}
        """)
        action_layout.addWidget(self.btn_run)

        layout.addWidget(action_bar)

        return page

    def _create_toggle_chip(self, text, checked=False):
        """Create a modern toggle chip"""
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setCursor(Qt.PointingHandCursor)
        cb.stateChanged.connect(lambda state: self._update_toggle_chip(cb))
        self._update_toggle_chip(cb)
        return cb

    def _update_toggle_chip(self, checkbox):
        """Update toggle chip style based on state"""
        if checkbox.isChecked():
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                    background: {_gradient()[0]};
                    border-radius: 8px;
                }}
                QCheckBox:hover {{ background: {_gradient()[1]}; }}
                QCheckBox::indicator {{ width: 0; height: 0; }}
            """)
        else:
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #888888;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 8px 16px;
                    background: #2a2a2a;
                    border-radius: 8px;
                }
                QCheckBox:hover { color: #ffffff; background: #3a3a3a; }
                QCheckBox::indicator { width: 0; height: 0; }
            """)

    # Keep old method names for compatibility
    def _create_simple_toggle(self, text, checked=False):
        return self._create_toggle_chip(text, checked)

    def _update_simple_toggle(self, checkbox):
        self._update_toggle_chip(checkbox)

    # ========================================================================
    # CHANNELS PAGE
    # ========================================================================

    def create_channels_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header row with title and category button
        header_row = QHBoxLayout()

        header_container = QWidget()
        header_vlayout = QVBoxLayout(header_container)
        header_vlayout.setContentsMargins(0, 0, 0, 0)
        header_vlayout.setSpacing(5)

        header = QLabel("Channel Management")
        header.setObjectName("page_title")
        header_vlayout.addWidget(header)

        subtitle = QLabel("Create and manage your YouTube channels/profiles")
        subtitle.setObjectName("subtitle")
        header_vlayout.addWidget(subtitle)

        header_row.addWidget(header_container)
        header_row.addStretch()

        btn_categories = QPushButton("  Manage Categories")
        btn_categories.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                color: white;
                font-weight: 600;
                padding: 12px 20px;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_accent()}, stop:1 #79b8ff);
            }}
        """)
        btn_categories.clicked.connect(self.open_category_manager)
        header_row.addWidget(btn_categories)
        layout.addLayout(header_row)

        # Category filter tabs
        self.channel_filter_category = "ALL"
        self.channel_category_buttons = {}

        filter_container = QFrame()
        filter_container.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: none;
                border-radius: 10px;
            }
        """)
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(8)

        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #888888; font-size: 13px; font-weight: 500; border: none; background: transparent;")
        filter_layout.addWidget(filter_label)

        self.channel_filter_buttons_layout = QHBoxLayout()
        self.channel_filter_buttons_layout.setSpacing(6)
        filter_layout.addLayout(self.channel_filter_buttons_layout)

        filter_layout.addStretch()
        layout.addWidget(filter_container)

        # Initialize filter buttons
        self.refresh_channel_filter_buttons()

        # Channel grid with scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                border-radius: 12px;
                background-color: #1a1a1a;
            }
        """)

        self.channel_list_container = QWidget()
        self.channel_grid_layout = QGridLayout(self.channel_list_container)
        self.channel_grid_layout.setContentsMargins(20, 20, 20, 20)
        self.channel_grid_layout.setSpacing(15)
        self.channel_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.channel_list_container)
        layout.addWidget(scroll, 1)

        self.update_channel_list()

        # Bottom action bar
        btn_bar = QFrame()
        btn_bar.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        btn_bar.setFixedHeight(70)
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(20, 15, 20, 15)

        btn_add = QPushButton("+ Add New Channel")
        btn_add.setMinimumWidth(180)
        btn_add.setMinimumHeight(44)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 12px 24px;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_accent()});
            }}
        """)
        btn_add.clicked.connect(self.add_channel)
        btn_layout.addWidget(btn_add)

        btn_layout.addStretch()
        layout.addWidget(btn_bar)

        return page

    # ========================================================================
    # SETTINGS PAGE
    # ========================================================================

    def create_settings_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(5)

        header = QLabel("Settings")
        header.setObjectName("page_title")
        header_layout.addWidget(header)

        subtitle = QLabel("Configure application settings and preferences")
        subtitle.setObjectName("subtitle")
        header_layout.addWidget(subtitle)

        layout.addWidget(header_container)

        # Use existing SettingsEditor
        self.settings_editor = SettingsEditor(self.config_manager)
        self.settings_editor.settingsChanged.connect(self.on_settings_changed)
        layout.addWidget(self.settings_editor)

        return page

    # ========================================================================
    # VOICES PAGE
    # ========================================================================

    def create_voices_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(5)

        header = QLabel("Voice Management")
        header.setObjectName("page_title")
        header_layout.addWidget(header)

        subtitle = QLabel("Configure AI voices for your videos")
        subtitle.setObjectName("subtitle")
        header_layout.addWidget(subtitle)

        layout.addWidget(header_container)

        # Voice list
        self.voice_list = QListWidget()
        self.voice_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #1a1a1a;
                border: none;
                border-radius: 12px;
                padding: 10px;
            }}
            QListWidget::item {{
                padding: 14px 16px;
                border-radius: 8px;
                margin: 3px 0;
            }}
            QListWidget::item:selected {{
                background-color: {_gradient()[0]};
            }}
            QListWidget::item:hover:!selected {{
                background-color: #252525;
            }}
        """)
        self.update_voice_list()
        layout.addWidget(self.voice_list, 1)

        # Bottom action bar
        btn_bar = QFrame()
        btn_bar.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        btn_bar.setFixedHeight(70)
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(20, 15, 20, 15)
        btn_layout.setSpacing(12)

        btn_add = QPushButton("  Add Voice")
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                color: white;
                font-weight: 600;
                padding: 12px 24px;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_accent()});
            }}
        """)
        btn_add.clicked.connect(self.add_voice)
        btn_layout.addWidget(btn_add)

        btn_edit = QPushButton("  Edit")
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                color: white;
                font-weight: 600;
                padding: 12px 24px;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_accent()}, stop:1 #79b8ff);
            }}
        """)
        btn_edit.clicked.connect(self.edit_voice)
        btn_layout.addWidget(btn_edit)

        btn_delete = QPushButton("  Delete")
        btn_delete.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #E74C3C);
                color: white;
                font-weight: 600;
                padding: 12px 24px;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #C0392B);
            }
        """)
        btn_delete.clicked.connect(self.delete_voice)
        btn_layout.addWidget(btn_delete)

        btn_layout.addStretch()
        layout.addWidget(btn_bar)

        return page

    # ========================================================================
    # API KEYS PAGE
    # ========================================================================

    def create_api_keys_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(5)

        header = QLabel("API Keys")
        header.setObjectName("page_title")
        header_layout.addWidget(header)

        subtitle = QLabel("Manage your AI service API keys")
        subtitle.setObjectName("subtitle")
        header_layout.addWidget(subtitle)

        layout.addWidget(header_container)

        # Use existing APIKeysManager
        self.api_manager = APIKeysManager(api_keys_file=str(API_KEYS_FILE))
        self.api_manager.apiKeysChanged.connect(self.on_api_keys_changed)
        layout.addWidget(self.api_manager)

        return page

    # ========================================================================
    # LOG PAGE
    # ========================================================================

    def create_log_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header with Run/Stop buttons
        header_layout = QHBoxLayout()

        header_container = QWidget()
        header_vlayout = QVBoxLayout(header_container)
        header_vlayout.setContentsMargins(0, 0, 0, 0)
        header_vlayout.setSpacing(5)

        header = QLabel("Activity Log")
        header.setObjectName("page_title")
        header_vlayout.addWidget(header)

        subtitle = QLabel("View real-time processing logs")
        subtitle.setObjectName("subtitle")
        header_vlayout.addWidget(subtitle)

        header_layout.addWidget(header_container)
        header_layout.addStretch()

        # Run Recreate Video button
        self.log_run_btn = QPushButton("  Recreate")
        self.log_run_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_accent()});
            }}
            QPushButton:disabled {{ background: #2a2a2a; color: #555555; }}
        """)
        self.log_run_btn.clicked.connect(self.run_pipeline)
        header_layout.addWidget(self.log_run_btn)

        # Run Create Video button
        self.log_cc_run_btn = QPushButton("  Create")
        self.log_cc_run_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_accent()}, stop:1 #79b8ff);
            }}
            QPushButton:disabled {{ background: #2a2a2a; color: #555555; }}
        """)
        self.log_cc_run_btn.clicked.connect(self.safe_run_content_creator)
        header_layout.addWidget(self.log_cc_run_btn)

        # Stop button
        self.log_stop_btn = QPushButton("  Stop")
        self.log_stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #E74C3C);
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #C0392B);
            }
            QPushButton:disabled { background: #2a2a2a; color: #555555; }
        """)
        self.log_stop_btn.clicked.connect(self.stop_pipeline)
        self.log_stop_btn.setEnabled(False)
        header_layout.addWidget(self.log_stop_btn)

        layout.addLayout(header_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: none;
                border-radius: 12px;
                padding: 16px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
                color: #27AE60;
            }
        """)
        layout.addWidget(self.log_output, 1)

        # Bottom bar
        btn_bar = QFrame()
        btn_bar.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: none;
                border-radius: 10px;
            }
        """)
        btn_bar.setFixedHeight(60)
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(16, 12, 16, 12)

        btn_clear = QPushButton("  Clear Log")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e1e4e8;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        btn_clear.clicked.connect(self.log_output.clear)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addWidget(btn_bar)

        return page

    # ========================================================================
    # YOUTUBE DOWNLOADER PAGE
    # ========================================================================

    def create_youtube_page(self):
        """Create YouTube Downloader page"""
        # Create container with correct background
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.youtube_page = YouTubeDownloaderPage(config_manager=self.config_manager, parent=page)
        layout.addWidget(self.youtube_page)
        return page

    # ========================================================================
    # SCRIPT TO VOICE PAGE
    # ========================================================================

    def create_script_to_voice_page(self):
        """Create Script to Voice tool page - generate voiceover from text"""
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ============ HEADER ============
        header_row = QHBoxLayout()

        header = QLabel("Script to Voice")
        header.setStyleSheet("""
            color: #f0f6fc;
            font-size: 22px;
            font-weight: 700;
            padding: 4px 0;
        """)
        header_row.addWidget(header)
        header_row.addStretch()

        self.stv_status_label = QLabel("Ready")
        self.stv_status_label.setStyleSheet(f"""
            background-color: {_gradient()[0]};
            color: white;
            padding: 6px 14px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        """)
        header_row.addWidget(self.stv_status_label)

        layout.addLayout(header_row)

        # ============ CATEGORY BUTTONS ============
        cat_row = QHBoxLayout()
        cat_row.setSpacing(8)

        cat_label = QLabel("Category")
        cat_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 500;")
        cat_label.setFixedWidth(60)
        cat_row.addWidget(cat_label)

        self.stv_cat_buttons_widget = QWidget()
        self.stv_cat_buttons_layout = QHBoxLayout(self.stv_cat_buttons_widget)
        self.stv_cat_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.stv_cat_buttons_layout.setSpacing(6)
        self.stv_category_buttons = {}
        self.stv_selected_category = None
        self._stv_refresh_category_buttons()
        cat_row.addWidget(self.stv_cat_buttons_widget)
        cat_row.addStretch()

        layout.addLayout(cat_row)

        # ============ METHOD TOGGLE (Browser / API) ============
        method_row = QHBoxLayout()
        method_row.setSpacing(8)

        method_label = QLabel("Method")
        method_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 500;")
        method_label.setFixedWidth(60)
        method_row.addWidget(method_label)

        self.stv_browser_btn = QPushButton("  Browser  ")
        self.stv_browser_btn.setCheckable(True)
        self.stv_browser_btn.setChecked(True)
        self.stv_browser_btn.setFixedHeight(34)
        self.stv_browser_btn.setMinimumWidth(100)
        self.stv_browser_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                border: none;
                border-radius: 6px;
                color: white;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:!checked {{
                background: #2a2a2a;
                color: #888888;
                border: none;
            }}
            QPushButton:hover:!checked {{
                background: #3a3a3a;
                border-color: {_gradient()[0]};
            }}
        """)
        self.stv_browser_btn.clicked.connect(lambda: self._stv_set_method(True))
        method_row.addWidget(self.stv_browser_btn)

        self.stv_api_btn = QPushButton("  API  ")
        self.stv_api_btn.setCheckable(True)
        self.stv_api_btn.setFixedHeight(34)
        self.stv_api_btn.setMinimumWidth(80)
        self.stv_api_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8E44AD, stop:1 #9B59B6);
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
                border-color: #8E44AD;
            }
        """)
        self.stv_api_btn.clicked.connect(lambda: self._stv_set_method(False))
        method_row.addWidget(self.stv_api_btn)

        method_row.addStretch()
        layout.addLayout(method_row)

        # ============ SETTINGS ROW: VOICE + OUTPUT + PARALLEL ============
        settings_row = QHBoxLayout()
        settings_row.setSpacing(16)

        # Voice
        voice_widget = QWidget()
        voice_layout = QVBoxLayout(voice_widget)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(4)
        voice_label = QLabel("Voice")
        voice_label.setStyleSheet(f"color: {_accent()}; font-size: 11px; font-weight: 600;")
        voice_layout.addWidget(voice_label)
        self.stv_voice_combo = QComboBox()
        self.stv_voice_combo.setFixedHeight(38)
        self.stv_voice_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid {_accent()};
                border-radius: 8px;
                color: {_accent()};
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ image: none; }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: 1px solid {_accent()};
                color: #e0e0e0;
                selection-background-color: {_accent()};
            }}
        """)
        self._stv_load_voices()
        voice_layout.addWidget(self.stv_voice_combo)
        settings_row.addWidget(voice_widget, 2)

        # Output folder
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(4)
        output_label = QLabel("Output Folder")
        output_label.setStyleSheet("color: #27AE60; font-size: 11px; font-weight: 600;")
        output_layout.addWidget(output_label)
        output_row = QHBoxLayout()
        output_row.setSpacing(6)
        self.stv_output_path = QLineEdit()
        self.stv_output_path.setFixedHeight(38)
        self.stv_output_path.setPlaceholderText("Select folder...")
        self.stv_output_path.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: none;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #27AE60; }
        """)
        btn_browse_output = QPushButton("...")
        btn_browse_output.setFixedSize(38, 38)
        btn_browse_output.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                border: 1px solid #27AE60;
                border-radius: 8px;
                color: #27AE60;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {_gradient()[0]};
                color: white;
            }}
        """)
        btn_browse_output.clicked.connect(self._stv_browse_output)
        output_row.addWidget(self.stv_output_path)
        output_row.addWidget(btn_browse_output)
        output_layout.addLayout(output_row)
        settings_row.addWidget(output_widget, 3)

        # Parallel
        parallel_widget = QWidget()
        parallel_layout = QVBoxLayout(parallel_widget)
        parallel_layout.setContentsMargins(0, 0, 0, 0)
        parallel_layout.setSpacing(4)
        parallel_label = QLabel("Parallel Tabs")
        parallel_label.setStyleSheet(f"color: {_gradient()[1]}; font-size: 11px; font-weight: 600;")
        parallel_layout.addWidget(parallel_label)
        self.stv_tabs_spin = QSpinBox()
        self.stv_tabs_spin.setRange(1, 25)
        self.stv_tabs_spin.setValue(5)
        self.stv_tabs_spin.setFixedHeight(38)
        self.stv_tabs_spin.setFixedWidth(80)
        self.stv_tabs_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #2a2a2a;
                border: 1px solid {_gradient()[1]};
                border-radius: 8px;
                color: {_gradient()[1]};
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: #3a3a3a;
                border: none;
                width: 16px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {_gradient()[1]};
            }}
        """)
        parallel_layout.addWidget(self.stv_tabs_spin)
        settings_row.addWidget(parallel_widget)

        layout.addLayout(settings_row)

        # ============ SCRIPT TEXT AREA (BIG) ============
        script_widget = QWidget()
        script_layout = QVBoxLayout(script_widget)
        script_layout.setContentsMargins(0, 0, 0, 0)
        script_layout.setSpacing(6)

        # Header with input mode toggle
        script_header_row = QHBoxLayout()
        script_label = QLabel("Script Text")
        script_label.setStyleSheet("color: #d2a8ff; font-size: 12px; font-weight: 600;")
        script_header_row.addWidget(script_label)
        script_header_row.addStretch()

        self.stv_paste_btn = QPushButton("  Paste  ")
        self.stv_paste_btn.setCheckable(True)
        self.stv_paste_btn.setChecked(True)
        self.stv_paste_btn.setFixedHeight(28)
        self.stv_paste_btn.setMinimumWidth(70)
        self.stv_paste_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                border: none;
                border-radius: 6px;
                color: white;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:!checked {{
                background: #2a2a2a;
                color: #888888;
                border: none;
            }}
            QPushButton:hover:!checked {{
                background: #3a3a3a;
                border-color: {_gradient()[0]};
            }}
        """)
        self.stv_paste_btn.clicked.connect(lambda: self._stv_set_input_mode(True))
        script_header_row.addWidget(self.stv_paste_btn)

        self.stv_file_btn = QPushButton("  File  ")
        self.stv_file_btn.setCheckable(True)
        self.stv_file_btn.setFixedHeight(28)
        self.stv_file_btn.setMinimumWidth(60)
        self.stv_file_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d29922, stop:1 #e3b341);
                border: none;
                border-radius: 6px;
                color: white;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:!checked {
                background: #2a2a2a;
                color: #888888;
                border: none;
            }
            QPushButton:hover:!checked {
                background: #3a3a3a;
                border-color: #d29922;
            }
        """)
        self.stv_file_btn.clicked.connect(lambda: self._stv_set_input_mode(False))
        script_header_row.addWidget(self.stv_file_btn)

        script_layout.addLayout(script_header_row)

        # Big text area
        self.stv_script_text = QTextEdit()
        self.stv_script_text.setPlaceholderText("Paste your script here...\n\nEach paragraph (separated by empty lines) becomes a separate audio file.\n\nExample:\nWelcome to our channel.\n\nToday we talk about...\n\nDon't forget to subscribe!")
        self.stv_script_text.setStyleSheet("""
            QTextEdit {
                background-color: #252525;
                border: none;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 14px;
                font-size: 13px;
                line-height: 1.6;
            }
            QTextEdit:focus {
                border-color: #d2a8ff;
            }
        """)
        script_layout.addWidget(self.stv_script_text)

        # File selection row (hidden by default)
        self.stv_file_row = QWidget()
        file_row_layout = QHBoxLayout(self.stv_file_row)
        file_row_layout.setContentsMargins(0, 0, 0, 0)
        file_row_layout.setSpacing(6)
        self.stv_file_path = QLineEdit()
        self.stv_file_path.setFixedHeight(38)
        self.stv_file_path.setPlaceholderText("Select a text file (.txt)...")
        self.stv_file_path.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: none;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #d29922; }
        """)
        btn_browse_file = QPushButton("  Browse...  ")
        btn_browse_file.setFixedHeight(38)
        btn_browse_file.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #d29922;
                border-radius: 8px;
                color: #d29922;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #d29922;
                color: white;
            }
        """)
        btn_browse_file.clicked.connect(self._stv_browse_file)
        file_row_layout.addWidget(self.stv_file_path)
        file_row_layout.addWidget(btn_browse_file)
        self.stv_file_row.setVisible(False)
        script_layout.addWidget(self.stv_file_row)

        layout.addWidget(script_widget, 1)  # stretch factor 1 to take remaining space

        # ============ BOTTOM: PROGRESS + GENERATE BUTTON ============
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.stv_progress_label = QLabel("")
        self.stv_progress_label.setStyleSheet("color: #888888; font-size: 12px;")
        bottom_row.addWidget(self.stv_progress_label)

        bottom_row.addStretch()

        # Open Folder button
        self.stv_open_folder_btn = QPushButton("  Open Folder  ")
        self.stv_open_folder_btn.setFixedHeight(42)
        self.stv_open_folder_btn.setMinimumWidth(110)
        self.stv_open_folder_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                border: 2px solid {_accent()};
                border-radius: 8px;
                color: {_accent()};
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {_gradient()[0]};
                color: white;
                border-color: {_gradient()[0]};
            }}
        """)
        self.stv_open_folder_btn.clicked.connect(self._stv_open_folder)
        bottom_row.addWidget(self.stv_open_folder_btn)

        # Stop button (hidden by default)
        self.stv_stop_btn = QPushButton("  Stop  ")
        self.stv_stop_btn.setFixedHeight(42)
        self.stv_stop_btn.setMinimumWidth(80)
        self.stv_stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #E74C3C);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E74C3C, stop:1 #C0392B);
            }
        """)
        self.stv_stop_btn.clicked.connect(self._stv_stop_generation)
        self.stv_stop_btn.setVisible(False)
        bottom_row.addWidget(self.stv_stop_btn)

        self.stv_generate_btn = QPushButton("  Generate Voiceover  ")
        self.stv_generate_btn.setFixedHeight(42)
        self.stv_generate_btn.setMinimumWidth(170)
        self.stv_generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 700;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_accent()});
            }}
            QPushButton:disabled {{
                background: #2a2a2a;
                color: #555555;
            }}
        """)
        self.stv_generate_btn.clicked.connect(self._stv_generate_voiceover)
        bottom_row.addWidget(self.stv_generate_btn)

        layout.addLayout(bottom_row)

        # Track if generation is running
        self.stv_is_running = False

        return page

    def _stv_toggle_input_mode(self, paste_mode):
        """Toggle between paste and file input modes"""
        self.stv_script_text.setVisible(paste_mode)
        self.stv_file_row.setVisible(not paste_mode)

    def _stv_set_input_mode(self, paste_mode):
        """Set input mode (Paste or File) using toggle buttons"""
        self.stv_paste_btn.setChecked(paste_mode)
        self.stv_file_btn.setChecked(not paste_mode)
        self.stv_script_text.setVisible(paste_mode)
        self.stv_file_row.setVisible(not paste_mode)

    def _stv_set_method(self, use_browser):
        """Set method (Browser or API) using toggle buttons"""
        self.stv_browser_btn.setChecked(use_browser)
        self.stv_api_btn.setChecked(not use_browser)

    def _stv_stop_generation(self):
        """Stop the voiceover generation, kill browser, and reset UI"""
        self.stv_is_running = False
        self.stv_generate_btn.setEnabled(True)
        self.stv_stop_btn.setVisible(False)
        self.stv_progress_label.setText("Stopped by user")
        print("🛑 Generation stopped by user")

        # Kill any running browser/chromium processes started by playwright
        try:
            import subprocess
            # Kill chromium processes (playwright browser)
            subprocess.run(['taskkill', '/F', '/IM', 'chromium.exe'],
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print("Browser processes killed")
        except Exception as e:
            print(f"Could not kill browser: {e}")

    def _stv_browse_file(self):
        """Browse for script text file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Script File", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.stv_file_path.setText(file_path)

    def _stv_browse_output(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.stv_output_path.setText(folder)

    def _stv_open_folder(self):
        """Open the output folder"""
        import os
        folder = self.stv_output_path.text()
        if folder and Path(folder).exists():
            os.startfile(folder)

    def _stv_load_voices(self):
        """Load voices from voices config into combo box"""
        self.stv_voice_combo.clear()

        # Load from voices (the correct source)
        voices = self.config_manager.get_voices()
        if voices:
            for name, voice_data in voices.items():
                if isinstance(voice_data, dict):
                    voice_url = voice_data.get('url', '')
                else:
                    voice_url = str(voice_data)
                if voice_url:
                    self.stv_voice_combo.addItem(f"{name}", voice_url)

        if self.stv_voice_combo.count() == 0:
            self.stv_voice_combo.addItem("No voices - add in Voices page first", "")

    def _stv_refresh_category_buttons(self):
        """Create category filter buttons (like channel page)"""
        # Clear existing buttons
        for i in reversed(range(self.stv_cat_buttons_layout.count())):
            widget = self.stv_cat_buttons_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.stv_category_buttons.clear()

        categories = self.config_manager.get_categories()

        for cat_name in categories:
            btn = QPushButton(f"  {cat_name}  ")
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(80)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    border: none;
                    border-radius: 6px;
                    color: #888888;
                    padding: 4px 14px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:checked {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_gradient()[1]});
                    border-color: {_gradient()[0]};
                    color: white;
                }}
                QPushButton:hover:!checked {{
                    border-color: #27AE60;
                    color: #27AE60;
                }}
            """)
            btn.clicked.connect(lambda checked, name=cat_name: self._stv_select_category(name))
            self.stv_cat_buttons_layout.addWidget(btn)
            self.stv_category_buttons[cat_name] = btn

        self.stv_cat_buttons_layout.addStretch()

    def _stv_select_category(self, cat_name):
        """Select a category and fill paths"""
        # Update button states
        for name, btn in self.stv_category_buttons.items():
            btn.setChecked(name == cat_name)

        self.stv_selected_category = cat_name

        # Get category data and fill paths
        cat_data = self.config_manager.get_category_data(cat_name)

        # Set input path (for file mode)
        input_path = cat_data.get("input_path", "")
        if input_path:
            self.stv_file_path.setText(input_path)

        # Set output path with /voiceover subfolder
        output_path = cat_data.get("output_path", "")
        if output_path:
            voiceover_path = str(Path(output_path) / "voiceover")
            self.stv_output_path.setText(voiceover_path)

    def _stv_generate_voiceover(self):
        """Generate voiceover from script"""
        # Get script text - check if paste mode is active (button checked)
        paste_mode = self.stv_paste_btn.isChecked()
        if paste_mode:
            script_text = self.stv_script_text.toPlainText().strip()
            if not script_text:
                QMessageBox.warning(self, "No Script", "Please enter your script text.")
                return
        else:
            file_path = self.stv_file_path.text().strip()
            if not file_path or not Path(file_path).exists():
                QMessageBox.warning(self, "No File", "Please select a valid text file.")
                return
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    script_text = f.read().strip()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read file: {e}")
                return

        # Get output folder
        output_folder = self.stv_output_path.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "No Output", "Please select an output folder.")
            return

        # Get voice URL
        voice_url = self.stv_voice_combo.currentData()
        if not voice_url:
            QMessageBox.warning(self, "No Voice", "Please select a voice. Add voices in the Voices page first.")
            return

        # Get number of tabs/parallel
        num_tabs = self.stv_tabs_spin.value()

        # Check method (Browser or API) - API button checked means use API
        use_api = self.stv_api_btn.isChecked()

        # Create temp script file
        os.makedirs(output_folder, exist_ok=True)
        temp_script_path = Path(output_folder) / "_temp_script.txt"

        # Split by paragraphs (empty lines) and format for voiceover script
        paragraphs = [p.strip() for p in script_text.split('\n\n') if p.strip()]
        formatted_script = '\n\n\n'.join(paragraphs)  # Triple newline for paragraph separator

        try:
            with open(temp_script_path, 'w', encoding='utf-8') as f:
                f.write(formatted_script)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create temp script: {e}")
            return

        # Disable generate button, show stop button
        self.stv_generate_btn.setEnabled(False)
        self.stv_stop_btn.setVisible(True)
        self.stv_is_running = True
        method_name = "API" if use_api else "Browser"
        self.stv_progress_label.setText(f"Generating {len(paragraphs)} files via {method_name}...")

        # Run voiceover generation in background
        self._run_script_to_voice(str(temp_script_path), output_folder, num_tabs, voice_url, use_api)

    def _run_script_to_voice(self, script_path, output_folder, num_tabs, voice_url, use_api=False):
        """Run the voiceover generation using VoiceoverWorker thread"""
        # Update status badge to running
        self.stv_status_label.setText("Running...")
        self.stv_status_label.setStyleSheet(f"""
            background-color: {_gradient()[0]};
            color: white;
            padding: 6px 14px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        """)

        # Create and start worker thread
        self.voiceover_worker = VoiceoverWorker(
            script_path, output_folder, voice_url, num_tabs, use_api
        )
        self.voiceover_worker.progress.connect(self._stv_on_progress)
        self.voiceover_worker.finished.connect(self._stv_on_finished)
        self.voiceover_worker.start()

    def _stv_on_progress(self, message):
        """Handle progress updates from voiceover worker"""
        self.stv_progress_label.setText(message)

    def _stv_on_finished(self, success, result):
        """Handle voiceover worker completion"""
        # Re-enable UI
        self.stv_generate_btn.setEnabled(True)
        self.stv_stop_btn.setVisible(False)
        self.stv_is_running = False

        if success:
            # Update to done state
            self.stv_progress_label.setText("Done! All voiceovers generated.")
            self.stv_status_label.setText("Done")
            self.stv_status_label.setStyleSheet(f"""
                background-color: {_gradient()[0]};
                color: white;
                padding: 6px 14px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
            """)
            QMessageBox.information(self, "Complete", f"Voiceover generation complete!\n\nOutput folder:\n{result}")
        else:
            # Show error
            self.stv_progress_label.setText(f"Error: {result[:50]}")
            self.stv_status_label.setText("Error")
            self.stv_status_label.setStyleSheet("""
                background-color: #E74C3C;
                color: white;
                padding: 6px 14px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
            """)
            QMessageBox.warning(self, "Error", f"Voiceover generation failed:\n{result}")

    # ========================================================================
    # STORY VIDEO PAGE (Like Recreate Video but for voiceover-only)
    # ========================================================================

    def create_story_video_page(self):
        """Story Video Page - For voiceover-only videos (no interviews)"""
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        # ============ HEADER ============
        header = QHBoxLayout()
        header.setSpacing(16)

        title = QLabel("Story Video")
        title.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 600; letter-spacing: -0.5px;")
        header.addWidget(title)

        header.addStretch()

        self.sv_status_label = QLabel("Ready")
        self.sv_status_label.setStyleSheet("""
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 6px 16px;
            border-radius: 16px;
            font-size: 12px;
            font-weight: 500;
        """)
        header.addWidget(self.sv_status_label)

        layout.addLayout(header)
        layout.addSpacing(24)

        # ============ MAIN CONTENT SCROLL ============
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; margin: 4px 0; }
            QScrollBar::handle:vertical { background: #3a3a3a; border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #3a3d45; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(20)

        # ============ CHANNELS SECTION ============
        channels_card = QFrame()
        channels_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        channels_layout = QVBoxLayout(channels_card)
        channels_layout.setContentsMargins(20, 16, 20, 16)
        channels_layout.setSpacing(14)

        # Channels header
        ch_header = QHBoxLayout()
        ch_header.setSpacing(12)

        ch_title = QLabel("Channels")
        ch_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        ch_header.addWidget(ch_title)

        # Category filter buttons for Story Video
        self.sv_category_buttons_widget = QWidget()
        self.sv_category_buttons_widget.setStyleSheet("background: transparent;")
        self.sv_category_buttons_layout = QHBoxLayout(self.sv_category_buttons_widget)
        self.sv_category_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.sv_category_buttons_layout.setSpacing(6)
        self.sv_category_buttons = {}
        self.sv_selected_category = "ALL"
        self.sv_selected_profile_names = set()
        self._sv_refresh_category_buttons()
        ch_header.addWidget(self.sv_category_buttons_widget)

        ch_header.addStretch()

        # All/None buttons
        btn_all = QPushButton("Select All")
        btn_all.setFixedHeight(32)
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_all.clicked.connect(self._sv_select_all_profiles)
        ch_header.addWidget(btn_all)

        btn_none = QPushButton("Clear")
        btn_none.setFixedHeight(32)
        btn_none.setCursor(Qt.PointingHandCursor)
        btn_none.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
        """)
        btn_none.clicked.connect(self._sv_select_no_profiles)
        ch_header.addWidget(btn_none)

        channels_layout.addLayout(ch_header)

        # Channel chips container
        self.sv_profile_checkboxes_container = QWidget()
        self.sv_profile_checkboxes_container.setStyleSheet("background: transparent;")
        self.sv_profile_checkboxes_layout = QHBoxLayout(self.sv_profile_checkboxes_container)
        self.sv_profile_checkboxes_layout.setContentsMargins(0, 4, 0, 0)
        self.sv_profile_checkboxes_layout.setSpacing(8)
        self.sv_profile_checkboxes_layout.setAlignment(Qt.AlignLeft)
        self.sv_profile_checkboxes = {}
        self._sv_update_profile_checkboxes()
        channels_layout.addWidget(self.sv_profile_checkboxes_container)

        content_layout.addWidget(channels_card)

        # ============ FOLDERS SECTION ============
        folders_card = QFrame()
        folders_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        folders_layout = QVBoxLayout(folders_card)
        folders_layout.setContentsMargins(20, 16, 20, 16)
        folders_layout.setSpacing(16)

        # Input folder header
        input_header = QHBoxLayout()
        input_header.setSpacing(12)

        input_title = QLabel("Input Folders")
        input_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        input_header.addWidget(input_title)

        input_desc = QLabel("(videos with voiceover only)")
        input_desc.setStyleSheet("color: #6e7681; font-size: 12px;")
        input_header.addWidget(input_desc)

        input_header.addStretch()

        # Add folder button
        btn_add_folder = QPushButton("+ Add Folder")
        btn_add_folder.setFixedHeight(32)
        btn_add_folder.setCursor(Qt.PointingHandCursor)
        btn_add_folder.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_add_folder.clicked.connect(self._sv_add_folder_input)
        input_header.addWidget(btn_add_folder)

        folders_layout.addLayout(input_header)

        # Input folders list container
        self.sv_folder_container = QWidget()
        self.sv_folder_container.setStyleSheet("background: transparent;")
        self.sv_folder_layout = QVBoxLayout(self.sv_folder_container)
        self.sv_folder_layout.setContentsMargins(0, 0, 0, 0)
        self.sv_folder_layout.setSpacing(8)
        self.sv_folder_list = []  # List of (row_widget, line_edit) tuples
        folders_layout.addWidget(self.sv_folder_container)

        # Hidden single input edit for compatibility
        self.sv_input_edit = QLineEdit()
        self.sv_input_edit.setVisible(False)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #2a2a2a;")
        folders_layout.addWidget(divider)

        # Output folder
        output_header = QLabel("Output Folder")
        output_header.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        folders_layout.addWidget(output_header)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)

        self.sv_output_edit = QLineEdit()
        self.sv_output_edit.setPlaceholderText("Select output folder...")
        self.sv_output_edit.setFixedHeight(42)
        self.sv_output_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        output_row.addWidget(self.sv_output_edit)

        btn_browse_output = QPushButton("Browse")
        btn_browse_output.setFixedSize(90, 42)
        btn_browse_output.setCursor(Qt.PointingHandCursor)
        btn_browse_output.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_browse_output.clicked.connect(self._sv_browse_output)
        output_row.addWidget(btn_browse_output)

        btn_clean_output = QPushButton("Clean")
        btn_clean_output.setFixedSize(110, 42)
        btn_clean_output.setCursor(Qt.PointingHandCursor)
        btn_clean_output.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #b91c1c; }
        """)
        btn_clean_output.clicked.connect(self._sv_clean_output)
        output_row.addWidget(btn_clean_output)

        folders_layout.addLayout(output_row)

        content_layout.addWidget(folders_card)

        # ============ OPTIONS SECTION ============
        options_card = QFrame()
        options_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(20, 16, 20, 16)
        options_layout.setSpacing(16)

        options_title = QLabel("Options")
        options_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        options_layout.addWidget(options_title)

        # Options toggles row 1
        toggles_row1 = QHBoxLayout()
        toggles_row1.setSpacing(10)

        self.sv_cb_clean = self._create_toggle_chip("Clean", False)
        toggles_row1.addWidget(self.sv_cb_clean)

        self.sv_cb_parallel = self._create_toggle_chip("Parallel", True)
        toggles_row1.addWidget(self.sv_cb_parallel)

        self.sv_cb_music = self._create_toggle_chip("Music", True)
        toggles_row1.addWidget(self.sv_cb_music)

        self.sv_cb_logo = self._create_toggle_chip("Logo", False)
        toggles_row1.addWidget(self.sv_cb_logo)

        toggles_row1.addStretch()

        # Start step selector
        step_container = QHBoxLayout()
        step_container.setSpacing(8)

        step_label = QLabel("Start Step")
        step_label.setStyleSheet("color: #888888; font-size: 13px;")
        step_container.addWidget(step_label)

        self.sv_start_step = QComboBox()
        self.sv_start_step.addItem("Auto", -1)
        for i in range(1, 8):
            self.sv_start_step.addItem(f"{i}", i)
        self.sv_start_step.setFixedSize(75, 34)
        self.sv_start_step.setStyleSheet(f"""
            QComboBox {{
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 0 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{ background: #3a3a3a; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ image: none; }}
            QComboBox QAbstractItemView {{
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #e0e0e0;
                selection-background-color: {_gradient()[0]};
            }}
        """)
        step_container.addWidget(self.sv_start_step)
        toggles_row1.addLayout(step_container)

        options_layout.addLayout(toggles_row1)

        # B-roll row
        broll_row = QHBoxLayout()
        broll_row.setSpacing(10)

        self.sv_cb_global_broll = self._create_toggle_chip("Global B-roll", False)
        self.sv_cb_global_broll.stateChanged.connect(self._sv_toggle_broll_path)
        broll_row.addWidget(self.sv_cb_global_broll)

        self.sv_broll_path = QLineEdit()
        self.sv_broll_path.setPlaceholderText("B-roll folder path...")
        self.sv_broll_path.setFixedHeight(34)
        self.sv_broll_path.setEnabled(False)
        self.sv_broll_path.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:disabled {{ color: #555555; background: #252525; }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        broll_row.addWidget(self.sv_broll_path, 1)

        self.sv_btn_browse_broll = QPushButton("...")
        self.sv_btn_browse_broll.setFixedSize(34, 34)
        self.sv_btn_browse_broll.setCursor(Qt.PointingHandCursor)
        self.sv_btn_browse_broll.clicked.connect(self._sv_browse_broll)
        self.sv_btn_browse_broll.setEnabled(False)
        self.sv_btn_browse_broll.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #888888;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
            QPushButton:disabled { background: #252525; color: #555555; }
        """)
        broll_row.addWidget(self.sv_btn_browse_broll)

        options_layout.addLayout(broll_row)
        content_layout.addWidget(options_card)

        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # ============ BOTTOM ACTION BAR ============
        layout.addSpacing(16)

        action_bar = QFrame()
        action_bar.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(20, 14, 20, 14)
        action_layout.setSpacing(16)

        self.sv_status_text = QLabel("Ready to process")
        self.sv_status_text.setStyleSheet("color: #888888; font-size: 13px;")
        action_layout.addWidget(self.sv_status_text)

        self.sv_progress_bar = QProgressBar()
        self.sv_progress_bar.setValue(0)
        self.sv_progress_bar.setTextVisible(False)
        self.sv_progress_bar.setFixedHeight(6)
        self.sv_progress_bar.setMinimumWidth(180)
        self.sv_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #2a2a2a;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                border-radius: 3px;
            }}
        """)
        action_layout.addWidget(self.sv_progress_bar)

        action_layout.addStretch()

        self.sv_btn_stop = QPushButton("Stop")
        self.sv_btn_stop.setFixedSize(90, 42)
        self.sv_btn_stop.setCursor(Qt.PointingHandCursor)
        self.sv_btn_stop.setEnabled(False)
        self.sv_btn_stop.clicked.connect(self._sv_stop_pipeline)
        self.sv_btn_stop.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #ef4444; }
            QPushButton:disabled { background: #2a2a2a; color: #555555; }
        """)
        action_layout.addWidget(self.sv_btn_stop)

        self.sv_btn_run = QPushButton("Start Processing")
        self.sv_btn_run.setFixedSize(150, 42)
        self.sv_btn_run.setCursor(Qt.PointingHandCursor)
        self.sv_btn_run.clicked.connect(self._sv_run_pipeline)
        self.sv_btn_run.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_gradient()[0]});
            }}
            QPushButton:disabled {{ background: #2a2a2a; color: #555555; }}
        """)
        action_layout.addWidget(self.sv_btn_run)

        layout.addWidget(action_bar)

        # Auto-fill from Recreate Video settings
        self._sv_auto_fill_settings()

        return page

    def _sv_auto_fill_settings(self):
        """Auto-fill input/output from Recreate Video saved settings"""
        try:
            # Get output folder from saved config
            output_path = self.config_manager.get_path('output_base_dir')
            if output_path and os.path.exists(output_path):
                self.sv_output_edit.setText(output_path)

            # Get input folders from saved config
            multi_paths = self.config_manager.get_path('multi_folder_paths')
            input_path = self.config_manager.get_path('input_videos_folder')

            paths_to_add = []
            if multi_paths:
                paths_to_add = [p for p in multi_paths.split("|") if p and os.path.exists(p)]
            elif input_path and os.path.exists(input_path):
                paths_to_add = [input_path]

            if paths_to_add:
                for path in paths_to_add:
                    self._sv_add_folder_input(path)
            else:
                # Add one empty row
                self._sv_add_folder_input()
        except Exception:
            # Add one empty row on error
            self._sv_add_folder_input()

    def _sv_refresh_category_buttons(self):
        """Refresh category filter buttons for Story Video"""
        # Clear existing
        for btn in self.sv_category_buttons.values():
            btn.setParent(None)
            btn.deleteLater()
        self.sv_category_buttons.clear()

        while self.sv_category_buttons_layout.count():
            item = self.sv_category_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Category colors (same as Recreate Video)
        category_colors = [
            ("#3b82f6", "#2563eb"),  # Blue
            ("#8b5cf6", "#7c3aed"),  # Purple
            ("#f59e0b", "#d97706"),  # Amber
            ("#ec4899", "#db2777"),  # Pink
            ("#06b6d4", "#0891b2"),  # Cyan
            ("#ef4444", "#dc2626"),  # Red
            ("#10b981", "#059669"),  # Emerald
        ]

        def get_style(color, hover_color, is_active):
            if is_active:
                return f"""
                    QPushButton {{
                        background: {color};
                        color: #ffffff;
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: {hover_color}; }}
                """
            else:
                return f"""
                    QPushButton {{
                        background: #2a2a2a;
                        color: {color};
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 500;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: #3a3a3a; color: #ffffff; }}
                """

        # "All" button (Indigo)
        btn_all = QPushButton("All")
        btn_all.setStyleSheet(get_style(_gradient()[0], _gradient()[1], self.sv_selected_category == "ALL"))
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.clicked.connect(lambda: self._sv_filter_by_category("ALL"))
        self.sv_category_buttons_layout.addWidget(btn_all)
        self.sv_category_buttons["ALL"] = btn_all

        # Get categories and profiles
        categories = self.config_manager.get_categories()
        profiles = self.config_manager.get_profiles()
        color_idx = 0

        for cat in categories:
            count = sum(1 for p in profiles.values() if p.get("category", "Default") == cat)
            if count == 0:
                continue

            color, hover_color = category_colors[color_idx % len(category_colors)]
            color_idx += 1

            btn = QPushButton(f"{cat} ({count})")
            btn.setStyleSheet(get_style(color, hover_color, self.sv_selected_category == cat))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=cat: self._sv_filter_by_category(c))
            self.sv_category_buttons_layout.addWidget(btn)
            self.sv_category_buttons[cat] = btn

    def _sv_update_category_button_styles(self):
        """Update category button styles"""
        for cat, btn in self.sv_category_buttons.items():
            if cat == self.sv_selected_category:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {_gradient()[0]};
                        color: #ffffff;
                        border: none;
                        border-radius: 6px;
                        padding: 0 12px;
                        font-size: 12px;
                        font-weight: 600;
                    }}
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #2a2a2a;
                        color: #888888;
                        border: none;
                        border-radius: 6px;
                        padding: 0 12px;
                        font-size: 12px;
                        font-weight: 500;
                    }
                    QPushButton:hover { background: #3a3a3a; color: #ffffff; }
                """)

    def _sv_filter_by_category(self, category):
        """Filter profiles by category and auto-fill paths"""
        self.sv_selected_category = category
        self._sv_refresh_category_buttons()  # Refresh with colors
        self._sv_update_profile_checkboxes()

        # Auto-fill input/output paths based on category
        if category != "ALL":
            cat_data = self.config_manager.get_category_data(category)
            input_path = cat_data.get("input_path", "")
            output_path = cat_data.get("output_path", "")

            # Clear existing folder inputs
            for item in self.sv_folder_list[:]:
                item[0].setParent(None)
                item[0].deleteLater()
            self.sv_folder_list.clear()

            # Scan for subfolders and add each as input
            if input_path and Path(input_path).exists():
                subfolders = sorted([
                    f for f in Path(input_path).iterdir()
                    if f.is_dir() and not f.name.startswith('.')
                ])

                if subfolders:
                    # Add each subfolder as input
                    for subfolder in subfolders:
                        self._sv_add_folder_input(str(subfolder))
                else:
                    # No subfolders, add one input with main path
                    self._sv_add_folder_input(input_path)
            else:
                # No valid input path, add empty row
                self._sv_add_folder_input()

            # Update output path
            if output_path and os.path.exists(output_path):
                self.sv_output_edit.setText(output_path)

    def _sv_update_profile_checkboxes(self):
        """Update profile checkboxes for Story Video"""
        # Clear existing
        while self.sv_profile_checkboxes_layout.count():
            item = self.sv_profile_checkboxes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.sv_profile_checkboxes = {}

        profiles = self.config_manager.get_profiles()
        for name, data in profiles.items():
            cat = data.get('category', 'Uncategorized')

            # Filter by category
            if self.sv_selected_category != "ALL" and cat != self.sv_selected_category:
                continue

            cb = QCheckBox(name)
            cb.setChecked(name in self.sv_selected_profile_names)
            cb.setCursor(Qt.PointingHandCursor)
            cb.stateChanged.connect(lambda state, n=name: self._sv_on_profile_toggle(n, state))
            self._sv_update_chip_style(cb, name, cb.isChecked())
            self.sv_profile_checkboxes[name] = cb
            self.sv_profile_checkboxes_layout.addWidget(cb)

    def _sv_update_chip_style(self, checkbox, name, checked):
        """Update profile chip style"""
        if checked:
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                    background: {_gradient()[0]};
                    border-radius: 8px;
                }}
                QCheckBox:hover {{ background: {_gradient()[1]}; }}
                QCheckBox::indicator {{ width: 0; height: 0; }}
            """)
        else:
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #888888;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 8px 16px;
                    background: #2a2a2a;
                    border-radius: 8px;
                }
                QCheckBox:hover { color: #ffffff; background: #3a3a3a; }
                QCheckBox::indicator { width: 0; height: 0; }
            """)

    def _sv_on_profile_toggle(self, name, state):
        """Handle profile toggle"""
        if state:
            self.sv_selected_profile_names.add(name)
        else:
            self.sv_selected_profile_names.discard(name)

        if name in self.sv_profile_checkboxes:
            self._sv_update_chip_style(self.sv_profile_checkboxes[name], name, state)

    def _sv_select_all_profiles(self):
        """Select all visible profiles"""
        for name, cb in self.sv_profile_checkboxes.items():
            cb.setChecked(True)

    def _sv_select_no_profiles(self):
        """Deselect all profiles"""
        for name, cb in self.sv_profile_checkboxes.items():
            cb.setChecked(False)

    def _sv_toggle_broll_path(self, state):
        """Toggle B-roll path input"""
        enabled = bool(state)
        self.sv_broll_path.setEnabled(enabled)
        self.sv_btn_browse_broll.setEnabled(enabled)

    def _sv_add_folder_input(self, path=""):
        """Add a folder input row - same style as Recreate Video"""
        folder_num = len(self.sv_folder_list) + 1

        # Main container for folder card - clean minimal style
        row_widget = QFrame()
        row_widget.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        card_layout = QVBoxLayout(row_widget)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Top row: Number + Path + Buttons
        top_row = QWidget()
        top_row.setStyleSheet("background: transparent;")
        main_layout = QHBoxLayout(top_row)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(14)

        # Number badge
        num_label = QLabel(f"{folder_num}")
        num_label.setFixedSize(30, 30)
        num_label.setAlignment(Qt.AlignCenter)
        num_label.setStyleSheet(f"""
            background: {_gradient()[0]};
            color: #ffffff;
            font-weight: 700;
            font-size: 14px;
            border-radius: 15px;
        """)
        main_layout.addWidget(num_label)

        # Path input
        line_edit = QLineEdit()
        line_edit.setPlaceholderText("Select input folder...")
        line_edit.setFixedHeight(40)
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        if path:
            line_edit.setText(path)
        main_layout.addWidget(line_edit, 1)

        # Browse button
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedSize(90, 40)
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_browse.clicked.connect(lambda: self._sv_browse_for_row(line_edit))
        main_layout.addWidget(btn_browse)

        # Remove button
        btn_remove = QPushButton("Remove")
        btn_remove.setFixedSize(100, 40)
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #dc2626; }
        """)
        btn_remove.clicked.connect(lambda: self._sv_remove_folder_input(row_widget))
        main_layout.addWidget(btn_remove)

        card_layout.addWidget(top_row)
        self.sv_folder_layout.addWidget(row_widget)
        self.sv_folder_list.append((row_widget, line_edit, num_label))

        return line_edit

    def _sv_browse_for_row(self, line_edit):
        """Browse folder for a specific row"""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            line_edit.setText(folder)

    def _sv_remove_folder_input(self, row_widget):
        """Remove a folder input row"""
        if len(self.sv_folder_list) <= 1:
            return  # Keep at least one

        for i, item in enumerate(self.sv_folder_list):
            if item[0] == row_widget:
                self.sv_folder_list.pop(i)
                row_widget.setParent(None)
                row_widget.deleteLater()
                break

        # Renumber remaining rows
        for i, item in enumerate(self.sv_folder_list):
            num_label = item[2] if len(item) > 2 else None
            if num_label:
                num_label.setText(f"{i+1}")

    def _sv_browse_input(self):
        """Browse for input folder (legacy - not used)"""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.sv_input_edit.setText(folder)

    def _sv_browse_output(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.sv_output_edit.setText(folder)

    def _sv_browse_broll(self):
        """Browse for B-Roll folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select B-Roll Folder")
        if folder:
            self.sv_broll_path.setText(folder)

    def _sv_clean_output(self):
        """Clean output folder"""
        output_folder = self.sv_output_edit.text().strip()
        if not output_folder or not os.path.exists(output_folder):
            QMessageBox.warning(self, "Error", "Please select a valid output folder first")
            return

        reply = QMessageBox.question(
            self, "Confirm Clean",
            f"Are you sure you want to delete all files in:\n{output_folder}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                for item in os.listdir(output_folder):
                    item_path = os.path.join(output_folder, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                QMessageBox.information(self, "Success", "Output folder cleaned!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to clean folder: {e}")

    def _sv_stop_pipeline(self):
        """Stop the Story Video pipeline"""
        if hasattr(self, 'sv_worker') and self.sv_worker:
            self.sv_worker.stop()
            self.log("⏹️ Stopping Story Video pipeline...")
            # Update UI immediately
            self.sv_btn_run.setEnabled(True)
            self.sv_btn_stop.setEnabled(False)
            self.sv_status_text.setText("⏹️ Pipeline stopped by user")

    def _sv_run_pipeline(self):
        """Run the Story Video pipeline"""
        # SECURITY: Verify license before running pipeline
        is_licensed, message, _ = self.license_manager.check_license()
        if not is_licensed:
            QMessageBox.warning(self, "License Required", f"Cannot run pipeline: {message}")
            return

        # Get input folders from list
        input_folders = []
        for item in self.sv_folder_list:
            line_edit = item[1]
            folder_path = line_edit.text().strip()
            if folder_path and os.path.exists(folder_path):
                input_folders.append(folder_path)

        output_folder = self.sv_output_edit.text().strip()

        if not input_folders:
            QMessageBox.warning(self, "Error", "Please add at least one valid input folder")
            return

        if not output_folder:
            QMessageBox.warning(self, "Error", "Please select an output folder")
            return

        if not self.sv_selected_profile_names:
            QMessageBox.warning(self, "Error", "Please select at least one channel")
            return

        # Get options
        start_step = self.sv_start_step.currentData()
        options = {
            'clean': self.sv_cb_clean.isChecked(),
            'parallel': self.sv_cb_parallel.isChecked(),
            'music': self.sv_cb_music.isChecked(),
            'logo': self.sv_cb_logo.isChecked(),
            'global_broll': self.sv_cb_global_broll.isChecked(),
            'broll_path': self.sv_broll_path.text().strip() if self.sv_cb_global_broll.isChecked() else '',
        }

        profiles = list(self.sv_selected_profile_names)

        # Clear log and switch to log page
        self.log_output.clear()
        self.switch_page(5)  # Log page

        # Update UI - Story Video page buttons
        self.sv_btn_run.setEnabled(False)
        self.sv_btn_stop.setEnabled(True)
        self.sv_progress_bar.setValue(0)
        self.sv_status_text.setText("📖 Starting Story Video pipeline...")

        # Enable Log page Stop button so user can stop from there
        self.log_stop_btn.setEnabled(True)

        # Start worker with multiple folders
        self.sv_worker = StoryVideoWorker(
            script_path=STORY_VIDEO_SCRIPT,
            input_folders=input_folders,
            output_folder=output_folder,
            selected_profiles=profiles,
            start_step=start_step if start_step >= 0 else 0,
            options=options
        )
        self.sv_worker.progress.connect(self._sv_on_progress)
        self.sv_worker.finished.connect(self._sv_on_finished)
        self.sv_worker.start()

        # Log start message
        self.log(f"📖 Story Video pipeline started")
        self.log(f"   Input folders: {len(input_folders)}")
        for folder in input_folders:
            self.log(f"      • {Path(folder).name}")
        self.log(f"   Output: {output_folder}")
        self.log(f"   Channels: {', '.join(profiles)}")
        if options.get('global_broll') and options.get('broll_path'):
            self.log(f"   Global B-roll: {options['broll_path']}")

    def _sv_on_progress(self, message):
        """Handle progress updates from Story Video worker"""
        self.log(message)

        # Update progress bar based on step
        msg_lower = message.lower()
        if "step 0" in msg_lower:
            self.sv_progress_bar.setValue(10)
            self.sv_status_text.setText("Step 0/8 - Copying clips...")
        elif "step 1" in msg_lower:
            self.sv_progress_bar.setValue(20)
            self.sv_status_text.setText("Step 1/8 - Transcribing...")
        elif "step 2" in msg_lower:
            self.sv_progress_bar.setValue(30)
            self.sv_status_text.setText("Step 2/8 - AI rewriting...")
        elif "step 3" in msg_lower:
            self.sv_progress_bar.setValue(45)
            self.sv_status_text.setText("Step 3/8 - Generating voiceovers...")
        elif "step 4" in msg_lower:
            self.sv_progress_bar.setValue(55)
            self.sv_status_text.setText("Step 4/8 - Creating B-roll...")
        elif "step 5" in msg_lower:
            self.sv_progress_bar.setValue(70)
            self.sv_status_text.setText("Step 5/8 - Assembling videos...")
        elif "step 6" in msg_lower:
            self.sv_progress_bar.setValue(80)
            self.sv_status_text.setText("Step 6/8 - Ranking sequence...")
        elif "step 7" in msg_lower:
            self.sv_progress_bar.setValue(90)
            self.sv_status_text.setText("Step 7/8 - Combining videos...")
        elif "step 8" in msg_lower:
            self.sv_progress_bar.setValue(95)
            self.sv_status_text.setText("Step 8/8 - Upload ready...")

    def _sv_on_finished(self, success):
        """Handle Story Video worker completion"""
        self.sv_btn_run.setEnabled(True)
        self.sv_btn_stop.setEnabled(False)
        self.log_stop_btn.setEnabled(False)  # Disable Log page stop button too

        if success:
            self.sv_progress_bar.setValue(100)
            self.sv_status_text.setText("✅ Story Video completed!")
            self.log("✅ Story Video pipeline completed successfully!")
        else:
            self.sv_status_text.setText("❌ Pipeline failed")
            self.log("❌ Story Video pipeline failed")

    # ========================================================================
    # THUMBNAIL VIEWER PAGE
    # ========================================================================

    def create_thumbnail_viewer_page(self):
        """Create Thumbnail Viewer page - Original button-based design with Quick Generate"""
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        # ============ HEADER ============
        header = QHBoxLayout()
        header.setSpacing(16)

        title = QLabel("Thumbnails")
        title.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 600; letter-spacing: -0.5px;")
        header.addWidget(title)

        header.addStretch()

        self.thumb_status = QLabel("Select a category")
        self.thumb_status.setStyleSheet(f"""
            background: #252525;
            color: {_accent()};
            padding: 6px 16px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
        """)
        header.addWidget(self.thumb_status)

        layout.addLayout(header)
        layout.addSpacing(24)

        # ============ MAIN SCROLL AREA ============
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; margin: 4px 0; }
            QScrollBar::handle:vertical { background: #3a3a3a; border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #3a3d45; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(20)

        # ============ QUICK TITLE INPUT CARD ============
        quick_card = QFrame()
        quick_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(20, 16, 20, 16)
        quick_layout.setSpacing(12)

        # Quick input header
        quick_header = QHBoxLayout()
        quick_header.setSpacing(10)

        quick_icon = QLabel("")
        quick_icon.setFixedSize(24, 24)
        quick_icon.setAlignment(Qt.AlignCenter)
        quick_icon.setStyleSheet(f"""
            background: {_accent()};
            border-radius: 12px;
            color: white;
            font-size: 14px;
            font-weight: bold;
        """)
        quick_header.addWidget(quick_icon)

        quick_title = QLabel("Quick Generate")
        quick_title.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 600;")
        quick_header.addWidget(quick_title)

        quick_desc = QLabel("— Type a title or topic, get thumbnail ideas instantly")
        quick_desc.setStyleSheet("color: #888888; font-size: 12px;")
        quick_header.addWidget(quick_desc)

        quick_header.addStretch()
        quick_layout.addLayout(quick_header)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.quick_title_input = QLineEdit()
        self.quick_title_input.setPlaceholderText("Enter video title or topic... (e.g., 'Top 10 Tips for Beginners')")
        self.quick_title_input.setFixedHeight(44)
        self.quick_title_input.setStyleSheet(f"""
            QLineEdit {{
                background: #0d0e12;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                padding: 0 16px;
            }}
            QLineEdit:focus {{
                border-color: {_gradient()[0]};
            }}
            QLineEdit::placeholder {{
                color: #6e7681;
            }}
        """)
        self.quick_title_input.returnPressed.connect(self._thumb_quick_generate)
        input_row.addWidget(self.quick_title_input, 1)

        # AI Provider dropdown (main one for all thumbnail generation)
        ai_label = QLabel("AI:")
        ai_label.setStyleSheet("color: #888888; font-size: 13px; font-weight: 500;")
        input_row.addWidget(ai_label)

        self.thumb_ai_combo = QComboBox()
        self.thumb_ai_combo.addItems(["Claude", "OpenAI", "Gemini"])
        self.thumb_ai_combo.setFixedHeight(44)
        self.thumb_ai_combo.setFixedWidth(105)
        self.thumb_ai_combo.setStyleSheet(f"""
            QComboBox {{
                background: #2a2a2a;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                padding: 0 12px;
            }}
            QComboBox:hover {{ border-color: {_gradient()[0]}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {_gradient()[0]};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: none;
                color: #ffffff;
                selection-background-color: {_gradient()[0]};
            }}
        """)
        input_row.addWidget(self.thumb_ai_combo)

        self.quick_generate_btn = QPushButton("Generate Ideas")
        self.quick_generate_btn.setFixedHeight(44)
        self.quick_generate_btn.setFixedWidth(140)
        self.quick_generate_btn.setCursor(Qt.PointingHandCursor)
        self.quick_generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #5558e3;
            }}
            QPushButton:pressed {{
                background: #4749d4;
            }}
        """)
        self.quick_generate_btn.clicked.connect(self._thumb_quick_generate)
        input_row.addWidget(self.quick_generate_btn)

        quick_layout.addLayout(input_row)

        content_layout.addWidget(quick_card)

        # Divider with "OR"
        divider_widget = QWidget()
        divider_widget.setFixedHeight(30)
        divider_layout = QHBoxLayout(divider_widget)
        divider_layout.setContentsMargins(0, 0, 0, 0)

        divider_left = QFrame()
        divider_left.setFixedHeight(1)
        divider_left.setStyleSheet("background: #3a3a3a;")
        divider_layout.addWidget(divider_left, 1)

        or_label = QLabel("OR select from existing videos")
        or_label.setStyleSheet("color: #6e7681; font-size: 11px; padding: 0 12px;")
        divider_layout.addWidget(or_label)

        divider_right = QFrame()
        divider_right.setFixedHeight(1)
        divider_right.setStyleSheet("background: #3a3a3a;")
        divider_layout.addWidget(divider_right, 1)

        content_layout.addWidget(divider_widget)

        # ============ SELECTION CARD ============
        select_card = QFrame()
        select_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        select_layout = QVBoxLayout(select_card)
        select_layout.setContentsMargins(20, 16, 20, 16)
        select_layout.setSpacing(14)

        # Row 1: Category + Refresh
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        cat_label = QLabel("Category")
        cat_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        row1.addWidget(cat_label)

        # Category buttons container
        self.thumb_cat_widget = QWidget()
        self.thumb_cat_widget.setStyleSheet("background: transparent;")
        self.thumb_cat_layout = QHBoxLayout(self.thumb_cat_widget)
        self.thumb_cat_layout.setContentsMargins(0, 0, 0, 0)
        self.thumb_cat_layout.setSpacing(6)
        row1.addWidget(self.thumb_cat_widget)

        row1.addStretch()

        # Refresh button
        self.thumb_refresh_btn = QPushButton("↻ Refresh")
        self.thumb_refresh_btn.setFixedHeight(32)
        self.thumb_refresh_btn.setCursor(Qt.PointingHandCursor)
        self.thumb_refresh_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
        """)
        self.thumb_refresh_btn.clicked.connect(self._thumb_refresh_all)
        row1.addWidget(self.thumb_refresh_btn)

        select_layout.addLayout(row1)

        # Row 2: Channel buttons
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        channel_label = QLabel("Channel")
        channel_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        row2.addWidget(channel_label)

        # Channel buttons container
        self.thumb_channel_widget = QWidget()
        self.thumb_channel_widget.setStyleSheet("background: transparent;")
        self.thumb_channel_layout = QHBoxLayout(self.thumb_channel_widget)
        self.thumb_channel_layout.setContentsMargins(0, 0, 0, 0)
        self.thumb_channel_layout.setSpacing(6)
        row2.addWidget(self.thumb_channel_widget)

        row2.addStretch()

        select_layout.addLayout(row2)

        # Row 3: Video selector
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        video_label = QLabel("Video")
        video_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        row3.addWidget(video_label)

        self.thumb_project_combo = QComboBox()
        self.thumb_project_combo.setFixedHeight(40)
        self.thumb_project_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 16px;
                font-size: 14px;
            }}
            QComboBox:hover {{ background: #3a3a3a; }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {_gradient()[0]};
                margin-right: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: none;
                color: #ffffff;
                selection-background-color: {_gradient()[0]};
                padding: 8px;
            }}
        """)
        self.thumb_project_combo.currentIndexChanged.connect(self._thumb_on_project_selected)
        row3.addWidget(self.thumb_project_combo, 1)

        # Count label
        self.thumb_count_label = QLabel("")
        self.thumb_count_label.setStyleSheet("""
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 500;
        """)
        self.thumb_count_label.setVisible(False)
        row3.addWidget(self.thumb_count_label)

        select_layout.addLayout(row3)

        content_layout.addWidget(select_card)

        # Initialize tracking variables
        self.thumb_category_buttons = {}
        self.thumb_channel_buttons = {}
        self.thumb_current_category = None
        self.thumb_current_channel = None

        # ============ THUMBNAILS CARD ============
        thumb_card = QFrame()
        thumb_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        thumb_layout = QVBoxLayout(thumb_card)
        thumb_layout.setContentsMargins(20, 16, 20, 16)
        thumb_layout.setSpacing(14)

        # Thumbnails header with Regenerate button
        thumb_header_row = QHBoxLayout()
        thumb_header_row.setSpacing(12)

        thumb_header = QLabel("Thumbnail Options")
        thumb_header.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        thumb_header_row.addWidget(thumb_header)

        thumb_header_row.addStretch()

        # Mode label
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: #888888; font-size: 12px;")
        thumb_header_row.addWidget(mode_label)

        # Load saved mode (default to title)
        saved_mode = self.config_manager.get("thumb_gen_mode", "title")
        if not saved_mode or saved_mode not in ["title", "script"]:
            saved_mode = "title"

        # Title mode button (DEFAULT)
        self.thumb_mode_title = QPushButton("Title")
        self.thumb_mode_title.setCheckable(True)
        self.thumb_mode_title.setChecked(True)  # Always start with Title selected
        self.thumb_mode_title.setFixedHeight(28)
        self.thumb_mode_title.setCursor(Qt.PointingHandCursor)
        self.thumb_mode_title.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 5px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:checked {
                background: #f59e0b;
                color: #000;
            }
            QPushButton:hover:!checked { background: #3a3a3a; color: #ffffff; }
        """)
        self.thumb_mode_title.clicked.connect(lambda: self._thumb_set_gen_mode("title"))
        thumb_header_row.addWidget(self.thumb_mode_title)

        # Script mode button
        self.thumb_mode_script = QPushButton("Script")
        self.thumb_mode_script.setCheckable(True)
        self.thumb_mode_script.setChecked(False)  # Not selected by default
        self.thumb_mode_script.setFixedHeight(28)
        self.thumb_mode_script.setCursor(Qt.PointingHandCursor)
        self.thumb_mode_script.setStyleSheet(f"""
            QPushButton {{
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 5px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:checked {{
                background: {_gradient()[0]};
                color: #ffffff;
            }}
            QPushButton:hover:!checked {{ background: #3a3a3a; color: #ffffff; }}
        """)
        self.thumb_mode_script.clicked.connect(lambda: self._thumb_set_gen_mode("script"))
        thumb_header_row.addWidget(self.thumb_mode_script)

        thumb_header_row.addSpacing(10)

        thumb_header_row.addStretch()

        # AI Provider dropdown for regenerate section
        self.thumb_regen_ai_label = QLabel("AI:")
        self.thumb_regen_ai_label.setStyleSheet("color: #888888; font-size: 13px; font-weight: 500;")
        thumb_header_row.addWidget(self.thumb_regen_ai_label)

        self.thumb_regen_ai_combo = QComboBox()
        self.thumb_regen_ai_combo.addItems(["Claude", "OpenAI", "Gemini"])
        self.thumb_regen_ai_combo.setFixedHeight(32)
        self.thumb_regen_ai_combo.setFixedWidth(100)
        self.thumb_regen_ai_combo.setStyleSheet(f"""
            QComboBox {{
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                padding: 0 10px;
            }}
            QComboBox:hover {{ border-color: {_gradient()[0]}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {_gradient()[0]};
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: none;
                color: #ffffff;
                selection-background-color: {_gradient()[0]};
            }}
        """)
        thumb_header_row.addWidget(self.thumb_regen_ai_combo)

        thumb_header_row.addSpacing(8)

        self.thumb_regenerate_btn = QPushButton("Regenerate Ideas")
        self.thumb_regenerate_btn.setFixedHeight(32)
        self.thumb_regenerate_btn.setCursor(Qt.PointingHandCursor)
        self.thumb_regenerate_btn.setVisible(False)
        self.thumb_regenerate_btn.setStyleSheet("""
            QPushButton {
                background: #f59e0b;
                border: none;
                border-radius: 6px;
                color: #000;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: #d97706;
            }
        """)
        self.thumb_regenerate_btn.clicked.connect(self._thumb_regenerate)
        thumb_header_row.addWidget(self.thumb_regenerate_btn)

        thumb_layout.addLayout(thumb_header_row)

        # Cards container - vertical list
        self.thumb_cards_container = QWidget()
        self.thumb_cards_container.setStyleSheet("background: transparent;")
        self.thumb_cards_layout = QVBoxLayout(self.thumb_cards_container)
        self.thumb_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.thumb_cards_layout.setSpacing(12)
        thumb_layout.addWidget(self.thumb_cards_container)

        content_layout.addWidget(thumb_card)
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Hidden elements for compatibility
        self.thumb_info_bar = QFrame()
        self.thumb_info_bar.setVisible(False)
        self.thumb_info_label = QLabel("")

        # Store data
        self.thumb_current_mode = "create"
        self.thumb_current_category = None
        self.thumb_category_buttons = {}
        self.thumb_projects_data = []
        self.thumb_current_video_data = None
        self._thumb_gen_mode = "title"  # Always default to title mode

        # Initialize
        self._thumb_init_categories()

        return page

    def _thumb_init_categories(self):
        """Initialize category buttons"""
        # Clear existing buttons
        while self.thumb_cat_layout.count():
            child = self.thumb_cat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.thumb_category_buttons = {}

        # Get all categories (returns a list)
        categories = self.config_manager.get_categories()

        for cat_name in categories:
            btn = QPushButton(cat_name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #2a2a2a;
                    color: #888888;
                    border: none;
                    border-radius: 6px;
                    padding: 0 14px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:checked {{
                    background: {_gradient()[0]};
                    color: #ffffff;
                }}
                QPushButton:hover:!checked {{
                    background: #3a3a3a;
                    color: #ffffff;
                }}
            """)
            btn.clicked.connect(lambda checked, name=cat_name: self._thumb_select_category(name))
            self.thumb_cat_layout.addWidget(btn)
            self.thumb_category_buttons[cat_name] = btn

        self.thumb_status.setText("Select a category")

    def _thumb_select_category(self, category):
        """When category button is clicked"""
        # Update button states
        for name, btn in self.thumb_category_buttons.items():
            btn.setChecked(name == category)

        self.thumb_current_category = category
        self.thumb_current_channel = None
        self._thumb_refresh_channels()

    def _thumb_refresh_channels(self):
        """Refresh channel buttons for selected category"""
        # Clear existing channel buttons
        while self.thumb_channel_layout.count():
            child = self.thumb_channel_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.thumb_channel_buttons = {}

        # Clear videos
        self.thumb_project_combo.clear()
        self.thumb_projects_data = []
        self.thumb_count_label.setVisible(False)
        self._thumb_clear_cards()

        if not self.thumb_current_category:
            self.thumb_project_combo.addItem("Select category first")
            return

        # Get channels in this category
        profiles = self.config_manager.get_profiles()
        channels_in_category = []
        for name, data in profiles.items():
            if data.get('category') == self.thumb_current_category:
                channels_in_category.append(name)

        if not channels_in_category:
            self.thumb_status.setText(f"No channels in {self.thumb_current_category}")
            return

        # Create channel buttons
        for channel_name in channels_in_category:
            btn = QPushButton(channel_name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a;
                    color: #888888;
                    border: none;
                    border-radius: 6px;
                    padding: 0 14px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:checked {
                    background: #22c55e;
                    color: #ffffff;
                }
                QPushButton:hover:!checked {
                    background: #3a3a3a;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked, name=channel_name: self._thumb_select_channel(name))
            self.thumb_channel_layout.addWidget(btn)
            self.thumb_channel_buttons[channel_name] = btn

        self.thumb_status.setText(f"Select a channel")

    def _thumb_select_channel(self, channel):
        """When channel button is clicked"""
        # Update button states
        for name, btn in self.thumb_channel_buttons.items():
            btn.setChecked(name == channel)

        self.thumb_current_channel = channel
        self._thumb_refresh_videos()

    def _thumb_refresh_videos(self):
        """Refresh video dropdown for current channel - shows both Recreate and Create videos"""
        self.thumb_project_combo.clear()
        self.thumb_projects_data = []
        self.thumb_count_label.setVisible(False)
        self._thumb_clear_cards()

        if not self.thumb_current_category or not self.thumb_current_channel:
            self.thumb_project_combo.addItem("Select channel first")
            return

        cat_data = self.config_manager.get_category_data(self.thumb_current_category)
        recreate_path = cat_data.get("output_path", "")
        create_path = cat_data.get("cc_output_path", "")

        projects_found = []

        # Get channel suffix for filtering
        profile_data = self.config_manager.get_profile(self.thumb_current_channel)
        channel_suffix = profile_data.get('suffix', self.thumb_current_channel) if profile_data else self.thumb_current_channel

        # Search Recreate videos - check multiple locations for channel processing
        if recreate_path and os.path.exists(recreate_path):
            for video_folder in os.listdir(recreate_path):
                video_path = os.path.join(recreate_path, video_folder)
                if not os.path.isdir(video_path):
                    continue

                # Check if this channel processed this video by looking in multiple places
                channel_processed = False

                # 1. Check voiceover folder: 3_voiceovers/{video}_voiceover_{suffix}
                voiceover_dir = os.path.join(video_path, "3_voiceovers", f"{video_folder}_voiceover_{channel_suffix}")
                if os.path.exists(voiceover_dir):
                    channel_processed = True

                # 2. Check styled clips: 2_styled_clips/{video}_styled_{suffix}
                if not channel_processed:
                    styled_dir = os.path.join(video_path, "2_styled_clips", f"{video_folder}_styled_{channel_suffix}")
                    if os.path.exists(styled_dir):
                        channel_processed = True

                # 3. Check script file: 2_ai_scripts/{video}_rewritten_script_{suffix}.txt
                if not channel_processed:
                    ai_scripts_dir = os.path.join(video_path, "2_ai_scripts")
                    script_file = os.path.join(ai_scripts_dir, f"{video_folder}_rewritten_script_{channel_suffix}.txt")
                    if os.path.exists(script_file):
                        channel_processed = True

                # 4. Check final video folder: 5_final_videos/{video}_final_{suffix}
                if not channel_processed:
                    final_dir = os.path.join(video_path, "5_final_videos", f"{video_folder}_final_{channel_suffix}")
                    if os.path.exists(final_dir):
                        channel_processed = True

                if not channel_processed:
                    continue  # This channel didn't process this video

                # Look for upload folder
                for upload_name in ['10_youtube_uploads', '8_youtube_upload']:
                    upload_folder = os.path.join(video_path, upload_name)
                    if os.path.exists(upload_folder):
                        thumb_file = os.path.join(upload_folder, "thumbnail_prompt.txt")
                        has_thumb = os.path.exists(thumb_file)
                        projects_found.append({
                            "video": video_folder,
                            "file": thumb_file,
                            "path": video_path,
                            "has_thumb": has_thumb,
                            "mode": "Recreate"
                        })
                        break

        # Search Create videos (in channel subfolder)
        if create_path and os.path.exists(create_path):
            for video_folder in os.listdir(create_path):
                video_path = os.path.join(create_path, video_folder)
                if not os.path.isdir(video_path):
                    continue
                # Check channel subfolder
                channel_path = os.path.join(video_path, self.thumb_current_channel)
                if os.path.exists(channel_path):
                    for upload_name in ['8_youtube_upload', '10_youtube_uploads']:
                        upload_folder = os.path.join(channel_path, upload_name)
                        if os.path.exists(upload_folder):
                            thumb_file = os.path.join(upload_folder, "thumbnail_prompt.txt")
                            has_thumb = os.path.exists(thumb_file)
                            projects_found.append({
                                "video": video_folder,
                                "file": thumb_file,
                                "path": video_path,
                                "has_thumb": has_thumb,
                                "mode": "Create"
                            })
                            break

        if not projects_found:
            self.thumb_project_combo.addItem("No videos found")
            self.thumb_status.setText(f"No videos for {self.thumb_current_channel}")
            return

        # Sort by modification time (newest first)
        projects_found.sort(key=lambda x: os.path.getmtime(x["path"]) if os.path.exists(x["path"]) else 0, reverse=True)

        # Add to dropdown with mode tags
        self.thumb_project_combo.addItem("Select video...")
        self.thumb_projects_data.append(None)

        for proj in projects_found:
            display = f"{proj['video']} [{proj['mode']}]"
            if not proj["has_thumb"]:
                display += " [NO THUMB]"
            self.thumb_project_combo.addItem(display)
            self.thumb_projects_data.append(proj)

        # Update count
        self.thumb_count_label.setText(f"{len(projects_found)} videos")
        self.thumb_count_label.setVisible(True)
        self.thumb_status.setText(f"{self.thumb_current_channel}")

    def _thumb_refresh_all(self):
        """Refresh everything"""
        self._thumb_init_categories()
        if self.thumb_current_category:
            self._thumb_refresh_channels()
            if self.thumb_current_channel:
                self._thumb_refresh_videos()

    def _thumb_clear_cards(self):
        """Clear all thumbnail cards from grid"""
        while self.thumb_cards_layout.count():
            item = self.thumb_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _thumb_on_project_selected(self, index):
        """Handle project selection"""
        self._thumb_clear_cards()
        self.thumb_regenerate_btn.setVisible(False)
        self.thumb_current_video_data = None

        if index <= 0 or index >= len(self.thumb_projects_data):
            return

        data = self.thumb_projects_data[index]
        if not data:
            return

        thumb_file = data["file"]
        video_name = data["video"]

        # Store current video data for regenerate (even if file doesn't exist yet)
        self.thumb_current_video_data = data

        # Always show regenerate button so user can generate thumbnails
        self.thumb_regenerate_btn.setVisible(True)

        if not os.path.exists(thumb_file):
            self.thumb_status.setText(f"No thumbnails yet for {video_name}. Click 'Regenerate Ideas' to generate.")
            return

        try:
            with open(thumb_file, 'r', encoding='utf-8') as f:
                content = f.read()

            self._thumb_parse_and_display(content)
            self.thumb_status.setText(f"Showing thumbnails for: {video_name}")

        except Exception as e:
            self.thumb_status.setText(f"Error: {e}")

    def _thumb_parse_and_display(self, content):
        """Parse thumbnail_prompt.txt and display in 2-column grid"""
        self._thumb_clear_cards()

        # Parse options from content
        options = []
        current_option = {}
        current_prompt = []
        in_prompt = False

        lines = content.split('\n')
        for line in lines:
            line_stripped = line.strip()

            # Detect option start
            if line_stripped.startswith('OPTION ') or (line_stripped.startswith('------') and len(lines) > lines.index(line) and 'OPTION' in lines[max(0, lines.index(line)-1)]):
                if current_option and current_option.get('id'):
                    if current_prompt:
                        current_option['image_prompt'] = '\n'.join(current_prompt).strip()
                    options.append(current_option)
                current_option = {}
                current_prompt = []
                in_prompt = False

                if 'OPTION' in line_stripped:
                    try:
                        num = ''.join(filter(str.isdigit, line_stripped.split('OPTION')[1].split()[0]))
                        current_option['id'] = int(num) if num else len(options) + 1
                    except:
                        current_option['id'] = len(options) + 1

            elif line_stripped.startswith('Thumbnail:'):
                current_option['thumbnail_text'] = line_stripped.replace('Thumbnail:', '').strip().strip('"')
            elif line_stripped.startswith('Title:'):
                current_option['viral_title'] = line_stripped.replace('Title:', '').strip()
            elif line_stripped.startswith('CTR Potential:'):
                ctr = line_stripped.replace('CTR Potential:', '').replace('%', '').strip()
                current_option['ctr_potential'] = ctr
            elif line_stripped.startswith('image_prompt:'):
                in_prompt = True
                prompt_part = line_stripped.replace('image_prompt:', '').strip()
                if prompt_part:
                    current_prompt.append(prompt_part)
            elif in_prompt and line_stripped and not line_stripped.startswith('---') and not line_stripped.startswith('==='):
                current_prompt.append(line_stripped)
            elif in_prompt and (line_stripped.startswith('---') or line_stripped.startswith('===')):
                in_prompt = False

        # Add last option
        if current_option and current_option.get('id'):
            if current_prompt:
                current_option['image_prompt'] = '\n'.join(current_prompt).strip()
            options.append(current_option)

        # Check for TOP 3
        top_3_ids = []
        if 'TOP 3 MEGA-VIRAL' in content:
            top3_section = content.split('TOP 3 MEGA-VIRAL')[1] if 'TOP 3 MEGA-VIRAL' in content else ''
            for marker in ['NUCLEAR OPTION #1:', 'CONTROVERSY KING #2:', 'EMOTIONAL NUKE #3:']:
                if marker in top3_section:
                    try:
                        after_marker = top3_section.split(marker)[1][:50]
                        num = ''.join(filter(str.isdigit, after_marker.split()[0]))
                        if num:
                            top_3_ids.append(int(num))
                    except:
                        pass

        # Sort by CTR (highest first)
        options_sorted = sorted(options, key=lambda x: int(x.get('ctr_potential', '0').replace('%', '') or 0), reverse=True)

        # Create cards in vertical list - sorted by CTR
        for i, opt in enumerate(options_sorted):
            is_top3 = i < 3  # Top 3 by CTR
            card = self._thumb_create_card(opt, is_top3, rank=i+1)
            self.thumb_cards_layout.addWidget(card)

        # Parse and display YouTube SEO section
        self._thumb_parse_youtube_seo(content)

    def _thumb_create_card(self, option, is_top3=False, rank=0):
        """Create card - same style as Create Video page"""
        # Different colors for top 3: Gold, Silver, Bronze
        if rank == 1:
            border_color = "#FFD700"  # Gold
            bg_color = "#1a1c23"
            badge_bg = "#FFD700"
            badge_text = "🏆 #1"
        elif rank == 2:
            border_color = "#C0C0C0"  # Silver
            bg_color = "#1a1c23"
            badge_bg = "#C0C0C0"
            badge_text = "🥈 #2"
        elif rank == 3:
            border_color = "#CD7F32"  # Bronze
            bg_color = "#1a1c23"
            badge_bg = "#CD7F32"
            badge_text = "🥉 #3"
        else:
            border_color = "#2a2a2a"
            bg_color = "#252525"
            badge_bg = _gradient()[0]
            badge_text = f"#{option.get('id', '?')}"

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg_color};
                border: 2px solid {border_color};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        # Left: Option number badge
        opt_lbl = QLabel(badge_text)
        opt_lbl.setFixedWidth(70)
        opt_lbl.setAlignment(Qt.AlignCenter)
        text_color = '#000' if rank <= 3 else '#fff'
        opt_lbl.setStyleSheet(f"""
            background: {badge_bg};
            color: {text_color};
            padding: 8px 4px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
        """)
        layout.addWidget(opt_lbl)

        # Middle: Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        # Thumbnail text - WHITE
        thumb_text = option.get('thumbnail_text', 'No text')
        thumb_lbl = QLabel(f'"{thumb_text}"')
        thumb_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 600;")
        thumb_lbl.setWordWrap(True)
        text_layout.addWidget(thumb_lbl)

        # Title text - GRAY
        title = option.get('viral_title', '')
        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #6e7681; font-size: 13px;")
            title_lbl.setWordWrap(True)
            text_layout.addWidget(title_lbl)

        layout.addLayout(text_layout, 1)

        # Right: CTR + Copy buttons
        right_layout = QVBoxLayout()
        right_layout.setSpacing(6)
        right_layout.setAlignment(Qt.AlignRight)

        # CTR badge
        ctr = option.get('ctr_potential', '?')
        ctr_lbl = QLabel(f"CTR {ctr}%")
        ctr_lbl.setAlignment(Qt.AlignCenter)
        ctr_lbl.setStyleSheet("""
            background: #22c55e;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        """)
        right_layout.addWidget(ctr_lbl)

        # Copy Title button
        if title:
            copy_title_btn = QPushButton("Copy Title")
            copy_title_btn.setFixedHeight(32)
            copy_title_btn.setMinimumWidth(120)
            copy_title_btn.setCursor(Qt.PointingHandCursor)
            copy_title_btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a;
                    border: none;
                    border-radius: 6px;
                    color: #888888;
                    font-size: 12px;
                    font-weight: 500;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background: #3a3a3a;
                    color: #ffffff;
                }
            """)
            copy_title_btn.clicked.connect(lambda checked, t=title: self._thumb_copy_prompt(t))
            right_layout.addWidget(copy_title_btn)

        # Copy Prompt button
        prompt = option.get('image_prompt', '')
        if prompt:
            copy_btn = QPushButton("Copy Prompt")
            copy_btn.setFixedHeight(32)
            copy_btn.setMinimumWidth(120)
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_gradient()[0]};
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {_gradient()[1]};
                }}
            """)
            copy_btn.clicked.connect(lambda checked, p=prompt: self._thumb_copy_prompt(p))
            right_layout.addWidget(copy_btn)

        layout.addLayout(right_layout)

        return card

    def _thumb_copy_prompt(self, prompt):
        """Copy prompt to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(prompt)
        self.thumb_status.setText("✅ Copied to clipboard!")

    def _thumb_parse_youtube_seo(self, content):
        """Parse YouTube SEO section and display with copy buttons"""
        # Check if SEO section exists
        if "YOUTUBE SEO" not in content:
            return

        # Get only the SEO section (after YOUTUBE SEO header)
        seo_start = content.index("YOUTUBE SEO")
        seo_content = content[seo_start:]

        # Parse description - find content between DESCRIPTION header and HASHTAGS header
        description = ""
        if "DESCRIPTION (copy to YouTube):" in seo_content:
            try:
                desc_start = seo_content.index("DESCRIPTION (copy to YouTube):") + len("DESCRIPTION (copy to YouTube):")
                desc_section = seo_content[desc_start:]
                # Find HASHTAGS section
                if "HASHTAGS:" in desc_section:
                    desc_end = desc_section.index("HASHTAGS:")
                    # Go back to find the dashed line before HASHTAGS
                    temp = desc_section[:desc_end]
                    if "------" in temp:
                        last_dash = temp.rfind("------")
                        desc_end = last_dash
                    description = desc_section[:desc_end].strip().strip('-').strip()
            except:
                pass

        # Parse hashtags - find content between HASHTAGS header and TAGS header
        hashtags = ""
        if "HASHTAGS:" in seo_content:
            try:
                hash_start = seo_content.index("HASHTAGS:") + len("HASHTAGS:")
                hash_section = seo_content[hash_start:]
                # Find TAGS section
                if "TAGS (copy to YouTube):" in hash_section:
                    hash_end = hash_section.index("TAGS (copy to YouTube):")
                    # Go back to find the dashed line before TAGS
                    temp = hash_section[:hash_end]
                    if "------" in temp:
                        last_dash = temp.rfind("------")
                        hash_end = last_dash
                    hashtags = hash_section[:hash_end].strip().strip('-').strip()
            except:
                pass

        # Parse tags - find content after TAGS header until end or ======
        tags = ""
        if "TAGS (copy to YouTube):" in seo_content:
            try:
                tags_start = seo_content.index("TAGS (copy to YouTube):") + len("TAGS (copy to YouTube):")
                tags_section = seo_content[tags_start:]
                # Find end markers
                tags_end = len(tags_section)
                if "======" in tags_section:
                    tags_end = tags_section.index("======")
                tags = tags_section[:tags_end].strip().strip('-').strip()
            except:
                pass

        # Only show if we have SEO data
        if not description and not tags:
            return

        # Combine description + hashtags for copying (hashtags go at end of description)
        # But only add hashtags if description doesn't already end with them
        full_description = description
        if hashtags and not description.strip().endswith(hashtags.strip()):
            # Check if description already contains the hashtags
            if hashtags.strip() not in description:
                full_description = description + "\n\n" + hashtags

        # Create SEO section card
        seo_card = QFrame()
        seo_card.setStyleSheet("""
            QFrame {
                background: #1a1c23;
                border: 2px solid #10b981;
                border-radius: 10px;
                margin-top: 20px;
            }
        """)

        seo_layout = QVBoxLayout(seo_card)
        seo_layout.setContentsMargins(16, 16, 16, 16)
        seo_layout.setSpacing(12)

        # Header
        header = QLabel("📋 YOUTUBE SEO - Description & Tags")
        header.setStyleSheet("color: #10b981; font-size: 16px; font-weight: 700; border: none;")
        seo_layout.addWidget(header)

        # Description section (includes hashtags at end)
        if full_description:
            desc_frame = QFrame()
            desc_frame.setStyleSheet("background: #252525; border-radius: 8px; border: none;")
            desc_layout = QVBoxLayout(desc_frame)
            desc_layout.setContentsMargins(12, 12, 12, 12)

            desc_header_row = QHBoxLayout()
            desc_label = QLabel("Description (with hashtags)")
            desc_label.setStyleSheet("color: #888888; font-size: 13px; font-weight: 600; border: none;")
            desc_header_row.addWidget(desc_label)
            desc_header_row.addStretch()

            copy_desc_btn = QPushButton("Copy Description")
            copy_desc_btn.setFixedHeight(28)
            copy_desc_btn.setCursor(Qt.PointingHandCursor)
            copy_desc_btn.setStyleSheet("""
                QPushButton {
                    background: #10b981;
                    border: none;
                    border-radius: 5px;
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 12px;
                }
                QPushButton:hover { background: #059669; }
            """)
            copy_desc_btn.clicked.connect(lambda checked, txt=full_description: self._thumb_copy_seo(txt, "Description"))
            desc_header_row.addWidget(copy_desc_btn)
            desc_layout.addLayout(desc_header_row)

            # Show preview with hashtags visible
            preview = full_description[:500] + "..." if len(full_description) > 500 else full_description
            desc_text = QLabel(preview)
            desc_text.setWordWrap(True)
            desc_text.setStyleSheet("color: #e0e0e0; font-size: 12px; border: none;")
            desc_layout.addWidget(desc_text)

            seo_layout.addWidget(desc_frame)

        # Tags section
        if tags:
            tags_frame = QFrame()
            tags_frame.setStyleSheet("background: #252525; border-radius: 8px; border: none;")
            tags_layout = QVBoxLayout(tags_frame)
            tags_layout.setContentsMargins(12, 12, 12, 12)

            tags_header_row = QHBoxLayout()
            tags_label = QLabel("Tags")
            tags_label.setStyleSheet("color: #888888; font-size: 13px; font-weight: 600; border: none;")
            tags_header_row.addWidget(tags_label)
            tags_header_row.addStretch()

            copy_tags_btn = QPushButton("Copy Tags")
            copy_tags_btn.setFixedHeight(28)
            copy_tags_btn.setCursor(Qt.PointingHandCursor)
            copy_tags_btn.setStyleSheet("""
                QPushButton {
                    background: #f59e0b;
                    border: none;
                    border-radius: 5px;
                    color: #000;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 12px;
                }
                QPushButton:hover { background: #d97706; }
            """)
            copy_tags_btn.clicked.connect(lambda checked, txt=tags: self._thumb_copy_seo(txt, "Tags"))
            tags_header_row.addWidget(copy_tags_btn)
            tags_layout.addLayout(tags_header_row)

            tags_text = QLabel(tags)
            tags_text.setWordWrap(True)
            tags_text.setStyleSheet("color: #fbbf24; font-size: 12px; border: none;")
            tags_layout.addWidget(tags_text)

            seo_layout.addWidget(tags_frame)

        # Add to cards layout
        self.thumb_cards_layout.addWidget(seo_card)

    def _thumb_copy_seo(self, text, label):
        """Copy SEO text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.thumb_status.setText(f"✅ {label} copied to clipboard!")

    def _thumb_set_gen_mode(self, mode):
        """Set thumbnail GENERATION mode (title or script)"""
        self._thumb_gen_mode = mode

        # Save preference
        try:
            self.config_manager.set("thumb_gen_mode", mode)
        except Exception as e:
            print(f"Error saving mode: {e}")

        # Update button states
        self.thumb_mode_title.setChecked(mode == "title")
        self.thumb_mode_script.setChecked(mode == "script")

        # Update status
        if mode == "title":
            self.thumb_status.setText("Mode: Title (from filename)")
        else:
            self.thumb_status.setText("Mode: Script (from video content)")

        # Clear input folder (will be determined from selected video when regenerating)
        self._thumb_input_folder = None

    def _thumb_regenerate(self):
        """Regenerate thumbnail ideas for current video"""
        if not self.thumb_current_video_data:
            self.thumb_status.setText("No video selected")
            return

        thumb_file = self.thumb_current_video_data.get("file", "")
        video_name = self.thumb_current_video_data.get("video", "")

        if not thumb_file:
            self.thumb_status.setText("Video folder not found")
            return

        # Get folders even if thumb_file doesn't exist yet
        video_output_dir = os.path.dirname(thumb_file)  # 8_youtube_upload or 10_youtube_uploads folder
        project_dir = os.path.dirname(video_output_dir)  # Video project folder (or channel folder for Create)

        # For Create videos: path is OUTPUT/VIDEO/CHANNEL/8_youtube_upload
        # project_dir would be CHANNEL level, but scripts are at VIDEO level (one up)
        # Check if 1_processing exists at project_dir, if not try parent
        if not os.path.exists(os.path.join(project_dir, "1_processing")):
            parent_dir = os.path.dirname(project_dir)
            if os.path.exists(os.path.join(parent_dir, "1_processing")):
                project_dir = parent_dir

        # Verify the output directory exists (even if thumbnail file doesn't)
        if not os.path.exists(video_output_dir):
            self.thumb_status.setText(f"Upload folder not found: {video_output_dir}")
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        thumb_script = os.path.join(script_dir, "11_thumbnail_generator.py")

        if not os.path.exists(thumb_script):
            self.thumb_status.setText("Thumbnail generator script not found")
            return

        # Step 1: Delete old thumbnail_prompt.txt so script will regenerate
        try:
            if os.path.exists(thumb_file):
                os.remove(thumb_file)
                self.thumb_status.setText(f"Deleted old thumbnails, generating new...")
        except Exception as e:
            self.thumb_status.setText(f"Error deleting old file: {e}")
            return

        # Store start time to check for new file
        import time
        self._thumb_regen_start_time = time.time()

        # Disable button
        self.thumb_regenerate_btn.setEnabled(False)
        self.thumb_regenerate_btn.setText("Regenerating...")

        # Run in thread with progress animation
        import subprocess
        import threading

        # Store for progress animation
        self._thumb_regen_running = True
        self._thumb_regen_dots = 0

        def update_progress():
            """Update progress animation"""
            if hasattr(self, '_thumb_regen_running') and self._thumb_regen_running:
                self._thumb_regen_dots = (self._thumb_regen_dots + 1) % 4
                dots = "." * self._thumb_regen_dots
                self.thumb_status.setText(f"AI generating new ideas{dots} (30-60 sec)")
                QTimer.singleShot(500, update_progress)

        # Store paths for checking
        self._thumb_regen_output_file = thumb_file
        self._thumb_regen_video_output_dir = video_output_dir

        # Start progress animation and file check
        QTimer.singleShot(500, update_progress)
        QTimer.singleShot(2000, self._thumb_check_regenerate_done)

        # Store error for later
        self._thumb_regen_error = ""

        # Get AI provider from regenerate dropdown (before thread starts)
        ai_provider = self.thumb_regen_ai_combo.currentText().lower()
        if ai_provider == "openai":
            ai_provider = "openai"
        elif ai_provider == "gemini":
            ai_provider = "gemini"
        else:
            ai_provider = "claude"

        def run_task():
            try:
                # Hide CMD window on Windows
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                # Get current generation mode (default to title)
                mode = getattr(self, '_thumb_gen_mode', 'title')

                # Script mode: use OUTPUT folder (where 1_processing/full_script_readable.txt is)
                # Title mode: use INPUT folder (where thumbnail_TITLE.jpg is)
                # OUTPUT structure: CATEGORY/OUTPUT/VIDEO/CHANNEL/8_youtube_upload (Create)
                # INPUT structure: CATEGORY/INPUT/VIDEO/ (title mode)
                source_dir = project_dir  # Default to project dir (OUTPUT)

                # Validate project_dir is not None
                if not project_dir:
                    self._thumb_regen_error = "Project directory not found"
                    return

                # For TITLE mode: find INPUT folder from OUTPUT path
                # For SCRIPT mode: keep using project_dir (OUTPUT folder)
                if mode == "title":
                    try:
                        output_parts = os.path.normpath(project_dir).split(os.sep)

                        # Find OUTPUT folder position and replace with INPUT
                        input_found = False
                        for i, part in enumerate(output_parts):
                            if part.upper() == "OUTPUT":
                                # For Create Video: OUTPUT/VIDEO/CHANNEL -> INPUT/VIDEO
                                # For Recreate Video: OUTPUT/VIDEO -> INPUT/VIDEO
                                # So we take up to VIDEO (i+2), not including CHANNEL
                                if i + 1 < len(output_parts):
                                    input_parts = output_parts[:i] + ["INPUT"] + [output_parts[i+1]]  # Replace OUTPUT with INPUT, keep VIDEO
                                    potential_input = os.path.sep.join(input_parts)

                                    if os.path.exists(potential_input):
                                        source_dir = potential_input
                                        print(f"Using INPUT folder for title mode: {source_dir}")
                                        input_found = True
                                        break

                        if not input_found:
                            print(f"Could not find INPUT folder for title mode, using project_dir: {project_dir}")
                    except Exception as e:
                        print(f"Error finding input folder: {e}")
                else:
                    # Script mode - use project_dir directly (OUTPUT folder where script is)
                    print(f"Using OUTPUT folder for script mode: {source_dir}")

                # Auto-detect mode: if script mode selected but no script file exists, try parent or switch to title
                if mode == "script":
                    import glob
                    # Check if script file exists in source_dir or parent (Create videos have channel subfolder)
                    search_dirs = [source_dir, os.path.dirname(source_dir)]
                    has_script = False
                    script_source = source_dir

                    for search_dir in search_dirs:
                        script_patterns = [
                            os.path.join(search_dir, "1_processing", "full_script_readable.txt"),
                            os.path.join(search_dir, "2_ai_scripts", "*_rewritten_script_*.txt"),
                        ]
                        for pattern in script_patterns:
                            if glob.glob(pattern):
                                has_script = True
                                script_source = search_dir
                                break
                        if has_script:
                            break

                    if has_script:
                        source_dir = script_source
                        print(f"Found script in: {source_dir}")
                    else:
                        print(f"No script file found in {source_dir}, switching to title mode")
                        mode = "title"
                        # Also try INPUT folder for title mode
                        try:
                            output_parts = os.path.normpath(source_dir).split(os.sep)
                            for idx, part in enumerate(output_parts):
                                if part.upper() == "OUTPUT" and idx + 1 < len(output_parts):
                                    input_parts = output_parts[:idx] + ["INPUT"] + [output_parts[idx+1]]
                                    potential_input = os.path.sep.join(input_parts)
                                    if os.path.exists(potential_input):
                                        source_dir = potential_input
                                        print(f"Switched to INPUT folder: {source_dir}")
                                        break
                        except Exception:
                            pass

                result = subprocess.run(
                    ["python", thumb_script, "--project-dir", source_dir, "--output-dir", video_output_dir, "--mode", mode, "--provider", ai_provider],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

                # Check if script had errors
                if result.returncode != 0:
                    # Try to find the actual error message (not INFO/DEBUG logs)
                    error_text = result.stderr or result.stdout or "Unknown error"

                    # Look for common error patterns
                    if "API key not found" in error_text:
                        self._thumb_regen_error = "API key not found. Please add your API key in Settings > API Keys."
                    elif "No script file found" in error_text:
                        self._thumb_regen_error = "No script file found in project folder."
                    elif "Script content is empty" in error_text:
                        self._thumb_regen_error = "Script file is empty."
                    elif "Failed to generate" in error_text:
                        self._thumb_regen_error = "AI failed to generate ideas. Check API key."
                    else:
                        # Look for ERROR level log lines (not INFO)
                        real_error = None
                        for line in error_text.split('\n'):
                            line_stripped = line.strip()
                            # Skip INFO/DEBUG/WARNING lines
                            if ' - INFO - ' in line_stripped or ' - DEBUG - ' in line_stripped:
                                continue
                            # Capture ERROR lines
                            if ' - ERROR - ' in line_stripped:
                                real_error = line_stripped.split(' - ERROR - ')[-1][:100]
                                break
                            # Capture exception messages
                            if 'Exception' in line_stripped or 'Traceback' in line_stripped:
                                real_error = line_stripped[:100]
                                break

                        if real_error:
                            self._thumb_regen_error = real_error
                        else:
                            # No clear error found, show generic message
                            self._thumb_regen_error = "Generation failed. Check logs for details."

                # Script finished - mark done
                self._thumb_regen_running = False
            except Exception as e:
                self._thumb_regen_error = str(e)
                self._thumb_regen_running = False

        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()

    def _thumb_check_regenerate_done(self):
        """Check if regeneration is done by looking for the new file"""
        import time
        video_output_dir = getattr(self, '_thumb_regen_video_output_dir', '')
        regen_error = getattr(self, '_thumb_regen_error', '')
        start_time = getattr(self, '_thumb_regen_start_time', 0)

        if video_output_dir:
            thumb_file = os.path.join(video_output_dir, "thumbnail_prompt.txt")

            # Check file exists AND was created AFTER we started regenerating
            if os.path.exists(thumb_file):
                try:
                    file_size = os.path.getsize(thumb_file)
                    file_time = os.path.getmtime(thumb_file)
                    # File must be created after we started AND have content
                    if file_size > 100 and file_time > start_time:
                        # New file created - done!
                        self._thumb_regen_running = False
                        self._thumb_regenerate_finished(True)
                        return
                except:
                    pass

        # Still running? Check again in 2 seconds (max 90 checks = 3 minutes)
        if hasattr(self, '_thumb_regen_running') and self._thumb_regen_running:
            self._thumb_regen_check_count = getattr(self, '_thumb_regen_check_count', 0) + 1
            if self._thumb_regen_check_count < 90:
                QTimer.singleShot(2000, self._thumb_check_regenerate_done)
            else:
                # Timeout
                self._thumb_regen_running = False
                self._thumb_regenerate_finished(False, "Timeout after 3 minutes")
        else:
            # Process ended - check for errors first
            if regen_error:
                self._thumb_regenerate_finished(False, regen_error[:100])  # First 100 chars of error
            elif video_output_dir:
                thumb_file = os.path.join(video_output_dir, "thumbnail_prompt.txt")
                if os.path.exists(thumb_file):
                    self._thumb_regenerate_finished(True)
                else:
                    self._thumb_regenerate_finished(False, "No file created")

    def _thumb_regenerate_finished(self, success, error_msg=""):
        """Called when regeneration completes - update UI"""
        self._thumb_regen_running = False
        self._thumb_regen_check_count = 0
        self.thumb_regenerate_btn.setEnabled(True)
        self.thumb_regenerate_btn.setText("Regenerate Ideas")

        if success:
            video_name = self.thumb_current_video_data.get("video", "") if self.thumb_current_video_data else ""
            self.thumb_status.setText(f"Done! Loading new ideas...")

            # Update the file path in current video data
            video_output_dir = getattr(self, '_thumb_regen_video_output_dir', '')
            if video_output_dir and self.thumb_current_video_data:
                new_file = os.path.join(video_output_dir, "thumbnail_prompt.txt")
                self.thumb_current_video_data["file"] = new_file

            # Reload by reading the new file directly
            if video_output_dir:
                new_file = os.path.join(video_output_dir, "thumbnail_prompt.txt")
                if os.path.exists(new_file):
                    try:
                        with open(new_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self._thumb_parse_and_display(content)
                        self.thumb_status.setText(f"New ideas loaded for: {video_name}")
                    except Exception as e:
                        self.thumb_status.setText(f"Error reading new file: {e}")
                else:
                    self.thumb_status.setText(f"File not found after regeneration")
        else:
            self.thumb_status.setText(f"Error: {error_msg}")

    def _thumb_quick_generate(self):
        """Quick generate thumbnail ideas from typed title - no video selection needed"""
        title_text = self.quick_title_input.text().strip()

        if not title_text:
            self.thumb_status.setText("Please enter a video title or topic")
            self.quick_title_input.setFocus()
            return

        if len(title_text) < 5:
            self.thumb_status.setText("Title too short - please enter more details")
            return

        # Clear any existing cards
        self._thumb_clear_cards()

        # Disable button and show progress
        self.quick_generate_btn.setEnabled(False)
        self.quick_generate_btn.setText("Generating...")
        self.thumb_status.setText("AI generating thumbnail ideas...")

        # Store for progress animation
        self._thumb_quick_running = True
        self._thumb_quick_dots = 0
        self._thumb_quick_title = title_text

        def update_progress():
            """Update progress animation"""
            if hasattr(self, '_thumb_quick_running') and self._thumb_quick_running:
                self._thumb_quick_dots = (self._thumb_quick_dots + 1) % 4
                dots = "." * self._thumb_quick_dots
                self.thumb_status.setText(f"AI generating ideas{dots} (30-60 sec)")
                QTimer.singleShot(500, update_progress)

        QTimer.singleShot(500, update_progress)

        # Get AI provider from the always-visible dropdown
        ai_provider = self.thumb_ai_combo.currentText().lower()
        if ai_provider == "openai":
            ai_provider = "openai"
        elif ai_provider == "gemini":
            ai_provider = "gemini"
        else:
            ai_provider = "claude"

        # Run generation in thread
        import subprocess
        import threading
        import tempfile

        # Create temp output directory
        temp_dir = tempfile.mkdtemp(prefix="nvs_thumb_")
        self._thumb_quick_temp_dir = temp_dir

        def run_quick_generate():
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                thumb_script = os.path.join(script_dir, "11_thumbnail_generator.py")

                if not os.path.exists(thumb_script):
                    self._thumb_quick_error = "Thumbnail generator script not found"
                    self._thumb_quick_running = False
                    return

                # Hide CMD window on Windows
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                # Run with --title flag for quick mode
                result = subprocess.run(
                    ["python", thumb_script,
                     "--title", title_text,
                     "--output-dir", temp_dir,
                     "--mode", "title",
                     "--provider", ai_provider],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

                if result.returncode != 0:
                    error_text = result.stderr or result.stdout or "Unknown error"
                    if "API key not found" in error_text:
                        self._thumb_quick_error = "API key not found. Add it in Settings > API Keys."
                    elif "max_tokens" in error_text or "max_completion_tokens" in error_text:
                        self._thumb_quick_error = "OpenAI API error: Model parameter issue. Try Claude or Gemini."
                    elif "401" in error_text or "Unauthorized" in error_text:
                        self._thumb_quick_error = "Invalid API key. Check Settings > API Keys."
                    elif "429" in error_text or "rate limit" in error_text.lower():
                        self._thumb_quick_error = "API rate limit. Wait a moment and try again."
                    elif "timeout" in error_text.lower():
                        self._thumb_quick_error = "API timeout. Try again."
                    else:
                        # Show first meaningful error line
                        for line in error_text.split('\n'):
                            if 'ERROR' in line or 'Exception' in line or 'Error' in line:
                                self._thumb_quick_error = f"Error: {line.strip()[:150]}"
                                break
                        else:
                            self._thumb_quick_error = f"Error: {error_text[:150]}"
                else:
                    self._thumb_quick_error = ""

                self._thumb_quick_running = False

            except subprocess.TimeoutExpired:
                self._thumb_quick_error = "Timeout after 3 minutes"
                self._thumb_quick_running = False
            except Exception as e:
                self._thumb_quick_error = str(e)[:100]
                self._thumb_quick_running = False

        # Start check timer
        self._thumb_quick_check_count = 0
        QTimer.singleShot(2000, self._thumb_quick_check_done)

        # Start thread
        thread = threading.Thread(target=run_quick_generate, daemon=True)
        thread.start()

    def _thumb_quick_check_done(self):
        """Check if quick generation is done"""
        temp_dir = getattr(self, '_thumb_quick_temp_dir', '')
        error = getattr(self, '_thumb_quick_error', '')

        if temp_dir:
            thumb_file = os.path.join(temp_dir, "thumbnail_prompt.txt")

            if os.path.exists(thumb_file):
                try:
                    file_size = os.path.getsize(thumb_file)
                    if file_size > 100:
                        # Done! Load the content
                        self._thumb_quick_running = False
                        self._thumb_quick_finished(True, thumb_file)
                        return
                except:
                    pass

        # Still running?
        if hasattr(self, '_thumb_quick_running') and self._thumb_quick_running:
            self._thumb_quick_check_count = getattr(self, '_thumb_quick_check_count', 0) + 1
            if self._thumb_quick_check_count < 90:  # 3 minutes max
                QTimer.singleShot(2000, self._thumb_quick_check_done)
            else:
                self._thumb_quick_running = False
                self._thumb_quick_finished(False, "", "Timeout after 3 minutes")
        else:
            # Process ended
            if error:
                self._thumb_quick_finished(False, "", error)
            elif temp_dir:
                thumb_file = os.path.join(temp_dir, "thumbnail_prompt.txt")
                if os.path.exists(thumb_file):
                    self._thumb_quick_finished(True, thumb_file)
                else:
                    self._thumb_quick_finished(False, "", "No ideas generated")

    def _thumb_quick_finished(self, success, thumb_file="", error_msg=""):
        """Called when quick generation completes"""
        self._thumb_quick_running = False
        self.quick_generate_btn.setEnabled(True)
        self.quick_generate_btn.setText("Generate Ideas")

        if success and thumb_file and os.path.exists(thumb_file):
            try:
                with open(thumb_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                self._thumb_parse_and_display(content)
                title = getattr(self, '_thumb_quick_title', 'your title')
                self.thumb_status.setText(f"Ideas generated for: {title[:50]}...")

                # Clear video selection since we used quick mode
                self.thumb_current_video_data = None
                self.thumb_regenerate_btn.setVisible(False)

            except Exception as e:
                self.thumb_status.setText(f"Error loading ideas: {e}")
        else:
            self.thumb_status.setText(f"Error: {error_msg or 'Generation failed'}")

        # Cleanup temp directory
        temp_dir = getattr(self, '_thumb_quick_temp_dir', '')
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

    # ========================================================================
    # CONTENT CREATOR PAGE
    # ========================================================================

    def create_content_creator_page(self):
        """Create Content Creator page - Modern Minimal Design"""
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        # ============ HEADER ============
        header = QHBoxLayout()
        header.setSpacing(16)

        title = QLabel("Create Video")
        title.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 600; letter-spacing: -0.5px;")
        header.addWidget(title)

        header.addStretch()

        self.cc_status_badge = QLabel("Ready")
        self.cc_status_badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 6px 16px;
            border-radius: 16px;
            font-size: 12px;
            font-weight: 500;
        """)
        header.addWidget(self.cc_status_badge)

        layout.addLayout(header)
        layout.addSpacing(24)

        # ============ MAIN CONTENT SCROLL ============
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; margin: 4px 0; }
            QScrollBar::handle:vertical { background: #3a3a3a; border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #3a3d45; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(20)

        # ============ CHANNELS SECTION ============
        channels_card = QFrame()
        channels_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        channels_layout = QVBoxLayout(channels_card)
        channels_layout.setContentsMargins(20, 16, 20, 16)
        channels_layout.setSpacing(14)

        # Channels header
        ch_header = QHBoxLayout()
        ch_header.setSpacing(12)

        ch_title = QLabel("Channels")
        ch_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        ch_header.addWidget(ch_title)

        # Category filter buttons
        self.cc_category_buttons_widget = QWidget()
        self.cc_category_buttons_widget.setStyleSheet("background: transparent;")
        self.cc_category_buttons_layout = QHBoxLayout(self.cc_category_buttons_widget)
        self.cc_category_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.cc_category_buttons_layout.setSpacing(6)
        self.cc_category_buttons = {}
        self.cc_selected_category = "ALL"
        self.refresh_cc_category_buttons()
        ch_header.addWidget(self.cc_category_buttons_widget)

        ch_header.addStretch()

        # All/None buttons
        btn_all = QPushButton("Select All")
        btn_all.setFixedHeight(32)
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_all.clicked.connect(self.cc_select_all_profiles)
        ch_header.addWidget(btn_all)

        btn_none = QPushButton("Clear")
        btn_none.setFixedHeight(32)
        btn_none.setCursor(Qt.PointingHandCursor)
        btn_none.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
        """)
        btn_none.clicked.connect(self.cc_select_no_profiles)
        ch_header.addWidget(btn_none)

        channels_layout.addLayout(ch_header)

        # Channel chips container
        self.cc_profile_checkboxes_container = QWidget()
        self.cc_profile_checkboxes_container.setStyleSheet("background: transparent;")
        self.cc_profile_checkboxes_layout = QHBoxLayout(self.cc_profile_checkboxes_container)
        self.cc_profile_checkboxes_layout.setContentsMargins(0, 4, 0, 0)
        self.cc_profile_checkboxes_layout.setSpacing(8)
        self.cc_profile_checkboxes_layout.setAlignment(Qt.AlignLeft)
        self.cc_profile_checkboxes = {}
        self.update_cc_profile_checkboxes()
        channels_layout.addWidget(self.cc_profile_checkboxes_container)

        content_layout.addWidget(channels_card)

        # ============ INPUT FOLDERS SECTION ============
        folders_card = QFrame()
        folders_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        folders_layout = QVBoxLayout(folders_card)
        folders_layout.setContentsMargins(20, 16, 20, 16)
        folders_layout.setSpacing(16)

        # Input folders header
        input_header = QHBoxLayout()
        input_header.setSpacing(12)

        input_title = QLabel("Input Folders")
        input_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        input_header.addWidget(input_title)

        input_header.addStretch()

        btn_add = QPushButton("+ Add Folder")
        btn_add.setFixedHeight(32)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_add.clicked.connect(self.cc_add_folder_input)
        input_header.addWidget(btn_add)

        self.cc_btn_add_from_cat = QPushButton("+ From Category")
        self.cc_btn_add_from_cat.setFixedHeight(32)
        self.cc_btn_add_from_cat.setCursor(Qt.PointingHandCursor)
        self.cc_btn_add_from_cat.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
        """)
        self.cc_btn_add_from_cat.clicked.connect(self.cc_show_category_menu)
        input_header.addWidget(self.cc_btn_add_from_cat)

        folders_layout.addLayout(input_header)

        # Input folders list
        self.cc_multi_folder_container = QWidget()
        self.cc_multi_folder_container.setStyleSheet("background: transparent;")
        self.cc_multi_folder_layout = QVBoxLayout(self.cc_multi_folder_container)
        self.cc_multi_folder_layout.setContentsMargins(0, 0, 0, 0)
        self.cc_multi_folder_layout.setSpacing(8)
        self.cc_multi_folder_list = []
        folders_layout.addWidget(self.cc_multi_folder_container)

        content_layout.addWidget(folders_card)

        # ============ B-ROLL & OUTPUT SECTION ============
        paths_card = QFrame()
        paths_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        paths_layout = QVBoxLayout(paths_card)
        paths_layout.setContentsMargins(20, 16, 20, 16)
        paths_layout.setSpacing(16)

        # B-Roll folder
        broll_header = QLabel("B-Roll Folder")
        broll_header.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        paths_layout.addWidget(broll_header)

        broll_row = QHBoxLayout()
        broll_row.setSpacing(10)

        self.cc_broll_line_edit = QLineEdit()
        self.cc_broll_line_edit.setPlaceholderText("Select B-roll folder...")
        self.cc_broll_line_edit.setFixedHeight(42)
        self.cc_broll_line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        broll_row.addWidget(self.cc_broll_line_edit)

        btn_broll_browse = QPushButton("Browse")
        btn_broll_browse.setFixedSize(90, 42)
        btn_broll_browse.setCursor(Qt.PointingHandCursor)
        btn_broll_browse.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_broll_browse.clicked.connect(self._cc_browse_broll_folder)
        broll_row.addWidget(btn_broll_browse)

        paths_layout.addLayout(broll_row)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #2a2a2a;")
        paths_layout.addWidget(divider)

        # Output folder
        output_header = QLabel("Output Folder")
        output_header.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        paths_layout.addWidget(output_header)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)

        self.cc_output_line_edit = QLineEdit()
        self.cc_output_line_edit.setPlaceholderText("Select output folder...")
        self.cc_output_line_edit.setFixedHeight(42)
        self.cc_output_line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_gradient()[0]}; }}
            QLineEdit::placeholder {{ color: #6e7681; }}
        """)
        output_row.addWidget(self.cc_output_line_edit)

        btn_output_browse = QPushButton("Browse")
        btn_output_browse.setFixedSize(90, 42)
        btn_output_browse.setCursor(Qt.PointingHandCursor)
        btn_output_browse.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_output_browse.clicked.connect(self._cc_browse_output_folder)
        output_row.addWidget(btn_output_browse)

        btn_cc_clean_out = QPushButton("Clean")
        btn_cc_clean_out.setFixedSize(90, 42)
        btn_cc_clean_out.setCursor(Qt.PointingHandCursor)
        btn_cc_clean_out.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #b91c1c; }
        """)
        btn_cc_clean_out.clicked.connect(self._cc_manual_clean_output_folder)
        output_row.addWidget(btn_cc_clean_out)

        # Clean All button - cleans both input and output
        btn_cc_clean_all = QPushButton("Clean All")
        btn_cc_clean_all.setFixedSize(100, 42)
        btn_cc_clean_all.setCursor(Qt.PointingHandCursor)
        btn_cc_clean_all.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ea580c);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #c2410c);
            }
        """)
        btn_cc_clean_all.setToolTip("Clean ALL files from both Input and Output folders")
        btn_cc_clean_all.clicked.connect(self._cc_clean_all_folders)
        output_row.addWidget(btn_cc_clean_all)

        paths_layout.addLayout(output_row)
        content_layout.addWidget(paths_card)

        # ============ OPTIONS SECTION ============
        options_card = QFrame()
        options_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(20, 16, 20, 16)
        options_layout.setSpacing(16)

        options_title = QLabel("Options")
        options_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        options_layout.addWidget(options_title)

        saved_opts = self.config_manager.config.get('cc_quick_options', {})

        # Options toggles row
        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(10)

        self.cc_cb_clean_output = self._create_toggle_chip("Clean", saved_opts.get('clean_output', False))
        self.cc_cb_clean_output.stateChanged.connect(self._save_cc_quick_options)
        toggles_row.addWidget(self.cc_cb_clean_output)

        self.cc_cb_parallel = self._create_toggle_chip("Parallel", saved_opts.get('parallel', True))
        self.cc_cb_parallel.stateChanged.connect(self._save_cc_quick_options)
        toggles_row.addWidget(self.cc_cb_parallel)

        # Max parallel folders spinbox
        parallel_count_label = QLabel("Max:")
        parallel_count_label.setStyleSheet("color: #888888; font-size: 12px;")
        toggles_row.addWidget(parallel_count_label)

        self.cc_parallel_count_spin = QSpinBox()
        self.cc_parallel_count_spin.setRange(1, 10)
        self.cc_parallel_count_spin.setValue(saved_opts.get('max_parallel_folders', 3))
        self.cc_parallel_count_spin.setFixedSize(60, 32)
        self.cc_parallel_count_spin.setStyleSheet(f"""
            QSpinBox {{
                background: #1a1a1a;
                border: none;
                border-radius: 6px;
                padding: 0 8px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QSpinBox:focus {{ border-color: {_gradient()[0]}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: #2a2a2a;
                border: none;
                width: 16px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: #3a3a3a;
            }}
        """)
        self.cc_parallel_count_spin.setToolTip("Maximum folders to process simultaneously (1-10)")
        self.cc_parallel_count_spin.valueChanged.connect(self._save_cc_quick_options)
        toggles_row.addWidget(self.cc_parallel_count_spin)

        self.cc_cb_music = self._create_toggle_chip("Music", saved_opts.get('music', True))
        self.cc_cb_music.stateChanged.connect(self._save_cc_quick_options)
        toggles_row.addWidget(self.cc_cb_music)

        self.cc_cb_logo = self._create_toggle_chip("Logo", saved_opts.get('logo', False))
        self.cc_cb_logo.stateChanged.connect(self._save_cc_quick_options)
        toggles_row.addWidget(self.cc_cb_logo)

        self.cc_cb_animations = self._create_toggle_chip("Anim", saved_opts.get('animations', True))
        self.cc_cb_animations.stateChanged.connect(self._save_cc_quick_options)
        toggles_row.addWidget(self.cc_cb_animations)

        toggles_row.addStretch()
        options_layout.addLayout(toggles_row)

        # Thumbnail Mode row
        thumb_row = QHBoxLayout()
        thumb_row.setSpacing(10)

        thumb_label = QLabel("Thumbnail Mode:")
        thumb_label.setStyleSheet("color: #888888; font-size: 13px;")
        thumb_row.addWidget(thumb_label)

        # Get saved mode (default to title)
        cc_thumb_saved = saved_opts.get('thumb_mode', 'title')

        # OFF button - disable thumbnail generation
        self.cc_thumb_mode_off = QPushButton("OFF")
        self.cc_thumb_mode_off.setCheckable(True)
        self.cc_thumb_mode_off.setChecked(cc_thumb_saved == 'off')
        self.cc_thumb_mode_off.setFixedHeight(32)
        self.cc_thumb_mode_off.setCursor(Qt.PointingHandCursor)
        self.cc_thumb_mode_off.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:checked {
                background: #ef4444;
                color: #ffffff;
            }
            QPushButton:hover:!checked { background: #3a3a3a; color: #ffffff; }
        """)
        self.cc_thumb_mode_off.clicked.connect(lambda: self._cc_set_thumb_mode("off"))
        thumb_row.addWidget(self.cc_thumb_mode_off)

        # Title mode button (DEFAULT)
        self.cc_thumb_mode_title = QPushButton("Title")
        self.cc_thumb_mode_title.setCheckable(True)
        self.cc_thumb_mode_title.setChecked(cc_thumb_saved == 'title')
        self.cc_thumb_mode_title.setFixedHeight(32)
        self.cc_thumb_mode_title.setCursor(Qt.PointingHandCursor)
        self.cc_thumb_mode_title.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:checked {
                background: #f59e0b;
                color: #000;
            }
            QPushButton:hover:!checked { background: #3a3a3a; color: #ffffff; }
        """)
        self.cc_thumb_mode_title.clicked.connect(lambda: self._cc_set_thumb_mode("title"))
        thumb_row.addWidget(self.cc_thumb_mode_title)

        # Script mode button
        self.cc_thumb_mode_script = QPushButton("Script")
        self.cc_thumb_mode_script.setCheckable(True)
        self.cc_thumb_mode_script.setChecked(cc_thumb_saved == 'script')
        self.cc_thumb_mode_script.setFixedHeight(32)
        self.cc_thumb_mode_script.setCursor(Qt.PointingHandCursor)
        self.cc_thumb_mode_script.setStyleSheet(f"""
            QPushButton {{
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:checked {{
                background: {_gradient()[0]};
                color: #ffffff;
            }}
            QPushButton:hover:!checked {{ background: #3a3a3a; color: #ffffff; }}
        """)
        self.cc_thumb_mode_script.clicked.connect(lambda: self._cc_set_thumb_mode("script"))
        thumb_row.addWidget(self.cc_thumb_mode_script)

        thumb_row.addStretch()
        options_layout.addLayout(thumb_row)

        content_layout.addWidget(options_card)

        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # ============ BOTTOM ACTION BAR ============
        layout.addSpacing(16)

        action_bar = QFrame()
        action_bar.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 12px;
            }
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(20, 14, 20, 14)
        action_layout.setSpacing(16)

        self.cc_status_label = QLabel("Ready to process")
        self.cc_status_label.setStyleSheet("color: #888888; font-size: 13px;")
        action_layout.addWidget(self.cc_status_label)

        self.cc_progress_bar = QProgressBar()
        self.cc_progress_bar.setValue(0)
        self.cc_progress_bar.setTextVisible(False)
        self.cc_progress_bar.setFixedHeight(6)
        self.cc_progress_bar.setMinimumWidth(180)
        self.cc_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #2a2a2a;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                border-radius: 3px;
            }}
        """)
        action_layout.addWidget(self.cc_progress_bar)

        action_layout.addStretch()

        self.cc_btn_stop = QPushButton("Stop")
        self.cc_btn_stop.setFixedSize(90, 42)
        self.cc_btn_stop.setCursor(Qt.PointingHandCursor)
        self.cc_btn_stop.setEnabled(False)
        self.cc_btn_stop.clicked.connect(self.stop_content_creator)
        self.cc_btn_stop.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #ef4444; }
            QPushButton:disabled { background: #2a2a2a; color: #555555; }
        """)
        action_layout.addWidget(self.cc_btn_stop)

        self.cc_btn_run = QPushButton("Start Processing")
        self.cc_btn_run.setFixedSize(150, 42)
        self.cc_btn_run.setCursor(Qt.PointingHandCursor)
        self.cc_btn_run.clicked.connect(self.run_content_creator)
        self.cc_btn_run.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[0]}, stop:1 {_accent()});
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_gradient()[1]}, stop:1 {_gradient()[0]});
            }}
            QPushButton:disabled {{ background: #2a2a2a; color: #555555; }}
        """)
        action_layout.addWidget(self.cc_btn_run)

        layout.addWidget(action_bar)

        # Initialize worker
        self.cc_worker = None

        return page

    def refresh_cc_category_buttons(self):
        """Create clickable category buttons with different colors"""
        # Clear existing buttons
        for btn in self.cc_category_buttons.values():
            btn.setParent(None)
            btn.deleteLater()
        self.cc_category_buttons.clear()

        # Clear layout
        while self.cc_category_buttons_layout.count():
            item = self.cc_category_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Category colors
        category_colors = [
            ("#3b82f6", "#2563eb"),  # Blue
            ("#8b5cf6", "#7c3aed"),  # Purple
            ("#f59e0b", "#d97706"),  # Amber
            ("#ec4899", "#db2777"),  # Pink
            ("#06b6d4", "#0891b2"),  # Cyan
            ("#ef4444", "#dc2626"),  # Red
            ("#10b981", "#059669"),  # Emerald
        ]

        def get_style(color, hover_color, is_active):
            if is_active:
                return f"""
                    QPushButton {{
                        background: {color};
                        color: #ffffff;
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: {hover_color}; }}
                """
            else:
                return f"""
                    QPushButton {{
                        background: #2a2a2a;
                        color: {color};
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 500;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: #3a3a3a; color: #ffffff; }}
                """

        # "All" button (Indigo)
        btn_all = QPushButton("All")
        btn_all.setStyleSheet(get_style(_gradient()[0], _gradient()[1], self.cc_selected_category == "ALL"))
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.clicked.connect(lambda: self.cc_select_category("ALL"))
        self.cc_category_buttons_layout.addWidget(btn_all)
        self.cc_category_buttons["ALL"] = btn_all

        # Category buttons with different colors
        categories = self.config_manager.get_categories()
        profiles = self.config_manager.get_profiles()
        color_idx = 0

        for cat in categories:
            count = sum(1 for p in profiles.values() if p.get("category", "Default") == cat)
            if count == 0:
                continue

            color, hover_color = category_colors[color_idx % len(category_colors)]
            color_idx += 1

            btn = QPushButton(f"{cat} ({count})")
            btn.setStyleSheet(get_style(color, hover_color, self.cc_selected_category == cat))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=cat: self.cc_select_category(c))
            self.cc_category_buttons_layout.addWidget(btn)
            self.cc_category_buttons[cat] = btn

        self.cc_category_buttons_layout.addStretch()

    def cc_select_category(self, category):
        """Select a category for Create Video page and auto-fill paths"""
        self.cc_selected_category = category
        self.refresh_cc_category_buttons()
        self.update_cc_profile_checkboxes()

        # Auto-fill input/output paths if a specific category is selected (not ALL)
        if category != "ALL":
            cat_data = self.config_manager.get_category_data(category)
            cc_interviews_path = cat_data.get("cc_interviews_path", "")
            cc_broll_path = cat_data.get("cc_broll_path", "")
            cc_output_path = cat_data.get("cc_output_path", "")

            # Clear existing folder inputs first
            for item in self.cc_multi_folder_list[:]:
                item[0].setParent(None)
                item[0].deleteLater()
            self.cc_multi_folder_list.clear()

            # Scan for subfolders and add each as input
            if cc_interviews_path and Path(cc_interviews_path).exists():
                subfolders = sorted([
                    f for f in Path(cc_interviews_path).iterdir()
                    if f.is_dir() and not f.name.startswith('.')
                ])

                if subfolders:
                    for subfolder in subfolders:
                        line_edit = self.cc_add_folder_input()
                        if line_edit:
                            line_edit.setText(str(subfolder))
                else:
                    line_edit = self.cc_add_folder_input()
                    if line_edit:
                        line_edit.setText(cc_interviews_path)
            else:
                self.cc_add_folder_input()

            # Update B-Roll and Output paths
            if cc_broll_path and hasattr(self, 'cc_broll_line_edit'):
                self.cc_broll_line_edit.setText(cc_broll_path)
            if cc_output_path and hasattr(self, 'cc_output_line_edit'):
                self.cc_output_line_edit.setText(cc_output_path)

    def _cc_set_thumb_mode(self, mode):
        """Set thumbnail generation mode for Create Video"""
        self.cc_thumb_mode_off.setChecked(mode == "off")
        self.cc_thumb_mode_title.setChecked(mode == "title")
        self.cc_thumb_mode_script.setChecked(mode == "script")
        # Save with mode directly to avoid timing issues
        self._save_cc_quick_options(thumb_mode_override=mode)

    def _rv_set_thumb_mode(self, mode):
        """Set thumbnail generation mode for Recreate Video"""
        self.rv_thumb_mode_off.setChecked(mode == "off")
        self.rv_thumb_mode_title.setChecked(mode == "title")
        self.rv_thumb_mode_script.setChecked(mode == "script")
        self._save_quick_options()

    def _save_cc_quick_options(self, state=None, thumb_mode_override=None):
        """Save Create Video quick options to config"""
        try:
            max_parallel = self.cc_parallel_count_spin.value() if hasattr(self, 'cc_parallel_count_spin') else 3
            # Get thumb_mode (off, title, or script)
            if thumb_mode_override:
                thumb_mode = thumb_mode_override
            else:
                thumb_mode = "title"  # default
                if hasattr(self, 'cc_thumb_mode_off') and self.cc_thumb_mode_off.isChecked():
                    thumb_mode = "off"
                elif hasattr(self, 'cc_thumb_mode_title') and self.cc_thumb_mode_title.isChecked():
                    thumb_mode = "title"
                elif hasattr(self, 'cc_thumb_mode_script') and self.cc_thumb_mode_script.isChecked():
                    thumb_mode = "script"

            opts = {
                'clean_output': self.cc_cb_clean_output.isChecked(),
                'parallel': self.cc_cb_parallel.isChecked(),
                'max_parallel_folders': max_parallel,
                'music': self.cc_cb_music.isChecked(),
                'logo': self.cc_cb_logo.isChecked(),
                'animations': self.cc_cb_animations.isChecked(),
                'thumb_mode': thumb_mode,
            }
            self.config_manager.config['cc_quick_options'] = opts

            # Also save to processing_settings so content_creator.py can read it
            if 'processing_settings' not in self.config_manager.config:
                self.config_manager.config['processing_settings'] = {}
            self.config_manager.config['processing_settings']['enable_parallel_folders'] = self.cc_cb_parallel.isChecked()
            self.config_manager.config['processing_settings']['max_parallel_folders'] = max_parallel
            self.config_manager.config['processing_settings']['thumb_mode'] = thumb_mode

            self.config_manager.save()
        except Exception as e:
            print(f"Error saving CC options: {e}")

    def _cc_browse_output_folder(self):
        """Browse for Create Video output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.cc_output_line_edit.setText(folder)

    def _cc_manual_clean_output_folder(self):
        """Manually clean the Create Video output folder"""
        output_path = self.cc_output_line_edit.text().strip()
        if not output_path:
            QMessageBox.warning(self, "No Folder", "Please select an output folder first.")
            return
        self._clean_output_folder(output_path)

    def _cc_clean_all_folders(self):
        """Clean Input and Output folders from category settings for Create Video"""
        # Get selected category to find the category paths
        selected_cat = getattr(self, 'cc_selected_category', 'ALL')

        folders_to_clean = []

        if selected_cat and selected_cat != "ALL":
            # Get category data
            cat_data = self.config_manager.get_category_data(selected_cat)

            # Get Input folder (cc_interviews_path) from category
            input_path = cat_data.get('cc_interviews_path', '')
            if input_path and os.path.exists(input_path):
                folders_to_clean.append(("Input", input_path))

            # Get Output folder from category
            output_path = cat_data.get('cc_output_path', '')
            if output_path and os.path.exists(output_path):
                folders_to_clean.append(("Output", output_path))
        else:
            # No category selected - use the output field directly
            output_path = self.cc_output_line_edit.text().strip()
            if output_path and os.path.exists(output_path):
                folders_to_clean.append(("Output", output_path))

        if not folders_to_clean:
            QMessageBox.warning(self, "No Folders", "No valid folders found to clean.\n\nPlease add input folders and/or select an output folder first.")
            return

        # Count total items
        total_items = 0
        for _, folder_path in folders_to_clean:
            try:
                total_items += len(os.listdir(folder_path))
            except:
                pass

        if total_items == 0:
            QMessageBox.information(self, "Already Clean", "All folders are already empty!")
            return

        # Build confirmation message
        folder_list = "\n".join([f"  • {name}: {path}" for name, path in folders_to_clean])

        # Custom styled confirmation dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("Clean All Folders")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"<b>Delete {total_items} items from all folders?</b>")
        msg.setInformativeText(f"This will permanently delete all files and subfolders in:\n\n{folder_list}\n\nThis action cannot be undone!")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("""
            QMessageBox { background-color: #1a1a2e; }
            QMessageBox QLabel { color: #e2e8f0; font-size: 13px; }
            QPushButton {
                background-color: #555555; color: white; border: none;
                padding: 8px 20px; border-radius: 6px; font-weight: 600; min-width: 80px;
            }
            QPushButton:hover { background-color: #555555; }
        """)

        if msg.exec_() == QMessageBox.Yes:
            cleaned_count = 0
            errors = []

            for folder_name, folder_path in folders_to_clean:
                try:
                    items = os.listdir(folder_path)
                    for item in items:
                        item_path = os.path.join(folder_path, item)
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                cleaned_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                cleaned_count += 1
                        except Exception as e:
                            errors.append(f"{item}: {str(e)}")
                except Exception as e:
                    errors.append(f"{folder_name}: {str(e)}")

            if errors:
                QMessageBox.warning(self, "Partial Success",
                    f"Cleaned {cleaned_count} items but had some errors:\n\n" + "\n".join(errors[:5]))
            else:
                QMessageBox.information(self, "Success",
                    f"Successfully cleaned {cleaned_count} items from all folders!")

    def update_cc_profile_checkboxes(self):
        """Update Content Creator profile checkboxes - modern chip style (same as Recreate Video)"""
        # Save currently selected profiles before clearing
        if not hasattr(self, 'cc_selected_profile_names'):
            self.cc_selected_profile_names = set()

        for name, cb in self.cc_profile_checkboxes.items():
            if cb.isChecked():
                self.cc_selected_profile_names.add(name)
            else:
                self.cc_selected_profile_names.discard(name)

        # Clear existing checkboxes
        for cb in self.cc_profile_checkboxes.values():
            cb.setParent(None)
            cb.deleteLater()
        self.cc_profile_checkboxes.clear()

        # Clear existing layout items
        while self.cc_profile_checkboxes_layout.count():
            item = self.cc_profile_checkboxes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get selected category
        selected_cat = getattr(self, 'cc_selected_category', 'ALL')
        max_channels = self.license_manager.get_max_channels()
        grouped = self.config_manager.get_profiles_by_category()

        channel_count = 0

        for category, profiles in grouped.items():
            if selected_cat != "ALL" and category != selected_cat:
                continue

            if profiles:
                for name, data in profiles.items():
                    voice = data.get('default_voice', data.get('voice', 'Not set'))
                    cb = QCheckBox(name)
                    cb.setToolTip(f"Voice: {voice}")
                    cb.setCursor(Qt.PointingHandCursor)

                    channel_count += 1
                    if channel_count > max_channels:
                        cb.setStyleSheet("""
                            QCheckBox {
                                color: #555555;
                                font-size: 13px;
                                padding: 8px 16px;
                                background: #252525;
                                border-radius: 8px;
                            }
                            QCheckBox::indicator { width: 0; height: 0; }
                        """)
                        cb.setEnabled(False)
                    else:
                        if name in self.cc_selected_profile_names:
                            cb.setChecked(True)
                            cb.setStyleSheet(f"""
                                QCheckBox {{
                                    color: #ffffff;
                                    font-size: 13px;
                                    font-weight: 600;
                                    padding: 8px 16px;
                                    background: {_gradient()[0]};
                                    border-radius: 8px;
                                }}
                                QCheckBox:hover {{ background: {_gradient()[1]}; }}
                                QCheckBox::indicator {{ width: 0; height: 0; }}
                            """)
                        else:
                            cb.setStyleSheet("""
                                QCheckBox {
                                    color: #888888;
                                    font-size: 13px;
                                    padding: 8px 16px;
                                    background: #2a2a2a;
                                    border-radius: 8px;
                                }
                                QCheckBox:hover { color: #ffffff; background: #3a3a3a; }
                                QCheckBox::indicator { width: 0; height: 0; }
                            """)

                        cb.stateChanged.connect(lambda state, c=cb, n=name: self._cc_update_channel_chip_style(c, n, state))

                    self.cc_profile_checkboxes_layout.addWidget(cb)
                    self.cc_profile_checkboxes[name] = cb

        self.cc_profile_checkboxes_layout.addStretch()

    def cc_select_all_profiles(self):
        """Select all Content Creator profiles"""
        if not hasattr(self, 'cc_selected_profile_names'):
            self.cc_selected_profile_names = set()
        for name, cb in self.cc_profile_checkboxes.items():
            cb.setChecked(True)
            self.cc_selected_profile_names.add(name)

    def cc_select_no_profiles(self):
        """Deselect all Content Creator profiles"""
        if not hasattr(self, 'cc_selected_profile_names'):
            self.cc_selected_profile_names = set()
        for name, cb in self.cc_profile_checkboxes.items():
            cb.setChecked(False)
            self.cc_selected_profile_names.discard(name)

    def _cc_update_channel_chip_style(self, checkbox, name, state):
        """Update channel chip style when checked/unchecked for Create Video"""
        if state == Qt.Checked:
            self.cc_selected_profile_names.add(name)
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                    background: {_gradient()[0]};
                    border-radius: 8px;
                }}
                QCheckBox:hover {{ background: {_gradient()[1]}; }}
                QCheckBox::indicator {{ width: 0; height: 0; }}
            """)
        else:
            self.cc_selected_profile_names.discard(name)
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #888888;
                    font-size: 13px;
                    padding: 8px 16px;
                    background: #2a2a2a;
                    border-radius: 8px;
                }
                QCheckBox:hover { color: #ffffff; background: #3a3a3a; }
                QCheckBox::indicator { width: 0; height: 0; }
            """)

    def cc_add_folder_input(self):
        """Add a new folder input row - simple design for Create Video"""
        folder_num = len(self.cc_multi_folder_list) + 1

        # Main container for folder card - clean minimal style
        row_widget = QFrame()
        row_widget.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        main_layout = QHBoxLayout(row_widget)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(14)

        # Number badge
        label = QLabel(f"{folder_num}")
        label.setFixedSize(30, 30)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            background: {_gradient()[0]};
            color: #ffffff;
            font-weight: 700;
            font-size: 14px;
            border-radius: 15px;
        """)
        main_layout.addWidget(label)

        # Path input - same style as output folder
        line_edit = QLineEdit()
        line_edit.setPlaceholderText("Select input folder...")
        line_edit.setFixedHeight(42)
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_accent()}; }}
            QLineEdit::placeholder {{ color: #666666; }}
        """)
        main_layout.addWidget(line_edit, 1)

        # Browse button
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedSize(90, 42)
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_browse.clicked.connect(lambda: self._cc_browse_folder(line_edit))
        main_layout.addWidget(btn_browse)

        # Remove button
        btn_remove = QPushButton("Remove")
        btn_remove.setFixedSize(100, 40)
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #dc2626; }
        """)
        btn_remove.clicked.connect(lambda: self._cc_remove_folder_input(row_widget))
        main_layout.addWidget(btn_remove)

        # Store label reference for renumbering
        row_widget.label = label

        self.cc_multi_folder_layout.addWidget(row_widget)
        self.cc_multi_folder_list.append((row_widget, line_edit))

        # Renumber all folders
        self._cc_renumber_folders()

        return line_edit  # Return for pre-filling path

    def _cc_browse_folder(self, line_edit):
        """Browse for folder in Create Video"""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder", line_edit.text())
        if folder:
            line_edit.setText(folder)

    def _cc_remove_folder_input(self, row_widget):
        """Remove a folder input row from Create Video"""
        # Don't remove if only one left
        if len(self.cc_multi_folder_list) <= 1:
            return

        # Find and remove from list
        for i, item in enumerate(self.cc_multi_folder_list):
            if item[0] == row_widget:
                self.cc_multi_folder_list.pop(i)
                break

        # Remove widget
        row_widget.setParent(None)
        row_widget.deleteLater()

        # Renumber remaining folders
        self._cc_renumber_folders()

    def _cc_renumber_folders(self):
        """Renumber folder labels after add/remove"""
        for i, item in enumerate(self.cc_multi_folder_list):
            widget = item[0]
            if hasattr(widget, 'label'):
                widget.label.setText(f"{i + 1}:")

    def _cc_browse_broll_folder(self):
        """Browse for B-Roll folder in Create Video"""
        folder = QFileDialog.getExistingDirectory(self, "Select B-Roll Folder", self.cc_broll_line_edit.text())
        if folder:
            self.cc_broll_line_edit.setText(folder)

    def _cc_browse_custom_broll(self, line_edit):
        """Browse for custom B-roll folder for specific folder input"""
        folder = QFileDialog.getExistingDirectory(self, "Select Custom B-Roll Folder", line_edit.text())
        if folder:
            line_edit.setText(folder)

    def cc_show_category_menu(self):
        """Show dropdown menu with categories that have CC input paths"""
        from PyQt5.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 5px;
            }}
            QMenu::item {{
                color: #e0e0e0;
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {_gradient()[0]};
            }}
        """)

        categories = self.config_manager.get("categories", default=["Default"])
        has_items = False

        for cat in categories:
            cat_data = self.config_manager.get_category_data(cat)
            cc_interviews_path = cat_data.get("cc_interviews_path", "")

            if cc_interviews_path:
                has_items = True
                action = menu.addAction(f"📁 {cat}")
                action.setData(cc_interviews_path)
                action.triggered.connect(lambda checked, p=cc_interviews_path, o=cat_data.get("cc_output_path", ""), b=cat_data.get("cc_broll_path", ""): self.cc_add_folder_from_category(p, o, b))

        if not has_items:
            action = menu.addAction("No categories with CC paths")
            action.setEnabled(False)

        # Show menu below the button
        menu.exec_(self.cc_btn_add_from_cat.mapToGlobal(
            self.cc_btn_add_from_cat.rect().bottomLeft()
        ))

    def cc_add_folder_from_category(self, interviews_path, output_path="", broll_path=""):
        """Add folders from a category - scans for subfolders like Recreate Video"""
        if interviews_path and Path(interviews_path).exists():
            # Scan for subfolders
            subfolders = sorted([
                f for f in Path(interviews_path).iterdir()
                if f.is_dir() and not f.name.startswith('.')
            ])

            if subfolders:
                # Add each subfolder as input
                for subfolder in subfolders:
                    line_edit = self.cc_add_folder_input()
                    if line_edit:
                        line_edit.setText(str(subfolder))
            else:
                # No subfolders, add the main path
                line_edit = self.cc_add_folder_input()
                if line_edit:
                    line_edit.setText(interviews_path)

            # Also fill output and broll if provided
            if output_path and hasattr(self, 'cc_output_line_edit'):
                self.cc_output_line_edit.setText(output_path)
            if broll_path and hasattr(self, 'cc_broll_selector'):
                self.cc_broll_selector.set_path(broll_path)

    def _cc_channel_selected(self, state, name, data):
        """Auto-fill folder paths when a channel is selected in Create Video"""
        if state == 2:  # Qt.Checked
            # Get the channel's category
            category = data.get('category', 'Default')
            # Get paths from category (not from channel)
            cat_data = self.config_manager.get_category_data(category)

            interviews_path = cat_data.get('cc_interviews_path', '')
            broll = cat_data.get('cc_broll_path', '')
            output = cat_data.get('cc_output_path', '')

            # Clear existing folder inputs
            for item in self.cc_multi_folder_list[:]:
                item[0].setParent(None)
                item[0].deleteLater()
            self.cc_multi_folder_list.clear()

            # Scan interviews folder for subfolders (like Recreate Video)
            if interviews_path and Path(interviews_path).exists():
                subfolders = sorted([
                    f for f in Path(interviews_path).iterdir()
                    if f.is_dir() and not f.name.startswith('.')
                ])

                if subfolders:
                    # Add each subfolder as input
                    for subfolder in subfolders:
                        line_edit = self.cc_add_folder_input()
                        if line_edit:
                            line_edit.setText(str(subfolder))
                else:
                    # No subfolders, add one input with the main path
                    line_edit = self.cc_add_folder_input()
                    if line_edit:
                        line_edit.setText(interviews_path)
            else:
                # No valid path, add one empty input
                self.cc_add_folder_input()

            # Update B-Roll and Output
            if broll and hasattr(self, 'cc_broll_selector'):
                self.cc_broll_selector.set_path(broll)
            if output and hasattr(self, 'cc_output_line_edit'):
                self.cc_output_line_edit.setText(output)

    def safe_run_content_creator(self):
        """Safe wrapper for run_content_creator with exception handling"""
        try:
            self.run_content_creator()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Content Creator failed:\n{e}")

    def run_content_creator(self):
        """Run the Content Creator pipeline"""
        try:
            # SECURITY: Verify license before running pipeline
            is_licensed, message, _ = self.license_manager.check_license()
            if not is_licensed:
                QMessageBox.warning(self, "License Required", f"Cannot run pipeline: {message}")
                return

            # Get all interview folders from multi-folder list
            interview_folders = []
            for widget, line_edit in self.cc_multi_folder_list:
                path = line_edit.text().strip()
                if path and Path(path).exists():
                    interview_folders.append(path)

            broll_folder = self.cc_broll_line_edit.text().strip()
            output_folder = self.cc_output_line_edit.text().strip()

            if not interview_folders:
                QMessageBox.warning(self, "Missing Input", "Please select at least one interviews folder.")
                return

            if not broll_folder:
                QMessageBox.warning(self, "Missing Input", "Please select a B-roll folder.")
                return
        except Exception as e:
            import traceback
            print(f"ERROR in run_content_creator: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error starting Content Creator:\n{e}")
            return

        if not output_folder:
            QMessageBox.warning(self, "Missing Input", "Please select an output folder.")
            return

        # Clean output folder if checkbox is checked
        if self.cc_cb_clean_output.isChecked():
            folder = Path(output_folder)
            if folder.exists():
                files = list(folder.glob("*"))
                if files:
                    for item in files:
                        try:
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                        except Exception as e:
                            self.log(f"⚠️ Could not delete {item.name}: {e}")
                    self.log(f"🗑️ Cleaned {len(files)} item(s) from output folder")

        # Get selected channels
        selected_channels = []
        for name, cb in self.cc_profile_checkboxes.items():
            if cb.isChecked():
                selected_channels.append(name)

        if not selected_channels:
            QMessageBox.warning(self, "Error", "Please select at least one channel.")
            return

        # Clear log and update UI
        self.log_output.clear()
        self.cc_btn_run.setEnabled(False)
        self.cc_btn_stop.setEnabled(True)
        # Also update Log page buttons so Stop works from there
        self.log_run_btn.setEnabled(False)
        self.log_cc_run_btn.setEnabled(False)
        self.log_stop_btn.setEnabled(True)
        self.cc_progress_bar.setValue(0)
        self.cc_progress_bar.setFormat("Starting...")
        self.cc_status_label.setText("Content Creator running...")

        # Switch to Log page
        self.switch_page(5)  # Log page index

        # Start worker (pass list of interview folders)
        self.cc_worker = ContentCreatorWorker(
            CONTENT_CREATOR_SCRIPT,
            interview_folders,  # Now a list of folders
            broll_folder,
            output_folder,
            selected_channels
        )
        self.cc_worker.progress.connect(self.on_cc_progress)
        self.cc_worker.finished.connect(self.on_cc_finished)
        self.cc_worker.start()

        start_msg = f"🎬 Starting Content Creator with {len(selected_channels)} channel(s)..."
        self.log_output.append(start_msg)

    def stop_content_creator(self):
        """Stop the Content Creator pipeline"""
        if self.cc_worker:
            self.cc_worker.stop()
            self.log_output.append("⏹️ Stopping Content Creator...")

    def on_cc_progress(self, message):
        """Handle Content Creator progress messages"""
        # Write to Log page
        self.log_output.append(message)
        self.log_output.moveCursor(QTextCursor.End)

        # Update progress bar based on step
        message_lower = message.lower()
        if "step 1" in message_lower:
            self.cc_progress_bar.setValue(15)
            self.cc_progress_bar.setFormat("Step 1/8")
        elif "step 2" in message_lower:
            self.cc_progress_bar.setValue(25)
            self.cc_progress_bar.setFormat("Step 2/8")
        elif "step 3" in message_lower:
            self.cc_progress_bar.setValue(35)
            self.cc_progress_bar.setFormat("Step 3/8")
        elif "step 4" in message_lower:
            self.cc_progress_bar.setValue(50)
            self.cc_progress_bar.setFormat("Step 4/8")
        elif "step 5" in message_lower:
            self.cc_progress_bar.setValue(65)
            self.cc_progress_bar.setFormat("Step 5/8")
        elif "step 6" in message_lower:
            self.cc_progress_bar.setValue(75)
            self.cc_progress_bar.setFormat("Step 6/8")
        elif "step 7" in message_lower:
            self.cc_progress_bar.setValue(85)
            self.cc_progress_bar.setFormat("Step 7/8")
        elif "step 8" in message_lower:
            self.cc_progress_bar.setValue(95)
            self.cc_progress_bar.setFormat("Step 8/8")

    def on_cc_finished(self, success):
        """Handle Content Creator completion"""
        self.cc_btn_run.setEnabled(True)
        self.cc_btn_stop.setEnabled(False)
        # Also re-enable Log page buttons
        self.log_run_btn.setEnabled(True)
        self.log_cc_run_btn.setEnabled(True)
        self.log_stop_btn.setEnabled(False)

        if success:
            self.cc_progress_bar.setValue(100)
            self.cc_progress_bar.setFormat("Complete!")
            self.cc_status_label.setText("✅ Content Creator completed successfully!")
            QMessageBox.information(self, "Success!", "Content Creator completed successfully!\n\nCheck your output folder for results.")
        else:
            self.cc_progress_bar.setFormat("Failed")
            self.cc_status_label.setText("❌ Content Creator failed - check log for errors")
            QMessageBox.warning(self, "Failed", "Content Creator failed!\n\nCheck the log for details.")

    # ========================================================================
    # ACTIONS
    # ========================================================================

    def toggle_custom_broll(self, state):
        """Show/hide custom B-roll folder selector"""
        self.broll_folder_widget.setVisible(state == Qt.Checked)

    def browse_broll_folder(self):
        """Browse for custom B-roll folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Custom B-roll Folder")
        if folder:
            self.broll_folder_edit.setText(folder)

    def add_folder_input(self):
        """Add a new folder input row with expandable custom settings"""
        folder_num = len(self.multi_folder_list) + 1

        # Main container for folder row - clean minimal style
        row_widget = QFrame()
        row_widget.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        card_layout = QVBoxLayout(row_widget)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ===== TOP ROW: Number + Path + Buttons =====
        top_row = QWidget()
        top_row.setStyleSheet("background: transparent;")
        main_layout = QHBoxLayout(top_row)
        main_layout.setContentsMargins(0, 8, 0, 8)
        main_layout.setSpacing(10)

        # Number badge
        label = QLabel(f"{folder_num}")
        label.setFixedSize(30, 30)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            background: {_gradient()[0]};
            color: #ffffff;
            font-weight: 700;
            font-size: 14px;
            border-radius: 15px;
        """)
        main_layout.addWidget(label)

        # Path input - same style as output folder
        line_edit = QLineEdit()
        line_edit.setPlaceholderText("Select input folder...")
        line_edit.setFixedHeight(42)
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: #e0e0e0;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {_accent()}; }}
            QLineEdit::placeholder {{ color: #666666; }}
        """)
        main_layout.addWidget(line_edit, 1)

        # Browse button
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedSize(90, 42)
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background: {_gradient()[0]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {_gradient()[1]}; }}
        """)
        btn_browse.clicked.connect(lambda: self._browse_folder(line_edit))
        main_layout.addWidget(btn_browse)

        # Settings toggle button
        btn_settings = QPushButton("Settings")
        btn_settings.setFixedSize(100, 40)
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.setCheckable(True)
        btn_settings.setStyleSheet(f"""
            QPushButton {{
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #3a3a3a; color: #ffffff; }}
            QPushButton:checked {{ background: {_gradient()[0]}; color: #ffffff; }}
        """)
        main_layout.addWidget(btn_settings)

        # Remove button
        btn_remove = QPushButton("Remove")
        btn_remove.setFixedSize(100, 40)
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #dc2626; }
        """)
        btn_remove.clicked.connect(lambda: self.remove_folder_input(row_widget))
        main_layout.addWidget(btn_remove)

        card_layout.addWidget(top_row)

        # ===== CUSTOM SETTINGS PANEL (Hidden by default) =====
        settings_panel = QWidget()
        settings_panel.setStyleSheet("background: #252525; border-radius: 8px; margin-top: 4px;")
        settings_panel.setVisible(False)
        settings_layout = QHBoxLayout(settings_panel)
        settings_layout.setContentsMargins(44, 12, 16, 12)
        settings_layout.setSpacing(16)

        # Custom Channel checkbox + dropdown
        channel_checkbox = QCheckBox("Custom Channel")
        channel_checkbox.setCursor(Qt.PointingHandCursor)
        channel_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: #888888;
                font-size: 13px;
                font-weight: 500;
            }}
            QCheckBox:checked {{ color: #ffffff; }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #3a3d45;
                background: #2a2a2a;
            }}
            QCheckBox::indicator:checked {{
                background: {_gradient()[0]};
                border-color: {_gradient()[0]};
            }}
        """)
        settings_layout.addWidget(channel_checkbox)

        channel_combo = QComboBox()
        channel_combo.setFixedSize(180, 36)
        channel_combo.setEnabled(False)
        channel_combo.setStyleSheet(f"""
            QComboBox {{
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                color: #888888;
                padding: 0 12px;
                font-size: 13px;
            }}
            QComboBox:enabled {{ color: #ffffff; }}
            QComboBox:disabled {{ background: #16181d; color: #555555; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background: #2a2a2a;
                border: none;
                color: #ffffff;
                selection-background-color: {_gradient()[0]};
            }}
        """)
        # Populate channel dropdown
        profiles = self.config_manager.get_profiles()
        for name in profiles.keys():
            channel_combo.addItem(name)
        channel_checkbox.stateChanged.connect(lambda state: channel_combo.setEnabled(state == Qt.Checked))
        settings_layout.addWidget(channel_combo)

        settings_layout.addSpacing(20)

        # Custom B-roll checkbox + path + browse
        broll_checkbox = QCheckBox("Custom B-roll")
        broll_checkbox.setCursor(Qt.PointingHandCursor)
        broll_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: #888888;
                font-size: 13px;
                font-weight: 500;
            }}
            QCheckBox:checked {{ color: #ffffff; }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #3a3d45;
                background: #2a2a2a;
            }}
            QCheckBox::indicator:checked {{
                background: {_gradient()[0]};
                border-color: {_gradient()[0]};
            }}
        """)
        settings_layout.addWidget(broll_checkbox)

        broll_edit = QLineEdit()
        broll_edit.setPlaceholderText("B-roll folder path...")
        broll_edit.setFixedHeight(36)
        broll_edit.setEnabled(False)
        broll_edit.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:disabled { background: #16181d; color: #555555; }
            QLineEdit::placeholder { color: #6e7681; }
        """)
        settings_layout.addWidget(broll_edit, 1)

        btn_broll_browse = QPushButton("...")
        btn_broll_browse.setFixedSize(40, 36)
        btn_broll_browse.setCursor(Qt.PointingHandCursor)
        btn_broll_browse.setEnabled(False)
        btn_broll_browse.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #888888;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #3a3a3a; color: #ffffff; }
            QPushButton:disabled { background: #16181d; color: #555555; }
        """)
        btn_broll_browse.clicked.connect(lambda: self._browse_broll_folder(broll_edit))
        broll_checkbox.stateChanged.connect(lambda state: broll_edit.setEnabled(state == Qt.Checked))
        broll_checkbox.stateChanged.connect(lambda state: btn_broll_browse.setEnabled(state == Qt.Checked))
        settings_layout.addWidget(btn_broll_browse)

        card_layout.addWidget(settings_panel)

        # Connect settings button to toggle panel
        btn_settings.clicked.connect(lambda checked: settings_panel.setVisible(checked))

        # Store references
        row_widget.label = label
        row_widget.channel_checkbox = channel_checkbox
        row_widget.channel_combo = channel_combo
        row_widget.broll_checkbox = broll_checkbox
        row_widget.broll_edit = broll_edit
        row_widget.settings_panel = settings_panel
        row_widget.btn_settings = btn_settings

        self.multi_folder_layout.addWidget(row_widget)
        self.multi_folder_list.append((row_widget, line_edit))

        # Renumber all folders
        self._renumber_folders()

        return line_edit

    def _browse_broll_folder(self, line_edit):
        """Browse for B-roll folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select B-roll Folder")
        if folder:
            line_edit.setText(folder)

    def show_category_menu(self):
        """Show dropdown menu with categories that have input paths"""
        from PyQt5.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 5px;
            }}
            QMenu::item {{
                color: #e0e0e0;
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {_gradient()[0]};
            }}
        """)

        categories = self.config_manager.get("categories", default=["Default"])
        has_items = False

        for cat in categories:
            cat_data = self.config_manager.get_category_data(cat)
            input_path = cat_data.get("input_path", "")

            if input_path:
                has_items = True
                action = menu.addAction(f"📁 {cat}")
                action.setData(input_path)
                action.triggered.connect(lambda checked, p=input_path: self.add_folder_from_category(p))

        if not has_items:
            action = menu.addAction("No categories with paths")
            action.setEnabled(False)

        # Show menu below the button
        menu.exec_(self.btn_add_from_cat.mapToGlobal(
            self.btn_add_from_cat.rect().bottomLeft()
        ))

    def add_folder_from_category(self, path):
        """Add a folder input with pre-filled category path"""
        line_edit = self.add_folder_input()
        if line_edit and path:
            line_edit.setText(path)

    def _populate_channel_combo(self, combo):
        """Populate a channel combo box with all profiles"""
        combo.clear()
        profiles = self.config_manager.get_profiles()
        for name, data in profiles.items():
            voice = data.get('default_voice', data.get('voice', ''))
            combo.addItem(f"🎬 {name}", name)

    def _browse_folder(self, line_edit):
        """Browse for folder and set path"""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            line_edit.setText(folder)

    def remove_folder_input(self, row_widget):
        """Remove a folder input row"""
        # Don't remove if only one left
        if len(self.multi_folder_list) <= 1:
            return

        # Find and remove from list
        for i, item in enumerate(self.multi_folder_list):
            if item[0] == row_widget:
                self.multi_folder_list.pop(i)
                break

        # Remove widget
        row_widget.setParent(None)
        row_widget.deleteLater()

        # Renumber remaining folders
        self._renumber_folders()

    def _renumber_folders(self):
        """Renumber folder labels after add/remove"""
        for i, item in enumerate(self.multi_folder_list):
            widget = item[0]
            if hasattr(widget, 'label'):
                widget.label.setText(f"{i + 1}:")

    def _toggle_custom_settings(self, state):
        """Toggle custom settings visibility for all input folders"""
        show = state == 2  # Qt.Checked
        for item in self.multi_folder_list:
            widget = item[0]
            if hasattr(widget, 'custom_settings_container'):
                widget.custom_settings_container.setVisible(show)

    def refresh_category_buttons(self):
        """Create clickable category buttons with different colors"""
        # Clear existing buttons
        for btn in self.category_buttons.values():
            btn.setParent(None)
            btn.deleteLater()
        self.category_buttons.clear()

        # Clear layout
        while self.category_buttons_layout.count():
            item = self.category_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Category colors
        category_colors = [
            ("#3b82f6", "#2563eb"),  # Blue
            ("#8b5cf6", "#7c3aed"),  # Purple
            ("#f59e0b", "#d97706"),  # Amber
            ("#ec4899", "#db2777"),  # Pink
            ("#06b6d4", "#0891b2"),  # Cyan
            ("#ef4444", "#dc2626"),  # Red
            ("#10b981", "#059669"),  # Emerald
        ]

        def get_style(color, hover_color, is_active):
            if is_active:
                return f"""
                    QPushButton {{
                        background: {color};
                        color: #ffffff;
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: {hover_color}; }}
                """
            else:
                return f"""
                    QPushButton {{
                        background: #2a2a2a;
                        color: {color};
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 500;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: #3a3a3a; color: #ffffff; }}
                """

        # "All" button (Indigo)
        btn_all = QPushButton("All")
        btn_all.setStyleSheet(get_style(_gradient()[0], _gradient()[1], self.selected_category == "ALL"))
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.clicked.connect(lambda: self.select_category("ALL"))
        self.category_buttons_layout.addWidget(btn_all)
        self.category_buttons["ALL"] = btn_all

        # Category buttons with different colors
        categories = self.config_manager.get_categories()
        profiles = self.config_manager.get_profiles()
        color_idx = 0

        for cat in categories:
            count = sum(1 for p in profiles.values() if p.get("category", "Default") == cat)
            if count == 0:
                continue

            color, hover_color = category_colors[color_idx % len(category_colors)]
            color_idx += 1

            btn = QPushButton(f"{cat} ({count})")
            btn.setStyleSheet(get_style(color, hover_color, self.selected_category == cat))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=cat: self.select_category(c))
            self.category_buttons_layout.addWidget(btn)
            self.category_buttons[cat] = btn

        self.category_buttons_layout.addStretch()

    def select_category(self, category):
        """Select a category and update display, auto-fill paths"""
        self.selected_category = category
        self.refresh_category_buttons()
        self.update_profile_checkboxes()

        # Auto-fill input/output paths if a specific category is selected (not ALL)
        if category != "ALL":
            cat_data = self.config_manager.get_category_data(category)
            input_path = cat_data.get("input_path", "")
            output_path = cat_data.get("output_path", "")

            # ALWAYS clear existing folder inputs first when switching categories
            for item in self.multi_folder_list[:]:
                item[0].setParent(None)
                item[0].deleteLater()
            self.multi_folder_list.clear()

            # Scan for subfolders (VD-1, VD-2, etc.) and add each as input
            if input_path and Path(input_path).exists():
                # Find all subfolders
                subfolders = sorted([
                    f for f in Path(input_path).iterdir()
                    if f.is_dir() and not f.name.startswith('.')
                ])

                if subfolders:
                    # Add each subfolder as input
                    for subfolder in subfolders:
                        line_edit = self.add_folder_input()
                        if line_edit:
                            line_edit.setText(str(subfolder))
                else:
                    # No subfolders, add one input with the main path
                    line_edit = self.add_folder_input()
                    if line_edit:
                        line_edit.setText(input_path)
            else:
                # No valid input path, add one empty input row
                self.add_folder_input()

            # Update output path
            if output_path and hasattr(self, 'output_line_edit'):
                self.output_line_edit.setText(output_path)

    def update_profile_checkboxes(self):
        """Update profile checkboxes - modern chip style"""
        # Save currently selected profiles before clearing
        for name, cb in self.profile_checkboxes.items():
            if cb.isChecked():
                self.selected_profile_names.add(name)
            else:
                self.selected_profile_names.discard(name)

        # Clear existing checkboxes
        for cb in self.profile_checkboxes.values():
            cb.setParent(None)
            cb.deleteLater()
        self.profile_checkboxes.clear()

        # Clear existing layout items
        while self.profile_checkboxes_layout.count():
            item = self.profile_checkboxes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get selected category
        selected_cat = getattr(self, 'selected_category', 'ALL')
        max_channels = self.license_manager.get_max_channels()
        grouped = self.config_manager.get_profiles_by_category()

        channel_count = 0

        for category, profiles in grouped.items():
            if selected_cat != "ALL" and category != selected_cat:
                continue

            if profiles:
                for name, data in profiles.items():
                    voice = data.get('default_voice', data.get('voice', 'Not set'))
                    cb = QCheckBox(name)
                    cb.setToolTip(f"Voice: {voice}")
                    cb.setCursor(Qt.PointingHandCursor)

                    channel_count += 1
                    if channel_count > max_channels:
                        cb.setStyleSheet("""
                            QCheckBox {
                                color: #555555;
                                font-size: 13px;
                                padding: 8px 16px;
                                background: #252525;
                                border-radius: 8px;
                            }
                            QCheckBox::indicator { width: 0; height: 0; }
                        """)
                        cb.setEnabled(False)
                    else:
                        if name in self.selected_profile_names:
                            cb.setChecked(True)
                            cb.setStyleSheet(f"""
                                QCheckBox {{
                                    color: #ffffff;
                                    font-size: 13px;
                                    font-weight: 600;
                                    padding: 8px 16px;
                                    background: {_gradient()[0]};
                                    border-radius: 8px;
                                }}
                                QCheckBox:hover {{ background: {_gradient()[1]}; }}
                                QCheckBox::indicator {{ width: 0; height: 0; }}
                            """)
                        else:
                            cb.setStyleSheet("""
                                QCheckBox {
                                    color: #888888;
                                    font-size: 13px;
                                    padding: 8px 16px;
                                    background: #2a2a2a;
                                    border-radius: 8px;
                                }
                                QCheckBox:hover { color: #ffffff; background: #3a3a3a; }
                                QCheckBox::indicator { width: 0; height: 0; }
                            """)

                        cb.stateChanged.connect(lambda state, c=cb, n=name: self._update_channel_chip_style(c, n, state))

                    self.profile_checkboxes_layout.addWidget(cb)
                    self.profile_checkboxes[name] = cb

        self.profile_checkboxes_layout.addStretch()

    def _update_channel_chip_style(self, checkbox, name, state):
        """Update channel chip style when checked/unchecked"""
        if state == Qt.Checked:
            self.selected_profile_names.add(name)
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                    background: {_gradient()[0]};
                    border-radius: 8px;
                }}
                QCheckBox:hover {{ background: {_gradient()[1]}; }}
                QCheckBox::indicator {{ width: 0; height: 0; }}
            """)
        else:
            self.selected_profile_names.discard(name)
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #888888;
                    font-size: 13px;
                    padding: 8px 16px;
                    background: #2a2a2a;
                    border-radius: 8px;
                }
                QCheckBox:hover { color: #ffffff; background: #3a3a3a; }
                QCheckBox::indicator { width: 0; height: 0; }
            """)

    def select_all_profiles(self):
        """Select all profile checkboxes (respecting channel limit)"""
        max_channels = self.license_manager.get_max_channels()
        count = 0
        for name, cb in self.profile_checkboxes.items():
            count += 1
            if count <= max_channels and cb.isEnabled():
                cb.setChecked(True)
                self.selected_profile_names.add(name)

    def select_no_profiles(self):
        """Deselect all profile checkboxes"""
        for name, cb in self.profile_checkboxes.items():
            cb.setChecked(False)
            self.selected_profile_names.discard(name)

    def update_profile_combo(self):
        """Update channel checkboxes (legacy function name for compatibility)"""
        self.update_profile_checkboxes()

    def update_channel_list(self):
        # Clear existing widgets
        while self.channel_grid_layout.count():
            item = self.channel_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profiles = self.config_manager.get_profiles()

        # Category colors mapping
        category_colors = {
            "WNBA": ("#f59e0b", "#78350f"),   # Amber
            "MMA": ("#ef4444", "#7f1d1d"),    # Red
            "TEN": ("#10b981", "#064e3b"),    # Emerald/Green
            "NFL": ("#3b82f6", "#1e3a8a"),    # Blue
            "Default": (_gradient()[0], "#0d419d"), # Indigo
        }

        # Get current filter
        current_filter = getattr(self, 'channel_filter_category', 'ALL')

        row = 0
        col = 0
        # Calculate max columns based on available width
        card_width = 200
        card_spacing = 15
        margins = 60  # left + right margins
        sidebar_width = 220
        try:
            # Use window width minus sidebar as reference
            window_width = self.width() - sidebar_width - margins
            if window_width < 500:  # Window not ready yet, use default
                max_cols = 5
            else:
                max_cols = max(3, window_width // (card_width + card_spacing))
        except:
            max_cols = 5  # fallback

        for name, data in profiles.items():
            voice = data.get('default_voice', data.get('voice', 'Not set'))
            category = data.get('category', 'Default')
            logo_path = data.get('logo_path', '')

            # Filter by category
            if current_filter != "ALL" and category != current_filter:
                continue

            # Get category color
            cat_color, cat_dark = category_colors.get(category, (_gradient()[0], "#0d419d"))

            # Create channel card - bigger and better looking
            card = QFrame()
            card.setFixedSize(200, 200)
            card.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1e2530, stop:1 #252525);
                    border: none;
                    border-radius: 12px;
                    border-top: 3px solid {cat_color};
                }}
                QFrame:hover {{
                    border-color: {cat_color};
                    border-top: 3px solid {cat_color};
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #252d3a, stop:1 #252525);
                }}
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 12)
            card_layout.setSpacing(6)

            # Category badge at top
            badge_row = QHBoxLayout()
            badge_row.setAlignment(Qt.AlignCenter)

            cat_badge = QLabel(category)
            cat_badge.setFixedHeight(20)
            cat_badge.setStyleSheet(f"""
                background-color: {cat_color};
                color: white;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 10px;
                border-radius: 10px;
                border: none;
            """)
            cat_badge.setAlignment(Qt.AlignCenter)
            badge_row.addWidget(cat_badge)
            card_layout.addLayout(badge_row)

            # Logo at top center - clickable to change
            logo_label = QLabel()
            logo_label.setFixedSize(60, 60)
            logo_label.setStyleSheet(f"""
                background-color: #2a2a2a;
                border-radius: 30px;
                border: 2px solid {cat_color};
            """)
            logo_label.setAlignment(Qt.AlignCenter)
            logo_label.setCursor(Qt.PointingHandCursor)
            logo_label.setToolTip("Click to change logo")

            # Try to load logo
            if logo_path and Path(logo_path).exists():
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    # Create circular pixmap
                    size = 56
                    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

                    # Crop to center if not square
                    if scaled.width() > size or scaled.height() > size:
                        x = (scaled.width() - size) // 2
                        y = (scaled.height() - size) // 2
                        scaled = scaled.copy(x, y, size, size)

                    # Create circular mask
                    from PyQt5.QtGui import QPainter, QBrush, QPainterPath
                    from PyQt5.QtCore import QRectF

                    circular = QPixmap(size, size)
                    circular.fill(Qt.transparent)

                    painter = QPainter(circular)
                    painter.setRenderHint(QPainter.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(QRectF(0, 0, size, size))
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, scaled)
                    painter.end()

                    logo_label.setPixmap(circular)
                else:
                    logo_label.setText("📺")
                    logo_label.setStyleSheet(logo_label.styleSheet() + "font-size: 24px;")
            else:
                logo_label.setText("📺")
                logo_label.setStyleSheet(logo_label.styleSheet() + "font-size: 24px;")

            # Make logo clickable to change
            logo_label.mousePressEvent = lambda e, n=name: self.change_channel_logo(n)

            card_layout.addWidget(logo_label, 0, Qt.AlignCenter)

            # Add spacing between logo and name
            card_layout.addSpacing(8)

            # Channel Name - centered
            name_label = QLabel(name)
            name_label.setStyleSheet("""
                color: #e0e0e0;
                font-weight: bold;
                font-size: 14px;
                background: transparent;
                border: none;
            """)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setWordWrap(True)
            card_layout.addWidget(name_label)

            # Voice info - smaller
            voice_short = voice[:18] + "..." if len(voice) > 18 else voice
            voice_label = QLabel(f"🎤 {voice_short}")
            voice_label.setStyleSheet("color: #888888; font-size: 10px; background: transparent; border: none;")
            voice_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(voice_label)

            card_layout.addStretch()

            # Buttons row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)

            btn_open = QPushButton("Open")
            btn_open.setFixedHeight(28)
            btn_open.setStyleSheet(f"""
                QPushButton {{
                    background-color: {_gradient()[0]};
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{ background-color: {_gradient()[1]}; }}
            """)
            btn_open.clicked.connect(lambda checked, n=name: self.open_channel_browser_by_name(n))
            btn_row.addWidget(btn_open)

            btn_edit = QPushButton("Edit")
            btn_edit.setFixedHeight(28)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    border: none;
                    border-radius: 6px;
                    color: #e0e0e0;
                    font-size: 11px;
                    padding: 0 12px;
                }
                QPushButton:hover { background-color: #3a3a3a; }
            """)
            btn_edit.clicked.connect(lambda checked, n=name: self.edit_channel_by_name(n))
            btn_row.addWidget(btn_edit)

            btn_del = QPushButton()
            btn_del.setText("X")
            btn_del.setFixedSize(32, 28)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #E74C3C;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    font-family: Arial, sans-serif;
                    padding: 0px;
                    margin: 0px;
                }
                QPushButton:hover { background-color: #E74C3C; }
            """)
            btn_del.setToolTip("Delete channel")
            btn_del.clicked.connect(lambda checked, n=name: self.delete_channel_by_name(n))
            btn_row.addWidget(btn_del)

            card_layout.addLayout(btn_row)

            # Add card to grid
            self.channel_grid_layout.addWidget(card, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Add "Add Channel" card at the end
        add_card = QFrame()
        add_card.setFixedSize(200, 200)
        add_card.setStyleSheet(f"""
            QFrame {{
                background-color: #1a1a1a;
                border: 2px dashed #3a3a3a;
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {_gradient()[0]};
                background-color: #121820;
            }}
        """)
        add_card.setCursor(Qt.PointingHandCursor)

        add_layout = QVBoxLayout(add_card)
        add_layout.setAlignment(Qt.AlignCenter)

        add_icon = QLabel("+")
        add_icon.setStyleSheet(f"color: {_gradient()[0]}; font-size: 48px; font-weight: bold; background: transparent; border: none;")
        add_icon.setAlignment(Qt.AlignCenter)
        add_layout.addWidget(add_icon)

        add_text = QLabel("Add Channel")
        add_text.setStyleSheet(f"color: {_gradient()[0]}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        add_text.setAlignment(Qt.AlignCenter)
        add_layout.addWidget(add_text)

        # Make the card clickable
        add_card.mousePressEvent = lambda e: self.add_channel()

        self.channel_grid_layout.addWidget(add_card, row, col)

    def refresh_channel_filter_buttons(self):
        """Refresh category filter buttons in channels page"""
        if not hasattr(self, 'channel_filter_buttons_layout'):
            return

        # Clear existing buttons
        while self.channel_filter_buttons_layout.count():
            item = self.channel_filter_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.channel_category_buttons = {}

        # Category colors
        category_colors = {
            "WNBA": ("#f59e0b", "#d97706"),   # Amber
            "MMA": ("#ef4444", "#dc2626"),    # Red
            "TEN": ("#10b981", "#059669"),    # Emerald/Green
            "NFL": ("#3b82f6", "#2563eb"),    # Blue
            "Default": (_gradient()[0], _gradient()[1]), # Indigo
        }

        profiles = self.config_manager.get_profiles()
        categories = self.config_manager.get_categories()

        # Count channels per category
        cat_counts = {}
        for p in profiles.values():
            cat = p.get("category", "Default")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        current_filter = getattr(self, 'channel_filter_category', 'ALL')

        def get_btn_style(color, hover_color, is_active):
            if is_active:
                return f"""
                    QPushButton {{
                        background: {color};
                        color: white;
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: {hover_color}; }}
                """
            else:
                return f"""
                    QPushButton {{
                        background: #2a2a2a;
                        color: {color};
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 500;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{ background: #3a3a3a; color: white; }}
                """

        # "All" button
        total_count = len(profiles)
        btn_all = QPushButton(f"All ({total_count})")
        btn_all.setStyleSheet(get_btn_style(_gradient()[0], _gradient()[1], current_filter == "ALL"))
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.clicked.connect(lambda: self.filter_channels_by_category("ALL"))
        self.channel_filter_buttons_layout.addWidget(btn_all)
        self.channel_category_buttons["ALL"] = btn_all

        # Category buttons
        for cat in categories:
            count = cat_counts.get(cat, 0)
            if count == 0:
                continue

            color, hover_color = category_colors.get(cat, (_gradient()[0], _gradient()[1]))

            btn = QPushButton(f"{cat} ({count})")
            btn.setStyleSheet(get_btn_style(color, hover_color, current_filter == cat))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=cat: self.filter_channels_by_category(c))
            self.channel_filter_buttons_layout.addWidget(btn)
            self.channel_category_buttons[cat] = btn

    def filter_channels_by_category(self, category):
        """Filter channels by category"""
        self.channel_filter_category = category
        self.refresh_channel_filter_buttons()
        self.update_channel_list()

    def change_channel_logo(self, channel_name):
        """Change or remove logo for a channel"""
        try:
            # Check if channel has a logo
            profiles = self.config_manager.get_profiles()
            has_logo = channel_name in profiles and profiles[channel_name].get('logo_path', '')

            if has_logo:
                # Show dialog with options
                msg = QMessageBox(self)
                msg.setWindowTitle("Channel Logo")
                msg.setText(f"What would you like to do with the logo for '{channel_name}'?")
                msg.setStyleSheet("""
                    QMessageBox { background-color: #252525; }
                    QLabel { color: #e0e0e0; font-size: 13px; }
                    QPushButton {
                        background-color: #2a2a2a;
                        color: #e0e0e0;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        min-width: 80px;
                    }
                    QPushButton:hover { background-color: #3a3a3a; }
                """)
                change_btn = msg.addButton("Change Logo", QMessageBox.ActionRole)
                remove_btn = msg.addButton("Remove Logo", QMessageBox.DestructiveRole)
                msg.addButton("Cancel", QMessageBox.RejectRole)
                msg.exec_()

                if msg.clickedButton() == change_btn:
                    self._browse_and_set_logo(channel_name)
                elif msg.clickedButton() == remove_btn:
                    profiles[channel_name]['logo_path'] = ''
                    self.config_manager.update_profile(channel_name, profiles[channel_name])
                    self.update_channel_list()
                    if hasattr(self, 'status_bar') and self.status_bar:
                        self.status_bar.showMessage(f"Logo removed for {channel_name}", 3000)
            else:
                # No logo, just browse for one
                self._browse_and_set_logo(channel_name)

        except Exception as e:
            print(f"Error changing logo: {e}")
            QMessageBox.warning(self, "Error", f"Failed to change logo: {str(e)}")

    def _browse_and_set_logo(self, channel_name):
        """Browse and set logo for a channel"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Logo for {channel_name}",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )

        if file_path:
            profiles = self.config_manager.get_profiles()
            if channel_name in profiles:
                profiles[channel_name]['logo_path'] = file_path
                self.config_manager.update_profile(channel_name, profiles[channel_name])
                self.update_channel_list()
                if hasattr(self, 'status_bar') and self.status_bar:
                    self.status_bar.showMessage(f"Logo updated for {channel_name}", 3000)

    def show_channel_menu(self, channel_name, button):
        """Show dropdown menu for channel actions"""
        from PyQt5.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #252525;
                border: none;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2a2a2a;
            }
        """)

        # Add actions
        delete_action = menu.addAction("Delete Channel")
        delete_action.triggered.connect(lambda: self.delete_channel_by_name(channel_name))

        # Show menu below button
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def delete_channel_by_name(self, channel_name):
        """Delete a channel by name"""
        reply = QMessageBox.question(
            self,
            "Delete Channel",
            f"Are you sure you want to delete '{channel_name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.config_manager.delete_profile(channel_name)
                self.update_channel_list()
                self.update_profile_combo()
                self.refresh_category_buttons()
                if hasattr(self, 'status_bar') and self.status_bar:
                    self.status_bar.showMessage(f"Channel '{channel_name}' deleted", 3000)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete channel: {str(e)}")

    def open_category_manager(self):
        """Open category manager dialog"""
        dialog = CategoryManagerDialog(self.config_manager, self)
        dialog.exec_()
        self.update_channel_list()
        self.refresh_category_buttons()
        self.update_profile_checkboxes()

    def update_voice_list(self):
        self.voice_list.clear()
        voices = self.config_manager.get_voices()
        for name, voice_data in voices.items():
            desc = voice_data.get("description", "No description") if isinstance(voice_data, dict) else str(voice_data)
            self.voice_list.addItem(f"🎤 {name}\n     {desc}")

    def add_channel(self):
        # Check channel limit before allowing new channels
        max_channels = self.license_manager.get_max_channels()
        current_channels = len(self.config_manager.get_profiles())

        if current_channels >= max_channels:
            QMessageBox.warning(
                self,
                "Channel Limit Reached",
                f"You have reached your channel limit ({max_channels} channels).\n\n"
                f"Upgrade your license to add more channels.\n\n"
                f"Current plan: {self.license_manager.get_tier().title()}"
            )
            return

        wizard = ProfileWizard(self.config_manager, self)
        if wizard.exec_():
            self.update_channel_list()
            self.update_profile_combo()

    def edit_channel_by_name(self, name):
        """Edit a channel by name"""
        dialog = ProfileEditorDialog(self.config_manager, name, self)
        if dialog.exec_():
            self.update_channel_list()
            self.update_profile_combo()

    def open_channel_browser_by_name(self, name):
        """Open Chrome with the channel's automatic browser profile"""
        import subprocess
        import os

        # Get browser profiles folder (same as 10_youtube_upload.py uses)
        try:
            import app_utils
            data_dir = app_utils.get_user_data_dir()
        except (ImportError, AttributeError):
            data_dir = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / "NabilVideoStudioPro"

        browser_profiles_folder = data_dir / "browser_profiles"
        profile_dir = browser_profiles_folder / f"profile_{name}"

        # Create profile folder if it doesn't exist
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Open Chrome with the profile
        try:
            chrome_cmd = f'start chrome --user-data-dir="{profile_dir}"'
            subprocess.Popen(chrome_cmd, shell=True)
            self.statusBar().showMessage(f"Opening browser for {name}...", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open browser:\n{str(e)}")

    def delete_channel_by_name(self, name):
        """Delete a channel by name"""
        reply = QMessageBox.question(self, "Delete Channel", f"Are you sure you want to delete '{name}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config_manager.delete_profile(name)
            self.update_channel_list()
            self.update_profile_combo()

    def add_voice(self):
        dialog = VoiceManagerDialog(self.config_manager, self)
        dialog.exec_()
        self.update_voice_list()

    def edit_voice(self):
        dialog = VoiceManagerDialog(self.config_manager, self)
        dialog.exec_()
        self.update_voice_list()

    def delete_voice(self):
        current = self.voice_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a voice to delete.")
            return
        text = current.text()
        name = text.split('\n')[0].replace('🎤 ', '').strip()
        reply = QMessageBox.question(self, "Delete Voice", f"Are you sure you want to delete '{name}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config_manager.delete_voice(name)
            self.update_voice_list()

    def on_settings_changed(self):
        self.log("Settings updated")

    def on_api_keys_changed(self):
        self.log("API keys updated")

    def log(self, message):
        self.log_output.append(message)
        self.log_output.moveCursor(QTextCursor.End)

    def load_settings(self):
        settings = self.config_manager.get_processing_settings()
        # Load quick options from saved state
        saved_opts = self.config_manager.config.get('quick_options', {})
        self.cb_parallel.setChecked(saved_opts.get('parallel', settings.get('enable_parallel', True)))
        self.cb_manual_crop.setChecked(saved_opts.get('manual_crop', settings.get('use_manual_crop_default', True)))
        self.cb_music.setChecked(saved_opts.get('music', settings.get('add_background_music', True)))
        self.cb_logo.setChecked(saved_opts.get('logo', settings.get('enable_logo_in_step7', False)))
        self.cb_animations.setChecked(saved_opts.get('animations', settings.get('enable_animations', True)))
        self.cb_folder_name.setChecked(settings.get('use_folder_name_for_output', True))

        # Load B-roll settings
        self.cb_voiceover_broll.setChecked(settings.get('use_voiceover_clips_for_broll', True))
        self.cb_custom_broll.setChecked(settings.get('use_custom_broll_input', False))
        self.toggle_custom_broll(Qt.Checked if settings.get('use_custom_broll_input', False) else Qt.Unchecked)

        # Load paths
        output_path = self.config_manager.get_path('output_base_dir')
        broll_path = self.config_manager.get_path('custom_broll_folder')
        if output_path:
            self.output_line_edit.setText(output_path)
        if broll_path:
            self.broll_folder_edit.setText(broll_path)

        # Load folder paths (unified - no separate single/multi mode)
        multi_paths_str = self.config_manager.get_path('multi_folder_paths')
        input_path = self.config_manager.get_path('input_videos_folder')

        # Clear existing entries
        for item in self.multi_folder_list[:]:
            item[0].setParent(None)
            item[0].deleteLater()
        self.multi_folder_list.clear()

        # Add saved folders
        paths_to_add = []
        if multi_paths_str:
            paths_to_add = [p for p in multi_paths_str.split("|") if p]
        elif input_path:
            paths_to_add = [input_path]

        if paths_to_add:
            for path in paths_to_add:
                self.add_folder_input()
                if self.multi_folder_list:
                    self.multi_folder_list[-1][1].setText(path)
        else:
            # Always have at least one folder input
            self.add_folder_input()

    def save_settings(self):
        settings = {
            'enable_parallel': self.cb_parallel.isChecked(),
            'use_manual_crop_default': self.cb_manual_crop.isChecked(),
            'add_background_music': self.cb_music.isChecked(),
            'enable_logo_in_step7': self.cb_logo.isChecked(),
            'enable_animations': self.cb_animations.isChecked(),
            'use_folder_name_for_output': self.cb_folder_name.isChecked(),
            'use_voiceover_clips_for_broll': self.cb_voiceover_broll.isChecked(),
            'use_custom_broll_input': self.cb_custom_broll.isChecked(),
        }
        self.config_manager.set_processing_settings(settings)

        self.config_manager.set_path('output_base_dir', self.output_line_edit.text().strip())
        self.config_manager.set_path('custom_broll_folder', self.broll_folder_edit.text())

        # Save folder paths
        multi_paths = []
        for item in self.multi_folder_list:
            path = item[1].text()  # folder_edit is index 1
            if path:
                multi_paths.append(path)
        self.config_manager.set_path('multi_folder_paths', "|".join(multi_paths))
        # Also save first path for backward compatibility
        if multi_paths:
            self.config_manager.set_path('input_videos_folder', multi_paths[0])

    def _save_quick_options(self):
        """Save quick options when checkbox changes"""
        use_global_broll = self.cb_global_broll.isChecked()
        global_broll_folder = self.global_broll_path.text().strip()

        # Get rv_thumb_mode if it exists (off, title, or script)
        rv_thumb_mode = "title"  # default
        if hasattr(self, 'rv_thumb_mode_off') and self.rv_thumb_mode_off.isChecked():
            rv_thumb_mode = "off"
        elif hasattr(self, 'rv_thumb_mode_title') and self.rv_thumb_mode_title.isChecked():
            rv_thumb_mode = "title"
        elif hasattr(self, 'rv_thumb_mode_script') and self.rv_thumb_mode_script.isChecked():
            rv_thumb_mode = "script"

        opts = {
            'clean_output': self.cb_clean_output.isChecked(),
            'parallel': self.cb_parallel.isChecked(),
            'manual_crop': self.cb_manual_crop.isChecked(),
            'music': self.cb_music.isChecked(),
            'logo': self.cb_logo.isChecked(),
            'animations': self.cb_animations.isChecked(),
            'use_global_broll': use_global_broll,
            'global_broll_folder': global_broll_folder,
            'rv_thumb_mode': rv_thumb_mode,
        }
        self.config_manager.config['quick_options'] = opts

        # IMPORTANT: Also sync to processing_settings so the script reads correct values
        if 'processing_settings' not in self.config_manager.config:
            self.config_manager.config['processing_settings'] = {}
        self.config_manager.config['processing_settings']['use_custom_broll_input'] = use_global_broll
        self.config_manager.config['processing_settings']['use_voiceover_clips_for_broll'] = not use_global_broll
        self.config_manager.config['processing_settings']['thumbnail_mode'] = rv_thumb_mode
        self.config_manager.config['processing_settings']['enable_animations'] = self.cb_animations.isChecked()

        # Also sync to animation_settings so recreat-videos.py reads correct values
        if 'animation_settings' not in self.config_manager.config:
            self.config_manager.config['animation_settings'] = {}
        self.config_manager.config['animation_settings']['enable_animation'] = self.cb_animations.isChecked()

        # Also sync the broll folder path
        if 'paths' not in self.config_manager.config:
            self.config_manager.config['paths'] = {}
        self.config_manager.config['paths']['custom_broll_folder'] = global_broll_folder

        self.config_manager.save()

    def _browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_line_edit.setText(folder)

    def _manual_clean_output_folder(self):
        """Manually clean the output folder"""
        output_path = self.output_line_edit.text().strip()
        if not output_path:
            QMessageBox.warning(self, "No Folder", "Please select an output folder first.")
            return
        self._clean_output_folder(output_path)

    def _clean_all_folders(self):
        """Clean ALL files from both input and output folders"""
        # Get all input folders
        input_folders = []
        for i in range(self.multi_folder_layout.count()):
            widget = self.multi_folder_layout.itemAt(i).widget()
            if widget:
                line_edit = widget.findChild(QLineEdit)
                if line_edit:
                    path = line_edit.text().strip()
                    if path and os.path.exists(path):
                        input_folders.append(path)

        # Find parent INPUT folder (if all inputs share same parent, clean that instead)
        parent_input_folder = None
        if input_folders:
            parents = set(str(Path(p).parent) for p in input_folders)
            if len(parents) == 1:
                parent_input_folder = list(parents)[0]

        # Get output folder
        output_path = self.output_line_edit.text().strip()

        # Check if we have any folders to clean
        folders_to_clean = []

        # If all inputs share same parent, clean the parent folder
        if parent_input_folder and os.path.exists(parent_input_folder):
            folders_to_clean.append(("Input", parent_input_folder))
        else:
            # Otherwise clean individual input folders
            for inp in input_folders:
                folders_to_clean.append(("Input", inp))

        if output_path and os.path.exists(output_path):
            folders_to_clean.append(("Output", output_path))

        if not folders_to_clean:
            QMessageBox.warning(self, "No Folders", "No valid folders found to clean.\n\nPlease add input folders and/or select an output folder first.")
            return

        # Count total items
        total_items = 0
        for _, folder_path in folders_to_clean:
            try:
                total_items += len(os.listdir(folder_path))
            except:
                pass

        if total_items == 0:
            QMessageBox.information(self, "Already Clean", "All folders are already empty!")
            return

        # Build confirmation message
        folder_list = "\n".join([f"  • {name}: {path}" for name, path in folders_to_clean])

        # Custom styled confirmation dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("🧹 Clean All Folders")
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"<b>Delete {total_items} items from all folders?</b>")
        msg.setInformativeText(f"This will permanently delete all files and subfolders in:\n\n{folder_list}\n\n⚠️ This action cannot be undone!")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("""
            QMessageBox { background-color: #1a1a2e; }
            QMessageBox QLabel { color: #e2e8f0; font-size: 13px; }
            QPushButton {
                background-color: #555555; color: white; border: none;
                padding: 8px 20px; border-radius: 6px; font-weight: 600; min-width: 80px;
            }
            QPushButton:hover { background-color: #555555; }
        """)

        if msg.exec_() == QMessageBox.Yes:
            cleaned_count = 0
            errors = []

            for folder_name, folder_path in folders_to_clean:
                try:
                    items = os.listdir(folder_path)
                    for item in items:
                        item_path = os.path.join(folder_path, item)
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                cleaned_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                cleaned_count += 1
                        except Exception as e:
                            errors.append(f"{item}: {str(e)}")
                except Exception as e:
                    errors.append(f"{folder_name}: {str(e)}")

            if errors:
                QMessageBox.warning(self, "Partial Success",
                    f"Cleaned {cleaned_count} items but had some errors:\n\n" + "\n".join(errors[:5]))
            else:
                QMessageBox.information(self, "Success",
                    f"✅ Successfully cleaned {cleaned_count} items from all folders!")

    def _clean_output_folder(self, folder_path):
        """Clean all files from output folder"""
        folder = Path(folder_path)
        if not folder.exists():
            QMessageBox.warning(self, "Folder Not Found", f"The folder does not exist:\n{folder_path}")
            return

        # Count files
        files = list(folder.glob("*"))
        if not files:
            QMessageBox.information(self, "Already Clean", "The output folder is already empty.")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Confirm Clean",
            f"Are you sure you want to delete {len(files)} item(s) from:\n{folder_path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            deleted = 0
            for item in files:
                try:
                    if item.is_file():
                        item.unlink()
                        deleted += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        deleted += 1
                except Exception as e:
                    self.log(f"⚠️ Could not delete {item.name}: {e}")
            QMessageBox.information(self, "Cleaned", f"Deleted {deleted} item(s) from output folder.")

    def _toggle_global_broll_path(self):
        """Enable/disable global B-roll path based on checkbox"""
        enabled = self.cb_global_broll.isChecked()
        self.global_broll_path.setEnabled(enabled)
        self.btn_browse_global_broll.setEnabled(enabled)

    def _browse_global_broll(self):
        """Browse for global B-roll folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Global B-roll Folder")
        if folder:
            self.global_broll_path.setText(folder)
            self._save_quick_options()

    def run_pipeline(self):
        # Log to file since pythonw.exe has no console
        log_file = SCRIPT_DIR / "pipeline_log.txt"
        try:
            with open(log_file, "a") as f:
                f.write(f"\n{'='*50}\n[{__import__('datetime').datetime.now()}] run_pipeline started\n")
            self._run_pipeline_impl()
        except Exception as e:
            with open(log_file, "a") as f:
                f.write(f"EXCEPTION: {e}\n")
                f.write(traceback.format_exc())
            raise

    def _run_pipeline_impl(self):
        log_file = SCRIPT_DIR / "pipeline_log.txt"
        def log(msg):
            with open(log_file, "a") as f:
                f.write(f"{msg}\n")

        log("_run_pipeline_impl started")

        # SECURITY: Verify license before running pipeline
        is_licensed, lic_message, _ = self.license_manager.check_license()
        if not is_licensed:
            log(f"License check FAILED: {lic_message}")
            QMessageBox.warning(self, "License Required", f"Cannot run pipeline: {lic_message}")
            return

        # SECURITY: Verify channel limit before running
        max_channels = self.license_manager.get_max_channels()
        total_profiles = len(self.config_manager.get_profiles())
        log(f"License check: max_channels={max_channels}, total_profiles={total_profiles}")

        if total_profiles > max_channels:
            QMessageBox.warning(
                self,
                "Channel Limit Exceeded",
                f"You have {total_profiles} channels but your license only allows {max_channels}.\n\n"
                f"Please remove {total_profiles - max_channels} channel(s) or upgrade your license.\n\n"
                f"Go to Channels page to manage your channels."
            )
            return

        # Get all input folders with their per-folder settings
        input_folders = []
        folder_settings = []  # List of dicts with channel and broll info
        for item in self.multi_folder_list:
            row_widget = item[0]
            line_edit = item[1]
            folder_path = line_edit.text()
            if folder_path and Path(folder_path).exists():
                input_folders.append(folder_path)
                # Get per-folder settings (only if checkbox is checked)
                channel = None
                broll_folder = None
                if hasattr(row_widget, 'channel_checkbox') and row_widget.channel_checkbox.isChecked():
                    channel = row_widget.channel_combo.currentData()  # Get selected channel
                if hasattr(row_widget, 'broll_checkbox') and row_widget.broll_checkbox.isChecked():
                    broll_folder = row_widget.broll_edit.text() if row_widget.broll_edit.text() else None
                folder_settings.append({
                    'path': folder_path,
                    'channel': channel,
                    'broll': broll_folder
                })

        if not input_folders:
            QMessageBox.warning(self, "Missing Input", "Please select at least one valid folder.")
            return

        log(f"Found {len(input_folders)} input folders")
        for fs in folder_settings:
            log(f"  - {Path(fs['path']).name}: channel={fs['channel'] or 'Use Selected'}, broll={fs['broll'] or 'default'}")
        print(f"DEBUG: Found {len(input_folders)} input folders")
        output_folder = self.output_line_edit.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "Error", "Please select an output folder.")
            return

        # Clean output folder if checkbox is checked
        if self.cb_clean_output.isChecked():
            folder = Path(output_folder)
            if folder.exists():
                files = list(folder.glob("*"))
                if files:
                    for item in files:
                        try:
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                        except Exception as e:
                            self.log(f"⚠️ Could not delete {item.name}: {e}")
                    self.log(f"🗑️ Cleaned {len(files)} item(s) from output folder")

        # Get selected channels from checkboxes
        selected_profiles = []
        for name, cb in self.profile_checkboxes.items():
            if cb.isChecked():
                selected_profiles.append(name)

        if not selected_profiles:
            QMessageBox.warning(self, "Error", "Please select at least one channel.")
            return

        profile_name = selected_profiles[0] if len(selected_profiles) == 1 else None
        profile_count = len(selected_profiles) if len(selected_profiles) > 1 else None

        # Save settings
        self.save_settings()

        # Get start step
        start_step = self.combo_start_step.currentData()

        # Update config for orchestrator
        config = self.config_manager.config
        config['input_folder'] = input_folders[0] if input_folders else ''
        config['output_base_folder'] = output_folder
        config['selected_profile'] = profile_name
        config['enable_parallel'] = self.cb_parallel.isChecked()
        config['use_manual_crop_default'] = self.cb_manual_crop.isChecked()
        config['add_background_music'] = self.cb_music.isChecked()
        config['enable_logo_in_step7'] = self.cb_logo.isChecked()
        config['enable_animations'] = self.cb_animations.isChecked()
        config['use_folder_name_for_output'] = self.cb_folder_name.isChecked()

        # Save per-folder settings (Custom Channel and Custom B-roll)
        config['per_folder_settings'] = folder_settings

        self.config_manager.save()

        # Clear log and switch to log page
        self.log_output.clear()
        self.switch_page(5)

        # Update UI - disable run, enable stop (both pages)
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_run_btn.setEnabled(False)
        self.log_cc_run_btn.setEnabled(False)
        self.log_stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Starting...")
        self.status_label.setText("Pipeline running...")

        # Start worker
        self.worker = PipelineWorker(
            MAIN_SCRIPT,
            profile_name=profile_name,
            profile_count=profile_count,
            input_folders=input_folders,
            start_step=start_step,
            selected_profiles=selected_profiles,
            manual_crop=self.cb_manual_crop.isChecked()
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.step_notification.connect(self.show_step_notification)
        self.worker.start()

        # Store pipeline info for history
        self._pipeline_channels = ", ".join(selected_profiles)
        self._pipeline_input_folders = ", ".join([Path(f).name for f in input_folders])
        self._pipeline_output_folder = Path(output_folder).name
        self._pipeline_video_count = len(input_folders)

        # Log message with per-folder settings
        channel_info = profile_name if profile_name else f"{len(selected_profiles)} channels"
        if len(input_folders) > 1:
            self.log(f"🚀 Pipeline started with {len(input_folders)} folders")
            for fs in folder_settings:
                folder_name = Path(fs['path']).name
                ch_name = fs['channel'] if fs['channel'] else "Selected"
                broll_info = f" | B-roll: {Path(fs['broll']).name}" if fs['broll'] else ""
                self.log(f"   📁 {folder_name} → {ch_name}{broll_info}")
        else:
            folder_name = Path(input_folders[0]).name if input_folders else "unknown"
            fs = folder_settings[0] if folder_settings else {}
            ch_name = fs.get('channel') or channel_info
            self.log(f"🚀 Pipeline started: {folder_name} → {ch_name}")

    def stop_pipeline(self):
        """Stop any running pipeline (Recreate Video, Create Video, or Story Video)"""
        stopped = False
        if self.worker:
            self.worker.stop()
            self.log("⏹️ Stopping Recreate Video pipeline...")
            stopped = True
        if self.cc_worker:
            self.cc_worker.stop()
            self.log("⏹️ Stopping Create Video pipeline...")
            stopped = True
        if self.sv_worker:
            self.sv_worker.stop()
            self.log("⏹️ Stopping Story Video pipeline...")
            stopped = True
        if not stopped:
            self.log("⚠️ No pipeline is currently running")

    def on_progress(self, message):
        self.log(message)

        # Update progress based on step
        if "step 0" in message.lower():
            self.progress_bar.setValue(5)
            self.progress_bar.setFormat("Step 0/10")
        elif "step 1" in message.lower():
            self.progress_bar.setValue(15)
            self.progress_bar.setFormat("Step 1/10")
        elif "step 2" in message.lower():
            self.progress_bar.setValue(25)
            self.progress_bar.setFormat("Step 2/10")
        elif "step 3" in message.lower():
            self.progress_bar.setValue(35)
            self.progress_bar.setFormat("Step 3/10")
        elif "step 4" in message.lower():
            self.progress_bar.setValue(45)
            self.progress_bar.setFormat("Step 4/10")
        elif "step 5" in message.lower():
            self.progress_bar.setValue(55)
            self.progress_bar.setFormat("Step 5/10")
        elif "step 6" in message.lower():
            self.progress_bar.setValue(65)
            self.progress_bar.setFormat("Step 6/10")
        elif "step 7" in message.lower():
            self.progress_bar.setValue(75)
            self.progress_bar.setFormat("Step 7/10")
        elif "step 8" in message.lower():
            self.progress_bar.setValue(85)
            self.progress_bar.setFormat("Step 8/10")
        elif "step 9" in message.lower():
            self.progress_bar.setValue(90)
            self.progress_bar.setFormat("Step 9/10")
        elif "step 10" in message.lower():
            self.progress_bar.setValue(95)
            self.progress_bar.setFormat("Step 10/10")

    def on_finished(self, success):
        # Re-enable run, disable stop (both pages)
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log_run_btn.setEnabled(True)
        self.log_cc_run_btn.setEnabled(True)
        self.log_stop_btn.setEnabled(False)

        log_text = self.log_output.toPlainText().lower()

        success_patterns = ["pipeline completed successfully", "orchestration complete"]
        has_success = any(p in log_text for p in success_patterns)

        critical_errors = ["403 forbidden", "authentication failed", "pipeline failed at step"]
        has_error = any(p in log_text for p in critical_errors)

        if success and (has_success or not has_error):
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Complete!")
            self.status_label.setText("✅ Pipeline completed successfully!")
            QMessageBox.information(self, "Success!", "Pipeline completed successfully!\n\nCheck your output folder for results.")
        else:
            self.progress_bar.setFormat("Failed")
            self.status_label.setText("❌ Pipeline failed - check log for errors")
            QMessageBox.warning(self, "Pipeline Failed", "Pipeline failed!\n\nCheck the log for details.")

    def show_step_notification(self, step_name, message):
        # Notifications are now handled directly by popup tools (crop_tool.py, logo_editor_tool.py)
        # They play notification sound when popup opens - no delayed notification needed
        pass

    def play_notification_sound(self):
        # Not used anymore - popups handle their own notifications
        pass


# ============================================================================
# RUN
# ============================================================================

def create_splash_pixmap():
    """Create a splash screen pixmap with logo and text"""
    from PyQt5.QtGui import QPainter, QLinearGradient, QBrush, QPen
    from PyQt5.QtCore import QRect
    from ui_styles import get_accent_color, get_accent_gradient

    # Get theme colors
    accent = get_accent_color()
    grad_start, grad_end = get_accent_gradient()

    # Create pixmap
    width, height = 500, 350
    pixmap = QPixmap(width, height)

    # Create painter
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Draw gradient background
    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0, QColor("#1a1a2e"))
    gradient.setColorAt(1, QColor("#0f0f1a"))
    painter.fillRect(0, 0, width, height, QBrush(gradient))

    # Draw border with theme accent color
    painter.setPen(QPen(QColor(accent), 2))
    painter.drawRect(1, 1, width-2, height-2)

    # Load and draw logo
    logo_path = Path(__file__).parent / "assets" / "logo.ico"
    if logo_path.exists():
        logo = QPixmap(str(logo_path))
        logo_scaled = logo.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_x = (width - logo_scaled.width()) // 2
        painter.drawPixmap(logo_x, 50, logo_scaled)

    # Draw app name with theme accent color
    painter.setPen(QColor(accent))
    font = QFont("Segoe UI", 28, QFont.Bold)
    painter.setFont(font)
    painter.drawText(QRect(0, 160, width, 50), Qt.AlignCenter, APP_NAME)

    # Draw version
    painter.setPen(QColor("#a0a0a0"))
    font = QFont("Segoe UI", 14)
    painter.setFont(font)
    painter.drawText(QRect(0, 210, width, 30), Qt.AlignCenter, f"Version {VERSION}")

    # Draw loading text
    painter.setPen(QColor("#606060"))
    font = QFont("Segoe UI", 11)
    painter.setFont(font)
    painter.drawText(QRect(0, 290, width, 30), Qt.AlignCenter, "Loading...")

    # Draw copyright
    painter.setPen(QColor("#404040"))
    font = QFont("Segoe UI", 9)
    painter.setFont(font)
    painter.drawText(QRect(0, 320, width, 20), Qt.AlignCenter, COPYRIGHT)

    painter.end()
    return pixmap


def main():
    try:
        print("Starting app...")

        # Set Windows AppUserModelID for taskbar icon (must match launcher!)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NabilSoftware.NVSPro.VideoStudio.1')
        except:
            pass

        app = QApplication(sys.argv)
        app.setFont(QFont("Segoe UI", 10))

        # Load and apply theme from config
        try:
            from ui_styles import set_current_theme, get_current_theme, THEMES
            config_path = get_user_data_dir() / "config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                saved_theme = config.get("appearance", {}).get("theme", "orange")
                if saved_theme in THEMES:
                    set_current_theme(saved_theme)
                    print(f"[THEME] Loaded theme: {saved_theme}")
        except Exception as e:
            print(f"[THEME] Could not load theme: {e}")

        # Set application-wide icon (for taskbar pinning)
        icon_path = Path(__file__).parent / "assets" / "logo.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        # Check license BEFORE showing splash screen
        print("Checking license...")
        license_manager = LicenseManager()
        is_licensed, message, license_info = license_manager.check_license()

        if not is_licensed:
            # Show license dialog on clean background (no splash)
            print("No valid license, showing activation dialog...")
            dialog = LicenseActivationDialog(None)
            if dialog.exec_() != dialog.Accepted:
                print("License activation cancelled, exiting...")
                sys.exit(0)
            print("License activated successfully!")

        # Now show splash screen (license is valid)
        splash_pixmap = create_splash_pixmap()
        splash = QSplashScreen(splash_pixmap, Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()

        print("Creating window...")
        window = ModernMainWindow(skip_license_check=True)  # Skip license check since we already did it
        print("Window created, showing...")

        # Close splash and show main window
        splash.finish(window)
        window.show()
        print("Window shown, starting event loop...")

        # Check for updates 3 seconds after startup (non-blocking)
        def _check_update():
            try:
                print("[UPDATE] Checking for updates...")
                from auto_updater import check_for_update, download_update, install_update, is_update_skipped, skip_update

                has_update, latest_version, download_url, release_notes = check_for_update()
                print(f"[UPDATE] Result: has_update={has_update}, version={latest_version}")
                if not has_update:
                    return

                if is_update_skipped(latest_version):
                    print(f"[UPDATE] User skipped v{latest_version}, not showing dialog")
                    return

                # Show update dialog
                msg = QMessageBox(window)
                msg.setWindowTitle(f"Update Available — v{latest_version}")
                msg.setText(f"A new version of Nabil Video Studio Pro is available: v{latest_version}")
                msg.setInformativeText(release_notes[:500] if release_notes else "")
                msg.setIcon(QMessageBox.Information)
                download_btn = msg.addButton("Download && Install", QMessageBox.AcceptRole)
                msg.addButton("Remind Me Later", QMessageBox.RejectRole)
                skip_btn = msg.addButton("Skip This Version", QMessageBox.DestructiveRole)
                msg.exec_()

                if msg.clickedButton() == skip_btn:
                    skip_update(latest_version)
                    return

                if msg.clickedButton() != download_btn:
                    return

                # Show progress dialog (modal so user can't close it)
                progress_dialog = QDialog(window)
                progress_dialog.setWindowTitle("Downloading Update...")
                progress_dialog.setFixedSize(400, 100)
                progress_dialog.setWindowFlags(progress_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint & ~Qt.WindowCloseButtonHint)
                progress_dialog.setModal(True)
                layout = QVBoxLayout(progress_dialog)
                progress_label = QLabel(f"Downloading v{latest_version}...")
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                layout.addWidget(progress_label)
                layout.addWidget(progress_bar)
                progress_dialog.show()
                QApplication.processEvents()

                def on_progress(percent):
                    progress_bar.setValue(percent)
                    QApplication.processEvents()

                installer_path = download_update(download_url, on_progress)
                progress_dialog.close()

                # Validate downloaded file (must be > 1MB to be a real installer)
                if installer_path and os.path.exists(installer_path) and os.path.getsize(installer_path) > 1_000_000:
                    # Show message that app will close
                    QMessageBox.information(window, "Installing Update",
                        "The application will now close to install the update.\n\n"
                        "It will restart automatically after installation.")
                    QApplication.processEvents()

                    # Cleanup callback to close all windows
                    def cleanup():
                        try:
                            window.close()
                            QApplication.quit()
                        except Exception:
                            pass

                    install_update(installer_path, cleanup_callback=cleanup)
                else:
                    QMessageBox.warning(window, "Update Failed",
                                        "Failed to download the update. Please try again later.")
            except Exception as e:
                print(f"[UPDATE] Error: {e}")

        QTimer.singleShot(3000, _check_update)

        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
