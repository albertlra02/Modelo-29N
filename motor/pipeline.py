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
from datos.familias import PROV_CCAA
from motor import senado
from motor.palancas import Palancas, aplicar
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


# ------------------------------------------------------------------ candidaturas
#
# Candidaturas registradas el 16/10/2026 (cierre de coaliciones ante la Junta Electoral Central):
#   - Frente Amplio: IU, Movimiento Sumar, Más Madrid y Comuns, con CHA (Aragón), Més (Baleares),
#     Batzarre, Somos Asturies, Iniciativa del Pueblo Andaluz y Recortes Cero. Es el espacio que las
#     encuestas llaman "Sumar": la columna SUMAR pasa a FRENTE_AMPLIO.
#   - Podemos va por su cuenta en el resto de comunidades.
#   - Cataluña: Podemos no presenta lista y se integra en las de ERC (encabezadas por Rufián). Sus
#     votantes se reparten entre ERC y los Comuns (Frente Amplio) según PODEMOS_CATALUNA.
#   - C. Valenciana: Compromís-Front Valencià (Compromís, Sumar, EU y Podem): una sola lista.
#   - Canarias: Unidad del Pueblo Canario (NC, IU, Sumar y Podemos): una sola lista.
#   Las listas conjuntas conservan todos los votos de sus partes y cuentan como Frente Amplio.
#
# Lista única: la hipótesis de Sumar y Podemos juntos en toda España, que no se ha dado.

CANDIDATURAS = ("registradas", "lista_unica")
# Supuesto sin calibrar: no hay precedente de Podemos pidiendo el voto para ERC
PODEMOS_CATALUNA = {"ERC": 0.6, "SUMAR": 0.4}
JUNTOS_CON_PODEMOS = {"C. Valenciana": ["SUMAR", "PODEMOS"], "Canarias": ["SUMAR", "PODEMOS", "NC"]}


def _reorganizar(c: dict, cambio) -> dict:
    """Aplica `cambio(df, ccaa, varianza)` a las cuotas provinciales y autonómicas, combina la sd
    regional de las listas que se juntan (en varianza) y recalcula el nacional agregando provincias."""
    c = dict(c)
    for k in ("s0", "s0_unif", "base"):
        c[k] = cambio(c[k].copy(), c[k].index.map(PROV_CCAA))
    c["obj_ccaa"] = cambio(c["obj_ccaa"].copy(), c["obj_ccaa"].index)
    c["sd_reg"] = np.sqrt(cambio(c["sd_reg"] ** 2, c["sd_reg"].index, varianza=True).clip(lower=0))
    w = c["pesos"].reindex(c["s0"].index)
    c["nacional"] = c["s0"].mul(w, axis=0).sum() / w.sum()
    return c


def registradas(c: dict) -> dict:
    """Candidaturas del 29-N tal como se han registrado (ver arriba)."""
    s0 = c["s0"]

    def cambio(df, ccaa, varianza=False):
        cat = np.asarray(ccaa == "Cataluña")
        for p, f in PODEMOS_CATALUNA.items():
            df.loc[cat, p] += (f**2 if varianza else f) * df.loc[cat, "PODEMOS"]
        df.loc[cat, "PODEMOS"] = 0.0
        for region, partes in JUNTOS_CON_PODEMOS.items():
            m = np.asarray(ccaa == region)
            df.loc[m, "SUMAR"] = df.loc[m, partes].sum(axis=1)
            df.loc[m, partes[1:]] = 0.0
        return df.drop(columns="NC").rename(columns={"SUMAR": "FRENTE_AMPLIO"})

    # Parte de cada lista del Frente Amplio que no está en el pacto del Senado (Podemos y NC)
    ccaa = s0.index.map(PROV_CCAA)
    ajena = pd.Series(0.0, index=s0.index)
    for region, partes in JUNTOS_CON_PODEMOS.items():
        m = np.asarray(ccaa == region)
        ajena[m] = s0.loc[m, partes[1:]].sum(axis=1) / s0.loc[m, partes].sum(axis=1)
    c = _reorganizar(c, cambio)
    c["ajena"] = ajena
    return c


def lista_unica(c: dict) -> dict:
    """Hipótesis de lista única Sumar + Podemos en toda España (no se ha dado)."""
    s0 = c["s0"]

    def cambio(df, ccaa, varianza=False):
        df["SUMAR"] = df[["SUMAR", "PODEMOS"]].sum(axis=1)
        return df.drop(columns="PODEMOS").rename(columns={"SUMAR": "FRENTE_AMPLIO"})

    ajena = (s0.PODEMOS / (s0.SUMAR + s0.PODEMOS)).fillna(0)
    c = _reorganizar(c, cambio)
    c["ajena"] = ajena
    return c


