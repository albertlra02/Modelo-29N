"""
Cálculo de escenarios para la aplicación, con caché en disco.

Cada escenario calculado se guarda resumido en resultados/cache/<huella>/, donde la huella
es un hash del código del modelo y de los datos: si cambia cualquiera de ellos, la caché
vieja deja de usarse (y se borra al arrancar). Volver a un escenario ya calculado cuesta
milisegundos; `python -m scripts.precalcular` calcula de antemano la rejilla habitual.
"""
from __future__ import annotations

import gzip
from dataclasses import replace
import hashlib
import pickle
import shutil
from datetime import date, timedelta
from pathlib import Path
from collections.abc import Callable

import numpy as np
import pandas as pd

from datos.cargar import escanos_2026
from datos.familias import PROV_CCAA
from interfaz.estilo import nombre
from motor import senado
from motor.pipeline import CANDIDATURAS, DERECHA, PART_BASE, Escenario, ejecutar, piezas_centrales
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
        return replace(esc, reparto="historico")
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
        fila["Reparto"] = _reparto_texto(moda)
        fila["Reparto más probable"] = round(100 * cnt.max() / len(arr))
        fila["Cambia el bloque"] = round(100 * float((bloque != b_moda).mean()))
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("Escaños", ascending=False)


def _detalle_provincias(r, n_repartos: int = 4) -> dict:
    """Para el panel de cada provincia: los repartos más frecuentes (texto, % de simulaciones) y la
    distribución de escaños de cada candidatura que saca alguno en al menos el 0,5 % ({escaños: %})."""
    out = {}
    for prov, df in r.provincias.items():
        vec, cnt = np.unique(df.to_numpy(), axis=0, return_counts=True)
        top = np.argsort(-cnt, kind="stable")[:n_repartos]
        repartos = [(_reparto_texto(pd.Series(vec[i], index=df.columns)), round(100 * cnt[i] / len(df), 1))
                    for i in top]
        dist = {}
        for p in df.columns:
            frec = df[p].value_counts(normalize=True).sort_index()
            if frec[frec.index > 0].sum() >= 0.005:
                dist[p] = {int(k): round(100 * float(v), 1) for k, v in frec.items()}
        out[prov] = {"repartos": repartos, "dist": dist}
    return out


def _reparto_texto(moda: pd.Series) -> str:
    moda = moda[moda > 0].sort_values(ascending=False, kind="stable")
    return ", ".join(f"{nombre(p)} {int(v)}" for p, v in moda.items())


def _senado(s: dict) -> dict:
    """Resumen del Senado: senadores por simulación (con y sin la coalición) y cada circunscripción."""
    circ = senado.circunscripciones()
    filas = []
    for c, df in s["circunscripciones"].items():
        arr = df.to_numpy()
        vec, cnt = np.unique(arr, axis=0, return_counts=True)
        moda = pd.Series(vec[cnt.argmax()], index=df.columns)
        primera = df.idxmax(axis=1).value_counts(normalize=True)
        filas.append({"Circunscripción": c, "Provincia": circ.at[c, "provincia"],
                      "CCAA": PROV_CCAA[circ.at[c, "provincia"]], "Senadores": int(circ.at[c, "escanos"]),
                      "Isla": bool(circ.at[c, "isla"]), "Coalición": bool(circ.at[c, "pacto"]),
                      "Reparto": _reparto_texto(moda), "Reparto más probable": round(100 * cnt.max() / len(arr)),
                      "Ganadora": moda.idxmax(), "P(ganadora)": round(100 * float(primera.get(moda.idxmax(), 0))),
                      "moda": moda[moda > 0].astype(int).to_dict()})
    return {"sim": s["sim"].astype("int16"), "sin_coalicion": s["sin_coalicion"].astype("int16"),
            "probs": s["probs"], "circunscripciones": pd.DataFrame(filas), "voto": s["voto"].round(1),
            # sólo en las hipótesis de retirada de Vox: dónde no va y dónde va dentro de la lista del PP
            **{k: s[k] for k in ("sin_vox", "vox_en_pp", "vox_en_pp_sim", "pp_fuera", "vox_uno") if k in s}}


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
        "detalle_prov": _detalle_provincias(r),
        "voto_prov": (100 * r.central["s0"]).round(1),
        "s0": r.central["s0"].astype("float32"),        # sin redondear, para el simulador
        "diag": r.central["diag"],
        "dias": r.escenario.dias,
        "senado": _senado(r.senado),
        "senado_vox": {h: _senado(v) for h, v in r.senado["hipotesis_vox"].items()},
    }


# ------------------------------------------------------------------ caché en disco

def _ruta(esc: Escenario, version: str) -> Path:
    clave = (f"{esc.fecha}_{esc.candidaturas}_{round(1000 * esc.participacion)}_{esc.reparto}"
             f"_{esc.n_sim}_{esc.semilla}")
    if esc.palancas.activas:
        clave += "_" + hashlib.sha1(repr(esc.palancas).encode()).hexdigest()[:10]
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
        for cand in CANDIDATURAS:
            out.append(Escenario(f, cand, PART_BASE, "historico", N_SIM, SEMILLA))
    for reparto in ("historico", "simetrico", "muy_asimetrico"):
        for part in sorted({p / 100 for p in PARTICIPACIONES} | set(BARRIDO)):
            for cand in CANDIDATURAS:
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
