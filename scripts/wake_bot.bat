@echo off
REM Wake bot via GitHub repository dispatch

set REPO=suraganovzh/coreelement-grants-hunter

if "%GITHUB_TOKEN%"=="" (
    echo Error: GITHUB_TOKEN not set
    echo Create token at: https://github.com/settings/tokens
    echo Required scope: repo
    echo.
    echo Usage:
    echo   set GITHUB_TOKEN=your_token_here
    echo   scripts\wake_bot.bat
    exit /b 1
)

echo Sending wake signal to bot...

curl -s -X POST ^
  -H "Authorization: token %GITHUB_TOKEN%" ^
  -H "Accept: application/vnd.github.v3+json" ^
  https://api.github.com/repos/%REPO%/dispatches ^
  -d "{\"event_type\":\"wake_bot\"}"

if %errorlevel% equ 0 (
    echo Wake signal sent successfully
    echo Check Telegram for confirmation
) else (
    echo Failed to send wake signal
    exit /b 1
)
