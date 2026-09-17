@echo off
REM Mo app ERP ra Internet cho sep test (CMD).
REM Lan dau chi 1 lan:  devtunnel user login
REM Sau do: bam dup file nay, hoac chay tu cmd.
REM Giu cua so nay mo trong suot luc sep test. Ctrl+C de tat.

setlocal
cd /d "%~dp0"

set "PY=C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe"
set "PORT=5199"
set "ERP_USER=lfood"
set /p ERP_PASS=<.demo-password.txt

echo Dang kiem tra dang nhap devtunnel...
devtunnel user show 2>&1 | findstr /i "expired logged" >nul
if not errorlevel 1 (
  echo.
  echo  Chua dang nhap. Chay lenh nay truoc, roi mo lai file nay:
  echo.
  echo      devtunnel user login
  echo.
  pause
  exit /b 1
)

REM don cong cu neu con ket
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>&1

echo Dang bat server...
start "ERP server" /min "%PY%" serve.py %PORT%
timeout /t 2 /nobreak >nul

echo.
echo =====================================================
echo   Gui cho sep: link ben duoi + tai khoan dang nhap
echo     Tai khoan : %ERP_USER%
echo     Mat khau  : %ERP_PASS%
echo =====================================================
echo.

devtunnel host -p %PORT% --allow-anonymous
