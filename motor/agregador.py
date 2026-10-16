"""
Agregador de encuestas con efectos de casa (house effects).

Modelo, por partido (en puntos porcentuales):

    y_k = mu(t_k) + h_casa(k) + e_k            e_k ~ N(0, s_k^2)
    mu(t+1) = mu(t) + w_t                      w_t ~ N(0, q^2)      (paseo aleatorio diario)
    h_j ~ N(0, s_h^2),  sum_j c_j h_j = 0      (la industria, en conjunto, sin sesgo)

    s_k^2 = 1e4 * p(1-p) / n_ef + tau^2        error muestral + no muestral

Es un modelo lineal gaussiano: la estimación MAP se obtiene resolviendo un
sistema de mínimos cuadrados (matriz de ~700x700), y la inversa da las
incertidumbres. Nada de MCMC.

La restricción de suma cero significa que el agregador estima "lo que dice
la industria quitando los sesgos relativos entre casas". El error común de
toda la industria (el de 2023, por ejemplo) NO se puede ver aquí: se mide en
el backtest y se añade en el Monte Carlo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Misma empresa con distintos nombres en Wikipedia según el año
ALIAS_CASAS = {
    "ElectoPanel": "EM-Analytics",
    "SigmaDos": "Sigma Dos",
    "Demoscopia y Servicios": "Demoscopia Servicios",
    "GESOP": "GESOP",
}
# KeyData/Público es una media de encuestas: meterla sería contar dos veces
EXCLUIR_CASAS = {"KeyData"}
PARTIDOS_ENCARGANTES = {"PP", "PSOE", "Sumar", "Vox", "Podemos"}


@dataclass
class Resultado:
    partido: str
    serie: pd.DataFrame          # fecha, media, sd
    casas: pd.DataFrame          # casa, efecto, sd, n_encuestas
    residuo_sd: float            # desviación de los residuos (pp)

    @property
    def final(self) -> tuple[float, float]:
        f = self.serie.iloc[-1]
        return float(f.media), float(f.sd)


def preparar(df: pd.DataFrame, hasta: str | pd.Timestamp, desde: str | None = None) -> pd.DataFrame:
    """Filtra y normaliza las encuestas usables hasta una fecha (fin de campo <= hasta)."""
    e = df[df.tipo == "encuesta"].copy()
    e["inicio"] = pd.to_datetime(e.inicio)
    e["fin"] = pd.to_datetime(e.fin)
    hasta = pd.Timestamp(hasta)
    e = e[e.fin <= hasta]
    if desde:
        e = e[e.fin >= pd.Timestamp(desde)]
    e["casa"] = e.encuestadora.replace(ALIAS_CASAS)
    encargo = e.encuestadora.isin(PARTIDOS_ENCARGANTES) | e.medio.isin(PARTIDOS_ENCARGANTES)
    e = e[~encargo & ~e.casa.isin(EXCLUIR_CASAS)]
    e["t"] = e.inicio + (e.fin - e.inicio) / 2
    # Tamaño efectivo: desconocido -> 1000; tope 3000 (efecto diseño, ponderaciones)
    e["n_ef"] = e.n.fillna(1000).clip(upper=3000)
    # Re-estimaciones del mismo microdato del CIS: se reparten su muestra
    cis = e.casa.str.startswith("CIS")
    grupos = e[cis].groupby(["inicio", "fin"]).casa.transform("count")
    e.loc[cis, "n_ef"] = e.loc[cis, "n_ef"] / grupos
    return e


def agregar(
    encuestas: pd.DataFrame,
    partido: str,
    hasta: str | pd.Timestamp,
    q: float = 0.20,
    tau: float = 0.6,
    s_h: float = 2.5,
    ancla: str = "igual",
) -> Resultado:
    """
    ancla: qué casas definen el "cero" de los house effects.
      'conteo'  media ponderada por nº de encuestas (las que más publican mandan)
      'igual'   cada casa pesa lo mismo
      'sin_cis' cada casa pesa lo mismo, sin el CIS en bruto (sus re-estimaciones sí cuentan)
    """
    e = encuestas.dropna(subset=[partido])
    if e.empty:
        raise ValueError(f"sin encuestas para {partido}")
    hasta = pd.Timestamp(hasta)
    t0 = e.t.min().normalize()
    dias = pd.date_range(t0, hasta, freq="D")
    T = len(dias)
    ti = ((e.t.dt.normalize() - t0).dt.days).clip(0, T - 1).to_numpy()
    casas = sorted(e.casa.unique())
    ci = e.casa.map({c: i for i, c in enumerate(casas)}).to_numpy()
    J = len(casas)

    y = e[partido].to_numpy(float)
    p = np.clip(y / 100, 0.005, 0.995)
    var = 1e4 * p * (1 - p) / e.n_ef.to_numpy() + tau**2
    w = 1 / var

    N = T + J
    A = np.zeros((N, N))
    b = np.zeros(N)
    # Observaciones: (y - mu_t - h_j)^2 * w
    for k in range(len(y)):
        i, j = ti[k], T + ci[k]
        A[i, i] += w[k]; A[j, j] += w[k]
        A[i, j] += w[k]; A[j, i] += w[k]
        b[i] += w[k] * y[k]; b[j] += w[k] * y[k]
    # Paseo aleatorio
    qq = 1 / q**2
    for i in range(T - 1):
        A[i, i] += qq; A[i + 1, i + 1] += qq
        A[i, i + 1] -= qq; A[i + 1, i] -= qq
    # Prior débil en el nivel inicial
    A[0, 0] += 1e-4; b[0] += 1e-4 * np.average(y, weights=w)
    # Prior de los efectos de casa
    for j in range(J):
        A[T + j, T + j] += 1 / s_h**2
    # Suma cero de los efectos de casa (penalización fuerte)
    cnt = np.bincount(ci, minlength=J).astype(float)
    if ancla == "conteo":
        pesos = cnt.copy()
    else:
        pesos = (cnt >= 3).astype(float)   # casas con muy pocas encuestas no anclan
        if ancla == "sin_cis":
            pesos[[i for i, cs in enumerate(casas) if cs == "CIS"]] = 0
    c = np.zeros(N); c[T:] = pesos / pesos.sum()
    A += 1e4 * np.outer(c, c)

    cov = np.linalg.inv(A)
    x = cov @ b
    mu, h = x[:T], x[T:]
    sd_mu = np.sqrt(np.diag(cov)[:T])
    sd_h = np.sqrt(np.diag(cov)[T:])
    res = y - mu[ti] - h[ci]

    return Resultado(
        partido=partido,
        serie=pd.DataFrame({"fecha": dias, "media": mu, "sd": sd_mu}),
        casas=pd.DataFrame({"casa": casas, "efecto": h, "sd": sd_h, "n_encuestas": cnt.astype(int)})
                .sort_values("efecto"),
        residuo_sd=float(np.sqrt(np.average(res**2, weights=w))),
    )


def agregar_todos(encuestas: pd.DataFrame, partidos: list[str], hasta, **kw) -> dict[str, Resultado]:
    return {pt: agregar(encuestas, pt, hasta, **kw) for pt in partidos}
