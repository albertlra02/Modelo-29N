"""
El acuerdo PP-Vox para el Senado (26/10/2026) frente a no pactar y frente al mejor pacto posible.

    python -m scripts.analisis_pacto_senado [participación] [reparto]      (p. ej. 0.65 historico)

En cada provincia hay cuatro opciones (motor/senado.py):
  separados   cada partido con su lista de 3 nombres
  vox_fuera   Vox no se presenta; en las de 4 senadores, uno de los tres nombres del PP es suyo
  pp_fuera    el PP no se presenta
  vox_uno     Vox lleva un solo nombre y sus votantes marcan también a dos del PP (sólo provincias de 4)

Como lo que pasa en una provincia no cambia las demás, basta simular una vez cada opción en todas las
provincias (mismas simulaciones de voto y mismo sorteo del 2 + 2) y combinar después. Se comparan:
  - sin pacto, el acuerdo real y dos pactos ideales: el que maximiza los senadores esperados de PP + Vox
    (en cada provincia, la opción con más senadores de media) y el que maximiza la probabilidad de los tres
    quintos (opciones elegidas una a una, siempre la que más la sube).

Salida: resultados/analisis/pacto_senado_<participación>_<reparto>.csv (opción real y mejor opción por provincia).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from motor import senado
from motor.pipeline import Escenario
from scripts.analisis_senado_vox import cuotas_simuladas
from scripts.consola import configurar_salida_utf8

DERECHA = ("PP", "VOX")
OPCIONES = ("separados", "vox_fuera", "pp_fuera", "vox_uno")


def opcion_real(prov: str) -> str:
    if prov in senado.PACTO_VOX_FUERA:
        return "vox_fuera"
    if prov in senado.PACTO_PP_FUERA:
        return "pp_fuera"
    if prov in senado.PACTO_VOX_UNO:
        return "vox_uno"
    return "separados"


def argumentos(opcion: str, provincias: frozenset[str]) -> dict:
    circ = senado.circunscripciones()
    cuatro = frozenset(circ.query("escanos == 4").index) & provincias
    return {"separados": {},
            "vox_fuera": {"sin_vox": provincias, "vox_en_pp": cuatro},
            "pp_fuera": {"pp_fuera": provincias},
            "vox_uno": {"vox_uno": cuatro}}[opcion]


def derecha_por_provincia(q: dict, esc: Escenario) -> dict[str, dict[str, np.ndarray]]:
    """provincia -> opción -> senadores de PP + Vox en cada simulación."""
    circ = senado.circunscripciones()
    provs = frozenset(circ.provincia)
    out: dict[str, dict[str, np.ndarray]] = {p: {} for p in provs}
    for op in OPCIONES:
        _, por_circ = senado.simular(q["S"], q["provs"], q["partidos"], q["ajena"], coalicion=True,
                                     semilla=esc.semilla, **argumentos(op, provs))
        der = {c: df[[p for p in DERECHA if p in df]].sum(axis=1).to_numpy() for c, df in por_circ.items()}
        for p in provs:
            out[p][op] = sum(der[c] for c in circ.index[circ.provincia == p])
    # vox_uno sólo existe en provincias de 4 senadores: en el resto es lo mismo que ir separados
    return out


def analizar(esc: Escenario) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = cuotas_simuladas(esc)
    d = derecha_por_provincia(q, esc)
    designados = senado.designados_por_lista().reindex(list(DERECHA), fill_value=0).sum()
    pleno_total = senado.TOTAL + len(senado.designados())
    umbral = -(-3 * pleno_total // 5) - designados                  # electos que faltan para 160
    provs = sorted(d)

    def total(eleccion: dict[str, str]) -> np.ndarray:
        return sum(d[p][eleccion[p]] for p in provs)

    def resumen(nombre: str, eleccion: dict[str, str]) -> dict:
        t = total(eleccion)
        return {"pacto": nombre, "senadores_pp_vox_mediana": float(np.median(t)),
                "senadores_pp_vox_media": float(t.mean()),
                "p_tres_quintos": float((t >= umbral).mean()),
                "cambios": sum(eleccion[p] != "separados" for p in provs)}

    sin = {p: "separados" for p in provs}
    real = {p: opcion_real(p) for p in provs}
    esperanza = {p: max(OPCIONES, key=lambda op: (d[p][op].mean(), op == "separados")) for p in provs}

    # tres quintos: opciones una a una desde «sin pacto», siempre la que más sube la probabilidad
    quintos, actual = dict(sin), total(sin)
    while True:
        mejor, valor = None, ((actual >= umbral).mean(), actual.mean())
        for p in provs:
            for op in OPCIONES:
                if op == quintos[p]:
                    continue
                nuevo = actual - d[p][quintos[p]] + d[p][op]
                v = ((nuevo >= umbral).mean(), nuevo.mean())
                if v > valor:
                    mejor, valor = (p, op), v
        if mejor is None:
            break
        p, op = mejor
        actual = actual - d[p][quintos[p]] + d[p][op]
        quintos[p] = op

    tabla = pd.DataFrame([resumen("Sin pacto", sin), resumen("Acuerdo del 26 de octubre", real),
                          resumen("Ideal: más senadores", esperanza), resumen("Ideal: tres quintos", quintos)])
    filas = []
    for p in provs:
        medias = {op: d[p][op].mean() for op in OPCIONES}
        filas.append({"provincia": p, "acuerdo": real[p], "ideal_senadores": esperanza[p],
                      "ideal_tres_quintos": quintos[p],
                      **{f"media_{op}": round(m, 2) for op, m in medias.items()},
                      "ganancia_acuerdo": round(medias[real[p]] - medias["separados"], 2),
                      "ganancia_ideal": round(medias[esperanza[p]] - medias["separados"], 2)})
    return tabla, pd.DataFrame(filas).set_index("provincia")


def main(participacion: float = 0.65, reparto: str = "historico", n_sim: int = 5000) -> None:
    configurar_salida_utf8()
    esc = Escenario(participacion=participacion, reparto=reparto, n_sim=n_sim)
    tabla, provs = analizar(esc)
    salida = Path("resultados/analisis") / f"pacto_senado_{round(100 * participacion)}_{reparto}.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    provs.to_csv(salida)
    print(f"Participación {participacion:.0%} ({reparto}), {n_sim} simulaciones, encuestas hasta {esc.fecha}")
    print(f"Supuestos: trasvase Vox→PP {senado.TRASVASE_VOX:.0%}, PP→Vox {senado.TRASVASE_PP:.0%}, "
          f"votantes de Vox que marcan dos del PP {senado.CUMPLE_VOX_UNO:.0%}\n")
    print(tabla.round(3).to_string(index=False))
    distintas = provs[(provs.acuerdo != provs.ideal_senadores) | (provs.acuerdo != provs.ideal_tres_quintos)]
    print("\nProvincias donde el acuerdo no coincide con el ideal:")
    print(distintas[["acuerdo", "ideal_senadores", "ideal_tres_quintos", "ganancia_acuerdo", "ganancia_ideal"]]
          .sort_values("ganancia_ideal", ascending=False).to_string())
    print(f"\nEscrito {salida}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(float(a[0]) if a else 0.65, a[1] if len(a) > 1 else "historico")
