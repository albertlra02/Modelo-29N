"""
Monte Carlo de escaños.

Cada simulación perturba la proyección central en escala logit con cuatro fuentes
de error, todas calibradas con datos:

1. Error nacional (solo partidos de ámbito estatal), en dos niveles:

   a) Error de bloque. El voto total de la derecha estatal (PP, Vox, SALF) y el de la
      izquierda estatal (PSOE, Sumar, Podemos) fallan en sentido contrario
      (correlación -0,65). Medido en el backtest del agregador (2015–2023):
                       víspera    30-48 días
          derecha      2,1 pp     3,6 pp
          izquierda    1,8 pp     3,6 pp
      El error del bloque se reparte entre sus partidos en proporción a su cuota.

   b) Trasvase dentro del bloque (suma cero dentro de cada bloque):
      sd = k_w(h) * sqrt(s(1-s)),  k_w = 0,035 en la víspera y 0,095 a 48 días.

   Entre la víspera y 48 días se interpola en varianza (crece como un paseo aleatorio).

2. Desviación autonómica: sd posterior de la capa CCAA (pequeña donde hay encuestas
   recientes, k_reg = 0,060 donde no las hay). Se centra para no tocar el total nacional.

3. Ruido provincial dentro de cada CCAA: k_prov = 0,026 (histórico 2016-2023).

4. Forma del reparto de Vox: en cada simulación se mezcla la proyección logit y la
   uniforme con un peso aleatorio, porque el histórico no decide cuál acertará.

Después: D'Hondt vectorizado en cada provincia (OTROS y BLANCO cuentan para el 3 %
pero no reciben escaños).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from motor.escanos import dhondt_vectorizado

SD_BLOQUE = {-1: (0.021, 0.036), +1: (0.018, 0.036)}   # (víspera, 48 días): derecha, izquierda
CORR_BLOQUES = -0.65
INFLACION_BLOQUE = 1.10  # pequeño margen por sólo cinco elecciones históricas
GL_COLAS = 5            # colas gruesas (t de Student, 5 g.l.): los grandes errores electorales no son normales
K_W = (0.035, 0.095)
K_PROV = 0.026
NO_LISTAS = ("OTROS", "BLANCO")


def interpolar(par: tuple[float, float], dias: int) -> float:
    """Interpola en varianza entre la víspera (1 día) y 48 días; más allá, sigue creciendo igual."""
    v1, v48 = par
    c = (v48**2 - v1**2) / 47
    return float(np.sqrt(v1**2 + c * max(dias - 1, 0)))


def k_nacional(dias: int) -> float:
    """Escala del trasvase dentro de bloque (se mantiene el nombre por compatibilidad)."""
    return interpolar(K_W, dias)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _factores_bloque(
    rng: np.random.Generator,
    n_sim: int,
    correlacion: float = CORR_BLOQUES,
    gl_colas: int | None = GL_COLAS,
) -> tuple[dict[int, np.ndarray], np.ndarray]:
    """Factores derecha/izquierda con varianza uno y la correlación indicada.

    Con ``gl_colas`` se genera una t multivariante: todos los factores normales
    comparten la misma escala chi-cuadrado en cada simulación. El multiplicador
    ``sqrt((gl-2)/chi2)`` deja varianza marginal uno cuando gl > 2.
    """
    if not -1 < correlacion <= 0:
        raise ValueError("la correlación entre bloques debe estar en (-1, 0]")
    if gl_colas is not None and gl_colas <= 2:
        raise ValueError("la t de Student necesita más de 2 grados de libertad")

    comun = rng.standard_normal((n_sim, 1))       # positivo = izquierda sube
    id_dcha = rng.standard_normal((n_sim, 1))
    id_izda = rng.standard_normal((n_sim, 1))
    if gl_colas:
        escala_t = np.sqrt((gl_colas - 2) / rng.chisquare(gl_colas, size=(n_sim, 1)))
        comun *= escala_t
        id_dcha *= escala_t
        id_izda *= escala_t

    a = np.sqrt(-correlacion)
    b = np.sqrt(1 - a**2)
    return {-1: -a * comun + b * id_dcha, +1: a * comun + b * id_izda}, comun


def _agregado_nacional(s: np.ndarray, pesos: np.ndarray) -> np.ndarray:
    """Cuotas nacionales de un tensor (simulación, provincia, partido)."""
    return np.einsum("nrp,r->np", s, pesos, optimize=True) / pesos.sum()


def _ajustar_margenes_nacionales(
    s: np.ndarray,
    pesos: np.ndarray,
    objetivos: np.ndarray,
    iteraciones: int = 12,
    tolerancia: float = 2e-6,
) -> np.ndarray:
    """IPF vectorizado para que cada simulación respete sus cuotas nacionales.

    Conserva los ceros estructurales (candidaturas ausentes) y modifica ``s``
    en el sitio para evitar otra copia grande del tensor Monte Carlo.
    """
    objetivos = np.clip(np.asarray(objetivos, dtype=float), 0, None)
    objetivos /= objetivos.sum(axis=1, keepdims=True)
    for _ in range(iteraciones):
        actual = _agregado_nacional(s, pesos)
        imposible = (objetivos > tolerancia) & (actual <= 0)
        if imposible.any():
            raise ValueError("objetivo nacional positivo para una candidatura ausente")
        factor = np.divide(objetivos, actual, out=np.ones_like(actual), where=actual > 0)
        s *= factor[:, None, :]
        s /= s.sum(axis=2, keepdims=True)
        if np.max(np.abs(_agregado_nacional(s, pesos) - objetivos)) < tolerancia:
            break
    return s


def simular(
    s0: pd.DataFrame,
    s0_alt: pd.DataFrame,
    nacional: pd.Series,
    region: pd.Series,
    sd_reg: pd.DataFrame,
    escanos: pd.Series,
    pesos: pd.Series,
    dias: int,
    bloques: dict[str, int],
    mezclar: tuple[str, ...] = ("VOX",),
    estatales: tuple[str, ...] | None = None,
    n_sim: int = 10_000,
    semilla: int = 2026,
    detalle: bool = False,
    por_provincia: bool = False,
):
    """
    Devuelve un DataFrame (n_sim x partido) con los escaños nacionales de cada simulación.
    detalle=True devuelve además (sim, info): voto nacional simulado por partido, peso
    logit/uniforme de Vox y factor de bloque. por_provincia=True añade los escaños
    por provincia (dict provincia -> array n_sim x listas).
    """
    rng = np.random.default_rng(semilla)
    provs = list(s0.index)
    partidos = list(s0.columns)
    listas = [p for p in partidos if p not in NO_LISTAS]
    P, R = len(partidos), len(provs)
    ip = {p: i for i, p in enumerate(partidos)}

    # 1. Error nacional: bloque + trasvase interno. Solo partidos estatales; los de una
    #    sola comunidad tienen su incertidumbre en la capa autonómica (paso 2).
    s_nac = nacional.reindex(partidos).fillna(0).to_numpy()
    est = np.array([(estatales is None or p in estatales) and p not in NO_LISTAS for p in partidos])
    signo = np.array([bloques.get(p, 0) for p in partidos], float) * est
    e = np.zeros((n_sim, P))
    factores_bloque, z_blq = _factores_bloque(rng, n_sim)
    kw = k_nacional(dias)
    for sg in (-1, +1):
        miembros = signo == sg
        if not miembros.any():
            continue
        sd_b = INFLACION_BLOQUE * interpolar(SD_BLOQUE[sg], dias)
        E_b = sd_b * factores_bloque[sg]
        s_b = s_nac[miembros]
        e[:, miembros] += E_b * s_b / s_b.sum()
        w = kw * np.sqrt(s_b * (1 - s_b)) * rng.standard_normal((n_sim, miembros.sum()))
        w -= w.sum(axis=1, keepdims=True) * s_b / s_b.sum()       # suma cero dentro del bloque
        e[:, miembros] += w
    # estatales sin bloque asignado: solo error individual
    sueltos = est & (signo == 0)
    e[:, sueltos] += kw * np.sqrt(s_nac[sueltos] * (1 - s_nac[sueltos])) * rng.standard_normal((n_sim, sueltos.sum()))
    objetivo_nac = np.clip(s_nac[None, :] + e, 1e-8, None)
    objetivo_nac /= objetivo_nac.sum(axis=1, keepdims=True)
    delta_nac = _logit(objetivo_nac) - _logit(s_nac)             # (n_sim, P)

    # 2. Desviación autonómica (centrada por partido para no mover el total nacional)
    ccaa = sorted(region.unique())
    ir = region.map({c: i for i, c in enumerate(ccaa)}).to_numpy()
    W = pesos.groupby(region).sum().reindex(ccaa).to_numpy()
    s_reg = s0.mul(pesos, axis=0).groupby(region).sum().div(pesos.groupby(region).sum(), axis=0).reindex(ccaa)
    sdr = sd_reg.reindex(index=ccaa, columns=partidos).fillna(0).to_numpy()
    sr = s_reg.reindex(columns=partidos).fillna(0).to_numpy()
    sd_logit_reg = np.where(sr > 0, sdr / np.maximum(sr * (1 - sr), 1e-4), 0.0)
    eta = rng.standard_normal((n_sim, len(ccaa), P)) * sd_logit_reg
    centrar = np.array([estatales is None or p in estatales for p in partidos])
    media = (eta * (W * 1.0)[None, :, None]).sum(axis=1, keepdims=True) / W.sum()
    eta -= np.where(centrar, media, 0.0)

    # 3. Ruido provincial
    S0 = s0.to_numpy()
    sd_logit_prov = np.where(S0 > 0, K_PROV / np.sqrt(np.maximum(S0 * (1 - S0), 1e-4)), 0.0)
    eps = rng.standard_normal((n_sim, R, P)) * sd_logit_prov

    # 4. Mezcla de formas de reparto para los partidos indicados
    base = np.broadcast_to(S0, (n_sim, R, P)).copy()
    lam = rng.uniform(0, 1, size=(n_sim, 1))
    for p in mezclar:
        j = ip[p]
        base[:, :, j] = lam * S0[:, j] + (1 - lam) * s0_alt.to_numpy()[:, j]

    L = _logit(base) + delta_nac[:, None, :] + eta[:, ir, :] + eps
    S = 1 / (1 + np.exp(-L))
    S = np.where(base > 0, S, 0.0)
    S /= S.sum(axis=2, keepdims=True)

    # El paso por logit, el ruido territorial y la normalización provincial
    # desplazan los márgenes nacionales. Se vuelven a imponer para los partidos
    # estatales; el resto conserva su reparto nacional relativo simulado.
    w = pesos.reindex(provs).to_numpy(float)
    actual_nac = _agregado_nacional(S, w)
    objetivo_final = actual_nac.copy()
    objetivo_final[:, est] = objetivo_nac[:, est]
    no_est = ~est
    masa_no_est = 1 - objetivo_final[:, est].sum(axis=1, keepdims=True)
    base_no_est = actual_nac[:, no_est]
    objetivo_final[:, no_est] = base_no_est * np.divide(
        masa_no_est,
        base_no_est.sum(axis=1, keepdims=True),
        out=np.zeros_like(masa_no_est),
        where=base_no_est.sum(axis=1, keepdims=True) > 0,
    )
    S = _ajustar_margenes_nacionales(S, w, objetivo_final)

    # D'Hondt por provincia
    il = [ip[p] for p in listas]
    inl = [ip[p] for p in NO_LISTAS if p in ip]
    total = np.zeros((n_sim, len(listas)), dtype=int)
    prov_esc = {}
    for r, prov in enumerate(provs):
        votos = S[:, r, il]
        blancos = S[:, r, inl].sum(axis=1)
        esc_r = dhondt_vectorizado(votos, int(escanos[prov]), blancos)
        total += esc_r
        if por_provincia:
            prov_esc[prov] = esc_r
    sim = pd.DataFrame(total, columns=listas)
    if not (detalle or por_provincia):
        return sim
    voto_nac = _agregado_nacional(S, w)
    info = pd.DataFrame(voto_nac, columns=partidos)
    info["peso_logit_vox"] = lam[:, 0]
    info["factor_bloque"] = z_blq[:, 0]
    return sim, info, prov_esc


def resumen(sim: pd.DataFrame, bloques_mayoria: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.Series]:
    q = sim.quantile([0.025, 0.1, 0.5, 0.9, 0.975]).T
    q.columns = ["p2.5", "p10", "mediana", "p90", "p97.5"]
    q["media"] = sim.mean()
    q = q.sort_values("media", ascending=False)
    probs = {}
    for nombre, partidos in bloques_mayoria.items():
        probs[f"P({nombre} ≥ 176)"] = float((sim[[p for p in partidos if p in sim]].sum(axis=1) >= 176).mean())
    probs["P(PP primero)"] = float((sim.PP > sim.drop(columns="PP").max(axis=1)).mean())
    return q, pd.Series(probs)
