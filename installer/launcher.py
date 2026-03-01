"""
Nabil Video Studio Pro - Launcher
Compiles to NVS_Pro.exe
"""
import os
import sys
import subprocess
import ctypes
from pathlib import Path

def main():
    # Set Windows AppUserModelID (for taskbar icon)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NabilSoftware.NVSPro')
    except:
        pass

    # Get the directory where this exe is located
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        app_dir = Path(sys.executable).parent
    else:
        # Running as script
        app_dir = Path(__file__).parent

    os.chdir(app_dir)

    python_exe = app_dir / "python" / "pythonw.exe"
    python_console = app_dir / "python" / "python.exe"
    setup_flag = app_dir / "setup_complete.flag"
    first_run_setup = app_dir / "first_run_setup.py"
    ui_script = app_dir / "ui_modern.py"

    # Check if first run setup is needed
    if not setup_flag.exists():
        # Quick check: if site-packages has torch, packages are likely installed
        # This handles cases where setup completed but flag wasn't created
        site_packages = app_dir / "python" / "Lib" / "site-packages"
        torch_dir = site_packages / "torch"
        if torch_dir.exists():
            # Packages already installed, create the flag and skip setup
            try:
                with open(setup_flag, 'w') as f:
                    f.write(f"Setup skipped - packages already present\n")
            except:
                pass
        elif first_run_setup.exists() and python_console.exists():
            # Run first time setup with console visible
            subprocess.run([str(python_console), str(first_run_setup)])

    # Launch main application and WAIT for it (keeps this process as the parent)
    if ui_script.exists() and python_exe.exists():
        # Use subprocess.call to wait - this keeps NVS_Pro.exe as the taskbar process
        subprocess.call([str(python_exe), str(ui_script)])

if __name__ == "__main__":
    main()
