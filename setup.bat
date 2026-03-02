@echo off
setlocal enabledelayedexpansion

title Arabesque to 3D - Maya Plugin Installer
color 0F

echo.
echo  ============================================
echo     Arabesque to 3D  -  Maya Plugin Setup
echo  ============================================
echo.
echo  This will install the plugin for Autodesk Maya.
echo  Please make sure Maya is CLOSED before continuing.
echo.
pause

:: -----------------------------------------------
:: 1. Locate mayapy
:: -----------------------------------------------
set "MAYAPY="

for %%V in (2025 2024 2023) do (
    if exist "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" (
        set "MAYAPY=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
        set "MAYA_VER=%%V"
        goto :found_maya
    )
)

echo.
echo  [ERROR] Could not find Maya 2023, 2024, or 2025.
echo  Make sure Autodesk Maya is installed in the default location.
echo.
pause
exit /b 1

:found_maya
echo.
echo  [OK] Found Maya %MAYA_VER%
echo       %MAYAPY%
echo.

:: -----------------------------------------------
:: 2. Install Python packages (OpenCV + numpy)
:: -----------------------------------------------
echo  Installing required Python packages...
echo.
"%MAYAPY%" -m pip install --user opencv-python-headless numpy 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Package installation failed.
    echo  Try running this file as Administrator.
    echo.
    pause
    exit /b 1
)
echo.
echo  [OK] Python packages installed.
echo.

:: -----------------------------------------------
:: 3. Create Maya modules folder if needed
:: -----------------------------------------------
set "MODULES_DIR=%USERPROFILE%\Documents\maya\%MAYA_VER%\modules"
if not exist "%MODULES_DIR%" (
    mkdir "%MODULES_DIR%"
    echo  [OK] Created modules folder: %MODULES_DIR%
) else (
    echo  [OK] Modules folder exists: %MODULES_DIR%
)

:: -----------------------------------------------
:: 4. Write the .mod file pointing to this folder
:: -----------------------------------------------
set "PLUGIN_DIR=%~dp0"
:: Remove trailing backslash
if "%PLUGIN_DIR:~-1%"=="\" set "PLUGIN_DIR=%PLUGIN_DIR:~0,-1%"

(
    echo + Arabesque 1.0 %PLUGIN_DIR%
) > "%MODULES_DIR%\arabesque.mod"

echo  [OK] Module file created: %MODULES_DIR%\arabesque.mod
echo.

:: -----------------------------------------------
:: 5. Done
:: -----------------------------------------------
echo  ============================================
echo     Installation complete!
echo  ============================================
echo.
echo  Next steps:
echo.
echo    1. Open Maya %MAYA_VER%
echo    2. Go to: Windows ^> Settings/Preferences ^> Plugin Manager
echo    3. Find "arabesque_to_3d.py" and check "Loaded"
echo       (also check "Auto-load" so it loads every time)
echo    4. A new "Arabesque" menu will appear in the menu bar
echo.
echo  That's it! You can now use Arabesque ^> Arabesque to 3D Model
echo.
pause
