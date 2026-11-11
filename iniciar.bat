@echo off
rem Prepara el entorno la primera vez y abre la aplicacion.
cd /d %~dp0
set "PY_VENV=.venv\Scripts\python.exe"

if exist "%PY_VENV%" (
  "%PY_VENV%" -c "import sys" >nul 2>&1
  if not errorlevel 1 goto entorno_listo
)

echo Creando o reparando el entorno de Python...
py -3 -m venv --clear .venv || python -m venv --clear .venv
if errorlevel 1 (
  echo No se encontro Python 3.10 o posterior. Instalalo y vuelve a intentarlo.
  pause
  exit /b 1
)

:entorno_listo
set "REQUISITOS=requirements.txt"
"%PY_VENV%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 if exist requirements-lock.txt set "REQUISITOS=requirements-lock.txt"
"%PY_VENV%" -m pip install -q -r "%REQUISITOS%"
if errorlevel 1 (
  echo No se pudieron instalar las dependencias.
  pause
  exit /b 1
)
"%PY_VENV%" lanzar.py
