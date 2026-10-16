"""
Cálculo de escenarios para la aplicación, con caché en disco.

Cada escenario calculado se guarda resumido en resultados/cache/<huella>/, donde la huella
es un hash del código del modelo y de los datos: si cambia cualquiera de ellos, la caché
vieja deja de usarse (y se borra al arrancar). Volver a un escenario ya calculado cuesta
milisegundos; `python -m scripts.precalcular` calcula de antemano la rejilla habitual.
"""
from __future__ import annotations

import gzip
import hashlib
import pickle
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from datos.cargar import escanos_2026
from datos.familias import PROV_CCAA
from interfaz.estilo import nombre
from motor.pipeline import DERECHA, PART_BASE, Escenario, ejecutar, piezas_centrales
from motor.proyeccion import FECHA

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "resultados" / "cache"
# Ficheros de los que dependen los resultados (este módulo incluido: resume cada escenario)
FICHEROS_MODELO = ["interfaz/calculo.py", "motor/*.py", "datos/*.py", "datos/*.csv",
                   "datos/raw/*.csv", "datos/encuestas/*.csv"]

N_SIM, SEMILLA = 5000, 2026                  # valores por defecto de la app (los que se precalculan)
INICIO_EVOLUCION = date(2026, 6, 1)          # primera fecha del deslizador y de la evolución
PARTICIPACIONES = range(60, 77)              # % enteros del deslizador
BARRIDO = [0.62, 0.65, 0.67, 0.69, 0.71, 0.73, 0.75]
N_SIM_BARRIDO = 3000


def huella_modelo() -> str:
    h = hashlib.sha1()
    for patron in FICHEROS_MODELO:
        for f in sorted(x for x in RAIZ.glob(patron) if x.is_file()):
            h.update(f.relative_to(RAIZ).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def fechas_semanales() -> list[str]:
    """Cortes de encuestas cada 7 días, terminando en la última fecha del modelo."""
    fin, d, out = date.fromisoformat(FECHA), date.fromisoformat(FECHA), []
    while d >= INICIO_EVOLUCION:
        out.append(d.isoformat())
        d -= timedelta(days=7)
    assert out[0] == fin.isoformat()
    return out[::-1]


def normalizar(esc: Escenario) -> Escenario:
    """Con la participación base el reparto de votantes extra no influye: misma clave para todos."""
    if abs(esc.participacion - PART_BASE) < 1e-9 and esc.reparto != "historico":
        return Escenario(esc.fecha, esc.candidaturas, esc.participacion, "historico", esc.n_sim, esc.semilla)
    return esc


# ------------------------------------------------------------------ resumen de un escenario

def _provincias(r) -> pd.DataFrame:
    esc = escanos_2026()
    derecha = [p for p in DERECHA if p in r.sim]
    filas = []
    for prov, df in r.provincias.items():
        arr = df.to_numpy()
        vec, cnt = np.unique(arr, axis=0, return_counts=True)
        moda = pd.Series(vec[cnt.argmax()], index=df.columns)
        bloque = df[derecha].sum(axis=1)
        b_moda = bloque.mode().iloc[0]
        fila = {"Provincia": prov, "CCAA": PROV_CCAA[prov], "Escaños": int(esc[prov])}
        moda = moda[moda > 0].sort_values(ascending=False, kind="stable")
        fila["Reparto"] = ", ".join(f"{nombre(p)} {int(v)}" for p, v in moda.items())
        fila["Reparto más probable"] = round(100 * cnt.max() / len(arr))
        fila["Cambia el bloque"] = round(100 * float((bloque != b_moda).mean()))
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("Escaños", ascending=False)


def voto_simulado(r) -> pd.DataFrame:
    """Cuantiles del voto nacional simulado (% de votos válidos) por candidatura."""
    v = 100 * r.voto[[x for x in r.sim.columns if x in r.voto]]
    q = v.quantile([0.025, 0.1, 0.5, 0.9, 0.975]).T
    q.columns = ["p2.5", "p10", "mediana", "p90", "p97.5"]
    return q


def resumir(r) -> dict:
    return {
        "sim": r.sim.astype("int16"),
        "tabla": r.tabla,
        "probs": r.probs,
        "voto": voto_simulado(r),
        "ppvox": r.suma(["PP", "VOX"]),
        "provincias": _provincias(r),
        "voto_prov": (100 * r.central["s0"]).round(1),
        "diag": r.central["diag"],
        "dias": r.escenario.dias,
    }


# ------------------------------------------------------------------ caché en disco

def _ruta(esc: Escenario, version: str) -> Path:
    clave = (f"{esc.fecha}_{esc.candidaturas}_{round(1000 * esc.participacion)}_{esc.reparto}"
             f"_{esc.n_sim}_{esc.semilla}")
    return CACHE / version / f"{clave}.pkl.gz"


def en_disco(esc: Escenario, version: str) -> bool:
    return _ruta(normalizar(esc), version).exists()


def limpiar_cache(version: str) -> None:
    """Borra las cachés de versiones anteriores del modelo."""
    if CACHE.exists():
        for d in CACHE.iterdir():
            if d.is_dir() and d.name != version:
                shutil.rmtree(d, ignore_errors=True)


def escenario(esc: Escenario, version: str,
              centrales: Callable[[str, float, str], dict] | None = None) -> dict:
    """Resumen del escenario: de disco si ya se calculó con esta versión; si no, lo calcula y lo guarda.
    `centrales(fecha, participacion, reparto)` permite reutilizar piezas centrales en memoria."""
    esc = normalizar(esc)
    ruta = _ruta(esc, version)
    if ruta.exists():
        try:
            with gzip.open(ruta, "rb") as f:
                return pickle.load(f)
        except Exception:  # noqa: BLE001  (fichero a medio escribir o corrupto: se recalcula)
            ruta.unlink(missing_ok=True)
    c = (centrales or piezas_centrales)(esc.fecha, esc.participacion, esc.reparto)
    d = resumir(ejecutar(esc, c))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    with gzip.open(tmp, "wb", compresslevel=5) as f:
        pickle.dump(d, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(ruta)
    return d


# ------------------------------------------------------------------ rejilla habitual

def rejilla() -> list[Escenario]:
    """Escenarios que la app usa con sus valores por defecto: evolución semanal, deslizador de
    participación en la última fecha y barrido de participación. Ordenados para reutilizar las
    piezas centrales (que dependen de fecha, participación y reparto, no de las candidaturas)."""
    out = []
    for f in fechas_semanales():
        for cand in ("separados", "frente_amplio"):
            out.append(Escenario(f, cand, PART_BASE, "historico", N_SIM, SEMILLA))
    for reparto in ("historico", "simetrico", "muy_asimetrico"):
        for part in sorted({p / 100 for p in PARTICIPACIONES} | set(BARRIDO)):
            for cand in ("separados", "frente_amplio"):
                if round(100 * part) in PARTICIPACIONES:
                    out.append(Escenario(FECHA, cand, part, reparto, N_SIM, SEMILLA))
                if part in BARRIDO:
                    out.append(Escenario(FECHA, cand, part, reparto, N_SIM_BARRIDO, SEMILLA))
    vistos, unicos = set(), []
    for e in map(normalizar, out):
        if e not in vistos:
            vistos.add(e)
            unicos.append(e)
    return unicos
