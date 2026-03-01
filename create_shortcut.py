"""
Create proper Windows shortcut with AppUserModelID
This allows the shortcut to be pinned to taskbar correctly
"""
import os
import sys
import winreg

def create_shortcut():
    """Create a proper shortcut that can be pinned"""
    try:
        import win32com.client
        from win32com.propsys import propsys, pscon
        import pythoncom
    except ImportError:
        print("Installing pywin32...")
        os.system(f'"{sys.executable}" -m pip install pywin32')
        import win32com.client
        from win32com.propsys import propsys, pscon
        import pythoncom

    # Get app directory
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Paths
    pythonw = os.path.join(app_dir, 'python', 'pythonw.exe')
    main_script = os.path.join(app_dir, 'ui_modern.py')
    icon_path = os.path.join(app_dir, 'assets', 'logo.ico')

    # Shortcut location (Desktop)
    desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    shortcut_path = os.path.join(desktop, 'NVS Pro.lnk')

    # Create shortcut
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = pythonw
    shortcut.Arguments = f'"{main_script}"'
    shortcut.WorkingDirectory = app_dir
    shortcut.IconLocation = icon_path
    shortcut.Description = "Nabil Video Studio Pro"
    shortcut.save()

    # Now set the AppUserModelID using IPropertyStore
    # This is the KEY for taskbar pinning!
    store = propsys.SHGetPropertyStoreFromParsingName(
        shortcut_path,
        None,
        pscon.GPS_READWRITE,
        propsys.IID_IPropertyStore
    )

    app_id = "NabilSoftware.NVSPro.VideoStudio.1"
    store.SetValue(
        pscon.PKEY_AppUserModel_ID,
        propsys.PROPVARIANTType(app_id)
    )
    store.Commit()

    print(f"Created shortcut: {shortcut_path}")
    print(f"AppUserModelID: {app_id}")
    print("\nYou can now pin this shortcut to the taskbar!")

if __name__ == "__main__":
    create_shortcut()
