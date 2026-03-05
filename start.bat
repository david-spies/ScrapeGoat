@echo off
:: ScrapeGoat — Windows startup script
:: Usage: double-click start.bat  OR  run from cmd

echo.
echo   ScrapeGoat v2.1 - startup
echo   --------------------------

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: Python not found. Install from https://python.org
    pause & exit /b 1
)

echo   Installing Python dependencies...
python -m pip install -r requirements.txt --quiet

echo   Checking Playwright Chromium...
python -m playwright install chromium

echo.
echo   Starting backend on http://localhost:7331
echo   Open http://localhost:7331 in your browser
echo.
python server.py
pause
