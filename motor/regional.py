"""
Capa autonómica: corrige el reparto del swing nacional con las encuestas por CCAA.

Para cada comunidad r y partido p:

    s_rp      cuota que da el swing nacional (agregando las provincias de r)
    d_rp      desviación real de la comunidad respecto a ese swing
              prior: d ~ N(0, (k_reg * sqrt(s(1-s)))^2)      k_reg = 0,060 (histórico 2016-2023)
    y_i       cada encuesta autonómica observa s_rp + d_rp con varianza
              s(1-s)/n + tau^2 + deriva * antigüedad

La posterior de d (gaussiana conjugada) da el objetivo de cada comunidad.
Después se reimpone el total nacional: la diferencia se reparte entre
comunidades en proporción a su varianza posterior (las que tienen encuesta
reciente se mueven poco; las que no, absorben el ajuste).

Devuelve también la sd posterior de cada desviación: es la incertidumbre
regional que usa el Monte Carlo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

K_REG = 0.060      # escala de la desviación CCAA frente al swing nacional (calibrada)
TAU_REG = 0.015    # error no muestral + efecto de casa de una encuesta autonómica (1,5 pp)
DERIVA = 0.020     # la desviación regional puede moverse ~2 pp al año

NOMBRES_CCAA = {
    "Andalusia": "Andalucía", "Aragon": "Aragón", "Basque Country": "País Vasco",
    "Canary Islands": "Canarias", "Catalonia": "Cataluña", "Galicia": "Galicia",
    "Madrid": "Madrid", "Murcia": "Murcia", "Navarre": "Navarra",
    "Valencian Community": "C. Valenciana",
}
# Encuestas que no se usan: encargadas por un partido u organización con candidatura propia
EXCLUIR = [("NC Report", "European Justice"), ("GAD3", "PP")]


def cargar_encuestas_ccaa(fecha: str, antiguedad_max_dias: int = 400) -> pd.DataFrame:
    a = pd.read_csv("datos/encuestas/autonomicas.csv")
    a = a[(a.tipo == "encuesta") & a.ambito.isin(NOMBRES_CCAA)]
    for casa, medio in EXCLUIR:
        a = a[~((a.encuestadora == casa) & (a.medio == medio))]
    a["fin"] = pd.to_datetime(a.fin)
    a = a[(a.fin <= pd.Timestamp(fecha)) & (a.fin >= pd.Timestamp(fecha) - pd.Timedelta(days=antiguedad_max_dias))]
    a["ccaa"] = a.ambito.map(NOMBRES_CCAA)
    a["edad"] = (pd.Timestamp(fecha) - a.fin).dt.days
    a["n"] = a.n.fillna(800)
    # Mismo espacio que en las encuestas nacionales: Sumar incluye Compromís y CHA
    sumar = a[["SUMAR", "COMPROMIS", "CHA"]]
    a["SUMAR"] = sumar.sum(axis=1, min_count=1)
    return a


def objetivos_ccaa(
    central: pd.DataFrame,
    pesos: pd.Series,
    region: pd.Series,
    nacional: pd.Series,
    encuestas: pd.DataFrame,
    k_reg: float = K_REG,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    central:  cuotas provinciales del swing nacional (provincia x partido), filas suman 1
    nacional: cuotas nacionales objetivo (partido), suman 1
    Devuelve (objetivos por CCAA, sd posterior de la desviación, tabla de diagnóstico).
    """
    W = pesos.groupby(region).sum()
    s = central.mul(pesos, axis=0).groupby(region).sum().div(W, axis=0)
    partidos = [c for c in central.columns if c not in ("OTROS", "BLANCO")]

    d = pd.DataFrame(0.0, index=s.index, columns=central.columns)
    var_post = pd.DataFrame(0.0, index=s.index, columns=central.columns)
    diag = []
    for r in s.index:
        enc_r = encuestas[encuestas.ccaa == r]
        for p in partidos:
            sp = float(s.at[r, p])
            if sp <= 0:
                continue
            prec = 1 / (k_reg**2 * sp * (1 - sp))
            num = 0.0
            obs = enc_r[p].dropna() if p in enc_r else pd.Series(dtype=float)
            for i in obs.index:
                y = obs[i] / 100
                v = y * (1 - y) / enc_r.at[i, "n"] + TAU_REG**2 + DERIVA**2 * enc_r.at[i, "edad"] / 365
                prec += 1 / v
                num += (y - sp) / v
            d.at[r, p] = num / prec
            var_post.at[r, p] = 1 / prec
            if len(obs):
                diag.append({"ccaa": r, "partido": p, "swing_nacional": 100 * sp, "encuestas": len(obs),
                             "media_encuestas": float(obs.mean()), "objetivo": 100 * (sp + num / prec)})

    t = (s + d).clip(lower=0)
    # Reimponer el total nacional, repartiendo el ajuste según la varianza posterior
    for _ in range(20):
        for p in partidos:
            agg = float((t[p] * W).sum() / W.sum())
            v = var_post[p].where(t[p] > 0, 0)
            if (v * W).sum() > 0:
                lam = (nacional[p] - agg) * W.sum() / float((v * W).sum())
                t[p] = (t[p] + lam * v).clip(lower=0)
        resto = [c for c in t.columns if c not in partidos]
        t[resto] = t[resto].mul(nacional[resto] / (t[resto].mul(W, axis=0).sum() / W.sum()), axis=1)
        t = t.div(t.sum(axis=1), axis=0)
    return t, np.sqrt(var_post), pd.DataFrame(diag)
