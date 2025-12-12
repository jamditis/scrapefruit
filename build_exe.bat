@echo off
echo Building Scrapefruit EXE...
echo.

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install PyInstaller if not present
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Build the EXE
echo.
echo Running PyInstaller...
pyinstaller --clean scrapefruit.spec

echo.
if exist "dist\Scrapefruit.exe" (
    echo SUCCESS: Scrapefruit.exe created in dist\ folder!
    echo.
    echo Note: Playwright browsers are NOT bundled in the EXE.
    echo Users will need to run: playwright install chromium
    echo Or you can copy the browsers folder manually.
) else (
    echo Build failed. Check the output above for errors.
)

echo.
pause
