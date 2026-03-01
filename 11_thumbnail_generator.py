#!/usr/bin/env python3
"""
Step 11: Thumbnail Generator for Nabil Video Studio Pro
Generates viral thumbnail ideas and image prompts from video scripts.

Process:
1. Read video script from Step 1 (full_script_readable.txt)
2. Use AI to generate 10 thumbnail ideas with CTR scores + TOP 3 MEGA-VIRAL picks
3. Auto-pick best one or let user choose
4. Generate ready-to-use image prompt for AI image generators

Output:
- thumbnail_ideas.json: All 10 ideas + TOP 3 with detailed breakdown
- thumbnail_selected.json: The selected best idea
- thumbnail_prompt.txt: Ready prompt for Nano Banana Pro / Midjourney / DALL-E
"""

import argparse
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# PROMPT TEMPLATES - Load from TXT file or use default
# =============================================================================

def load_prompt_template():
    """Load prompt from TXT file if exists, otherwise use default"""
    # Look for prompt file in prompts folder
    prompt_paths = [
        Path(__file__).parent / "prompts" / "thumbnail_prompt_template.txt",
        Path(os.environ.get('LOCALAPPDATA', '')) / 'NabilVideoStudioPro' / 'prompts' / 'thumbnail_prompt_template.txt',
    ]

    for prompt_path in prompt_paths:
        if prompt_path.exists():
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Skip comment lines at the top (lines starting with #)
                lines = content.split('\n')
                # Find where actual prompt starts (after header comments)
                start_idx = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.strip().startswith('#'):
                        # Check if this looks like the start of the prompt
                        if 'YOUR ROLE' in line.upper() or 'YOU ARE' in line.upper():
                            start_idx = i
                            break

                prompt_content = '\n'.join(lines[start_idx:])
                logger.info(f"Loaded prompt template from: {prompt_path}")
                return prompt_content
            except Exception as e:
                logger.warning(f"Error loading prompt file: {e}")

    logger.info("Using default prompt template")
    return DEFAULT_PROMPT

# Default prompt (fallback if TXT file not found)
DEFAULT_PROMPT = '''# YOUR ROLE:

You are a Master Viral Content Strategist who creates thumbnails that consistently achieve 25-35% CTR. You understand deep psychological triggers, YouTube algorithm mechanics, and what makes people physically unable to scroll past without clicking.

## INPUT: VIDEO CONTENT

{video_content}

## YOUR TASK:
Based on the content above, generate 10 viral thumbnail ideas. Analyze the content to understand:
- Who are the main people/subjects mentioned?
- What is the drama/conflict/story?
- What emotions should the thumbnail convey?

### 10 THUMBNAIL + TITLE COMBINATIONS

Each option MUST include:
- Thumbnail Text (in quotes) - 2-4 words, shocking quote
- Who Says It (speaker identification)
- About Who/What (target)
- Viral Title (matching the thumbnail)
- CTR Potential (estimated percentage)
- Virality Score (1-10)
- Algorithm Boost Factors
- image_prompt (DETAILED, ready for Nano Banana Pro / Midjourney)

### PSYCHOLOGICAL CTR MAXIMIZATION FORMULAS:

**NEUROSCIENCE TRIGGERS TO EXPLOIT:**

1. **FEAR OF MISSING OUT (FOMO)**
- "LAST TIME" / "NEVER AGAIN" / "DELETED SOON"
- Creates panic that information will disappear

2. **SOCIAL HIERARCHY THREAT**
- "REPLACED" / "KICKED OUT" / "DEMOTED"
- Triggers status anxiety

3. **BETRAYAL RESPONSE**
- "STABBED MY BACK" / "SNAKE" / "FAKE FRIEND"
- Activates trust violation emotions

4. **INJUSTICE RAGE**
- "ROBBED" / "CHEATED" / "RIGGED"
- Triggers fairness violation anger

5. **TRIBAL LOYALTY**
- "DISRESPECTED US" / "ATTACKED OUR TEAM"
- Activates group defence mechanisms

6. **SCANDAL AROUSAL**
- "CAUGHT RED-HANDED" / "EXPOSED" / "BUSTED"
- Triggers gossip reward centres

### VIRALITY AMPLIFIERS:

**CONTROVERSY MULTIPLIERS:**
- Add "LIVE" or "RAW" = +5% CTR
- Add timestamp "3 MINUTES AGO" = +4% CTR
- Add "DELETED" or "BANNED" = +6% CTR
- Add "EMERGENCY" or "BREAKING" = +3% CTR
- Use ALL CAPS for 1-2 words = +2% CTR

**EMOTIONAL INTENSITY SCALE:**
Rate each thumbnail 1-10 for:
- Shock Value
- Drama Level
- Urgency Factor
- Controversial Risk
- Share Potential

### FORBIDDEN POWER WORDS (USE STRATEGICALLY):

**Career Destruction:** "FIRED" / "CANCELED" / "DONE" / "FINISHED" / "OVER"
**Relationship Bombs:** "CHEATING" / "DIVORCED" / "AFFAIR" / "CAUGHT"
**Money Triggers:** "LOST MILLIONS" / "BROKE" / "SUED" / "BANKRUPT"
**Health Scares:** "RUSHED TO" / "EMERGENCY" / "CRITICAL" / "HOSPITAL"

### ALGORITHM HACKING ELEMENTS:

**SESSION TIME BOOSTERS:**
- Promise multiple reveals: "3 Things She Said"
- Tease escalation: "Gets Worse"
- Suggest plot twist: "Ending Shocked Me"

**COMMENT MAGNETS:**
- Divisive statements requiring sides
- "Am I wrong?" implications
- Generational divide topics
- Gender perspective differences

**SHARE TRIGGERS:**
- "Everyone needs to see this"
- Information that affects others
- Protective warnings
- Justice campaigns

### ADVANCED VIRAL FORMULAS:

**The "Everyone's Talking" Method:** [Topic] + "finally addressed" + [consequence]
**The "Picking Sides" Method:** [Person A] vs [Person B] + "who's right?"
**The "Countdown Crisis" Method:** [Time limit] + "before it's too late"
**The "Secret Revealed" Method:** "What they didn't want you to know"
**The "Victim to Victor" Method:** [Underdog] + "destroys" + [villain]

## ═══════════════════════════════════════════════════════════════
## IMAGE PROMPT RULES FOR NANO BANANA PRO / MIDJOURNEY
## ═══════════════════════════════════════════════════════════════

**STEP 1: ANALYZE & COUNT PEOPLE**
- 1 person → SINGLE FACE layout
- 2 people → SPLIT SCREEN layout
- 3+ people → MULTI PANEL layout

**STEP 2: DETECT EMOTION FROM CONTEXT**
- Injury/crash/hospital → pain, suffering, bandages
- Drama/beef/callout → angry vs scared
- Arrested/jail/FBI → crying, defeated, handcuffs
- Retired/quit/finished → sad, emotional, tears
- Reaction/response → shocked, screaming

**STEP 3: CHOOSE LAYOUT**

【1 PERSON - SINGLE FACE】
- That person fills 80% of frame
- Extreme close-up face
- Emotion matches context
- Inset image showing incident (small, corner)
- Background: blurred hospital/jail/press conference

【2 PEOPLE - SPLIT SCREEN】
- Split screen 50/50
- LEFT = attacker/reactor (angry, yelling)
- RIGHT = victim/target (crying, defeated)
- Center inset with red border + red arrow

【3+ PEOPLE - MULTI PANEL】
- Main person large on left (40%)
- Others smaller on right (collage)

**STEP 4: THUMBNAIL TEXT STYLE**
- Quotation marks, ALL CAPS
- Giant bold BLACK text, thick WHITE outline
- Bottom 30% of thumbnail
- 2-4 word shocking quote
- Censor curse words (F*CK, SH*T, B*TCH)

**STEP 5: REQUIRED ELEMENTS**
- "BREAKING" or "EXCLUSIVE" red label bottom left (always)
- "LIVE" badge if breaking news
- Red arrow pointing to key detail
- CNN-style news look for serious topics

**STEP 6: CTR MAXIMIZERS**
- EXTREME facial emotions (NOT subtle - exaggerated!)
- Eyes WIDE OPEN, looking at camera
- Mouth OPEN (screaming, shocked, or crying)
- Visible tears/sweat if emotional
- High contrast, dramatic cinematic lighting
- 4K photorealistic quality

## OUTPUT FORMAT - MUST BE VALID JSON:

IMPORTANT: You MUST output ONLY valid JSON. No markdown, no explanations before or after. Start with {{ and end with }}.

```json
{{
    "video_topic": "Brief description of video content",
    "main_people": ["Person 1", "Person 2"],
    "ideas": [
        {{
            "id": 1,
            "thumbnail_text": "2-4 WORD QUOTE",
            "speaker": "Who says it",
            "target": "About who/what",
            "viral_title": "Full viral YouTube title (50-70 chars)",
            "ctr_potential": 28,
            "virality_score": 9,
            "emotion": "angry/shocked/crying/scared",
            "layout": "single_face/split_screen/multi_panel",
            "algorithm_boost_factors": ["FOMO", "Tribal loyalty", "Breaking news feel"],
            "why_viral": "Primary psychological trigger and target audience pain point",
            "image_prompt": "YouTube thumbnail, 16:9 aspect ratio, [LAYOUT TYPE from step 3], [person name] [EXTREME emotion from step 2], [background context], red BREAKING/EXCLUSIVE banner bottom left with white text, quote text '[THUMBNAIL_TEXT]' at very bottom in giant bold black letters with thick white outline in quotation marks, red arrow pointing to key element, 4K photorealistic, dramatic cinematic lighting, hyper-detailed"
        }},
        {{
            "id": 2,
            ... continue for all 10 ideas ...
        }}
    ],
    "top_3_picks": {{
        "nuclear_option_1": {{
            "option_id": 1,
            "thumbnail_text": "THE QUOTE",
            "virality_breakdown": {{
                "shock_factor": 9,
                "drama_level": 9,
                "urgency": 8,
                "controversy": 8,
                "share_potential": 9
            }},
            "why_mega_viral": "Primary psychological trigger and why it works",
            "visual_psychology": {{
                "dominant_color": "Red for anger",
                "face_expression": "Screaming, veins visible",
                "composition": "Rule of thirds, face dominates"
            }}
        }},
        "controversy_king_2": {{
            "option_id": 2,
            ... same structure ...
        }},
        "emotional_nuke_3": {{
            "option_id": 3,
            ... same structure ...
        }}
    }}
}}
```

Generate EXACTLY 10 ideas in the "ideas" array. Each idea MUST have all fields including a detailed image_prompt.
Also include "top_3_picks" with the 3 most viral options and detailed breakdown.

CRITICAL: Output ONLY the JSON object. No text before or after. Start your response with {{ and end with }}.
'''

# Load prompt from TXT file (or use default)
THUMBNAIL_IDEAS_PROMPT = load_prompt_template()


# =============================================================================
# AI PROVIDERS
# =============================================================================

def load_api_keys() -> Dict:
    """Load API keys from config file"""
    api_keys_paths = [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'NabilVideoStudioPro' / 'api_keys.json',
        Path(__file__).parent / 'api_keys.json',
    ]

    for path in api_keys_paths:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    keys = json.load(f)
                    logger.info(f"Loaded API keys from {path}")
                    return keys
            except Exception as e:
                logger.warning(f"Failed to load API keys from {path}: {e}")

    return {}


def call_claude_api(prompt: str, api_key: str) -> str:
    """Call Claude API for text generation"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise


def call_gemini_api(prompt: str, api_key: str, model_name: str = None) -> str:
    """Call Gemini API for text generation"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Use provided model or default
        if not model_name:
            model_name = 'gemini-2.0-flash'

        logger.info(f"Calling Gemini API with model: {model_name}")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)

        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise


