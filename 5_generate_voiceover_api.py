# Fix Windows console encoding for emoji/unicode
import sys
import io
if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Fish Audio API Voiceover Generator
Generates voiceovers using Fish Audio API (faster than browser method)
"""

import os
import json
import time
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== SETTINGS =====
MAX_PARAGRAPH_LENGTH = 6500  # Maximum characters per API call
MAX_PARALLEL_REQUESTS = 5  # Number of parallel API requests (like browser tabs)
REQUEST_TIMEOUT = 120  # Timeout for API requests in seconds

# Default paths
DEFAULT_OUTPUT_FOLDER = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NabilVideoStudioPro', 'voiceovers')

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('voiceover_api.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def load_api_key():
    """Load Fish Audio API key from api_keys.json"""
    # Try multiple locations for api_keys.json
    possible_paths = [
        Path(__file__).parent / "api_keys.json",
        Path(os.environ.get('LOCALAPPDATA', '')) / "NabilVideoStudioPro" / "api_keys.json",
    ]

    for api_keys_path in possible_paths:
        if api_keys_path.exists():
            try:
                with open(api_keys_path, 'r', encoding='utf-8') as f:
                    api_keys = json.load(f)

                fish_data = api_keys.get("fish_audio", {})
                api_key = fish_data.get("api_key", "")

                if api_key:
                    logger.info(f"Loaded Fish Audio API key from: {api_keys_path}")
                    return api_key
            except Exception as e:
                logger.warning(f"Error loading {api_keys_path}: {e}")

    return None


def extract_voice_id_from_url(voice_url):
    """Extract modelId from Fish Audio URL"""
    if not voice_url:
        return None

    # URL format: https://fish.audio/app/text-to-speech/?modelId=e4a2d14e7f5c4b2d80a6c56538051612&version=speech-1.6
    try:
        if "modelId=" in voice_url:
            voice_id = voice_url.split("modelId=")[1].split("&")[0]
            logger.info(f"Extracted voice ID: {voice_id[:20]}...")
            return voice_id
    except Exception as e:
        logger.warning(f"Could not extract voice ID from URL: {e}")

    return None


def load_config_settings():
    """Load voiceover settings from config.json"""
    config_path = Path(os.environ.get('LOCALAPPDATA', '')) / "NabilVideoStudioPro" / "config.json"

    settings = {
        "max_parallel": MAX_PARALLEL_REQUESTS,
    }

    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            voice_settings = config.get("voiceover_settings", {})
            if voice_settings.get("enable_parallel_processing", True):
                settings["max_parallel"] = MAX_PARALLEL_REQUESTS
            else:
                settings["max_parallel"] = 1

            logger.info("Loaded voiceover settings from config.json")
    except Exception as e:
        logger.warning(f"Could not load config: {e}")

    return settings


def split_long_paragraph(paragraph, max_length=MAX_PARAGRAPH_LENGTH):
    """Split long paragraph into smaller chunks at natural break points (like browser version)"""
    if len(paragraph) <= max_length:
        return [paragraph]

    splits = []
    remaining_text = paragraph

    while remaining_text:
        if len(remaining_text) <= max_length:
            splits.append(remaining_text)
            break

        # Find the best split point within max_length
        best_split = 0

        # Priority 1: Look for sentence endings (. ! ?)
        for i in range(min(len(remaining_text), max_length) - 1, 0, -1):
            if remaining_text[i] in '.!?' and (i + 1 >= len(remaining_text) or remaining_text[i + 1] == ' '):
                best_split = i + 1
                break

        # Priority 2: Look for paragraph breaks (\n\n)
        if best_split == 0:
            for i in range(min(len(remaining_text), max_length) - 2, 0, -1):
                if remaining_text[i:i+2] == '\n\n':
                    best_split = i + 2
                    break

        # Priority 3: Look for line breaks (\n)
        if best_split == 0:
            for i in range(min(len(remaining_text), max_length) - 1, 0, -1):
                if remaining_text[i] == '\n':
                    best_split = i + 1
                    break

        # Priority 4: Look for comma
        if best_split == 0:
            for i in range(min(len(remaining_text), max_length) - 1, 0, -1):
                if remaining_text[i] == ',':
                    best_split = i + 1
                    break

        # Fallback: Just split at max_length
        if best_split == 0:
            best_split = max_length

        # Extract the split part and add to results
        split_part = remaining_text[:best_split].strip()
        if split_part:
            splits.append(split_part)

        remaining_text = remaining_text[best_split:].strip()

    return splits


def load_script_paragraphs(script_file_path):
    """Load script file and split into paragraphs (same as browser version - split by triple newline)"""
    try:
        with open(script_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            return []

        # Split by TRIPLE newline (same as browser version)
        paragraphs = [p.strip() for p in content.split("\n\n\n") if p.strip()]

        logger.info(f"Loaded {len(paragraphs)} paragraphs from script")
        return paragraphs

    except Exception as e:
        logger.error(f"Error loading script file: {e}")
        return []


def generate_voiceover_api(text, api_key, voice_id, output_path):
    """Generate voiceover using Fish Audio API"""

    # Fish Audio TTS API endpoint
    api_url = "https://api.fish.audio/v1/tts"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "reference_id": voice_id,  # Voice model ID
        "format": "mp3",
        "latency": "normal"  # or "balanced" or "low"
    }

    try:
        logger.info(f"Generating voiceover ({len(text)} chars)...")
        start_time = time.time()

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            stream=True
        )

        if response.status_code == 200:
            # Save audio file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            elapsed = time.time() - start_time
            logger.info(f"Generated: {output_path} ({elapsed:.1f}s)")
            return True, output_path

        elif response.status_code == 401:
            logger.error("Invalid API key! Please check your Fish Audio API key.")
            return False, "Invalid API key"

        elif response.status_code == 402:
            logger.error("Insufficient credits! Please add credits to your Fish Audio account.")
            return False, "Insufficient credits"

        elif response.status_code == 429:
            logger.warning("Rate limited! Waiting before retry...")
            time.sleep(10)
            return False, "Rate limited"

        else:
            error_msg = f"API error: {response.status_code} - {response.text[:200]}"
            logger.error(error_msg)
            return False, error_msg

    except requests.exceptions.Timeout:
        logger.error(f"Request timed out after {REQUEST_TIMEOUT}s")
        return False, "Timeout"

    except Exception as e:
        logger.error(f"Error generating voiceover: {e}")
        return False, str(e)


def generate_paragraph_audio(args):
    """Generate audio for a single paragraph (for parallel processing)"""
    paragraph_idx, paragraph_text, api_key, voice_id, output_folder = args

    output_path = Path(output_folder) / f"paragraph_{paragraph_idx:03d}.mp3"
    success, result = generate_voiceover_api(paragraph_text, api_key, voice_id, str(output_path))

    if success:
        return paragraph_idx, str(output_path), None
    else:
        return paragraph_idx, None, result


def process_script_file(script_file, api_key, voice_id, output_folder):
    """Process a single script file - split into paragraphs and generate audio for each (like browser version)"""

    try:
        # Load and split script into paragraphs (using triple newline like browser)
        paragraphs = load_script_paragraphs(script_file)

        if not paragraphs:
            logger.warning(f"No paragraphs found in: {script_file}")
            return []

        logger.info(f"Processing {len(paragraphs)} paragraphs from script")

        # Create output folder
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)

        # Check which paragraphs already exist (skip completed ones)
        existing_files = []
        tasks = []
        for i, para in enumerate(paragraphs):
            para_idx = i + 1
            audio_file = output_path / f"paragraph_{para_idx:03d}.mp3"
            if audio_file.exists() and audio_file.stat().st_size > 0:
                existing_files.append((para_idx, str(audio_file)))
                logger.info(f"⏭️ Skipping paragraph {para_idx} (already exists)")
            else:
                tasks.append((para_idx, para, api_key, voice_id, str(output_path)))

        # If all paragraphs already exist, return them
        if not tasks:
            print(f"\n✅ All {len(paragraphs)} paragraphs already generated - skipping!")
            logger.info(f"All {len(paragraphs)} paragraphs already exist, skipping generation")
            existing_files.sort(key=lambda x: x[0])
            return [f[1] for f in existing_files]

        print(f"\nProcessing {len(tasks)} paragraphs ({len(existing_files)} already done)...")

        results = list(existing_files)  # Start with existing files
        failed = []

        # Limit parallel requests to avoid rate limiting
        max_workers = min(MAX_PARALLEL_REQUESTS, len(tasks))
        logger.info(f"Using {max_workers} parallel workers for {len(tasks)} remaining paragraphs")

        # Process paragraphs in parallel with limited workers
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(generate_paragraph_audio, task): task[0] for task in tasks}

            for future in as_completed(futures):
                para_idx = futures[future]
                try:
                    idx, audio_path, error = future.result()
                    if audio_path:
                        results.append((idx, audio_path))
                        print(f"  [{idx}/{len(paragraphs)}] paragraph_{idx:03d}.mp3")
                    else:
                        failed.append((idx, error))
                        print(f"  [{idx}/{len(paragraphs)}] FAILED: {error}")
                except Exception as e:
                    failed.append((para_idx, str(e)))
                    print(f"  [{para_idx}/{len(paragraphs)}] ERROR: {e}")

        # Retry failed paragraphs (rate limited ones) with delay
        if failed:
            rate_limited = [(idx, err) for idx, err in failed if "Rate limited" in str(err)]
            if rate_limited:
                print(f"\n⏳ Retrying {len(rate_limited)} rate-limited paragraphs...")
                logger.info(f"Retrying {len(rate_limited)} rate-limited paragraphs with delay")
                time.sleep(5)  # Wait before retrying

                # Get the tasks for failed paragraphs
                retry_tasks = [t for t in tasks if t[0] in [idx for idx, _ in rate_limited]]

                # Retry one at a time to avoid rate limiting again
                for task in retry_tasks:
                    time.sleep(2)  # Delay between retries
                    try:
                        idx, audio_path, error = generate_paragraph_audio(task)
                        if audio_path:
                            results.append((idx, audio_path))
                            # Remove from failed list
                            failed = [(i, e) for i, e in failed if i != idx]
                            print(f"  [{idx}/{len(paragraphs)}] ✅ RETRY SUCCESS: paragraph_{idx:03d}.mp3")
                        else:
                            print(f"  [{idx}/{len(paragraphs)}] ❌ RETRY FAILED: {error}")
                    except Exception as e:
                        print(f"  [{task[0]}/{len(paragraphs)}] ❌ RETRY ERROR: {e}")

        # Sort results by paragraph index
        results.sort(key=lambda x: x[0])
        audio_files = [r[1] for r in results]

        # Summary
        print(f"\nGenerated {len(audio_files)}/{len(paragraphs)} paragraph audio files")
        if failed:
            print(f"Failed paragraphs: {[f[0] for f in failed]}")

        return audio_files

    except Exception as e:
        logger.error(f"Error processing script {script_file}: {e}")
        return []


def process_text_file(text_file, api_key, voice_id, output_folder):
    """Process a single text file and generate voiceover (legacy - for folder processing)"""

    try:
        # Read text content
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read().strip()

        if not text:
            logger.warning(f"Empty file: {text_file}")
            return None

        # Create output filename
        base_name = Path(text_file).stem
        output_path = Path(output_folder) / f"{base_name}.mp3"

        success, result = generate_voiceover_api(text, api_key, voice_id, str(output_path))

        if success:
            return str(output_path)
        else:
            logger.error(f"Failed to generate {base_name}: {result}")
            return None

    except Exception as e:
        logger.error(f"Error processing {text_file}: {e}")
        return None


def process_folder(input_folder, output_folder=None, api_key=None, voice_url=None):
    """Process all text files in a folder"""

    input_path = Path(input_folder)

    if not input_path.exists():
        logger.error(f"Input folder not found: {input_folder}")
        return []

    # Set output folder
    if output_folder:
        output_path = Path(output_folder)
    else:
        output_path = input_path / "voiceovers"

    output_path.mkdir(parents=True, exist_ok=True)

    # Load API key if not provided
    if not api_key:
        api_key = load_api_key()

    if not api_key:
        logger.error("No Fish Audio API key found!")
        logger.error("Please add your API key in: API Manager -> Fish Audio")
        print("\n" + "="*60)
        print("ERROR: Fish Audio API key not configured!")
        print("="*60)
        print("Please go to API Manager and add your Fish Audio API key.")
        print("Get your API key from: https://fish.audio/api-keys")
        print("="*60 + "\n")
        return []

    # Extract voice ID from URL (passed from profile/orchestrator)
    voice_id = extract_voice_id_from_url(voice_url)

    if not voice_id:
        logger.error("No voice URL/ID provided!")
        logger.error("Voice URL should come from your profile settings.")
        print("\n" + "="*60)
        print("ERROR: No voice selected!")
        print("="*60)
        print("Please make sure you have a voice selected in your profile.")
        print("The voice URL from Voice Manager will be used automatically.")
        print("="*60 + "\n")
        return []

    # Find text files
    text_files = sorted(input_path.glob("*.txt"))

    if not text_files:
        logger.warning(f"No .txt files found in: {input_folder}")
        return []

    logger.info(f"Found {len(text_files)} text files to process")
    print(f"\nProcessing {len(text_files)} files with Fish Audio API...")
    print(f"Voice ID: {voice_id[:20]}..." if len(voice_id) > 20 else f"Voice ID: {voice_id}")
    print(f"Output: {output_path}\n")

    # Load config settings
    config = load_config_settings()

    # Dynamic parallel - use number of files as workers (process all at once)
    num_files = len(text_files)
    max_parallel = num_files if config["max_parallel"] > 1 else 1

    results = []

    if max_parallel > 1:
        # Parallel processing - all files at once
        logger.info(f"Using parallel processing with {max_parallel} workers (all files at once)")

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {
                executor.submit(
                    process_text_file,
                    str(tf),
                    api_key,
                    voice_id,
                    str(output_path)
                ): tf for tf in text_files
            }

            for i, future in enumerate(as_completed(futures)):
                text_file = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        print(f"[{i+1}/{len(text_files)}] {Path(text_file).name}")
                    else:
                        print(f"[{i+1}/{len(text_files)}] FAILED: {Path(text_file).name}")
                except Exception as e:
                    logger.error(f"Error processing {text_file}: {e}")
                    print(f"[{i+1}/{len(text_files)}] ERROR: {Path(text_file).name}")

    else:
        # Sequential processing
        for i, text_file in enumerate(text_files):
            print(f"[{i+1}/{len(text_files)}] Processing: {text_file.name}")

            result = process_text_file(
                str(text_file),
                api_key,
                voice_id,
                str(output_path)
            )

            if result:
                results.append(result)

            # Small delay between requests to avoid rate limiting
            if i < len(text_files) - 1:
                time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print(f"COMPLETED: {len(results)}/{len(text_files)} voiceovers generated")
    print(f"Output folder: {output_path}")
    print(f"{'='*60}\n")

    return results


def run_voiceover_from_script(script_file, output_folder, voice_url=None):
    """
    Process a single script file and generate voiceovers for each paragraph.
    Called from orchestrator/pipeline for API method.

    Same behavior as browser version:
    - Splits script by triple newline (\\n\\n\\n) into paragraphs
    - Creates paragraph_001.mp3, paragraph_002.mp3, etc.
    - Processes all paragraphs in parallel

    Args:
        script_file: Path to the rewritten script .txt file
        output_folder: Folder to save paragraph_XXX.mp3 files
        voice_url: Fish Audio voice URL with modelId parameter

    Returns:
        List of generated audio file paths, or empty list on failure
    """
    print("\n" + "="*60)
    print("FISH AUDIO API - Voiceover Generator")
    print("="*60)

    # Load API key
    api_key = load_api_key()
    if not api_key:
        logger.error("No Fish Audio API key found!")
        print("ERROR: Fish Audio API key not configured!")
        print("Please go to API Manager and add your Fish Audio API key.")
        return []

    # Extract voice ID from URL
    voice_id = extract_voice_id_from_url(voice_url)
    if not voice_id:
        logger.error("No voice URL/ID provided!")
        print("ERROR: No voice selected!")
        print("Please make sure you have a voice selected in your profile.")
        return []

    print(f"Script: {script_file}")
    print(f"Voice ID: {voice_id[:20]}..." if len(voice_id) > 20 else f"Voice ID: {voice_id}")
    print(f"Output: {output_folder}")

    # Process script file - split into paragraphs and generate audio
    results = process_script_file(script_file, api_key, voice_id, output_folder)

    print(f"\n{'='*60}")
    print(f"COMPLETED: {len(results)} voiceover files generated")
    print(f"Output folder: {output_folder}")
    print(f"{'='*60}\n")

    return results


def generate_voiceovers_from_script(script_file, output_folder, voice_url, num_parallel=5):
    """
    Wrapper function called by Script to Voice tool.

    Args:
        script_file: Path to script text file
        output_folder: Output folder for MP3 files
        voice_url: Fish Audio voice URL
        num_parallel: Number of parallel requests (not used in API, kept for compatibility)
    """
    return run_voiceover_from_script(script_file, output_folder, voice_url)


def main(input_folder=None, output_folder=None, voice_url=None, script_file=None):
    """Main entry point - compatible with orchestrator"""

    print("\n" + "="*60)
    print("FISH AUDIO API - Voiceover Generator")
    print("="*60)

    if voice_url:
        print(f"Voice URL: {voice_url[:50]}...")

    # If script_file is provided, use paragraph mode (like browser)
    if script_file:
        if not output_folder:
            output_folder = str(Path(script_file).parent / "voiceovers")
        return run_voiceover_from_script(script_file, output_folder, voice_url)

    # Otherwise, process folder of text files (legacy mode)
    if not input_folder:
        input_folder = os.getcwd()

    results = process_folder(input_folder, output_folder, voice_url=voice_url)

    return len(results) > 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fish Audio API Voiceover Generator")
    parser.add_argument("--input", "-i", help="Input folder with .txt files (legacy mode)")
    parser.add_argument("--output", "-o", help="Output folder for .mp3 files")
    parser.add_argument("--voice", "-v", help="Voice ID or Fish Audio URL")
    parser.add_argument("--script", "-s", help="Single script file to process (paragraph mode - like browser)")

    args = parser.parse_args()

    # If script file provided, use paragraph mode
    if args.script:
        results = main(
            output_folder=args.output,
            voice_url=args.voice,
            script_file=args.script
        )
        success = len(results) > 0 if isinstance(results, list) else results
    else:
        success = main(
            input_folder=args.input,
            output_folder=args.output,
            voice_url=args.voice
        )

    sys.exit(0 if success else 1)
