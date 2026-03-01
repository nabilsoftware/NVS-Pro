"""
Input Validators - Validate all user inputs
Prevent errors and ensure data integrity
"""

import re
from pathlib import Path
from typing import Tuple, Optional


class Validators:
    """Input validation functions"""

    @staticmethod
    def validate_profile_name(name: str, existing_names: list = None) -> Tuple[bool, str]:
        """
        Validate profile name
        Returns: (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "Profile name cannot be empty"

        # Check length
        if len(name) < 2:
            return False, "Profile name must be at least 2 characters"

        if len(name) > 50:
            return False, "Profile name must be less than 50 characters"

        # Check for invalid characters
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', name):
            return False, "Profile name can only contain letters, numbers, spaces, hyphens and underscores"

        # Check for uniqueness
        if existing_names and name in existing_names:
            return False, f"Profile '{name}' already exists"

        return True, ""

    @staticmethod
    def validate_voice_name(name: str, existing_names: list = None) -> Tuple[bool, str]:
        """Validate voice name"""
        if not name or not name.strip():
            return False, "Voice name cannot be empty"

        if len(name) < 2:
            return False, "Voice name must be at least 2 characters"

        if len(name) > 50:
            return False, "Voice name must be less than 50 characters"

        # Check for uniqueness
        if existing_names and name in existing_names:
            return False, f"Voice '{name}' already exists"

        return True, ""

    @staticmethod
    def validate_fish_audio_url(url: str) -> Tuple[bool, str]:
        """Validate Fish Audio URL"""
        if not url or not url.strip():
            return False, "URL cannot be empty"

        # Check if it's a valid fish.audio URL
        if "fish.audio" not in url.lower():
            return False, "URL must be from fish.audio"

        # Check basic URL format
        if not url.startswith("http://") and not url.startswith("https://"):
            return False, "URL must start with http:// or https://"

        # Check for modelId parameter
        if "modelId=" not in url:
            return False, "URL must contain modelId parameter"

        return True, ""

    @staticmethod
    def validate_path(path: str, must_exist: bool = False, is_file: bool = False) -> Tuple[bool, str]:
        """
        Validate file/folder path
        Args:
            path: Path to validate
            must_exist: If True, path must exist
            is_file: If True, path should be a file, else folder
        """
        if not path or not path.strip():
            return False, "Path cannot be empty"

        try:
            p = Path(path)

            if must_exist:
                if not p.exists():
                    return False, f"Path does not exist: {path}"

                if is_file and not p.is_file():
                    return False, f"Path is not a file: {path}"

                if not is_file and not p.is_dir():
                    return False, f"Path is not a directory: {path}"

            return True, ""
        except Exception as e:
            return False, f"Invalid path: {str(e)}"

    @staticmethod
    def validate_color_hex(color: str) -> Tuple[bool, str]:
        """Validate hex color code"""
        if not color or not color.strip():
            return False, "Color cannot be empty"

        # Remove # if present
        color = color.strip()
        if color.startswith("#"):
            color = color[1:]

        # Check format
        if not re.match(r'^[0-9A-Fa-f]{6}$', color):
            return False, "Color must be in format #RRGGBB (e.g., #FF0000)"

        return True, ""

    @staticmethod
    def validate_number_range(value: float, min_val: float, max_val: float, name: str = "Value") -> Tuple[bool, str]:
        """Validate number is within range"""
        if value < min_val or value > max_val:
            return False, f"{name} must be between {min_val} and {max_val}"
        return True, ""

    @staticmethod
    def validate_integer(value: str, name: str = "Value") -> Tuple[bool, str]:
        """Validate string is valid integer"""
        try:
            int(value)
            return True, ""
        except ValueError:
            return False, f"{name} must be a valid integer"

    @staticmethod
    def validate_float(value: str, name: str = "Value") -> Tuple[bool, str]:
        """Validate string is valid float"""
        try:
            float(value)
            return True, ""
        except ValueError:
            return False, f"{name} must be a valid number"

    @staticmethod
    def validate_youtube_channel(name: str) -> Tuple[bool, str]:
        """Validate YouTube channel name"""
        if not name or not name.strip():
            return False, "Channel name cannot be empty"

        if len(name) < 3:
            return False, "Channel name must be at least 3 characters"

        if len(name) > 100:
            return False, "Channel name must be less than 100 characters"

        return True, ""

    @staticmethod
    def validate_animation_type(anim_type: str) -> Tuple[bool, str]:
        """Validate animation type"""
        valid_types = ["slide", "bounce", "fade", "zoom", "none"]
        if anim_type not in valid_types:
            return False, f"Animation type must be one of: {', '.join(valid_types)}"
        return True, ""

    @staticmethod
    def validate_animation_direction(direction: str) -> Tuple[bool, str]:
        """Validate animation direction"""
        valid_directions = ["left", "right", "up", "down"]
        if direction not in valid_directions:
            return False, f"Direction must be one of: {', '.join(valid_directions)}"
        return True, ""

    @staticmethod
    def validate_ai_model(model: str) -> Tuple[bool, str]:
        """Validate AI model name"""
        valid_models = ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
        if model not in valid_models:
            return False, f"Model must be one of: {', '.join(valid_models)}"
        return True, ""

    @staticmethod
    def validate_demucs_model(model: str) -> Tuple[bool, str]:
        """Validate Demucs model"""
        valid_models = ["htdemucs", "htdemucs_ft", "mdx_extra"]
        if model not in valid_models:
            return False, f"Model must be one of: {', '.join(valid_models)}"
        return True, ""

    @staticmethod
    def validate_required_field(value: str, field_name: str) -> Tuple[bool, str]:
        """Validate required field is not empty"""
        if not value or not str(value).strip():
            return False, f"{field_name} is required"
        return True, ""

    @staticmethod
    def path_exists(path: str) -> bool:
        """Quick check if path exists"""
        if not path:
            return False
        try:
            return Path(path).exists()
        except:
            return False

    @staticmethod
    def is_file(path: str) -> bool:
        """Quick check if path is a file"""
        if not path:
            return False
        try:
            return Path(path).is_file()
        except:
            return False

    @staticmethod
    def is_directory(path: str) -> bool:
        """Quick check if path is a directory"""
        if not path:
            return False
        try:
            return Path(path).is_dir()
        except:
            return False

    @staticmethod
    def get_file_extension(path: str) -> str:
        """Get file extension"""
        try:
            return Path(path).suffix.lower()
        except:
            return ""

    @staticmethod
    def validate_video_file(path: str) -> Tuple[bool, str]:
        """Validate video file"""
        valid, msg = Validators.validate_path(path, must_exist=True, is_file=True)
        if not valid:
            return valid, msg

        ext = Validators.get_file_extension(path)
        valid_extensions = [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"]
        if ext not in valid_extensions:
            return False, f"Video file must be one of: {', '.join(valid_extensions)}"

        return True, ""

    @staticmethod
    def validate_audio_file(path: str) -> Tuple[bool, str]:
        """Validate audio file"""
        valid, msg = Validators.validate_path(path, must_exist=True, is_file=True)
        if not valid:
            return valid, msg

        ext = Validators.get_file_extension(path)
        valid_extensions = [".mp3", ".wav", ".flac", ".m4a", ".aac"]
        if ext not in valid_extensions:
            return False, f"Audio file must be one of: {', '.join(valid_extensions)}"

        return True, ""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to remove invalid characters"""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename


