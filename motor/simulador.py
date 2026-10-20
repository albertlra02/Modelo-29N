"""
Simulador "¿y si…?": el usuario fija el voto nacional de algunos partidos y se recalcula el reparto, sin
Monte Carlo (es la proyección central desplazada, no una predicción con incertidumbre).

1. Objetivos nacionales: los partidos tocados quedan en lo que pide el usuario; los demás (incluidos voto en
   blanco y «otros») se escalan en proporción para que todo sume 100.
2. Reparto provincial: se desplaza la cuota de cada partido en todas las provincias con el mismo término en
   escala logit (como el swing del modelo) hasta que la media nacional ponderada por votos válidos de 2023 cuadra
   con el objetivo (ajuste proporcional iterativo). Un partido que no se presenta en una provincia sigue sin
   presentarse.
3. D'Hondt en cada provincia, con el 3 % sobre votos válidos (blanco y «otros» cuentan para el umbral).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from motor.escanos import dhondt_vectorizado

NO_LISTAS = ("OTROS", "BLANCO")


def objetivos(nacional: pd.Series, fijados: dict[str, float]) -> pd.Series:
    """Cuotas nacionales objetivo (suman 1). nacional: cuotas actuales; fijados: {partido: cuota pedida}."""
    fijados = {p: float(np.clip(v, 0.0, 1.0)) for p, v in fijados.items() if p in nacional.index}
    resto = [p for p in nacional.index if p not in fijados]
    libre = max(0.0, 1.0 - sum(fijados.values()))
    base = nacional[resto].sum()
    out = nacional.copy().astype(float)
    for p, v in fijados.items():
        out[p] = v
    out[resto] = nacional[resto] * (libre / base) if base > 0 else 0.0
    return out / out.sum()


def ajustar(s0: pd.DataFrame, pesos: pd.Series, objetivo: pd.Series, iteraciones: int = 200) -> pd.DataFrame:
    """Cuotas provinciales (filas suman 1) cuya media ponderada por `pesos` es `objetivo`."""
    s = s0.to_numpy(dtype=float)
    w = (pesos.reindex(s0.index) / pesos.reindex(s0.index).sum()).to_numpy()
    t = objetivo.reindex(s0.columns).fillna(0.0).to_numpy()
    b = np.zeros(s.shape[1])
    for _ in range(iteraciones):
        x = s * np.exp(b)
        x /= x.sum(axis=1, keepdims=True)
        nac = w @ x
        con = (nac > 0) & (t > 0)
        paso = np.zeros_like(b)
        paso[con] = np.log(t[con] / nac[con])
        b += paso
        b[(t == 0)] = -50.0                    # un partido con objetivo 0 desaparece
        if np.abs(paso).max() < 1e-7:
            break
    x = s * np.exp(b)
    x /= x.sum(axis=1, keepdims=True)
    return pd.DataFrame(x, index=s0.index, columns=s0.columns)


def nacional_de(s: pd.DataFrame, pesos: pd.Series) -> pd.Series:
    w = pesos.reindex(s.index) / pesos.reindex(s.index).sum()
    return (s.mul(w, axis=0)).sum()


def repartir(s: pd.DataFrame, escanos: pd.Series) -> pd.DataFrame:
    """Escaños por provincia (filas) y candidatura (columnas) con D'Hondt sobre cuotas."""
    listas = [p for p in s.columns if p not in NO_LISTAS]
    fuera = [p for p in s.columns if p in NO_LISTAS]
    filas = {}
    for prov in s.index:
        filas[prov] = dhondt_vectorizado(s.loc[prov, listas].to_numpy()[None, :], int(escanos[prov]),
                                         float(s.loc[prov, fuera].sum()))[0]
    return pd.DataFrame.from_dict(filas, orient="index", columns=listas)


def simular(s0: pd.DataFrame, pesos: pd.Series, escanos: pd.Series,
            fijados: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(cuotas provinciales, escaños por provincia) con el voto nacional de `fijados` (cuotas, no %)."""
    obj = objetivos(nacional_de(s0, pesos), fijados)
    s = ajustar(s0, pesos, obj) if fijados else s0
    return s, repartir(s, escanos)
