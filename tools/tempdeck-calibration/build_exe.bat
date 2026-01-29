@echo off
echo ========================================
echo  Building Temperature Module Calibration Tool
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install pyserial qrcode pillow pyinstaller

echo.
echo [2/3] Building executable...
pyinstaller --onefile --windowed --name "TempDeck_Calibration_Tool" tempdeck_calibration_tool.py

echo.
echo [3/3] Cleaning up...
rmdir /s /q build 2>nul
del /q *.spec 2>nul

echo.
echo ========================================
echo  BUILD COMPLETE!
echo ========================================
echo.
echo Your executable is ready at:
echo   dist\TempDeck_Calibration_Tool.exe
echo.
echo You can distribute this single .exe file.
echo No installation required on target computers.
echo.
pause
