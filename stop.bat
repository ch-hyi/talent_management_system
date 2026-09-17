@echo off
chcp 65001 >nul
setlocal EnableExtensions




for %%I in ("%~dp0.") do set "TALENT_SYSTEM=%%~fI"

set "START_BAT=%~f0"
set "ENV_FILE=%TALENT_SYSTEM%\.env"



if not exist "%ENV_FILE%" (
    echo [錯誤] 找不到 .env：
    echo %ENV_FILE%
    echo.
    pause
    exit /b 1
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if not "%%A"=="" set "%%A=%%B"
)



if /I "%~1"=="__talent_service__" goto RUN_SERVICE



title Talent System Start Tool

echo ========================================
echo Talent System Start Tool
echo ========================================
echo.
echo 專案根目錄：
echo %TALENT_SYSTEM%
echo.



if not exist "%TALENT_SYSTEM%\backend" (
    echo [錯誤] 找不到 backend 資料夾：
    echo %TALENT_SYSTEM%\backend
    echo.
    echo 請確認 start.bat 位於 talent_system 根目錄。
    pause
    exit /b 1
)

if not exist "%TALENT_SYSTEM%\frontend\ui.py" (
    echo [錯誤] 找不到 Streamlit 入口：
    echo %TALENT_SYSTEM%\frontend\ui.py
    echo.
    pause
    exit /b 1
)



if not defined REDIS_EXE (
    echo [錯誤] .env 中沒有設定 REDIS_EXE
    echo.
    echo 請在 .env 中加入：
    echo REDIS_EXE=C:\Redis\redis-server.exe
    echo.
    pause
    exit /b 1
)

if not exist "%REDIS_EXE%" (
    echo [錯誤] 找不到 Redis 執行檔：
    echo %REDIS_EXE%
    echo.
    echo 請檢查 .env 中的 REDIS_EXE。
    pause
    exit /b 1
)

echo Redis 執行檔：
echo %REDIS_EXE%
echo.



echo ========================================
echo 正在停止上一輪服務...
echo ========================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$processes = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*__talent_service__*' }; if (-not $processes) { Write-Host '沒有找到上一輪服務。' }; foreach ($process in $processes) { Write-Host ('停止服務 PID：' + $process.ProcessId); taskkill.exe /PID $process.ProcessId /T /F | Out-Null }"

echo.
echo 等待服務完全停止...
timeout /t 3 /nobreak >nul



taskkill /F /T /IM redis-server.exe >nul 2>&1
taskkill /F /T /IM ollama.exe >nul 2>&1



timeout /t 2 /nobreak >nul
