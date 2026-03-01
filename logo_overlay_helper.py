"""
Logo Overlay Helper for Step 7
This module handles logo overlay integration with FFmpeg
"""

import json
from pathlib import Path
import os

# Import app utilities for portable paths
try:
    import app_utils
    FFMPEG_PATH = app_utils.get_ffmpeg_path()
except ImportError:
    FFMPEG_PATH = "ffmpeg"

def load_logo_config():
    """Load logo configuration from JSON file"""
    config_file = Path(__file__).parent / "logo_config.json"

    if not config_file.exists():
        return None

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Verify logo file exists
        if not os.path.exists(config['logo_path']):
            print(f"Warning: Logo file not found: {config['logo_path']}")
            return None

        if not config.get('enabled', True):
            return None

        return config
    except Exception as e:
        print(f"Error loading logo config: {e}")
        return None

def get_overlay_position(position, padding):
    """Convert position name to FFmpeg overlay coordinates"""
    overlay_positions = {
        "top-left": f"{padding}:{padding}",
        "top": f"(W-w)/2:{padding}",
        "top-right": f"W-w-{padding}:{padding}",
        "left": f"{padding}:(H-h)/2",
        "center": f"(W-w)/2:(H-h)/2",
        "right": f"W-w-{padding}:(H-h)/2",
        "bottom-left": f"{padding}:H-h-{padding}",
        "bottom": f"(W-w)/2:H-h-{padding}",
        "bottom-right": f"W-w-{padding}:H-h-{padding}"
    }

    return overlay_positions.get(position, f"W-w-{padding}:H-h-{padding}")

def build_logo_filter_complex(logo_config):
    """Build the FFmpeg filter_complex string for logo overlay"""

    # Scale logo to specified percentage of video width
    size_percent = logo_config['size_percent'] / 100.0

    # Get overlay position
    overlay_pos = get_overlay_position(
        logo_config['position'],
        logo_config['padding_pixels']
    )

    # Calculate opacity (FFmpeg uses 0-1 scale)
    opacity = logo_config['opacity_percent'] / 100.0

    # Build filter complex string
    # [2:v] is the logo input
    # [0:v] is the main video
    filter_complex = (
        f"[2:v]scale=iw*{size_percent}:-1,"  # Scale logo proportionally
        f"format=rgba,"  # Ensure alpha channel
        f"colorchannelmixer=aa={opacity}[logo];"  # Apply opacity
        f"[0:v][logo]overlay={overlay_pos}"  # Overlay on video
    )

    return filter_complex

def add_logo_to_ffmpeg_cmd(original_cmd, logo_config):
    """
    Modify an existing FFmpeg command to include logo overlay

    Args:
        original_cmd: List of FFmpeg command arguments
        logo_config: Dictionary with logo configuration

    Returns:
        Modified FFmpeg command with logo overlay
    """

    if not logo_config:
        return original_cmd

    # Find where to insert logo input (after other inputs, before filters)
    modified_cmd = original_cmd.copy()

    # Add logo input
    logo_input = ["-i", logo_config['logo_path']]

    # Find position to insert (after concat input and audio input)
    insert_pos = 0
    for i, arg in enumerate(modified_cmd):
        if arg == "-filter_complex":
            insert_pos = i
            break
        elif arg in ["-c:v", "-map", "-shortest"]:
            insert_pos = i
            break

    # Insert logo input
    modified_cmd[insert_pos:insert_pos] = logo_input

    # Build filter complex for logo
    filter_complex = build_logo_filter_complex(logo_config)

    # Check if command already has filter_complex
    if "-filter_complex" in modified_cmd:
        # Modify existing filter_complex
        fc_index = modified_cmd.index("-filter_complex") + 1
        existing_filter = modified_cmd[fc_index]

        # Combine filters
        modified_cmd[fc_index] = f"{existing_filter};{filter_complex}"
    else:
        # Add new filter_complex
        # Insert before output file (last argument)
        output_pos = len(modified_cmd) - 1
        modified_cmd[output_pos:output_pos] = ["-filter_complex", filter_complex]

    return modified_cmd

def get_ffmpeg_logo_args(logo_config):
    """
    Get FFmpeg arguments for logo overlay as separate components

    Returns tuple of (input_args, filter_args, map_args)
    """

    if not logo_config:
        return [], [], []

    # Input arguments for logo file
    input_args = ["-i", logo_config['logo_path']]

    # Build filter
    filter_complex = build_logo_filter_complex(logo_config)

    # Filter arguments
    filter_args = ["-filter_complex", filter_complex]

    # Map arguments (if needed)
    map_args = ["-map", "[v]", "-map", "1:a"]

    return input_args, filter_args, map_args

# Example usage for Step 7 integration
def create_ffmpeg_cmd_with_logo(concat_file, voiceover_file, output_file, use_copy=True):
    """
    Create FFmpeg command with optional logo overlay

    This shows how Step 7 would integrate the logo
    """

    # Load logo configuration
    logo_config = load_logo_config()

    # Base FFmpeg command
    cmd = [FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-i", voiceover_file]

    if logo_config:
        # Add logo input
        cmd.extend(["-i", logo_config['logo_path']])

        # Build filter complex
        size_percent = logo_config['size_percent'] / 100.0
        opacity = logo_config['opacity_percent'] / 100.0
        overlay_pos = get_overlay_position(logo_config['position'], logo_config['padding_pixels'])

        filter_complex = (
            f"[2:v]scale=iw*{size_percent}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
            f"[0:v][logo]overlay={overlay_pos}[v]"
        )

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[v]", "-map", "1:a"])
    else:
        # No logo, use original mapping
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

    if use_copy and not logo_config:
        # Can only use copy when no filter is applied
        cmd.extend(["-c:v", "copy"])
    else:
        # Must re-encode when using filters
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "22"])

    cmd.extend(["-shortest", output_file])

    return cmd

if __name__ == "__main__":
    # Test loading configuration
    config = load_logo_config()
    if config:
        print("Logo configuration loaded:")
        print(json.dumps(config, indent=2))

        # Show example FFmpeg filter
        filter_complex = build_logo_filter_complex(config)
        print(f"\nFFmpeg filter_complex:\n{filter_complex}")
    else:
        print("No logo configuration found or logo disabled")