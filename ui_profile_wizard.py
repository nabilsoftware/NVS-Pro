"""
Channel Creation Wizard - 7-step guided channel creation
Makes it EASY for customers to create perfect channels!
NO config.json editing needed!
"""

from PyQt5.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QTextEdit, QRadioButton,
                             QButtonGroup, QMessageBox, QPushButton, QComboBox,
                             QGroupBox, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from pathlib import Path

from ui_config_manager import ConfigManager
from ui_validators import Validators, ProfileValidator
from ui_widgets import PathSelector, ColorPicker, LabeledSlider, LabeledCheckBox, LabeledComboBox


class ProfileWizard(QWizard):
    """7-step wizard for creating profiles"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.profile_data = {}

        self.setWindowTitle("🧙 Channel Creation Wizard")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(700, 550)

        # Apply dark theme
        self.setStyleSheet("""
            QWizard { background-color: #0d1117; }
            QWizardPage { background-color: #0d1117; }
            QLabel { color: #e6edf3; }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                color: #e6edf3;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #58a6ff; }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 16px;
                color: #e6edf3;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #30363d; }
            QGroupBox {
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #161b22;
            }
            QRadioButton { color: #e6edf3; }
            QRadioButton::indicator {
                width: 16px; height: 16px;
                border-radius: 8px;
                background-color: #21262d;
                border: 1px solid #30363d;
            }
            QRadioButton::indicator:checked {
                background-color: #238636;
                border-color: #238636;
            }
        """)

        # Add pages (Step 6 AI Prompt removed - uses defaults automatically)
        self.addPage(Page1_BasicInfo(self))
        self.addPage(Page2_ChooseVoice(self))
        self.addPage(Page3_VisualStyle(self))
        self.addPage(Page4_AudioSettings(self))
        self.addPage(Page5_Animations(self))
        # Page6_AIPrompt removed - default prompts used automatically
        self.addPage(Page7_YouTubeSettings(self))

    def accept(self):
        """Save profile when wizard completes"""
        # Collect all data
        self.collect_all_data()

        # Validate complete profile
        existing_names = list(self.config_manager.get_profiles().keys())
        valid, errors = ProfileValidator.validate_profile(self.profile_data, existing_names)

        if not valid:
            QMessageBox.warning(
                self,
                "Validation Errors",
                "Please fix the following errors:\n\n" + "\n".join(errors)
            )
            return

        # Save profile
        profile_name = self.profile_data["name"]
        success = self.config_manager.add_profile(profile_name, self.profile_data)

        if success:
            QMessageBox.information(
                self,
                "Success!",
                f"✅ Profile '{profile_name}' created successfully!\n\n"
                f"You can now use this channel to create videos."
            )
            super().accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create channel '{profile_name}'.\n"
                f"The channel name might already exist."
            )

    def collect_all_data(self):
        """Collect data from all pages"""
        for page_id in self.pageIds():
            page = self.page(page_id)
            if hasattr(page, 'get_data'):
                data = page.get_data()
                self.profile_data.update(data)

        # Auto-add default prompts (Step 6 removed from wizard)
        import sys
        if getattr(sys, 'frozen', False):
            script_dir = Path(sys.executable).parent
        else:
            script_dir = Path(__file__).parent

        recreate_prompt = script_dir / "prompts" / "recreate_script_template.txt"
        create_prompt = script_dir / "prompts" / "create_script_template.txt"

        if recreate_prompt.exists():
            self.profile_data["prompt_file"] = str(recreate_prompt)
        if create_prompt.exists():
            self.profile_data["cc_prompt_file"] = str(create_prompt)


# ==================== PAGE 1: Basic Info ====================

class Page1_BasicInfo(QWizardPage):
    """Step 1: Enter basic profile information"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 1: Basic Information")
        self.setSubTitle("Let's start by giving your channel a name and description.")

        layout = QVBoxLayout()

        # Profile Name
        name_label = QLabel("Channel Name*:")
        name_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(name_label)

        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("e.g., ActionMMA, ProfessionalAnalysis, CasualFights")
        self.registerField("profile_name*", self.name_field)
        layout.addWidget(self.name_field)

        hint = QLabel("💡 Tip: Choose a descriptive name that reflects your channel's style")
        hint.setStyleSheet("color: #8b949e; font-style: italic;")
        layout.addWidget(hint)

        layout.addSpacing(20)

        # Description
        desc_label = QLabel("Description:")
        desc_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(desc_label)

        self.desc_field = QTextEdit()
        self.desc_field.setPlaceholderText("Describe your video style, target audience, etc.")
        self.desc_field.setMaximumHeight(100)
        layout.addWidget(self.desc_field)

        layout.addSpacing(20)

        # Category selection
        cat_label = QLabel("Category:")
        cat_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(cat_label)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumHeight(35)
        layout.addWidget(self.category_combo)

        cat_hint = QLabel("💡 Tip: Organize your channels into categories for easier management")
        cat_hint.setStyleSheet("color: #8b949e; font-style: italic;")
        layout.addWidget(cat_hint)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Called when page is shown - refresh categories"""
        self.category_combo.clear()
        categories = self.wizard().config_manager.get_categories()
        for cat in categories:
            self.category_combo.addItem(f"📁 {cat}", cat)

    def validatePage(self):
        """Validate before moving to next page"""
        name = self.name_field.text().strip()
        config_manager = self.wizard().config_manager
        existing_names = list(config_manager.get_profiles().keys())

        valid, msg = Validators.validate_profile_name(name, existing_names)
        if not valid:
            QMessageBox.warning(self, "Invalid Name", msg)
            return False

        return True

    def get_data(self):
        """Get data from this page"""
        return {
            "name": self.name_field.text().strip(),
            "description": self.desc_field.toPlainText().strip(),
            "suffix": self.name_field.text().strip(),
            "category": self.category_combo.currentData() or "Default"
        }


# ==================== PAGE 2: Choose Voice ====================

class Page2_ChooseVoice(QWizardPage):
    """Step 2: Select voice model"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 2: Choose Voice")
        self.setSubTitle("Select the voice that will narrate your videos.")

        layout = QVBoxLayout()

        # Voice selection
        self.voice_buttons = []
        self.button_group = QButtonGroup(self)

        voices_label = QLabel("Available Voices:")
        voices_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(voices_label)

        # Will be populated in initializePage
        self.voices_layout = QVBoxLayout()
        layout.addLayout(self.voices_layout)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Load voices when page is shown"""
        # Clear existing
        for i in reversed(range(self.voices_layout.count())):
            self.voices_layout.itemAt(i).widget().setParent(None)

        self.voice_buttons.clear()

        # Get voices from config
        config_manager = self.wizard().config_manager
        voices = config_manager.get_voices()

        if not voices:
            no_voices = QLabel("⚠️ No voices configured!\nPlease add voices in the Voice Manager first.")
            no_voices.setStyleSheet("color: #da3633; padding: 10px;")
            self.voices_layout.addWidget(no_voices)
            return

        # Create radio button for each voice
        for i, (name, voice_data) in enumerate(voices.items()):
            radio = QRadioButton(f"{name} - {voice_data.get('description', 'No description')}")
            if i == 0:
                radio.setChecked(True)  # Select first by default
            self.button_group.addButton(radio, i)
            self.voice_buttons.append((name, radio))
            self.voices_layout.addWidget(radio)

    def get_data(self):
        """Get selected voice"""
        for name, radio in self.voice_buttons:
            if radio.isChecked():
                return {"default_voice": name}
        return {"default_voice": ""}


# ==================== PAGE 3: Visual Style ====================

class Page3_VisualStyle(QWizardPage):
    """Step 3: Configure visual appearance"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 3: Visual Style")
        self.setSubTitle("Customize how your videos will look.")

        layout = QVBoxLayout()

        # Background Video
        bg_label = QLabel("Background Video:")
        bg_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(bg_label)

        self.bg_selector = PathSelector(
            label="",
            is_file=True,
            file_filter="Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        layout.addWidget(self.bg_selector)

        layout.addSpacing(10)

        # Frame Color
        color_label = QLabel("Frame Color:")
        color_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(color_label)

        self.color_picker = ColorPicker(label="", default_color="#FFFFFF")
        layout.addWidget(self.color_picker)

        layout.addSpacing(10)

        # Video Scale
        scale_label = QLabel("Video Scale:")
        scale_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(scale_label)

        self.scale_slider = LabeledSlider(
            label="Size",
            min_val=0.5,
            max_val=1.0,
            default=0.85,
            decimals=2
        )
        layout.addWidget(self.scale_slider)

        layout.addSpacing(10)

        # Manual Crop
        self.manual_crop = LabeledCheckBox(
            label="Use Manual Crop (more precise control)",
            default=True,
            tooltip="Manual crop gives you more control. AI auto-crop is faster but less precise."
        )
        layout.addWidget(self.manual_crop)

        layout.addStretch()
        self.setLayout(layout)

    def get_data(self):
        """Get visual settings"""
        return {
            "background_video": self.bg_selector.get_path(),
            "frame_color": self.color_picker.get_color(),
            "video_scale": self.scale_slider.get_value(),
            "use_manual_crop": self.manual_crop.is_checked()
        }


# ==================== PAGE 4: Audio Settings ====================

class Page4_AudioSettings(QWizardPage):
    """Step 4: Configure audio levels"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 4: Audio Settings")
        self.setSubTitle("Set voice and music levels for your videos.")

        layout = QVBoxLayout()

        # Background Music
        music_label = QLabel("Background Music (optional):")
        music_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(music_label)

        self.music_selector = PathSelector(
            label="",
            is_file=True,
            file_filter="Audio Files (*.mp3 *.wav *.flac *.m4a)"
        )
        layout.addWidget(self.music_selector)

        layout.addSpacing(15)

        # Voice Level
        voice_label = QLabel("Voice Volume:")
        voice_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(voice_label)

        self.voice_slider = LabeledSlider(
            label="Volume",
            min_val=0.0,
            max_val=2.0,
            default=1.2,
            decimals=1
        )
        layout.addWidget(self.voice_slider)

        hint1 = QLabel("💡 Recommended: 1.0 - 1.5 for clear narration")
        hint1.setStyleSheet("color: #8b949e; font-style: italic;")
        layout.addWidget(hint1)

        layout.addSpacing(15)

        # Music Level
        music_vol_label = QLabel("Background Music Volume:")
        music_vol_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(music_vol_label)

        self.music_slider = LabeledSlider(
            label="Volume",
            min_val=0.0,
            max_val=1.0,
            default=0.09,
            decimals=2
        )
        layout.addWidget(self.music_slider)

        hint2 = QLabel("💡 Recommended: 0.05 - 0.15 for subtle background")
        hint2.setStyleSheet("color: #8b949e; font-style: italic;")
        layout.addWidget(hint2)

        layout.addStretch()
        self.setLayout(layout)

    def get_data(self):
        """Get audio settings"""
        return {
            "background_music": self.music_selector.get_path(),
            "voice_level": self.voice_slider.get_value(),
            "music_level": self.music_slider.get_value()
        }


# ==================== PAGE 5: Animations ====================

class Page5_Animations(QWizardPage):
    """Step 5: Configure animations"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 5: Animations")
        self.setSubTitle("Add smooth transitions and animations to your videos.")

        layout = QVBoxLayout()

        # Enable Animations
        self.enable_anim = LabeledCheckBox(
            label="Enable Animations",
            default=True,
            tooltip="Adds smooth entry/exit animations to clips"
        )
        layout.addWidget(self.enable_anim)

        layout.addSpacing(15)

        # Animation Type
        type_label = QLabel("Animation Type:")
        type_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(type_label)

        self.anim_type = LabeledComboBox(
            label="Type",
            items=["slide", "bounce", "fade", "zoom"]
        )
        self.anim_type.set_current_text("slide")
        layout.addWidget(self.anim_type)

        layout.addSpacing(10)

        # Animation Direction
        dir_label = QLabel("Animation Direction:")
        dir_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(dir_label)

        self.anim_direction = LabeledComboBox(
            label="Direction",
            items=["left", "right", "up", "down"]
        )
        self.anim_direction.set_current_text("left")
        layout.addWidget(self.anim_direction)

        layout.addSpacing(10)

        # Animation Duration
        dur_label = QLabel("Animation Speed:")
        dur_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(dur_label)

        self.anim_duration = LabeledSlider(
            label="Duration",
            min_val=0.1,
            max_val=2.0,
            default=0.5,
            decimals=1
        )
        layout.addWidget(self.anim_duration)

        layout.addStretch()
        self.setLayout(layout)

    def get_data(self):
        """Get animation settings"""
        return {
            "enable_animation": self.enable_anim.is_checked(),
            "animation_type": self.anim_type.get_current_text(),
            "animation_direction": self.anim_direction.get_current_text(),
            "animation_duration": self.anim_duration.get_value(),
            "enable_out_animation": True,
            "out_animation_duration": self.anim_duration.get_value()
        }


# ==================== PAGE 6: AI Prompt ====================

class Page6_AIPrompt(QWizardPage):
    """Step 6: Select or create AI prompt"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 6: AI Script Prompts")
        self.setSubTitle("Set up prompts for Recreate Video and Create Video.")

        layout = QVBoxLayout()

        info = QLabel(
            "Choose prompts for each video mode. Default prompts are provided.\n"
            "You can customize them later if needed."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(10)

        # ============ RECREATE VIDEO PROMPT ============
        recreate_group = QGroupBox("🔄 Recreate Video Prompt")
        recreate_layout = QVBoxLayout(recreate_group)

        self.recreate_prompt_selector = PathSelector(
            label="",
            is_file=True,
            file_filter="Text Files (*.txt)"
        )
        recreate_layout.addWidget(self.recreate_prompt_selector)

        recreate_btn_row = QHBoxLayout()
        btn_recreate_default = QPushButton("✅ Use Default")
        btn_recreate_default.setStyleSheet("QPushButton { background-color: #238636; } QPushButton:hover { background-color: #2ea043; }")
        btn_recreate_default.clicked.connect(self.use_default_recreate_prompt)
        recreate_btn_row.addWidget(btn_recreate_default)
        recreate_btn_row.addStretch()
        recreate_layout.addLayout(recreate_btn_row)

        layout.addWidget(recreate_group)

        layout.addSpacing(10)

        # ============ CREATE VIDEO PROMPT ============
        create_group = QGroupBox("🎬 Create Video Prompt")
        create_layout = QVBoxLayout(create_group)

        self.create_prompt_selector = PathSelector(
            label="",
            is_file=True,
            file_filter="Text Files (*.txt)"
        )
        create_layout.addWidget(self.create_prompt_selector)

        create_btn_row = QHBoxLayout()
        btn_create_default = QPushButton("✅ Use Default")
        btn_create_default.setStyleSheet("QPushButton { background-color: #238636; } QPushButton:hover { background-color: #2ea043; }")
        btn_create_default.clicked.connect(self.use_default_create_prompt)
        create_btn_row.addWidget(btn_create_default)
        create_btn_row.addStretch()
        create_layout.addLayout(create_btn_row)

        layout.addWidget(create_group)

        # Keep old selector for backwards compatibility
        self.prompt_selector = self.recreate_prompt_selector

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Called when page is shown - auto-load default prompts"""
        # Auto-select default prompts if not already set
        if not self.recreate_prompt_selector.get_path():
            self.use_default_recreate_prompt()
        if not self.create_prompt_selector.get_path():
            self.use_default_create_prompt()

    def _get_script_dir(self):
        """Get the script directory"""
        import sys
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        else:
            return Path(__file__).parent

    def use_default_recreate_prompt(self):
        """Use the default Recreate Video prompt template"""
        script_dir = self._get_script_dir()
        default_prompt = script_dir / "prompts" / "recreate_script_template.txt"

        if default_prompt.exists():
            self.recreate_prompt_selector.set_path(str(default_prompt))
        else:
            # Create if doesn't exist
            prompts_folder = script_dir / "prompts"
            prompts_folder.mkdir(parents=True, exist_ok=True)
            default_content = """# DEFAULT PROMPT - RECREATE VIDEO
You are a professional YouTube content writer.

Your task is to rewrite the provided transcript into an engaging script.

Guidelines:
- Keep facts accurate
- Make it engaging
- Use conversational tone
- Output ONLY the script, no comments.
"""
            try:
                with open(default_prompt, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                self.recreate_prompt_selector.set_path(str(default_prompt))
            except:
                pass

    def use_default_create_prompt(self):
        """Use the default Create Video prompt template"""
        script_dir = self._get_script_dir()
        default_prompt = script_dir / "prompts" / "create_script_template.txt"

        if default_prompt.exists():
            self.create_prompt_selector.set_path(str(default_prompt))
        else:
            # Create if doesn't exist
            prompts_folder = script_dir / "prompts"
            prompts_folder.mkdir(parents=True, exist_ok=True)
            default_content = """# DEFAULT PROMPT - CREATE VIDEO
You are a professional YouTube content creator.

Your task is to create a complete video script based on the provided title/topic.

Guidelines:
- Start with a strong hook
- Make content engaging and valuable
- Use conversational tone
- Output ONLY the script, no comments.
"""
            try:
                with open(default_prompt, 'w', encoding='utf-8') as f:
                    f.write(default_content)
                self.create_prompt_selector.set_path(str(default_prompt))
            except:
                pass

    def use_default_prompt(self):
        """Backwards compatibility - use recreate prompt"""
        self.use_default_recreate_prompt()

    def load_prompt_preview(self, path: str):
        """Load and preview prompt file - kept for compatibility"""
        pass

    def create_new_prompt(self):
        """Create new prompt file"""
        # Get prompts folder from config
        config_manager = self.wizard().config_manager
        prompts_folder = Path(config_manager.get_path("prompts_folder") or "./prompts")
        prompts_folder.mkdir(parents=True, exist_ok=True)

        # Get profile name for default filename
        profile_name = self.wizard().field("profile_name") or "NewProfile"
        default_name = f"{profile_name}-PROMPT.txt"

        # Save dialog
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Create Prompt File",
            str(prompts_folder / default_name),
            "Text Files (*.txt)"
        )

        if filename:
            # Create with default template
            template = """You are a professional MMA content writer.

Your task is to rewrite the provided transcript into an engaging, well-structured script suitable for a YouTube video.

Guidelines:
- Keep the original facts and information accurate
- Make the content more engaging and dynamic
- Use clear, concise language
- Add smooth transitions between topics
- Maintain a professional tone
- Keep the script length similar to the original

Output only the rewritten script, no additional comments or explanations.
"""
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(template)

                self.prompt_selector.set_path(filename)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Prompt file created!\n\nYou can edit it later to customize the AI behavior."
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create prompt file:\n{e}")

    def get_data(self):
        """Get prompt file paths"""
        return {
            "prompt_file": self.recreate_prompt_selector.get_path(),
            "create_prompt_file": self.create_prompt_selector.get_path()
        }


# ==================== PAGE 7: YouTube Settings ====================

class Page7_YouTubeSettings(QWizardPage):
    """Step 7: YouTube upload settings"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Step 7: YouTube Settings")
        self.setSubTitle("Configure automatic YouTube upload (optional).")

        layout = QVBoxLayout()

        info = QLabel(
            "If you want videos automatically uploaded to YouTube, enable this feature.\n"
            "Otherwise, you can manually upload the final videos."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(15)

        # Enable Upload
        self.enable_upload = LabeledCheckBox(
            label="Enable Automatic YouTube Upload",
            default=False,
            tooltip="Videos will be automatically uploaded when processing completes"
        )
        self.enable_upload.stateChanged.connect(self.toggle_fields)
        layout.addWidget(self.enable_upload)

        layout.addSpacing(15)

        # YouTube Channel Name
        channel_label = QLabel("YouTube Channel Name:")
        channel_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(channel_label)

        self.channel_field = QLineEdit()
        self.channel_field.setPlaceholderText("e.g., My MMA Channel")
        self.channel_field.setEnabled(False)
        layout.addWidget(self.channel_field)

        layout.addSpacing(10)

        # Browser Profile
        browser_label = QLabel("Browser Profile:")
        browser_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(browser_label)

        self.browser_field = QLineEdit()
        self.browser_field.setPlaceholderText("e.g., Profile1")
        self.browser_field.setEnabled(False)
        layout.addWidget(self.browser_field)

        hint = QLabel("💡 The browser profile must be configured separately for authentication")
        hint.setStyleSheet("color: #8b949e; font-style: italic;")
        layout.addWidget(hint)

        layout.addSpacing(10)

        # Upload Wait Time
        wait_label = QLabel("Upload Wait Time:")
        wait_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(wait_label)

        from ui_widgets import LabeledSpinBox
        self.wait_spinner = LabeledSpinBox(
            label="Wait",
            min_val=1,
            max_val=60,
            default=5,
            suffix="minutes"
        )
        self.wait_spinner.setEnabled(False)
        layout.addWidget(self.wait_spinner)

        layout.addStretch()
        self.setLayout(layout)

    def toggle_fields(self, enabled: bool):
        """Enable/disable fields based on checkbox"""
        self.channel_field.setEnabled(enabled)
        self.browser_field.setEnabled(enabled)
        self.wait_spinner.setEnabled(enabled)

    def get_data(self):
        """Get YouTube settings"""
        return {
            "enable_upload": self.enable_upload.is_checked(),
            "youtube_channel": self.channel_field.text().strip(),
            "browser_profile": self.browser_field.text().strip(),
            "upload_wait_minutes": self.wait_spinner.get_value()
        }