def call_openai_api(prompt: str, api_key: str, model_name: str = None) -> str:
    """Call OpenAI (ChatGPT) API for text generation"""
    try:
        import requests

        # Use provided model or default
        if not model_name:
            model_name = 'gpt-4o'

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Newer models use max_completion_tokens instead of max_tokens
        # This includes: gpt-4o, gpt-4-turbo, o1, o3, gpt-5, etc.
        newer_models = ['gpt-4o', 'gpt-4-turbo', 'gpt-5', 'o1', 'o3', 'chatgpt-4o']
        use_new_param = any(model_name.startswith(m) or model_name == m for m in newer_models)

        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}]
        }

        if use_new_param:
            data["max_completion_tokens"] = 8192
        else:
            data["max_tokens"] = 8192

        logger.info(f"Calling OpenAI API with model: {model_name}...")
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
                raise Exception("OpenAI returned empty response")
        else:
            error_msg = response.text[:500] if response.text else "Unknown error"
            logger.error(f"OpenAI API error: {response.status_code} - {error_msg}")
            raise Exception(f"OpenAI API error: {response.status_code} - {error_msg}")

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


def call_ai(prompt: str, provider: str = "auto") -> str:
    """Call AI provider to generate response"""
    api_keys = load_api_keys()

    # Extract API keys and models - handle both flat and nested formats
    claude_key = (
        api_keys.get('claude_api_key') or
        api_keys.get('anthropic_api_key') or
        (api_keys.get('claude', {}).get('api_key') if isinstance(api_keys.get('claude'), dict) else None)
    )
    claude_model = api_keys.get('claude', {}).get('model') if isinstance(api_keys.get('claude'), dict) else None

    gemini_key = (
        api_keys.get('gemini_api_key') or
        api_keys.get('google_api_key') or
        (api_keys.get('gemini', {}).get('api_key') if isinstance(api_keys.get('gemini'), dict) else None)
    )
    gemini_model = api_keys.get('gemini', {}).get('model') if isinstance(api_keys.get('gemini'), dict) else None

    openai_key = (
        api_keys.get('openai_api_key') or
        (api_keys.get('openai', {}).get('api_key') if isinstance(api_keys.get('openai'), dict) else None)
    )
    openai_model = api_keys.get('openai', {}).get('model') if isinstance(api_keys.get('openai'), dict) else None

    logger.info(f"Provider requested: {provider}")
    logger.info(f"Available keys: Claude={bool(claude_key)}, OpenAI={bool(openai_key)}, Gemini={bool(gemini_key)}")

    # If specific provider requested
    if provider == "claude":
        if claude_key:
            logger.info(f"Using Claude API with model: {claude_model or 'default'}...")
            return call_claude_api(prompt, claude_key)
        else:
            raise ValueError("Claude API key not found")

    if provider == "openai" or provider == "chatgpt":
        if openai_key:
            logger.info(f"Using OpenAI (ChatGPT) API with model: {openai_model or 'gpt-4o'}...")
            return call_openai_api(prompt, openai_key, openai_model)
        else:
            raise ValueError("OpenAI API key not found")

    if provider == "gemini" or provider == "google":
        if gemini_key:
            logger.info(f"Using Gemini API with model: {gemini_model or 'gemini-2.0-flash'}...")
            return call_gemini_api(prompt, gemini_key, gemini_model)
        else:
            raise ValueError("Gemini API key not found")

    # Auto mode - try Claude first, then OpenAI, then Gemini
    if provider == "auto":
        if claude_key:
            try:
                logger.info(f"Using Claude API with model: {claude_model or 'default'}...")
                return call_claude_api(prompt, claude_key)
            except Exception as e:
                logger.warning(f"Claude failed: {e}, trying next...")

        if openai_key:
            try:
                logger.info(f"Using OpenAI API with model: {openai_model or 'gpt-4o'}...")
                return call_openai_api(prompt, openai_key, openai_model)
            except Exception as e:
                logger.warning(f"OpenAI failed: {e}, trying next...")

        if gemini_key:
            try:
                logger.info(f"Using Gemini API with model: {gemini_model or 'gemini-2.0-flash'}...")
                return call_gemini_api(prompt, gemini_key, gemini_model)
            except Exception as e:
                logger.error(f"Gemini failed: {e}")
                raise

    raise ValueError("No valid API key found for any AI provider")


