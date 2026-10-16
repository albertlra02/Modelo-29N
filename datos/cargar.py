"""
Carga de resultados oficiales del Congreso por circunscripción.

Fuente: Ministerio del Interior (infoelectoral). Los CSV se generan con `python datos/oficiales.py`
a partir de los ficheros oficiales guardados en datos/raw/infoelectoral/; no se editan a mano.

Formato de los CSV (datos/raw/congreso_AAAA-MM.csv):
  fila 1: #color   -> color por candidatura (opcional)
  fila 2: #bloque  -> 'derecha' / 'izquierda' para algunas candidaturas
  fila 3: cabecera -> provincia, censo, votos_nulos, diputados, <candidaturas...>, Voto en blanco
  resto:  una fila por circunscripción (52)

Ojo: "Escaños en Blanco" es una candidatura, no el voto en blanco.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

RAW = Path(__file__).parent / "raw"
COLS_META = ["provincia", "censo", "votos_nulos", "diputados"]
COL_BLANCO = "Voto en blanco"

ELECCIONES = {
    "2015-12": "congreso_2015-12.csv",
    "2016-06": "congreso_2016-06.csv",
    "2019-04": "congreso_2019-04.csv",
    "2019-11": "congreso_2019-11.csv",
    "2023-07": "congreso_2023-07.csv",
}


@dataclass
class Eleccion:
    id: str
    meta: pd.DataFrame            # index provincia: censo, votos_nulos, diputados, blancos
    votos: pd.DataFrame           # index provincia, columnas candidaturas (enteros, 0 si no se presenta)
    color: dict[str, str] = field(default_factory=dict)
    bloque: dict[str, str] = field(default_factory=dict)

    @property
    def candidaturas(self) -> list[str]:
        return list(self.votos.columns)

    @property
    def validos(self) -> pd.Series:
        return self.votos.sum(axis=1) + self.meta["blancos"]

    @property
    def votantes(self) -> pd.Series:
        return self.validos + self.meta["votos_nulos"]

    def resumen_nacional(self) -> pd.DataFrame:
        v = self.votos.sum().sort_values(ascending=False)
        return pd.DataFrame({"votos": v, "pct_validos": 100 * v / self.validos.sum()})


def _leer_filas(eleccion: str, ruta: Path | None = None) -> tuple[list[str], list[str], list[str], list[list[str]]]:
    ruta = ruta or RAW / ELECCIONES[eleccion]
    with ruta.open(encoding="utf-8") as f:
        filas = list(csv.reader(f))
    color_row, bloque_row, cabecera, datos = filas[0], filas[1], filas[2], filas[3:]

    anchos = {len(r) for r in datos}
    if anchos != {len(cabecera)}:
        raise ValueError(f"{eleccion}: cabecera con {len(cabecera)} columnas, datos con {anchos}")
    return color_row, bloque_row, cabecera, datos


def cargar(eleccion: str, ruta: Path | None = None) -> Eleccion:
    """Carga una elección de ELECCIONES, o cualquier fichero con el mismo formato
    (p. ej. una encuesta provincial) si se pasa `ruta`."""
    color_row, bloque_row, cabecera, datos = _leer_filas(eleccion, ruta)

    df = pd.DataFrame(datos, columns=cabecera).replace({"null": None, "": None})
    df["provincia"] = df["provincia"].str.strip()
    df = df.set_index("provincia").sort_index()
    df = df.apply(pd.to_numeric)

    partidos = [c for c in df.columns if c not in COLS_META + [COL_BLANCO]]
    votos = df[partidos].fillna(0).astype(int)
    meta = df[["censo", "votos_nulos", "diputados"]].astype(int).copy()
    meta["blancos"] = df[COL_BLANCO].fillna(0).astype(int)

    color = {c: v for c, v in zip(cabecera, color_row) if c in partidos and v.startswith("#") and len(v) > 1}
    bloque = {c: v for c, v in zip(cabecera, bloque_row) if c in partidos and v in ("derecha", "izquierda")}

    assert len(meta) == 52, f"{eleccion}: {len(meta)} circunscripciones"
    assert meta["diputados"].sum() == 350, f"{eleccion}: {meta['diputados'].sum()} diputados"
    return Eleccion(eleccion, meta, votos, color, bloque)


def escanos_2026() -> pd.Series:
    """Reparto de 2026: el de 2023 con los cambios del decreto de convocatoria."""
    esc = cargar("2023-07").meta["diputados"].copy()
    esc["Madrid"] += 1   # 37 -> 38
    esc["Cádiz"] -= 1    # 9 -> 8
    assert esc.sum() == 350
    return esc
