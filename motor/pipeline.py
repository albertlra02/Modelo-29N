"""
Punto de entrada único del modelo: un escenario entra, un resultado sale.

Lo usan la aplicación (app.py) y los scripts de línea de comandos
(scripts/prediccion_2026.py, validacion/).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from datos.cargar import escanos_2026
from motor.montecarlo import resumen, simular
from motor.proyeccion import FECHA, central

ELECCION = pd.Timestamp("2026-11-29")

# Signo del factor de bloque: -1 derecha, +1 izquierda; los demás no comparten error común
BLOQUES = {"PP": -1, "VOX": -1, "SALF": -1, "UPN": -1,
           "PSOE": +1, "SUMAR": +1, "PODEMOS": +1, "ADELANTE": +1}
ESTATALES = ("PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "SALF")
DERECHA = ["PP", "VOX", "UPN", "SALF"]
SOCIOS_2023 = ["PSOE", "SUMAR", "PODEMOS", "ERC", "JUNTS", "BILDU", "PNV", "BNG", "CC", "ADELANTE"]
MAYORIAS = {
    "PP + Vox": ["PP", "VOX"],
    "PP + Vox + UPN + SALF": DERECHA,
    "PP solo": ["PP"],
    "bloque de investidura 2023": SOCIOS_2023,
}

# Participación que suponen de media las encuestas que la publican (jul-oct 2026)
PART_BASE = 0.65
# Cómo se reparten los votantes extra (de cada 100 votos válidos adicionales)
REPARTOS = {
    "historico": {"dcha": 0.18, "izda": 0.57, "resto": 0.25},     # regresión 2015-2023
    "simetrico": {"dcha": 0.45, "izda": 0.49, "resto": 0.06},     # como cayó en 2019N
    "muy_asimetrico": {"dcha": 0.05, "izda": 0.80, "resto": 0.15},
}
IZDA_ESTATAL = ["PSOE", "SUMAR", "PODEMOS", "ADELANTE"]


def ajuste_participacion(participacion: float, composicion: dict):
    """Devuelve una función nacional -> nacional que añade o quita votantes."""
    def f(nac: pd.Series) -> pd.Series:
        extra = participacion / PART_BASE - 1
        votos = nac.copy()
        resto = [p for p in nac.index if p not in DERECHA + IZDA_ESTATAL]
        for grupo, partidos in [("dcha", DERECHA), ("izda", IZDA_ESTATAL), ("resto", resto)]:
            votos[partidos] += extra * composicion[grupo] * nac[partidos] / nac[partidos].sum()
        return (votos / votos.sum()).clip(lower=0)
    return f


def fusionar(c: dict, partidos: list[str], nuevo: str) -> dict:
    """Escenario de lista conjunta: suma cuotas; la sd regional se combina en cuadratura."""
    c = dict(c)
    for k in ("s0", "s0_unif", "base", "obj_ccaa"):
        df = c[k].copy()
        df[nuevo] = df[partidos].sum(axis=1)
        c[k] = df.drop(columns=partidos)
    sd = c["sd_reg"].copy()
    sd[nuevo] = np.sqrt((sd[partidos] ** 2).sum(axis=1))
    c["sd_reg"] = sd.drop(columns=partidos)
    nac = c["nacional"].copy()
    nac[nuevo] = nac[partidos].sum()
    c["nacional"] = nac.drop(partidos).reindex(c["s0"].columns)
    return c


@dataclass(frozen=True)
class Escenario:
    fecha: str = FECHA
    candidaturas: str = "separados"          # 'separados' | 'frente_amplio'
    participacion: float = PART_BASE
    reparto: str = "historico"               # clave de REPARTOS
    n_sim: int = 10_000
    semilla: int = 2026

    @property
    def dias(self) -> int:
        return int((ELECCION - pd.Timestamp(self.fecha)).days)


@dataclass
class Resultado:
    escenario: Escenario
    sim: pd.DataFrame                 # n_sim x partido: escaños nacionales
    voto: pd.DataFrame                # n_sim x partido: voto nacional simulado (+ factores)
    provincias: dict                  # provincia -> array n_sim x partido (escaños)
    tabla: pd.DataFrame               # resumen por partido (cuantiles, media, voto central)
    probs: pd.Series                  # probabilidades de mayorías
    nacional: pd.Series               # voto central por partido (cuotas)
    central: dict = field(repr=False)

    @property
    def partidos(self) -> list[str]:
        return list(self.sim.columns)

    def suma(self, partidos: list[str]) -> pd.Series:
        return self.sim[[p for p in partidos if p in self.sim]].sum(axis=1)


def piezas_centrales(fecha: str, participacion: float, reparto: str) -> dict:
    ajuste = None
    if abs(participacion - PART_BASE) > 1e-9:
        ajuste = ajuste_participacion(participacion, REPARTOS[reparto])
    return central(fecha, ajuste=ajuste)


def ejecutar(esc: Escenario, c: dict | None = None) -> Resultado:
    """Corre el modelo completo. `c` permite reutilizar las piezas centrales ya calculadas."""
    if c is None:
        c = piezas_centrales(esc.fecha, esc.participacion, esc.reparto)
    estatales, bloques = ESTATALES, dict(BLOQUES)
    mayorias = {k: list(v) for k, v in MAYORIAS.items()}
    if esc.candidaturas == "frente_amplio":
        c = fusionar(c, ["SUMAR", "PODEMOS"], "FRENTE_AMPLIO")
        estatales = tuple(p for p in ESTATALES if p not in ("SUMAR", "PODEMOS")) + ("FRENTE_AMPLIO",)
        bloques["FRENTE_AMPLIO"] = +1
        mayorias = {k: list(dict.fromkeys("FRENTE_AMPLIO" if p in ("SUMAR", "PODEMOS") else p for p in v))
                    for k, v in mayorias.items()}

    sim, voto, prov = simular(
        c["s0"], c["s0_unif"], c["nacional"], c["region"], c["sd_reg"], escanos_2026(), c["pesos"],
        esc.dias, bloques, estatales=estatales, n_sim=esc.n_sim, semilla=esc.semilla,
        detalle=True, por_provincia=True,
    )
    tabla, probs = resumen(sim, mayorias)
    tabla.insert(0, "voto_%", (100 * c["nacional"]).reindex(tabla.index).round(1))
    derecha = [p for p in DERECHA if p in sim]
    socios = [p for p in SOCIOS_2023 + ["FRENTE_AMPLIO"] if p in sim]
    probs["P(ningún bloque llega)"] = float(((sim[derecha].sum(axis=1) < 176)
                                             & (sim[socios].sum(axis=1) < 176)).mean())
    probs["P(PSOE primero)"] = float((sim.PSOE > sim.drop(columns="PSOE").max(axis=1)).mean())
    return Resultado(esc, sim, voto, {p: pd.DataFrame(v, columns=sim.columns) for p, v in prov.items()},
                     tabla, probs, c["nacional"], c)
