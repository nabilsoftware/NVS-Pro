# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

**PyArmor obfuscate (ALWAYS all 42 files):**
```
cd "D:\DEV-SCRIPT\ALL-SCRIPT\3-NVS-PRO" && "D:\DEV-SCRIPT\ALL-SCRIPT\3-NVS-PRO\python\Scripts\pyarmor.exe" gen -O pyarmor_dist 1_diarize_cut_video.py 1_smart_interview_processor.py 10_youtube_upload.py 11_thumbnail_generator.py 2_style_interview_clips.py 3_transcribe_clips.py 4_ai_rewrite_script.py 4_smart_broll_processor.py 5_generate_voiceover.py 5_generate_voiceover_api.py 7_assemble_final_video.py 8_rank_video_sequence.py 9_combine_ranked_videos.py app_utils.py auto_updater.py content_creator.py content_creator_parallel.py crop_tool.py firebase_license.py first_run_setup.py license_manager.py logo_editor_tool.py logo_overlay_helper.py recreat-videos.py remote_control.py story_video_creator.py ui_api_manager.py ui_config_manager.py ui_license_dialog.py ui_modern.py ui_profile_wizard.py ui_settings_editor.py ui_styles.py ui_subscription_dialog.py ui_system_check.py ui_validators.py ui_voice_manager.py ui_widgets.py ui_youtube_downloader.py version.py video_editor_tool.py video_queue_manager.py
```

**Build installer:**
```
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "D:\DEV-SCRIPT\ALL-SCRIPT\3-NVS-PRO\installer\NVS_Pro_Setup.iss"
```

Output: `installer_output/NVS_Pro_v{VERSION}_Setup.exe`

## Critical Build Rules

- **NEVER use system Python 3.13** for PyArmor — use embedded `python\Scripts\pyarmor.exe` (Python 3.11.9)
- **NEVER use PyInstaller** — this project uses PyArmor + Inno Setup only
- **ALWAYS obfuscate ALL 42 files** — partial obfuscation causes mixed-version bugs in `pyarmor_dist/`
- **Update version in TWO places**: `version.py` AND `installer\NVS_Pro_Setup.iss`

## Architecture Overview

NVS Pro is a Windows desktop app for automated YouTube video production. It uses an embedded Python 3.11.9 runtime, PyQt5 GUI, and AI/ML libraries (Whisper, pyannote, Gemini, Claude).

### Launch Chain
```
NVS_Pro.exe → python/pythonw.exe ui_modern.py
```
`launcher.py` sets the Windows AppUserModelID then launches `ui_modern.py` via `pythonw.exe` (no console).

### Three Pipeline Orchestrators

1. **`recreat-videos.py`** — Recreate Videos pipeline (interview-based). Steps 1→2→3→4→5→7→8→9→10→11.
2. **`content_creator.py`** — Create Video pipeline (full AI creation). Uses `content_creator_parallel.py` + `video_queue_manager.py` for parallel processing.
3. **`story_video_creator.py`** — Story Video pipeline (voiceover-only, skips interview steps).

### Numbered Pipeline Scripts

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `1_diarize_cut_video.py` | Speaker diarization (pyannote) + clip cutting |
| 1 alt | `1_smart_interview_processor.py` | AI-powered smart clip selection |
| 2 | `2_style_interview_clips.py` | GPU styling (NVENC), 9:16 crop, animations, SFX |
| 3 | `3_transcribe_clips.py` | Speech-to-text (faster-whisper) |
| 4 | `4_ai_rewrite_script.py` | AI script rewriting (Gemini/Claude/OpenAI) |
| 4 alt | `4_smart_broll_processor.py` | B-roll clip creation from raw footage |
| 5 | `5_generate_voiceover.py` | Browser-based TTS (Playwright + fish.audio) |
| 5 alt | `5_generate_voiceover_api.py` | API-based TTS (fish.audio REST API) |
| 7 | `7_assemble_final_video.py` | Assemble final video from B-roll + voiceover |
| 8 | `8_rank_video_sequence.py` | Create interview→voiceover alternating sequence |
| 9 | `9_combine_ranked_videos.py` | Concatenate into single video + background music |
| 10 | `10_youtube_upload.py` | YouTube upload via Playwright |
| 11 | `11_thumbnail_generator.py` | AI thumbnail generation |

Voiceover method (browser vs API) is selected at runtime from `config.json["voiceover_settings"]["method"]`.

### UI Layer (`ui_*.py`)

`ui_modern.py` is the main PyQt5 QMainWindow with sidebar navigation + QStackedWidget pages. Pipeline workers run in QThread subclasses (PipelineWorker, ContentCreatorWorker, etc.).

Key modules: `ui_styles.py` (3 themes: orange/blue/green), `ui_config_manager.py` (config.json access), `ui_api_manager.py` (API keys), `ui_voice_manager.py` (voice profiles), `ui_settings_editor.py` (full settings page).

### Parallel Processing

`video_queue_manager.py` implements queue-based parallel pipeline execution with per-step concurrency limits. Each parallel video gets its own cloned browser profile for voiceover generation.

## Key File Paths

- **Dev source**: `D:\DEV-SCRIPT\ALL-SCRIPT\3-NVS-PRO\`
- **Installed app**: `C:\Users\nanab\AppData\Local\Programs\Nabil Video Studio Pro\`
- **User config**: `%LOCALAPPDATA%\NabilVideoStudioPro\config.json`
- **API keys**: `%LOCALAPPDATA%\NabilVideoStudioPro\api_keys.json`
- **Embedded Python**: `python\` (3.11.9 with stdlib, heavy packages installed on first run)
- **Prompt templates**: `prompts\` (AI script/thumbnail prompt templates)

## torchcodec / PyTorch Nightly Compatibility

RTX 5080/5090 requires PyTorch nightly cu128. The nightly torchaudio delegates to torchcodec, which doesn't work on Windows (needs FFmpeg shared DLLs).

**Solution** (applied by `first_run_setup.py` → `patch_installed_packages()`):
1. Uninstall torchcodec
2. Patch `pyannote/audio/core/io.py` — FFmpeg subprocess fallback for audio loading
3. Patch `speechbrain/utils/torch_audio_backend.py` — hasattr guards for removed APIs
4. Patch `torchaudio/__init__.py` — soundfile fallback for load()/save()

These patches run on every first_run_setup execution, even when packages are already installed.

## Path Resolution Pattern

All scripts use this pattern to work in both dev and installed (frozen) mode:
```python
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()
```

## First Run Setup

`first_run_setup.py` installs ~3-4 GB of packages in 12 stages on first launch. It also checks for Visual C++ Runtime and FFmpeg. The setup flag file is `setup_complete.flag`.
