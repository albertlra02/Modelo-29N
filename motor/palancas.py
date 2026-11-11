"""
Palancas de escenario sobre la proyección central, antes de simular (mueven Congreso, Senado y mayorías):

  - Movilización por bloque: el voto de la izquierda, la derecha o los nacionalistas y regionalistas sube o baja
    un porcentaje en toda España o en una sola comunidad. Es participación diferencial: los demás votos no
    cambian, así que las cuotas se renormalizan en cada provincia y la participación total se mueve con ella.
  - Voto útil: una parte de los votantes de un partido pasa a otro, en todas las provincias o sólo donde el de
    origen no saca escaño en la proyección central (D'Hondt sobre el voto sin simular).

No son estimaciones sino supuestos que elige quien mira: el modelo dice qué pasaría si se cumplen.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from datos.cargar import escanos_2026
from datos.familias import CCAA, PROV_CCAA
from motor.escanos import dhondt_vectorizado

BLOQUES_MOV = {
    "izda": ["PSOE", "FRENTE_AMPLIO", "PODEMOS", "ADELANTE"],
    "dcha": ["PP", "VOX", "SALF", "UPN"],
    "nac": ["ERC", "JUNTS", "BILDU", "PNV", "BNG", "CC", "NC", "TERUEL", "UPL", "SORIA_YA"],
}
NOMBRES_BLOQUE = {"izda": "la izquierda", "dcha": "la derecha", "nac": "nacionalistas y regionalistas"}
# clave -> (origen, destino)
TRASVASES = {
    "pod_fa": ("PODEMOS", "FRENTE_AMPLIO"),
    "fa_psoe": ("FRENTE_AMPLIO", "PSOE"),
    "vox_pp": ("VOX", "PP"),
    "salf_vox": ("SALF", "VOX"),
}
AMBITOS = ("España",) + tuple(CCAA)
LIMITE_MOV, LIMITE_UTIL = 20, 50          # % máximos que admite la web


@dataclass(frozen=True)
class Palancas:
    mov_izda: int = 0          # % de cambio del voto del bloque
    mov_dcha: int = 0
    mov_nac: int = 0
    mov_ambito: str = "España"
    util_pod_fa: int = 0       # % de los votantes del origen que pasan al destino
    util_fa_psoe: int = 0
    util_vox_pp: int = 0
    util_salf_vox: int = 0
    util_sin_escano: bool = True   # sólo donde el origen no saca escaño

    @property
    def activas(self) -> bool:
        return self != Palancas(mov_ambito=self.mov_ambito, util_sin_escano=self.util_sin_escano)

    def movilizacion(self) -> dict[str, int]:
        return {b: getattr(self, f"mov_{b}") for b in BLOQUES_MOV if getattr(self, f"mov_{b}")}

    def trasvases(self) -> dict[str, int]:
        return {k: getattr(self, f"util_{k}") for k in TRASVASES if getattr(self, f"util_{k}")}


def sin_escano(s0: pd.DataFrame, partido: str) -> pd.Series:
    """Provincias en que `partido` no saca escaño con el voto central (D'Hondt con el 3 %)."""
    esc = escanos_2026()
    listas = [p for p in s0.columns if p not in ("OTROS", "BLANCO")]
    j = listas.index(partido)
    out = {}
    for prov, fila in s0.iterrows():
        blancos = fila.drop(listas).sum()
        out[prov] = dhondt_vectorizado(fila[listas].to_numpy()[None], int(esc[prov]), blancos)[0, j] == 0
    return pd.Series(out)


def _cambio(df: pd.DataFrame, filas: np.ndarray, pal: Palancas, donde_util: dict[str, np.ndarray]) -> pd.DataFrame:
    df = df.copy()
    for b, pct in pal.movilizacion().items():
        cols = [p for p in BLOQUES_MOV[b] if p in df]
        df.loc[filas, cols] *= 1 + pct / 100
    for k, pct in pal.trasvases().items():
        o, d = TRASVASES[k]
        if o not in df or d not in df:
            continue
        m = donde_util[k] & (df[d] > 0).to_numpy()
        pasa = df.loc[m, o] * pct / 100
        df.loc[m, o] -= pasa
        df.loc[m, d] += pasa
    return df.div(df.sum(axis=1), axis=0)


def aplicar(c: dict, pal: Palancas) -> dict:
    """Devuelve las piezas centrales con las palancas aplicadas (s0, s0_unif, base, obj_ccaa y nacional)."""
    if not pal.activas:
        return c
    c = dict(c)
    s0 = c["s0"]
    ccaa = s0.index.map(PROV_CCAA)
    filas = np.ones(len(s0), bool) if pal.mov_ambito == "España" else np.asarray(ccaa == pal.mov_ambito)
    todas = np.ones(len(s0), bool)
    # dónde se aplica cada trasvase: decidido con el voto central ya movilizado (antes de trasvasar)
    movil = _cambio(s0, filas, Palancas(pal.mov_izda, pal.mov_dcha, pal.mov_nac, pal.mov_ambito), {})
    donde = {}
    for k in pal.trasvases():
        o, d = TRASVASES[k]
        if o not in s0 or d not in s0:
            continue
        m = sin_escano(movil, o).reindex(s0.index).to_numpy() if pal.util_sin_escano else todas
        donde[k] = m & (s0[o] > 0).to_numpy() & (s0[d] > 0).to_numpy()
    for k in ("s0", "s0_unif", "base"):
        c[k] = _cambio(c[k], filas, pal, donde)
    w = c["pesos"].reindex(c["s0"].index)
    c["obj_ccaa"] = c["s0"].mul(w, axis=0).groupby(ccaa).sum().div(w.groupby(ccaa).sum(), axis=0)
    c["nacional"] = c["s0"].mul(w, axis=0).sum() / w.sum()
    c["palancas_donde"] = {k: list(s0.index[v]) for k, v in donde.items()}
    return c
