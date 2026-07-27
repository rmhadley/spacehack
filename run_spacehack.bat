@echo off
title Spacehack
python "%~dp0\run.py"
if errorlevel 1 (
    echo.
    echo Failed to launch. Make sure Python 3.10+ is installed.
    pause
)
