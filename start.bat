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
echo Stop Active Services
echo ========================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$processes = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*__talent_service__*' }; if (-not $processes) { Write-Host '沒有找到上一輪服務。' }; foreach ($process in $processes) { Write-Host ('停止服務 PID：' + $process.ProcessId); taskkill.exe /PID $process.ProcessId /T /F | Out-Null }"

echo.
echo ...
timeout /t 3 /nobreak >nul



taskkill /F /T /IM redis-server.exe >nul 2>&1
taskkill /F /T /IM ollama.exe >nul 2>&1



timeout /t 2 /nobreak >nul



echo.
echo ========================================
echo Service List
echo ========================================
echo   1. Redis
echo   2. Ollama
echo   3. Mail Service
echo   4. Worker - LocalLLM
echo   5. Worker - OCR Service
echo   6. Worker - SendService
echo   7. API Server
echo   8. Streamlit UI
echo ========================================
echo.





REM 1. Redis
echo [1/8] Activate Redis...

start "TalentSystem Redis" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ redis

timeout /t 2 /nobreak >nul


REM 2. Ollama
echo [2/8] Activate Ollama...

start "TalentSystem Ollama" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ ollama

timeout /t 3 /nobreak >nul


REM 3. Mail Service
echo [3/8] Activate Mail Service...

start "TalentSystem Mail Service" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ mail

timeout /t 2 /nobreak >nul


REM 4. Worker LocalLLM
echo [4/8] Activate Worker LocalLLM...

start "TalentSystem Worker LocalLLM" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ local_llm

timeout /t 2 /nobreak >nul


REM 5. Worker OCR Service
echo [5/8] Activate Worker OCR Service...

start "TalentSystem Worker OCRService" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ ocr

timeout /t 2 /nobreak >nul


REM 6. Worker SendService
echo [6/8] Activate Worker SendService...

start "TalentSystem Worker SendService" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ send

timeout /t 2 /nobreak >nul


REM 7. API Server
echo [7/8] Activate API Server...

start "TalentSystem API Server" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ api

timeout /t 3 /nobreak >nul


REM 8. Streamlit UI
echo [8/8] Activate Streamlit UI...

start "TalentSystem Streamlit UI" ^
    "%ComSpec%" /d /k ^
    call "%START_BAT%" __talent_service__ streamlit

timeout /t 3 /nobreak >nul



echo.
echo ========================================
echo All Service Started
echo ========================================
echo.
echo   Redis:         ACTIVE
echo   Ollama:        ACTIVE
echo   Mail Service:  ACTIVE
echo   LocalLLM:      ACTIVE
echo   OCR Service:   ACTIVE
echo   SendService:   ACTIVE
echo   API Server:    ACTIVE
echo   Streamlit UI:  ACTIVE
echo.
echo ========================================
echo URL
echo ========================================
echo Streamlit: http://localhost:8501
echo API:       http://localhost:8000
echo Redis:     localhost:6379
echo Ollama:    http://localhost:11434
exit /b 0



:RUN_SERVICE

set "SERVICE_NAME=%~2"

cd /d "%TALENT_SYSTEM%"

if errorlevel 1 (
    echo [錯誤] 無法切換到專案根目錄：
    echo %TALENT_SYSTEM%
    echo.
    pause
    exit /b 1
)



if /I "%SERVICE_NAME%"=="redis" (
    title TalentSystem Redis

    echo ========================================
    echo Talent System Redis
    echo ========================================
    echo.
    echo Working Directory：
    echo %CD%
    echo.
    echo Redis Executable：
    echo %REDIS_EXE%
    echo.

    "%REDIS_EXE%"

    goto SERVICE_ENDED
)


if /I "%SERVICE_NAME%"=="ollama" (
    title TalentSystem Ollama

    echo ========================================
    echo Talent System Ollama
    echo ========================================
    echo.

    ollama serve

    goto SERVICE_ENDED
)



if /I "%SERVICE_NAME%"=="mail" (
    title TalentSystem Mail Service

    echo ========================================
    echo Talent System Mail Service
    echo ========================================
    echo.

    python -m backend.services.mail

    goto SERVICE_ENDED
)



if /I "%SERVICE_NAME%"=="local_llm" (
    title TalentSystem Worker LocalLLM

    echo ========================================
    echo Talent System Worker LocalLLM
    echo ========================================
    echo.

    python -m celery -A backend.services.local_llm worker --loglevel=info --queues=scoring_queue -P solo

    goto SERVICE_ENDED
)


if /I "%SERVICE_NAME%"=="ocr" (
    title TalentSystem Worker OCRService

    set "PYTHONUTF8=1"
    set "DOCLING_USE_TORCH_COMPILE=0"

    echo ========================================
    echo Talent System Worker OCRService
    echo ========================================
    echo.
    echo PYTHONUTF8=%PYTHONUTF8%
    echo DOCLING_USE_TORCH_COMPILE=%DOCLING_USE_TORCH_COMPILE%
    echo.

    python -m celery -A backend.services.ocr_service worker --loglevel=info --queues=ocr_queue -P solo

    goto SERVICE_ENDED
)



if /I "%SERVICE_NAME%"=="send" (
    title TalentSystem Worker SendService

    echo ========================================
    echo Talent System Worker SendService
    echo ========================================
    echo.

    python -m celery -A backend.services.send_service worker --loglevel=info --queues=mail_queue -P solo

    goto SERVICE_ENDED
)



if /I "%SERVICE_NAME%"=="api" (
    title TalentSystem API Server

    echo ========================================
    echo Talent System API Server
    echo ========================================
    echo.

    python -m backend

    goto SERVICE_ENDED
)


if /I "%SERVICE_NAME%"=="streamlit" (
    title TalentSystem Streamlit UI

    echo ========================================
    echo Talent System Streamlit UI
    echo ========================================
    echo.

    python -m streamlit run frontend\ui.py

    goto SERVICE_ENDED
)


echo [錯誤] 無法識別的服務：
echo %SERVICE_NAME%
echo.
timeout /t 1 /nobreak >nul
exit /b 0



:SERVICE_ENDED

set "SERVICE_EXIT_CODE=%ERRORLEVEL%"

echo.
echo ========================================
echo 服務已停止
echo ========================================
echo.
echo Service：%SERVICE_NAME%
echo Exit Code：%SERVICE_EXIT_CODE%
echo.
echo 請重新執行根目錄的 start.bat 重新啟動服務。
echo.

exit /b %SERVICE_EXIT_CODE%