class ProfileValidator:
    """Validate complete profile data"""

    @staticmethod
    def validate_profile(profile_data: dict, existing_names: list = None) -> Tuple[bool, list]:
        """
        Validate complete profile data
        Returns: (is_valid, list_of_errors)
        """
        errors = []

        # Validate name
        name = profile_data.get("name", "")
        valid, msg = Validators.validate_profile_name(name, existing_names)
        if not valid:
            errors.append(f"Name: {msg}")

        # Validate voice
        voice = profile_data.get("default_voice", "")
        if not voice:
            errors.append("Voice: Voice must be selected")

        # Validate background video (if provided)
        bg_video = profile_data.get("background_video", "")
        if bg_video:
            valid, msg = Validators.validate_path(bg_video)
            if not valid:
                errors.append(f"Background Video: {msg}")

        # Validate frame color
        color = profile_data.get("frame_color", "")
        if color:
            valid, msg = Validators.validate_color_hex(color)
            if not valid:
                errors.append(f"Frame Color: {msg}")

        # Validate video scale
        scale = profile_data.get("video_scale", 0.85)
        valid, msg = Validators.validate_number_range(scale, 0.1, 1.0, "Video Scale")
        if not valid:
            errors.append(msg)

        # Validate voice level
        voice_level = profile_data.get("voice_level", 1.2)
        valid, msg = Validators.validate_number_range(voice_level, 0.0, 2.0, "Voice Level")
        if not valid:
            errors.append(msg)

        # Validate music level
        music_level = profile_data.get("music_level", 0.1)
        valid, msg = Validators.validate_number_range(music_level, 0.0, 1.0, "Music Level")
        if not valid:
            errors.append(msg)

        # Validate YouTube channel (if upload enabled)
        if profile_data.get("enable_upload", False):
            channel = profile_data.get("youtube_channel", "")
            valid, msg = Validators.validate_youtube_channel(channel)
            if not valid:
                errors.append(f"YouTube Channel: {msg}")

        return len(errors) == 0, errors
