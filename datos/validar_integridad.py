"""Comprueba que los datos versionados coinciden con el manifiesto SHA-256."""
from __future__ import annotations

import hashlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("MANIFEST.sha256")


def validar(manifest: Path = MANIFEST) -> list[str]:
    errores = []
    for numero, linea in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not linea or linea.startswith("#"):
            continue
        esperado, ruta_rel = linea.split(maxsplit=1)
        ruta = RAIZ / ruta_rel
        if not ruta.is_file():
            errores.append(f"línea {numero}: falta {ruta_rel}")
            continue
        real = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if real != esperado:
            errores.append(f"línea {numero}: hash distinto para {ruta_rel}")
    return errores


def main() -> int:
    errores = validar()
    if errores:
        print("\n".join(errores))
        return 1
    print("Integridad de datos: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
