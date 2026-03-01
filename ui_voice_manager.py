"""
Voice Manager - Add, Edit, Delete voice models
Complete voice management interface - NO manual editing needed!
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QListWidget, QLabel, QMessageBox, QLineEdit,
                             QTextEdit, QWidget, QSplitter, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ui_config_manager import ConfigManager
from ui_validators import Validators


class VoiceEditorDialog(QDialog):
    """Dialog for adding/editing a voice"""

    def __init__(self, config_manager: ConfigManager, voice_name: str = None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.voice_name = voice_name  # None for new voice
        self.is_edit_mode = voice_name is not None

        self.setWindowTitle("Edit Voice" if self.is_edit_mode else "Add New Voice")
        self.setMinimumSize(600, 400)
        self.init_ui()

        if self.is_edit_mode:
            self.load_voice_data()

    def init_ui(self):
        # Apply dark theme
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #e0e0e0; }
            QLineEdit, QTextEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px;
                color: #e0e0e0;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #E67E22; }
            QPushButton {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 16px;
                color: #e0e0e0;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3a3a3a; }
            QGroupBox {
                color: #E67E22;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #252525;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Title
        title = QLabel("✏️ Edit Voice" if self.is_edit_mode else "➕ Add New Voice")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(title)

        # Voice Name
        name_label = QLabel("Voice Name*:")
        layout.addWidget(name_label)

        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Enter unique voice name (e.g., PROFESSIONAL_VOICE)")
        if self.is_edit_mode:
            self.name_field.setEnabled(False)  # Can't change name in edit mode
        layout.addWidget(self.name_field)

        # Description
        desc_label = QLabel("Description:")
        layout.addWidget(desc_label)

        self.desc_field = QTextEdit()
        self.desc_field.setPlaceholderText("Describe this voice (e.g., Professional, energetic narrator)")
        self.desc_field.setMaximumHeight(80)
        layout.addWidget(self.desc_field)

        # Fish Audio URL
        url_label = QLabel("Fish Audio URL*:")
        layout.addWidget(url_label)

        self.url_field = QLineEdit()
        self.url_field.setPlaceholderText("https://fish.audio/app/text-to-speech/?modelId=...")
        layout.addWidget(self.url_field)

        # Help instructions
        help_group = QGroupBox("How to get Fish Audio URL:")
        help_layout = QVBoxLayout()
        help_text = QLabel(
            "1. Go to https://fish.audio/\n"
            "2. Browse available voices\n"
            "3. Click on a voice you like\n"
            "4. Click 'Text-to-Speech' button\n"
            "5. Copy the URL from your browser address bar\n"
            "6. Paste it above"
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)

        # Buttons
        button_layout = QHBoxLayout()

        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self.save_voice)
        btn_save.setStyleSheet("background-color: #238636; border: 1px solid #238636; color: white; padding: 10px 20px; font-weight: bold; border-radius: 6px;")
        button_layout.addWidget(btn_save)

        btn_cancel = QPushButton("❌ Cancel")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_voice_data(self):
        """Load existing voice data for editing"""
        voice = self.config_manager.get_voice(self.voice_name)
        if voice:
            self.name_field.setText(voice.get("name", ""))
            self.desc_field.setPlainText(voice.get("description", ""))
            self.url_field.setText(voice.get("url", ""))

    def save_voice(self):
        """Save voice data"""
        # Get values
        name = self.name_field.text().strip()
        description = self.desc_field.toPlainText().strip()
        url = self.url_field.text().strip()

        # Validate name
        existing_names = list(self.config_manager.get_voices().keys())
        if not self.is_edit_mode:  # Only check uniqueness for new voices
            valid, msg = Validators.validate_voice_name(name, existing_names)
        else:
            valid, msg = Validators.validate_required_field(name, "Voice name")

        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return

        # Validate URL
        valid, msg = Validators.validate_fish_audio_url(url)
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return

        # Create voice data
        voice_data = {
            "name": name,
            "description": description,
            "url": url
        }

        # Save to config
        if self.is_edit_mode:
            success = self.config_manager.update_voice(self.voice_name, voice_data)
            action = "updated"
        else:
            success = self.config_manager.add_voice(name, voice_data)
            action = "added"

        if success:
            QMessageBox.information(self, "Success", f"Voice '{name}' {action} successfully!")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to {action.replace('ed', '')} voice!")


class VoiceManagerDialog(QDialog):
    """Main voice management dialog"""
    voicesChanged = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager

        self.setWindowTitle("🎙️ Voice Manager")
        self.setMinimumSize(800, 600)
        self.init_ui()
        self.load_voices()

    def init_ui(self):
        layout = QHBoxLayout()

        # Create splitter for list and details
        splitter = QSplitter(Qt.Horizontal)

        # LEFT SIDE: Voice List
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        # List title
        list_title = QLabel("Available Voices")
        list_title.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(list_title)

        # Voice list
        self.voice_list = QListWidget()
        self.voice_list.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.voice_list)

        # Action buttons
        btn_layout = QVBoxLayout()

        self.btn_add = QPushButton("➕ Add New Voice")
        self.btn_add.clicked.connect(self.add_voice)
        btn_layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏️ Edit Voice")
        self.btn_edit.clicked.connect(self.edit_voice)
        self.btn_edit.setEnabled(False)
        btn_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑️ Delete Voice")
        self.btn_delete.clicked.connect(self.delete_voice)
        self.btn_delete.setEnabled(False)
        btn_layout.addWidget(self.btn_delete)

        btn_layout.addStretch()
        left_layout.addLayout(btn_layout)

        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # RIGHT SIDE: Voice Details
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # Details title
        details_title = QLabel("Voice Details")
        details_title.setFont(QFont("Arial", 12, QFont.Bold))
        right_layout.addWidget(details_title)

        # Details display
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Select a voice to view details...")
        right_layout.addWidget(self.details_text)

        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # Bottom buttons
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    def load_voices(self):
        """Load voices from config"""
        self.voice_list.clear()
        voices = self.config_manager.get_voices()

        if not voices:
            self.details_text.setPlainText("No voices configured.\nClick 'Add New Voice' to get started!")
            return

        for name, voice_data in voices.items():
            desc = voice_data.get("description", "No description")
            self.voice_list.addItem(f"{name} - {desc}")

    def on_selection_changed(self):
        """Handle voice selection"""
        selected_items = self.voice_list.selectedItems()
        has_selection = len(selected_items) > 0

        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

        if has_selection:
            # Get voice name (before the " - " separator)
            item_text = selected_items[0].text()
            voice_name = item_text.split(" - ")[0]

            # Display details
            voice = self.config_manager.get_voice(voice_name)
            if voice:
                details = f"""
