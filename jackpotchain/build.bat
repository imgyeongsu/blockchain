@echo off
echo ========================================
echo JackpotChain Build Script
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] PyInstaller: Python → EXE
call .venv\Scripts\activate
pyinstaller jackpotchain.spec --clean
if errorlevel 1 (
    echo PyInstaller failed!
    pause
    exit /b 1
)
echo.

echo [2/2] Inno Setup: EXE → Installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if errorlevel 1 (
    echo Inno Setup failed!
    pause
    exit /b 1
)
echo.

echo ========================================
echo Build Complete!
echo Output: installer_output\JackpotChain-Setup-1.0.0.exe
echo ========================================
pause
