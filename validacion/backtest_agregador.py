"""
Backtest del agregador: ¿qué habría dicho en cinco elecciones, a distintas
distancias de la elección, y cuánto se equivocó?

Separa dos errores:
  - error del agregador frente al resultado real (lo que nos importa)
  - sesgo de la industria: media de todas las encuestas de la última semana
    frente al resultado. Es el error común que ningún agregador corrige y que
    hay que meter en el Monte Carlo.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.consola import configurar_salida_utf8
from motor.agregador import agregar, preparar

CICLOS = {
    "2015": {"eleccion": "2015-12-20", "partidos": ["PP", "PSOE", "PODEMOS", "CS", "IU"]},
    "2016": {"eleccion": "2016-06-26", "partidos": ["PP", "PSOE", "PODEMOS", "CS"]},
    "2019A": {"eleccion": "2019-04-28", "partidos": ["PP", "PSOE", "PODEMOS", "CS", "VOX"]},
    "2019N": {"eleccion": "2019-11-10", "partidos": ["PSOE", "PP", "VOX", "PODEMOS", "CS", "MAS_PAIS"]},
    "2023": {"eleccion": "2023-07-23", "partidos": ["PP", "PSOE", "VOX", "SUMAR"]},
}
HORIZONTES = [1, 14, 30, 48]   # días antes de la elección


def informe(res: pd.DataFrame) -> str:
    bloques = []
    for (ciclo, dias), g in res.groupby(["ciclo", "dias_antes"], sort=False):
        mae = g.error.abs().mean()
        tabla = g[["partido", "agregador", "sd", "media_ultima_semana", "real", "error"]].to_string(index=False)
        bloques.append(f"{ciclo}, {dias} días antes ({g.n_enc.max()} encuestas) — error medio {mae:.2f} pp\n{tabla}")
    return "\n\n".join(bloques)


def main(q=0.20, tau=0.6, ancla="igual", verbose=True):
    configurar_salida_utf8()
    nac = pd.read_csv("datos/encuestas/nacionales.csv")
    filas = []
    for ciclo, cfg in CICLOS.items():
        d = nac[nac.ciclo == ciclo]
        real = d[(d.tipo == "resultado") & d.encuestadora.str.contains("general election")]
        real = real.sort_values("fin").iloc[-1]
        eleccion = pd.Timestamp(cfg["eleccion"])
        for dias in HORIZONTES:
            corte = eleccion - pd.Timedelta(days=dias)
            enc = preparar(d, corte)
            if len(enc) < 20:
                continue
            ultima = enc[enc.fin > corte - pd.Timedelta(days=7)]
            for pt in cfg["partidos"]:
                if enc[pt].notna().sum() < 5:
                    continue
                r = agregar(enc, pt, corte, q=q, tau=tau, ancla=ancla)
                m, sd = r.final
                filas.append({
                    "ciclo": ciclo, "dias_antes": dias, "partido": pt, "n_enc": len(enc.dropna(subset=[pt])),
                    "agregador": round(m, 1), "sd": round(sd, 2), "media_ultima_semana": round(ultima[pt].mean(), 1),
                    "real": real[pt], "error": round(m - real[pt], 1),
                })
    res = pd.DataFrame(filas)
    if verbose:
        print(informe(res))
    return res


if __name__ == "__main__":
    res = main(verbose=False)
    texto = informe(res)
    print(texto)
    res.to_csv("resultados/validacion/backtest_agregador.csv", index=False)
    Path("resultados/validacion/backtest_agregador.txt").write_text(texto + "\n", encoding="utf-8")
