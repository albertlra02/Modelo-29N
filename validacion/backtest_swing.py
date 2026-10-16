"""
Backtest de la capa provincial con "oráculo": le damos el resultado agregado REAL
de la elección siguiente (nacional o por CCAA) y medimos cuánto se equivoca al
repartirlo por provincias y convertirlo en escaños.

Esto aísla el error de esta capa. En la predicción real se le sumará el error
de las encuestas.
"""
from __future__ import annotations

import pandas as pd

from scripts.consola import configurar_salida_utf8
from datos.cargar import cargar
from datos.familias import OTROS, PROV_CCAA, a_familias
from motor.escanos import dhondt_exacto
from motor.swing import METODOS, escanos_desde_cuotas, proyectar

TRANSICIONES = [("2015-12", "2016-06"), ("2016-06", "2019-04"),
                ("2019-04", "2019-11"), ("2019-11", "2023-07")]
REGION_CCAA = pd.Series(PROV_CCAA)


def cuotas(e) -> pd.DataFrame:
    """Cuotas sobre votos válidos: familias + OTROS + BLANCO (filas suman 1)."""
    f = a_familias(e.votos)
    f["BLANCO"] = e.meta["blancos"]
    return f.div(f.sum(axis=1), axis=0)


def objetivos_por_region(e, region: pd.Series) -> pd.DataFrame:
    f = a_familias(e.votos)
    f["BLANCO"] = e.meta["blancos"]
    agg = f.groupby(region.reindex(f.index)).sum()
    return agg.div(agg.sum(axis=1), axis=0)


def escanos_reales(e) -> pd.DataFrame:
    filas = {}
    for prov in e.votos.index:
        votos = {p: int(x) for p, x in e.votos.loc[prov].items() if x > 0}
        filas[prov] = dhondt_exacto(votos, int(e.meta.at[prov, "diputados"]), int(e.meta.at[prov, "blancos"]))
    esc = pd.DataFrame.from_dict(filas, orient="index").fillna(0).astype(int)
    return a_familias(esc.reindex(columns=e.votos.columns, fill_value=0))


def evaluar(pred_c, real_c, pred_e, real_e) -> dict:
    cols = [c for c in real_e.columns if c != OTROS]
    pe = pred_e.reindex(index=real_e.index, columns=cols, fill_value=0)
    re = real_e[cols]
    err_prov = (pe - re).abs().sum().sum() // 2
    err_nac = (pe.sum() - re.sum()).abs().sum() // 2
    fam = [c for c in real_c.columns if c not in ("BLANCO",)]
    pc, rc = pred_c[fam], real_c[fam]
    mask = (pc > 0.01) | (rc > 0.01)
    mae = 100 * (pc - rc).abs()[mask].stack().mean()
    return {"esc_mal_provincia": int(err_prov), "esc_mal_nacional": int(err_nac), "mae_pp": round(float(mae), 2)}


def main():
    configurar_salida_utf8()
    filas = []
    for b_id, t_id in TRANSICIONES:
        B, T = cargar(b_id), cargar(t_id)
        base, real = cuotas(B), cuotas(T)
        cols = sorted(set(base.columns) | set(real.columns))
        base, real = base.reindex(columns=cols, fill_value=0), real.reindex(columns=cols, fill_value=0)
        pesos = B.validos
        presencia = real > 0
        real_esc = escanos_reales(T)
        assert real_esc[OTROS].sum() == 0

        nac = pd.Series("España", index=base.index)
        escenarios = [("sin_swing", "proporcional", nac, 0)]
        escenarios += [(m, m, nac, 50) for m in METODOS]
        escenarios += [(f"{m}+ccaa", m, REGION_CCAA, 50) for m in METODOS]

        for nombre, metodo, region, it in escenarios:
            obj = objetivos_por_region(T, region).reindex(columns=cols, fill_value=0)
            p = proyectar(base, pesos, obj, region, metodo, presencia, iteraciones=it)
            # comprobación: con calibración, el agregado debe cuadrar con el objetivo
            if it:
                agg = p.mul(pesos, axis=0).groupby(region).sum()
                agg = agg.div(agg.sum(axis=1), axis=0)
                assert (agg - obj).abs().max().max() < 2e-3, (nombre, (agg - obj).abs().max().max())
            pe = escanos_desde_cuotas(p, T.validos, T.meta["diputados"])
            filas.append({"transicion": f"{b_id}→{t_id}", "metodo": nombre, **evaluar(p, real, pe, real_esc)})

    res = pd.DataFrame(filas)
    print(res.pivot(index="metodo", columns="transicion", values="esc_mal_provincia").to_string())
    print()
    resumen = res.groupby("metodo")[["esc_mal_provincia", "esc_mal_nacional", "mae_pp"]].mean().round(1)
    print(resumen.sort_values("esc_mal_provincia").to_string())
    res.to_csv("resultados/validacion/backtest_swing.csv", index=False)
    return res


if __name__ == "__main__":
    main()
