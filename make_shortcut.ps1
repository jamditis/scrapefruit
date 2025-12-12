$ScrapePath = "C:\Users\amdit\OneDrive\Desktop\Crimes\playground\scrapefruit"
$PythonPath = "$ScrapePath\venv\Scripts\pythonw.exe"
$MainScript = "$ScrapePath\main.py"

$WshShell = New-Object -ComObject WScript.Shell

# Start Menu shortcut
$StartMenuLnk = "C:\Users\amdit\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Scrapefruit.lnk"
$Shortcut = $WshShell.CreateShortcut($StartMenuLnk)
$Shortcut.TargetPath = $PythonPath
$Shortcut.Arguments = "`"$MainScript`""
$Shortcut.WorkingDirectory = $ScrapePath
$Shortcut.Description = "Scrapefruit"
$Shortcut.Save()
Write-Host "Created: $StartMenuLnk"

# Desktop shortcut
$DesktopLnk = "C:\Users\amdit\OneDrive\Desktop\Scrapefruit.lnk"
$Shortcut2 = $WshShell.CreateShortcut($DesktopLnk)
$Shortcut2.TargetPath = $PythonPath
$Shortcut2.Arguments = "`"$MainScript`""
$Shortcut2.WorkingDirectory = $ScrapePath
$Shortcut2.Description = "Scrapefruit"
$Shortcut2.Save()
Write-Host "Created: $DesktopLnk"
