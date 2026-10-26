"""
Procedencia de una predicción: con qué código, datos y parámetros se generó.

Junto a cada salida de resultados/prediccion/ se escribe un JSON con la fecha de generación,
el commit de git (y si había cambios sin guardar), la huella del modelo, el escenario completo
(semilla y simulaciones incluidas), la última encuesta usada y el SHA-256 de cada fichero
escrito. Con eso cualquier cifra publicada se puede rastrear y reproducir.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

from interfaz.calculo import huella_modelo

RAIZ = Path(__file__).resolve().parent.parent
PAQUETES = ["numpy", "pandas", "plotly"]


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def estado_git() -> dict:
    """Commit actual y si el código o los datos tienen cambios sin confirmar (None fuera de un
    repositorio). resultados/ no cuenta: son las propias salidas, no lo que las produce."""
    commit = _git("rev-parse", "HEAD")
    if commit is None:
        return {"commit": None, "cambios_sin_confirmar": None}
    cambios = _git("status", "--porcelain", "--", ".", ":(exclude)resultados")
    return {"commit": commit, "cambios_sin_confirmar": bool(cambios)}


def encuestas_usadas(fecha: str) -> dict:
    """Encuestas nacionales del ciclo 2026 con trabajo de campo terminado hasta el corte."""
    nac = pd.read_csv(RAIZ / "datos/encuestas/nacionales.csv", dtype={"ciclo": str})
    enc = nac[(nac.ciclo == "2026") & (nac.tipo != "resultado") & (nac.fin <= fecha)]
    if enc.empty:
        return {"n": 0, "ultima": None}
    u = enc.sort_values("fin").iloc[-1]
    return {"n": int(len(enc)), "ultima": {"fin": u.fin, "encuestadora": u.encuestadora,
                                           "medio": None if pd.isna(u.medio) else u.medio}}


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _version(paquete: str) -> str | None:
    try:
        return version(paquete)
    except PackageNotFoundError:
        return None


def escribir(destino: Path, escenario, ficheros: list[Path]) -> dict:
    """Escribe el JSON de procedencia en `destino` y lo devuelve como diccionario."""
    meta = {
        "generado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git": estado_git(),
        "huella_modelo": huella_modelo(),
        "escenario": asdict(escenario),
        "encuestas": encuestas_usadas(escenario.fecha),
        "entorno": {"python": platform.python_version(),
                    **{p: _version(p) for p in PAQUETES}},
        "ficheros": {Path(f).name: sha256(Path(f)) for f in ficheros},
    }
    destino.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
