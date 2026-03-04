"""
Nabil Video Studio Pro - System Check UI Page
Check and fix package installations
"""
import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGroupBox, QProgressBar, QMessageBox,
    QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import qtawesome as qta

# Get app directory
APP_DIR = Path(__file__).parent.resolve()
PYTHON_EXE = APP_DIR / "python" / "python.exe"
TARGET_DIR = APP_DIR / "python" / "Lib" / "site-packages"

# ============================================================================
# LOCKED PACKAGE VERSIONS - Must match first_run_setup.py
# ============================================================================
PYTORCH_VERSION = "2.3.1"
TORCHVISION_VERSION = "0.18.1"
TORCHAUDIO_VERSION = "2.3.1"

LOCKED_PACKAGES = {
    "numpy": "1.26.4",
    "protobuf": "3.20.3",
    "scipy": "1.15.3",
    "scikit-learn": "1.7.2",
    "pyannote.audio": "3.4.0",
    "openai-whisper": "20250625",
    "faster-whisper": "1.1.0",
    "google-generativeai": "0.8.5",
    "anthropic": "0.69.0",
    "demucs": "4.0.1",
    "opencv-python": "4.10.0.84",
    "pillow": "11.3.0",
    "moviepy": "1.0.3",
    "requests": "2.32.5",
    "aiohttp": "3.12.15",
    "selenium": "4.40.0",
    "playwright": "1.55.0",
    "PyQt5": "5.15.11",
    "qtawesome": "1.4.0",
    "soundfile": "0.13.1",
    "pydub": "0.25.1",
    "librosa": "0.11.0",
    "tqdm": "4.67.1",
    "colorama": "0.4.6",
    "torchmetrics": "1.8.2",
    "torch-audiomentations": "0.12.0",
    "speechbrain": "1.0.3",
}

# Package check commands
PACKAGE_CHECKS = {
    "PyTorch (CUDA)": {
        "check": "import torch; v=torch.__version__; c=torch.cuda.is_available(); print(f'{v} CUDA:{c}')",
        "install": f"torch=={PYTORCH_VERSION} torchvision=={TORCHVISION_VERSION} torchaudio=={TORCHAUDIO_VERSION} --index-url https://download.pytorch.org/whl/cu121",
        "category": "Core AI",
        "critical": True,
    },
    "NumPy": {
        "check": "import numpy; print(numpy.__version__)",
        "install": f"numpy=={LOCKED_PACKAGES['numpy']}",
        "category": "Core",
        "critical": True,
    },
    "Pyannote": {
        "check": "import pyannote.audio; print('OK')",
        "install": f"pyannote.audio=={LOCKED_PACKAGES['pyannote.audio']} --no-deps",
        "category": "Core AI",
        "critical": True,
    },
    "Whisper": {
        "check": "import whisper; print('OK')",
        "install": f"openai-whisper=={LOCKED_PACKAGES['openai-whisper']}",
        "category": "Core AI",
        "critical": True,
    },
    "Faster Whisper": {
        "check": "import faster_whisper; print('OK')",
        "install": f"faster-whisper=={LOCKED_PACKAGES['faster-whisper']}",
        "category": "Core AI",
        "critical": False,
    },
    "Google Gemini AI": {
        "check": "import google.generativeai; print('OK')",
        "install": f"google-generativeai=={LOCKED_PACKAGES['google-generativeai']}",
        "category": "AI Providers",
        "critical": True,
    },
    "Anthropic Claude": {
        "check": "import anthropic; print('OK')",
        "install": f"anthropic=={LOCKED_PACKAGES['anthropic']}",
        "category": "AI Providers",
        "critical": True,
    },
    "OpenCV": {
        "check": "import cv2; print(cv2.__version__)",
        "install": f"opencv-python=={LOCKED_PACKAGES['opencv-python']}",
        "category": "Video/Image",
        "critical": True,
    },
    "Pillow": {
        "check": "from PIL import Image; print('OK')",
        "install": f"pillow=={LOCKED_PACKAGES['pillow']}",
        "category": "Video/Image",
        "critical": True,
    },
    "MoviePy": {
        "check": "import moviepy; print('OK')",
        "install": f"moviepy=={LOCKED_PACKAGES['moviepy']}",
        "category": "Video/Image",
        "critical": False,
    },
    "PyQt5": {
        "check": "from PyQt5.QtWidgets import QApplication; print('OK')",
        "install": f"PyQt5=={LOCKED_PACKAGES['PyQt5']}",
        "category": "UI",
        "critical": True,
    },
    "Selenium": {
        "check": "import selenium; print(selenium.__version__)",
        "install": f"selenium=={LOCKED_PACKAGES['selenium']}",
        "category": "Browser",
        "critical": False,
    },
    "Playwright": {
        "check": "import playwright; print('OK')",
        "install": f"playwright=={LOCKED_PACKAGES['playwright']}",
        "category": "Browser",
        "critical": False,
    },
    "Demucs": {
        "check": "import demucs; print('OK')",
        "install": f"demucs=={LOCKED_PACKAGES['demucs']}",
        "category": "Audio",
        "critical": False,
    },
    "SciPy": {
        "check": "import scipy; print(scipy.__version__)",
        "install": f"scipy=={LOCKED_PACKAGES['scipy']}",
        "category": "Core",
        "critical": True,
    },
    "AioHTTP": {
        "check": "import aiohttp; print(aiohttp.__version__)",
        "install": f"aiohttp=={LOCKED_PACKAGES['aiohttp']}",
        "category": "Web",
        "critical": True,
    },
}


