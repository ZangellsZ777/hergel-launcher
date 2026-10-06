@echo off
cd /d "%~dp0"
py run.py
if errorlevel 1 (
  echo.
  echo Hergel Launcher no pudo abrir. Copia el error de arriba y envialo en el chat.
  pause
)
