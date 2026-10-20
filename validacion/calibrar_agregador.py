"""Calibración leave-one-election-out de los hiperparámetros del agregador.

Cada combinación se evalúa por separado en las cinco elecciones disponibles.
Para cada elección retenida se elige la combinación con menor MAE medio en las
otras cuatro y sólo entonces se mide el error en la elección no vista.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path

import pandas as pd

from validacion.backtest_agregador import CICLOS, main as ejecutar_backtest
from scripts.consola import configurar_salida_utf8


Q = (0.10, 0.15, 0.20)
TAU = (0.6, 0.8, 1.0)
ANCLAS = ("igual", "sin_cis")
SALIDA = Path("resultados/validacion/calibracion_agregador_loo.csv")


def evaluar_rejilla() -> pd.DataFrame:
    filas = []
    total = len(Q) * len(TAU) * len(ANCLAS)
    for numero, (q, tau, ancla) in enumerate(product(Q, TAU, ANCLAS), 1):
        res = ejecutar_backtest(q=q, tau=tau, ancla=ancla, verbose=False)
        for ciclo, grupo in res.groupby("ciclo"):
            filas.append({
                "q": q,
                "tau": tau,
                "ancla": ancla,
                "ciclo": ciclo,
                "mae": grupo.error.abs().mean(),
                "n_predicciones": len(grupo),
            })
        print(f"[{numero:02d}/{total}] q={q:.2f}, tau={tau:.1f}, ancla={ancla}")
    return pd.DataFrame(filas)


def leave_one_out(evaluaciones: pd.DataFrame) -> pd.DataFrame:
    claves = ["q", "tau", "ancla"]
    filas = []
    for retenida in CICLOS:
        entrenamiento = (
            evaluaciones[evaluaciones.ciclo != retenida]
            .groupby(claves, as_index=False).mae.mean()
            .rename(columns={"mae": "mae_entrenamiento"})
            .sort_values(["mae_entrenamiento", "q", "tau", "ancla"])
        )
        mejor = entrenamiento.iloc[0]
        mascara = (
            (evaluaciones.ciclo == retenida)
            & (evaluaciones.q == mejor.q)
            & (evaluaciones.tau == mejor.tau)
            & (evaluaciones.ancla == mejor.ancla)
        )
        prueba = evaluaciones[mascara].iloc[0]
        filas.append({
            "eleccion_retenida": retenida,
            "q_elegido": mejor.q,
            "tau_elegido": mejor.tau,
            "ancla_elegida": mejor.ancla,
            "mae_entrenamiento": mejor.mae_entrenamiento,
            "mae_fuera_muestra": prueba.mae,
            "n_predicciones": int(prueba.n_predicciones),
        })
    return pd.DataFrame(filas)


def mejor_global(evaluaciones: pd.DataFrame) -> pd.Series:
    return (
        evaluaciones.groupby(["q", "tau", "ancla"], as_index=False).mae.mean()
        .sort_values(["mae", "q", "tau", "ancla"])
        .iloc[0]
    )


def main() -> pd.DataFrame:
    configurar_salida_utf8()
    evaluaciones = evaluar_rejilla()
    loo = leave_one_out(evaluaciones)
    mejor = mejor_global(evaluaciones)
    SALIDA.parent.mkdir(exist_ok=True)
    loo.to_csv(SALIDA, index=False)
    print("\nLeave-one-election-out:")
    print(loo.round(3).to_string(index=False))
    print(
        "\nMejor en las cinco elecciones: "
        f"q={mejor.q:.2f}, tau={mejor.tau:.1f}, ancla={mejor.ancla}, MAE={mejor.mae:.3f} pp"
    )
    print(f"Guardado en {SALIDA}")
    return loo


if __name__ == "__main__":
    main()
