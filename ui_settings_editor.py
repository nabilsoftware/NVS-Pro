"""
Settings Editor - Tab-Based Layout
Clean, organized settings with Quick access to most used options
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QScrollArea, QMessageBox, QFileDialog, QGroupBox,
                             QLabel, QFrame, QTabWidget, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ui_config_manager import ConfigManager
from ui_widgets import (PathSelector, LabeledSlider, LabeledSpinBox,
                        LabeledCheckBox, LabeledComboBox, LabeledLineEdit, SectionHeader, SettingsGroup)
from ui_styles import get_accent_color, get_accent_gradient


class SettingsTab(QWidget):
    """Base class for settings tabs with scroll support"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #252525;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3a3a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
        """)

        # Content widget
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(12)

        scroll.setWidget(self.content)
        main_layout.addWidget(scroll)

    def add_widget(self, widget):
        """Add widget to content"""
        self.content_layout.addWidget(widget)

    def add_section(self, title):
        """Add a section header"""
        label = QLabel(title)
        accent = get_accent_color()
        label.setStyleSheet(f"""
            color: {accent};
            font-weight: bold;
            font-size: 13px;
            padding: 10px 0 5px 0;
            border-bottom: 1px solid #3a3a3a;
        """)
        self.content_layout.addWidget(label)

    def add_spacer(self):
        """Add vertical spacer"""
        self.content_layout.addStretch()


class SettingsEditor(QWidget):
    """Tab-based settings editor"""
    settingsChanged = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the settings UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #ffffff; padding: 5px 0 10px 0;")
        main_layout.addWidget(title)

        # Tab Widget
        accent = get_accent_color()
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: #1a1a1a;
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background-color: #2a2a2a;
                color: #888888;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                min-width: 60px;
            }}
            QTabBar::tab:selected {{
                background-color: #1a1a1a;
                color: {accent};
                border: none;
                border-bottom: none;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #3a3a3a;
                color: #e0e0e0;
            }}
        """)

        # Create tabs
        self.create_quick_tab()
        self.create_folders_tab()
        self.create_ai_voice_tab()
        self.create_video_tab()
        self.create_advanced_tab()

        main_layout.addWidget(self.tabs)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_save = QPushButton("Save Settings")
        self.btn_save.clicked.connect(self.save_settings)
        self._apply_save_button_style()
        button_layout.addWidget(self.btn_save)

        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.clicked.connect(self.reset_to_defaults)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                color: #e0e0e0;
                padding: 12px 20px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        button_layout.addWidget(btn_reset)

        button_layout.addStretch()

        btn_import = QPushButton("Import")
        btn_import.clicked.connect(self.import_settings)
        btn_import.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                color: #e0e0e0;
                padding: 12px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        button_layout.addWidget(btn_import)

        btn_export = QPushButton("Export")
        btn_export.clicked.connect(self.export_settings)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                color: #e0e0e0;
                padding: 12px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        button_layout.addWidget(btn_export)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def create_quick_tab(self):
        """Quick Settings - Most commonly used"""
        tab = SettingsTab()

        # Description
        desc = QLabel("Most frequently used settings for quick access")
        desc.setStyleSheet("color: #888888; font-style: italic; padding-bottom: 10px;")
        tab.add_widget(desc)

        # Theme Selection
        tab.add_section("🎨 Appearance")

        theme_container = QWidget()
        theme_layout = QHBoxLayout(theme_container)
        theme_layout.setContentsMargins(0, 5, 0, 10)
        theme_layout.setSpacing(15)

        theme_label = QLabel("Color Theme:")
        theme_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        theme_layout.addWidget(theme_label)

        # Orange theme button
        self.theme_orange = QPushButton("🟠 Orange")
        self.theme_orange.setCheckable(True)
        self.theme_orange.setChecked(True)
        self.theme_orange.clicked.connect(lambda: self.select_theme("orange"))
        self.theme_orange.setStyleSheet(self._get_theme_button_style("#E85D04", True))
        theme_layout.addWidget(self.theme_orange)

        # Blue theme button
        self.theme_blue = QPushButton("🔵 Blue")
        self.theme_blue.setCheckable(True)
        self.theme_blue.clicked.connect(lambda: self.select_theme("blue"))
        self.theme_blue.setStyleSheet(self._get_theme_button_style("#0078D4", False))
        theme_layout.addWidget(self.theme_blue)

        # Green theme button
        self.theme_green = QPushButton("🟢 Green")
        self.theme_green.setCheckable(True)
        self.theme_green.clicked.connect(lambda: self.select_theme("green"))
        self.theme_green.setStyleSheet(self._get_theme_button_style("#10B981", False))
        theme_layout.addWidget(self.theme_green)

        theme_layout.addStretch()
        tab.add_widget(theme_container)

        # Main folders
        tab.add_section("Main Folders")

        self.input_path = PathSelector("Input Videos Folder:", is_file=False)
        tab.add_widget(self.input_path)

        self.output_path = PathSelector("Output Directory:", is_file=False)
        tab.add_widget(self.output_path)

        # === RECREATE VIDEO AI ===
        tab.add_section("🔄 Recreate Video AI")

        self.ai_provider = LabeledComboBox(
            "AI Provider",
            items=["Gemini (Google)", "Claude (Anthropic)", "ChatGPT (OpenAI)"]
        )
        tab.add_widget(self.ai_provider)

        # === CREATE VIDEO AI ===
        tab.add_section("🎬 Create Video AI")

        self.cc_ai_provider_quick = LabeledComboBox(
            "AI Provider",
            items=["Gemini (Google)", "Claude (Anthropic)", "ChatGPT (OpenAI)"]
        )
        tab.add_widget(self.cc_ai_provider_quick)

        # === THUMBNAIL AI ===
        tab.add_section("🎨 Thumbnail AI")

        self.thumbnail_ai_provider = LabeledComboBox(
            "AI Provider",
            items=["Claude (Anthropic)", "Gemini (Google)", "ChatGPT (OpenAI)"]
        )
        tab.add_widget(self.thumbnail_ai_provider)

        # Voiceover
        tab.add_section("Voiceover Generation")

        self.voiceover_method = LabeledComboBox(
            "Voiceover Method",
            items=["Fish Audio (Browser)", "Fish Audio (API)"]
        )
        tab.add_widget(self.voiceover_method)

        # Performance
        tab.add_section("Performance")

        self.enable_parallel = LabeledCheckBox(
            "Enable Parallel Processing",
            tooltip="Run independent steps simultaneously (30-40% faster)"
        )
        tab.add_widget(self.enable_parallel)

        tab.add_spacer()
        self.tabs.addTab(tab, "  Quick  ")

    def create_folders_tab(self):
        """All folder/path settings"""
        tab = SettingsTab()

        tab.add_section("Main Folders")

        self.input_path_2 = PathSelector("Input Videos Folder:", is_file=False)
        tab.add_widget(self.input_path_2)

        self.output_path_2 = PathSelector("Output Directory:", is_file=False)
        tab.add_widget(self.output_path_2)

        tab.add_section("Media Folders")

        self.broll_path = PathSelector("Custom B-roll Folder:", is_file=False)
        tab.add_widget(self.broll_path)

        self.music_path = PathSelector("Background Music Folder:", is_file=False)
        tab.add_widget(self.music_path)

        self.backgrounds_path = PathSelector("Backgrounds Folder:", is_file=False)
        tab.add_widget(self.backgrounds_path)

        tab.add_section("Other")

        self.prompts_path = PathSelector("Prompts Folder:", is_file=False)
        tab.add_widget(self.prompts_path)

        self.notif_sound = PathSelector("Notification Sound:", is_file=True,
                                        file_filter="Audio Files (*.mp3 *.wav *.ogg)")
        tab.add_widget(self.notif_sound)

        # Create Video (Content Creator) Folders
        tab.add_section("Create Video Folders")

        self.cc_interviews_path = PathSelector("Interviews Folder:", is_file=False)
        tab.add_widget(self.cc_interviews_path)

        self.cc_broll_path = PathSelector("B-Roll Folder:", is_file=False)
        tab.add_widget(self.cc_broll_path)

        self.cc_output_path = PathSelector("Output Folder:", is_file=False)
        tab.add_widget(self.cc_output_path)

        tab.add_spacer()
        self.tabs.addTab(tab, "  Folders  ")

    def create_ai_voice_tab(self):
        """AI and Voiceover settings"""
        tab = SettingsTab()

        # AI Settings
        tab.add_section("AI Script Rewriting")

        self.ai_provider_2 = LabeledComboBox(
            "AI Provider",
            items=["Gemini (Google)", "Claude (Anthropic)", "ChatGPT (OpenAI)"]
        )
        tab.add_widget(self.ai_provider_2)

        info = QLabel("↑ AI Provider for Recreate Video (model configured in API Keys page)")
        info.setStyleSheet("color: #888888; font-style: italic; padding: 5px 0;")
        tab.add_widget(info)

        # === CREATE VIDEO AI SETTINGS ===
        tab.add_section("🎬 Create Video AI Settings")

        self.cc_ai_provider = LabeledComboBox(
            "AI Provider",
            items=["Gemini (Google)", "Claude (Anthropic)", "ChatGPT (OpenAI)"]
        )
        tab.add_widget(self.cc_ai_provider)

        info2 = QLabel("↑ AI Provider for Create Video (model configured in API Keys page)")
        info2.setStyleSheet("color: #888888; font-style: italic; padding: 5px 0;")
        tab.add_widget(info2)

        # Voiceover Settings
        tab.add_section("Voiceover Generation")

        self.voiceover_method_2 = LabeledComboBox(
            "Voiceover Method",
            items=["Fish Audio (Browser)", "Fish Audio (API)"]
        )
        tab.add_widget(self.voiceover_method_2)

        self.multi_window = LabeledCheckBox(
            "Multi-Window Mode",
            tooltip="Open multiple browser windows for faster processing"
        )
        tab.add_widget(self.multi_window)

        self.parallel_voiceover = LabeledCheckBox("Parallel Processing")
        tab.add_widget(self.parallel_voiceover)

        tab.add_section("Timing Settings")

        self.base_wait = LabeledSpinBox(
            "Base Wait Time",
            min_val=5,
            max_val=30,
            suffix=" seconds"
        )
        tab.add_widget(self.base_wait)

        self.seconds_per_100 = LabeledSpinBox(
            "Seconds per 100 Chars",
            min_val=2,
            max_val=10
        )
        tab.add_widget(self.seconds_per_100)

        self.max_wait = LabeledSpinBox(
            "Max Wait Time",
            min_val=60,
            max_val=600,
            suffix=" seconds"
        )
        tab.add_widget(self.max_wait)

        tab.add_spacer()
        self.tabs.addTab(tab, "  AI  ")

    def create_video_tab(self):
        """Video processing settings"""
        tab = SettingsTab()

        # Cropping
        tab.add_section("Video Cropping")

        self.manual_crop = LabeledCheckBox(
            "Use Manual Crop by Default",
            tooltip="Manual crop gives more control, AI auto-crop is faster"
        )
        tab.add_widget(self.manual_crop)

        # B-roll
        tab.add_section("B-roll Settings")

        self.use_custom_broll = LabeledCheckBox(
            "Use Custom B-roll",
            tooltip="Use videos from custom B-roll folder"
        )
        tab.add_widget(self.use_custom_broll)

        self.use_voiceover_clips = LabeledCheckBox(
            "Use Voiceover Clips for B-roll",
            tooltip="Use voiceover clips as B-roll when custom B-roll is disabled"
        )
        tab.add_widget(self.use_voiceover_clips)

        self.trim_seconds = LabeledSpinBox(
            "Trim Voiceover Clips",
            min_val=0,
            max_val=10,
            suffix=" seconds"
        )
        tab.add_widget(self.trim_seconds)

        self.trim_interview_seconds = LabeledSpinBox(
            "Trim Interview Clips",
            min_val=0,
            max_val=10,
            suffix=" seconds"
        )
        tab.add_widget(self.trim_interview_seconds)

        # Animation
        tab.add_section("Animation")

        self.enable_animation = LabeledCheckBox("Enable Animations")
        tab.add_widget(self.enable_animation)

        self.anim_type = LabeledComboBox(
            "Animation Type",
            items=["slide", "bounce", "fade", "zoom"]
        )
        tab.add_widget(self.anim_type)

        self.anim_direction = LabeledComboBox(
            "Direction",
            items=["left", "right", "up", "down"]
        )
        tab.add_widget(self.anim_direction)

        self.anim_duration = LabeledSlider(
            "Duration",
            min_val=0.1,
            max_val=2.0,
            default=0.5,
            decimals=1
        )
        tab.add_widget(self.anim_duration)

        self.enable_out_anim = LabeledCheckBox("Enable Exit Animation")
        tab.add_widget(self.enable_out_anim)

        self.out_anim_duration = LabeledSlider(
            "Exit Duration",
            min_val=0.1,
            max_val=2.0,
            default=0.5,
            decimals=1
        )
        tab.add_widget(self.out_anim_duration)

        # Sound Effect
        tab.add_section("Transition Sound Effect")

        self.enable_sound_effect = LabeledCheckBox(
            "Enable Sound Effect",
            tooltip="Play a sound effect during clip transitions"
        )
        tab.add_widget(self.enable_sound_effect)

        self.sound_effect_path = PathSelector(
            "Sound Effect File:",
            is_file=True,
            file_filter="Audio Files (*.mp3 *.wav *.ogg);;All Files (*.*)"
        )
        tab.add_widget(self.sound_effect_path)

        self.sound_effect_volume = LabeledSlider(
            "Volume",
            min_val=0.1,
            max_val=1.0,
            default=1.0,
            decimals=1
        )
        tab.add_widget(self.sound_effect_volume)

        self.sound_effect_duration = LabeledSlider(
            "Duration",
            min_val=0.1,
            max_val=2.0,
            default=0.8,
            decimals=1,
            tooltip="How long to play the sound effect (seconds)"
        )
        tab.add_widget(self.sound_effect_duration)

        # Final Video
        tab.add_section("Final Video Assembly")

        self.enable_logo = LabeledCheckBox(
            "Enable Logo Selection",
            tooltip="Show logo selection during video assembly"
        )
        tab.add_widget(self.enable_logo)

        self.music_enabled = LabeledCheckBox("Enable Background Music")
        tab.add_widget(self.music_enabled)

        self.default_voice_level = LabeledSlider(
            "Voice Level",
            min_val=0.0,
            max_val=2.0,
            default=1.2,
            decimals=1
        )
        tab.add_widget(self.default_voice_level)

        self.default_music_level = LabeledSlider(
            "Music Level",
            min_val=0.0,
            max_val=1.0,
            default=0.1,
            decimals=2
        )
        tab.add_widget(self.default_music_level)

        tab.add_spacer()
        self.tabs.addTab(tab, "  Video  ")

    def create_advanced_tab(self):
        """Advanced/technical settings"""
        tab = SettingsTab()

        # Processing
        tab.add_section("Processing Options")

        self.enable_parallel_2 = LabeledCheckBox(
            "Enable Parallel Processing",
            tooltip="Run independent steps simultaneously"
        )
        tab.add_widget(self.enable_parallel_2)

        self.use_folder_name = LabeledCheckBox(
            "Use Folder Name for Output",
            tooltip="Use folder name (VD-1) instead of long video names"
        )
        tab.add_widget(self.use_folder_name)

        self.re_encode = LabeledCheckBox(
            "Re-encode Videos",
            tooltip="Re-encode videos during processing"
        )
        tab.add_widget(self.re_encode)

        # Audio Extraction
        tab.add_section("Audio Processing")

        self.vocal_enabled = LabeledCheckBox("Enable Vocal Extraction")
        tab.add_widget(self.vocal_enabled)

        self.vocal_jobs = LabeledSpinBox(
            "Parallel Jobs",
            min_val=1,
            max_val=16
        )
        tab.add_widget(self.vocal_jobs)

        self.vocal_model = LabeledComboBox(
            "Demucs Model",
            items=["htdemucs", "htdemucs_ft", "mdx_extra"]
        )
        tab.add_widget(self.vocal_model)

        self.use_spleeter = LabeledCheckBox(
            "Use Spleeter",
            tooltip="Experimental - may cause issues"
        )
        tab.add_widget(self.use_spleeter)

        # Transcription
        tab.add_section("Transcription")

        self.whisper_model = LabeledComboBox(
            "Whisper Model",
            items=["auto", "tiny", "base", "small", "medium", "large"]
        )
        tab.add_widget(self.whisper_model)

        self.transcribe_language = LabeledComboBox(
            "Language",
            items=["auto", "en", "es", "fr", "de", "ar", "zh", "ja", "ko"]
        )
        tab.add_widget(self.transcribe_language)

        self.use_gpu_transcribe = LabeledCheckBox(
            "Use GPU",
            tooltip="Faster but requires NVIDIA GPU with CUDA"
        )
        tab.add_widget(self.use_gpu_transcribe)

        # Output Files
        tab.add_section("Output Files")

        self.save_srt = LabeledCheckBox("Save SRT Files")
        tab.add_widget(self.save_srt)

        self.save_individual_txt = LabeledCheckBox("Save Individual TXT Files")
        tab.add_widget(self.save_individual_txt)

        self.save_combined = LabeledCheckBox("Save Combined File")
        tab.add_widget(self.save_combined)

        self.save_json = LabeledCheckBox("Save JSON Files")
        tab.add_widget(self.save_json)

        self.show_progress = LabeledCheckBox("Show Progress Bar")
        tab.add_widget(self.show_progress)

        self.show_detailed_logs = LabeledCheckBox("Show Detailed Logs")
        tab.add_widget(self.show_detailed_logs)

        # Notifications
        tab.add_section("Notifications")

        self.notif_enabled = LabeledCheckBox(
            "Enable Step Notifications",
            tooltip="Play sound when certain steps start"
        )
        tab.add_widget(self.notif_enabled)

        tab.add_spacer()
        self.tabs.addTab(tab, "  More  ")

    def _get_theme_button_style(self, color: str, selected: bool) -> str:
        """Get style for theme button"""
        if selected:
            return f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 8px;
                    border: 2px solid {color};
                }}
                QPushButton:hover {{
                    background-color: {color};
                    border: 2px solid white;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: #888888;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 8px;
                    border: 2px solid #3a3a3a;
                }}
                QPushButton:hover {{
                    background-color: #3a3a3a;
                    color: {color};
                    border: 2px solid {color};
                }}
            """

    def select_theme(self, theme_name: str):
        """Handle theme selection"""
        # Update button states
        self.theme_orange.setChecked(theme_name == "orange")
        self.theme_blue.setChecked(theme_name == "blue")
        self.theme_green.setChecked(theme_name == "green")

        # Update button styles
        self.theme_orange.setStyleSheet(self._get_theme_button_style("#E85D04", theme_name == "orange"))
        self.theme_blue.setStyleSheet(self._get_theme_button_style("#0078D4", theme_name == "blue"))
        self.theme_green.setStyleSheet(self._get_theme_button_style("#10B981", theme_name == "green"))

        # Store selected theme
        self._selected_theme = theme_name

        # Apply theme live (find main window and apply)
        main_window = self.window()
        if hasattr(main_window, 'apply_theme'):
            main_window.apply_theme(theme_name)

        # Refresh tab widget accent colors
        self._refresh_tab_styles()

    def _refresh_tab_styles(self):
        """Refresh tab widget styles with current theme colors"""
        accent = get_accent_color()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: #1a1a1a;
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background-color: #2a2a2a;
                color: #888888;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                min-width: 60px;
            }}
            QTabBar::tab:selected {{
                background-color: #1a1a1a;
                color: {accent};
                border: none;
                border-bottom: none;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #3a3a3a;
                color: #e0e0e0;
            }}
        """)

        # Also refresh save button
        self._apply_save_button_style()

    def _apply_save_button_style(self):
        """Apply theme colors to save button"""
        accent = get_accent_color()
        grad_start, grad_end = get_accent_gradient()
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {grad_start};
                border: none;
                color: white;
                padding: 12px 30px;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
        """)

    def sync_duplicate_fields(self):
        """Sync fields that appear in multiple tabs"""
        # Sync input path
        path1 = self.input_path.get_path()
        path2 = self.input_path_2.get_path()
        if path1 != path2:
            if path1:
                self.input_path_2.set_path(path1)
            elif path2:
                self.input_path.set_path(path2)

        # Sync output path
        path1 = self.output_path.get_path()
        path2 = self.output_path_2.get_path()
        if path1 != path2:
            if path1:
                self.output_path_2.set_path(path1)
            elif path2:
                self.output_path.set_path(path2)

        # Sync AI provider
        prov1 = self.ai_provider.get_current_text()
        prov2 = self.ai_provider_2.get_current_text()
        if prov1 != prov2:
            self.ai_provider_2.set_current_text(prov1)

        # Sync voiceover method
        vm1 = self.voiceover_method.get_current_text()
        vm2 = self.voiceover_method_2.get_current_text()
        if vm1 != vm2:
            self.voiceover_method_2.set_current_text(vm1)

        # Sync parallel processing
        p1 = self.enable_parallel.is_checked()
        p2 = self.enable_parallel_2.is_checked()
        if p1 != p2:
            self.enable_parallel_2.set_checked(p1)

    def load_settings(self):
        """Load all settings from config"""
        # Theme
        appearance = self.config_manager.config.get("appearance", {})
        saved_theme = appearance.get("theme", "orange")
        self._selected_theme = saved_theme
        self.select_theme(saved_theme)

        # Paths
        paths = self.config_manager.get_all_paths()
        input_path = paths.get("input_videos_folder", "./input")
        output_path = paths.get("output_base_dir", "./output")

        self.input_path.set_path(input_path)
        self.input_path_2.set_path(input_path)
        self.output_path.set_path(output_path)
        self.output_path_2.set_path(output_path)
        self.broll_path.set_path(paths.get("custom_broll_folder", "./broll"))
        self.music_path.set_path(paths.get("background_music_folder", "./music"))
        self.backgrounds_path.set_path(paths.get("backgrounds_folder", "./backgrounds"))
        self.prompts_path.set_path(paths.get("prompts_folder", "./prompts"))

        # Content Creator (Create Video) folders
        cc_settings = self.config_manager.get_content_creator_settings()
        self.cc_interviews_path.set_path(cc_settings.get("interviews_folder", ""))
        self.cc_broll_path.set_path(cc_settings.get("broll_folder", ""))
        self.cc_output_path.set_path(cc_settings.get("output_folder", ""))

        # Processing
        proc = self.config_manager.get_processing_settings()
        parallel = proc.get("enable_parallel_steps", True)
        self.enable_parallel.set_checked(parallel)
        self.enable_parallel_2.set_checked(parallel)
        self.use_custom_broll.set_checked(proc.get("use_custom_broll_input", False))
        self.use_voiceover_clips.set_checked(proc.get("use_voiceover_clips_for_broll", True))
        self.trim_seconds.set_value(proc.get("trim_voiceover_clips_seconds", 4))
        self.trim_interview_seconds.set_value(proc.get("trim_interview_clips_seconds", 0))
        self.manual_crop.set_checked(proc.get("use_manual_crop_default", True))
        self.enable_logo.set_checked(proc.get("enable_logo_in_step7", True))
        self.use_folder_name.set_checked(proc.get("use_folder_name_for_output", True))

        # Animation
        anim = self.config_manager.get_animation_settings()
        self.enable_animation.set_checked(anim.get("enable_animation", True))
        self.anim_type.set_current_text(anim.get("animation_type", "slide"))
        self.anim_direction.set_current_text(anim.get("animation_direction", "left"))
        self.anim_duration.set_value(anim.get("animation_duration", 0.5))
        self.enable_out_anim.set_checked(anim.get("enable_out_animation", True))
        self.out_anim_duration.set_value(anim.get("out_animation_duration", 0.5))

        # Sound Effect
        sfx = self.config_manager.get_sound_effect_settings()
        self.enable_sound_effect.set_checked(sfx.get("enabled", False))
        self.sound_effect_path.set_path(sfx.get("file_path", ""))
        self.sound_effect_volume.set_value(sfx.get("volume", 1.0))
        self.sound_effect_duration.set_value(sfx.get("duration", 0.8))

        # Vocal Extraction
        vocal = self.config_manager.get_vocal_extraction()
        self.vocal_enabled.set_checked(vocal.get("enabled", True))
        self.vocal_jobs.set_value(vocal.get("parallel_jobs", 4))
        self.vocal_model.set_current_text(vocal.get("model", "htdemucs"))

        # Background Music
        music = self.config_manager.get_background_music()
        self.music_enabled.set_checked(music.get("enabled", True))
        self.default_voice_level.set_value(music.get("default_voice_level", 1.2))
        self.default_music_level.set_value(music.get("default_music_level", 0.1))

        # Voiceover
        voice = self.config_manager.get_voiceover_settings()
        voiceover_method = voice.get("method", "Fish Audio (Browser)")
        self.voiceover_method.set_current_text(voiceover_method)
        self.voiceover_method_2.set_current_text(voiceover_method)
        self.multi_window.set_checked(voice.get("use_multi_window", True))
        self.parallel_voiceover.set_checked(voice.get("enable_parallel_processing", True))
        self.base_wait.set_value(voice.get("base_wait_time", 10))
        self.seconds_per_100.set_value(voice.get("seconds_per_100_chars", 4))
        self.max_wait.set_value(voice.get("max_wait_time", 300))

        # AI - only provider (model comes from API Keys page)
        ai = self.config_manager.get_ai_settings()
        provider = ai.get("provider", "gemini")
        provider_map = {
            "gemini": "Gemini (Google)",
            "claude": "Claude (Anthropic)",
            "openai": "ChatGPT (OpenAI)"
        }
        ai_display = provider_map.get(provider, "Gemini (Google)")
        self.ai_provider.set_current_text(ai_display)
        self.ai_provider_2.set_current_text(ai_display)

        # Create Video AI Settings - only provider
        cc_ai = self.config_manager.config.get("cc_ai_settings", {})
        cc_provider = cc_ai.get("provider", "claude")
        cc_ai_display = provider_map.get(cc_provider, "Claude (Anthropic)")
        self.cc_ai_provider.set_current_text(cc_ai_display)
        self.cc_ai_provider_quick.set_current_text(cc_ai_display)

        # Thumbnail AI Settings
        thumb_ai = self.config_manager.config.get("thumbnail_ai_settings", {})
        thumb_provider = thumb_ai.get("provider", "claude")
        thumb_ai_display = provider_map.get(thumb_provider, "Claude (Anthropic)")
        self.thumbnail_ai_provider.set_current_text(thumb_ai_display)

        # Transcription
        trans = self.config_manager.get_transcription_settings()
        self.save_srt.set_checked(trans.get("save_srt_files", False))
        self.save_individual_txt.set_checked(trans.get("save_individual_txt", False))
        self.save_combined.set_checked(trans.get("save_combined_file", True))
        self.save_json.set_checked(trans.get("save_json_files", False))
        self.show_progress.set_checked(trans.get("show_progress_bar", True))
        self.show_detailed_logs.set_checked(trans.get("show_detailed_logs", True))

        try:
            self.whisper_model.set_current_text(trans.get("model_size", "auto"))
            self.transcribe_language.set_current_text(trans.get("language", "auto"))
            self.use_gpu_transcribe.set_checked(trans.get("use_gpu", True))
        except:
            pass

        # Diarization
        diar = self.config_manager.get_diarization_settings()
        self.re_encode.set_checked(diar.get("re_encode", True))
        self.use_spleeter.set_checked(diar.get("use_spleeter", False))

        # Notification
        notif = self.config_manager.get_notification_settings()
        self.notif_enabled.set_checked(notif.get("enabled", True))
        self.notif_sound.set_path(notif.get("sound_file", "./notifications.mp3"))

    def save_settings(self):
        """Save all settings to config"""
        # Sync duplicate fields first
        self.sync_duplicate_fields()

        # Theme/Appearance
        self.config_manager.config["appearance"] = {
            "theme": getattr(self, '_selected_theme', 'orange')
        }

        # Paths (use Quick tab values as primary)
        paths = {
            "input_videos_folder": self.input_path.get_path(),
            "output_base_dir": self.output_path.get_path(),
            "custom_broll_folder": self.broll_path.get_path(),
            "background_music_folder": self.music_path.get_path(),
            "backgrounds_folder": self.backgrounds_path.get_path(),
            "prompts_folder": self.prompts_path.get_path()
        }
        self.config_manager.set_all_paths(paths)

        # Content Creator (Create Video) folders
        cc_settings = self.config_manager.get_content_creator_settings()
        cc_settings["interviews_folder"] = self.cc_interviews_path.get_path()
        cc_settings["broll_folder"] = self.cc_broll_path.get_path()
        cc_settings["output_folder"] = self.cc_output_path.get_path()
        self.config_manager.set_content_creator_settings(cc_settings)

        # Processing
        proc = {
            "enable_parallel_steps": self.enable_parallel.is_checked(),
            "use_custom_broll_input": self.use_custom_broll.is_checked(),
            "use_voiceover_clips_for_broll": self.use_voiceover_clips.is_checked(),
            "trim_voiceover_clips_seconds": self.trim_seconds.get_value(),
            "trim_interview_clips_seconds": self.trim_interview_seconds.get_value(),
            "use_manual_crop_default": self.manual_crop.is_checked(),
            "enable_logo_in_step7": self.enable_logo.is_checked(),
            "use_folder_name_for_output": self.use_folder_name.is_checked(),
            "processing_mode": "ASK_USER"
        }
        self.config_manager.set_processing_settings(proc)

        # Animation
        anim = {
            "enable_animation": self.enable_animation.is_checked(),
            "animation_type": self.anim_type.get_current_text(),
            "animation_direction": self.anim_direction.get_current_text(),
            "animation_duration": self.anim_duration.get_value(),
            "enable_out_animation": self.enable_out_anim.is_checked(),
            "out_animation_duration": self.out_anim_duration.get_value()
        }
        self.config_manager.set_animation_settings(anim)

        # Sound Effect
        sfx = {
            "enabled": self.enable_sound_effect.is_checked(),
            "file_path": self.sound_effect_path.get_path(),
            "volume": self.sound_effect_volume.get_value(),
            "duration": self.sound_effect_duration.get_value()
        }
        self.config_manager.set_sound_effect_settings(sfx)

        # Vocal Extraction
        vocal = {
            "enabled": self.vocal_enabled.is_checked(),
            "parallel_jobs": self.vocal_jobs.get_value(),
            "model": self.vocal_model.get_current_text()
        }
        self.config_manager.set_vocal_extraction(vocal)

        # Background Music
        music = {
            "enabled": self.music_enabled.is_checked(),
            "default_voice_level": self.default_voice_level.get_value(),
            "default_music_level": self.default_music_level.get_value()
        }
        self.config_manager.set_background_music(music)

        # Voiceover
        voice = {
            "method": self.voiceover_method.get_current_text(),
            "use_multi_window": self.multi_window.is_checked(),
            "tabs_per_window": "auto",
            "enable_parallel_processing": self.parallel_voiceover.is_checked(),
            "base_wait_time": self.base_wait.get_value(),
            "seconds_per_100_chars": self.seconds_per_100.get_value(),
            "max_wait_time": self.max_wait.get_value(),
            "num_tabs": "auto"
        }
        self.config_manager.set_voiceover_settings(voice)

        # AI (Recreate Video) - use Quick tab model text
        provider_text = self.ai_provider.get_current_text()
        provider_reverse_map = {
            "Gemini (Google)": "gemini",
            "Claude (Anthropic)": "claude",
            "ChatGPT (OpenAI)": "openai"
        }
        provider_key = provider_reverse_map.get(provider_text, "gemini")

        # AI settings - only provider, model comes from API Keys page
        ai = {
            "provider": provider_key,
            "api_keys_file": "./api_keys.json"
        }
        self.config_manager.set_ai_settings(ai)

        # Create Video AI Settings - only provider
        cc_provider_text = self.cc_ai_provider_quick.get_current_text()
        cc_provider_key = provider_reverse_map.get(cc_provider_text, "claude")

        cc_ai = {
            "provider": cc_provider_key
        }
        self.config_manager.config["cc_ai_settings"] = cc_ai

        # Thumbnail AI Settings
        thumb_provider_text = self.thumbnail_ai_provider.get_current_text()
        thumb_provider_key = provider_reverse_map.get(thumb_provider_text, "claude")

        thumb_ai = {
            "provider": thumb_provider_key
        }
        self.config_manager.config["thumbnail_ai_settings"] = thumb_ai

        # Transcription
        trans = {
            "save_srt_files": self.save_srt.is_checked(),
            "save_individual_txt": self.save_individual_txt.is_checked(),
            "save_combined_file": self.save_combined.is_checked(),
            "save_json_files": self.save_json.is_checked(),
            "create_folder_per_input": False,
            "show_progress_bar": self.show_progress.is_checked(),
            "show_detailed_logs": self.show_detailed_logs.is_checked(),
            "model_size": self.whisper_model.get_current_text(),
            "language": self.transcribe_language.get_current_text(),
            "use_gpu": self.use_gpu_transcribe.is_checked()
        }
        self.config_manager.set_transcription_settings(trans)

        # Diarization
        diar = {
            "re_encode": self.re_encode.is_checked(),
            "use_spleeter": self.use_spleeter.is_checked()
        }
        self.config_manager.set_diarization_settings(diar)

        # Notification
        notif = {
            "enabled": self.notif_enabled.is_checked(),
            "sound_file": self.notif_sound.get_path()
        }
        self.config_manager.set_notification_settings(notif)

        # Emit signal and show message
        self.settingsChanged.emit()
        QMessageBox.information(self, "Success", "Settings saved successfully!")

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset ALL settings to defaults?\n\n"
            "This will overwrite your current configuration!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.config_manager.reset_to_defaults():
                self.load_settings()
                self.settingsChanged.emit()
                QMessageBox.information(self, "Success", "Settings reset to defaults!")
            else:
                QMessageBox.critical(self, "Error", "Failed to reset settings!")

    def import_settings(self):
        """Import settings from JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Settings",
            "",
            "JSON Files (*.json)"
        )

        if filename:
            from pathlib import Path
            if self.config_manager.import_all_settings(Path(filename)):
                self.load_settings()
                self.settingsChanged.emit()
                QMessageBox.information(self, "Success", f"Settings imported from:\n{filename}")
            else:
                QMessageBox.critical(self, "Error", "Failed to import settings!")

    def export_settings(self):
        """Export settings to JSON file"""
        from datetime import datetime
        default_name = f"settings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Settings",
            default_name,
            "JSON Files (*.json)"
        )

        if filename:
            from pathlib import Path
            if self.config_manager.export_all_settings(Path(filename)):
                QMessageBox.information(self, "Success", f"Settings exported to:\n{filename}")
            else:
                QMessageBox.critical(self, "Error", "Failed to export settings!")
