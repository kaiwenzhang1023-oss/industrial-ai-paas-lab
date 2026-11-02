@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ACCEPT_V18_PHASE4.ps1"
exit /b %ERRORLEVEL%
