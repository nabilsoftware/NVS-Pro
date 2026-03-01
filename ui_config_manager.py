"""
Config Manager - Handle all config.json read/write operations
NO manual editing required - everything through UI
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List


class ConfigManager:
    """Manages configuration file read/write operations"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = {}
        self.load()

    def load(self) -> bool:
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                return True
            else:
                # Create default config if not exists
                self.config = self._get_default_config()
                self.save()
                return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False

    def save(self) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, *keys, default=None) -> Any:
        """Get nested value from config"""
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys, value) -> None:
        """Set nested value in config"""
        if len(keys) == 0:
            return

        # Navigate to parent
        parent = self.config
        for key in keys[:-1]:
            if key not in parent or not isinstance(parent[key], dict):
                parent[key] = {}
            parent = parent[key]

        # Set value
        parent[keys[-1]] = value

    # ==================== PROFILES ====================

    def get_profiles(self) -> Dict:
        """Get all profiles"""
        return self.get("profiles", default={})

    def get_profile(self, name: str) -> Optional[Dict]:
        """Get specific profile"""
        profiles = self.get_profiles()
        return profiles.get(name)

    def add_profile(self, name: str, profile_data: Dict) -> bool:
        """Add new profile"""
        profiles = self.get_profiles()
        if name in profiles:
            return False  # Profile already exists

        profiles[name] = profile_data
        self.set("profiles", value=profiles)
        return self.save()

    def update_profile(self, name: str, profile_data: Dict) -> bool:
        """Update existing profile"""
        profiles = self.get_profiles()
        if name not in profiles:
            return False  # Profile doesn't exist

        profiles[name] = profile_data
        self.set("profiles", value=profiles)
        return self.save()

    def delete_profile(self, name: str) -> bool:
        """Delete profile"""
        profiles = self.get_profiles()
        if name not in profiles:
            return False

        del profiles[name]
        self.set("profiles", value=profiles)
        return self.save()

    def duplicate_profile(self, original_name: str, new_name: str) -> bool:
        """Duplicate profile with new name"""
        profiles = self.get_profiles()
        if original_name not in profiles or new_name in profiles:
            return False

        # Copy profile
        profiles[new_name] = profiles[original_name].copy()
        profiles[new_name]["name"] = new_name
        profiles[new_name]["suffix"] = new_name  # Also update suffix to match new name
        self.set("profiles", value=profiles)
        return self.save()

    # ==================== VOICES ====================

    def get_voices(self) -> Dict:
        """Get all voices"""
        return self.get("voices", default={})

    def get_voice(self, name: str) -> Optional[Dict]:
        """Get specific voice"""
        voices = self.get_voices()
        return voices.get(name)

    def add_voice(self, name: str, voice_data: Dict) -> bool:
        """Add new voice"""
        voices = self.get_voices()
        if name in voices:
            return False

        voices[name] = voice_data
        self.set("voices", value=voices)
        return self.save()

    def update_voice(self, name: str, voice_data: Dict) -> bool:
        """Update voice"""
        voices = self.get_voices()
        if name not in voices:
            return False

        voices[name] = voice_data
        self.set("voices", value=voices)
        return self.save()

    def delete_voice(self, name: str) -> bool:
        """Delete voice"""
        voices = self.get_voices()
        if name not in voices:
            return False

        del voices[name]
        self.set("voices", value=voices)
        return self.save()

    # ==================== CATEGORIES ====================

    def get_categories(self) -> List:
        """Get all category names (backward compatible)"""
        categories_data = self.get("categories_data", default={})
        if categories_data:
            return list(categories_data.keys())
        # Fallback to old list format
        return self.get("categories", default=["Default"])

    def get_category_data(self, name: str) -> Dict:
        """Get category data including paths"""
        categories_data = self.get("categories_data", default={})
        return categories_data.get(name, {"input_path": "", "output_path": ""})

    def set_category_paths(self, name: str, input_path: str, output_path: str,
                          cc_interviews_path: str = "", cc_broll_path: str = "",
                          cc_output_path: str = "") -> bool:
        """Set input/output paths for a category (Recreate Video + Create Video)"""
        categories_data = self.get("categories_data", default={})
        if name not in categories_data:
            categories_data[name] = {}
        categories_data[name]["input_path"] = input_path
        categories_data[name]["output_path"] = output_path
        categories_data[name]["cc_interviews_path"] = cc_interviews_path
        categories_data[name]["cc_broll_path"] = cc_broll_path
        categories_data[name]["cc_output_path"] = cc_output_path
        self.set("categories_data", value=categories_data)
        return self.save()

    def add_category(self, name: str) -> bool:
        """Add new category"""
        categories_data = self.get("categories_data", default={})
        if name in categories_data:
            return False
        categories_data[name] = {"input_path": "", "output_path": ""}
        self.set("categories_data", value=categories_data)
        # Also maintain old list for backward compatibility
        old_list = self.get("categories", default=["Default"])
        if name not in old_list:
            old_list.append(name)
            self.set("categories", value=old_list)
        return self.save()

    def delete_category(self, name: str) -> bool:
        """Delete category (moves channels to Default)"""
        if name == "Default":
            return False  # Can't delete default category

        categories_data = self.get("categories_data", default={})
        if name not in categories_data and name not in self.get("categories", default=[]):
            return False

        # Move all channels in this category to Default
        profiles = self.get_profiles()
        for profile_name, profile_data in profiles.items():
            if profile_data.get("category") == name:
                profile_data["category"] = "Default"
        self.set("profiles", value=profiles)

        # Remove from categories_data
        if name in categories_data:
            del categories_data[name]
            self.set("categories_data", value=categories_data)

        # Also remove from old list
        old_list = self.get("categories", default=["Default"])
        if name in old_list:
            old_list.remove(name)
            self.set("categories", value=old_list)

        return self.save()

    def rename_category(self, old_name: str, new_name: str) -> bool:
        """Rename category"""
        if old_name == "Default":
            return False  # Can't rename default category

        categories_data = self.get("categories_data", default={})
        old_list = self.get("categories", default=["Default"])

        if old_name not in categories_data and old_name not in old_list:
            return False
        if new_name in categories_data or new_name in old_list:
            return False

        # Update all channels with this category
        profiles = self.get_profiles()
        for profile_name, profile_data in profiles.items():
            if profile_data.get("category") == old_name:
                profile_data["category"] = new_name
        self.set("profiles", value=profiles)

        # Rename in categories_data (preserve paths)
        if old_name in categories_data:
            categories_data[new_name] = categories_data.pop(old_name)
            self.set("categories_data", value=categories_data)

        # Rename in old list
        if old_name in old_list:
            idx = old_list.index(old_name)
            old_list[idx] = new_name
            self.set("categories", value=old_list)

        return self.save()

    def migrate_categories_to_data(self) -> bool:
        """Migrate old categories list to new categories_data format"""
        old_list = self.get("categories", default=["Default"])
        categories_data = self.get("categories_data", default={})

        for cat in old_list:
            if cat not in categories_data:
                categories_data[cat] = {"input_path": "", "output_path": ""}

        # Ensure Default exists
        if "Default" not in categories_data:
            categories_data["Default"] = {"input_path": "", "output_path": ""}

        self.set("categories_data", value=categories_data)
        return self.save()

    def get_profiles_by_category(self) -> Dict:
        """Get profiles grouped by category"""
        profiles = self.get_profiles()
        categories = self.get_categories()

        # Initialize with all categories
        grouped = {cat: {} for cat in categories}
        grouped["Default"] = {}  # Ensure Default exists

        for name, data in profiles.items():
            category = data.get("category", "Default")
            if category not in grouped:
                category = "Default"
            grouped[category][name] = data

        return grouped

    # ==================== PATHS ====================

    def get_path(self, key: str) -> str:
        """Get path from config"""
        return self.get("paths", key, default="")

    def set_path(self, key: str, value: str) -> bool:
        """Set path in config"""
        self.set("paths", key, value=value)
        return self.save()

    def get_all_paths(self) -> Dict:
        """Get all paths"""
        return self.get("paths", default={})

    def set_all_paths(self, paths: Dict) -> bool:
        """Set all paths"""
        self.set("paths", value=paths)
        return self.save()

    # ==================== SETTINGS ====================

    def get_processing_settings(self) -> Dict:
        """Get processing settings"""
        return self.get("processing_settings", default={})

    def set_processing_settings(self, settings: Dict) -> bool:
        """Set processing settings"""
        self.set("processing_settings", value=settings)
        return self.save()

    def get_animation_settings(self) -> Dict:
        """Get animation settings"""
        return self.get("animation_settings", default={})

    def set_animation_settings(self, settings: Dict) -> bool:
        """Set animation settings"""
        self.set("animation_settings", value=settings)
        return self.save()

    def get_sound_effect_settings(self) -> Dict:
        """Get sound effect settings for transitions"""
        return self.get("sound_effect_settings", default={
            "enabled": False,
            "file_path": "",
            "volume": 1.0,
            "duration": 0.8
        })

    def set_sound_effect_settings(self, settings: Dict) -> bool:
        """Set sound effect settings"""
        self.set("sound_effect_settings", value=settings)
        return self.save()

    def get_vocal_extraction(self) -> Dict:
        """Get vocal extraction settings"""
        return self.get("vocal_extraction", default={})

    def set_vocal_extraction(self, settings: Dict) -> bool:
        """Set vocal extraction settings"""
        self.set("vocal_extraction", value=settings)
        return self.save()

    def get_background_music(self) -> Dict:
        """Get background music settings"""
        return self.get("background_music", default={})

    def set_background_music(self, settings: Dict) -> bool:
        """Set background music settings"""
        self.set("background_music", value=settings)
        return self.save()

    def get_voiceover_settings(self) -> Dict:
        """Get voiceover settings"""
        return self.get("voiceover_settings", default={})

    def set_voiceover_settings(self, settings: Dict) -> bool:
        """Set voiceover settings"""
        self.set("voiceover_settings", value=settings)
        return self.save()

    def get_ai_settings(self) -> Dict:
        """Get AI settings"""
        return self.get("ai_settings", default={})

    def set_ai_settings(self, settings: Dict) -> bool:
        """Set AI settings"""
        self.set("ai_settings", value=settings)
        return self.save()

    def get_transcription_settings(self) -> Dict:
        """Get transcription settings"""
        return self.get("transcription_settings", default={})

    def set_transcription_settings(self, settings: Dict) -> bool:
        """Set transcription settings"""
        self.set("transcription_settings", value=settings)
        return self.save()

    def get_diarization_settings(self) -> Dict:
        """Get diarization settings"""
        return self.get("diarization_settings", default={})

    def set_diarization_settings(self, settings: Dict) -> bool:
        """Set diarization settings"""
        self.set("diarization_settings", value=settings)
        return self.save()

    def get_notification_settings(self) -> Dict:
        """Get notification settings"""
        return self.get("notification_settings", default={"enabled": True, "sound_file": "./notifications.mp3"})

    def set_notification_settings(self, settings: Dict) -> bool:
        """Set notification settings"""
        self.set("notification_settings", value=settings)
        return self.save()

    def get_multi_folder_mode(self) -> Dict:
        """Get multi-folder mode settings"""
        return self.get("multi_folder_mode", default={})

    def set_multi_folder_mode(self, settings: Dict) -> bool:
        """Set multi-folder mode settings"""
        self.set("multi_folder_mode", value=settings)
        return self.save()

    def get_content_creator_settings(self) -> Dict:
        """Get content creator (Create Video) settings"""
        return self.get("content_creator", default={})

    def set_content_creator_settings(self, settings: Dict) -> bool:
        """Set content creator (Create Video) settings"""
        self.set("content_creator", value=settings)
        return self.save()

    # ==================== AUTOMATION TASKS ====================

    def get_automation_tasks(self) -> List:
        """Get all automation tasks"""
        return self.get("automation_tasks", default=[])

    def add_automation_task(self, task_data: Dict) -> bool:
        """Add new automation task"""
        tasks = self.get_automation_tasks()
        # Check for duplicate name
        for t in tasks:
            if t.get("name") == task_data.get("name"):
                return False
        tasks.append(task_data)
        self.set("automation_tasks", value=tasks)
        return self.save()

    def update_automation_task(self, name: str, task_data: Dict) -> bool:
        """Update existing automation task by name"""
        tasks = self.get_automation_tasks()
        for i, t in enumerate(tasks):
            if t.get("name") == name:
                tasks[i] = task_data
                self.set("automation_tasks", value=tasks)
                return self.save()
        return False

    def delete_automation_task(self, name: str) -> bool:
        """Delete automation task by name"""
        tasks = self.get_automation_tasks()
        tasks = [t for t in tasks if t.get("name") != name]
        self.set("automation_tasks", value=tasks)
        return self.save()

    # ==================== UTILITY ====================

    def export_profile(self, profile_name: str, export_path: Path) -> bool:
        """Export single profile to JSON file"""
        profile = self.get_profile(profile_name)
        if not profile:
            return False

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False

    def import_profile(self, import_path: Path, profile_name: Optional[str] = None) -> bool:
        """Import profile from JSON file"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)

            # Use provided name or get from profile data
            name = profile_name or profile_data.get("name", "Imported_Profile")

            # Ensure unique name
            base_name = name
            counter = 1
            while self.get_profile(name):
                name = f"{base_name}_{counter}"
                counter += 1

            profile_data["name"] = name
            return self.add_profile(name, profile_data)
        except:
            return False

    def export_all_settings(self, export_path: Path) -> bool:
        """Export entire config to file"""
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False

    def import_all_settings(self, import_path: Path) -> bool:
        """Import entire config from file"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            return self.save()
        except:
            return False

    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults"""
        self.config = self._get_default_config()
        return self.save()

    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            "paths": {
                "input_videos_folder": "./input",
                "output_base_dir": "./output",
                "custom_broll_folder": "./broll",
                "background_music_folder": "./music",
                "backgrounds_folder": "./backgrounds",
                "prompts_folder": "./prompts"
            },
            "multi_folder_mode": {
                "enabled": False,
                "input_folders": []
            },
            "processing_settings": {
                "enable_parallel_steps": True,
                "use_custom_broll_input": False,
                "use_voiceover_clips_for_broll": True,
                "trim_voiceover_clips_seconds": 4,
                "trim_interview_clips_seconds": 0,
                "use_manual_crop_default": True,
                "enable_logo_in_step7": True,
                "processing_mode": "ASK_USER"
            },
            "animation_settings": {
                "enable_animation": True,
                "animation_type": "slide",
                "animation_direction": "left",
                "animation_duration": 0.5,
                "enable_out_animation": True,
                "out_animation_duration": 0.5
            },
            "vocal_extraction": {
                "enabled": True,
                "parallel_jobs": 4,
                "model": "htdemucs"
            },
            "background_music": {
                "enabled": True,
                "default_voice_level": 1.2,
                "default_music_level": 0.1
            },
            "voiceover_settings": {
                "use_multi_window": True,
                "tabs_per_window": "auto",
                "enable_parallel_processing": True,
                "base_wait_time": 10,
                "seconds_per_100_chars": 4,
                "max_wait_time": 300,
                "num_tabs": "auto"
            },
            "ai_settings": {
                "model_name": "gemini-2.5-pro",
                "api_keys_file": "./api_keys.json"
            },
            "transcription_settings": {
                "save_srt_files": False,
                "save_individual_txt": False,
                "save_combined_file": True,
                "save_json_files": False,
                "create_folder_per_input": False,
                "show_progress_bar": True,
                "show_detailed_logs": True
            },
            "diarization_settings": {
                "re_encode": True,
                "use_spleeter": False
            },
            "profiles": {
                "Profile1": {
                    "name": "Profile1",
                    "description": "Example profile for video creation",
                    "prompt_file": "prompts/Profile1-PROMPT.txt",
                    "default_voice": "VOICE1",
                    "suffix": "Profile1",
                    "background_video": "backgrounds/profile1-bg.mp4",
                    "frame_color": "#ffffff",
                    "video_scale": 0.85,
                    "use_manual_crop": True,
                    "background_music": "music/profile1-bg-music.mp3",
                    "voice_level": 1.2,
                    "music_level": 0.09,
                    "youtube_channel": "My Channel 1",
                    "browser_profile": "Profile1",
                    "enable_upload": False,
                    "upload_wait_minutes": 5
                }
            },
            "voices": {
                "VOICE1": {
                    "name": "VOICE1",
                    "description": "Professional voice 1",
                    "url": "https://fish.audio/app/text-to-speech/?modelId=YOUR_MODEL_ID&version=speech-1.6"
                }
            }
        }
