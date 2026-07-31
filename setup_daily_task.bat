@echo off
:: Sets up a Windows Task Scheduler job to fetch river data daily at 7 AM
:: and open the dashboard. Run this once as Administrator (or it will prompt).

setlocal
set "SCRIPT_DIR=%~dp0"
set "TASK_NAME=PaddleboardRiverConditions"
set "PYTHON=python"
set "SCRIPT=%SCRIPT_DIR%fetch_river_data.py"
set "DASHBOARD=%SCRIPT_DIR%dashboard.html"

echo Creating scheduled task: %TASK_NAME%
echo Runs daily at 7:00 AM — fetches USGS data and opens the dashboard.
echo.

:: Delete old task if it exists
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create the task:
::   - Trigger: daily at 07:00
::   - Action 1: run fetch_river_data.py
::   - The dashboard opens automatically after fetch
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%SCRIPT%\"" ^
  /sc DAILY ^
  /st 07:00 ^
  /rl HIGHEST ^
  /f

if errorlevel 1 (
    echo.
    echo FAILED to create scheduled task.
    echo Try right-clicking this file and selecting "Run as administrator".
    pause
    exit /b 1
)

echo.
echo Success! The task "%TASK_NAME%" will run daily at 7:00 AM.
echo You can also run it manually with:
echo   schtasks /run /tn "%TASK_NAME%"
echo.
echo To open the dashboard manually, double-click open_widget.bat
echo.
pause
endlocal