@dataclass(frozen=True)
class Escenario:
    fecha: str = FECHA
    candidaturas: str = "registradas"        # clave de CANDIDATURAS
    participacion: float = PART_BASE
    reparto: str = "historico"               # clave de REPARTOS
    n_sim: int = 10_000
    semilla: int = 2026
    palancas: Palancas = Palancas()          # movilización por bloque y voto útil (motor/palancas.py)

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
    senado: dict = field(default_factory=dict, repr=False)   # sim, sin_coalicion, circunscripciones, voto, probs

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
    if esc.candidaturas not in CANDIDATURAS:
        raise ValueError(f"candidaturas desconocidas: {esc.candidaturas!r} (válidas: {CANDIDATURAS})")
    if c is None:
        c = piezas_centrales(esc.fecha, esc.participacion, esc.reparto)
    c = registradas(c) if esc.candidaturas == "registradas" else lista_unica(c)
    c = aplicar(c, esc.palancas)
    renombrar = {"SUMAR": "FRENTE_AMPLIO"}
    if esc.candidaturas == "lista_unica":
        renombrar["PODEMOS"] = "FRENTE_AMPLIO"
    estatales = tuple(dict.fromkeys(renombrar.get(p, p) for p in ESTATALES))
    bloques = {renombrar.get(p, p): v for p, v in BLOQUES.items()}
    mayorias = {k: list(dict.fromkeys(renombrar.get(p, p) for p in v)) for k, v in MAYORIAS.items()}

    sim, voto, prov, S = simular(
        c["s0"], c["s0_unif"], c["nacional"], c["region"], c["sd_reg"], escanos_2026(), c["pesos"],
        esc.dias, bloques, estatales=estatales, n_sim=esc.n_sim, semilla=esc.semilla,
        detalle=True, por_provincia=True, cuotas=True,
    )
    provs, partidos = list(c["s0"].index), list(c["s0"].columns)
    sen, sen_circ = senado.simular(S, provs, partidos, c["ajena"], coalicion=True, semilla=esc.semilla)
    sen_sin, _ = senado.simular(S, provs, partidos, c["ajena"], coalicion=False, semilla=esc.semilla)
    # Hipótesis de retirada de Vox del Senado, sobre las mismas simulaciones (y la misma semilla)
    hip_vox, seguras = {}, senado.pp_seguro(sen_circ)
    for h in senado.HIPOTESIS_VOX:
        sv = senado.retirada_vox(h, seguras)
        nv = senado.nombres_vox(c["s0"], sv)
        kw = dict(semilla=esc.semilla, sin_vox=sv, vox_en_pp=nv)
        con_h, circ_h = senado.simular(S, provs, partidos, c["ajena"], coalicion=True, **kw)
        sin_h, _ = senado.simular(S, provs, partidos, c["ajena"], coalicion=False, **kw)
        # sin lista propia en esas provincias, cualquier senador de Vox ahí sale de la lista del PP
        en_pp = sum((circ_h[p]["VOX"] for p in nv if "VOX" in circ_h[p]), pd.Series(0, index=con_h.index))
        hip_vox[h] = {"sim": con_h, "sin_coalicion": sin_h, "circunscripciones": circ_h,
                      "voto": senado.central(c["s0"], c["ajena"], sin_vox=sv), "probs": probs_senado(con_h, sin_h),
                      "sin_vox": sorted(sv), "vox_en_pp": sorted(nv), "vox_en_pp_sim": en_pp.astype("int16")}
    del S

    tabla, probs = resumen(sim, mayorias)
    tabla.insert(0, "voto_%", (100 * c["nacional"]).reindex(tabla.index).round(1))
    derecha = [p for p in DERECHA if p in sim]
    socios = [p for p in mayorias["bloque de investidura 2023"] if p in sim]
    probs["P(ningún bloque llega)"] = float(((sim[derecha].sum(axis=1) < 176)
                                             & (sim[socios].sum(axis=1) < 176)).mean())
    probs["P(PSOE primero)"] = float((sim.PSOE > sim.drop(columns="PSOE").max(axis=1)).mean())
    return Resultado(esc, sim, voto, {p: pd.DataFrame(v, columns=sim.columns) for p, v in prov.items()},
                     tabla, probs, c["nacional"], c,
                     senado={"sim": sen, "sin_coalicion": sen_sin, "circunscripciones": sen_circ,
                             "voto": senado.central(c["s0"], c["ajena"]), "probs": probs_senado(sen, sen_sin),
                             "hipotesis_vox": hip_vox})


MITAD_SENADO = senado.TOTAL // 2 + 1        # 105 de los 208 electos
IZQUIERDA_SENADO = [senado.PROGRESO, "PSOE", "FRENTE_AMPLIO", "PODEMOS", "ERC", "BILDU", "BNG", "GBAI"]
DERECHA_SENADO = ["PP", "VOX", "UPN"]


def probs_senado(sen: pd.DataFrame, sin: pd.DataFrame) -> pd.Series:
    def llega(df, ps, umbral=MITAD_SENADO):
        return float((df[[p for p in ps if p in df]].sum(axis=1) >= umbral).mean())
    pl, pl_sin = senado.pleno(sen), senado.pleno(sin)
    pleno_total = len(senado.designados()) + senado.TOTAL
    mayoria = pleno_total // 2 + 1                                      # 134 de 266
    tres_quintos = -(-3 * pleno_total // 5)                              # 160 de 266
    return pd.Series({
        "P(PP mayoría absoluta)": llega(pl, ["PP"], mayoria),
        "P(PP + Vox + UPN mayoría absoluta)": llega(pl, DERECHA_SENADO, mayoria),
        "P(PP + Vox tres quintos)": llega(pl, ["PP", "VOX"], tres_quintos),
        "P(izquierda mayoría absoluta)": llega(pl, IZQUIERDA_SENADO, mayoria),
        "P(PP mayoría absoluta sin coalición)": llega(pl_sin, ["PP"], mayoria),
        "P(PP ≥ 105)": llega(sen, ["PP"]),
        "P(PP + Vox ≥ 105)": llega(sen, ["PP", "VOX"]),
        "P(izquierda ≥ 105)": llega(sen, IZQUIERDA_SENADO),
        "P(PP ≥ 105 sin coalición)": llega(sin, ["PP"]),
        "P(izquierda ≥ 105 sin coalición)": llega(sin, IZQUIERDA_SENADO),
    })
