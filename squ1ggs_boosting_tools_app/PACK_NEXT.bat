@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo Squ1ggs Boosting Tools - FIRST RELEASE ONLY
echo Checks source, bumps EXE and mod versions, then builds locally.
echo Close the previous test EXE before building.
echo.

where node >nul 2>&1
if errorlevel 1 goto missing_node
where npm >nul 2>&1
if errorlevel 1 goto missing_npm
where python >nul 2>&1
if errorlevel 1 goto missing_python
if not exist "release_bundle_hashes.json" goto wrong_folder
if not exist "tools\refresh_release_hashes.py" goto wrong_folder

echo [1/5] Checking JavaScript...
call npm run check
if errorlevel 1 goto failed
echo.
echo [2/5] Verifying reviewed first-release mod files...
python sync_sdkmod.py
if errorlevel 1 goto failed
if /i "%~1"=="--check-only" (
  echo Checks passed. Versions unchanged; no EXE built.
  exit /b 0
)
echo.
echo [3/5] Bumping EXE and mod versions...
node "scripts\bump_version.cjs" "Local first-release test build."
if errorlevel 1 goto failed
echo.
echo [4/5] Updating reviewed hashes after version bump...
python "tools\refresh_release_hashes.py"
if errorlevel 1 goto failed
echo.
echo [5/5] Building and checking the portable EXE. This takes a few minutes...
call npm run pack
if errorlevel 1 goto failed

set "EXE="
for /f "usebackq delims=" %%A in (`node -e "const p=require('./package.json'); console.log(require('path').resolve(p.build.directories.output,'win-unpacked','Squ1ggsBoostingTools.exe'))"`) do set "EXE=%%A"
if not defined EXE goto failed
if not exist "%EXE%" goto failed
echo.
echo BUILD COMPLETE
echo EXE: %EXE%
echo Restart Borderlands 4 after installing the bundled mod.
explorer /select,"%EXE%"
pause
exit /b 0

:missing_node
echo ERROR: Node.js is not available on PATH.
goto failed
:missing_npm
echo ERROR: npm is not available on PATH.
goto failed
:missing_python
echo ERROR: Python is not available on PATH.
goto failed
:wrong_folder
echo ERROR: This script must run from the first-release source folder.
goto failed
:failed
echo.
echo BUILD FAILED. Read the error above. No upload or publication was performed.
echo If a file is locked, close the old EXE and retry.
if /i not "%~1"=="--check-only" pause
exit /b 1
