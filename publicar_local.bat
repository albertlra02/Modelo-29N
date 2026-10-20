@echo off
rem Publica la web desde este ordenador con un tunel gratuito de Cloudflare (sin cuenta).
rem Da un enlace https://....trycloudflare.com que funciona mientras esta ventana siga abierta.
rem Requisito, una sola vez:  winget install --id Cloudflare.cloudflared
chcp 65001 >nul
cd /d "%~dp0"
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo Falta cloudflared. Instalalo una vez con:  winget install --id Cloudflare.cloudflared
  pause
  exit /b 1
)
set /p CLAVE=Contrasena para entrar en la web publicada:
set PUBLICADO=1
start "Modelo 29-N" .venv\Scripts\python.exe lanzar.py --sin-navegador
echo.
echo Busca abajo la linea con https://....trycloudflare.com: ese es el enlace para compartir.
echo Para cerrar la web publicada, cierra esta ventana y la del modelo.
echo.
cloudflared tunnel --url http://127.0.0.1:8029
