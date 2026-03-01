# Fix Windows console encoding for emoji/unicode
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.stdout.flush()
print("[DEBUG] Step 3 script starting...", flush=True)

# PyTorch 2.6+ compatibility fix - MUST BE BEFORE ANY AI IMPORTS
import os
print("[DEBUG] Importing torch...", flush=True)
import torch
print("[DEBUG] Torch imported, applying patch...", flush=True)
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False  # Always force False for trusted models
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
print("✅ PyTorch compatibility patch applied", flush=True)

# 🚀 Try to import faster-whisper first (3-5x faster), fallback to standard whisper
print("[DEBUG] Importing faster-whisper...", flush=True)
try:
    from faster_whisper import WhisperModel
    USE_FASTER_WHISPER = True
    print("✅ Using faster-whisper (3-5x faster transcription)", flush=True)
except ImportError:
    import whisper
    USE_FASTER_WHISPER = False
    print("⚠️ faster-whisper not found, using standard whisper (slower)")
    print("   Install with: pip install faster-whisper")

import gc
from tqdm import tqdm
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading
import hashlib
import time
from pathlib import Path

# ====================================================================
# 🎛️ LOAD SETTINGS FROM CONFIG FILE
# ====================================================================

def load_config_settings():
    """Load settings from config.json"""
    config_path = Path(os.environ.get('LOCALAPPDATA', '')) / "NabilVideoStudioPro" / "config.json"

    # Default settings
    settings = {
        "model_size": "auto",
        "language": "auto",
        "use_gpu": True,
        "save_srt_files": False,
        "save_individual_txt": False,
        "save_combined_file": True,
        "save_json_files": False,
        "show_progress_bar": True,
        "show_detailed_logs": True
    }

    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            trans = config.get("transcription_settings", {})
            settings["model_size"] = trans.get("model_size", "auto")
            settings["language"] = trans.get("language", "auto")
            settings["use_gpu"] = trans.get("use_gpu", True)
            settings["save_srt_files"] = trans.get("save_srt_files", False)
            settings["save_individual_txt"] = trans.get("save_individual_txt", False)
            settings["save_combined_file"] = trans.get("save_combined_file", True)
            settings["save_json_files"] = trans.get("save_json_files", False)
            settings["show_progress_bar"] = trans.get("show_progress_bar", True)
            settings["show_detailed_logs"] = trans.get("show_detailed_logs", True)

            print(f"✅ Loaded settings from config.json", flush=True)
            print(f"   Model: {settings['model_size']}, Language: {settings['language']}, GPU: {settings['use_gpu']}", flush=True)
    except Exception as e:
        print(f"⚠️ Could not load config, using defaults: {e}", flush=True)

    return settings

# Load settings from config
_config_settings = load_config_settings()

# ====================================================================
# 🎛️ SETTINGS (FROM CONFIG OR DEFAULTS)
# ====================================================================

# 📁 FOLDER SETTINGS (set by UI, these are fallback defaults)
INPUT_FOLDERS = [
    "",
]

OUTPUT_BASE_FOLDER = ""

# 📄 OUTPUT FILE CONTROLS
OUTPUT_FILE_PREFIX = ""
OUTPUT_FILE_SUFFIX = ""
COMBINED_FILE_NAME = "all_script"
CREATE_FOLDER_PER_INPUT = False
KEEP_ORIGINAL_NAMES = False
INCLUDE_HEADER_IN_COMBINED_FILE = False

# 🤖 WHISPER SETTINGS (FROM CONFIG)
MODEL_SIZE = _config_settings["model_size"]  # From Settings UI
_config_lang = _config_settings["language"]
LANGUAGE = None if _config_lang == "auto" else _config_lang  # From Settings UI
TASK = "transcribe"

# ⚡ SPEED SETTINGS (FROM CONFIG)
PARALLEL_WORKERS = 1
USE_GPU = _config_settings["use_gpu"]  # From Settings UI
GPU_BATCH_SIZE = 4
ENABLE_CACHING = True
CACHE_FOLDER = "cache"

# 🚀 FASTER-WHISPER OPTIMIZATION
FASTER_WHISPER_COMPUTE_TYPE = "auto"
FASTER_WHISPER_BEAM_SIZE = 5
FASTER_WHISPER_VAD_FILTER = True
FASTER_WHISPER_NUM_WORKERS = 2

# =============================================================================
# 🎮 AUTO-DETECT GPU VRAM AND OPTIMIZE SETTINGS
# =============================================================================

