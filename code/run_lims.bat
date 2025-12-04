@echo off
echo ========================================================
echo STARTING LIMS PRODUCTION SYSTEM
echo ========================================================

:: --- CONFIGURATION ---
set ENV_PATH=D:\envs\sflims
set PYTHON_PATH=%ENV_PATH%\python.exe

:: --- CRITICAL FIX: MANUALLY ACTIVATE ENVIRONMENT ---
:: We add the folders where Conda hides DLLs (like sqlite3.dll) to the Windows PATH
:: This stops the "DLL load failed" error.
set PATH=%ENV_PATH%;%ENV_PATH%\Library\mingw-w64\bin;%ENV_PATH%\Library\usr\bin;%ENV_PATH%\Library\bin;%ENV_PATH%\Scripts;%PATH%

set REDIS_DIR=D:\redis
set REDIS_EXE=redis-server.exe
set REDIS_CONF=redis.windows.conf
:: ---------------------

@REM echo Starting Redis Cache...
@REM cd /d "%REDIS_DIR%"
@REM if exist "%REDIS_EXE%" (
@REM     start "Redis Server" /min "%REDIS_EXE%" "%REDIS_CONF%"
@REM ) else (
@REM     echo CRITICAL ERROR: Redis not found.
@REM     pause
@REM     exit
@REM )

echo Starting Nginx...
cd /d D:\nginx-1.28.0
start nginx.exe

::echo Launching Background Services...
::cd /d D:\NGINX_SERVER\code
::start "LIMS Services" /min "%PYTHON_PATH%" services.py

echo Launching Web Workers...
cd /d D:\NGINX_SERVER\code


:: We use --threads=4 so you don't overload the CPU while doing PDF work
@REM start "DEBUG SHELL" cmd /k "echo Type: D:\envs\sflims\python.exe && echo Then try: import app"
start "Worker 1" cmd /k "%PYTHON_PATH%" -m waitress --port=8001 --threads=4 app:app



::start "Worker 1" /min "%PYTHON_PATH%" -m waitress --port=8001 --threads=4 app:app
::start "Worker 2" /min "%PYTHON_PATH%" -m waitress --port=8002 --threads=4 app:app
:: start "Worker 3" /min "%PYTHON_PATH%" -m waitress --port=8003 --threads=4 app:app
:: start "Worker 4" /min "%PYTHON_PATH%" -m waitress --port=8004 --threads=4 app:app
:: Uncomment these lines if you need more power later:
:: start "Worker 5" /min "%PYTHON_PATH%" -m waitress --port=8005 --threads=4 app:app
:: start "Worker 6" /min "%PYTHON_PATH%" -m waitress --port=8006 --threads=4 app:app

echo.
echo SYSTEM LIVE AT: http://localhost:8000
pause