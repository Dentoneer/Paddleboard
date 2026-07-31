@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON=python"
set "SCRIPT=%SCRIPT_DIR%fetch_river_data.py"
set "DASHBOARD=%SCRIPT_DIR%dashboard.html"

echo ============================================================
echo  Paddleboard Conditions — Elm Fork below Lake Ray Roberts
echo ============================================================
echo.

:: Fetch fresh data and regenerate dashboard
%PYTHON% "%SCRIPT%"
if errorlevel 1 (
    echo.
    echo ERROR: Failed to fetch river data. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo Opening dashboard in browser...
start "" "%DASHBOARD%"

endlocal
