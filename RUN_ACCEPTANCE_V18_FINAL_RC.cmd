@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ACCEPT_V18_FINAL_RC.ps1"
exit /b %ERRORLEVEL%
