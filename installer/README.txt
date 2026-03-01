============================================================
NABIL VIDEO STUDIO PRO - INSTALLER BUILD GUIDE
============================================================

HOW TO BUILD THE INSTALLER:
---------------------------

1. Download and install Inno Setup from:
   https://jrsoftware.org/isdl.php

2. Open "NVS_Pro_Setup.iss" in Inno Setup Compiler

3. Click Build > Compile (or press Ctrl+F9)

4. The installer will be created in:
   installer_output\NVS_Pro_v1.2.0_Setup.exe


WHAT THE INSTALLER INCLUDES:
----------------------------
- Embedded Python 3.12
- All Python scripts (.py files)
- PyQt5 and qtawesome (pre-bundled)
- Assets, prompts, and config files
- First Run Setup script (downloads AI packages)


WHAT GETS DOWNLOADED ON FIRST RUN:
----------------------------------
The first_run_setup.py will download (~3-4 GB):
- PyTorch with CUDA support
- Pyannote (speaker diarization)
- Whisper (speech recognition)
- Demucs (audio separation)
- OpenCV, MoviePy (video processing)
- Google Gemini, Anthropic Claude APIs
- Selenium, Playwright (browser automation)
- And other dependencies


OPTIONAL: ADD AN ICON
---------------------
1. Create or get an .ico file (256x256 recommended)
2. Save it as: assets\icon.ico
3. Uncomment the SetupIconFile lines in NVS_Pro_Setup.iss


FILES IN THIS FOLDER:
---------------------
- NVS_Pro_Setup.iss  = Inno Setup script
- NVS_Pro.bat        = App launcher (checks for first run)
- README.txt         = This file


TROUBLESHOOTING:
----------------
If build fails:
1. Check that MySourceDir path is correct in .iss file
2. Make sure all referenced folders exist
3. Run Inno Setup as Administrator if needed

============================================================