# =============================================================================
# TITLE EXTRACTION FROM THUMBNAIL FILENAME
# =============================================================================

def extract_title_from_input_folder(input_folder: Path) -> Optional[str]:
    """Extract video title from thumbnail filename in input folder

    Input folder structure:
    ├── video.mp4 (or any video file)
    ├── thumbnail_VIDEO TITLE HERE.jpg (title extracted from filename)

    Returns the extracted title or None if not found
    """
    logger.info(f"Looking for thumbnail file in: {input_folder}")

    # Check if folder exists
    if not input_folder.exists():
        logger.error(f"Input folder does not exist: {input_folder}")
        return None

    # List all files in folder for debugging
    all_files = list(input_folder.glob("*"))
    logger.info(f"Files in folder: {[f.name for f in all_files]}")

    # Look for thumbnail files with title in name
    thumbnail_patterns = [
        "thumbnail_*.jpg",
        "thumbnail_*.png",
        "thumbnail_*.jpeg",
        "thumb_*.jpg",
        "thumb_*.png",
    ]

    for pattern in thumbnail_patterns:
        thumbnails = list(input_folder.glob(pattern))
        if thumbnails:
            logger.info(f"Found thumbnail with pattern {pattern}: {thumbnails[0].name}")
            # Get the first thumbnail found
            thumb_file = thumbnails[0]
            filename = thumb_file.stem  # Remove extension

            # Extract title by removing prefix
            if filename.lower().startswith('thumbnail_'):
                title = filename[10:]  # Remove "thumbnail_"
            elif filename.lower().startswith('thumb_'):
                title = filename[6:]  # Remove "thumb_"
            else:
                title = filename

            # Clean up the title
            title = title.strip()
            if title:
                logger.info(f"Extracted title from thumbnail: '{title}'")
                return title

    # Fallback: Check for any image file with a meaningful name
    image_extensions = ['*.jpg', '*.png', '*.jpeg', '*.webp']
    for ext in image_extensions:
        images = list(input_folder.glob(ext))
        for img in images:
            # Skip generic names
            if img.stem.lower() not in ['thumbnail', 'thumb', 'cover', 'image', 'poster']:
                title = img.stem.replace('_', ' ').replace('-', ' ').strip()
                if len(title) > 3:  # Must be meaningful
                    logger.info(f"Extracted title from image filename: '{title}'")
                    return title

    # Fallback: Use the folder name as the title (video folders are often named after the video)
    folder_name = input_folder.name
    if folder_name and len(folder_name) > 3:
        title = folder_name.replace('_', ' ').replace('-', ' ').strip()
        logger.info(f"Using folder name as title: '{title}'")
        return title

    # Last fallback: check parent folder name
    parent_name = input_folder.parent.name
    if parent_name and len(parent_name) > 3 and parent_name.upper() not in ['INPUT', 'OUTPUT', 'VIDEOS']:
        title = parent_name.replace('_', ' ').replace('-', ' ').strip()
        logger.info(f"Using parent folder name as title: '{title}'")
        return title

    logger.warning(f"No thumbnail with title found in {input_folder}")
    return None


# =============================================================================
# SCRIPT READING
# =============================================================================

