"""
Backtest fuera de muestra del modelo completo (Monte Carlo de escaños), dejando fuera cada elección.

Para cada elección evaluada (2016, abril y noviembre de 2019, 2023):
  1. Las escalas de error nacional (bloque y trasvase) se recalculan SIN esa elección, con la misma regla
     que usa producción (error cuadrático medio a 1 y 48 días, calibrar_error_nacional.calcular).
  2. Se proyecta desde la elección anterior (base provincial) con las encuestas disponibles 30, 14 y 1 días
     antes, como en backtest_mc.py, y se simula con esas escalas.
  3. Se mide si el resultado real cae dentro de los intervalos y cómo puntúan las probabilidades.

Para comparar, cada caso se corre también con las escalas de producción (calibradas con las cinco
elecciones, la evaluada incluida: dentro de muestra).

Límites (se dicen en el informe): 2015 no se puede evaluar (no hay resultados de 2011); sin encuestas
autonómicas la capa CCAA usa sólo su prior; K_REG, K_PROV, el margen ×1,10, la correlación −0,65 y las colas t(5)
se mantienen como en producción (no se re-estiman por elección); las candidaturas son las que concurrieron.

    python -m validacion.backtest_loo   # escribe resultados/validacion/backtest_loo*
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

from validacion.backtest_swing import escanos_desde_cuotas, escanos_reales
from validacion.calibrar_error_nacional import calcular
from scripts.consola import configurar_salida_utf8
from datos.cargar import cargar
from datos.familias import PROV_CCAA, a_familias
import motor.montecarlo as mc
from motor.agregador import agregar, preparar
from motor.regional import K_REG
from motor.swing import proyectar

HORIZONTES = [30, 14, 1]
N_SIM = 10_000
# elección evaluada: (base, fecha, ciclo de encuestas, familia <- columnas de encuestas, familias estatales)
CASOS = {
    "2016": ("2015-12", "2016-06-26", "2016-06",
             {"PP": ["PP"], "PSOE": ["PSOE"], "CS": ["CS"], "IZQ": ["PODEMOS"], "JUNTS": ["JUNTS"],
              "PNV": ["PNV"], "BILDU": ["BILDU"]},
             ("PP", "PSOE", "CS", "IZQ")),
    "2019A": ("2016-06", "2019-04-28", "2019-04",
              {"PP": ["PP"], "PSOE": ["PSOE"], "CS": ["CS"], "VOX": ["VOX"], "IZQ": ["PODEMOS", "COMPROMIS"],
               "ERC": ["ERC"], "JUNTS": ["JUNTS"], "PNV": ["PNV"], "BILDU": ["BILDU"], "CC": ["CC"],
               "NAV_DCHA": ["NAV_DCHA"]},
              ("PP", "PSOE", "CS", "VOX", "IZQ")),
    # Más País incluye a Compromís en las encuestas de Wikipedia: no se suma COMPROMIS para no contarlo dos veces
    "2019N": ("2019-04", "2019-11-10", "2019-11",
              {"PP": ["PP"], "PSOE": ["PSOE"], "CS": ["CS"], "VOX": ["VOX"], "IZQ": ["PODEMOS", "MAS_PAIS"],
               "ERC": ["ERC"], "JUNTS": ["JUNTS"], "PNV": ["PNV"], "BILDU": ["BILDU"], "CC": ["CC"],
               "NAV_DCHA": ["NAV_DCHA"], "CUP": ["CUP"], "PRC": ["PRC"]},
              ("PP", "PSOE", "CS", "VOX", "IZQ")),
    "2023": ("2019-11", "2023-07-23", "2023-07",
             {"PP": ["PP"], "PSOE": ["PSOE"], "VOX": ["VOX"], "IZQ": ["SUMAR"], "ERC": ["ERC"], "JUNTS": ["JUNTS"],
              "PNV": ["PNV"], "BILDU": ["BILDU"], "CUP": ["CUP"], "CC": ["CC"], "BNG": ["BNG"], "NAV_DCHA": ["UPN"]},
             ("PP", "PSOE", "VOX", "IZQ")),
}
BLOQUES = {"PP": -1, "CS": -1, "VOX": -1, "NAV_DCHA": -1, "PSOE": +1, "IZQ": +1}
DERECHA = ["PP", "CS", "VOX", "NAV_DCHA"]
SALIDA = Path("resultados/validacion")


def rmse(x) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def escalas(sin: str | None) -> dict:
    """Escalas de error nacional con la regla de producción, sin la elección indicada."""
    bt = pd.read_csv("resultados/validacion/backtest_agregador.csv")
    if sin is not None:
        bt = bt[bt.ciclo.astype(str) != sin]
    bloques, internos = calcular(bt)
    sd = {}
    for signo, nombre in [(-1, "derecha"), (+1, "izquierda")]:
        b = bloques[bloques.bloque == nombre]
        sd[signo] = (rmse(b[b.dias_antes == 1].error_pp) / 100, rmse(b[b.dias_antes == 48].error_pp) / 100)
    kw = (rmse(internos[internos.dias_antes == 1].k_residuo), rmse(internos[internos.dias_antes == 48].k_residuo))
    return {"SD_BLOQUE": sd, "K_W": kw}


@contextmanager
def escalas_de(esc: dict):
    """Sustituye temporalmente las escalas del Monte Carlo (sólo dentro de este script)."""
    antes = {k: getattr(mc, k) for k in esc}
    try:
        for k, v in esc.items():
            setattr(mc, k, v)
        yield
    finally:
        for k, v in antes.items():
            setattr(mc, k, v)


def preparar_caso(ciclo: str, dias: int) -> dict:
    base_id, fecha, real_id, columnas, estatales = CASOS[ciclo]
    eleccion = pd.Timestamp(fecha)
    corte = eleccion - pd.Timedelta(days=dias)
    b, t = cargar(base_id), cargar(real_id)
    f = a_familias(b.votos); f["BLANCO"] = b.meta.blancos
    base = f.div(f.sum(axis=1), axis=0)
    real_f = a_familias(t.votos)
    presencia = (real_f > 0).reindex(columns=base.columns, fill_value=False)
    presencia[["OTROS", "BLANCO"]] = True
    pesos = b.validos

    nac = pd.read_csv("datos/encuestas/nacionales.csv")
    enc = preparar(nac[nac.ciclo.astype(str) == ciclo], corte)
    obj = {}
    for fam, cols in columnas.items():
        valores = [agregar(enc, c, corte).final[0] for c in cols if c in enc and enc[c].notna().sum() >= 5]
        # sin casas con 3+ encuestas el agregador no tiene ancla (NaN): se queda el voto de la elección base
        if valores and np.isfinite(valores).all():
            obj[fam] = sum(valores) / 100
    obj = pd.Series(obj)
    nacional = base.mul(pesos, axis=0).sum() / pesos.sum()
    nacional[obj.index] = obj
    nacional[~presencia.any()] = 0
    nacional["BLANCO"] = float((b.meta.blancos.sum()) / b.validos.sum())
    nacional["OTROS"] = 0
    nacional["OTROS"] = max(1 - nacional.sum(), 0.005)
    nacional /= nacional.sum()

    region = pd.Series(PROV_CCAA).reindex(base.index)
    nac_reg = pd.Series("España", index=base.index)
    obj_nac = nacional.to_frame("España").T
    s0 = proyectar(base, pesos, obj_nac, nac_reg, "logit", presencia)
    s0_alt = proyectar(base, pesos, obj_nac, nac_reg, "uniforme", presencia)
    s_reg = s0.mul(pesos, axis=0).groupby(region).sum().div(pesos.groupby(region).sum(), axis=0)
    sd_reg = K_REG * np.sqrt(s_reg * (1 - s_reg))
    real = escanos_reales(t).sum()
    previos = escanos_reales(b).sum()
    central = escanos_desde_cuotas(s0, pesos, t.meta.diputados).sum()
    return dict(s0=s0, s0_alt=s0_alt, nacional=nacional, region=region, sd_reg=sd_reg, escanos=t.meta.diputados,
                pesos=pesos, dias=dias, estatales=estatales, real=real, previos=previos, central=central,
                n_enc=len(enc), corte=corte)


def simular_caso(c: dict, esc: dict, semilla: int) -> pd.DataFrame:
    with escalas_de(esc):
        return mc.simular(c["s0"], c["s0_alt"], c["nacional"], c["region"], c["sd_reg"], c["escanos"], c["pesos"],
                          c["dias"], BLOQUES, estatales=c["estatales"], n_sim=N_SIM, semilla=semilla)


def evaluar(ciclo: str, dias: int, c: dict, sim: pd.DataFrame, calibracion: str) -> tuple[list, dict]:
    filas = []
    real = c["real"].reindex(sim.columns).fillna(0)
    for p in sim.columns:
        if sim[p].mean() < 0.5 and real[p] == 0:
            continue
        s = sim[p]
        q = s.quantile([0.025, 0.1, 0.5, 0.9, 0.975])
        r = real[p]
        filas.append({
            "eleccion": ciclo, "dias_antes": dias, "calibracion": calibracion, "partido": p,
            "estatal": p in c["estatales"], "real": int(r), "mediana": q[0.5], "p10": q[0.1], "p90": q[0.9],
            "p2.5": q[0.025], "p97.5": q[0.975],
            "dentro_80": bool(q[0.1] <= r <= q[0.9]), "dentro_95": bool(q[0.025] <= r <= q[0.975]),
            # percentil del resultado real (con empates repartidos): uniforme si el modelo está calibrado
            "percentil_real": float((s < r).mean() + 0.5 * (s == r).mean()),
            "error_mediana": float(q[0.5] - r),
            "error_central": float(c["central"].get(p, 0) - r),
            "error_sin_swing": float(c["previos"].get(p, 0) - r),
        })
    der = [p for p in DERECHA if p in sim]
    suma_der = sim[der].sum(axis=1)
    real_der = int(real[der].sum())
    otros = sim.drop(columns=["PP", "PSOE"]).max(axis=1)
    evento = {
        "eleccion": ciclo, "dias_antes": dias, "calibracion": calibracion, "encuestas": c["n_enc"],
        "p_derecha_176": float((suma_der >= 176).mean()), "derecha_176_real": real_der >= 176,
        "derecha_mediana": float(suma_der.median()), "derecha_real": real_der,
        "p_pp_mas_que_psoe": float((sim.PP > sim.PSOE).mean()), "pp_mas_que_psoe_real": bool(real["PP"] > real["PSOE"]),
        "p_pp_o_psoe_primero_correcto": float(((sim.PP > np.maximum(sim.PSOE, otros)) if real["PP"] > real["PSOE"]
                                               else (sim.PSOE > np.maximum(sim.PP, otros))).mean()),
    }
    return filas, evento


def brier(p, real) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(real, float)) ** 2))


def informe(partidos: pd.DataFrame, eventos: pd.DataFrame, esc_loo: dict) -> str:
    out = ["Backtest fuera de muestra (dejando fuera cada elección) del Monte Carlo de escaños",
           f"{N_SIM} simulaciones por caso; horizontes {HORIZONTES} días; elecciones {list(CASOS)}.", ""]
    out.append("Escalas usadas (error de bloque derecha / izquierda a 1 y 48 días; trasvase k):")
    for k, e in esc_loo.items():
        sd = e["SD_BLOQUE"]
        out.append(f"  {k:6s} dcha {100 * sd[-1][0]:.1f}→{100 * sd[-1][1]:.1f} pp, izda {100 * sd[+1][0]:.1f}→"
                   f"{100 * sd[+1][1]:.1f} pp, k {e['K_W'][0]:.3f}→{e['K_W'][1]:.3f}")
    out.append("")
    for cal in ["fuera de muestra", "dentro de muestra"]:
        p = partidos[partidos.calibracion == cal]
        e = eventos[eventos.calibracion == cal]
        out.append(f"== Calibración {cal}")
        for nombre, sub in [("todos los partidos", p), ("partidos estatales", p[p.estatal])]:
            out.append(f"  Cobertura ({nombre}, n = {len(sub)}): 80 % -> {100 * sub.dentro_80.mean():.0f} %, "
                       f"95 % -> {100 * sub.dentro_95.mean():.0f} %")
        out.append("  Por horizonte (estatales): " + ", ".join(
            f"{d} días: 80 % -> {100 * g.dentro_80.mean():.0f} %, 95 % -> {100 * g.dentro_95.mean():.0f} %"
            for d, g in p[p.estatal].groupby("dias_antes", sort=False)))
        est = p[p.estatal]
        out.append(f"  Error medio absoluto en escaños (estatales): mediana del modelo {est.error_mediana.abs().mean():.1f}, "
                   f"proyección central {est.error_central.abs().mean():.1f}, repetir la elección anterior "
                   f"{est.error_sin_swing.abs().mean():.1f}")
        out.append(f"  Brier P(derecha ≥ 176): {brier(e.p_derecha_176, e.derecha_176_real):.3f} "
                   f"(referencia 50 %: 0,250) | Brier P(PP > PSOE): {brier(e.p_pp_mas_que_psoe, e.pp_mas_que_psoe_real):.3f}")
        out.append("")
    loo = eventos[eventos.calibracion == "fuera de muestra"]
    out.append("Eventos, fuera de muestra:")
    out.append(loo[["eleccion", "dias_antes", "encuestas", "p_derecha_176", "derecha_mediana", "derecha_real",
                    "p_pp_mas_que_psoe", "pp_mas_que_psoe_real"]].round(3).to_string(index=False))
    out.append("")
    out.append("Partidos estatales, fuera de muestra (real frente a mediana e intervalo del 80 %):")
    est = partidos[(partidos.calibracion == "fuera de muestra") & partidos.estatal]
    out.append(est[["eleccion", "dias_antes", "partido", "real", "mediana", "p10", "p90", "percentil_real"]]
               .round(2).to_string(index=False))
    out.append("")
    out.append("Límites: 4 elecciones (2015 no tiene base); sin encuestas autonómicas; K_REG, K_PROV, margen ×1,10, "
               "correlación −0,65 y colas t(5) fijos; los horizontes de una misma elección no son independientes.")
    return "\n".join(out)


def main() -> tuple[pd.DataFrame, pd.DataFrame]:
    configurar_salida_utf8()
    produccion = {"SD_BLOQUE": dict(mc.SD_BLOQUE), "K_W": mc.K_W}
    esc_loo = {ciclo: escalas(ciclo) for ciclo in CASOS}
    partidos, eventos = [], []
    for i, ciclo in enumerate(CASOS):
        for j, dias in enumerate(HORIZONTES):
            c = preparar_caso(ciclo, dias)
            for cal, esc in [("fuera de muestra", esc_loo[ciclo]), ("dentro de muestra", produccion)]:
                sim = simular_caso(c, esc, semilla=1000 + 10 * i + j)
                f, e = evaluar(ciclo, dias, c, sim, cal)
                partidos += f
                eventos.append(e)
            print(f"  {ciclo}, {dias} días: hecho", flush=True)
    partidos, eventos = pd.DataFrame(partidos), pd.DataFrame(eventos)
    SALIDA.mkdir(exist_ok=True)
    partidos.to_csv(SALIDA / "backtest_loo.csv", index=False)
    eventos.to_csv(SALIDA / "backtest_loo_eventos.csv", index=False)
    texto = informe(partidos, eventos, esc_loo)
    (SALIDA / "backtest_loo.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return partidos, eventos


if __name__ == "__main__":
    main()
