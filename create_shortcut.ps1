# Create Start Menu shortcut for Scrapefruit
# Run this script as: powershell -ExecutionPolicy Bypass -File create_shortcut.ps1

$ScrapePath = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ScrapePath ".venv\Scripts\pythonw.exe"
$MainScript = Join-Path $ScrapePath "main.py"
$IconPath = Join-Path $ScrapePath "static\favicon.ico"

# Start Menu location
$StartMenuPath = [Environment]::GetFolderPath("StartMenu")
$ShortcutPath = Join-Path $StartMenuPath "Programs\Scrapefruit.lnk"

# Create the shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonPath
$Shortcut.Arguments = "`"$MainScript`""
$Shortcut.WorkingDirectory = $ScrapePath
$Shortcut.Description = "Scrapefruit - Desktop scraping platform"
$Shortcut.WindowStyle = 1  # Normal window

# Use icon if it exists
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}

$Shortcut.Save()

Write-Host "Shortcut created at: $ShortcutPath" -ForegroundColor Green
Write-Host "You can now find 'Scrapefruit' in your Start Menu!" -ForegroundColor Cyan

# Also create a desktop shortcut
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = Join-Path $DesktopPath "Scrapefruit.lnk"

$Shortcut2 = $WshShell.CreateShortcut($DesktopShortcut)
$Shortcut2.TargetPath = $PythonPath
$Shortcut2.Arguments = "`"$MainScript`""
$Shortcut2.WorkingDirectory = $ScrapePath
$Shortcut2.Description = "Scrapefruit - Desktop scraping platform"
$Shortcut2.WindowStyle = 1

if (Test-Path $IconPath) {
    $Shortcut2.IconLocation = $IconPath
}

$Shortcut2.Save()

Write-Host "Desktop shortcut also created!" -ForegroundColor Green
