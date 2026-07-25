@echo off
title ESENCIA X - MCP Installer

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python is not installed.
    echo     Download it from https://python.org
    echo     Check "Add Python to PATH" when installing.
    pause
    exit /b
)

python "%~dp0install.py"
pause
