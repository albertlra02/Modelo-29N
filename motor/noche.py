"""
Noche electoral: proyección de escaños a partir de un escrutinio parcial (datos/escrutinio.py).

En cada provincia, la cuota final se estima mezclando lo escrutado con la predicción central del modelo, con el
peso del porcentaje escrutado: al 0 % es la predicción; al 100 %, el escrutinio. Es deliberadamente simple: no
corrige que unas mesas se cuenten antes que otras (en España suelen adelantarse las rurales, y eso favorece al
principio al PP y a Vox), así que con poco escrutado conviene mirar más la predicción.
"""
from __future__ import annotations

import pandas as pd

from motor.simulador import repartir


def alinear(cuotas: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """Cuotas del escrutinio con las columnas del modelo; lo que no está en el modelo pasa a OTROS."""
    fuera = [c for c in cuotas.columns if c not in columnas]
    out = cuotas.reindex(columns=columnas).fillna(0.0)
    if fuera and "OTROS" in out:
        out["OTROS"] += cuotas[fuera].fillna(0.0).sum(axis=1)
    return out


def proyectar(s0: pd.DataFrame, cuotas: pd.DataFrame, escrutado: pd.Series, escanos: pd.Series) -> tuple[
        pd.DataFrame, pd.DataFrame]:
    """(cuotas proyectadas, escaños por provincia). s0: predicción central (filas suman 1)."""
    c = alinear(cuotas, list(s0.columns)).reindex(s0.index)
    hay = c.sum(axis=1) > 0
    w = (escrutado.reindex(s0.index).fillna(0) / 100).where(hay, 0.0)
    s = s0.mul(1 - w, axis=0) + c.fillna(0).mul(w, axis=0)
    s = s.div(s.sum(axis=1), axis=0)
    return s, repartir(s, escanos)


def escanos_escrutados(columnas: list[str], cuotas: pd.DataFrame, escanos: pd.Series) -> pd.DataFrame:
    """Escaños con lo escrutado tal cual (D'Hondt no da ninguno en una provincia sin votos contados)."""
    return repartir(alinear(cuotas, columnas).fillna(0.0), escanos)
