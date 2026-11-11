"""Utilidades pequeñas para los scripts de línea de comandos."""
from __future__ import annotations

import sys


def configurar_salida_utf8() -> None:
    """Permite imprimir acentos y símbolos matemáticos en consolas de Windows."""
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
