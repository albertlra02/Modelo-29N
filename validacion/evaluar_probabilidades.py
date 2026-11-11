"""
Evaluación de las probabilidades del modelo, fuera de muestra (2016, abril y noviembre de 2019, 2023).

backtest_loo.py mide si el resultado real cae en los intervalos del 80 % y del 95 %. Aquí se puntúa la
distribución entera con reglas de puntuación propias y se compara con referencias sin incertidumbre:

  1. CRPS por partido (escaños): cuánto se aleja la distribución simulada del resultado real. Para una
     predicción puntual el CRPS es el error absoluto, así que se compara directamente con la proyección
     central del modelo (sin simular) y con repetir la elección anterior.
  2. Calibración de los intervalos centrales del 10 % al 90 % (extremos incluidos, como backtest_loo).
  3. Brier de los sucesos «el partido saca al menos k escaños» y de los dos sucesos de bloque, frente a las
     mismas referencias convertidas en 0/1.
  4. Fiabilidad: agrupando las probabilidades por tramos, frecuencia con que el suceso ocurrió.

Usa las mismas simulaciones que backtest_loo.py (escalas calibradas sin la elección evaluada y las mismas
semillas), así que la cobertura cuadra con la suya.

Límite principal: son 4 elecciones y los 3 horizontes y los muchos sucesos de una misma elección están muy
correlacionados. Las cifras describen el comportamiento pasado; no son una prueba estadística fuerte.

    python -m validacion.evaluar_probabilidades   # escribe resultados/validacion/probabilidades*
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.consola import configurar_salida_utf8
from validacion.backtest_loo import CASOS, DERECHA, HORIZONTES, SALIDA, escalas, preparar_caso, simular_caso

UMBRALES = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170]
NIVELES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
TRAMOS = [0, 0.02, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.98, 1.0001]


def crps(muestras: np.ndarray, real: float) -> float:
    """CRPS de una muestra frente a un valor: E|X - y| - E|X - X'| / 2 (X, X' independientes)."""
    x = np.sort(np.asarray(muestras, float))
    n = len(x)
    e_xy = np.abs(x - real).mean()
    e_xx = 2 * np.sum((2 * np.arange(n) - n + 1) * x) / n ** 2
    return float(e_xy - e_xx / 2)


def brier(p, ocurrio) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(ocurrio, float)) ** 2))


def puntuar(ciclo: str, dias: int, c: dict, sim: pd.DataFrame) -> tuple[list, list]:
    real = c["real"].reindex(sim.columns).fillna(0)
    partidos, sucesos = [], []
    for p in sim.columns:
        s = sim[p].to_numpy()
        if s.mean() < 0.5 and real[p] == 0:
            continue
        r, central, previo = float(real[p]), float(c["central"].get(p, 0)), float(c["previos"].get(p, 0))
        partidos.append({
            "eleccion": ciclo, "dias_antes": dias, "partido": p, "estatal": p in c["estatales"], "real": int(r),
            "crps_modelo": crps(s, r), "crps_central": abs(central - r), "crps_anterior": abs(previo - r),
            "percentil_real": float((s < r).mean() + 0.5 * (s == r).mean()),
            # dentro del intervalo central de cada nivel, con los extremos incluidos (como backtest_loo)
            **{f"dentro_{round(100 * n)}": bool(np.quantile(s, (1 - n) / 2) <= r <= np.quantile(s, (1 + n) / 2))
               for n in NIVELES},
        })
        for k in UMBRALES:
            if k > max(s.max(), r, central, previo):
                continue          # nadie le da ese número de escaños: suceso trivial que inflaría el acierto
            sucesos.append({"eleccion": ciclo, "dias_antes": dias, "suceso": f"{p} >= {k}", "tipo": "umbral",
                            "estatal": p in c["estatales"], "p_modelo": float((s >= k).mean()),
                            "p_central": float(central >= k), "p_anterior": float(previo >= k), "ocurrio": r >= k})
    der = [p for p in DERECHA if p in sim]
    suma = sim[der].sum(axis=1)
    sucesos.append({"eleccion": ciclo, "dias_antes": dias, "suceso": "derecha >= 176", "tipo": "bloque",
                    "estatal": True, "p_modelo": float((suma >= 176).mean()),
                    "p_central": float(c["central"].reindex(der).fillna(0).sum() >= 176),
                    "p_anterior": float(c["previos"].reindex(der).fillna(0).sum() >= 176),
                    "ocurrio": bool(real[der].sum() >= 176)})
    sucesos.append({"eleccion": ciclo, "dias_antes": dias, "suceso": "PP > PSOE", "tipo": "bloque", "estatal": True,
                    "p_modelo": float((sim.PP > sim.PSOE).mean()),
                    "p_central": float(c["central"].get("PP", 0) > c["central"].get("PSOE", 0)),
                    "p_anterior": float(c["previos"].get("PP", 0) > c["previos"].get("PSOE", 0)),
                    "ocurrio": bool(real["PP"] > real["PSOE"])})
    return partidos, sucesos


def cobertura(sub: pd.DataFrame) -> list[float]:
    """Frecuencia con que el resultado real cae en el intervalo central de cada nivel."""
    return [float(sub[f"dentro_{round(100 * n)}"].mean()) for n in NIVELES]


def fiabilidad(s: pd.DataFrame) -> pd.DataFrame:
    tramo = pd.cut(s.p_modelo, TRAMOS, right=False)
    g = s.groupby(tramo, observed=True)
    return pd.DataFrame({"n": g.size(), "p_media": g.p_modelo.mean(), "frecuencia": g.ocurrio.mean()})


def informe(part: pd.DataFrame, suc: pd.DataFrame) -> str:
    pct = lambda x: f"{100 * x:.0f} %"   # noqa: E731
    out = ["Evaluación de las probabilidades, fuera de muestra",
           f"Elecciones {list(CASOS)}; horizontes {HORIZONTES} días; mismas simulaciones que backtest_loo.", ""]

    out.append("== 1. CRPS por partido (escaños; menor es mejor; para una predicción puntual = error absoluto)")
    for nombre, sub in [("partidos estatales", part[part.estatal]), ("todos los partidos", part)]:
        m, c_, a = sub.crps_modelo.mean(), sub.crps_central.mean(), sub.crps_anterior.mean()
        out.append(f"  {nombre} (n = {len(sub)}): modelo {m:.2f} | proyección central {c_:.2f} | "
                   f"repetir la anterior {a:.2f}")
        out.append(f"    mejora frente a la central {pct(1 - m / c_)}, frente a repetir la anterior {pct(1 - m / a)}")
    est = part[part.estatal]
    out.append("  Por horizonte (estatales): " + ", ".join(
        f"{d} días: {g.crps_modelo.mean():.1f} frente a {g.crps_central.mean():.1f}"
        for d, g in est.groupby("dias_antes", sort=False)))
    out.append("  Por elección (estatales): " + ", ".join(
        f"{e}: {g.crps_modelo.mean():.1f} frente a {g.crps_central.mean():.1f}"
        for e, g in est.groupby("eleccion", sort=False)))
    out.append("")

    out.append("== 2. Calibración de los intervalos centrales (lo ideal: observado = nominal)")
    tab = pd.DataFrame({"nominal": NIVELES})
    for nombre, sub in [("estatales", est), ("todos", part)]:
        tab[nombre] = cobertura(sub)
    out.append(tab.assign(**{k: tab[k].map(pct) for k in tab.columns}).to_string(index=False))
    out.append("  En «todos», los niveles bajos salen altos por los partidos pequeños: si casi siempre sacan los mismos")
    out.append("  escaños, hasta el intervalo más estrecho contiene ese valor. La columna fiable es la de estatales.")
    out.append("  Percentil del resultado real (estatales), por décimas; uniforme = calibrado:")
    deciles = pd.cut(est.percentil_real, np.linspace(0, 1, 11), include_lowest=True).value_counts(sort=False)
    out.append("  " + " ".join(f"{n:2d}" for n in deciles.to_numpy()))
    out.append(f"  Percentil medio {est.percentil_real.mean():.2f} (0,50 = sin sesgo de dirección)")
    out.append("")

    out.append("== 3. Brier (menor es mejor) frente a referencias sin incertidumbre (0/1)")
    for nombre, sub in [("umbrales de escaños, estatales", suc[(suc.tipo == "umbral") & suc.estatal]),
                        ("umbrales de escaños, todos", suc[suc.tipo == "umbral"]),
                        ("sucesos de bloque (derecha ≥ 176, PP > PSOE)", suc[suc.tipo == "bloque"])]:
        bm, bc, ba = (brier(sub[col], sub.ocurrio) for col in ("p_modelo", "p_central", "p_anterior"))
        out.append(f"  {nombre} (n = {len(sub)}): modelo {bm:.3f} | central {bc:.3f} | repetir la anterior {ba:.3f}"
                   f" | mejora frente a la central {pct(1 - bm / bc) if bc else '–'}")
    duda = suc[(suc.p_modelo > 0.02) & (suc.p_modelo < 0.98)]
    out.append(f"  sólo sucesos en duda (el modelo da entre 2 % y 98 %, n = {len(duda)}): modelo "
               f"{brier(duda.p_modelo, duda.ocurrio):.3f} | central {brier(duda.p_central, duda.ocurrio):.3f}")
    out.append("")

    out.append("== 4. Fiabilidad (todos los sucesos): cuando el modelo dice p, ¿con qué frecuencia ocurre?")
    fia = fiabilidad(suc)
    etiquetas = [f"{100 * i.left:.0f}–{min(100 * i.right, 100):.0f} %" for i in fia.index]
    out.append(pd.DataFrame({"tramo": etiquetas, "n": fia.n.to_numpy(),
                             "p media": fia.p_media.map(pct).to_numpy(),
                             "ocurrió": fia.frecuencia.map(pct).to_numpy()}).to_string(index=False))
    raros = suc[((suc.p_modelo < 0.02) & suc.ocurrio) | ((suc.p_modelo > 0.98) & ~suc.ocurrio)]
    out.append("  Sorpresas (el modelo daba menos de un 2 % a algo que pasó, o más de un 98 % a algo que no pasó):")
    out.append("  " + "; ".join(f"{r.eleccion} a {r.dias_antes} días: {r.suceso} ({pct(r.p_modelo)})"
                                for r in raros.itertuples()))
    out.append("")
    out.append("Límites: 4 elecciones; los horizontes y los sucesos de una misma elección no son independientes (el "
               "tamaño efectivo es mucho menor que n); los umbrales de un partido son sucesos encadenados. Sirve para "
               "ver tendencias (intervalos estrechos, sesgos de dirección), no como prueba estadística.")
    return "\n".join(out)


def main() -> tuple[pd.DataFrame, pd.DataFrame]:
    configurar_salida_utf8()
    partidos, sucesos = [], []
    for i, ciclo in enumerate(CASOS):
        esc = escalas(ciclo)
        for j, dias in enumerate(HORIZONTES):
            c = preparar_caso(ciclo, dias)
            sim = simular_caso(c, esc, semilla=1000 + 10 * i + j)   # mismas semillas que backtest_loo
            p, s = puntuar(ciclo, dias, c, sim)
            partidos += p
            sucesos += s
            print(f"  {ciclo}, {dias} días: hecho", flush=True)
    partidos, sucesos = pd.DataFrame(partidos), pd.DataFrame(sucesos)
    SALIDA.mkdir(exist_ok=True)
    partidos.to_csv(SALIDA / "probabilidades_partidos.csv", index=False)
    sucesos.to_csv(SALIDA / "probabilidades_sucesos.csv", index=False)
    texto = informe(partidos, sucesos)
    (SALIDA / "probabilidades.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return partidos, sucesos


if __name__ == "__main__":
    main()
