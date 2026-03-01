# 4_ai_rewrite_script.py

# Fix Windows console encoding for emoji/unicode
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import pathlib
import time
import argparse
import re
import json
import requests

# --- Configuration ---
def get_user_data_dir():
    """Get user data directory (AppData on Windows) - same as UI"""
    if os.name == 'nt':  # Windows
        appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        return pathlib.Path(appdata) / "NabilVideoStudioPro"
    else:  # Linux/Mac
        return pathlib.Path.home() / ".nvspro"


def load_api_keys():
    """Load all API keys from api_keys.json"""
    api_keys = {}
    api_keys_file = "api_keys.json"

    try:
        # First try AppData (where UI saves it)
        user_data_dir = get_user_data_dir()
        api_keys_path = user_data_dir / api_keys_file

        # Fallback to script folder if not in AppData
        if not api_keys_path.exists():
            api_keys_path = pathlib.Path(__file__).parent / api_keys_file

        if api_keys_path.exists():
            with open(api_keys_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Load Gemini
            gemini_data = data.get("gemini", {})
            api_keys["gemini"] = {
                "api_key": gemini_data.get("api_key", ""),
                "model": gemini_data.get("model", "gemini-2.5-flash-preview-05-20")
            }

            # Load Claude
            claude_data = data.get("claude", {})
            api_keys["claude"] = {
                "api_key": claude_data.get("api_key", ""),
                "model": claude_data.get("model", "claude-sonnet-4-20250514")
            }

            # Load OpenAI
            openai_data = data.get("openai", {})
            api_keys["openai"] = {
                "api_key": openai_data.get("api_key", ""),
                "model": openai_data.get("model", "gpt-4o")
            }

            print(f"API keys loaded from {api_keys_path}")
            return api_keys

    except Exception as e:
        print(f"Error loading API keys: {e}")

    return api_keys


# Load API keys
API_KEYS = load_api_keys()

# Default settings
DEFAULT_PROVIDER = "gemini"
DEFAULT_PROMPT_FILE_PATH = pathlib.Path("D:/YOUTUBE/script-videos/PRO/prompt.txt")
DEFAULT_INPUT_TRANSCRIPT_PATH = pathlib.Path("D:/0-AutomatedVideoProjects/vd-1/3_transcripts/vd-1_raw_transcript.txt")
DEFAULT_OUTPUT_SCRIPT_PATH = pathlib.Path("D:/0-VIDEO/0-Download/vd-1/sample_transcript_rewritten.txt")


def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None


def write_file(filepath, content):
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote output to: {filepath}")
        return True
    except Exception as e:
        print(f"Error writing file {filepath}: {e}")
        return False


def generate_with_gemini(prompt_content, transcript_content, api_key, model_name):
    """Generate script using Google Gemini API"""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        print(f"Using Gemini model: {model_name}")

        model = genai.GenerativeModel(model_name=model_name)
        full_input = f"Prompt:\n{prompt_content}\n\nTranscript:\n{transcript_content}"

        print(f"Calling Gemini API ({len(full_input)} chars)...")
        response = model.generate_content(full_input)

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            return response.candidates[0].content.parts[0].text
        else:
            finish_reason = getattr(response.candidates[0], 'finish_reason', "Unknown") if response.candidates else "No candidates"
            print(f"Warning: Empty response. Finish reason: {finish_reason}")
            return None

    except Exception as e:
        print(f"Gemini API error: {e}")
        return None


def generate_with_claude(prompt_content, transcript_content, api_key, model_name):
    """Generate script using Claude (Anthropic) API"""
    try:
        print(f"Using Claude model: {model_name}")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        full_input = f"Prompt:\n{prompt_content}\n\nTranscript:\n{transcript_content}"

        data = {
            "model": model_name,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": full_input}]
        }

        print(f"Calling Claude API ({len(full_input)} chars)...")
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=300
        )

        if response.status_code == 200:
            result = response.json()
            content = result.get("content", [])
            if content and len(content) > 0:
                return content[0].get("text", "")
        else:
            print(f"Claude API error: {response.status_code} - {response.text[:200]}")
            return None

    except Exception as e:
        print(f"Claude API error: {e}")
        return None


