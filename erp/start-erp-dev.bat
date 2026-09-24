@echo off
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker chua chay. Mo Docker Desktop, doi "Engine running" roi chay lai file nay.
  pause
  exit /b 1
)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
echo Dang khoi dong Odoo o che do sua app...
timeout /t 8 /nobreak >nul
start "" "http://localhost:8069/web/login?db=lfood"
echo Da mo trinh duyet: http://localhost:8069
echo Sua XML xong: F5 la thay. Sua Python: docker compose restart odoo
echo Ve che do chay that: start-erp.bat
pause