def find_script_file(project_dir: Path) -> Optional[Path]:
    """Find the script file from project directory

    Supports both:
    - Content Creator mode: 1_processing/full_script_readable.txt
    - Recreate mode: 2_ai_scripts/*_rewritten_script_*.txt
    """
    # Look for script files in order of preference
    script_locations = [
        # Content Creator mode
        project_dir / "1_processing" / "full_script_readable.txt",
        project_dir / "1_processing" / "voiceover_script.txt",
        project_dir / "1_processing" / "script_data.json",
        project_dir / "scripts" / "voiceover_script.txt",
    ]

    for location in script_locations:
        if location.exists():
            logger.info(f"Found script at: {location}")
            return location

    # Recreate mode: Check 2_ai_scripts folder for rewritten scripts
    ai_scripts_dir = project_dir / "2_ai_scripts"
    if ai_scripts_dir.exists():
        # Look for rewritten script files
        rewritten_scripts = list(ai_scripts_dir.glob("*_rewritten_script_*.txt"))
        if rewritten_scripts:
            # Use the first/newest one
            rewritten_scripts.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            logger.info(f"Found script at: {rewritten_scripts[0]}")
            return rewritten_scripts[0]

        # Any txt file in ai_scripts
        txt_files = list(ai_scripts_dir.glob("*.txt"))
        if txt_files:
            logger.info(f"Found script at: {txt_files[0]}")
            return txt_files[0]

    # Recreate mode: Check 1_transcripts folder for raw transcript
    transcripts_dir = project_dir / "1_transcripts"
    if transcripts_dir.exists():
        transcript_files = list(transcripts_dir.glob("*_raw_transcript.txt"))
        if transcript_files:
            logger.info(f"Found transcript at: {transcript_files[0]}")
            return transcript_files[0]

    # Search recursively for any script file
    for pattern in ["**/full_script_readable.txt", "**/voiceover_script.txt", "**/*_rewritten_script_*.txt"]:
        matches = list(project_dir.glob(pattern))
        if matches:
            logger.info(f"Found script at: {matches[0]}")
            return matches[0]

    # Check parent directory (Create videos: project_dir may be CHANNEL level, scripts at VIDEO level)
    parent_dir = project_dir.parent
    if parent_dir != project_dir:
        parent_locations = [
            parent_dir / "1_processing" / "full_script_readable.txt",
            parent_dir / "1_processing" / "voiceover_script.txt",
        ]
        for location in parent_locations:
            if location.exists():
                logger.info(f"Found script in parent dir: {location}")
                return location

        ai_scripts_dir = parent_dir / "2_ai_scripts"
        if ai_scripts_dir.exists():
            rewritten = list(ai_scripts_dir.glob("*_rewritten_script_*.txt"))
            if rewritten:
                rewritten.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                logger.info(f"Found script in parent dir: {rewritten[0]}")
                return rewritten[0]

    return None


