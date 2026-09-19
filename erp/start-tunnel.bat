@echo off
REM Mo ERP LiFeOOD ra Internet qua Microsoft Dev Tunnels (link HTTPS co dinh).
REM Dong cua so nay la tat link; app tren may van chay.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-tunnel.ps1"
pause
