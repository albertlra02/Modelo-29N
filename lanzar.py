"""
Arranca la web del modelo y la abre en el navegador. Es el archivo de inicio en VS Code (F5)
y lo usa iniciar.bat.

    python lanzar.py                 # http://127.0.0.1:8029
    python lanzar.py --puerto 8100
    python lanzar.py --sin-navegador

El servidor se reinicia solo al guardar cambios en el código Python (web/, motor/, interfaz/, datos/);
las plantillas y el CSS se recogen al recargar la página.
"""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))

import uvicorn  # noqa: E402


def abrir_cuando_responda(url: str, puerto: int, espera: float = 60) -> None:
    """Abre el navegador cuando el servidor ya acepta conexiones (si se abre antes, sale una página de error)."""
    fin = time.monotonic() + espera
    while time.monotonic() < fin:
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
                break
        except OSError:
            time.sleep(0.3)
    webbrowser.open(url)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Abre la web del modelo electoral.")
    ap.add_argument("--puerto", type=int, default=8029)
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.puerto}"
    print(f"Web del modelo en {url}  (Ctrl+C para cerrar)")
    if not args.sin_navegador:
        threading.Thread(target=abrir_cuando_responda, args=(url, args.puerto), daemon=True).start()
    uvicorn.run("web.servidor:app", host="127.0.0.1", port=args.puerto, reload=True,
                reload_dirs=[str(RAIZ / d) for d in ("web", "motor", "interfaz", "datos")], log_level="warning")
