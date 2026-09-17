@echo off
REM Bat ERP LiFeOOD tren laptop. Can mo Docker Desktop truoc (Engine running).
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker chua chay. Mo Docker Desktop, doi "Engine running" roi chay lai file nay.
  pause
  exit /b 1
)
docker compose up -d
echo Dang khoi dong Odoo...
timeout /t 8 /nobreak >nul
start "" "http://localhost:8069/web/login?db=lfood"
echo Da mo trinh duyet: http://localhost:8069
echo Tat app: docker compose down   (du lieu van giu nguyen)
pause
