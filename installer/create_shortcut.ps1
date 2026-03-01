# Create shortcut with AppUserModelID for proper taskbar pinning
param(
    [string]$AppDir = $PSScriptRoot
)

$AppDir = (Get-Item $AppDir).Parent.FullName
$PythonW = Join-Path $AppDir "python\pythonw.exe"
$MainScript = Join-Path $AppDir "ui_modern.py"
$IconPath = Join-Path $AppDir "assets\logo.ico"
$ShortcutPath = [System.IO.Path]::Combine([Environment]::GetFolderPath("Desktop"), "Nabil Video Studio Pro.lnk")
$StartMenuPath = [System.IO.Path]::Combine([Environment]::GetFolderPath("StartMenu"), "Programs", "Nabil Video Studio Pro.lnk")

$AppUserModelID = "NabilSoftware.NVSPro.VideoStudio.1"

# Create WScript.Shell shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$MainScript`""
$Shortcut.WorkingDirectory = $AppDir
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Nabil Video Studio Pro"
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"

# Set AppUserModelID using Shell COM
$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace([System.IO.Path]::GetDirectoryName($ShortcutPath))
$item = $folder.ParseName([System.IO.Path]::GetFileName($ShortcutPath))

# Unfortunately PowerShell can't easily set AppUserModelID on shortcuts
# The proper way is through IPropertyStore which requires C++ or special tools

Write-Host "Shortcut created. To pin to taskbar:"
Write-Host "1. Right-click the shortcut"
Write-Host "2. Select 'Pin to taskbar'"
