@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ACCEPT_V18_PHASE2.ps1"
exit /b %ERRORLEVEL%