class PackageCheckWorker(QThread):
    """Worker thread for checking packages"""
    progress = pyqtSignal(str, str, str)  # name, status, details
    finished = pyqtSignal(dict)  # results

    def __init__(self, packages: Dict):
        super().__init__()
        self.packages = packages

    def run(self):
        results = {}
        python = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable

        for name, info in self.packages.items():
            try:
                result = subprocess.run(
                    [python, "-c", info["check"]],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    output = result.stdout.strip()[:30]
                    results[name] = ("ok", output)
                    self.progress.emit(name, "ok", output)
                else:
                    error = result.stderr.strip().split('\n')[-1][:40] if result.stderr else "Failed"
                    results[name] = ("error", error)
                    self.progress.emit(name, "error", error)
            except subprocess.TimeoutExpired:
                results[name] = ("error", "Timeout")
                self.progress.emit(name, "error", "Timeout")
            except Exception as e:
                results[name] = ("error", str(e)[:30])
                self.progress.emit(name, "error", str(e)[:30])

        self.finished.emit(results)


class PackageInstallWorker(QThread):
    """Worker thread for installing packages"""
    progress = pyqtSignal(str)  # status message
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, package_name: str, install_cmd: str):
        super().__init__()
        self.package_name = package_name
        self.install_cmd = install_cmd

    def run(self):
        python = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable
        target = str(TARGET_DIR)

        self.progress.emit(f"Installing {self.package_name}...")

        cmd = f'"{python}" -m pip install {self.install_cmd} --target "{target}" --no-warn-script-location -q'

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                self.finished.emit(True, f"{self.package_name} installed successfully!")
            else:
                error = result.stderr[:200] if result.stderr else "Unknown error"
                self.finished.emit(False, f"Failed: {error}")
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "Installation timed out")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")


