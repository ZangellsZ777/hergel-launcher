@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto error
py -m pip install "pyinstaller>=6.11,<7"
if errorlevel 1 goto error
py tools\descargar_paquete.py
if errorlevel 1 goto error
py tools\preparar_version.py
if errorlevel 1 goto error
py -m PyInstaller --noconfirm --clean build-windows\launcher.spec
if errorlevel 1 goto error
set "HERGEL_ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%HERGEL_ISCC%" set "HERGEL_ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%HERGEL_ISCC%" (
    echo.
    echo La aplicacion ya esta en dist\HergelLauncher.
    echo Para generar el instalador instala Inno Setup 6 y ejecuta este archivo de nuevo.
    echo Sitio oficial: https://jrsoftware.org/isdl.php
    pause
    exit /b 0
)
"%HERGEL_ISCC%" build-windows\installer.iss
if errorlevel 1 goto error
echo.
echo Listo: dist\Hergel-Launcher-Instalador.exe
pause
exit /b 0
:error
echo.
echo No se pudo compilar. Copia el error de arriba.
pause
exit /b 1