def auto_detect_gpu_settings():
    """
    Automatically detect GPU and choose safe settings.
    Returns: (model_size, compute_type, use_gpu, gpu_name, vram_gb)
    """
    gpu_name = "CPU"
    vram_gb = 0
    
    try:
        print("[DEBUG] Checking CUDA availability...", flush=True)
        if torch.cuda.is_available():
            print("[DEBUG] CUDA available, getting device name...", flush=True)
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[DEBUG] GPU: {gpu_name}", flush=True)
            
            # Skip VRAM detection (can crash on some systems)
            # Instead, detect GPU tier from name
            gpu_lower = gpu_name.lower()
            
            if any(x in gpu_lower for x in ["1050", "1060", "1650", "1660", "mx", "quadro p"]):
                # Older/budget GPUs - use int8 for safety
                vram_gb = 4  # Assume 4GB
                print(f"[DEBUG] Detected budget GPU, using safe settings", flush=True)
                return ("base", "int8", True, gpu_name, vram_gb)
            elif any(x in gpu_lower for x in ["1070", "1080", "2060", "2070", "2080", "3060", "3070", "3080", "3090", "4060", "4070", "4080", "4090"]):
                # Modern GPUs - use float16
                vram_gb = 8  # Assume 8GB+
                print(f"[DEBUG] Detected modern GPU, using full settings", flush=True)
                return ("base", "float16", True, gpu_name, vram_gb)
            else:
                # Unknown GPU - use safe defaults
                vram_gb = 4
                print(f"[DEBUG] Unknown GPU, using safe settings", flush=True)
                return ("base", "int8", True, gpu_name, vram_gb)
        else:
            print("[DEBUG] CUDA not available, using CPU", flush=True)
            return ("base", "int8", False, "No GPU", 0)
    except Exception as e:
        print(f"[DEBUG] GPU detection error: {e}, using CPU", flush=True)
        return ("base", "int8", False, "Error", 0)

    # Choose settings based on VRAM
    # VRAM requirements (approximate):
    # - tiny:   ~1GB
    # - base:   ~1.5GB  
    # - small:  ~2GB
    # - medium: ~5GB
    # - large:  ~10GB

    if vram_gb < 3:
        # Very low VRAM (e.g., GTX 1050 2GB) - use tiny + int8
        model_size = "tiny"
        compute_type = "int8"
    elif vram_gb < 5:
        # Low VRAM (e.g., GTX 1050 Ti 4GB) - use base + int8
        model_size = "base"
        compute_type = "int8"
    elif vram_gb < 7:
        # Medium VRAM (e.g., GTX 1060 6GB) - use base + float16
        model_size = "base"
        compute_type = "float16"
    elif vram_gb < 10:
        # Good VRAM (e.g., RTX 3060 Ti 8GB) - use base + float16
        model_size = "base"
        compute_type = "float16"
    else:
        # High VRAM (e.g., RTX 3090 24GB) - use medium + float16
        model_size = "medium"
        compute_type = "float16"

    return (model_size, compute_type, True, gpu_name, vram_gb)

# Apply auto-detection if settings are "auto"
_auto_model_size = MODEL_SIZE
_auto_compute_type = FASTER_WHISPER_COMPUTE_TYPE
_auto_use_gpu = USE_GPU
_detected_gpu_name = ""
_detected_vram_gb = 0

if MODEL_SIZE == "auto" or FASTER_WHISPER_COMPUTE_TYPE == "auto":
    (_auto_model_size, _auto_compute_type, _auto_use_gpu,
     _detected_gpu_name, _detected_vram_gb) = auto_detect_gpu_settings()
    
    # Only override if set to "auto"
    if MODEL_SIZE == "auto":
        MODEL_SIZE = _auto_model_size
    if FASTER_WHISPER_COMPUTE_TYPE == "auto":
        FASTER_WHISPER_COMPUTE_TYPE = _auto_compute_type
    # Use the result from auto-detect (don't call torch.cuda.is_available again - it can hang!)
    USE_GPU = _auto_use_gpu

    print(f"🎮 [AUTO-DETECT] GPU: {_detected_gpu_name} ({_detected_vram_gb:.1f}GB VRAM)", flush=True)
    print(f"⚡ [AUTO-DETECT] Selected: model={MODEL_SIZE}, compute={FASTER_WHISPER_COMPUTE_TYPE}, GPU={USE_GPU}", flush=True)

