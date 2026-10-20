"""
Familias de partidos comparables entre elecciones, y provincias -> CCAA.

Una "familia" agrupa las candidaturas que ocupan el mismo espacio de una
elección a otra (DL -> CDC -> JUNTS; Podemos/IU/Más País/Compromís -> SUMAR...).
Todo lo que no está mapeado va a OTROS.

Decisiones discutibles, documentadas:
  - IZQ (espacio a la izquierda del PSOE): Podemos y sus confluencias (vienen
    agregadas en la columna 'Podemos'), IU, Más País, Compromís, Més y CHA en
    2015-2019; SUMAR en 2023. Para 2026 habrá que decidir si Podemos va aparte.
  - CC incluye a NC en 2023 (en 2019 concurrieron juntos).
  - NAV_DCHA: Navarra Suma (UPN+PP+Cs) en 2019, UPN en 2023. En 2019 PP y Cs no
    concurrieron por separado en Navarra; es un cambio estructural real.
"""
from __future__ import annotations

import pandas as pd

FAMILIAS: dict[str, list[str]] = {
    "PP": ["PP"],
    "PSOE": ["PSOE"],
    "VOX": ["VOX"],
    "CS": ["Cs"],
    "IZQ": ["Podemos", "IU", "Más País", "Compromís", "Més", "CHA", "SUMAR"],
    "ERC": ["ERC"],
    "JUNTS": ["DL", "CDC", "JUNTS"],
    "PNV": ["PNV"],
    "BILDU": ["EH BILDU"],
    "BNG": ["BNG"],
    "CC": ["CC", "NC"],
    "NAV_DCHA": ["NA+", "UPN"],
    "CUP": ["CUP"],
    "PRC": ["PRC"],
    "TERUEL": ["Teruel Existe"],
}
OTROS = "OTROS"

CCAA: dict[str, list[str]] = {
    "Andalucía": ["Almería", "Cádiz", "Córdoba", "Granada", "Huelva", "Jaén", "Málaga", "Sevilla"],
    "Aragón": ["Huesca", "Teruel", "Zaragoza"],
    "Asturias": ["Asturias"],
    "Baleares": ["Illes Balears"],
    "Canarias": ["Las Palmas", "Santa Cruz de Tenerife"],
    "Cantabria": ["Cantabria"],
    "Castilla y León": ["Ávila", "Burgos", "León", "Palencia", "Salamanca", "Segovia",
                        "Soria", "Valladolid", "Zamora"],
    "Castilla-La Mancha": ["Albacete", "Ciudad Real", "Cuenca", "Guadalajara", "Toledo"],
    "Cataluña": ["Barcelona", "Girona", "Lleida", "Tarragona"],
    "C. Valenciana": ["Alacant/Alicante", "Castelló/Castellón", "València/Valencia"],
    "Extremadura": ["Badajoz", "Cáceres"],
    "Galicia": ["A Coruña", "Lugo", "Ourense", "Pontevedra"],
    "Madrid": ["Madrid"],
    "Murcia": ["Murcia"],
    "Navarra": ["Navarra"],
    "País Vasco": ["Araba/Álava", "Bizkaia", "Gipuzkoa"],
    "La Rioja": ["La Rioja"],
    "Ceuta": ["Ceuta"],
    "Melilla": ["Melilla"],
}
PROV_CCAA = {p: c for c, ps in CCAA.items() for p in ps}


def a_familias(votos: pd.DataFrame) -> pd.DataFrame:
    """Votos por candidatura -> votos por familia (+ OTROS). Mismas filas."""
    asignadas = set()
    out = {}
    for fam, cands in FAMILIAS.items():
        cols = [c for c in cands if c in votos.columns]
        out[fam] = votos[cols].sum(axis=1) if cols else 0
        asignadas.update(cols)
    resto = [c for c in votos.columns if c not in asignadas]
    out[OTROS] = votos[resto].sum(axis=1)
    return pd.DataFrame(out, index=votos.index).astype(int)