Name: {voice.get('name', 'Unknown')}

Description:
{voice.get('description', 'No description')}

Fish Audio URL:
{voice.get('url', 'No URL')}
                """.strip()
                self.details_text.setPlainText(details)
        else:
            self.details_text.clear()

    def add_voice(self):
        """Add new voice"""
        dialog = VoiceEditorDialog(self.config_manager, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_voices()
            self.voicesChanged.emit()
            QMessageBox.information(self, "Success", "Voice added successfully!")

    def edit_voice(self):
        """Edit selected voice"""
        selected_items = self.voice_list.selectedItems()
        if not selected_items:
            return

        item_text = selected_items[0].text()
        voice_name = item_text.split(" - ")[0]

        dialog = VoiceEditorDialog(self.config_manager, voice_name, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_voices()
            self.voicesChanged.emit()

    def delete_voice(self):
        """Delete selected voice"""
        selected_items = self.voice_list.selectedItems()
        if not selected_items:
            return

        item_text = selected_items[0].text()
        voice_name = item_text.split(" - ")[0]

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete voice '{voice_name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.config_manager.delete_voice(voice_name):
                self.load_voices()
                self.voicesChanged.emit()
                QMessageBox.information(self, "Success", f"Voice '{voice_name}' deleted successfully!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete voice '{voice_name}'!")
