"""
Precalcula la rejilla de escenarios que usa la aplicación (evolución semanal, deslizador de
participación y barrido), para que moverse por ella sea instantáneo.

    python -m scripts.precalcular              # sólo lo que falte
    python -m scripts.precalcular --procesos 4

Hay que volver a correrlo cuando cambien las encuestas o el modelo (la app también calcula
y guarda al vuelo lo que no encuentre, sólo que tarda unos segundos por escenario).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))
# Un hilo de álgebra lineal por proceso: con varios procesos, los hilos de numpy se pisan y todo va
# decenas de veces más lento. Tiene que fijarse antes de importar numpy (los procesos hijos heredan el entorno).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

from scripts.consola import configurar_salida_utf8  # noqa: E402
from interfaz.calculo import en_disco, escenario, huella_modelo, limpiar_cache, rejilla  # noqa: E402
from motor.pipeline import piezas_centrales  # noqa: E402


def _grupo(escenarios, version) -> int:
    """Escenarios que comparten piezas centrales: se calculan una sola vez."""
    os.chdir(RAIZ)
    e0 = escenarios[0]
    c = piezas_centrales(e0.fecha, e0.participacion, e0.reparto)
    for e in escenarios:
        escenario(e, version, centrales=lambda *_: c)
    return len(escenarios)


def main() -> int:
    configurar_salida_utf8()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()

    version = huella_modelo()
    limpiar_cache(version)
    pendientes = [e for e in rejilla() if not en_disco(e, version)]
    total = len(rejilla())
    if not pendientes:
        print(f"Rejilla completa ({total} escenarios, versión {version}).")
        return 0
    grupos = defaultdict(list)
    for e in pendientes:
        grupos[(e.fecha, e.participacion, e.reparto)].append(e)
    print(f"Versión {version}: faltan {len(pendientes)} de {total} escenarios "
          f"({len(grupos)} grupos, {args.procesos} procesos)…")
    t0, hechos = time.perf_counter(), 0
    with ProcessPoolExecutor(max_workers=args.procesos) as pool:
        futuros = [pool.submit(_grupo, g, version) for g in grupos.values()]
        for fut in as_completed(futuros):
            hechos += fut.result()
            print(f"  {hechos}/{len(pendientes)}  ({time.perf_counter() - t0:.0f} s)", flush=True)
    print(f"Hecho en {time.perf_counter() - t0:.0f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
