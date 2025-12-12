@echo off
echo Creating Scrapefruit shortcuts...
powershell -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
echo.
echo Done! Press any key to exit.
pause >nul