def generate_with_openai(prompt_content, transcript_content, api_key, model_name):
    """Generate script using OpenAI (ChatGPT) API"""
    try:
        print(f"Using OpenAI model: {model_name}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        full_input = f"Prompt:\n{prompt_content}\n\nTranscript:\n{transcript_content}"

        data = {
            "model": model_name,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": full_input}]
        }

        print(f"Calling OpenAI API ({len(full_input)} chars)...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=300
        )

        if response.status_code == 200:
            result = response.json()
            choices = result.get("choices", [])
            if choices and len(choices) > 0:
                return choices[0].get("message", {}).get("content", "")
        else:
            print(f"OpenAI API error: {response.status_code} - {response.text[:200]}")
            return None

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def process_single_transcript(input_transcript_filepath, output_script_filepath, prompt_filepath,
                              provider="gemini", model_name=None, api_key=None):
    """Process a single transcript file and rewrite it using the selected AI provider"""

    print("\n--- Starting AI Script Writing ---")
    print(f"Provider: {provider.upper()}")

    # Get API key and model for the provider
    if not api_key:
        provider_config = API_KEYS.get(provider, {})
        api_key = provider_config.get("api_key", "")
        if not model_name:
            model_name = provider_config.get("model", "")

    if not api_key:
        print(f"Error: No API key found for {provider}!")
        print(f"Please add your {provider} API key through the API Manager.")
        return False

    # Read input files
    prompt_content = read_file(prompt_filepath)
    if prompt_content is None:
        print(f"Cannot proceed without prompt file: {prompt_filepath}")
        return False

    transcript_content = read_file(input_transcript_filepath)
    if transcript_content is None:
        print(f"Cannot proceed without transcript file: {input_transcript_filepath}")
        return False

    print(f"Prompt File: {prompt_filepath.name}")
    print(f"Input Transcript: {input_transcript_filepath.name}")
    print(f"Output: {output_script_filepath.name}")
    print(f"Model: {model_name}")

    # Generate with selected provider
    MAX_RETRIES = 3
    ai_response_text = None

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\nAttempt {attempt}/{MAX_RETRIES}...")

        if provider == "gemini":
            ai_response_text = generate_with_gemini(prompt_content, transcript_content, api_key, model_name)
        elif provider == "claude":
            ai_response_text = generate_with_claude(prompt_content, transcript_content, api_key, model_name)
        elif provider == "openai":
            ai_response_text = generate_with_openai(prompt_content, transcript_content, api_key, model_name)
        else:
            print(f"Unknown provider: {provider}")
            return False

        if ai_response_text:
            print("AI generation successful!")
            break

        if attempt < MAX_RETRIES:
            print("Retrying in 5 seconds...")
            time.sleep(5)

    if not ai_response_text:
        print("Failed to get AI response after all retries.")
        write_file(output_script_filepath, "Error: AI generation failed after retries.")
        return False

    # Format output with triple newline paragraph separation
    print("\nFormatting output...")
    formatted_text = ""
    if ai_response_text:
        # Normalize multiple newlines to paragraph marker
        temp_text = re.sub(r'\n\s*\n+', '___PARAGRAPH_MARKER___', ai_response_text.strip())
        # Replace marker with quadruple newline (for triple newline separation)
        formatted_text = temp_text.replace('___PARAGRAPH_MARKER___', '\n\n\n\n')
        # Ensure text ends with newline
        if formatted_text and not formatted_text.endswith('\n'):
            formatted_text += '\n'

    if write_file(output_script_filepath, formatted_text):
        print("--- AI Script Writing Complete ---")
        return True
    else:
        print("--- AI Script Writing Failed (File Write Error) ---")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Script Writer - Multi-Provider Support")
    parser.add_argument('--input-file', type=pathlib.Path, default=DEFAULT_INPUT_TRANSCRIPT_PATH,
                        help=f"Input transcript .txt. Default: {DEFAULT_INPUT_TRANSCRIPT_PATH}")
    parser.add_argument('--output-file', type=pathlib.Path, default=DEFAULT_OUTPUT_SCRIPT_PATH,
                        help=f"Output rewritten script .txt. Default: {DEFAULT_OUTPUT_SCRIPT_PATH}")
    parser.add_argument('--prompt-file', type=pathlib.Path, default=DEFAULT_PROMPT_FILE_PATH,
                        help=f"Prompt .txt file. Default: {DEFAULT_PROMPT_FILE_PATH}")
    parser.add_argument('--provider', type=str, default=DEFAULT_PROVIDER,
                        choices=['gemini', 'claude', 'openai'],
                        help=f"AI provider to use. Default: {DEFAULT_PROVIDER}")
    parser.add_argument('--model-name', type=str, default=None,
                        help="AI model name. Uses default from API Manager if not specified.")
    parser.add_argument('--api-key', type=str, default=None,
                        help="API Key. Uses saved key from API Manager if not specified.")

    args = parser.parse_args()

    if not (args.input_file.exists() and args.prompt_file.exists()):
        print("Error: Input transcript file or prompt file not found.")
        if not args.input_file.exists():
            print(f"Missing: {args.input_file}")
        if not args.prompt_file.exists():
            print(f"Missing: {args.prompt_file}")
        sys.exit(1)

    success = process_single_transcript(
        input_transcript_filepath=args.input_file.resolve(),
        output_script_filepath=args.output_file.resolve(),
        prompt_filepath=args.prompt_file.resolve(),
        provider=args.provider,
        model_name=args.model_name,
        api_key=args.api_key
    )

    if not success:
        print("AI Script writing process encountered errors.", file=sys.stderr)
        sys.exit(1)