def read_script_content(script_path: Path) -> str:
    """Read and return script content"""
    try:
        if script_path.suffix == '.json':
            with open(script_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Extract text from JSON structure
                if isinstance(data, dict):
                    if 'voiceover_text' in data:
                        return data['voiceover_text']
                    elif 'script' in data:
                        return data['script']
                    elif 'segments' in data:
                        return '\n'.join([s.get('text', '') for s in data['segments']])
                return json.dumps(data, indent=2)
        else:
            with open(script_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        logger.error(f"Error reading script: {e}")
        return ""


# =============================================================================
# THUMBNAIL GENERATION
# =============================================================================

def generate_thumbnail_ideas(video_content: str, provider: str = "auto") -> Dict:
    """Generate 10 thumbnail ideas with image_prompt for each (ONE API call)

    Args:
        video_content: Either video script content OR video title (works with both modes)
        provider: AI provider to use (auto, claude, openai, gemini)
    """
    logger.info("Generating 10 thumbnail ideas + image prompts (ONE API call)...")
    logger.info(f"Using AI provider: {provider}")
    logger.info("Using full viral strategy prompt with psychological triggers...")

    prompt = THUMBNAIL_IDEAS_PROMPT.format(
        video_content=video_content[:10000]  # Limit content length
    )

    response = call_ai(prompt, provider=provider)

    # Extract JSON from response
    try:
        # Try multiple methods to find JSON
        ideas_data = None

        # Method 1: Try to parse the whole response as JSON
        try:
            ideas_data = json.loads(response.strip())
            logger.info("Parsed response directly as JSON")
        except json.JSONDecodeError:
            pass

        # Method 2: Find JSON block in markdown code fence
        if not ideas_data:
            json_code_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
            if json_code_match:
                try:
                    ideas_data = json.loads(json_code_match.group(1))
                    logger.info("Extracted JSON from code fence")
                except json.JSONDecodeError:
                    pass

        # Method 3: Find any JSON object with "ideas" key
        if not ideas_data:
            json_match = re.search(r'\{[^{}]*"ideas"\s*:\s*\[[\s\S]*\]\s*[^{}]*\}', response)
            if json_match:
                try:
                    ideas_data = json.loads(json_match.group())
                    logger.info("Extracted JSON object with ideas array")
                except json.JSONDecodeError:
                    pass

        # Method 4: Greedy match for largest JSON object
        if not ideas_data:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    ideas_data = json.loads(json_match.group())
                    logger.info("Extracted JSON using greedy match")
                except json.JSONDecodeError:
                    pass

        if ideas_data and ideas_data.get('ideas'):
            num_ideas = len(ideas_data.get('ideas', []))
            logger.info(f"Generated {num_ideas} thumbnail ideas!")
            return ideas_data
        else:
            logger.error("No valid JSON with ideas found in AI response")
            logger.error(f"Response preview: {response[:500]}...")
            return {"ideas": [], "error": "No JSON in response", "raw_response": response[:2000]}
    except Exception as e:
        logger.error(f"Failed to parse AI response: {e}")
        return {"ideas": [], "error": str(e), "raw_response": response[:2000]}


def select_best_idea(ideas_data: Dict, auto_select: bool = True) -> Dict:
    """Select the best thumbnail idea from TOP 3 picks"""
    ideas = ideas_data.get('ideas', [])
    top_3 = ideas_data.get('top_3_picks', {})

    if not ideas:
        logger.warning("No ideas to select from")
        return {}

    if auto_select:
        # Use TOP 3 nuclear option if available
        if top_3 and 'nuclear_option_1' in top_3:
            nuclear = top_3['nuclear_option_1']
            nuclear_id = nuclear.get('id', 1)
            for idea in ideas:
                if idea.get('id') == nuclear_id:
                    idea['selected_reason'] = nuclear.get('reason', 'Top viral pick')
                    idea['visual_setup'] = nuclear.get('visual_setup', {})
                    logger.info(f"Selected NUCLEAR OPTION #1: #{nuclear_id} - {nuclear.get('thumbnail_text', '')}")
                    return idea

        # Fallback: pick highest CTR potential
        best = max(ideas, key=lambda x: (x.get('ctr_potential', 0), x.get('virality_score', 0)))
        logger.info(f"Auto-selected idea #{best.get('id')} with CTR: {best.get('ctr_potential')}%")
        return best
    else:
        # Return first idea for manual selection mode
        return ideas[0]


def select_top_3_ideas(ideas_data: Dict) -> List[Dict]:
    """Select TOP 3 ideas sorted by CTR potential"""
    ideas = ideas_data.get('ideas', [])

    if not ideas:
        return []

    # Sort by CTR potential and virality score
    sorted_ideas = sorted(ideas, key=lambda x: (x.get('ctr_potential', 0), x.get('virality_score', 0)), reverse=True)

    # Return top 3
    return sorted_ideas[:3]


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def thumbnail_generator_step(project_dir: Path, output_dir: Path = None,
                             auto_select: bool = True, provider: str = "auto") -> bool:
    """Main thumbnail generator function (SCRIPT MODE)

    Args:
        project_dir: Project directory (where script files are)
        output_dir: Output directory for thumbnail files (default: 8_youtube_upload)
        auto_select: Auto-select best idea
        provider: AI provider to use (auto, claude, openai, gemini)
    """

    # Default output to 8_youtube_upload folder
    if output_dir is None:
        output_dir = project_dir / "8_youtube_upload"

    logger.info("=" * 60)
    logger.info("THUMBNAIL GENERATOR - SCRIPT MODE")
    logger.info("=" * 60)
    logger.info(f"Project: {project_dir}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Auto-select: {auto_select}")
    logger.info("=" * 60)

    # Find and read script
    script_path = find_script_file(project_dir)
    if not script_path:
        logger.error(f"No script file found in {project_dir}")
        return False

    script_content = read_script_content(script_path)
    if not script_content:
        logger.error("Script content is empty")
        return False

    logger.info(f"Script loaded: {len(script_content)} characters from {script_path.name}")

    # Output to specified directory (8_youtube_upload)
    thumbnail_dir = output_dir
    thumbnail_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate thumbnail ideas + prompts (ONE API call)
    logger.info("\n" + "=" * 60)
    logger.info("STEP 1: Generating 10 Ideas + Image Prompts (ONE API call)")
    logger.info(f"AI Provider: {provider}")
    logger.info("=" * 60)
    ideas_data = generate_thumbnail_ideas(script_content, provider=provider)

    ideas = ideas_data.get('ideas', [])
    if not ideas:
        logger.error("Failed to generate thumbnail ideas")
        return False

    logger.info(f"Generated {len(ideas)} ideas with prompts")

    # Save ONE txt file with ALL 10 ideas + prompts + TOP 3 MEGA-VIRAL PICKS
    prompt_file = thumbnail_dir / "thumbnail_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write("#" * 70 + "\n")
        f.write("#  THUMBNAIL IDEAS - ALL 10 WITH PROMPTS + TOP 3 MEGA-VIRAL PICKS\n")
        f.write("#  Copy prompt to Nano Banana Pro / Midjourney / DALL-E\n")
        f.write("#" * 70 + "\n\n")

        # Video topic
        if ideas_data.get('video_topic'):
            f.write(f"VIDEO TOPIC: {ideas_data.get('video_topic')}\n")
        if ideas_data.get('main_people'):
            f.write(f"MAIN PEOPLE: {', '.join(ideas_data.get('main_people', []))}\n")
        f.write("\n")

        # 10 OPTIONS WITH VIRALITY METRICS
        f.write("=" * 70 + "\n")
        f.write("  10 OPTIONS WITH VIRALITY METRICS\n")
        f.write("=" * 70 + "\n\n")

        for idea in ideas:
            f.write("-" * 70 + "\n")
            f.write(f"OPTION {idea.get('id', '?')}\n")
            f.write("-" * 70 + "\n")
            f.write(f"Thumbnail: \"{idea.get('thumbnail_text', 'N/A')}\"\n")
            f.write(f"Speaker: {idea.get('speaker', 'N/A')}\n")
            f.write(f"About: {idea.get('target', 'N/A')}\n")
            f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
            f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
            f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n")
            f.write(f"Layout: {idea.get('layout', 'N/A')}\n")
            f.write(f"Emotion: {idea.get('emotion', 'N/A')}\n")
            if idea.get('algorithm_boost_factors'):
                factors = idea.get('algorithm_boost_factors', [])
                if isinstance(factors, list):
                    f.write(f"Algorithm Boost: {', '.join(factors)}\n")
                else:
                    f.write(f"Algorithm Boost: {factors}\n")
            if idea.get('why_viral'):
                f.write(f"Why Viral: {idea.get('why_viral')}\n")
            f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")

        # TOP 3 MEGA-VIRAL PICKS section
        f.write("\n" + "=" * 70 + "\n")
        f.write("  TOP 3 MEGA-VIRAL PICKS\n")
        f.write("=" * 70 + "\n\n")

        # Check if AI provided top_3_picks with detailed breakdown
        top_3_picks = ideas_data.get('top_3_picks', {})
        pick_keys = ['nuclear_option_1', 'controversy_king_2', 'emotional_nuke_3']
        pick_names = ["NUCLEAR OPTION #1", "CONTROVERSY KING #2", "EMOTIONAL NUKE #3"]

        if top_3_picks:
            # Use AI's detailed top 3 picks
            for i, key in enumerate(pick_keys):
                pick = top_3_picks.get(key, {})
                if not pick:
                    continue

                option_id = pick.get('option_id', '?')
                # Find the full idea data
                idea = next((x for x in ideas if x.get('id') == option_id), {})

                f.write("-" * 70 + "\n")
                f.write(f"{pick_names[i]}: Option {option_id}\n")
                f.write("-" * 70 + "\n")
                f.write(f"Thumbnail Text: \"{pick.get('thumbnail_text', idea.get('thumbnail_text', 'N/A'))}\"\n")
                f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
                f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
                f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n\n")

                # Virality breakdown from AI
                breakdown = pick.get('virality_breakdown', {})
                if breakdown:
                    f.write("Virality Breakdown:\n")
                    f.write(f"  - Shock Factor: {breakdown.get('shock_factor', 'N/A')}/10\n")
                    f.write(f"  - Drama Level: {breakdown.get('drama_level', 'N/A')}/10\n")
                    f.write(f"  - Urgency: {breakdown.get('urgency', 'N/A')}/10\n")
                    f.write(f"  - Controversy: {breakdown.get('controversy', 'N/A')}/10\n")
                    f.write(f"  - Share Potential: {breakdown.get('share_potential', 'N/A')}/10\n")

                if pick.get('why_mega_viral'):
                    f.write(f"\nWhy MEGA-VIRAL: {pick.get('why_mega_viral')}\n")

                # Visual psychology
                visual = pick.get('visual_psychology', {})
                if visual:
                    f.write("\nVisual Psychology:\n")
                    f.write(f"  - Dominant Color: {visual.get('dominant_color', 'N/A')}\n")
                    f.write(f"  - Face Expression: {visual.get('face_expression', 'N/A')}\n")
                    f.write(f"  - Composition: {visual.get('composition', 'N/A')}\n")

                f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")
        else:
            # Fallback: Sort by CTR and virality to get top 3
            sorted_ideas = sorted(ideas, key=lambda x: (x.get('ctr_potential', 0), x.get('virality_score', 0)), reverse=True)
            top_3 = sorted_ideas[:3]

            for i, idea in enumerate(top_3):
                f.write("-" * 70 + "\n")
                f.write(f"{pick_names[i]}: Option {idea.get('id', '?')}\n")
                f.write("-" * 70 + "\n")
                f.write(f"Thumbnail Text: \"{idea.get('thumbnail_text', 'N/A')}\"\n")
                f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
                f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
                f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n\n")
                f.write("Virality Breakdown:\n")
                f.write(f"  - Layout: {idea.get('layout', 'N/A')}\n")
                f.write(f"  - Emotion: {idea.get('emotion', 'N/A')}\n")
                if idea.get('algorithm_boost_factors'):
                    factors = idea.get('algorithm_boost_factors', [])
                    if isinstance(factors, list):
                        f.write(f"  - Algorithm Boost: {', '.join(factors)}\n")
                if idea.get('why_viral'):
                    f.write(f"  - Why Viral: {idea.get('why_viral')}\n")
                f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")

        # YOUTUBE SEO SECTION
        youtube_seo = ideas_data.get('youtube_seo', {})
        if youtube_seo:
            f.write("\n" + "=" * 70 + "\n")
            f.write("  YOUTUBE SEO - DESCRIPTION, HASHTAGS & TAGS\n")
            f.write("=" * 70 + "\n\n")

            # Description
            description = youtube_seo.get('description', '')
            if description:
                f.write("-" * 70 + "\n")
                f.write("DESCRIPTION (copy to YouTube):\n")
                f.write("-" * 70 + "\n")
                f.write(f"{description}\n\n")

            # Hashtags
            hashtags = youtube_seo.get('hashtags', [])
            if hashtags:
                f.write("-" * 70 + "\n")
                f.write("HASHTAGS:\n")
                f.write("-" * 70 + "\n")
                if isinstance(hashtags, list):
                    f.write(" ".join(hashtags) + "\n\n")
                else:
                    f.write(f"{hashtags}\n\n")

            # Tags
            tags = youtube_seo.get('tags', [])
            if tags:
                f.write("-" * 70 + "\n")
                f.write("TAGS (copy to YouTube):\n")
                f.write("-" * 70 + "\n")
                if isinstance(tags, list):
                    f.write(", ".join(tags) + "\n\n")
                else:
                    f.write(f"{tags}\n\n")

    logger.info(f"Saved to: {prompt_file}")

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("THUMBNAIL GENERATION COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Generated {len(ideas)} ideas with prompts")
    logger.info(f"Output: {prompt_file}")
    logger.info("=" * 70)

    return True


def thumbnail_generator_quick(title_text: str, output_dir: Path, provider: str = "auto") -> bool:
    """Quick generate thumbnail ideas from direct title input (no project folder needed)

    Args:
        title_text: Video title or topic text directly entered by user
        output_dir: Output directory for thumbnail files
        provider: AI provider to use (auto, claude, openai, gemini)

    Returns:
        True if successful, False otherwise
    """

    logger.info("=" * 60)
    logger.info("THUMBNAIL GENERATOR - QUICK MODE")
    logger.info("=" * 60)
    logger.info(f"Title: {title_text}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"AI Provider: {provider}")
    logger.info("=" * 60)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate thumbnail ideas from title
    logger.info("\n" + "=" * 60)
    logger.info("Generating 10 Ideas from QUICK TITLE INPUT")
    logger.info(f"AI Provider: {provider}")
    logger.info("=" * 60)
    ideas_data = generate_thumbnail_ideas(title_text, provider=provider)

    ideas = ideas_data.get('ideas', [])
    if not ideas:
        logger.error("Failed to generate thumbnail ideas")
        return False

    logger.info(f"Generated {len(ideas)} ideas with prompts")

    # Save ONE txt file with ALL 10 ideas + prompts + TOP 3 MEGA-VIRAL PICKS
    prompt_file = output_dir / "thumbnail_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write("#" * 70 + "\n")
        f.write("#  THUMBNAIL IDEAS - QUICK GENERATE\n")
        f.write("#  Copy prompt to Nano Banana Pro / Midjourney / DALL-E\n")
        f.write("#" * 70 + "\n\n")

        # Video title
        f.write(f"VIDEO TITLE: {title_text}\n")
        if ideas_data.get('main_people'):
            f.write(f"MAIN PEOPLE: {', '.join(ideas_data.get('main_people', []))}\n")
        f.write("\n")

        # 10 OPTIONS WITH VIRALITY METRICS
        f.write("=" * 70 + "\n")
        f.write("  10 OPTIONS WITH VIRALITY METRICS\n")
        f.write("=" * 70 + "\n\n")

        for idea in ideas:
            f.write("-" * 70 + "\n")
            f.write(f"OPTION {idea.get('id', '?')}\n")
            f.write("-" * 70 + "\n")
            f.write(f"Thumbnail: \"{idea.get('thumbnail_text', 'N/A')}\"\n")
            f.write(f"Speaker: {idea.get('speaker', 'N/A')}\n")
            f.write(f"About: {idea.get('target', 'N/A')}\n")
            f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
            f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
            f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n")
            f.write(f"Layout: {idea.get('layout', 'N/A')}\n")
            f.write(f"Emotion: {idea.get('emotion', 'N/A')}\n")
            if idea.get('algorithm_boost_factors'):
                factors = idea.get('algorithm_boost_factors', [])
                if isinstance(factors, list):
                    f.write(f"Algorithm Boost: {', '.join(factors)}\n")
                else:
                    f.write(f"Algorithm Boost: {factors}\n")
            if idea.get('why_viral'):
                f.write(f"Why Viral: {idea.get('why_viral')}\n")
            f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")

        # TOP 3 MEGA-VIRAL PICKS section
        f.write("\n" + "=" * 70 + "\n")
        f.write("  TOP 3 MEGA-VIRAL PICKS\n")
        f.write("=" * 70 + "\n\n")

        # Check if AI provided top_3_picks with detailed breakdown
        top_3_picks = ideas_data.get('top_3_picks', {})
        pick_keys = ['nuclear_option_1', 'controversy_king_2', 'emotional_nuke_3']
        pick_names = ["NUCLEAR OPTION #1", "CONTROVERSY KING #2", "EMOTIONAL NUKE #3"]

        if top_3_picks:
            for i, key in enumerate(pick_keys):
                pick = top_3_picks.get(key, {})
                if not pick:
                    continue

                option_id = pick.get('option_id', '?')
                idea = next((x for x in ideas if x.get('id') == option_id), {})

                f.write("-" * 70 + "\n")
                f.write(f"{pick_names[i]}: Option {option_id}\n")
                f.write("-" * 70 + "\n")
                f.write(f"Thumbnail Text: \"{pick.get('thumbnail_text', idea.get('thumbnail_text', 'N/A'))}\"\n")
                f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
                f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n\n")
        else:
            # Fallback: show top 3 by CTR
            sorted_ideas = sorted(ideas, key=lambda x: int(x.get('ctr_potential', 0) or 0), reverse=True)[:3]
            for i, idea in enumerate(sorted_ideas):
                f.write("-" * 70 + "\n")
                f.write(f"{pick_names[i]}: Option {idea.get('id', '?')}\n")
                f.write("-" * 70 + "\n")
                f.write(f"Thumbnail Text: \"{idea.get('thumbnail_text', 'N/A')}\"\n")
                f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
                f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n\n")

        # YouTube SEO section
        youtube_seo = ideas_data.get('youtube_seo', {})
        if youtube_seo:
            f.write("\n" + "=" * 70 + "\n")
            f.write("  YOUTUBE SEO\n")
            f.write("=" * 70 + "\n\n")

            if youtube_seo.get('description'):
                f.write("DESCRIPTION:\n")
                f.write(youtube_seo.get('description', '') + "\n\n")

            if youtube_seo.get('hashtags'):
                hashtags = youtube_seo.get('hashtags', [])
                if isinstance(hashtags, list):
                    f.write(f"HASHTAGS: {' '.join(hashtags)}\n\n")

            if youtube_seo.get('tags'):
                tags = youtube_seo.get('tags', [])
                if isinstance(tags, list):
                    f.write(f"TAGS: {', '.join(tags)}\n")

    logger.info(f"Saved all ideas to: {prompt_file}")
    logger.info("=" * 70)
    logger.info("QUICK GENERATE COMPLETE")
    logger.info("=" * 70)

    return True


def thumbnail_generator_from_title(input_folder: Path, output_dir: Path = None, provider: str = "auto") -> bool:
    """Generate thumbnail ideas from video title (extracted from thumbnail filename)

    Args:
        input_folder: Input folder containing video + thumbnail_TITLE.jpg
        output_dir: Output directory for thumbnail files (default: same as input)
        provider: AI provider to use (auto, claude, openai, gemini)
    """

    # Default output to same folder
    if output_dir is None:
        output_dir = input_folder

    logger.info("=" * 60)
    logger.info("THUMBNAIL GENERATOR - TITLE MODE")
    logger.info("=" * 60)
    logger.info(f"Input: {input_folder}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"AI Provider: {provider}")
    logger.info("=" * 60)

    # Extract title from thumbnail filename
    video_title = extract_title_from_input_folder(input_folder)
    if not video_title:
        logger.error(f"No thumbnail with title found in {input_folder}")
        logger.error("Expected: thumbnail_VIDEO TITLE HERE.jpg")
        return False

    logger.info(f"Extracted title: '{video_title}'")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate thumbnail ideas from title (using unified function)
    logger.info("\n" + "=" * 60)
    logger.info("Generating 10 Ideas from VIDEO TITLE (ONE API call)")
    logger.info(f"AI Provider: {provider}")
    logger.info("=" * 60)
    ideas_data = generate_thumbnail_ideas(video_title, provider=provider)

    ideas = ideas_data.get('ideas', [])
    if not ideas:
        logger.error("Failed to generate thumbnail ideas")
        return False

    logger.info(f"Generated {len(ideas)} ideas with prompts")

    # Save ONE txt file with ALL 10 ideas + prompts + TOP 3 MEGA-VIRAL PICKS
    prompt_file = output_dir / "thumbnail_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write("#" * 70 + "\n")
        f.write("#  THUMBNAIL IDEAS - GENERATED FROM VIDEO TITLE\n")
        f.write("#  Copy prompt to Nano Banana Pro / Midjourney / DALL-E\n")
        f.write("#" * 70 + "\n\n")

        # Video title
        f.write(f"VIDEO TITLE: {video_title}\n")
        if ideas_data.get('main_people'):
            f.write(f"MAIN PEOPLE: {', '.join(ideas_data.get('main_people', []))}\n")
        f.write("\n")

        # 10 OPTIONS WITH VIRALITY METRICS
        f.write("=" * 70 + "\n")
        f.write("  10 OPTIONS WITH VIRALITY METRICS\n")
        f.write("=" * 70 + "\n\n")

        for idea in ideas:
            f.write("-" * 70 + "\n")
            f.write(f"OPTION {idea.get('id', '?')}\n")
            f.write("-" * 70 + "\n")
            f.write(f"Thumbnail: \"{idea.get('thumbnail_text', 'N/A')}\"\n")
            f.write(f"Speaker: {idea.get('speaker', 'N/A')}\n")
            f.write(f"About: {idea.get('target', 'N/A')}\n")
            f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
            f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
            f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n")
            f.write(f"Layout: {idea.get('layout', 'N/A')}\n")
            f.write(f"Emotion: {idea.get('emotion', 'N/A')}\n")
            if idea.get('algorithm_boost_factors'):
                factors = idea.get('algorithm_boost_factors', [])
                if isinstance(factors, list):
                    f.write(f"Algorithm Boost: {', '.join(factors)}\n")
                else:
                    f.write(f"Algorithm Boost: {factors}\n")
            if idea.get('why_viral'):
                f.write(f"Why Viral: {idea.get('why_viral')}\n")
            f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")

        # TOP 3 MEGA-VIRAL PICKS section
        f.write("\n" + "=" * 70 + "\n")
        f.write("  TOP 3 MEGA-VIRAL PICKS\n")
        f.write("=" * 70 + "\n\n")

        # Check if AI provided top_3_picks with detailed breakdown
        top_3_picks = ideas_data.get('top_3_picks', {})
        pick_keys = ['nuclear_option_1', 'controversy_king_2', 'emotional_nuke_3']
        pick_names = ["NUCLEAR OPTION #1", "CONTROVERSY KING #2", "EMOTIONAL NUKE #3"]

        if top_3_picks:
            for i, key in enumerate(pick_keys):
                pick = top_3_picks.get(key, {})
                if not pick:
                    continue

                option_id = pick.get('option_id', '?')
                idea = next((x for x in ideas if x.get('id') == option_id), {})

                f.write("-" * 70 + "\n")
                f.write(f"{pick_names[i]}: Option {option_id}\n")
                f.write("-" * 70 + "\n")
                f.write(f"Thumbnail Text: \"{pick.get('thumbnail_text', idea.get('thumbnail_text', 'N/A'))}\"\n")
                f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
                f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
                f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n\n")

                breakdown = pick.get('virality_breakdown', {})
                if breakdown:
                    f.write("Virality Breakdown:\n")
                    f.write(f"  - Shock Factor: {breakdown.get('shock_factor', 'N/A')}/10\n")
                    f.write(f"  - Drama Level: {breakdown.get('drama_level', 'N/A')}/10\n")
                    f.write(f"  - Urgency: {breakdown.get('urgency', 'N/A')}/10\n")
                    f.write(f"  - Controversy: {breakdown.get('controversy', 'N/A')}/10\n")
                    f.write(f"  - Share Potential: {breakdown.get('share_potential', 'N/A')}/10\n")

                if pick.get('why_mega_viral'):
                    f.write(f"\nWhy MEGA-VIRAL: {pick.get('why_mega_viral')}\n")

                visual = pick.get('visual_psychology', {})
                if visual:
                    f.write("\nVisual Psychology:\n")
                    f.write(f"  - Dominant Color: {visual.get('dominant_color', 'N/A')}\n")
                    f.write(f"  - Face Expression: {visual.get('face_expression', 'N/A')}\n")
                    f.write(f"  - Composition: {visual.get('composition', 'N/A')}\n")

                f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")
        else:
            # Fallback: Sort by CTR and virality to get top 3
            sorted_ideas = sorted(ideas, key=lambda x: (x.get('ctr_potential', 0), x.get('virality_score', 0)), reverse=True)
            top_3 = sorted_ideas[:3]

            for i, idea in enumerate(top_3):
                f.write("-" * 70 + "\n")
                f.write(f"{pick_names[i]}: Option {idea.get('id', '?')}\n")
                f.write("-" * 70 + "\n")
                f.write(f"Thumbnail Text: \"{idea.get('thumbnail_text', 'N/A')}\"\n")
                f.write(f"Title: {idea.get('viral_title', 'N/A')}\n")
                f.write(f"CTR Potential: {idea.get('ctr_potential', 'N/A')}%\n")
                f.write(f"Virality Score: {idea.get('virality_score', 'N/A')}/10\n\n")
                f.write(f"\nimage_prompt:\n{idea.get('image_prompt', 'No prompt generated')}\n\n")

        # YOUTUBE SEO SECTION
        youtube_seo = ideas_data.get('youtube_seo', {})
        if youtube_seo:
            f.write("\n" + "=" * 70 + "\n")
            f.write("  YOUTUBE SEO - DESCRIPTION, HASHTAGS & TAGS\n")
            f.write("=" * 70 + "\n\n")

            # Description
            description = youtube_seo.get('description', '')
            if description:
                f.write("-" * 70 + "\n")
                f.write("DESCRIPTION (copy to YouTube):\n")
                f.write("-" * 70 + "\n")
                f.write(f"{description}\n\n")

            # Hashtags
            hashtags = youtube_seo.get('hashtags', [])
            if hashtags:
                f.write("-" * 70 + "\n")
                f.write("HASHTAGS:\n")
                f.write("-" * 70 + "\n")
                if isinstance(hashtags, list):
                    f.write(" ".join(hashtags) + "\n\n")
                else:
                    f.write(f"{hashtags}\n\n")

            # Tags
            tags = youtube_seo.get('tags', [])
            if tags:
                f.write("-" * 70 + "\n")
                f.write("TAGS (copy to YouTube):\n")
                f.write("-" * 70 + "\n")
                if isinstance(tags, list):
                    f.write(", ".join(tags) + "\n\n")
                else:
                    f.write(f"{tags}\n\n")

    logger.info(f"Saved to: {prompt_file}")

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("THUMBNAIL GENERATION COMPLETE! (TITLE MODE)")
    logger.info("=" * 70)
    logger.info(f"Title: {video_title}")
    logger.info(f"Generated {len(ideas)} ideas with prompts")
    logger.info(f"Output: {prompt_file}")
    logger.info("=" * 70)

    return True


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Generate viral thumbnail ideas and prompts')
    parser.add_argument('--project-dir', '-p', type=str, default=None,
                        help='Project directory or input folder (for title mode)')
    parser.add_argument('--output-dir', '-o', type=str, default=None,
                        help='Output directory for thumbnail files (default: 8_youtube_upload in project)')
    parser.add_argument('--manual', '-m', action='store_true',
                        help='Manual selection mode (don\'t auto-pick)')
    parser.add_argument('--mode', type=str, default='script', choices=['script', 'title', 'quick'],
                        help='Mode: "script" (read script content), "title" (extract from thumbnail filename), or "quick" (direct title input)')
    parser.add_argument('--provider', type=str, default='auto', choices=['auto', 'claude', 'openai', 'chatgpt', 'gemini', 'google'],
                        help='AI provider: auto, claude, openai/chatgpt, gemini/google')
    parser.add_argument('--title', '-t', type=str, default=None,
                        help='Direct title input for quick mode (no project directory needed)')

    args = parser.parse_args()

    # Get AI provider
    ai_provider = args.provider

    # Quick mode: generate from direct title input
    if args.title:
        output_path = Path(args.output_dir) if args.output_dir else Path.cwd()
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Quick mode: Generating thumbnails for title: {args.title}")
        success = thumbnail_generator_quick(
            title_text=args.title,
            output_dir=output_path,
            provider=ai_provider
        )
        sys.exit(0 if success else 1)

    # For other modes, project_dir is required
    if not args.project_dir:
        logger.error("--project-dir is required (or use --title for quick mode)")
        sys.exit(1)

    project_path = Path(args.project_dir)
    if not project_path.exists():
        logger.error(f"Directory not found: {project_path}")
        sys.exit(1)

    # Title mode: extract title from thumbnail filename
    if args.mode == 'title':
        output_path = Path(args.output_dir) if args.output_dir else project_path
        success = thumbnail_generator_from_title(
            input_folder=project_path,
            output_dir=output_path,
            provider=ai_provider
        )
    else:
        # Script mode: read script content (default)
        output_path = Path(args.output_dir) if args.output_dir else project_path / "8_youtube_upload"
        success = thumbnail_generator_step(
            project_dir=project_path,
            output_dir=output_path,
            auto_select=not args.manual,
            provider=ai_provider
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
