Set WshShell = CreateObject("WScript.Shell")
Set shortcut = WshShell.CreateShortcut(WScript.Arguments(0))
shortcut.TargetPath = WScript.Arguments(1)
shortcut.IconLocation = WScript.Arguments(2)
shortcut.WorkingDirectory = WScript.Arguments(3)
shortcut.Save
