"""
Backtest del modelo completo: el 23J de 2023 visto desde N días antes.

Base: resultado del 10N por provincia. Objetivos: agregador con las encuestas
disponibles en la fecha de corte. Sin encuestas autonómicas (no las tenemos para
2023), así que la capa CCAA usa solo el prior. Candidaturas: las que realmente
concurrieron (se conocían antes de la elección).

Pregunta: ¿el resultado real cae dentro de los intervalos que daba el modelo?
"""
import sys

import numpy as np
import pandas as pd

from scripts.consola import configurar_salida_utf8
from validacion.backtest_swing import escanos_reales
from datos.cargar import cargar
from datos.familias import PROV_CCAA, a_familias
from motor.agregador import agregar, preparar
from motor.montecarlo import resumen, simular
from motor.regional import K_REG
from motor.swing import proyectar

ELECCION = pd.Timestamp("2023-07-23")
# familia del modelo <- columna de las encuestas de 2023
ENCUESTADOS = {"PP": "PP", "PSOE": "PSOE", "VOX": "VOX", "IZQ": "SUMAR", "ERC": "ERC", "JUNTS": "JUNTS",
               "PNV": "PNV", "BILDU": "BILDU", "CUP": "CUP", "CC": "CC", "BNG": "BNG", "NAV_DCHA": "UPN"}
ESTATALES = ("PP", "PSOE", "VOX", "IZQ")
BLOQUES = {"PP": -1, "VOX": -1, "NAV_DCHA": -1, "PSOE": +1, "IZQ": +1}


def main(dias=30, n_sim=10_000):
    configurar_salida_utf8()
    corte = ELECCION - pd.Timedelta(days=dias)
    b, t = cargar("2019-11"), cargar("2023-07")
    f = a_familias(b.votos); f["BLANCO"] = b.meta.blancos
    base = f.div(f.sum(axis=1), axis=0)
    real_f = a_familias(t.votos)
    presencia = (real_f > 0).reindex(columns=base.columns, fill_value=False)
    presencia[["OTROS", "BLANCO"]] = True
    pesos = b.validos

    nac = pd.read_csv("datos/encuestas/nacionales.csv")
    enc = preparar(nac[nac.ciclo == "2023"], corte)
    obj = {}
    for fam, col in ENCUESTADOS.items():
        obj[fam] = agregar(enc, col, corte).final[0] / 100 if enc[col].notna().sum() >= 5 else np.nan
    obj = pd.Series(obj)
    agg_base = base.mul(pesos, axis=0).sum() / pesos.sum()
    nacional = agg_base.copy()
    nacional[obj.dropna().index] = obj.dropna()
    nacional[~presencia.any()] = 0
    nacional["BLANCO"] = 0.008
    nacional["OTROS"] = 0
    nacional["OTROS"] = max(1 - nacional.sum(), 0.005)
    nacional /= nacional.sum()

    region = pd.Series(PROV_CCAA).reindex(base.index)
    obj_nac = nacional.to_frame("España").T
    nac_reg = pd.Series("España", index=base.index)
    s0 = proyectar(base, pesos, obj_nac, nac_reg, "logit", presencia)
    s0_alt = proyectar(base, pesos, obj_nac, nac_reg, "uniforme", presencia)
    s_reg = s0.mul(pesos, axis=0).groupby(region).sum().div(pesos.groupby(region).sum(), axis=0)
    sd_reg = K_REG * np.sqrt(s_reg * (1 - s_reg))

    sim = simular(s0, s0_alt, nacional, region, sd_reg, t.meta.diputados, pesos, dias, BLOQUES,
                  estatales=ESTATALES, n_sim=n_sim)
    tabla, probs = resumen(sim, {"PP + Vox": ["PP", "VOX"], "PP + Vox + UPN": ["PP", "VOX", "NAV_DCHA"]})
    real = escanos_reales(t).sum().reindex(tabla.index).fillna(0).astype(int)
    tabla.insert(0, "voto_obj_%", (100 * nacional.reindex(tabla.index)).round(1))
    tabla["real"] = real
    tabla["dentro_80"] = (real >= tabla.p10) & (real <= tabla.p90)
    tabla["dentro_95"] = (real >= tabla["p2.5"]) & (real <= tabla["p97.5"])
    tabla["percentil_real"] = [(sim[p] < real[p]).mean() + 0.5 * (sim[p] == real[p]).mean() for p in tabla.index]
    print(f"23J visto {dias} días antes ({corte.date()}), {len(enc)} encuestas\n")
    print(tabla[tabla.media >= 0.5].round(2).to_string())
    print("\n", (100 * probs).round(1).astype(str).add(" %").to_string(), "  | real: PP+Vox = 170, PP+Vox+UPN = 171")
    return tabla, probs


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
