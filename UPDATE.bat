@echo off
title ESENCIA X - Updater

echo.
echo    =========================================
echo       ESENCIA X - MCP Updater
echo    =========================================
echo.

set "URL=https://raw.githubusercontent.com/Jairoxdhola/ESENCIA-X/main"

echo Downloading latest...
powershell -Command "Invoke-WebRequest '%URL%/update.py' -OutFile '%~dp0update.py'; Unblock-File '%~dp0update.py'" 2>nul

python "%~dp0update.py"
exit /b 0
