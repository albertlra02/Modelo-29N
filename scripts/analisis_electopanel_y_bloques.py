"""
Dos análisis de apoyo (12/10/2026):

1) ElectoPanel provincial (datos/encuestas/electopanel_provincias_2026-10-12.csv):
   - escaños con nuestro motor vs los que publica Electomanía
   - cómo reparte el voto por provincias respecto a 2023 (¿uniforme o proporcional?)
   - cuánto se parece a nuestro swing por CCAA

2) Votos absolutos por bloque 2015-2023 y su relación con la participación
   (la tesis de que la derecha es estable y la participación decide).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from validacion.backtest_swing import REGION_CCAA, cuotas, objetivos_por_region
from datos.cargar import ELECCIONES, cargar, escanos_2026
from datos.familias import FAMILIAS, a_familias
from motor.escanos import dhondt_exacto
from motor.swing import proyectar

EP = Path("datos/encuestas/electopanel_provincias_2026-10-12.csv")


def electopanel():
    FAMILIAS["IZQ"] = FAMILIAS["IZQ"] + ["Compromis"]
    FAMILIAS["ADELANTE"] = ["AA", "Adelante And."]  # misma candidatura en dos columnas
    FAMILIAS["SALF"] = ["SALF"]
    ep, b23 = cargar("ep", EP), cargar("2023-07")
    e26 = escanos_2026()

    esc = {}
    for p in ep.votos.index:
        v = {k: int(x) for k, x in ep.votos.loc[p].items() if x > 0 and k != "OTROS"}
        esc[p] = dhondt_exacto(v, int(e26[p]), int(ep.meta.at[p, "blancos"] + ep.votos.at[p, "OTROS"]))
    tot = pd.DataFrame.from_dict(esc, orient="index").fillna(0).astype(int).sum()
    print("Escaños (reparto 2026) con nuestro motor:", tot[tot > 0].sort_values(ascending=False).to_dict())

    E, B = cuotas(ep), cuotas(b23)
    cols = sorted(set(E) | set(B))
    E, B = E.reindex(columns=cols, fill_value=0), B.reindex(columns=cols, fill_value=0)
    print("\ncuota_EP = a + b·cuota_2023 (uniforme: b=1 | proporcional: a=0)")
    for f in ["PP", "PSOE", "VOX", "IZQ"]:
        x, y = 100 * B[f], 100 * E[f]
        b, a = np.polyfit(x, y, 1, w=np.sqrt(b23.validos))
        print(f"  {f:5s} a={a:+5.2f} b={b:4.2f}")

    for nombre, region in [("nacional", pd.Series("España", index=B.index)), ("ccaa", REGION_CCAA)]:
        obj = objetivos_por_region(ep, region).reindex(columns=cols, fill_value=0)
        p = proyectar(B, b23.validos, obj, region, "logit", E > 0)
        fam = [c for c in cols if c not in ("BLANCO", "OTROS")]
        mae = 100 * (p[fam] - E[fam]).abs()[(p[fam] > 0.01) | (E[fam] > 0.01)].stack().mean()
        print(f"  swing logit {nombre}: MAE vs ElectoPanel provincial = {mae:.2f} pp")


def bloques():
    DCHA, IZQ = ["PP", "CS", "VOX", "NAV_DCHA"], ["PSOE", "IZQ"]
    filas = []
    for e in ELECCIONES:
        E = cargar(e)
        F = a_familias(E.votos).sum()
        filas.append({"eleccion": e, "participacion": 100 * E.votantes.sum() / E.meta.censo.sum(),
                      "derecha_M": F[DCHA].sum() / 1e6, "izquierda_M": F[IZQ].sum() / 1e6})
    d = pd.DataFrame(filas).set_index("eleccion").round(2)
    print("\n", d.to_string())
    print("corr. con participación: derecha %.2f | izquierda %.2f"
          % (d.derecha_M.corr(d.participacion), d.izquierda_M.corr(d.participacion)))


if __name__ == "__main__":
    electopanel()
    bloques()
