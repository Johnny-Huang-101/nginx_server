@echo off
echo STOPPING ALL LIMS SERVICES...

:: Kill Nginx
taskkill /F /IM nginx.exe


:: 2. Kill Redis
echo Stopping Redis...
taskkill /F /IM redis-server.exe >nul 2>&1

:: Kill all Python processes (The Waitress workers)
taskkill /F /IM python.exe

echo All services stopped.
pause