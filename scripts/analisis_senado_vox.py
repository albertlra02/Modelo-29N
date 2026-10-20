"""
¿En qué provincias le conviene a Vox no presentarse al Senado si la derecha quiere los tres quintos?

    python -m scripts.analisis_senado_vox [participación] [reparto]      (p. ej. 0.65 historico)

Los tres quintos del Senado completo (160 de 266) permiten a PP y Vox renovar sin el PSOE los magistrados del
Constitucional y los vocales del CGPJ que elige el Senado. Con los 28 designados que ya tienen (PP 23, Vox 5), les
hacen falta 132 de los 208 senadores electos.

Método: retirarse en una provincia sólo cambia los senadores de esa provincia, así que se simula cada provincia
una vez (las mismas simulaciones de voto y el mismo sorteo del 2 + 2 que el escenario base) y cualquier conjunto
de retiradas se obtiene sumando las diferencias. Donde Vox se retira, el 80 % de su voto va a la lista del PP
(TRASVASE_VOX) y, si su voto llega a un tercio del de PP + Vox, uno de los tres nombres del PP es suyo
(motor/senado.py). Después se eligen las retiradas una a una, siempre la que más sube la probabilidad de los
tres quintos (algoritmo voraz), hasta que ninguna la mejora.

Salida: resultados/analisis/senado_vox_<participación>_<reparto>.csv (beneficio de cada provincia por separado) y
la curva de retiradas por consola.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from datos.cargar import escanos_2026
from motor import senado
from motor.montecarlo import simular
from motor.palancas import aplicar
from motor.pipeline import BLOQUES, ESTATALES, Escenario, piezas_centrales, registradas
from scripts.consola import configurar_salida_utf8

DERECHA = ("PP", "VOX")


def cuotas_simuladas(esc: Escenario) -> dict:
    """Voto simulado por provincia (como en motor/pipeline.ejecutar, candidaturas registradas)."""
    c = aplicar(registradas(piezas_centrales(esc.fecha, esc.participacion, esc.reparto)), esc.palancas)
    estatales = tuple(dict.fromkeys("FRENTE_AMPLIO" if p == "SUMAR" else p for p in ESTATALES))
    bloques = {("FRENTE_AMPLIO" if p == "SUMAR" else p): v for p, v in BLOQUES.items()}
    _, _, _, S = simular(c["s0"], c["s0_unif"], c["nacional"], c["region"], c["sd_reg"], escanos_2026(), c["pesos"],
                         esc.dias, bloques, estatales=estatales, n_sim=esc.n_sim, semilla=esc.semilla,
                         detalle=True, por_provincia=True, cuotas=True)
    return {"S": S, "provs": list(c["s0"].index), "partidos": list(c["s0"].columns), "ajena": c["ajena"],
            "s0": c["s0"]}


def derecha_por_circ(por_circ: dict[str, pd.DataFrame]) -> dict[str, np.ndarray]:
    return {k: df[[p for p in DERECHA if p in df]].sum(axis=1).to_numpy() for k, df in por_circ.items()}


def analizar(esc: Escenario) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    q = cuotas_simuladas(esc)
    args = (q["S"], q["provs"], q["partidos"], q["ajena"])
    _, base_circ = senado.simular(*args, coalicion=True, semilla=esc.semilla)
    base = derecha_por_circ(base_circ)
    designados = senado.designados_por_lista().reindex(list(DERECHA), fill_value=0).sum()
    total = senado.TOTAL + len(senado.designados())
    umbral = -(-3 * total // 5) - designados                     # electos que les faltan para 160
    circ = senado.circunscripciones()
    base_total = sum(base.values())

    # beneficio de retirarse en cada provincia, por separado (vector por simulación)
    delta, filas = {}, []
    for prov in sorted(set(circ.provincia)):
        sv = frozenset([prov])
        _, por_circ = senado.simular(*args, coalicion=True, semilla=esc.semilla, sin_vox=sv,
                                     vox_en_pp=senado.nombres_vox(q["s0"], sv))
        nuevo = derecha_por_circ(por_circ)
        d = sum(nuevo[c] - base[c] for c in circ.index[circ.provincia == prov])
        delta[prov] = d
        filas.append({"provincia": prov, "senadores": int(circ.loc[circ.provincia == prov, "escanos"].sum()),
                      "ganancia_media": float(d.mean()), "p_gana": float((d > 0).mean()),
                      "p_pierde": float((d < 0).mean()),
                      "p_tres_quintos_sola": float((base_total + d >= umbral).mean())})
    sueltas = pd.DataFrame(filas).set_index("provincia").sort_values("ganancia_media", ascending=False)

    # retiradas una a una (voraz), siempre la que más sube P(tres quintos)
    actual, elegidas, curva = base_total.copy(), [], []
    p_base = float((actual >= umbral).mean())
    curva.append({"retiradas": 0, "provincia": "(Vox en todas)", "p_tres_quintos": p_base,
                  "derecha_mediana": float(np.median(actual + designados))})
    restantes = set(delta)
    while restantes:
        mejor = max(restantes, key=lambda p: ((actual + delta[p] >= umbral).mean(), (actual + delta[p]).mean()))
        nuevo = actual + delta[mejor]
        if (nuevo >= umbral).mean() <= (actual >= umbral).mean() and nuevo.mean() <= actual.mean():
            break
        actual = nuevo
        elegidas.append(mejor)
        restantes.remove(mejor)
        curva.append({"retiradas": len(elegidas), "provincia": mejor, "p_tres_quintos": float((actual >= umbral).mean()),
                      "derecha_mediana": float(np.median(actual + designados))})
    return sueltas, pd.DataFrame(curva), p_base


def main(participacion: float = 0.65, reparto: str = "historico", n_sim: int = 5000) -> None:
    configurar_salida_utf8()
    esc = Escenario(participacion=participacion, reparto=reparto, n_sim=n_sim)
    sueltas, curva, p_base = analizar(esc)
    salida = Path("resultados/analisis") / f"senado_vox_{round(100 * participacion)}_{reparto}.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    sueltas.to_csv(salida)
    print(f"Participación {participacion:.0%} ({reparto}), {n_sim} simulaciones, encuestas hasta {esc.fecha}")
    print(f"P(PP + Vox ≥ 160 de 266) con Vox en todas: {p_base:.1%}\n")
    print("Provincias donde retirarse ayuda (por separado):")
    print(sueltas[sueltas.ganancia_media > 0.01].round(3).to_string())
    print("\nRetiradas una a una:")
    print(curva.round(3).to_string(index=False))
    print(f"\nEscrito {salida}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(float(a[0]) if a else 0.65, a[1] if len(a) > 1 else "historico")