class PackageItemWidget(QFrame):
    """Widget for a single package status"""
    fix_requested = pyqtSignal(str)  # package name

    def __init__(self, name: str, info: Dict, parent=None):
        super().__init__(parent)
        self.name = name
        self.info = info
        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            PackageItemWidget {
                background-color: #2b2b2b;
                border-radius: 8px;
                padding: 5px;
                margin: 2px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        # Status icon
        self.status_icon = QLabel()
        self.status_icon.setFixedWidth(24)
        layout.addWidget(self.status_icon)

        # Package name
        name_label = QLabel(self.name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        name_label.setStyleSheet("color: white;")
        name_label.setFixedWidth(150)
        layout.addWidget(name_label)

        # Category badge
        category = self.info.get("category", "Other")
        cat_label = QLabel(category)
        cat_label.setStyleSheet("""
            background-color: #3d3d3d;
            color: #888;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 9px;
        """)
        cat_label.setFixedWidth(80)
        layout.addWidget(cat_label)

        # Status text
        self.status_label = QLabel("Checking...")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label, 1)

        # Fix button
        self.fix_btn = QPushButton("Fix")
        self.fix_btn.setIcon(qta.icon('fa5s.wrench', color='white'))
        self.fix_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        self.fix_btn.setVisible(False)
        self.fix_btn.clicked.connect(lambda: self.fix_requested.emit(self.name))
        layout.addWidget(self.fix_btn)

    def set_status(self, status: str, details: str):
        """Update package status"""
        if status == "ok":
            self.status_icon.setPixmap(qta.icon('fa5s.check-circle', color='#2ecc71').pixmap(20, 20))
            self.status_label.setText(details)
            self.status_label.setStyleSheet("color: #2ecc71;")
            self.fix_btn.setVisible(False)
            self.setStyleSheet("""
                PackageItemWidget {
                    background-color: #1a3320;
                    border-radius: 8px;
                    border: 1px solid #2ecc71;
                }
            """)
        elif status == "error":
            self.status_icon.setPixmap(qta.icon('fa5s.times-circle', color='#e74c3c').pixmap(20, 20))
            self.status_label.setText(details)
            self.status_label.setStyleSheet("color: #e74c3c;")
            self.fix_btn.setVisible(True)
            self.setStyleSheet("""
                PackageItemWidget {
                    background-color: #3d1f1f;
                    border-radius: 8px;
                    border: 1px solid #e74c3c;
                }
            """)
        else:  # checking
            self.status_icon.setPixmap(qta.icon('fa5s.spinner', color='#f39c12').pixmap(20, 20))
            self.status_label.setText("Checking...")
            self.status_label.setStyleSheet("color: #f39c12;")
            self.fix_btn.setVisible(False)

    def set_installing(self, installing: bool):
        """Show installing state"""
        if installing:
            self.fix_btn.setEnabled(False)
            self.fix_btn.setText("Installing...")
            self.status_label.setText("Installing...")
            self.status_label.setStyleSheet("color: #f39c12;")
        else:
            self.fix_btn.setEnabled(True)
            self.fix_btn.setText("Fix")


class SystemCheckPage(QWidget):
    """System Check page for the main application"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.package_widgets: Dict[str, PackageItemWidget] = {}
        self.check_worker = None
        self.install_worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("System Check")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Check All button
        self.check_btn = QPushButton("  Check All")
        self.check_btn.setIcon(qta.icon('fa5s.sync', color='white'))
        self.check_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        self.check_btn.clicked.connect(self.check_all_packages)
        header_layout.addWidget(self.check_btn)

        # Fix All button
        self.fix_all_btn = QPushButton("  Fix All Problems")
        self.fix_all_btn.setIcon(qta.icon('fa5s.magic', color='white'))
        self.fix_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        self.fix_all_btn.clicked.connect(self.fix_all_problems)
        self.fix_all_btn.setVisible(False)
        header_layout.addWidget(self.fix_all_btn)

        layout.addLayout(header_layout)

        # Summary
        self.summary_label = QLabel("Click 'Check All' to scan your system")
        self.summary_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.summary_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #2b2b2b;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Scroll area for packages
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        scroll_content = QWidget()
        self.packages_layout = QVBoxLayout(scroll_content)
        self.packages_layout.setSpacing(5)
        self.packages_layout.setContentsMargins(0, 0, 0, 0)

        # Create package widgets
        for name, info in PACKAGE_CHECKS.items():
            widget = PackageItemWidget(name, info)
            widget.fix_requested.connect(self.fix_package)
            self.package_widgets[name] = widget
            self.packages_layout.addWidget(widget)

        self.packages_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def check_all_packages(self):
        """Start checking all packages"""
        self.check_btn.setEnabled(False)
        self.check_btn.setText("  Checking...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(PACKAGE_CHECKS))
        self.progress_bar.setValue(0)
        self.summary_label.setText("Checking packages...")

        # Reset all widgets
        for widget in self.package_widgets.values():
            widget.set_status("checking", "")

        # Start worker
        self.check_worker = PackageCheckWorker(PACKAGE_CHECKS)
        self.check_worker.progress.connect(self.on_check_progress)
        self.check_worker.finished.connect(self.on_check_finished)
        self.check_worker.start()

    def on_check_progress(self, name: str, status: str, details: str):
        """Handle progress update from worker"""
        if name in self.package_widgets:
            self.package_widgets[name].set_status(status, details)
        self.progress_bar.setValue(self.progress_bar.value() + 1)

    def on_check_finished(self, results: Dict):
        """Handle check completion"""
        self.check_btn.setEnabled(True)
        self.check_btn.setText("  Check All")
        self.progress_bar.setVisible(False)

        # Count results
        ok_count = sum(1 for s, _ in results.values() if s == "ok")
        error_count = len(results) - ok_count

        if error_count == 0:
            self.summary_label.setText(f"All {ok_count} packages are working correctly!")
            self.summary_label.setStyleSheet("color: #2ecc71; font-size: 12px;")
            self.fix_all_btn.setVisible(False)
        else:
            self.summary_label.setText(f"{ok_count} OK, {error_count} problems found")
            self.summary_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
            self.fix_all_btn.setVisible(True)

    def fix_package(self, name: str):
        """Fix a single package"""
        if name not in PACKAGE_CHECKS:
            return

        info = PACKAGE_CHECKS[name]
        widget = self.package_widgets.get(name)
        if widget:
            widget.set_installing(True)

        self.install_worker = PackageInstallWorker(name, info["install"])
        self.install_worker.progress.connect(lambda msg: self.summary_label.setText(msg))
        self.install_worker.finished.connect(lambda success, msg: self.on_install_finished(name, success, msg))
        self.install_worker.start()

    def on_install_finished(self, name: str, success: bool, message: str):
        """Handle install completion"""
        widget = self.package_widgets.get(name)
        if widget:
            widget.set_installing(False)

        if success:
            self.summary_label.setText(message)
            self.summary_label.setStyleSheet("color: #2ecc71; font-size: 12px;")
            # Re-check this package
            QTimer.singleShot(1000, self.check_all_packages)
        else:
            self.summary_label.setText(message)
            self.summary_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
            QMessageBox.warning(self, "Installation Failed", message)

    def fix_all_problems(self):
        """Fix all problematic packages"""
        # Find all failed packages
        failed = []
        for name, widget in self.package_widgets.items():
            # Check if fix button is visible (means it failed)
            if widget.fix_btn.isVisible():
                failed.append(name)

        if not failed:
            return

        reply = QMessageBox.question(
            self, "Fix All Problems",
            f"This will reinstall {len(failed)} packages:\n\n" + "\n".join(f"  • {n}" for n in failed) + "\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Fix first one, then chain to next
            self.fix_queue = failed
            self.fix_next_in_queue()

    def fix_next_in_queue(self):
        """Fix next package in queue"""
        if hasattr(self, 'fix_queue') and self.fix_queue:
            next_pkg = self.fix_queue.pop(0)
            self.fix_package(next_pkg)
            # Chain to next after a delay
            if self.fix_queue:
                QTimer.singleShot(2000, self.fix_next_in_queue)


# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark theme
    palette = app.palette()
    palette.setColor(palette.Window, QColor(30, 30, 30))
    palette.setColor(palette.WindowText, QColor(255, 255, 255))
    palette.setColor(palette.Base, QColor(40, 40, 40))
    palette.setColor(palette.Text, QColor(255, 255, 255))
    app.setPalette(palette)

    window = SystemCheckPage()
    window.setWindowTitle("System Check")
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
