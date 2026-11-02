@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ACCEPT_V17_FINAL.ps1"
exit /b %ERRORLEVEL%
