"""
Paso de voto agregado (nacional o autonómico) a voto por circunscripción.

Partimos de las cuotas provinciales de una elección base y las ajustamos para
que, agregadas por región (España entera o cada CCAA), cuadren con unas cuotas
objetivo (las de una encuesta o, en el backtest, las reales).

Métodos de ajuste por familia:
  uniforme      s_i + c          (todas las provincias suben/bajan los mismos puntos)
  proporcional  s_i * k          (cada provincia se mueve en proporción a su base)
  logit         sigma(logit(s_i) + d)  (proporcional en el centro, frena en los extremos)

OTROS y BLANCO siempre se ajustan de forma proporcional.

Procedimiento (tipo IPF): se alterna
  1) ajustar cada columna para que cuadre con su objetivo en cada región,
  2) renormalizar cada provincia para que sus cuotas sumen 1,
hasta que converja.

Presencia: una familia que no se presenta en una provincia queda a 0 ahí.
Si una familia se presenta donde no lo hizo en la base (p. ej. Vox en
Santa Cruz de Tenerife 2023 -> 2026), se siembra con su cuota media en las
provincias de la misma región en las que sí estaba (o la nacional si no hay).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from motor.escanos import dhondt_exacto

METODOS = ("uniforme", "proporcional", "logit")
SIEMPRE_PROPORCIONAL = ("OTROS", "BLANCO")
_EPS = 1e-9


def _sigma(x):
    return 1.0 / (1.0 + np.exp(-x))


def _logit(p):
    p = np.clip(p, _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def _ajustar_columna(s: np.ndarray, w: np.ndarray, W: float, objetivo: float, metodo: str) -> np.ndarray:
    """
    Ajusta las cuotas s de las provincias donde la familia se presenta para que
    sum(w*s) / W = objetivo, con W el tamaño de TODA la región (también las
    provincias donde no se presenta: el objetivo es una cuota sobre la región).
    """
    if len(s) == 0:
        return s
    if objetivo <= 0:
        return np.zeros_like(s)
    if metodo == "uniforme":
        c = (objetivo * W - (w * s).sum()) / w.sum()
        return np.clip(s + c, 0.0, 1.0)
    if metodo == "proporcional":
        actual = (w * s).sum() / W
        return s * (objetivo / actual) if actual > 0 else np.full_like(s, objetivo)
    if metodo == "logit":
        z = _logit(s)
        lo, hi = -30.0, 30.0
        for _ in range(80):  # bisección: la media ponderada es monótona en d
            d = 0.5 * (lo + hi)
            if (w * _sigma(z + d)).sum() / W < objetivo:
                lo = d
            else:
                hi = d
        return _sigma(z + 0.5 * (lo + hi))
    raise ValueError(metodo)


def proyectar(
    base: pd.DataFrame,
    pesos: pd.Series,
    objetivos: pd.DataFrame,
    region: pd.Series,
    metodo: str,
    presencia: pd.DataFrame | None = None,
    iteraciones: int = 50,
) -> pd.DataFrame:
    """
    base:      cuotas base (provincia x columna), filas suman 1. Columnas: familias + OTROS + BLANCO.
    pesos:     tamaño de cada provincia (votos válidos base) para agregar por región.
    objetivos: cuotas objetivo (región x columna), filas suman 1.
    region:    provincia -> región (la misma clave que el índice de `objetivos`).
    presencia: bool (provincia x columna); por defecto, presente donde la base > 0.
    Devuelve cuotas proyectadas (provincia x columna), filas suman 1.
    """
    cols = list(objetivos.columns)
    s = base.reindex(columns=cols, fill_value=0.0).astype(float).copy()
    pres = (s > 0) if presencia is None else presencia.reindex(index=s.index, columns=cols, fill_value=False)
    for c in SIEMPRE_PROPORCIONAL:
        if c in pres:
            pres[c] = True

    # Sembrar presencias nuevas y anular ausencias
    for c in cols:
        nuevas = pres[c] & (s[c] <= 0)
        for prov in s.index[nuevas]:
            mismas = (region == region[prov]) & pres[c] & (s[c] > 0)
            ref = s.loc[mismas, c] if mismas.any() else s.loc[s[c] > 0, c]
            s.at[prov, c] = float(np.average(ref, weights=pesos[ref.index])) if len(ref) else 0.01
    s = s.where(pres, 0.0)
    s = s.div(s.sum(axis=1), axis=0)

    # Bucle IPF en numpy (en pandas era ~100x más lento: miles de .loc por llamada)
    regiones = list(objetivos.index)
    reg = region.reindex(s.index).to_numpy()
    w = pesos.reindex(s.index).to_numpy(float)
    W_region = pesos.groupby(region.reindex(pesos.index)).sum()
    S = s.to_numpy(float, copy=True)
    P = pres.to_numpy(bool)
    obj = objetivos.reindex(columns=cols).to_numpy(float)
    grupos = []   # (columna, región) -> índices de provincias presentes
    for j, c in enumerate(cols):
        m = metodo if c not in SIEMPRE_PROPORCIONAL else "proporcional"
        for i, r in enumerate(regiones):
            idx = np.flatnonzero((reg == r) & P[:, j])
            grupos.append((j, idx, w[idx], float(W_region[r]), float(obj[i, j]), m))
    for _ in range(iteraciones):
        for j, idx, wi, Wr, o, m in grupos:
            S[idx, j] = _ajustar_columna(S[idx, j], wi, Wr, o, m)
        S = S / S.sum(axis=1, keepdims=True)
    s = pd.DataFrame(S, index=s.index, columns=cols)
    return s


def escanos_desde_cuotas(c: pd.DataFrame, validos: pd.Series, diputados: pd.Series) -> pd.DataFrame:
    """D'Hondt con familias como listas. OTROS y BLANCO cuentan para el 3% pero no reciben escaño."""
    filas = {}
    for prov in c.index:
        v = (c.loc[prov] * validos[prov]).round().astype(int)
        no_lista = int(sum(v.get(k, 0) for k in SIEMPRE_PROPORCIONAL))
        listas = {k: int(x) for k, x in v.items() if k not in SIEMPRE_PROPORCIONAL and x > 0}
        filas[prov] = dhondt_exacto(listas, int(diputados[prov]), no_lista)
    return pd.DataFrame.from_dict(filas, orient="index").fillna(0).astype(int)
