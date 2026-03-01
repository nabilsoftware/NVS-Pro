"""
API Keys Manager - Secure API key management for customers
Allows customers to add their own API keys through the UI
Modern card-based dark theme (matching Recreate Video page style)
"""

import json
import subprocess
import sys
from pathlib import Path
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QMessageBox,
                             QScrollArea, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

# Hide console window on Windows
if sys.platform == 'win32':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

# Modern dark theme colors - DaVinci Style (matching ui_modern.py)
COLORS = {
    'bg_page': '#1a1a1a',
    'bg_card': '#252525',
    'bg_input': '#1a1a1a',
    'border_card': '#3a3a3a',
    'border_input': '#3a3a3a',
    'border_focus': '#E67E22',
    'accent_primary': '#D35400',
    'accent_hover': '#F39C12',
    'accent_success': '#27AE60',
    'accent_warning': '#F39C12',
    'accent_error': '#E74C3C',
    'text_primary': '#e0e0e0',
    'text_secondary': '#888888',
    'text_muted': '#666666',
}

# Provider accent colors
PROVIDER_COLORS = {
    'gemini': '#58a6ff',
    'claude': '#ffa657',
    'openai': '#27AE60',
    'huggingface': '#d29922',
    'fish': '#a371f7',
}


class APIKeysManager(QWidget):
    """API Keys management interface for customers - Modern card-based design"""
    apiKeysChanged = pyqtSignal()

    def __init__(self, api_keys_file="api_keys.json", parent=None):
        super().__init__(parent)
        self.api_keys_file = Path(api_keys_file)
        self.api_keys = {}
        self.init_ui()
        self.load_api_keys()

    def _create_card(self, title: str, accent_color: str = None) -> tuple:
        """Create a modern card with title, returns (card_frame, content_layout)"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: none;
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Title with optional accent
        title_label = QLabel(title)
        if accent_color:
            title_label.setStyleSheet(f"""
                color: {accent_color};
                font-size: 15px;
                font-weight: 700;
                padding-bottom: 4px;
            """)
        else:
            title_label.setStyleSheet(f"""
                color: {COLORS['text_primary']};
                font-size: 15px;
                font-weight: 700;
                padding-bottom: 4px;
            """)
        layout.addWidget(title_label)

        return card, layout

    def _create_input_row(self, label_text: str, placeholder: str, is_password: bool = True) -> tuple:
        """Create a modern input row, returns (row_layout, line_edit, show_hide_btn)"""
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel(label_text)
        label.setFixedWidth(70)
        label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: 600; font-size: 13px;")
        row.addWidget(label)

        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setFixedHeight(42)
        if is_password:
            line_edit.setEchoMode(QLineEdit.Password)
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_input']};
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus {{ background: #1f1f1f; }}
            QLineEdit::placeholder {{ color: {COLORS['text_muted']}; }}
        """)
        row.addWidget(line_edit)

        show_hide_btn = None
        if is_password:
            show_hide_btn = QPushButton("Show")
            show_hide_btn.setFixedSize(55, 36)
            show_hide_btn.setCursor(Qt.PointingHandCursor)
            show_hide_btn.setToolTip("Show/Hide password")
            show_hide_btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a;
                    border: none;
                    border-radius: 6px;
                    color: #888888;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #3a3a3a;
                    color: #E67E22;
                }
            """)
            row.addWidget(show_hide_btn)

        return row, line_edit, show_hide_btn

    def _create_status_label(self) -> QLabel:
        """Create a modern status label"""
        status = QLabel("Status: Not configured")
        status.setFixedHeight(36)
        status.setStyleSheet(f"""
            QLabel {{
                background: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_input']};
                border-radius: 8px;
                padding: 0 14px;
                color: {COLORS['text_muted']};
                font-size: 12px;
                font-weight: 500;
            }}
        """)
        return status

    def _create_button(self, text: str, color: str, is_outline: bool = False, small: bool = False) -> QPushButton:
        """Create a modern button"""
        btn = QPushButton(text)
        btn.setFixedHeight(36 if small else 38)
        btn.setCursor(Qt.PointingHandCursor)

        if is_outline:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {COLORS['border_input']};
                    border-radius: 6px;
                    color: {COLORS['text_secondary']};
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: {COLORS['bg_input']};
                    border-color: {color};
                    color: {color};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: none;
                    border-radius: 6px;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {color}dd;
                }}
                QPushButton:disabled {{
                    background: {COLORS['border_input']};
                    color: {COLORS['text_muted']};
                }}
            """)

        return btn

    def _set_status(self, label: QLabel, status_type: str, message: str):
        """Update status label with appropriate styling"""
        colors = {
            'valid': COLORS['accent_success'],
            'invalid': COLORS['accent_error'],
            'testing': COLORS['accent_primary'],
            'warning': COLORS['accent_warning'],
            'changed': COLORS['accent_warning'],
        }
        color = colors.get(status_type, COLORS['text_muted'])

        label.setText(f"Status: {message}")
        label.setStyleSheet(f"""
            QLabel {{
                background: {COLORS['bg_input']};
                border: 1px solid {color}40;
                border-radius: 8px;
                padding: 0 14px;
                color: {color};
                font-size: 12px;
                font-weight: 600;
            }}
        """)

    def init_ui(self):
        """Initialize the API keys UI with modern card-based design"""
        # Main layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {COLORS['bg_card']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border_input']};
                border-radius: 4px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['text_muted']};
            }}
        """)

        # Content widget
        content = QWidget()
        content.setStyleSheet(f"background: {COLORS['bg_page']};")
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(0, 0, 16, 20)

        # ===== GEMINI CARD =====
        gemini_card, gemini_layout = self._create_card("🔷 Google Gemini", PROVIDER_COLORS['gemini'])

        # API Key row
        key_row, self.gemini_key_input, self.show_hide_btn = self._create_input_row(
            "API Key:", "Enter your Gemini API key..."
        )
        self.gemini_key_input.textChanged.connect(self.on_key_changed)
        self.show_hide_btn.clicked.connect(self.toggle_show_hide)
        gemini_layout.addLayout(key_row)

        # Model row
        model_row, self.model_input, _ = self._create_input_row(
            "Model:", "e.g., gemini-2.5-pro", is_password=False
        )
        self.model_input.setText("gemini-2.5-pro")
        gemini_layout.addLayout(model_row)

        # Status
        self.status_label = self._create_status_label()
        gemini_layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.save_btn = self._create_button("Save & Test", PROVIDER_COLORS['gemini'])
        self.save_btn.clicked.connect(self.save_and_test_gemini)
        btn_row.addWidget(self.save_btn)

        self.clear_btn = self._create_button("Clear", COLORS['accent_error'], is_outline=True, small=True)
        self.clear_btn.clicked.connect(self.clear_gemini_key)
        btn_row.addWidget(self.clear_btn)

        btn_row.addStretch()

        gemini_layout.addLayout(btn_row)
        main_layout.addWidget(gemini_card)

        # ===== CLAUDE CARD =====
        claude_card, claude_layout = self._create_card("🟠 Claude (Anthropic)", PROVIDER_COLORS['claude'])

        key_row, self.claude_key_input, self.claude_show_hide_btn = self._create_input_row(
            "API Key:", "Enter Claude API key (sk-ant-...)..."
        )
        self.claude_key_input.textChanged.connect(self.on_claude_key_changed)
        self.claude_show_hide_btn.clicked.connect(self.toggle_claude_show_hide)
        claude_layout.addLayout(key_row)

        model_row, self.claude_model_input, _ = self._create_input_row(
            "Model:", "e.g., claude-sonnet-4-20250514", is_password=False
        )
        self.claude_model_input.setText("claude-sonnet-4-20250514")
        claude_layout.addLayout(model_row)

        self.claude_status_label = self._create_status_label()
        claude_layout.addWidget(self.claude_status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.claude_save_btn = self._create_button("Save & Test", PROVIDER_COLORS['claude'])
        self.claude_save_btn.clicked.connect(self.save_and_test_claude)
        btn_row.addWidget(self.claude_save_btn)

        self.claude_clear_btn = self._create_button("Clear", COLORS['accent_error'], is_outline=True, small=True)
        self.claude_clear_btn.clicked.connect(self.clear_claude_key)
        btn_row.addWidget(self.claude_clear_btn)

        btn_row.addStretch()

        claude_layout.addLayout(btn_row)
        main_layout.addWidget(claude_card)

        # ===== OPENAI CARD =====
        openai_card, openai_layout = self._create_card("🟢 OpenAI (ChatGPT)", PROVIDER_COLORS['openai'])

        key_row, self.openai_key_input, self.openai_show_hide_btn = self._create_input_row(
            "API Key:", "Enter OpenAI API key (sk-...)..."
        )
        self.openai_key_input.textChanged.connect(self.on_openai_key_changed)
        self.openai_show_hide_btn.clicked.connect(self.toggle_openai_show_hide)
        openai_layout.addLayout(key_row)

        model_row, self.openai_model_input, _ = self._create_input_row(
            "Model:", "e.g., gpt-4o, gpt-4-turbo", is_password=False
        )
        self.openai_model_input.setText("gpt-4o")
        openai_layout.addLayout(model_row)

        self.openai_status_label = self._create_status_label()
        openai_layout.addWidget(self.openai_status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.openai_save_btn = self._create_button("Save & Test", PROVIDER_COLORS['openai'])
        self.openai_save_btn.clicked.connect(self.save_and_test_openai)
        btn_row.addWidget(self.openai_save_btn)

        self.openai_clear_btn = self._create_button("Clear", COLORS['accent_error'], is_outline=True, small=True)
        self.openai_clear_btn.clicked.connect(self.clear_openai_key)
        btn_row.addWidget(self.openai_clear_btn)

        btn_row.addStretch()

        openai_layout.addLayout(btn_row)
        main_layout.addWidget(openai_card)

        # ===== HUGGINGFACE CARD =====
        hf_card, hf_layout = self._create_card("🤗 HuggingFace", PROVIDER_COLORS['huggingface'])

        # Info text
        hf_info = QLabel("Token for speaker diarization (pyannote)")
        hf_info.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; padding-bottom: 2px;")
        hf_layout.addWidget(hf_info)

        key_row, self.hf_token_input, self.hf_show_hide_btn = self._create_input_row(
            "Token:", "Enter HuggingFace token (hf_...)..."
        )
        self.hf_token_input.textChanged.connect(self.on_hf_token_changed)
        self.hf_show_hide_btn.clicked.connect(self.toggle_hf_show_hide)
        hf_layout.addLayout(key_row)

        self.hf_status_label = self._create_status_label()
        hf_layout.addWidget(self.hf_status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.hf_save_btn = self._create_button("Save", PROVIDER_COLORS['huggingface'])
        self.hf_save_btn.clicked.connect(self.save_hf_token)
        btn_row.addWidget(self.hf_save_btn)

        self.hf_clear_btn = self._create_button("Clear", COLORS['accent_error'], is_outline=True, small=True)
        self.hf_clear_btn.clicked.connect(self.clear_hf_token)
        btn_row.addWidget(self.hf_clear_btn)

        hf_open_btn = self._create_button("Get Token", COLORS['accent_primary'], is_outline=True, small=True)
        hf_open_btn.clicked.connect(self.open_huggingface)
        btn_row.addWidget(hf_open_btn)

        btn_row.addStretch()

        hf_layout.addLayout(btn_row)
        main_layout.addWidget(hf_card)

        # ===== FISH AUDIO CARD =====
        fish_card, fish_layout = self._create_card("🐟 Fish Audio (TTS)", PROVIDER_COLORS['fish'])

        fish_info = QLabel("API key for fast voiceover generation")
        fish_info.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; padding-bottom: 2px;")
        fish_layout.addWidget(fish_info)

        key_row, self.fish_api_key_input, self.fish_show_hide_btn = self._create_input_row(
            "API Key:", "Enter Fish Audio API key..."
        )
        self.fish_api_key_input.textChanged.connect(self.on_fish_key_changed)
        self.fish_show_hide_btn.clicked.connect(self.toggle_fish_show_hide)
        fish_layout.addLayout(key_row)

        self.fish_status_label = self._create_status_label()
        fish_layout.addWidget(self.fish_status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.fish_save_btn = self._create_button("Save & Test", PROVIDER_COLORS['fish'])
        self.fish_save_btn.clicked.connect(self.save_and_test_fish)
        btn_row.addWidget(self.fish_save_btn)

        self.fish_clear_btn = self._create_button("Clear", COLORS['accent_error'], is_outline=True, small=True)
        self.fish_clear_btn.clicked.connect(self.clear_fish_api_key)
        btn_row.addWidget(self.fish_clear_btn)

        btn_row.addStretch()

        fish_layout.addLayout(btn_row)
        main_layout.addWidget(fish_card)

        # ===== SECURITY WARNING =====
        warning_card = QFrame()
        warning_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: none;
                border-radius: 8px;
            }
        """)
        warning_layout = QHBoxLayout(warning_card)
        warning_layout.setContentsMargins(16, 10, 16, 10)

        warning_icon = QLabel("!")
        warning_icon.setFixedSize(24, 24)
        warning_icon.setAlignment(Qt.AlignCenter)
        warning_icon.setStyleSheet("""
            background: #E67E22;
            border-radius: 12px;
            color: white;
            font-size: 14px;
            font-weight: bold;
        """)
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel("Keep your API keys private. Never share them or commit to version control.")
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: #888888; font-size: 12px;")
        warning_layout.addWidget(warning_text)

        main_layout.addWidget(warning_card)

        # Spacer
        main_layout.addStretch()

        # Set up scroll area
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ==================== GEMINI METHODS ====================

    def load_api_keys(self):
        """Load API keys from file"""
        if self.api_keys_file.exists():
            try:
                with open(self.api_keys_file, 'r', encoding='utf-8') as f:
                    self.api_keys = json.load(f)

                if "gemini" in self.api_keys:
                    gemini_data = self.api_keys["gemini"]
                    self.gemini_key_input.setText(gemini_data.get("api_key", ""))
                    self.model_input.setText(gemini_data.get("model", "gemini-2.5-pro"))

                    status = gemini_data.get("status", "not_tested")
                    if status == "valid":
                        self._set_status(self.status_label, "valid", "Valid (tested)")
                    elif gemini_data.get("api_key"):
                        self._set_status(self.status_label, "warning", "Configured (not tested)")

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load API keys: {e}")
        else:
            self.api_keys = {}

        self.load_hf_token()
        self.load_fish_api_key()
        self.load_claude_api_key()
        self.load_openai_api_key()


    def toggle_show_hide(self):
        """Toggle show/hide for Gemini API key"""
        if self.gemini_key_input.echoMode() == QLineEdit.Password:
            self.gemini_key_input.setEchoMode(QLineEdit.Normal)
            self.show_hide_btn.setText("Hide")
        else:
            self.gemini_key_input.setEchoMode(QLineEdit.Password)
            self.show_hide_btn.setText("Show")

    def on_key_changed(self):
        """Reset status when key is changed"""
        self._set_status(self.status_label, "changed", "Not saved")

    def get_embedded_python(self):
        """Get the embedded Python executable path"""
        import sys
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent

        python_exe = app_dir / "python" / "python.exe"
        if python_exe.exists():
            return str(python_exe)
        return sys.executable

    def save_and_test_gemini(self):
        """Save and test Gemini API connection"""
        import os

        api_key = self.gemini_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your Gemini API key first!")
            return

        # Save first
        try:
            self.api_keys["gemini"] = {
                "api_key": api_key,
                "model": self.model_input.text().strip() or "gemini-2.5-pro",
                "status": "testing",
            }
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, indent=2)
            self.apiKeysChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            return

        # Test connection
        self._set_status(self.status_label, "testing", "Testing connection...")
        self.save_btn.setEnabled(False)
        self.save_btn.setText("Testing...")

        # Process events to update UI
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            model_name = self.model_input.text().strip() or "gemini-2.5-pro"
            python_exe = self.get_embedded_python()

            test_script = '''
import os
import google.generativeai as genai
api_key = os.environ.get("GEMINI_TEST_KEY")
model_name = os.environ.get("GEMINI_TEST_MODEL")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name)
response = model.generate_content("Say hello")
print("SUCCESS:" + response.text[:100])
'''

            env = os.environ.copy()
            env["GEMINI_TEST_KEY"] = api_key
            env["GEMINI_TEST_MODEL"] = model_name
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                [python_exe, "-c", test_script],
                capture_output=True, text=True, timeout=60,
                encoding='utf-8', errors='replace', env=env,
                creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0 and "SUCCESS:" in result.stdout:
                self._set_status(self.status_label, "valid", "Saved & Valid!")
                self.api_keys["gemini"]["status"] = "valid"
                with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                    json.dump(self.api_keys, f, indent=2)
            else:
                raise Exception(result.stderr or result.stdout or "Unknown error")

        except subprocess.TimeoutExpired:
            self._set_status(self.status_label, "warning", "Saved (test timeout)")
        except Exception as e:
            self._set_status(self.status_label, "warning", "Saved (test failed)")
        finally:
            self.save_btn.setEnabled(True)
            self.save_btn.setText("Save & Test")

    def clear_gemini_key(self):
        """Clear Gemini API key"""
        reply = QMessageBox.question(self, "Confirm", "Clear Gemini API key?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.gemini_key_input.clear()
            self._set_status(self.status_label, "default", "Not configured")

    def get_gemini_api_key(self):
        return self.gemini_key_input.text().strip()

    def get_gemini_model(self):
        return self.model_input.text().strip()

    # ==================== CLAUDE METHODS ====================

    def load_claude_api_key(self):
        """Load Claude API key"""
        if "claude" in self.api_keys:
            data = self.api_keys["claude"]
            self.claude_key_input.setText(data.get("api_key", ""))
            self.claude_model_input.setText(data.get("model", "claude-sonnet-4-20250514"))

            status = data.get("status", "not_tested")
            if status == "valid":
                self._set_status(self.claude_status_label, "valid", "Valid (tested)")
            elif data.get("api_key"):
                self._set_status(self.claude_status_label, "warning", "Configured")


    def save_and_test_claude(self):
        """Save and test Claude API connection"""
        import os

        api_key = self.claude_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing", "Please enter Claude API key!")
            return

        # Save first
        try:
            self.api_keys["claude"] = {
                "api_key": api_key,
                "model": self.claude_model_input.text().strip() or "claude-sonnet-4-20250514",
                "status": "testing",
            }
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, indent=2)
            self.apiKeysChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            return

        # Test connection
        self._set_status(self.claude_status_label, "testing", "Testing connection...")
        self.claude_save_btn.setEnabled(False)
        self.claude_save_btn.setText("Testing...")

        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            model_name = self.claude_model_input.text().strip() or "claude-sonnet-4-20250514"
            python_exe = self.get_embedded_python()

            test_script = '''
import os, requests
api_key = os.environ.get("CLAUDE_TEST_KEY")
model_name = os.environ.get("CLAUDE_TEST_MODEL")
headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
data = {"model": model_name, "max_tokens": 100, "messages": [{"role": "user", "content": "Say hello"}]}
response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data, timeout=60)
if response.status_code == 200:
    print("SUCCESS:" + response.json().get("content", [{}])[0].get("text", "")[:100])
else:
    print(f"ERROR:{response.status_code}")
'''

            env = os.environ.copy()
            env["CLAUDE_TEST_KEY"] = api_key
            env["CLAUDE_TEST_MODEL"] = model_name
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                [python_exe, "-c", test_script],
                capture_output=True, text=True, timeout=90,
                encoding='utf-8', errors='replace', env=env,
                creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0 and "SUCCESS:" in result.stdout:
                self._set_status(self.claude_status_label, "valid", "Saved & Valid!")
                self.api_keys["claude"]["status"] = "valid"
                with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                    json.dump(self.api_keys, f, indent=2)
            else:
                raise Exception(result.stderr or result.stdout or "Unknown error")

        except subprocess.TimeoutExpired:
            self._set_status(self.claude_status_label, "warning", "Saved (test timeout)")
        except Exception as e:
            self._set_status(self.claude_status_label, "warning", "Saved (test failed)")
        finally:
            self.claude_save_btn.setEnabled(True)
            self.claude_save_btn.setText("Save & Test")

    def toggle_claude_show_hide(self):
        if self.claude_key_input.echoMode() == QLineEdit.Password:
            self.claude_key_input.setEchoMode(QLineEdit.Normal)
            self.claude_show_hide_btn.setText("Hide")
        else:
            self.claude_key_input.setEchoMode(QLineEdit.Password)
            self.claude_show_hide_btn.setText("Show")

    def on_claude_key_changed(self):
        self._set_status(self.claude_status_label, "changed", "Not saved")

    def clear_claude_key(self):
        reply = QMessageBox.question(self, "Confirm", "Clear Claude API key?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.claude_key_input.clear()
            self._set_status(self.claude_status_label, "default", "Not configured")

    def get_claude_api_key(self):
        return self.claude_key_input.text().strip()

    def get_claude_model(self):
        return self.claude_model_input.text().strip()

    # ==================== OPENAI METHODS ====================

    def load_openai_api_key(self):
        """Load OpenAI API key"""
        if "openai" in self.api_keys:
            data = self.api_keys["openai"]
            self.openai_key_input.setText(data.get("api_key", ""))
            self.openai_model_input.setText(data.get("model", "gpt-4o"))

            status = data.get("status", "not_tested")
            if status == "valid":
                self._set_status(self.openai_status_label, "valid", "Valid (tested)")
            elif data.get("api_key"):
                self._set_status(self.openai_status_label, "warning", "Configured")


    def save_and_test_openai(self):
        """Save and test OpenAI API connection"""
        import os

        api_key = self.openai_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing", "Please enter OpenAI API key!")
            return

        # Save first
        try:
            self.api_keys["openai"] = {
                "api_key": api_key,
                "model": self.openai_model_input.text().strip() or "gpt-4o",
                "status": "testing",
            }
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, indent=2)
            self.apiKeysChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            return

        # Test connection
        self._set_status(self.openai_status_label, "testing", "Testing connection...")
        self.openai_save_btn.setEnabled(False)
        self.openai_save_btn.setText("Testing...")

        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            model_name = self.openai_model_input.text().strip() or "gpt-4o"
            python_exe = self.get_embedded_python()

            test_script = '''
import os, requests
api_key = os.environ.get("OPENAI_TEST_KEY")
model_name = os.environ.get("OPENAI_TEST_MODEL")
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
data = {"model": model_name, "max_tokens": 100, "messages": [{"role": "user", "content": "Say hello"}]}
response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=60)
if response.status_code == 200:
    print("SUCCESS:" + response.json().get("choices", [{}])[0].get("message", {}).get("content", "")[:100])
else:
    print(f"ERROR:{response.status_code}")
'''

            env = os.environ.copy()
            env["OPENAI_TEST_KEY"] = api_key
            env["OPENAI_TEST_MODEL"] = model_name
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                [python_exe, "-c", test_script],
                capture_output=True, text=True, timeout=90,
                encoding='utf-8', errors='replace', env=env,
                creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0 and "SUCCESS:" in result.stdout:
                self._set_status(self.openai_status_label, "valid", "Saved & Valid!")
                self.api_keys["openai"]["status"] = "valid"
                with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                    json.dump(self.api_keys, f, indent=2)
            else:
                raise Exception(result.stderr or result.stdout or "Unknown error")

        except subprocess.TimeoutExpired:
            self._set_status(self.openai_status_label, "warning", "Saved (test timeout)")
        except Exception as e:
            self._set_status(self.openai_status_label, "warning", "Saved (test failed)")
        finally:
            self.openai_save_btn.setEnabled(True)
            self.openai_save_btn.setText("Save & Test")

    def toggle_openai_show_hide(self):
        if self.openai_key_input.echoMode() == QLineEdit.Password:
            self.openai_key_input.setEchoMode(QLineEdit.Normal)
            self.openai_show_hide_btn.setText("Hide")
        else:
            self.openai_key_input.setEchoMode(QLineEdit.Password)
            self.openai_show_hide_btn.setText("Show")

    def on_openai_key_changed(self):
        self._set_status(self.openai_status_label, "changed", "Not saved")

    def clear_openai_key(self):
        reply = QMessageBox.question(self, "Confirm", "Clear OpenAI API key?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.openai_key_input.clear()
            self._set_status(self.openai_status_label, "default", "Not configured")

    def get_openai_api_key(self):
        return self.openai_key_input.text().strip()

    def get_openai_model(self):
        return self.openai_model_input.text().strip()

    # ==================== HUGGINGFACE METHODS ====================

    def get_hf_token_path(self):
        hf_cache = Path.home() / ".cache" / "huggingface"
        hf_cache.mkdir(parents=True, exist_ok=True)
        return hf_cache / "token"

    def load_hf_token(self):
        """Load HuggingFace token"""
        token_path = self.get_hf_token_path()
        if token_path.exists():
            try:
                token = token_path.read_text().strip()
                if token:
                    self.hf_token_input.setText(token)
                    self._set_status(self.hf_status_label, "valid", "Token configured")
                    return
            except Exception:
                pass
        self._set_status(self.hf_status_label, "warning", "No token")

    def save_hf_token(self):
        """Save HuggingFace token"""
        token = self.hf_token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Missing", "Please enter HuggingFace token!")
            return

        try:
            token_path = self.get_hf_token_path()
            token_path.write_text(token)
            self._set_status(self.hf_status_label, "valid", "Token saved!")
            QMessageBox.information(self, "Success", f"Token saved to {token_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def toggle_hf_show_hide(self):
        if self.hf_token_input.echoMode() == QLineEdit.Password:
            self.hf_token_input.setEchoMode(QLineEdit.Normal)
            self.hf_show_hide_btn.setText("Hide")
        else:
            self.hf_token_input.setEchoMode(QLineEdit.Password)
            self.hf_show_hide_btn.setText("Show")

    def on_hf_token_changed(self):
        self._set_status(self.hf_status_label, "changed", "Not saved")

    def clear_hf_token(self):
        reply = QMessageBox.question(self, "Confirm", "Clear HuggingFace token?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.hf_token_input.clear()
            try:
                token_path = self.get_hf_token_path()
                if token_path.exists():
                    token_path.unlink()
            except Exception:
                pass
            self._set_status(self.hf_status_label, "default", "Not configured")

    def open_huggingface(self):
        import webbrowser
        webbrowser.open("https://huggingface.co/settings/tokens")

    def get_hf_token(self):
        return self.hf_token_input.text().strip()

    # ==================== FISH AUDIO METHODS ====================

    def load_fish_api_key(self):
        """Load Fish Audio API key"""
        if "fish_audio" in self.api_keys:
            data = self.api_keys["fish_audio"]
            self.fish_api_key_input.setText(data.get("api_key", ""))

            status = data.get("status", "not_tested")
            if status == "valid":
                self._set_status(self.fish_status_label, "valid", "Valid (tested)")
            elif data.get("api_key"):
                self._set_status(self.fish_status_label, "warning", "Configured")


    def save_and_test_fish(self):
        """Save and test Fish Audio API connection"""
        import os

        api_key = self.fish_api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing", "Please enter Fish Audio API key!")
            return

        # Save first
        try:
            self.api_keys["fish_audio"] = {
                "api_key": api_key,
                "status": "testing",
            }
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, indent=2)
            self.apiKeysChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            return

        # Test connection
        self._set_status(self.fish_status_label, "testing", "Testing connection...")
        self.fish_save_btn.setEnabled(False)
        self.fish_save_btn.setText("Testing...")

        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            python_exe = self.get_embedded_python()

            test_script = '''
import os, requests
api_key = os.environ.get("FISH_TEST_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
response = requests.get("https://api.fish.audio/wallet/self/api-credit", headers=headers, timeout=30)
if response.status_code == 200:
    print("SUCCESS:API key valid")
elif response.status_code == 401:
    print("ERROR:Invalid API key")
elif response.status_code == 403:
    print("ERROR:Access forbidden")
else:
    print(f"ERROR:Status {response.status_code}")
'''

            env = os.environ.copy()
            env["FISH_TEST_KEY"] = api_key
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                [python_exe, "-c", test_script],
                capture_output=True, text=True, timeout=60,
                encoding='utf-8', errors='replace', env=env,
                creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0 and "SUCCESS:" in result.stdout:
                self._set_status(self.fish_status_label, "valid", "Saved & Valid!")
                self.api_keys["fish_audio"]["status"] = "valid"
                with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                    json.dump(self.api_keys, f, indent=2)
            else:
                raise Exception(result.stderr or result.stdout or "Unknown error")

        except subprocess.TimeoutExpired:
            self._set_status(self.fish_status_label, "warning", "Saved (test timeout)")
        except Exception as e:
            self._set_status(self.fish_status_label, "warning", "Saved (test failed)")
        finally:
            self.fish_save_btn.setEnabled(True)
            self.fish_save_btn.setText("Save & Test")

    def toggle_fish_show_hide(self):
        if self.fish_api_key_input.echoMode() == QLineEdit.Password:
            self.fish_api_key_input.setEchoMode(QLineEdit.Normal)
            self.fish_show_hide_btn.setText("Hide")
        else:
            self.fish_api_key_input.setEchoMode(QLineEdit.Password)
            self.fish_show_hide_btn.setText("Show")

    def on_fish_key_changed(self):
        self._set_status(self.fish_status_label, "changed", "Not saved")

    def clear_fish_api_key(self):
        reply = QMessageBox.question(self, "Confirm", "Clear Fish Audio API key?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.fish_api_key_input.clear()
            self._set_status(self.fish_status_label, "default", "Not configured")

    def open_fish_api_keys(self):
        import webbrowser
        webbrowser.open("https://fish.audio/api-keys")

    def open_fish_audio(self):
        import webbrowser
        webbrowser.open("https://fish.audio/app/text-to-speech/")

    def get_fish_api_key(self):
        return self.fish_api_key_input.text().strip()
