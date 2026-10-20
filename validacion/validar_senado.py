"""
Valida el reparto del Senado (motor/senado.py) contra 2023.

Toma el voto real al Congreso de julio de 2023 por provincia, lo pasa al Senado con los mismos
supuestos que el modelo (voto de partido, patrón insular del Congreso, listas insulares ASG y AHI
con su cuota del Senado) y compara los senadores que salen con los elegidos de verdad.
En 2023 la única coalición distinta de las listas del Congreso fue PSOE + Sumar en Eivissa-Formentera.

    python -m validacion.validar_senado
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from datos.cargar import cargar
from motor.senado import PROGRESO, circunscripciones, repartir, senado_2023, umbrales_empate, voto_senado

COLUMNAS = {"PP": "PP", "PSOE": "PSOE", "VOX": "VOX", "SUMAR": "SUMAR", "ERC": "ERC", "JUNTS": "JUNTS",
            "PNV": "PNV", "BILDU": "EH BILDU", "BNG": "BNG", "CC": "CC", "NC": "NC", "UPN": "UPN"}
SIGLAS = {"PP": "PP", "PSOE": "PSOE", "PSC": "PSOE", "PSE-EE (PSOE)": "PSOE", "PSdeG-PSOE": "PSOE",
          "PSN-PSOE": "PSOE", "PSIB-PSOE": "PSOE", "PSOE-SUMAR-EUIB-ARA EIVISSA": PROGRESO,
          "ERC": "ERC", "ERC-ESQUERRES PER LA INDEPENDÈNCIA": "ERC", "JxCAT - JUNTS": "JUNTS",
          "EAJ-PNV": "PNV", "EH BILDU-INDEPENDENTZIA EZKERRETIK": "BILDU", "U.P.N.": "UPN",
          "ASG": "ASG", "A.H.I.": "AHI"}
COALICIONES_2023 = {"Eivissa-Formentera": ["PSOE", "SUMAR"]}


def reparto_2023(empates: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(previsto, real): circunscripción x lista, con los senadores de 2023. Con `empates`, el previsto
    es el esperado al sortear el margen del 2 + 2 como en el Monte Carlo (no entero)."""
    e = cargar("2023-07")
    v = pd.DataFrame({k: e.votos[c] for k, c in COLUMNAS.items()})
    v["OTROS"] = e.votos.sum(axis=1) - v.sum(axis=1)
    v["BLANCO"] = e.meta.blancos
    s = v.div(v.sum(axis=1), axis=0)
    V, L = voto_senado(s.to_numpy()[None], list(s.index), list(s.columns), pd.Series(dtype=float), coalicion=False)
    V = V[0]
    circ = circunscripciones()
    il = {p: i for i, p in enumerate(L)}
    prev = np.zeros((len(circ), len(L)))
    u = umbrales_empate()
    for c, (nombre, fila) in enumerate(circ.iterrows()):
        if nombre in COALICIONES_2023:
            ids = [il[p] for p in COALICIONES_2023[nombre]]
            V[c, il[PROGRESO]] = V[c, ids].sum()
            V[c, ids] = 0
        if empates:
            prev[c] = repartir(np.repeat(V[c][None], len(u), axis=0), int(fila.escanos), u).mean(axis=0)
        else:
            prev[c] = repartir(V[c][None], int(fila.escanos))[0]
    prev = pd.DataFrame(prev, index=circ.index, columns=L)

    r = senado_2023().copy()
    r["lista"] = r.siglas.map(SIGLAS)
    r["nombre"] = np.where(r.circ.str[2] != "9", r.circunscripcion, r.provincia)
    real = r[r.electos > 0].pivot_table(index="nombre", columns="lista", values="electos", aggfunc="sum")
    real = real.reindex(index=circ.index, columns=L).fillna(0).astype(int)
    return prev, real


def main() -> None:
    prev, real = reparto_2023()
    dif = (prev - real).abs().sum(axis=1) // 2
    print(f"Senado 2023 desde el voto al Congreso: {int(prev.to_numpy().sum())} senadores")
    print(f"Circunscripciones con el reparto exacto: {int((dif == 0).sum())} de {len(dif)}")
    print(f"Senadores mal asignados: {int(dif.sum())} de {int(real.to_numpy().sum())}")
    esp, _ = reparto_2023(empates=True)
    print(f"Con el sorteo del 2 + 2 del Monte Carlo, senadores mal asignados en promedio: "
          f"{float((esp - real).abs().to_numpy().sum() / 2):.1f}")
    tot = pd.DataFrame({"previsto": prev.sum().astype(int), "con 2 + 2": esp.sum().round(1), "real": real.sum()})
    print(tot[(tot > 0).any(axis=1)].sort_values("real", ascending=False).to_string())
    fallos = dif[dif > 0].index
    if len(fallos):
        print("\nFallos (previsto -> real):")
        for c in fallos:
            p = ", ".join(f"{k} {int(v)}" for k, v in prev.loc[c][prev.loc[c] > 0].items())
            q = ", ".join(f"{k} {v}" for k, v in real.loc[c][real.loc[c] > 0].items())
            print(f"  {c}: {p}  ->  {q}")


if __name__ == "__main__":
    main()
