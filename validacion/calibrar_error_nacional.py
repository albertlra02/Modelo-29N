"""Resume el error nacional de bloque y de trasvase en cinco elecciones."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.consola import configurar_salida_utf8


BLOQUES = {
    "2015": {-1: ("PP", "CS"), +1: ("PSOE", "PODEMOS", "IU")},
    "2016": {-1: ("PP", "CS"), +1: ("PSOE", "PODEMOS")},
    "2019A": {-1: ("PP", "CS", "VOX"), +1: ("PSOE", "PODEMOS")},
    "2019N": {-1: ("PP", "CS", "VOX"), +1: ("PSOE", "PODEMOS", "MAS_PAIS")},
    "2023": {-1: ("PP", "VOX"), +1: ("PSOE", "SUMAR")},
}
SALIDA = Path("resultados/validacion/calibracion_error_nacional.csv")


def calcular(backtest: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bloques, internos = [], []
    for (ciclo, dias), grupo in backtest.groupby(["ciclo", "dias_antes"]):
        tabla = grupo.set_index("partido")
        for signo, partidos in BLOQUES[ciclo].items():
            if not set(partidos) <= set(tabla.index):
                continue
            sub = tabla.loc[list(partidos)]
            error_bloque = float(sub.error.sum())
            bloques.append({
                "ciclo": ciclo,
                "dias_antes": dias,
                "bloque": "derecha" if signo == -1 else "izquierda",
                "signo": signo,
                "error_pp": error_bloque,
            })
            # Quita el error común repartido según el peso previsto del partido.
            residuo = sub.error - error_bloque * sub.agregador / sub.agregador.sum()
            cuota = sub.agregador / 100
            k = (residuo / 100) / np.sqrt(cuota * (1 - cuota))
            internos.extend({
                "ciclo": ciclo,
                "dias_antes": dias,
                "bloque": "derecha" if signo == -1 else "izquierda",
                "partido": partido,
                "k_residuo": valor,
            } for partido, valor in k.items())
    return pd.DataFrame(bloques), pd.DataFrame(internos)


def main() -> tuple[pd.DataFrame, pd.DataFrame]:
    configurar_salida_utf8()
    backtest = pd.read_csv("resultados/validacion/backtest_agregador.csv")
    bloques, internos = calcular(backtest)
    SALIDA.parent.mkdir(exist_ok=True)
    bloques.to_csv(SALIDA, index=False)

    rmse = bloques.groupby(["bloque", "dias_antes"]).error_pp.apply(
        lambda x: np.sqrt(np.mean(np.square(x)))
    ).unstack()
    k = internos.groupby("dias_antes").k_residuo.apply(
        lambda x: np.sqrt(np.mean(np.square(x)))
    )
    pares = bloques.pivot(index=["ciclo", "dias_antes"], columns="signo", values="error_pp").dropna()
    correlacion = pares.corr().iloc[0, 1]

    print("RMSE del error de bloque (pp):")
    print(rmse.round(2).to_string())
    print("\nEscala k del trasvase interno:")
    print(k.round(3).to_string())
    print(f"\nCorrelación empírica entre bloques: {correlacion:.2f} ({len(pares)} pares)")
    print(f"Observaciones guardadas en {SALIDA}")
    return bloques, internos


if __name__ == "__main__":
    main()
