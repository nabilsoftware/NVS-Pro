"""
Nabil Video Studio Pro - Launcher
Proper .exe launcher for taskbar pinning.
"""
import sys
import os
import subprocess
import ctypes

def main():
    # Set Windows AppUserModelID for taskbar pinning
    try:
        myappid = 'NabilSoftware.NVSPro.VideoStudio.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except:
        pass

    # Get the directory where this exe is located
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Paths
    pythonw_exe = os.path.join(app_dir, 'python', 'pythonw.exe')
    python_exe = os.path.join(app_dir, 'python', 'python.exe')
    main_script = os.path.join(app_dir, 'ui_modern.py')

    # Use pythonw (no console) if available
    if os.path.exists(pythonw_exe):
        python = pythonw_exe
    elif os.path.exists(python_exe):
        python = python_exe
    else:
        ctypes.windll.user32.MessageBoxW(0, "Python not found!", "Error", 0x10)
        return 1

    if not os.path.exists(main_script):
        ctypes.windll.user32.MessageBoxW(0, "ui_modern.py not found!", "Error", 0x10)
        return 1

    # Launch and WAIT for it to finish
    # This keeps the launcher process alive so taskbar icon stays correct
    os.chdir(app_dir)

    try:
        # Use Popen and wait - this keeps OUR process as the "main" one
        process = subprocess.Popen(
            [python, main_script],
            cwd=app_dir
        )
        # Wait for the app to close
        process.wait()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Launch Error", 0x10)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
