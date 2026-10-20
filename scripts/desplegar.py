"""
Publica la web: sube el código actual y los escenarios ya calculados a la rama `despliegue` del repositorio
remoto, y Render la despliega sola (render.yaml). No toca tu rama, tu índice ni tu historial.

    python -m scripts.desplegar                # pasa los tests, empaqueta y sube
    python -m scripts.desplegar --sin-subir    # empaqueta y dice qué subiría, sin subir nada
    python -m scripts.desplegar --sin-tests    # se salta los tests (sólo si acabas de pasarlos)

Antes: `python -m scripts.precalcular` (o `scripts.actualizar_encuestas`, que ya lo hace). La caché viaja en la
rama de despliegue porque el disco del plan gratuito se borra cada vez que el servicio se duerme; la web la usa
mientras la huella del modelo (código + datos) sea la misma, y es la misma porque se suben los mismos ficheros.

La rama `despliegue` se reescribe en cada publicación (un único commit, sin historia), así que las cachés
antiguas no se acumulan en el repositorio.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from interfaz.calculo import CACHE, huella_modelo
from scripts.consola import configurar_salida_utf8

RAIZ = Path(__file__).resolve().parent.parent
RAMA = "despliegue"
REMOTO = "origin"
MIN_ESCENARIOS = 100       # la rejilla de precalcular tiene unos 170


def git(*args: str, env: dict | None = None, capturar: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, env=env, text=True, check=True,
                       capture_output=capturar)
    return (r.stdout or "").strip()


def main() -> int:
    configurar_salida_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-subir", action="store_true")
    ap.add_argument("--sin-tests", action="store_true")
    args = ap.parse_args()

    huella = huella_modelo()
    cache = CACHE / huella
    n = len(list(cache.glob("*.pkl.gz"))) if cache.exists() else 0
    if n < MIN_ESCENARIOS:
        print(f"La caché de esta versión del modelo ({huella}) tiene {n} escenarios. "
              "Corre antes `python -m scripts.precalcular`.")
        return 1
    if not args.sin_subir:
        remotos = git("remote").split()
        if REMOTO not in remotos:
            print("Falta el repositorio remoto. Crea uno privado en github.com y conéctalo con:\n"
                  f"    git remote add {REMOTO} https://github.com/<usuario>/<repositorio>.git")
            return 1
    if not args.sin_tests:
        print("Pasando los tests…")
        if subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=RAIZ).returncode:
            print("Los tests fallan: no se publica.")
            return 1

    # Árbol con lo que hay ahora en la carpeta (respetando .gitignore) más la caché, en un índice temporal
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "indice")}
        git("read-tree", "--empty", env=env)
        git("add", "-A", ".", env=env)
        git("add", "-f", str(cache.relative_to(RAIZ)), env=env)
        arbol = git("write-tree", env=env)
        ficheros = git("ls-tree", "-r", "--name-only", arbol).splitlines()
    mensaje = f"Despliegue {datetime.now():%Y-%m-%d %H:%M} · huella {huella} · {n} escenarios"
    commit = git("commit-tree", arbol, "-m", mensaje)
    print(f"{mensaje}\n{len(ficheros)} ficheros en el commit {commit[:10]}")
    if args.sin_subir:
        print("No se ha subido nada (--sin-subir).")
        return 0
    git("push", "--force", REMOTO, f"{commit}:refs/heads/{RAMA}", capturar=False)
    print(f"Subido a {REMOTO}/{RAMA}. Render lo publicará en unos minutos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
