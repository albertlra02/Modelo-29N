"""
Escrutinio de la noche electoral (datos/escrutinio/escrutinio.csv), para la página /noche.

Formato: una fila por provincia (los nombres de datos/raw/, p. ej. "València/Valencia"):
  provincia, escrutado (% de mesas, 0-100), blancos, <una columna por candidatura con su clave del modelo:
  PP, PSOE, VOX, FRENTE_AMPLIO, PODEMOS, ERC…>, OTROS (opcional)
Votos en número. Las provincias que falten se toman como 0 % escrutado. Lo que no sea una candidatura del modelo
va a OTROS (cuenta para el 3 % pero no saca escaños).

El fichero se puede rellenar a mano o convertir desde la fuente oficial que haya esa noche. Para probar la página
antes de la noche: `python -m scripts.escrutinio simulacro --avance 40` lo genera con los votos reales de 2023.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from datos.cargar import cargar

CARPETA = Path(__file__).parent / "escrutinio"
RUTA = CARPETA / "escrutinio.csv"
MARCA_SIMULACRO = CARPETA / "SIMULACRO"     # existe si el escrutinio es el de prueba (lo crea y borra el script)
META = ("provincia", "escrutado", "blancos")

# Candidatura de 2023 -> clave del modelo (para el simulacro; Sumar 2023 -> Frente Amplio)
DESDE_2023 = {"PP": "PP", "PSOE": "PSOE", "VOX": "VOX", "SUMAR": "FRENTE_AMPLIO", "ERC": "ERC", "JUNTS": "JUNTS",
              "EH BILDU": "BILDU", "PNV": "PNV", "BNG": "BNG", "CC": "CC", "NC": "NC", "UPN": "UPN", "UPL": "UPL",
              "Teruel Existe": "TERUEL", "Soria ¡Ya!": "SORIA_YA", "Adelante And.": "ADELANTE"}


def leer(ruta: Path = RUTA, provincias: list[str] | None = None) -> pd.DataFrame | None:
    """Escrutinio como DataFrame (índice: provincia; columnas: escrutado, blancos y votos). None si no hay fichero."""
    if not ruta.exists():
        return None
    df = pd.read_csv(ruta)
    faltan = [c for c in META if c not in df.columns]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan columnas {faltan}")
    df["provincia"] = df["provincia"].str.strip()
    df = df.set_index("provincia")
    if provincias is not None:
        desconocidas = sorted(set(df.index) - set(provincias))
        if desconocidas:
            raise ValueError(f"{ruta.name}: provincias desconocidas {desconocidas}")
        df = df.reindex(provincias)
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0)
    df["escrutado"] = df["escrutado"].clip(0, 100)
    return df


def cuotas(esc: pd.DataFrame) -> pd.DataFrame:
    """Cuota de cada candidatura (y BLANCO) sobre votos válidos, por provincia (NaN donde no hay votos)."""
    votos = esc.drop(columns=["escrutado", "blancos"]).copy()
    votos["BLANCO"] = esc["blancos"]
    validos = votos.sum(axis=1)
    return votos.div(validos.where(validos > 0), axis=0)


def simulacro(avance: float, semilla: int = 29) -> pd.DataFrame:
    """Escrutinio parcial de prueba con los votos reales de 2023: cada provincia lleva un % escrutado alrededor de
    `avance` y sus votos son los de 2023 escalados a ese porcentaje."""
    b = cargar("2023-07")
    rng = np.random.default_rng(semilla)
    escr = np.clip(avance + rng.normal(0, 12, len(b.votos)), 0, 100).round(1) if avance < 100 else np.full(
        len(b.votos), 100.0)
    out = pd.DataFrame(index=b.votos.index)
    out.index.name = "provincia"
    out["escrutado"] = escr
    f = escr / 100
    out["blancos"] = (b.meta["blancos"] * f).round().astype(int)
    for c23, clave in DESDE_2023.items():
        if c23 in b.votos:
            out[clave] = (b.votos[c23] * f).round().astype(int)
    resto = [c for c in b.votos.columns if c not in DESDE_2023]
    out["OTROS"] = (b.votos[resto].sum(axis=1) * f).round().astype(int)
    return out
