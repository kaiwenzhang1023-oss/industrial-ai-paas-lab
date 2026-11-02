@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ACCEPT_V18_PHASE1.ps1"
exit /b %ERRORLEVEL%
