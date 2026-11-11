import numpy as np
import pandas as pd

from motor.montecarlo import (_agregado_nacional, _ajustar_margenes_nacionales,
                              _factores_bloque, k_nacional, resumen, simular)


def _caso():
    provs = ["a", "b", "c"]
    s0 = pd.DataFrame({"X": [0.5, 0.4, 0.3], "Y": [0.3, 0.4, 0.5], "R": [0.0, 0.0, 0.1],
                       "OTROS": [0.19, 0.19, 0.09], "BLANCO": [0.01, 0.01, 0.01]}, index=provs)
    pesos = pd.Series([100.0, 100.0, 100.0], index=provs)
    region = pd.Series(["N", "N", "S"], index=provs)
    nacional = s0.mul(pesos, axis=0).sum() / pesos.sum()
    sd_reg = pd.DataFrame(0.01, index=["N", "S"], columns=s0.columns)
    escanos = pd.Series([5, 3, 2], index=provs)
    return s0, pesos, region, nacional, sd_reg, escanos


def test_reparte_todos_los_escanos_y_respeta_ausencias():
    s0, pesos, region, nac, sd_reg, esc = _caso()
    sim = simular(s0, s0, nac, region, sd_reg, esc, pesos, dias=30, bloques={"X": -1, "Y": 1},
                  estatales=("X", "Y"), mezclar=("X",), n_sim=500)
    assert (sim.sum(axis=1) == 10).all()
    assert set(sim.columns) == {"X", "Y", "R"}
    assert sim.R.max() <= 2   # R solo se presenta en la provincia c (2 escaños)


def test_reproducible_con_semilla():
    s0, pesos, region, nac, sd_reg, esc = _caso()
    a = simular(s0, s0, nac, region, sd_reg, esc, pesos, 30, {}, mezclar=("X",), n_sim=200, semilla=1)
    b = simular(s0, s0, nac, region, sd_reg, esc, pesos, 30, {}, mezclar=("X",), n_sim=200, semilla=1)
    assert a.equals(b)


def test_incertidumbre_crece_con_la_distancia():
    assert k_nacional(1) < k_nacional(14) < k_nacional(48)
    assert np.isclose(k_nacional(48), 0.095, atol=1e-3)


def test_factores_t_tienen_varianza_y_correlacion_configuradas():
    rng = np.random.default_rng(42)
    factores, _ = _factores_bloque(rng, 250_000, correlacion=-0.6, gl_colas=5)
    dcha, izda = factores[-1][:, 0], factores[+1][:, 0]
    assert np.isclose(dcha.std(), 1.0, atol=0.035)
    assert np.isclose(izda.std(), 1.0, atol=0.035)
    assert np.isclose(np.corrcoef(dcha, izda)[0, 1], -0.6, atol=0.02)


def test_ipf_reimpone_margenes_nacionales_y_respeta_ausencias():
    s = np.array([
        [[0.50, 0.30, 0.20], [0.40, 0.60, 0.00], [0.20, 0.30, 0.50]],
        [[0.35, 0.25, 0.40], [0.55, 0.45, 0.00], [0.15, 0.25, 0.60]],
    ])
    pesos = np.array([100.0, 200.0, 300.0])
    objetivos = np.array([[0.30, 0.36, 0.34], [0.24, 0.31, 0.45]])
    ausencias = s == 0
    ajustado = _ajustar_margenes_nacionales(s, pesos, objetivos, iteraciones=40)
    assert np.allclose(_agregado_nacional(ajustado, pesos), objetivos, atol=3e-6)
    assert (ajustado[ausencias] == 0).all()
    assert np.allclose(ajustado.sum(axis=2), 1.0)


def test_primero_compara_con_todos_los_partidos():
    sim = pd.DataFrame({"PP": [5, 5], "PSOE": [4, 4], "X": [6, 3]})
    _, probs = resumen(sim, {})
    assert probs["P(PP primero)"] == 0.5