# 📄 OUTPUT SETTINGS (FROM CONFIG)
SAVE_SRT_FILES = _config_settings["save_srt_files"]  # From Settings UI
SAVE_INDIVIDUAL_TXT = _config_settings["save_individual_txt"]  # From Settings UI
SAVE_COMBINED_FILE = _config_settings["save_combined_file"]  # From Settings UI
SAVE_JSON_FILES = _config_settings["save_json_files"]  # From Settings UI

# 🎨 DISPLAY SETTINGS (FROM CONFIG)
SHOW_PROGRESS_BAR = _config_settings["show_progress_bar"]  # From Settings UI
SHOW_DETAILED_LOGS = _config_settings["show_detailed_logs"]  # From Settings UI
SHOW_SUCCESS_EMOJI = True  # Always show emojis


# ====================================================================
# 📝 SCRIPT CODE (Don't change below unless you know what you're doing)
# ====================================================================

thread_local_data = threading.local()

# =============================================================================
# SMART CACHING SYSTEM
# =============================================================================

def calculate_file_hash(file_path):
    """Calculate MD5 hash of a file for cache identification"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        log_message(f"❌ Error calculating hash for {file_path}: {e}")
        return None

def get_cache_path(file_path, cache_folder):
    """Get cache file path for a given media file"""
    file_hash = calculate_file_hash(file_path)
    if not file_hash:
        return None
    
    cache_dir = Path(cache_folder)
    cache_dir.mkdir(exist_ok=True)
    
    # Include model size and settings in cache filename
    cache_filename = f"{file_hash}_{MODEL_SIZE}_{LANGUAGE or 'auto'}.json"
    return cache_dir / cache_filename

def load_cached_transcript(file_path, cache_folder):
    """Load cached transcript if available and valid"""
    if not ENABLE_CACHING:
        return None
        
    cache_path = get_cache_path(file_path, cache_folder)
    if not cache_path or not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
        
        # Verify cache is for same file (check file size and modified time)
        file_stat = os.stat(file_path)
        if (cached_data.get('file_size') == file_stat.st_size and 
            cached_data.get('file_mtime') == file_stat.st_mtime):
            
            log_message(f"📋 Using cached transcript for {os.path.basename(file_path)}")
            return cached_data.get('result')
    
    except Exception as e:
        log_message(f"⚠️ Error loading cache for {file_path}: {e}")
    
    return None

def save_transcript_to_cache(file_path, result, cache_folder):
    """Save transcript result to cache"""
    if not ENABLE_CACHING:
        return
        
    cache_path = get_cache_path(file_path, cache_folder)
    if not cache_path:
        return
    
    try:
        file_stat = os.stat(file_path)
        cache_data = {
            'file_size': file_stat.st_size,
            'file_mtime': file_stat.st_mtime,
            'model_size': MODEL_SIZE,
            'language': LANGUAGE,
            'timestamp': time.time(),
            'result': result
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        log_message(f"💾 Cached transcript for {os.path.basename(file_path)}")
    
    except Exception as e:
        log_message(f"⚠️ Error saving cache for {file_path}: {e}")

# =============================================================================
# GPU BATCH PROCESSING OPTIMIZATION
# =============================================================================

def process_gpu_batch(video_batch, output_folder, gpu_manager):
    """Process multiple videos in a GPU batch for better efficiency"""
    if not USE_GPU or not torch.cuda.is_available():
        # Fallback to individual processing
        return [transcribe_single_video(video_info) for video_info in video_batch]
    
    device_to_use = None
    results = []
    
    try:
        device_to_use = gpu_manager.acquire()
        model = get_model(device_to_use)
        
        log_message(f"🚀 Processing GPU batch of {len(video_batch)} files...")
        
        for video_info in video_batch:
            video_path, output_folder, _, file_index = video_info
            filename = os.path.basename(video_path)
            
            try:
                # Check cache first
                cached_result = load_cached_transcript(video_path, CACHE_FOLDER)
                if cached_result:
                    save_transcription_files(output_folder, filename, cached_result, file_index)
                    results.append({
                        "success": True, 
                        "file": filename, 
                        "text": cached_result["text"],
                        "output_name": generate_output_filename(filename, file_index),
                        "cached": True
                    })
                    continue
                
                # Process with GPU
                log_message(f"🎤 GPU transcribing {filename}...")

                if USE_FASTER_WHISPER:
                    # 🚀 faster-whisper transcription (3-5x faster)
                    segments, info = model.transcribe(
                        video_path,
                        language=LANGUAGE,
                        task=TASK,
                        beam_size=FASTER_WHISPER_BEAM_SIZE,
                        vad_filter=FASTER_WHISPER_VAD_FILTER,
                        vad_parameters=dict(min_silence_duration_ms=500) if FASTER_WHISPER_VAD_FILTER else None
                    )
                    # Convert segments to standard whisper format
                    result = {
                        "text": " ".join([segment.text for segment in segments]),
                        "language": info.language
                    }
                else:
                    # Standard whisper transcription
                    options = {"fp16": True, "task": TASK}
                    if LANGUAGE:
                        options["language"] = LANGUAGE
                    result = model.transcribe(video_path, **options)
                
                # Save to cache
                save_transcript_to_cache(video_path, result, CACHE_FOLDER)
                
                # Save files
                save_transcription_files(output_folder, filename, result, file_index)
                
                results.append({
                    "success": True, 
                    "file": filename, 
                    "text": result["text"],
                    "output_name": generate_output_filename(filename, file_index),
                    "cached": False
                })
                
                log_message(f"✅ GPU completed: {filename}")
                
            except Exception as e:
                log_message(f"❌ GPU batch error with {filename}: {e}")
                results.append({"success": False, "file": filename, "error": str(e)})
        
        return results
        
    except Exception as e:
        log_message(f"❌ GPU batch processing error: {e}")
        # Fallback to individual processing
        return [transcribe_single_video(video_info) for video_info in video_batch]
    
    finally:
        if device_to_use:
            gpu_manager.release()

def create_batches(video_args, batch_size):
    """Create batches for GPU processing"""
    batches = []
    for i in range(0, len(video_args), batch_size):
        batches.append(video_args[i:i + batch_size])
    return batches

def get_model(device_to_use):
    """Loads or retrieves the model for the current thread."""
    if not hasattr(thread_local_data, "whisper_model"):
        if SHOW_DETAILED_LOGS:
            print(f"Thread {threading.get_ident()}: Loading model {MODEL_SIZE} onto {device_to_use}...")

        if USE_FASTER_WHISPER:
            # 🚀 Use faster-whisper (3-5x faster, same quality)
            thread_local_data.whisper_model = WhisperModel(
                MODEL_SIZE,
                device=device_to_use,
                compute_type=FASTER_WHISPER_COMPUTE_TYPE,
                num_workers=FASTER_WHISPER_NUM_WORKERS
            )
            if SHOW_DETAILED_LOGS:
                print(f"Thread {threading.get_ident()}: Faster-whisper model loaded (compute: {FASTER_WHISPER_COMPUTE_TYPE}).")
        else:
            # Fallback to standard whisper
            thread_local_data.whisper_model = whisper.load_model(MODEL_SIZE).to(device_to_use)
            if SHOW_DETAILED_LOGS:
                print(f"Thread {threading.get_ident()}: Standard whisper model loaded.")

    return thread_local_data.whisper_model

class SimpleGPUManager:
    """Simple GPU/resource management using a Semaphore."""
    def __init__(self, max_workers=2):
        self.semaphore = threading.Semaphore(max_workers)
        self.device = "cuda" if (torch.cuda.is_available() and USE_GPU) else "cpu"

    def acquire(self):
        self.semaphore.acquire()
        return self.device

    def release(self):
        if self.device == "cuda":
            try:
                torch.cuda.empty_cache() # Clear cache after each GPU task
            except Exception:
                pass  # Ignore CUDA cleanup errors
        # gc.collect() # Call less frequently if it's a bottleneck
        self.semaphore.release()


def log_message(message, show_emoji=True):
    """Print message with optional emoji and timestamp/thread ID."""
    if SHOW_DETAILED_LOGS:
        timestamp = datetime.now().strftime('%H:%M:%S')
        thread_id_str = f"[Thread-{threading.get_ident() % 1000:03d}]"
        full_message = f"{timestamp} {thread_id_str} {message}"
        if show_emoji and SHOW_SUCCESS_EMOJI:
            print(full_message)
        elif not show_emoji: # Only remove emojis if they are not desired for non-success messages
            print(full_message.replace("🚀", "").replace("✅", "").replace("❌", "").replace("📁", "").replace("🎉", "").replace("📄","").replace("📚","").replace("🎤",""))
        else: # SHOW_SUCCESS_EMOJI is False, print without emojis
            print(full_message.replace("🚀", "").replace("✅", "").replace("❌", "").replace("📁", "").replace("🎉", "").replace("📄","").replace("📚","").replace("🎤",""))


def get_video_files(folder_path):
    """Get all video and audio files from folder"""
    if not os.path.exists(folder_path):
        log_message(f"❌ Warning: Folder {folder_path} does not exist!")
        return []

    media_extensions = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv",  # Video
                        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a")         # Audio
    media_files = [f for f in os.listdir(folder_path) if f.lower().endswith(media_extensions)]

    try:
        return sorted(media_files, key=lambda x: int(''.join(filter(str.isdigit, os.path.splitext(x)[0]))))
    except ValueError: # Handles filenames that might not sort numerically cleanly
        return sorted(media_files)


def generate_output_filename(original_filename, index=None):
    """Generate output filename based on settings"""
    base_name = os.path.splitext(original_filename)[0]

    if not KEEP_ORIGINAL_NAMES and index is not None:
        base_name = f"video_{index:03d}" # Or media_ for general purpose

    if OUTPUT_FILE_PREFIX:
        base_name = OUTPUT_FILE_PREFIX + base_name
    if OUTPUT_FILE_SUFFIX:
        base_name = base_name + OUTPUT_FILE_SUFFIX

    return base_name


def get_output_folder(input_folder, base_output_folder):
    """Get the output folder path based on settings"""
    if CREATE_FOLDER_PER_INPUT:
        folder_name = os.path.basename(input_folder.rstrip('/\\'))
        return os.path.join(base_output_folder, folder_name)
    else:
        return base_output_folder


def save_transcription_files(output_folder, filename, result, file_index=None):
    """Save transcription in different formats based on settings"""
    # NOTE: With the requested changes, these individual file saves will be disabled.
    # This function will essentially do nothing unless you re-enable them in settings.
    base_name = generate_output_filename(filename, file_index)
    os.makedirs(output_folder, exist_ok=True)

    if SAVE_INDIVIDUAL_TXT:
        txt_path = os.path.join(output_folder, f"{base_name}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(result["text"])
        log_message(f"📄 Saved individual TXT: {txt_path}", show_emoji=False)

    if SAVE_JSON_FILES:
        json_path = os.path.join(output_folder, f"{base_name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        log_message(f"📄 Saved JSON: {json_path}", show_emoji=False)

    if SAVE_SRT_FILES and "segments" in result:
        srt_path = os.path.join(output_folder, f"{base_name}.srt")
        with open(srt_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(result["segments"]):
                start_time = segment['start']
                end_time = segment['end']
                text = segment['text']

                start_h = int(start_time // 3600)
                start_m = int((start_time % 3600) // 60)
                start_s = int(start_time % 60)
                start_ms = int((start_time % 1) * 1000)

                end_h = int(end_time // 3600)
                end_m = int((end_time % 3600) // 60)
                end_s = int(end_time % 60)
                end_ms = int((end_time % 1) * 1000)

                start_srt = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d}"
                end_srt = f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"

                srt_file.write(f"{i + 1}\n")
                srt_file.write(f"{start_srt} --> {end_srt}\n")
                srt_file.write(f"{text.strip()}\n\n")
        log_message(f"📄 Saved SRT: {srt_path}", show_emoji=False)


def transcribe_single_video(video_info):
    """Transcribe one video file with caching support. Model is retrieved via thread_local."""
    video_path, output_folder, gpu_manager, file_index = video_info
    filename = os.path.basename(video_path)
    device_to_use = None

    try:
        # Check cache first
        cached_result = load_cached_transcript(video_path, CACHE_FOLDER)
        if cached_result:
            save_transcription_files(output_folder, filename, cached_result, file_index)
            log_message(f"📋 Loaded from cache: {filename}")
            return {
                "success": True, 
                "file": filename, 
                "text": cached_result["text"],
                "output_name": generate_output_filename(filename, file_index),
                "cached": True
            }
        
        # Process normally if not cached
        device_to_use = gpu_manager.acquire()
        model = get_model(device_to_use)

        log_message(f"🎤 Transcribing {filename} on {device_to_use}...")

        if USE_FASTER_WHISPER:
            # 🚀 faster-whisper transcription (3-5x faster)
            segments, info = model.transcribe(
                video_path,
                language=LANGUAGE,
                task=TASK,
                beam_size=FASTER_WHISPER_BEAM_SIZE,
                vad_filter=FASTER_WHISPER_VAD_FILTER,
                vad_parameters=dict(min_silence_duration_ms=500) if FASTER_WHISPER_VAD_FILTER else None
            )
            # Convert segments to standard whisper format
            result = {
                "text": " ".join([segment.text for segment in segments]),
                "language": info.language
            }
        else:
            # Standard whisper transcription
            options = {"fp16": (device_to_use == "cuda"), "task": TASK}
            if LANGUAGE:
                options["language"] = LANGUAGE
            result = model.transcribe(video_path, **options)
        
        # Save to cache
        save_transcript_to_cache(video_path, result, CACHE_FOLDER)
        
        # Save files
        save_transcription_files(output_folder, filename, result, file_index)

        log_message(f"✅ Completed: {filename}")
        return {
            "success": True, 
            "file": filename, 
            "text": result["text"],
            "output_name": generate_output_filename(filename, file_index),
            "cached": False
        }

    except Exception as e:
        log_message(f"❌ Error with {filename}: {e}")
        import traceback
        if SHOW_DETAILED_LOGS:
            traceback.print_exc()
        return {"success": False, "file": filename, "error": str(e)}
    finally:
        if device_to_use:
            gpu_manager.release()
        # Do not del model here, it's managed by thread_local_data and cleared per folder
        # gc.collect() # Moved to less frequent calls


def process_single_folder(input_folder):
    """Process all videos in one folder"""
    folder_name = os.path.basename(input_folder.rstrip('/\\'))
    # output_folder is still computed based on CREATE_FOLDER_PER_INPUT,
    # but individual file saving is now disabled.
    # The combined file path will be handled specifically below.
    output_folder = get_output_folder(input_folder, OUTPUT_BASE_FOLDER)

    log_message(f"🚀 Starting folder: {folder_name}")
    log_message(f"📁 Output will be in: {OUTPUT_BASE_FOLDER}") # Clarify for the user

    # No need to os.makedirs(output_folder) here if individual files are off
    # as the combined file will create its own specific path in OUTPUT_BASE_FOLDER.

    media_files = get_video_files(input_folder)
    if not media_files:
        log_message(f"❌ No media files found in {input_folder}")
        return {"processed": 0, "failed": 0}

    log_message(f"📁 Found {len(media_files)} media files in {folder_name}")

    # If using GPU, PARALLEL_WORKERS dictates how many models are loaded.
    # Ensure this number is compatible with VRAM.
    gpu_manager = SimpleGPUManager(max_workers=PARALLEL_WORKERS)

    video_args = []
    for i, filename in enumerate(media_files, 1):
        video_path = os.path.join(input_folder, filename)
        video_args.append((video_path, output_folder, gpu_manager, i)) # output_folder is passed but not used for individual files now

    results = []
    
    # Use GPU batch processing if enabled and GPU is available
    if USE_GPU and torch.cuda.is_available() and GPU_BATCH_SIZE > 1:
        log_message(f"🚀 Using GPU batch processing (batch size: {GPU_BATCH_SIZE})")
        batches = create_batches(video_args, GPU_BATCH_SIZE)
        
        for batch_idx, batch in enumerate(batches, 1):
            log_message(f"📦 Processing batch {batch_idx}/{len(batches)} ({len(batch)} files)")
            batch_results = process_gpu_batch(batch, output_folder, gpu_manager)
            results.extend(batch_results)
            
            # Progress update
            completed_so_far = len(results)
            log_message(f"📊 Batch {batch_idx} complete. Total progress: {completed_so_far}/{len(media_files)}")
    else:
        # Standard processing with ThreadPoolExecutor
        log_message(f"⚙️ Using standard processing (workers: {PARALLEL_WORKERS})")
    
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        # Function to clear model from thread-local storage
        def clear_thread_model():
            if hasattr(thread_local_data, "whisper_model"):
                del thread_local_data.whisper_model # Deletes the model instance
                if SHOW_DETAILED_LOGS:
                    log_message(f"Model cleared from thread-local storage.", show_emoji=False)
                # Trigger CUDA cache clearing if GPU was used by this thread
                # This is more robust if some threads used GPU and others CPU (though unlikely with current setup)
                if torch.cuda.is_available() and USE_GPU:
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass  # Ignore CUDA cleanup errors
                try:
                    gc.collect() # Collect garbage after model deletion
                except Exception:
                    pass

        # Only process with ThreadPoolExecutor if not using GPU batching
        if not (USE_GPU and torch.cuda.is_available() and GPU_BATCH_SIZE > 1):
            futures_list = [executor.submit(transcribe_single_video, args) for args in video_args]

            if SHOW_PROGRESS_BAR:
                for future in tqdm(futures_list, desc=f"Processing {folder_name}", total=len(media_files)):
                    try:
                        results.append(future.result())
                    except Exception as e: # Catch errors from future.result() itself
                        log_message(f"❌ Critical error retrieving result for a file in {folder_name}: {e}")
                        results.append({"success": False, "file": "Unknown", "error": str(e)}) # Placeholder
            else:
                for future in futures_list:
                    try:
                        results.append(future.result())
                    except Exception as e:
                        log_message(f"❌ Critical error retrieving result for a file in {folder_name}: {e}")
                        results.append({"success": False, "file": "Unknown", "error": str(e)})

        # Clean up models from threads in this pool
        log_message(f"Folder {folder_name} processing complete. Cleaning up models from threads...", show_emoji=False)
        cleanup_futures = [executor.submit(clear_thread_model) for _ in range(PARALLEL_WORKERS)]
        for f in cleanup_futures:
            try:
                f.result() # Wait for cleanup
            except Exception as e:
                log_message(f"Error during thread model cleanup: {e}", show_emoji=False)
        log_message(f"Models cleaned up for folder {folder_name}.", show_emoji=False)


    successful_results = [r for r in results if r and r.get("success")]
    failed_count = len(media_files) - len(successful_results)
    
    # Count cached vs processed results
    cached_count = len([r for r in successful_results if r.get("cached", False)])
    processed_count = len(successful_results) - cached_count
    
    log_message(f"📊 Results: {processed_count} processed, {cached_count} from cache, {failed_count} failed")

    if SAVE_COMBINED_FILE and successful_results:
        # --- START OF CUSTOMIZATION FOR COMBINED FILE NAMING ---
        # If COMBINED_FILE_NAME is set (from CLI), use it; otherwise use folder name
        if COMBINED_FILE_NAME and COMBINED_FILE_NAME != "all_script":
            combined_filename_for_folder = COMBINED_FILE_NAME
        else:
            combined_filename_for_folder = f"{folder_name}.txt"
        combined_path = os.path.join(OUTPUT_BASE_FOLDER, combined_filename_for_folder)
        os.makedirs(OUTPUT_BASE_FOLDER, exist_ok=True) # Ensure base output folder exists
        # --- END OF CUSTOMIZATION ---

        with open(combined_path, "w", encoding="utf-8") as f:
            if INCLUDE_HEADER_IN_COMBINED_FILE:
                f.write(f"📝 Transcriptions for folder: {folder_name}\n")
                f.write(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"🤖 Model: {MODEL_SIZE}\n")
                f.write(f"🌐 Language: {LANGUAGE or 'Auto-detect'}\n")
                f.write(f"✅ Success: {len(successful_results)}/{len(media_files)}\n\n")
                f.write("=" * 50 + "\n\n")

            for result_item in successful_results:
                display_name = result_item.get('output_name', result_item['file'])
                f.write(f"🎬 {display_name}\n\n{result_item['text']}\n\n" + "-" * 40 + "\n\n")
        log_message(f"📚 Saved combined transcript: {combined_path}", show_emoji=False)

    log_message(f"✅ Folder {folder_name}: {len(successful_results)} processed, {failed_count} failed")
    return {"processed": len(successful_results), "failed": failed_count}


def main():
    """Main function"""
    print("🎬" + "=" * 50)
    print("   FAST WHISPER MEDIA TRANSCRIPTION (Optimized)")
    print("=" * 50 + "🎬")

    device_str = "CPU"
    actual_use_gpu = USE_GPU and torch.cuda.is_available() # Determine actual GPU usage
    if actual_use_gpu:
        device_str = f"GPU ({torch.cuda.get_device_name(0)})"
    elif USE_GPU and not torch.cuda.is_available():
        print("⚠️ WARNING: USE_GPU is True, but CUDA is not available. Falling back to CPU.")

    print(f"🤖 Model: {MODEL_SIZE}")
    print(f"💻 Device: {device_str}")
    print(f"👥 Workers: {PARALLEL_WORKERS} (Ensure VRAM supports this if using GPU)")
    if ENABLE_CACHING:
        print(f"💾 Smart Caching: Enabled (Cache folder: {CACHE_FOLDER})")
    if USE_GPU and torch.cuda.is_available() and GPU_BATCH_SIZE > 1:
        print(f"🚀 GPU Batch Processing: Enabled (Batch size: {GPU_BATCH_SIZE})")
    print(f"📁 Folders to process: {len(INPUT_FOLDERS)}")
    print("-" * 50)

    start_time = datetime.now()
    total_processed = 0
    total_failed = 0

    for i, input_folder_path in enumerate(INPUT_FOLDERS, 1):
        if not os.path.isdir(input_folder_path):
            log_message(f"❌ Input folder does not exist or is not a directory: {input_folder_path}. Skipping.", show_emoji=False)
            continue

        folder_name_display = os.path.basename(input_folder_path.rstrip('/\\')) or f"folder_{i}"
        print(f"\n📁 [{i}/{len(INPUT_FOLDERS)}] Processing: {folder_name_display}")

        result = process_single_folder(input_folder_path)
        total_processed += result["processed"]
        total_failed += result["failed"]

        # Aggressive memory cleanup after each folder, especially for GPU
        if actual_use_gpu:
            try:
                log_message("Attempting to clear CUDA cache after folder processing...", show_emoji=False)
                torch.cuda.empty_cache()
            except Exception as e:
                log_message(f"CUDA cache clear warning (non-fatal): {e}", show_emoji=False)
        try:
            gc.collect()
        except:
            pass

    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "🎉" + "=" * 48 + "🎉")
    print("           TRANSCRIPTION COMPLETE!")
    print("=" * 50)
    print(f"⏱️  Total time: {duration}")
    print(f"✅ Media files processed: {total_processed}")
    print(f"❌ Media files failed: {total_failed}")
    print(f"📁 Folders processed: {len([f for f in INPUT_FOLDERS if os.path.isdir(f)])}") # Count actual folders processed
    print(f"💾 Output location: {os.path.abspath(OUTPUT_BASE_FOLDER)}")

    if total_processed > 0:
        avg_time_per_file = duration.total_seconds() / total_processed
        print(f"⚡ Average per file: {avg_time_per_file:.2f} seconds")
        
        # Show caching statistics if enabled
        if ENABLE_CACHING:
            cache_dir = Path(CACHE_FOLDER)
            if cache_dir.exists():
                cache_files = list(cache_dir.glob("*.json"))
                print(f"💾 Cache files: {len(cache_files)} transcripts cached")

    print("🎉" + "=" * 48 + "🎉")
    
    # Safe cleanup to prevent CUDA crash on exit
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass  # Ignore any CUDA cleanup errors
    
    # Force garbage collection before exit
    try:
        import gc
        gc.collect()
    except Exception:
        pass


def parse_arguments():
    """Parse command-line arguments for CLI usage"""
    import argparse
    parser = argparse.ArgumentParser(
        description="Transcribe video/audio files using Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("input_folder", nargs="?", default=None,
                        help="Input folder containing video/audio files")
    parser.add_argument("--output-folder", "-o", default=None,
                        help="Output folder for transcripts")
    parser.add_argument("--save-combined", action="store_true",
                        help="Save combined transcript file")
    parser.add_argument("--combined-name", default=None,
                        help="Name for combined transcript file")

    return parser.parse_args()


def run_with_args():
    """Run transcription with command-line arguments"""
    global INPUT_FOLDERS, OUTPUT_BASE_FOLDER, SAVE_COMBINED_FILE, COMBINED_FILE_NAME

    # Parse command-line arguments
    args = parse_arguments()

    # Override module-level variables if arguments provided
    if args.input_folder:
        INPUT_FOLDERS = [args.input_folder]
        print(f"📁 Input folder: {args.input_folder}", flush=True)

    if args.output_folder:
        OUTPUT_BASE_FOLDER = args.output_folder
        print(f"📁 Output folder: {args.output_folder}", flush=True)

    if args.save_combined:
        SAVE_COMBINED_FILE = True

    if args.combined_name:
        COMBINED_FILE_NAME = args.combined_name

    main()


if __name__ == "__main__":
    exit_code = 0
    try:
        run_with_args()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    finally:
        # Skip CUDA cleanup - it can cause crashes on exit
        pass

    # Force clean exit to avoid CUDA crash during Python interpreter shutdown
    import os
    os._exit(exit_code)