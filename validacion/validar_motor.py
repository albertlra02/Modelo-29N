"""
Paso 2: el motor de escaños debe reproducir el Congreso real de cada elección.

Referencia: escaños oficiales por candidatura a nivel nacional. Las confluencias
de Podemos (En Comú, En Marea, Compromís-Podemos...) vienen agregadas en la
columna 'Podemos' del fichero, así que se comparan con el total del grupo.
"""
import sys

import numpy as np
import pandas as pd

from scripts.consola import configurar_salida_utf8
from datos.cargar import ELECCIONES, cargar, escanos_2026
from motor.escanos import dhondt_exacto, dhondt_vectorizado

REFERENCIA = {
    "2015-12": {"PP": 123, "PSOE": 90, "Podemos": 69, "Cs": 40, "ERC": 9, "DL": 8,
                "PNV": 6, "IU": 2, "EH BILDU": 2, "CC": 1},
    "2016-06": {"PP": 137, "PSOE": 85, "Podemos": 71, "Cs": 32, "ERC": 9, "CDC": 8,
                "PNV": 5, "EH BILDU": 2, "CC": 1},
    "2019-04": {"PSOE": 123, "PP": 66, "Cs": 57, "Podemos": 42, "VOX": 24, "ERC": 15,
                "JUNTS": 7, "PNV": 6, "EH BILDU": 4, "CC": 2, "NA+": 2, "Compromís": 1, "PRC": 1},
    "2019-11": {"PSOE": 120, "PP": 89, "VOX": 52, "Podemos": 35, "ERC": 13, "Cs": 10,
                "JUNTS": 8, "PNV": 6, "EH BILDU": 5, "Más País": 2, "CUP": 2, "CC": 2,
                "NA+": 2, "Compromís": 1, "BNG": 1, "PRC": 1, "Teruel Existe": 1},
    "2023-07": {"PP": 137, "PSOE": 121, "VOX": 33, "SUMAR": 31, "ERC": 7, "JUNTS": 7,
                "EH BILDU": 6, "PNV": 5, "BNG": 1, "CC": 1, "UPN": 1},
}


def repartir(e) -> pd.DataFrame:
    filas = {}
    for prov in e.votos.index:
        votos = {p: int(v) for p, v in e.votos.loc[prov].items() if v > 0}
        filas[prov] = dhondt_exacto(votos, int(e.meta.at[prov, "diputados"]), int(e.meta.at[prov, "blancos"]))
    return pd.DataFrame.from_dict(filas, orient="index").fillna(0).astype(int)


def main() -> int:
    configurar_salida_utf8()
    fallos = 0
    for eid in ELECCIONES:
        e = cargar(eid)
        esc = repartir(e)
        nacional = esc.sum()
        nacional = nacional[nacional > 0].sort_values(ascending=False)
        ref = pd.Series(REFERENCIA[eid]).sort_values(ascending=False)
        comp = pd.DataFrame({"motor": nacional, "oficial": ref}).fillna(0).astype(int)
        diff = comp[comp.motor != comp.oficial]

        # La versión vectorizada debe coincidir provincia a provincia
        vec_ok = all(
            (dhondt_vectorizado(e.votos.loc[[p]].to_numpy(), int(e.meta.at[p, "diputados"]),
                                float(e.meta.at[p, "blancos"]))[0]
             == esc.reindex(columns=e.votos.columns, fill_value=0).loc[p].to_numpy()).all()
            for p in e.votos.index
        )

        estado = "OK " if diff.empty and vec_ok else "FALLO"
        fallos += estado == "FALLO"
        resumen = ", ".join(f"{p} {n}" for p, n in nacional.items())
        print(f"[{estado}] {eid}  {resumen}")
        if not diff.empty:
            print(diff.to_string())
        if not vec_ok:
            print("   la versión vectorizada no coincide con la exacta")

    esc26 = escanos_2026()
    cambios = esc26 - cargar("2023-07").meta["diputados"]
    print("\nEscaños 2026:", int(esc26.sum()), "| cambios vs 2023:",
          ", ".join(f"{p} {int(esc26[p])} ({c:+d})" for p, c in cambios[cambios != 0].items()))
    return fallos


if __name__ == "__main__":
    sys.exit(main())
