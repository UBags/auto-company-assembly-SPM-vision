@echo off
echo ============================================
echo Compiling MainProgram.py with Nuitka
echo ============================================
echo Started: %date% %time%

REM Clean previous build
if exist MainProgram.dist rmdir /s /q MainProgram.dist
if exist MainProgram.build rmdir /s /q MainProgram.build

REM Compile with Nuitka
nuitka --standalone ^
    --follow-imports ^
    --assume-yes-for-downloads ^
    --remove-output ^
    --force-dll-dependency-cache-update ^
    --enable-plugin=numpy ^
    --enable-plugin=torch ^
    --include-module=psycopg2._psycopg ^
    --include-package=psycopg2 ^
    --enable-plugin=tk-inter ^
    --enable-plugin=pyside6 ^
    --include-data-dir=wavs=wavs ^
    --include-data-dir=internalimages=internalimages ^
    --windows-console-mode=attach ^
    --include-package=cv2 ^
    --include-package=torch ^
    --include-package=torchvision ^
    --include-package=ultralytics ^
    --include-package=sklearn.externals ^
    MainProgram.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo Copying sklearn data files...
    echo ============================================
    robocopy ".venv\lib\site-packages\sklearn" "MainProgram.dist\sklearn" *.css *.json *.txt *.rst /S
    echo.
    echo ============================================
    echo SUCCESS! Executable created at:
    echo MainProgram.dist\MainProgram.exe
    echo ============================================
) else (
    echo.
    echo ============================================
    echo ERROR! Compilation failed.
    echo ============================================
)

echo Ended: %date% %time%
pause