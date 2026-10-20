"""
Piezas deterministas del modelo para el 29-N (las usa motor/pipeline.py):

    encuestas nacionales --agregador--> cuotas nacionales 2026 (estimacion_nacional, objetivo_nacional)
    resultado 2023 por provincia (+ semillas para partidos nuevos) = base_2026
    encuestas autonómicas --regional--> objetivos por CCAA --swing logit--> cuotas provinciales (central)

Semillas de reparto provincial para candidaturas sin base comparable en 2023:
  - SUMAR / PODEMOS: el espacio Sumar de 2023 se reparte por provincia según el
    peso relativo de Sumar y Podemos en las europeas de 2024
  - SALF: patrón provincial de las europeas de 2024
  - ADELANTE: patrón provincial del ElectoPanel 12/10/2026 (en 2023 solo fue en Cádiz)

Nueva Canarias va como candidatura local (congelada en su base de 2023): en 2026 se integra en
la lista conjunta de Canarias con el Frente Amplio y Podemos (ver motor/pipeline.py).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from datos.cargar import cargar
from datos.familias import a_familias
from motor.agregador import agregar, preparar
from motor.swing import proyectar

FECHA = "2026-10-20"   # corte de encuestas por defecto; la app lo usa también como última fecha elegible
PARTIDOS = ["PP", "PSOE", "VOX", "SUMAR", "PODEMOS", "SALF", "ERC", "JUNTS",
            "BILDU", "PNV", "BNG", "CC", "UPN", "ADELANTE"]
BLANCO_PCT = 0.8   # voto en blanco 2023 ≈ 0,8 %

def estimacion_nacional(fecha=FECHA) -> pd.DataFrame:
    nac = pd.read_csv("datos/encuestas/nacionales.csv")
    enc = preparar(nac[nac.ciclo == "2026"], fecha)
    filas = []
    for pt in PARTIDOS:
        m, sd = agregar(enc, pt, fecha).final
        filas.append({"partido": pt, "media": max(m, 0.05), "sd": sd})
    est = pd.DataFrame(filas).set_index("partido")
    resto = 100 - est.media.sum() - BLANCO_PCT
    est.loc["OTROS"] = [max(resto, 0.5), np.nan]
    est.loc["BLANCO"] = [BLANCO_PCT, np.nan]
    est["cuota"] = est.media / est.media.sum()
    return est


def europeas_2024() -> pd.DataFrame:
    """Europeas 2024 por provincia, en cuota de votos válidos (candidaturas + blanco).
    Fuente oficial: datos/raw/europeas_2024_provincias.csv, generado con datos/oficiales.py."""
    e = pd.read_csv("datos/raw/europeas_2024_provincias.csv", index_col="provincia")
    votos = e.drop(columns=["censo", "votos_nulos", "blancos"])
    return votos.div(votos.sum(axis=1) + e.blancos, axis=0)


def base_2026() -> tuple[pd.DataFrame, pd.Series]:
    b = cargar("2023-07")
    f = a_familias(b.votos)
    f["BLANCO"] = b.meta.blancos
    s = f.div(f.sum(axis=1), axis=0)
    eu = europeas_2024().reindex(s.index)
    assert eu.PP.notna().all(), "provincias de las europeas sin casar"

    base = pd.DataFrame(index=s.index)
    for col in ["PP", "PSOE", "VOX", "ERC", "JUNTS", "PNV", "BNG", "BLANCO"]:
        base[col] = s[col]
    # CC: las encuestas de 2026 dan a CC sola; NC (que en la familia CC va dentro) va aparte, como local
    validos = f.sum(axis=1)
    base["CC"] = b.votos["CC"] / validos
    base["BILDU"] = s["BILDU"]
    base["UPN"] = s["NAV_DCHA"]
    frac_podemos = eu.Podemos / (eu.Podemos + eu.Sumar)
    base["PODEMOS"] = s["IZQ"] * frac_podemos
    base["SUMAR"] = s["IZQ"] * (1 - frac_podemos)
    base["SALF"] = eu.SALF * 0.3            # semilla: solo importa el patrón, el nivel lo fija el swing
    ep = cargar("ep", Path("datos/encuestas/electopanel_provincias_2026-10-12.csv"))
    ade = (ep.votos.get("AA", 0) + ep.votos.get("Adelante And.", 0)) / ep.validos
    base["ADELANTE"] = ade.reindex(s.index).fillna(0)
    # Candidaturas locales que pueden pelear un escaño: se mantienen con su base de 2023
    locales = {"TERUEL": "Teruel Existe", "UPL": "UPL", "SORIA_YA": "Soria ¡Ya!", "NC": "NC"}
    for k, col in locales.items():
        base[k] = b.votos[col] / validos
    # OTROS de la familia ya incluye UPL y Soria ¡Ya!; Teruel Existe tiene familia propia (s["TERUEL"])
    # y NC va dentro de la familia CC, así que se resta de OTROS sólo lo que viene de OTROS
    de_otros = base[["UPL", "SORIA_YA"]].sum(axis=1)
    base["OTROS"] = s[["OTROS", "CS", "CUP", "PRC"]].sum(axis=1) - de_otros
    base = base.div(base.sum(axis=1), axis=0)

    presencia = base > 0
    presencia["VOX"] = True   # en 2023 no concurrió en S.C. de Tenerife; en 2026 se asume que sí
    return base, presencia


LOCALES = ["TERUEL", "UPL", "SORIA_YA", "NC"]


def objetivo_nacional(est: pd.DataFrame, base: pd.DataFrame, pesos: pd.Series) -> pd.Series:
    """Cuotas nacionales objetivo: partidos encuestados + locales congelados en su base + resto."""
    nac = est.loc[PARTIDOS, "media"] / 100
    loc = base[LOCALES].mul(pesos, axis=0).sum() / pesos.sum()
    nac = pd.concat([nac, loc])
    nac["BLANCO"] = BLANCO_PCT / 100
    nac["OTROS"] = max(1 - nac.sum(), 0.005)
    return (nac / nac.sum()).reindex(base.columns)


def central(fecha: str = FECHA, ajuste=None):
    """
    Todo lo determinista del modelo: devuelve un dict con las piezas que usa el Monte Carlo.
    ajuste: función opcional nacional -> nacional (escenarios, p. ej. de participación).
    """
    from datos.familias import PROV_CCAA
    from motor.regional import cargar_encuestas_ccaa, objetivos_ccaa

    est = estimacion_nacional(fecha)
    base, presencia = base_2026()
    pesos = cargar("2023-07").validos
    nacional = objetivo_nacional(est, base, pesos)
    if ajuste is not None:
        nacional = ajuste(nacional)
    region_nac = pd.Series("España", index=base.index)
    obj_nac = nacional.to_frame("España").T
    s_nac = proyectar(base, pesos, obj_nac, region_nac, "logit", presencia)

    region = pd.Series(PROV_CCAA).reindex(base.index)
    enc_ccaa = cargar_encuestas_ccaa(fecha)
    obj_ccaa, sd_reg, diag = objetivos_ccaa(s_nac, pesos, region, nacional, enc_ccaa)
    s0 = proyectar(base, pesos, obj_ccaa, region, "logit", presencia)
    s0_unif = proyectar(base, pesos, obj_ccaa, region, "uniforme", presencia)
    return {"est": est, "base": base, "presencia": presencia, "pesos": pesos, "nacional": nacional,
            "s_nac": s_nac, "obj_ccaa": obj_ccaa, "sd_reg": sd_reg, "diag": diag, "region": region,
            "s0": s0, "s0_unif": s0_unif, "encuestas_ccaa": enc_ccaa}
